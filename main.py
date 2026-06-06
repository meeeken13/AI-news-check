"""エントリポイント: スクレイプ → 新規抽出 → Claude生成 → Sheets書込。"""

from __future__ import annotations

import importlib
import logging
import time
from datetime import datetime, timedelta, timezone

from playwright.sync_api import sync_playwright

import config
from claude_client import generate_note_article
from sheets_client import SheetsClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def _load_scraper(site: dict, page):
    """config.SITES の1エントリからスクレイパーインスタンスを生成。"""
    module = importlib.import_module(f"scrapers.{site['module']}")
    klass = getattr(module, site["klass"])
    return klass(page)


def _is_fresh(published: str | None) -> bool:
    """公開日時が鮮度ウィンドウ内か。取得できない(None)場合は通す。"""
    if not published:
        return True
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return True  # パースできなければ除外しない
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.FRESHNESS_HOURS)
    return dt >= cutoff


def scrape_all(page) -> list[dict]:
    """全サイトをスクレイプして記事を集約する。"""
    collected: list[dict] = []
    for site in config.SITES:
        try:
            scraper = _load_scraper(site, page)
            articles = scraper.fetch_articles()
            logger.info("[%s] %d件取得 (%s)", site["company"], len(articles), site["url"])
            collected.extend(articles)
        except Exception as e:  # noqa: BLE001 - 1サイトの失敗で全体を止めない
            logger.warning("[%s] スクレイプ失敗: %s", site["company"], e)
        time.sleep(config.REQUEST_DELAY)  # アクセス間隔（マナー）
    return collected


def main() -> None:
    sheets = SheetsClient()
    processed_urls = sheets.fetch_processed_urls()
    logger.info("処理済みURL: %d件", len(processed_urls))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=config.USER_AGENT)
        try:
            articles = scrape_all(page)
        finally:
            browser.close()

    # 鮮度フィルタ ＋ 重複チェックで新規記事を抽出。
    # 実行内重複も除外（DeepMindのblog.googleクロス投稿がGoogle AIと衝突しうる）。
    new_articles: list[dict] = []
    seen_urls: set[str] = set()
    for a in articles:
        if a["url"] in processed_urls or a["url"] in seen_urls:
            continue
        if not _is_fresh(a["published"]):
            continue
        seen_urls.add(a["url"])
        new_articles.append(a)
    logger.info("新規候補: %d件 / 全%d件", len(new_articles), len(articles))

    processed_count = 0
    for article in new_articles[: config.MAX_PER_RUN]:
        try:
            note = generate_note_article(article)
            sheets.append_generated(article, note)
            sheets.append_processed(article)
            processed_count += 1
            logger.info("生成・書込完了: %s", note["title"])
            time.sleep(config.GEN_DELAY)  # API負荷対策
        except Exception as e:  # noqa: BLE001 - 1記事の失敗で全体を止めない
            logger.warning("記事処理失敗 (%s): %s", article["url"], e)

    logger.info("完了: %d件を生成・書込", processed_count)


if __name__ == "__main__":
    main()
