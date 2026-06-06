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
- [x] **Google DeepMind（解決済み）** — `/blog/` へリダイレクト。見出し起点＋ネイティブ/blog.googleクロス投稿の両形式で10件確認。`state="attached"`待ちが鍵
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
- [x] 実行内URL重複の除外（DeepMindのblog.googleクロス投稿対策）
- [x] エンドツーエンド実行成功（GitHub Actionsで5件生成・書込を確認）

## フェーズ7: GitHub Actions
- [x] `scrape.yml` 作成（schedule cron `0 * * * *` ＋ workflow_dispatch）
- [x] Secrets 3種を登録
- [x] `workflow_dispatch` で手動実行成功
- [ ] cron運用に乗せた（毎時自動実行の継続確認）

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

## 既知の問題・注意点
- **DeepMind は解決済み。** `/discover/blog/` → `/blog/` リダイレクト。記事リンクは①ネイティブ `deepmind.google/blog/<slug>` ②クロス投稿 `blog.google/...` が混在。隠れナビにも `/blog/` 要素があるため待ちは `state="attached"`（`base.goto`）。`"visible"` に戻すと0件になるので注意。
- **セレクタは実サイト準拠（2026-06時点）。** 各サイトは予告なく再設計される。Microsoft・Google AI・DeepMind は仕様書記載URLから既に移行済みだった。0件警告をActionsログで監視すること。
- **処理順による偏り。** 処理はサイト順（先頭=Google AI）で `MAX_PER_RUN=10` まで。初回は新規候補が多いと先頭サイトに偏る。定常運用では問題ないが、各社混在させたい場合は抽出後にインターリーブを検討。
