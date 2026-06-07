"""記事の公開日を取得・パースするユーティリティ。

取得元はサイトにより異なる:
- 多くのサイト: 記事ページの meta[article:published_time] か JSON-LD datePublished
- Anthropic: 記事ページに日付が無く、一覧カードのテキストから取得（scraper側）
"""

from __future__ import annotations

from datetime import datetime, timezone

# 記事ページから公開日(ISO文字列)を抜くJS。meta → JSON-LD → time[datetime] の順。
_META_JS = r"""() => {
  const m = document.querySelector(
    'meta[property="article:published_time"],meta[name="article:published_time"]');
  if (m && m.getAttribute('content')) return m.getAttribute('content');
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const j = JSON.parse(s.textContent);
      const arr = Array.isArray(j) ? j : [j];
      for (const o of arr) {
        if (o && o.datePublished) return o.datePublished;
        if (o && o['@graph'])
          for (const g of o['@graph']) if (g && g.datePublished) return g.datePublished;
      }
    } catch (e) {}
  }
  const t = document.querySelector('time[datetime]');
  const dt = t ? t.getAttribute('datetime') : null;
  if (dt && /\d{4}-\d{2}-\d{2}/.test(dt)) return dt;  // ISO形式のtimeのみ採用
  return null;
}"""


# 公開日のシグナルとなる要素。JSで遅れて差し込まれるサイト(OpenAI)があるため待つ。
_DATE_SELECTOR = (
    'meta[property="article:published_time"], time[datetime], '
    'script[type="application/ld+json"]'
)


def extract_published(page, url: str) -> str | None:
    """記事ページに遷移し、公開日のISO文字列を返す（取れなければ None）。"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # 日付要素の出現を待つ（OpenAIの<time>はJSで後から入る）。無くても続行。
        try:
            page.wait_for_selector(_DATE_SELECTOR, state="attached", timeout=5000)
        except Exception:
            pass
        return page.evaluate(_META_JS)
    except Exception:
        return None


def parse_published(raw: str | None) -> datetime | None:
    """公開日文字列を tz-aware(UTC) の datetime に変換する。

    対応: ISO日付/日時（"2026-05-19", "2026-06-03T13:15", "...Z"）、
          "May 28, 2026" / "Jun 2, 2026" 形式（Anthropic一覧カード）。
    """
    if not raw:
        return None
    raw = raw.strip()
    # ISO
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    # "May 28, 2026" / "Jun 2, 2026" / "Feb. 3, 2026"（略称・正式名・末尾ピリオド対応）
    cleaned = raw.replace(".", "")
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def fmt_date(dt: datetime | None) -> str:
    """表示用に YYYY-MM-DD へ整形（None は空文字）。"""
    return dt.strftime("%Y-%m-%d") if dt else ""
