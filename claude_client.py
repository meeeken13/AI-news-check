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
- **提供された「元タイトル」「企業名」「URL」「本文」が全ての情報源。** 学習データにないモデル名・機能名・発表であっても、与えられた情報のみをもとに記事を書くこと。URLへのアクセスや外部情報の補完は不要。知識にないことを理由に断らない。

# 構成（本文 body はこの順）
1. タイトル: 30字以内・【】を使う（title フィールド）
2. リード文
3. ## 何が発表されたのか
4. ## 読んで思ったこと
5. ハッシュタグ5つ（#で始める）

# 出力形式
次の形式で出力する。前後に説明やコードブロック記号は付けない。
[[[TITLE]]]
記事タイトル
[[[BODY]]]
リード文から始まる記事本文全体"""

# 詳細解説版（速報より踏み込んだ中ボリュームの記事）
DETAIL_SYSTEM_PROMPT = """あなたはAI・テクノロジー分野の専門ライター兼ブロガーです。
AI企業の公式発表をもとに、note向けの「詳しい解説記事」を日本語で書きます。
これは速報ではなく、背景・技術的な仕組み・意義まで踏み込んだ読み物です。

# 方針
- 本文は1500〜2500字程度。読み応えのある解説にする。
- **公式記事の本文が与えられた場合は、その事実に厳密に基づいて書く。**書かれていない数値・固有名詞・主張を推測で創作しない。
- 公式発表の事実を正確に伝えつつ、なぜ重要か・どういう文脈かを丁寧に補足する。
- 技術的な内容は具体的なたとえや身近な例で噛み砕く。専門用語は短く補足。
- 公式文書の丸写しはしない。自分の言葉で再構成する。
- 書き手の視点・考察を2〜3箇所、自然に差し込む（断言しすぎない）。
- 英語の記事は必ず日本語に翻訳して記事化する。
- **提供された「元タイトル」「企業名」「URL」「本文」が全ての情報源。** 学習データにないモデル名・機能名・発表であっても、与えられた情報のみをもとに記事を書くこと。URLへのアクセスや外部情報の補完は不要。知識にないことを理由に断らない。

# 構成（本文 body はこの順、見出しは ## を使う）
1. タイトル: 40字以内・【】を使う（速報より説明的でよい）（title フィールド）
2. リード文（2〜3文）
3. ## 背景：何がこれまでの状況だったか
4. ## 何が発表されたのか（詳細）
5. ## 技術的なポイント／仕組み
6. ## これが持つ意味・影響
7. ## 読んで思ったこと（書き手の考察）
8. ハッシュタグ5つ（#で始める）

# 出力形式
次の形式で出力する。前後に説明やコードブロック記号は付けない。
[[[TITLE]]]
記事タイトル
[[[BODY]]]
リード文から始まる記事本文全体"""


def _is_english(text: str) -> bool:
    """タイトルがASCIIのみなら英語と判定（GAS版と同じロジック）。"""
    return text.isascii()


def _parse_response(raw: str) -> dict:
    """応答から ``{"title", "body"}`` を取り出す。

    マーカー区切り（[[[TITLE]]] / [[[BODY]]]）を優先。長文markdownの
    エスケープ崩れに強い。旧JSON形式や混在にも備えてJSONフォールバックも持つ。
    """
    if "[[[BODY]]]" in raw:
        head, body = raw.split("[[[BODY]]]", 1)
        title = head.replace("[[[TITLE]]]", "").strip()
        body = body.strip()
        if title and body:
            return {"title": title, "body": body}

    # JSONフォールバック（まず素直に、ダメなら {...} を抽出）
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group(0))
    return {"title": data["title"], "body": data["body"]}


def _generate(article: dict, system_prompt: str, instruction: str,
              include_content: bool = False) -> dict:
    """指定のシステムプロンプトで記事を生成し ``{"title", "body"}`` を返す。

    include_content=True かつ article["content"] があれば、公式記事の本文を
    プロンプトに含めて、それに基づいて書かせる（詳細記事で使用）。
    """
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    lang_note = ""
    if _is_english(article["title"]):
        lang_note = "\nこの記事は英語です。必ず日本語に翻訳して記事化してください。"

    content_block = ""
    if include_content and article.get("content"):
        content_block = (
            "\n\n# 公式記事の本文（以下の事実に厳密に基づいて書くこと。"
            "書かれていないことを推測で補わない）\n"
            f"{article['content']}"
        )

    user_prompt = (
        f"{instruction}{lang_note}\n\n"
        f"企業: {article['company']}\n"
        f"元タイトル: {article['title']}\n"
        f"元URL: {article['url']}"
        f"{content_block}"
    )

    last_err: Exception | None = None
    raw = ""
    for attempt in range(2):  # 空応答・JSON崩れに備えて1回リトライ
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # 先頭ブロックが空の場合に備え、全テキストブロックを結合する
        raw = "".join(
            b.text for b in message.content if getattr(b, "type", "") == "text"
        ).strip()
        if not raw:
            last_err = ValueError("Claudeが空のレスポンスを返しました")
            continue
        try:
            data = _parse_response(raw)
            return {"title": data["title"], "body": _append_source(data["body"], article)}
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            last_err = e  # 次のループでリトライ

    raise RuntimeError(
        f"記事生成に失敗（2回試行）: {last_err} / 応答先頭={raw[:120]!r}"
    )


def generate_note_article(article: dict) -> dict:
    """速報版の note 記事を生成し ``{"title", "body"}`` を返す。

    article: ``{"title", "url", "published", "company"}``
    """
    return _generate(
        article, SYSTEM_PROMPT,
        "以下のAI公式ブログ記事をもとに、note記事（速報）を書いてください。",
    )


def generate_detailed_article(article: dict) -> dict:
    """詳しい解説版の note 記事を生成し ``{"title", "body"}`` を返す。

    速報より踏み込んだ中ボリューム（1500〜2500字）の読み物。公式記事向け。
    """
    return _generate(
        article, DETAIL_SYSTEM_PROMPT,
        "以下のAI公式ブログ記事をもとに、詳しい解説記事を書いてください。",
        include_content=True,  # 詳細は公式の実際の本文に基づかせる
    )


def _append_source(body: str, article: dict) -> str:
    """note本文の末尾に公式記事の出典リンクを付与する。

    URLはモデルに書かせず元データをそのまま使う（改変・切れ防止）。
    既に同じURLが本文に含まれていれば二重に足さない。
    """
    url = article["url"]
    date = article.get("published_str") or ""
    if date and article.get("date_estimated"):
        date += "（推定）"  # 公開日が取れず取得日で補完したもの
    label = f"{article['company']}公式" + (f"・{date}" if date else "")
    if url in body:
        return body
    return f"{body.rstrip()}\n\n---\n📖 元記事（{label}）\n{url}"
