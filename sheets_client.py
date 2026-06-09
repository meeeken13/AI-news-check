"""Google Sheets の読み書き（gspread + サービスアカウント認証）。

GAS版と同じスプレッドシートを共有する。「生成記事」シートの A〜F 列は
GAS互換のため順序を変えてはならない。企業名は G 列に追記する。
"""

from __future__ import annotations

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

    def append_generated(self, source: dict, detail: dict) -> None:
        """「生成記事」シートに追記。

        source: ``{"title", "url", "company", "published_str", ...}``
        detail: ``{"title", "body"}``
        """
        self._append_row(source, detail["title"], detail["body"], "🏢 公式")

    def _append_row(self, source: dict, title: str, body: str, label: str) -> None:
        """「生成記事」シートに1行追記。A〜F は GAS互換、G企業名・H公開日。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws = self.sh.worksheet(SHEET_GENERATED)
        row = [
            now,                          # A 処理日時
            source["title"],              # B 元記事タイトル
            source["url"],                # C 元記事URL
            title,                        # D noteタイトル（速報 or 詳細）
            body,                         # E note本文
            label,                        # F ソース種別（🏢 公式 / 🏢 公式（詳細））
            source["company"],            # G 企業名
            source.get("published_str", ""),  # H 記事の公開日（YYYY-MM-DD）
        ]
        ws.append_row(row, value_input_option="USER_ENTERED", table_range="A1")

    def append_processed(self, source: dict) -> None:
        """「処理済み」シートに追記（A:URL / B:タイトル / C:処理日時）。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws = self.sh.worksheet(SHEET_PROCESSED)
        ws.append_row(
            [source["url"], source["title"], now],
            value_input_option="USER_ENTERED",
            table_range="A1",
        )
