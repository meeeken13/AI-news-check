"""Google AI Blog (https://blog.google/technology/ai/) 用スクレイパー。

現行サイトはカテゴリ階層型ハブで、記事URLは /innovation-and-ai/...,
/products-and-platforms/..., /company-news/... など多様。記事リンクの
パスでは絞れないため、見出し（記事タイトル）起点で収集する。
"""

from config import ARTICLES_PER_SITE
from scrapers.base import BaseScraper

LIST_URL = "https://blog.google/technology/ai/"
WAIT_SELECTOR = "main h2, main h3"


class GoogleAIScraper(BaseScraper):
    company = "Google AI"
    base_url = "https://blog.google"

    def fetch_articles(self) -> list[dict]:
        if not self.goto(LIST_URL, WAIT_SELECTOR):
            return []
        # blog.google 内部リンクであればよい（pat=""）。一覧自身は除外。
        articles = self.collect_by_heading("", ARTICLES_PER_SITE, exclude_url=LIST_URL)
        return self.warn_if_empty(articles)
