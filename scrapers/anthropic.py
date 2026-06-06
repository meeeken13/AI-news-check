"""Anthropic 公式ブログ用スクレイパー（News / Engineering）。

どちらも同じDOM構造のため、一覧URLと記事パスだけ差し替えて共通化する。
"""

from config import ARTICLES_PER_SITE
from scrapers.base import BaseScraper


class _AnthropicBase(BaseScraper):
    company = "Anthropic"
    base_url = "https://www.anthropic.com"

    list_url: str = ""
    article_href: str = ""

    def fetch_articles(self) -> list[dict]:
        # 記事カードのリンク出現を待つ（JS描画）。
        if not self.goto(self.list_url, f'a[href*="{self.article_href}"]'):
            return []
        articles = self.collect_by_heading(
            self.article_href, ARTICLES_PER_SITE, exclude_url=self.list_url
        )
        return self.warn_if_empty(articles)


class AnthropicNewsScraper(_AnthropicBase):
    list_url = "https://www.anthropic.com/news"
    article_href = "/news/"


class AnthropicEngineeringScraper(_AnthropicBase):
    list_url = "https://www.anthropic.com/engineering"
    article_href = "/engineering/"
