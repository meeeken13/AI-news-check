# AI公式ブログ スクレイピング → note記事生成 システム仕様書

## 概要

複数のAI企業の公式ブログを Playwright でスクレイピングし、Claude API で note 向け記事を生成して、Google Sheets に書き込むシステム。GitHub Actions で毎時自動実行する。

既存の GAS（Google Apps Script）システムと**同じスプレッドシート**に書き込むことで、GAS側のnote転記サイドバーUIをそのまま使えるようにする。

---

## システム全体構成

```
GitHub Actions（毎時 cron 実行）
  └→ Python + Playwright
       ├→ 各AI企業の公式ブログをスクレイピング（JSレンダリング対応）
       ├→ 既存記事と重複チェック（Google Sheets「処理済み」シート参照）
       ├→ 新規記事のみ Claude API で note 記事生成
       └→ Google Sheets「生成記事」「処理済み」シートに書き込み
```

---

## スクレイピング対象（公式ブログ）

クライアントサイドレンダリング（JS描画）のサイトが多いため、Playwright を使う。

| 企業 | URL | 備考 |
|------|-----|------|
| Anthropic News | https://www.anthropic.com/news | JS描画 |
| Anthropic Engineering | https://www.anthropic.com/engineering | JS描画 |
| OpenAI News | https://openai.com/news/ | JS描画 |
| Google DeepMind | https://deepmind.google/discover/blog/ | JS描画 |
| Google AI Blog | https://blog.google/technology/ai/ | 比較的取りやすい |
| Microsoft AI | https://blogs.microsoft.com/ai/ | 比較的取りやすい |

各サイトの記事一覧ページから「記事タイトル」「記事URL」「公開日（取得できれば）」を抽出する。
各サイトでHTML構造が異なるため、サイトごとにセレクタを定義できる設計にすること。

---

## ファイル構成

```
ai-news-scraper/
├── .github/
│   └── workflows/
│       └── scrape.yml          # GitHub Actions ワークフロー
├── scrapers/
│   ├── __init__.py
│   ├── base.py                 # スクレイパー基底クラス
│   ├── anthropic.py            # Anthropic用スクレイパー
│   ├── openai.py               # OpenAI用スクレイパー
│   ├── deepmind.py             # DeepMind用スクレイパー
│   ├── google_ai.py            # Google AI Blog用スクレイパー
│   └── microsoft.py            # Microsoft AI用スクレイパー
├── main.py                     # エントリポイント
├── claude_client.py            # Claude API クライアント
├── sheets_client.py            # Google Sheets クライアント
├── config.py                   # 設定（対象サイト、定数など）
├── requirements.txt
└── README.md                   # セットアップ手順
```

---

## 各モジュールの仕様

### config.py

- スクレイピング対象サイトのリスト（企業名、URL、スクレイパークラス名）
- 1回の実行で処理する最大記事数（`MAX_PER_RUN = 5` など）
- 記事の鮮度フィルター（公開から N 時間以内のみ対象、デフォルト48時間）
- 環境変数からの設定読み込み（APIキー等）

### scrapers/base.py

スクレイパーの基底クラス `BaseScraper` を定義。

- `__init__(self, page)`: Playwright の page を受け取る
- `fetch_articles(self) -> list[dict]`: 抽象メソッド。各サイトで実装
- 返す記事の形式: `{"title": str, "url": str, "published": str | None, "company": str}`
- 共通ユーティリティ（要素待機、テキスト抽出など）を持たせる

### scrapers/各サイト.py

`BaseScraper` を継承し、サイトごとのセレクタで記事一覧を抽出。

- ページ遷移後、JSレンダリング完了を待つ（`page.wait_for_selector` 等）
- 記事一覧から上位 N 件（例: 最新10件）を取得
- セレクタは変更されやすいので、定数として分かりやすくまとめておく
- 取得失敗時は空リストを返し、ログを出して処理を止めない

### claude_client.py

Claude API で note 記事を生成する。

- モデル: `claude-sonnet-4-6`
- 環境変数 `ANTHROPIC_API_KEY` を使用
- システムプロンプトは以下の方針（GAS版と統一）:
  - AI・テクノロジー分野の専門ライター兼ブロガーとして書く
  - 公式発表の事実を正確に報道調で伝えつつ、書き手の視点・感想も1〜2箇所入れる
  - 公式文書の丸写しはしない、自分の言葉で噛み砕く
  - 技術的内容は具体的なたとえでわかりやすく
  - 英語記事は必ず日本語に翻訳して記事化
  - 構成: ①タイトル(30字以内・【】使用) ②リード文 ③## 何が発表されたのか ④## 読んで思ったこと ⑤ハッシュタグ5つ
  - 出力は JSON のみ: `{"title": "...", "body": "..."}`
- JSONパースは堅牢に（まず json.loads、失敗したら正規表現フォールバック）
- 戻り値: `{"title": str, "body": str}`

### sheets_client.py

Google Sheets への読み書き。`gspread` ライブラリを使用。

認証はサービスアカウント方式（GitHub Actions で動かすため）。

**読み込み:**
- 「処理済み」シートから既存の記事URL・タイトルを取得（重複チェック用）

**書き込み:**
- 「生成記事」シートに追記:
  | 列 | 内容 |
  |---|---|
  | A | 処理日時 |
  | B | 元記事タイトル |
  | C | 元記事URL |
  | D | noteタイトル（生成） |
  | E | note本文（生成） |
  | F | ソース種別（"🏢 公式" 固定） |
  | G | 企業名（Anthropic/OpenAI など） |
- 「処理済み」シートに追記:
  | 列 | 内容 |
  |---|---|
  | A | 記事URL |
  | B | 記事タイトル |
  | C | 処理日時 |

※ GAS版の既存シート構造に合わせる。GAS版「生成記事」はA〜F列なので、G列（企業名）を追加する形。GAS側のサイドバーは6列目までしか読まないので、G列追加は影響しない。

### main.py

エントリポイント。処理フロー:

1. 設定読み込み（config.py）
2. Google Sheets から処理済み記事を読み込み
3. Playwright を起動（ヘッドレス Chromium）
4. 各スクレイパーを順に実行して記事一覧を集約
5. 鮮度フィルター（N時間以内）＋ 重複チェックで新規記事を抽出
6. 新規記事を最大 `MAX_PER_RUN` 件まで処理:
   - Claude API で note 記事生成
   - Google Sheets に書き込み
   - API負荷対策で数秒スリープ
7. 処理結果をログ出力
8. Playwright を終了

エラーハンドリング: 1記事の失敗で全体を止めない。各記事を try/except で囲む。

---

## GitHub Actions ワークフロー（.github/workflows/scrape.yml）

- トリガー: `schedule`（毎時, cron `0 * * * *`）＋ `workflow_dispatch`（手動実行可）
- 実行環境: ubuntu-latest, Python 3.12
- ステップ:
  1. リポジトリをチェックアウト
  2. Python セットアップ
  3. 依存インストール（`pip install -r requirements.txt`）
  4. Playwright ブラウザインストール（`playwright install --with-deps chromium`）
  5. `python main.py` 実行
- 環境変数（GitHub Secrets から注入）:
  - `ANTHROPIC_API_KEY`
  - `GOOGLE_SERVICE_ACCOUNT_JSON`（サービスアカウントの認証JSON全体）
  - `SPREADSHEET_ID`

---

## requirements.txt

```
playwright
anthropic
gspread
google-auth
```

---

## README.md に含めるセットアップ手順

1. **Google サービスアカウント作成**
   - Google Cloud Console でサービスアカウントを作成
   - JSON キーをダウンロード
   - 対象スプレッドシートをそのサービスアカウントのメールアドレスに「編集者」として共有

2. **GitHub リポジトリ作成 & Secrets 設定**
   - `ANTHROPIC_API_KEY`: Claude APIキー
   - `GOOGLE_SERVICE_ACCOUNT_JSON`: サービスアカウントJSONの中身全体を貼り付け
   - `SPREADSHEET_ID`: スプレッドシートのID（URLの d/【ID】/edit の部分）

3. **ローカルテスト方法**
   - `.env` ファイルまたは環境変数を設定
   - `playwright install chromium`
   - `python main.py`

4. **デプロイ**
   - main ブランチに push すれば GitHub Actions が毎時自動実行

---

## 重要な実装上の注意

- **スクレイピングのマナー**: 各サイトへのアクセス間隔を空ける（1〜2秒）。User-Agent を明示。robots.txt を尊重する設計コメントを残す。
- **セレクタの壊れやすさ**: サイト構造が変わるとセレクタが効かなくなる。各スクレイパーで「記事が0件だった場合は警告ログを出す」ようにし、気づけるようにする。
- **重複チェックの一貫性**: GAS版と同じスプシを使うため、URL・タイトルでの重複判定ロジックを GAS版と揃える。
- **GAS版との共存**: GAS版は news 系（Google News）を担当、Python版は公式ブログのスクレイピングを担当、と役割分担する。両方が同じ「処理済み」シートを見るので重複は起きない。
- **日本語/英語判定**: 公式ブログは英語が多い。タイトルがASCIIのみなら英語と判定し、Claudeに日本語翻訳を明示する（GAS版と同じロジック）。

---

## 完成イメージ

- GitHub Actions が毎時起動
- Anthropic / OpenAI / DeepMind / Google / Microsoft の公式ブログから新着を検出
- 各記事を日本語の note 記事に自動変換
- GAS と同じスプシの「生成記事」シートに蓄積
- ユーザーは GAS のサイドバーから記事を選んで note に転記

→ 公式一次情報ベースの note 記事が、人手ゼロで溜まっていく。
