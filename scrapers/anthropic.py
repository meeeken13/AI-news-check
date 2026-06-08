"""Anthropic 公式ブログ用スクレイパー（News / Engineering）。

/news には「Announcements（お知らせ）」「Product」「Policy」等のカードが並ぶ。
見出しタグを使わないカードもあるため、記事リンク(アンカー)起点で全カードを拾う。
カードのテキストは「カテゴリ」「日付」「タイトル」が混在し順序も一定でないので、
- 日付: 日付正規表現にマッチする行
- タイトル: 日付でもカテゴリ名でもない「最初」の行（カードは概ね
  カテゴリ→日付→タイトル→説明文の順。説明文は後ろなので最初を採る）
として抽出する（Anthropicの記事ページには公開日が無いためカードから取る）。
"""

import re

from config import ARTICLES_PER_SITE
from scrapers.base import BaseScraper

# "May 28, 2026" / "Jun 2, 2026" / "Feb. 3, 2026" 形式
_DATE_RE = re.compile(r"[A-Z][a-z]{2,8}\.?\s+\d{1,2},\s+\d{4}")

# タイトルと紛らわしいカテゴリ名（タイトル抽出時に除外）
_CATEGORIES = {
    "announcements", "announcement", "product", "policy", "research",
    "societal impacts", "interpretability", "engineering", "company",
    "education", "alignment", "featured",
}

# 記事リンク(アンカー)の href とカード全文を返すJS
_CARD_JS = """
(pat) => Array.from(document.querySelectorAll(`a[href*="${pat}"]`))
  .map(a => ({ href: a.getAttribute('href') || '', text: a.innerText || '' }));
"""


class _AnthropicBase(BaseScraper):
    company = "Anthropic"
    base_url = "https://www.anthropic.com"

    list_url: str = ""
    article_href: str = ""

    def fetch_articles(self) -> list[dict]:
        if not self.goto(self.list_url, f'a[href*="{self.article_href}"]'):
            return []
        raw = self.page.evaluate(_CARD_JS, self.article_href)
        results: list[dict] = []
        seen: set[str] = set()
        exclude = self.list_url.rstrip("/")
        for item in raw:
            url = self.absolute_url(item["href"])
            if url.rstrip("/") == exclude or url in seen:
                continue
            lines = [ln.strip() for ln in item["text"].split("\n") if ln.strip()]
            if not lines:
                continue
            # 日付行
            date = None
            for ln in lines:
                m = _DATE_RE.search(ln)
                if m:
                    date = m.group(0)
                    break
            # タイトル候補: 日付でもカテゴリ名でもない行。説明文は後ろに来るので最初を採る。
            cands = [
                ln for ln in lines
                if not _DATE_RE.search(ln) and ln.lower() not in _CATEGORIES
            ]
            if not cands:
                continue
            title = cands[0]
            if len(title) < 10:
                continue
            seen.add(url)
            results.append({
                "title": title,
                "url": url,
                "published": date,
                "company": self.company,
            })
            if len(results) >= ARTICLES_PER_SITE:
                break
        return self.warn_if_empty(results)


class AnthropicNewsScraper(_AnthropicBase):
    list_url = "https://www.anthropic.com/news"
    article_href = "/news/"


class AnthropicEngineeringScraper(_AnthropicBase):
    list_url = "https://www.anthropic.com/engineering"
    article_href = "/engineering/"
