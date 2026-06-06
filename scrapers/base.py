"""スクレイパー基底クラスと共通ユーティリティ。"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class BaseScraper:
    """各サイト用スクレイパーの基底クラス。

    サブクラスは ``company``・``base_url``（相対URL解決用）を定義し、
    ``fetch_articles`` を実装する。
    """

    company: str = ""
    base_url: str = ""

    def __init__(self, page: Page):
        self.page = page

    def fetch_articles(self) -> list[dict]:
        """記事一覧を返す。

        返す形式: ``{"title": str, "url": str, "published": str | None,
        "company": str}`` のリスト。
        取得失敗時は空リストを返し、処理を止めない。
        """
        raise NotImplementedError

    # --- 共通ユーティリティ ---

    def goto(self, url: str, wait_selector: str | None = None) -> bool:
        """ページ遷移し、必要ならJS描画完了（セレクタ出現）を待つ。

        成功で True、失敗で False（呼び出し側は空リストを返せる）。
        """
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if wait_selector:
                self.page.wait_for_selector(wait_selector, timeout=15000)
            return True
        except PlaywrightTimeoutError:
            logger.warning("[%s] タイムアウト: %s (selector=%s)", self.company, url, wait_selector)
            return False
        except Exception as e:  # noqa: BLE001 - スクレイプ失敗で全体を止めない
            logger.warning("[%s] ページ取得失敗: %s (%s)", self.company, url, e)
            return False

    def absolute_url(self, href: str) -> str:
        """相対URLを絶対URLに変換する。"""
        return urljoin(self.base_url, href)

    def warn_if_empty(self, articles: list[dict]) -> list[dict]:
        """0件なら警告ログ（セレクタ破損の早期検知）。リストはそのまま返す。"""
        if not articles:
            logger.warning("[%s] 記事を1件も取得できませんでした。セレクタ要確認。", self.company)
        return articles

    # 見出し要素から記事を収集するJS。見出しテキストをタイトルに使い、
    # 見出しの近傍（祖先・子孫）から記事リンクを辿る。深いCSSセレクタより
    # サイト改修に強く、カテゴリ/ナビのラベルをタイトルに拾いにくい。
    _COLLECT_JS = """
    (pat) => {
      const out = [];
      const seen = new Set();
      const heads = document.querySelectorAll('h1,h2,h3,h4');
      for (const h of heads) {
        const title = (h.innerText || '').trim().split('\\n')[0].trim();
        if (!title || title.length < 10) continue;
        // 見出しから最大5階層さかのぼってアンカーを探す
        let a = null, el = h;
        for (let i = 0; i < 5 && el; i++) {
          if (el.tagName === 'A' && el.getAttribute('href')) { a = el; break; }
          const found = el.querySelector ? el.querySelector('a[href]') : null;
          if (found) { a = found; break; }
          el = el.parentElement;
        }
        if (!a) continue;
        const href = a.getAttribute('href') || '';
        if (!href || href.startsWith('#') || href.startsWith('javascript:')) continue;
        if (pat && !href.includes(pat)) continue;
        if (seen.has(href)) continue;
        seen.add(href);
        out.push({ title, href });
      }
      return out;
    }
    """

    def collect_by_href(self, href_contains: str, limit: int,
                        exclude_url: str = "") -> list[dict]:
        """``href`` に特定パスを含むアンカーを記事として収集する。

        見出しを持たないカード構造（例: OpenAI）向け。タイトルはアンカー
        テキストの最初の行。公開日は取れないので None。
        """
        anchors = self.page.locator(f'a[href*="{href_contains}"]')
        results: list[dict] = []
        seen: set[str] = set()
        exclude = exclude_url.rstrip("/")
        for i in range(anchors.count()):
            a = anchors.nth(i)
            href = a.get_attribute("href") or ""
            title = (a.inner_text() or "").strip().split("\n")[0].strip()
            if not href or not title or len(title) < 8:
                continue
            url = self.absolute_url(href)
            if url.rstrip("/") == exclude or url in seen:
                continue
            seen.add(url)
            results.append({
                "title": title,
                "url": url,
                "published": None,
                "company": self.company,
            })
            if len(results) >= limit:
                break
        return results

    def collect_by_heading(self, href_contains: str, limit: int,
                           exclude_url: str = "") -> list[dict]:
        """見出し要素を起点に記事を収集する汎用ヘルパー。

        href_contains: 記事リンクが含むべきパス（""なら任意の内部リンク）。
        exclude_url:   一覧ページ自身など除外したいURL。
        公開日はここでは取れないので None。
        """
        raw = self.page.evaluate(self._COLLECT_JS, href_contains)
        results: list[dict] = []
        seen: set[str] = set()
        exclude = exclude_url.rstrip("/")
        for item in raw:
            url = self.absolute_url(item["href"])
            if url.rstrip("/") == exclude or url in seen:
                continue
            seen.add(url)
            results.append({
                "title": item["title"],
                "url": url,
                "published": None,
                "company": self.company,
            })
            if len(results) >= limit:
                break
        return results
