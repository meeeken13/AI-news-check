# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクトの状態

実装済み。`config.py` / `claude_client.py` / `sheets_client.py` / `main.py` と `scrapers/` 一式、`.github/workflows/scrape.yml` が存在する。元仕様は `ai-news-scraper-spec.md`、開発手順は `DEVELOPMENT.md`、進捗と既知の問題は `CHECKLIST.md` を参照。

**現状（2026-06 時点）**: スクレイピング層は**6サイト全て実サイトで動作確認済み**（計約53件）。Claude生成・Sheets書込・E2EもGitHub Actionsで実行成功済み。`MAX_PER_RUN=10`。

DeepMind の注意点: `/discover/blog/` は `/blog/` にリダイレクトするSPAで、記事リンクは①ネイティブ `deepmind.google/blog/<slug>` と②クロス投稿 `blog.google/...` が混在する。記事リンクが隠れナビにも存在するため `goto` の待ちは `state="attached"`（可視性を問わない）にしている — ここを `"visible"` に戻すと0件になる。blog.google クロス投稿は Google AI スクレイパーと衝突しうるため、`main.py` で実行内URL重複も除外している。

## このシステムの目的

複数のAI企業の公式ブログを Playwright でスクレイピングし、Claude API で note 向けの日本語記事を生成して Google Sheets に書き込む。GitHub Actions で毎時自動実行する。**既存の GAS（Google Apps Script）システムと同じスプレッドシートを共有**することで、GAS側のnote転記サイドバーUIをそのまま使い続けられるようにするのが要点。

## コマンド

```bash
# ローカルセットアップ
pip install -r requirements.txt
playwright install chromium        # CI では: playwright install --with-deps chromium

# パイプライン全体を実行（唯一のエントリポイント）
python main.py
```

必要な環境変数（CI では GitHub Secrets、ローカルでは `.env` か export）:
- `ANTHROPIC_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON` — サービスアカウントJSONの中身全体
- `SPREADSHEET_ID`

仕様書にテストスイートの定義はない。個別スクレイパーを直す際は、`main.py` 全体を回さず、そのスクレイパー単体で動かして確認する（各スクレイパーは `BaseScraper` を継承し Playwright の `page` を受け取る）。

## アーキテクチャ

`main.py` が処理フローを統括する: Sheetsから処理済みリスト読込 → ヘッドレスChromium起動 → 各スクレイパー実行 → 重複除去 → **各候補に公開日を付与**（`enrich_dates`、ブラウザを開いている間に実行）→ **鮮度フィルタ＋新しい順ソート**（`filter_fresh`）→ 上位 `MAX_PER_RUN` 件をClaudeで生成 → Sheetsに書き込み。

鮮度フィルタは `FRESHNESS_HOURS`（既定48h）。公開日を特定できない記事は `SKIP_UNDATED`（既定True）でスキップ＝古い記事の混入を防ぐ。GitHubのcronは約2時間おきに動くため48h窓なら取りこぼさない。

- **`scrapers/base.py`** — `BaseScraper(page)`、抽象メソッド `fetch_articles() -> list[dict]`。1記事の形式は `{"title": str, "url": str, "published": str | None, "company": str}`。収集ヘルパーは2種: **`collect_by_heading`**（h1〜h4見出しを起点にタイトル＋近傍リンクを辿る／カテゴリ・ナビのラベルを拾いにくい）と **`collect_by_href`**（href にパスを含むアンカーを集める／見出しを持たないカード向け、OpenAIで使用）。サイト別サブクラスはどちらか適した方を使う。対象サイトの多くは JS描画なので `goto(url, wait_selector)` で描画完了を待つ（`state="attached"`）。
- **`dates.py`** — 公開日の取得とパース。`extract_published(page, url)` は記事ページの `meta[article:published_time]` → JSON-LD `datePublished` → `time[datetime]` の順で抜く（OpenAIの`<time>`はJSで遅延描画されるため `wait_for_selector` で待つ）。Anthropicは記事ページに日付が無いため**一覧カードのテキスト**（"May 28, 2026"等）から取得し scraper が `published` に入れる。`parse_published` はISO/英語表記の両方を tz-aware datetime に変換。
- **`claude_client.py`** — note記事を生成。モデルは `claude-sonnet-4-6`。出力は**マーカー区切り**（`[[[TITLE]]]` / `[[[BODY]]]`）— 長文markdownのJSONエスケープ崩れを避けるため。`_parse_response`がマーカー優先＋JSONフォールバックで解析。空応答/解析失敗時は1回リトライ（`_generate`）。
- **`sheets_client.py`** — `gspread` ＋ サービスアカウント認証。「処理済み」シートを重複チェック用に読み、「生成記事」「処理済み」に追記する。
- **`config.py`** — 対象サイト一覧、`MAX_PER_RUN`（1実行の最大記事数, 目安5）、鮮度ウィンドウ（デフォルト48時間）、環境変数の読み込み。

## 重要な制約（間違えやすい箇所）

- **GASとスプレッドシートを共有している。** 「生成記事」シートは GAS互換のため A〜F列。このシステムは**G列=企業名・H列=公開日(YYYY-MM-DD)・I列=詳細タイトル・J列=詳細本文**を追記する。GASサイドバー/WebAppはこれらを読んで速報(D/E)と詳細(I/J)を切替表示する。A〜F列の並び替えや列挿入は禁止。
- **公式記事は速報＋詳細の2本を生成する。** `claude_client.generate_note_article`(速報, `SYSTEM_PROMPT`)と`generate_detailed_article`(詳しい解説1500〜2500字, `DETAIL_SYSTEM_PROMPT`)を各記事で呼ぶ＝Claude APIは1記事あたり2コール。両方とも本文末尾に出典リンクを付与。重複判定（URL＋タイトル）は GAS版とロジックを揃えること（同じ「処理済み」シートに両者が書くため）。役割分担: GAS版は Google News 系、Python版は公式ブログのみを担当。
- **網羅性より頑健性。** 1記事の失敗で全体を止めない — 各記事を try/except で囲む。記事0件のスクレイパーは空リストを返し、**警告ログ**を出す（サイト構造が変わるとセレクタが壊れる。警告が異常検知の手段）。
- **スクレイピングのマナー。** アクセス間隔を空ける（1〜2秒）、User-Agent を明示、robots.txt を尊重。
- **言語判定。** 公式ブログは英語が多い。タイトルが ASCII のみなら英語と判定し、Claude に日本語翻訳を明示する — GAS版と同じロジック。

## Claude記事生成のプロンプト方針

GAS版と統一して保つ: AI・テクノロジーの専門ライター兼ブロガーとして、公式発表の事実を正確に報道調で伝えつつ書き手の視点・感想を1〜2箇所入れる。公式文書の丸写しはせず自分の言葉で噛み砕く。英語記事は必ず日本語に翻訳。構成: ①タイトル（30字以内・【】使用）②リード文 ③## 何が発表されたのか ④## 読んで思ったこと ⑤ハッシュタグ5つ。
