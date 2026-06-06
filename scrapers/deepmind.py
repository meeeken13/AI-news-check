"""Google DeepMind Blog 用スクレイパー。

注意: 旧 `/discover/blog/` は `https://deepmind.google/blog/` にリダイレクトする
JSレンダリングのSPA。記事リンクは2種類が混在する:
  - ネイティブ:  https://deepmind.google/blog/<slug>
  - クロス投稿:  https://blog.google/innovation-and-ai/.../<slug>
そのため単一のhrefパターンでは絞れず、見出し起点で集めてから両形式で絞る。
ナビ（/models/ /research/ /about/ 等）はこの絞り込みで除外される。
"""

from config import ARTICLES_PER_SITE
from scrapers.base import BaseScraper

LIST_URL = "https://deepmind.google/blog/"
# ネイティブ記事リンクの出現を待つ（JS描画。ナビより遅れて入る）。
WAIT_SELECTOR = "a[href*='/blog/']"


def _is_article(url: str) -> bool:
    """記事リンクか判定（ネイティブ /blog/<slug> か blog.google 記事）。"""
    if "blog.google/" in url:
        return True
    # deepmind.google/blog/<slug> で slug が空でないもの（一覧自身を除く）
    return "deepmind.google/blog/" in url and url.rstrip("/").split("/blog/")[-1] != ""


class DeepMindScraper(BaseScraper):
    company = "DeepMind"
    base_url = "https://deepmind.google"

    def fetch_articles(self) -> list[dict]:
        if not self.goto(LIST_URL, WAIT_SELECTOR):
            return []
        found = self.collect_by_heading("", ARTICLES_PER_SITE + 10, exclude_url=LIST_URL)
        articles = [a for a in found if _is_article(a["url"])][:ARTICLES_PER_SITE]
        return self.warn_if_empty(articles)
