"""エントリポイント: スクレイプ → 新規抽出 → 日付付与 → Claude生成 → Sheets書込。"""

from __future__ import annotations

import importlib
import logging
import time
from datetime import datetime, timedelta, timezone

from playwright.sync_api import sync_playwright

import config
from claude_client import generate_detailed_article, generate_note_article
from dates import extract_content, extract_published, fmt_date, parse_published
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


def dedup(articles: list[dict], processed_urls: set[str]) -> list[dict]:
    """処理済みURL・実行内重複を除外して新規候補を返す。

    実行内重複はDeepMindのblog.googleクロス投稿がGoogle AIと衝突するため必要。
    """
    out: list[dict] = []
    seen: set[str] = set()
    for a in articles:
        if a["url"] in processed_urls or a["url"] in seen:
            continue
        seen.add(a["url"])
        out.append(a)
    return out


def enrich_dates(page, articles: list[dict]) -> None:
    """各候補に公開日を付与する。

    scraperが既にpublishedを入れていれば（Anthropic）記事ページ取得は省く。
    結果を ``_dt``（datetime|None）として各dictに格納する。
    """
    for a in articles:
        raw = a.get("published")
        if not raw:
            raw = extract_published(page, a["url"])
            a["published"] = raw
            time.sleep(config.REQUEST_DELAY)  # アクセス間隔（マナー）
        dt = parse_published(raw)
        if dt is None and config.UNDATED_FALLBACK_TODAY:
            # 公開日が取れない記事は取得日(実行日)で補完し取りこぼさない。推定印を付ける。
            dt = datetime.now(timezone.utc)
            a["date_estimated"] = True
        a["_dt"] = dt


def filter_fresh(articles: list[dict]) -> list[dict]:
    """鮮度ウィンドウ内の記事のみ残し、新しい順に並べる。

    公開日不明は enrich_dates 側で取得日に補完済み（UNDATED_FALLBACK_TODAY=True時）。
    補完しない設定では _dt が None のままなのでスキップする。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.FRESHNESS_HOURS)
    fresh: list[dict] = []
    for a in articles:
        dt = a.get("_dt")
        if dt is None:
            logger.warning("公開日不明のためスキップ: %s", a["url"])
            continue
        if dt >= cutoff:
            fresh.append(a)
    # 新しい順（日付不明は末尾）
    fresh.sort(key=lambda x: x.get("_dt") or datetime.min.replace(tzinfo=timezone.utc),
               reverse=True)
    return fresh


def main() -> None:
    sheets = SheetsClient()
    processed_urls = sheets.fetch_processed_urls()
    logger.info("処理済みURL: %d件", len(processed_urls))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=config.USER_AGENT)
        try:
            articles = scrape_all(page)
            candidates = dedup(articles, processed_urls)
            logger.info("新規候補(重複除外後): %d件 / 全%d件", len(candidates), len(articles))
            enrich_dates(page, candidates)  # 公開日の取得はブラウザを開いている間に
            targets = filter_fresh(candidates)[: config.MAX_PER_RUN]
            logger.info("鮮度フィルタ後: %d件（%d時間以内）", len(targets), config.FRESHNESS_HOURS)
            # 詳細記事を公式情報に基づかせるため、対象記事の本文を取得（ブラウザを開いている間に）
            for a in targets:
                a["content"] = extract_content(page, a["url"])
                time.sleep(config.REQUEST_DELAY)
        finally:
            browser.close()

    processed_count = 0
    for article in targets:
        try:
            article["published_str"] = fmt_date(article.get("_dt"))
            note = generate_note_article(article)        # 速報
            detail = generate_detailed_article(article)  # 詳しい解説（公式記事）
            sheets.append_generated(article, note, detail)
            sheets.append_processed(article)
            processed_count += 1
            logger.info("生成・書込完了: [%s] %s（速報＋詳細）", article["published_str"], note["title"])
            time.sleep(config.GEN_DELAY)  # API負荷対策
        except Exception as e:  # noqa: BLE001 - 1記事の失敗で全体を止めない
            logger.warning("記事処理失敗 (%s): %s", article["url"], e)

    logger.info("完了: %d件を生成・書込", processed_count)


if __name__ == "__main__":
    main()
