"""Anthropic 公式ブログ用スクレイパー（News / Engineering）。

どちらも同じDOM構造のため、一覧URLと記事パスだけ差し替えて共通化する。
Anthropicの記事ページには公開日が無いため、一覧カードのテキスト
（例: "May 28, 2026" / "Jun 2, 2026"）から日付を取得する。
"""

import re

from config import ARTICLES_PER_SITE
from scrapers.base import BaseScraper

# カードテキスト内の "May 28, 2026" / "Jun 2, 2026" 形式を拾う
_DATE_RE = re.compile(r"[A-Z][a-z]{2,8}\.?\s+\d{1,2},\s+\d{4}")

# 見出し→記事リンク＋カード全文を返すJS（カード全文から日付を抽出するため）
_CARD_JS = """
(pat) => {
  const out = [];
  for (const h of document.querySelectorAll('h1,h2,h3,h4')) {
    const title = (h.innerText || '').trim().split('\\n')[0].trim();
    if (!title || title.length < 10) continue;
    let a = h.closest('a');
    if (!a) {
      let el = h;
      for (let i = 0; i < 5 && el; i++) {
        const f = el.querySelector ? el.querySelector('a[href]') : null;
        if (f) { a = f; break; }
        el = el.parentElement;
      }
    }
    if (!a) continue;
    const href = a.getAttribute('href') || '';
    if (!href.includes(pat)) continue;
    const card = a.closest('a') || a;
    out.push({ title, href, text: (card.innerText || '') });
  }
  return out;
}
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
            seen.add(url)
            m = _DATE_RE.search(item["text"])
            results.append({
                "title": item["title"],
                "url": url,
                "published": m.group(0) if m else None,
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
