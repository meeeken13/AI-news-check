# 実装チェックリスト

`DEVELOPMENT.md` の各フェーズに対応した進捗トラッキング用チェックリスト。完了したら `[x]` にする。

## フェーズ0: 環境準備
- [ ] `git init` 済み
- [ ] `.gitignore` 作成（`.env` / `__pycache__/` / `*.pyc` / `service_account.json` を除外）
- [ ] `requirements.txt` 作成
- [ ] `pip install -r requirements.txt` 成功
- [ ] `playwright install chromium` 成功

## フェーズ1: config.py
- [ ] 対象サイト一覧を定義（企業名・URL・クラス名）
- [ ] 定数 `MAX_PER_RUN` / `FRESHNESS_HOURS` / `REQUEST_DELAY` 定義
- [ ] 環境変数3種の読み込み実装
- [ ] import してエラーが出ないことを確認

## フェーズ2: scrapers/base.py
- [ ] `BaseScraper(page)` 実装
- [ ] 抽象メソッド `fetch_articles()` 定義
- [ ] 共通ユーティリティ（要素待機 / テキスト抽出 / 相対→絶対URL / 0件警告ログ）

## フェーズ3: サイト別スクレイパー（単体動作確認込み）
スクレイパーは2方式: **見出し起点**（`collect_by_heading`）と**アンカー起点**（`collect_by_href`）。サイト構造に合う方を使う。
- [x] Google AI Blog（見出し起点・実サイトで10件確認）
- [x] Microsoft AI（**news.microsoft.com/source/topics/ai/ へ移行**・見出し起点で8件確認）
- [x] Anthropic News（見出し起点・5件確認）
- [x] Anthropic Engineering（見出し起点・10件確認）
- [x] OpenAI News（アンカー起点・10件確認）
- [ ] **Google DeepMind（未解決）** — `/discover/blog/` がJSルーティングでDOMに記事リンクを出さず0件。要URL/手法見直し（末尾[既知の問題]参照）
- [x] 各スクレイパーが正しい形式の dict を返すことを確認
- [x] 0件時に空リスト＋警告ログになることを確認

## フェーズ4: claude_client.py
- [x] モデル `claude-sonnet-4-6` で生成
- [x] システムプロンプト（構成①〜⑤）実装
- [x] ASCIIのみ→英語判定＋日本語翻訳指示
- [x] JSON堅牢パース（json.loads → 正規表現フォールバック）
- [ ] ダミー記事で日本語 title/body が返ることを確認（要 `ANTHROPIC_API_KEY`・未実行）

## フェーズ5: sheets_client.py
- [x] サービスアカウント認証実装
- [x] 「処理済み」シートからURL読込
- [x] 「生成記事」へ A〜G列で追記
- [x] 「処理済み」へ A〜C列で追記
- [ ] A〜F列の順序がGAS互換であることを実シートで確認（要認証情報・未実行）

## フェーズ6: main.py
- [x] 全体フロー（1〜8）実装
- [x] 鮮度フィルタ＋重複チェック実装（published=None時は通す方針）
- [x] 各記事 try/except で隔離
- [x] アクセス間隔／API負荷スリープ実装
- [ ] ローカルでエンドツーエンド実行成功（要認証情報・未実行）

## フェーズ7: GitHub Actions
- [ ] `scrape.yml` 作成（schedule cron `0 * * * *` ＋ workflow_dispatch）
- [ ] Secrets 3種を登録
- [ ] `workflow_dispatch` で手動実行成功
- [ ] cron運用に乗せた

## フェーズ8: README.md
- [ ] サービスアカウント作成＋共有手順
- [ ] Secrets設定手順
- [ ] ローカルテスト手順
- [ ] デプロイ手順

---

## リリース前の最終確認（重要制約）
- [ ] **GAS互換**: 「生成記事」A〜F列の順序は不変、企業名はG列のみ
- [ ] **重複判定**: URL＋タイトルのロジックがGAS版と一致
- [ ] **役割分担**: Python版は公式ブログのみ（Google NewsはGAS版担当）
- [ ] **頑健性**: 1記事／1サイトの失敗で全体が止まらない
- [ ] **マナー**: アクセス間隔1〜2秒、User-Agent明示、robots.txt尊重
- [ ] **言語**: 英語記事が日本語note記事になっている
- [ ] **秘密情報**: 認証JSON・APIキーがリポジトリにコミットされていない

---

## 既知の問題（要対応）
- **DeepMind スクレイパーが0件。** `https://deepmind.google/discover/blog/` は現在JSルーティングのSPAで、記事リンク（`/discover/blog/<slug>`）がDOM上のアンカーとして存在しない（heading/anchorどちらでも取得不可）。対応案: ①正しい記事一覧URLを特定して差し替え ②内部のJSON/APIエンドポイントを直接叩く ③記事ページのレンダリングを待つ別セレクタを探す。当面は0件＋警告ログで安全に素通りする。
- **実認証を要する検証が未完了。** Claude生成・Sheets書込・E2Eは `ANTHROPIC_API_KEY` / `GOOGLE_SERVICE_ACCOUNT_JSON` / `SPREADSHEET_ID` が必要なためローカル未実行。スクレイピング層（5/6サイト）は実サイトで動作確認済み。
- **セレクタは実サイト準拠（2026-06時点）。** 各サイトは予告なく再設計される。Microsoft・Google AI は仕様書記載URLから既に移行済みだった。0件警告をActionsログで監視すること。
