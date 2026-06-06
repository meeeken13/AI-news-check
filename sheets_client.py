"""Google Sheets の読み書き（gspread + サービスアカウント認証）。

GAS版と同じスプレッドシートを共有する。「生成記事」シートの A〜F 列は
GAS互換のため順序を変えてはならない。企業名は G 列に追記する。
"""

import json
import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from config import (
    GOOGLE_SERVICE_ACCOUNT_JSON,
    SHEET_GENERATED,
    SHEET_PROCESSED,
    SPREADSHEET_ID,
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    def __init__(self):
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.sh = self.gc.open_by_key(SPREADSHEET_ID)

    def fetch_processed_urls(self) -> set[str]:
        """「処理済み」シートのA列（記事URL）を集合で返す（重複チェック用）。"""
        ws = self.sh.worksheet(SHEET_PROCESSED)
        # A列のみ取得。1行目がヘッダーでもURL重複判定には影響しない。
        urls = ws.col_values(1)
        return {u.strip() for u in urls if u.strip()}

    def append_generated(self, source: dict, note: dict) -> None:
        """「生成記事」シートに追記。A〜F は GAS互換、G に企業名。

        source: ``{"title", "url", "company", ...}``
        note:   ``{"title", "body"}``
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws = self.sh.worksheet(SHEET_GENERATED)
        row = [
            now,                # A 処理日時
            source["title"],    # B 元記事タイトル
            source["url"],      # C 元記事URL
            note["title"],      # D noteタイトル（生成）
            note["body"],       # E note本文（生成）
            "🏢 公式",          # F ソース種別（固定）
            source["company"],  # G 企業名（GAS版にはない追加列）
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")

    def append_processed(self, source: dict) -> None:
        """「処理済み」シートに追記（A:URL / B:タイトル / C:処理日時）。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws = self.sh.worksheet(SHEET_PROCESSED)
        ws.append_row(
            [source["url"], source["title"], now],
            value_input_option="USER_ENTERED",
        )
