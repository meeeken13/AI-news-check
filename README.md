# AI-news-check

複数のAI企業の公式ブログを Playwright でスクレイピングし、Claude API で note 向けの日本語記事を生成して Google Sheets に書き込むシステム。GitHub Actions で毎時自動実行する。

既存の GAS（Google Apps Script）システムと同じスプレッドシートを共有し、GAS側のnote転記サイドバーUIをそのまま使えるようにしている。GAS版は Google News 系、本システムは公式ブログを担当する。

対象: Anthropic (News / Engineering) ・ OpenAI ・ Google DeepMind ・ Google AI Blog ・ Microsoft AI

## セットアップ

### 1. Google サービスアカウント作成
1. Google Cloud Console でサービスアカウントを作成し、JSONキーをダウンロード。
2. 対象スプレッドシートを、そのサービスアカウントのメールアドレスに「編集者」として共有。
3. スプレッドシートに「生成記事」「処理済み」シートが存在することを確認。

### 2. GitHub Secrets 設定
リポジトリの Settings → Secrets and variables → Actions に登録:
- `ANTHROPIC_API_KEY`: Claude APIキー
- `GOOGLE_SERVICE_ACCOUNT_JSON`: サービスアカウントJSONの中身全体を貼り付け
- `SPREADSHEET_ID`: スプレッドシートID（URLの `d/【ID】/edit` の部分）

### 3. ローカルテスト
```bash
pip install -r requirements.txt
playwright install chromium

# .env を作成（コミットされない）
cat > .env <<'EOF'
ANTHROPIC_API_KEY=sk-ant-...
SPREADSHEET_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
EOF

python main.py
```

### 4. デプロイ
`main` ブランチに push すれば GitHub Actions が毎時自動実行する。初回は Actions タブから `workflow_dispatch`（手動実行）で動作確認するとよい。

## 設定の調整

`config.py` で変更可能:
- `MAX_PER_RUN`: 1実行あたりの最大生成記事数（デフォルト5）
- `FRESHNESS_HOURS`: 鮮度フィルタ（デフォルト48時間）
- `ARTICLES_PER_SITE`: 各サイトの一覧から取得する件数
- `SITES`: スクレイピング対象サイト一覧

## 注意

各スクレイパーのセレクタ（`scrapers/*.py`）はサイト構造の変更で壊れることがある。記事0件のときは警告ログを出すので、Actions のログで気づける。詳しい開発手順は `DEVELOPMENT.md`、進捗管理は `CHECKLIST.md` を参照。
