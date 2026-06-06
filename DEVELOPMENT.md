# 開発手順書

`ai-news-scraper-spec.md` の仕様をゼロから実装するための手順。上から順に進めれば動くところまで到達できる構成にしてある。各ステップは独立して動作確認できるよう、依存の浅い順に並べている。

---

## フェーズ0: 環境準備

1. **リポジトリ初期化**
   ```bash
   git init
   ```
2. **`.gitignore` 作成** — `.env` / `__pycache__/` / `*.pyc` / `service_account.json` を必ず除外（認証情報の漏洩防止）。
3. **`requirements.txt` 作成**
   ```
   playwright
   anthropic
   gspread
   google-auth
   python-dotenv      # ローカルの .env 読み込み用
   ```
4. **依存インストール**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

---

## フェーズ1: 設定とスケルトン（`config.py`）

- 対象サイト一覧を「企業名・URL・スクレイパークラス名」の構造で定義。
- 定数: `MAX_PER_RUN = 5`、`FRESHNESS_HOURS = 48`、アクセス間隔 `REQUEST_DELAY = 1.5` 秒。
- 環境変数読み込み（`ANTHROPIC_API_KEY` / `GOOGLE_SERVICE_ACCOUNT_JSON` / `SPREADSHEET_ID`）。ローカルは `.env` から、CI は環境変数から。
- **確認**: `python -c "import config; print(config.SITES)"` でエラーが出ないこと。

---

## フェーズ2: スクレイパー基底クラス（`scrapers/base.py`）

- `BaseScraper(self, page)`: Playwright の `page` を受け取る。
- `fetch_articles(self) -> list[dict]`: 抽象メソッド。
- 返す形式: `{"title": str, "url": str, "published": str | None, "company": str}`。
- 共通ユーティリティ: 要素待機ラッパ、テキスト抽出、相対URL→絶対URL変換、0件時の警告ログ。
- **確認**: 単体ではテストしづらいので、最初のサイト実装（フェーズ3）と一緒に検証する。

---

## フェーズ3: サイト別スクレイパー（1つずつ）

`scrapers/anthropic.py` など。**一気に全社作らず、1サイトずつ完成させて動作確認する。**

各サイトの手順:
1. ブラウザで対象URLを開き、記事一覧のDOM構造とセレクタを実際に調べる。
2. `BaseScraper` を継承し、`fetch_articles` を実装。JS描画完了を `wait_for_selector` で待つ。
3. 上位N件（最新10件程度）を取得。セレクタは定数としてファイル上部にまとめる。
4. 取得失敗時は空リスト＋警告ログ。
5. **単体動作確認スニペット**で実行:
   ```python
   import asyncio
   from playwright.async_api import async_playwright
   from scrapers.anthropic import AnthropicScraper

   async def main():
       async with async_playwright() as p:
           browser = await p.chromium.launch()
           page = await browser.new_page()
           print(await AnthropicScraper(page).fetch_articles())
           await browser.close()
   asyncio.run(main())
   ```

対象（優先度順 — 取りやすいものから着手すると勢いがつく）:
- [ ] Google AI Blog（比較的取りやすい）
- [ ] Microsoft AI（比較的取りやすい）
- [ ] Anthropic News
- [ ] Anthropic Engineering
- [ ] OpenAI News
- [ ] Google DeepMind

---

## フェーズ4: Claude クライアント（`claude_client.py`）

- モデル `claude-sonnet-4-6`、`ANTHROPIC_API_KEY` 使用。
- システムプロンプトは CLAUDE.md / 仕様書の方針（構成①〜⑤）に従う。
- タイトルが ASCII のみなら英語と判定し、日本語翻訳を明示。
- 出力は JSON のみ `{"title", "body"}`。`json.loads` → 失敗時に正規表現で `{...}` を抽出するフォールバック。
- **確認**: ダミー記事 `{"title": "...", "url": "...", "company": "OpenAI"}` を渡し、日本語の `title`/`body` が返ることを確認。

---

## フェーズ5: Sheets クライアント（`sheets_client.py`）

- `gspread` ＋ サービスアカウント認証（`GOOGLE_SERVICE_ACCOUNT_JSON`）。
- 読込: 「処理済み」シートから既存の URL・タイトル一覧を取得。
- 書込:
  - 「生成記事」← A:処理日時 / B:元タイトル / C:元URL / D:noteタイトル / E:note本文 / F:`"🏢 公式"` / **G:企業名**
  - 「処理済み」← A:記事URL / B:記事タイトル / C:処理日時
- **A〜F列の順序は GAS互換のため厳守。G列追加のみ可。**
- **確認**: テスト用スプレッドシートで読み書きが成功し、列ズレがないこと。

---

## フェーズ6: エントリポイント（`main.py`）

処理フロー（仕様書の通り）:
1. 設定読み込み
2. Sheetsから処理済み記事を読込
3. ヘッドレスChromium起動
4. 各スクレイパーを順に実行し記事を集約（間にアクセス間隔スリープ）
5. 鮮度フィルタ（N時間以内）＋ 重複チェックで新規記事抽出
6. 新規を最大 `MAX_PER_RUN` 件処理: Claude生成 → Sheets書込 → 数秒スリープ
7. 結果をログ出力
8. Playwright終了

- **各記事を try/except で囲み、1件の失敗で全体を止めない。**
- **確認**: `python main.py` をローカルで実行し、エンドツーエンドで1〜数件がシートに追記されること。

---

## フェーズ7: GitHub Actions（`.github/workflows/scrape.yml`）

- トリガー: `schedule`（cron `0 * * * *`）＋ `workflow_dispatch`（手動実行）。
- 環境: `ubuntu-latest`, Python 3.12。
- ステップ: checkout → Python setup → `pip install -r requirements.txt` → `playwright install --with-deps chromium` → `python main.py`。
- Secrets: `ANTHROPIC_API_KEY` / `GOOGLE_SERVICE_ACCOUNT_JSON` / `SPREADSHEET_ID`。
- **確認**: まず `workflow_dispatch` で手動実行し成功を確認してから、cron運用に乗せる。

---

## フェーズ8: ドキュメント（`README.md`）

仕様書の「README.mdに含めるセットアップ手順」を反映:
1. Googleサービスアカウント作成＋スプレッドシートを編集者として共有
2. GitHubリポジトリ作成＆Secrets設定
3. ローカルテスト方法
4. main へ push でデプロイ
