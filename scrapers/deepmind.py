"""Google DeepMind Blog (https://deepmind.google/discover/blog/) 用スクレイパー。"""

from config import ARTICLES_PER_SITE
from scrapers.base import BaseScraper

LIST_URL = "https://deepmind.google/discover/blog/"
ARTICLE_HREF = "/discover/blog/"
WAIT_SELECTOR = "a[href*='/discover/blog/']"


class DeepMindScraper(BaseScraper):
    company = "DeepMind"
    base_url = "https://deepmind.google"

    def fetch_articles(self) -> list[dict]:
        if not self.goto(LIST_URL, WAIT_SELECTOR):
            return []
        articles = [
            a for a in self.collect_by_href(ARTICLE_HREF, ARTICLES_PER_SITE + 5)
            if a["url"].rstrip("/") != LIST_URL.rstrip("/")
        ][:ARTICLES_PER_SITE]
        return self.warn_if_empty(articles)
