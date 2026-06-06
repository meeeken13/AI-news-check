"""設定（対象サイト・定数・環境変数）。"""

import os

from dotenv import load_dotenv

# ローカル実行時は .env を読む。CI では環境変数が直接渡るので影響しない。
load_dotenv()

# --- 環境変数 ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")

# --- 動作パラメータ ---
MAX_PER_RUN = 5          # 1回の実行でClaude生成する最大記事数
FRESHNESS_HOURS = 48     # 公開からこの時間以内の記事のみ対象
REQUEST_DELAY = 1.5      # サイトへのアクセス間隔（秒）
GEN_DELAY = 3.0          # Claude生成ごとのスリープ（秒, API負荷対策）
ARTICLES_PER_SITE = 10   # 各サイトの一覧から取得する最大件数

# スクレイピング時に名乗る User-Agent（マナー: 明示する）
USER_AGENT = (
    "Mozilla/5.0 (compatible; AINewsScraper/1.0; "
    "+https://github.com/meeeken13/AI-news-check)"
)

# Claude モデル
CLAUDE_MODEL = "claude-sonnet-4-6"

# Google Sheets のシート名（GAS版と共有）
SHEET_GENERATED = "生成記事"
SHEET_PROCESSED = "処理済み"

# --- スクレイピング対象 ---
# module/class は scrapers パッケージ内のものを指す。
SITES = [
    {"company": "Google AI",  "url": "https://blog.google/technology/ai/",          "module": "google_ai", "klass": "GoogleAIScraper"},
    {"company": "Microsoft",  "url": "https://news.microsoft.com/source/topics/ai/", "module": "microsoft", "klass": "MicrosoftScraper"},
    {"company": "Anthropic",  "url": "https://www.anthropic.com/news",              "module": "anthropic", "klass": "AnthropicNewsScraper"},
    {"company": "Anthropic",  "url": "https://www.anthropic.com/engineering",       "module": "anthropic", "klass": "AnthropicEngineeringScraper"},
    {"company": "OpenAI",     "url": "https://openai.com/news/",                    "module": "openai",    "klass": "OpenAIScraper"},
    {"company": "DeepMind",   "url": "https://deepmind.google/discover/blog/",      "module": "deepmind",  "klass": "DeepMindScraper"},
]
