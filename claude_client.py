"""Claude API で note 向け記事を生成するクライアント。"""

import json
import logging
import re

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたはAI・テクノロジー分野の専門ライター兼ブロガーです。
AI企業の公式発表をもとに、note向けの日本語記事を書きます。

# 方針
- 公式発表の事実を正確に、報道調で伝える。
- ただし書き手の視点・感想を1〜2箇所だけ自然に入れる。
- 公式文書の丸写しはしない。自分の言葉で噛み砕く。
- 技術的な内容は、具体的なたとえを使ってわかりやすく説明する。
- 英語の記事は必ず日本語に翻訳して記事化する。

# 構成（本文 body はこの順）
1. タイトル: 30字以内・【】を使う（title フィールド）
2. リード文
3. ## 何が発表されたのか
4. ## 読んで思ったこと
5. ハッシュタグ5つ（#で始める）

# 出力形式
必ず次のJSONのみを出力する。前後に説明文やコードブロック記号を付けない。
{"title": "記事タイトル", "body": "リード文から始まる記事本文全体"}"""


def _is_english(text: str) -> bool:
    """タイトルがASCIIのみなら英語と判定（GAS版と同じロジック）。"""
    return text.isascii()


def _parse_json(raw: str) -> dict:
    """まず json.loads、失敗したら正規表現で {...} を抽出するフォールバック。"""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def generate_note_article(article: dict) -> dict:
    """記事メタ情報から note 記事を生成し ``{"title", "body"}`` を返す。

    article: ``{"title", "url", "published", "company"}``
    """
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    lang_note = ""
    if _is_english(article["title"]):
        lang_note = "\nこの記事は英語です。必ず日本語に翻訳して記事化してください。"

    user_prompt = (
        f"以下のAI公式ブログ記事をもとに、note記事を書いてください。{lang_note}\n\n"
        f"企業: {article['company']}\n"
        f"元タイトル: {article['title']}\n"
        f"元URL: {article['url']}"
    )

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = message.content[0].text.strip()

    data = _parse_json(raw)
    return {"title": data["title"], "body": data["body"]}
