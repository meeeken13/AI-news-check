"""OpenAI News (https://openai.com/news/) 用スクレイパー。"""

from config import ARTICLES_PER_SITE
from scrapers.base import BaseScraper

LIST_URL = "https://openai.com/news/"
ARTICLE_HREF = "/index/"  # OpenAIの個別記事は /index/<slug>/ 形式
WAIT_SELECTOR = "a[href*='/index/']"


class OpenAIScraper(BaseScraper):
    company = "OpenAI"
    base_url = "https://openai.com"

    def fetch_articles(self) -> list[dict]:
        if not self.goto(LIST_URL, WAIT_SELECTOR):
            return []
        # OpenAIのカードは見出しタグを使わないのでアンカー起点で収集。
        found = self.collect_by_href(ARTICLE_HREF, ARTICLES_PER_SITE + 5)
        # /research/index/ などナビは /index/ 直後にslugが無いので除外。
        articles = [
            a for a in found if not a["url"].rstrip("/").endswith("/index")
        ][:ARTICLES_PER_SITE]
        return self.warn_if_empty(articles)
