"""Microsoft の AI 系ブログ用スクレイパー。

旧 blogs.microsoft.com/ai/ は news.microsoft.com の "Source" サイトへ移行。
AIトピックの一覧から、記事（/source/.../features/... 等）を見出し起点で収集する。
"""

from config import ARTICLES_PER_SITE
from scrapers.base import BaseScraper

LIST_URL = "https://news.microsoft.com/source/topics/ai/"
ARTICLE_HREF = "/source/"  # 記事は /source/features/... 等。topics/tag はナビ
WAIT_SELECTOR = "main h2, main h3"


class MicrosoftScraper(BaseScraper):
    company = "Microsoft"
    base_url = "https://news.microsoft.com"

    def fetch_articles(self) -> list[dict]:
        if not self.goto(LIST_URL, WAIT_SELECTOR):
            return []
        articles = self.collect_by_heading(ARTICLE_HREF, ARTICLES_PER_SITE, exclude_url=LIST_URL)
        return self.warn_if_empty(articles)
