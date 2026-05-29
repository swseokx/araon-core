# Copyright (c) 2026 swseokx. All rights reserved.

"""
araon_core/sheet_manager.py
구글 시트 연동 — 인증 캐싱 + 배치 API 호출
"""

import os
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials


_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def _normalize_name(name: str) -> str:
    return re.sub(r'\s+', '', (name or '').strip()).lower()


def _same_sheet_date(cell: str, selected_date: str) -> bool:
    """시트 날짜 헤더에서 '5/2'가 '5/20'에 걸리지 않게 정확 비교."""
    match = re.search(r'(?<!\d)(\d{1,2}/\d{1,2})(?!\d)', cell or '')
    return bool(match and match.group(1) == selected_date)


def _looks_like_date_header(cell: str) -> bool:
    return bool(re.search(r'(?<!\d)\d{1,2}/\d{1,2}(?!\d)', cell or ''))


def _cell(row: list, index: int) -> str:
    return str(row[index] if index < len(row) else '').strip()


def _is_separator_cell(value: str) -> bool:
    normalized = re.sub(r'\s+', '', str(value or ''))
    return bool(re.fullmatch(r'[-‐‑‒–—―ㅡ]{2,}', normalized))


def _is_date_header_row(abc_row: list, selected_date: str | None = None) -> bool:
    """A/C가 ---인 행만 실제 날짜 헤더로 인정한다."""
    a_val = _cell(abc_row, 0)
    b_val = _cell(abc_row, 1)
    c_val = _cell(abc_row, 2)
    if not _is_separator_cell(a_val) or not _is_separator_cell(c_val):
        return False
    if selected_date is not None:
        return _same_sheet_date(b_val, selected_date)
    return _looks_like_date_header(b_val)


def _row_belongs_to_date(abc_rows: list[list], idx: int, selected_date: str) -> bool:
    """학생 행의 B열이 비어있어도 직전 날짜 헤더 기준으로 소속 날짜를 확인."""
    for j in range(min(idx, len(abc_rows) - 1), -1, -1):
        if _is_date_header_row(abc_rows[j]):
            return _is_date_header_row(abc_rows[j], selected_date)
    return False


class SheetManager:
    """
    인증 객체와 시트 객체를 캐싱하여 매번 재인증하지 않음.
    설정이 바뀌면 invalidate()를 호출해 캐시를 초기화.
    """

    def __init__(self, config_manager):
        self.cfg = config_manager
        self._client = None
        self._sheet = None

    def invalidate(self):
        """설정 변경 후 캐시 초기화."""
        self._client = None
        self._sheet = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        creds_path = os.path.join(
            self.cfg.base_path,
            self.cfg.get('DEFAULT', 'CREDENTIALS_FILE', 'credentials.json'),
        )
        if not os.path.exists(creds_path):
            raise FileNotFoundError(
                f'credentials.json 파일이 없습니다.\n'
                f'프로그램 폴더에 credentials.json 을 넣어주세요.\n'
                f'경로: {creds_path}'
            )
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, _SCOPES)
        self._client = gspread.authorize(creds)
        return self._client

    def _get_sheet(self):
        if self._sheet is not None:
            return self._sheet
        client = self._get_client()
        spreadsheet_id = self.cfg.get('MAIN_SHEET', 'SPREADSHEET_ID')
        sheet_name = self.cfg.get('MAIN_SHEET', 'SHEET_NAME', 'Sheet1')
        self._sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
        return self._sheet

    def load_day_data(self, selected_date: str) -> tuple[list[list], dict]:
        """
        선택 날짜 데이터 로드.
        반환: (filtered_rows, row_map)
          filtered_rows: [[col0..col15], ...]  (D열부터 S열, 0-indexed)
          row_map: {ui_index: actual_sheet_row_number}
        """
        sheet = self._get_sheet()

        # A~S를 행 단위로 가져와 날짜 헤더와 학생 데이터의 행 정렬을 보장한다.
        rows = sheet.get('A:S')
        abc_raw = [row[:3] for row in rows]
        ds_raw = [row[3:19] for row in rows]

        # 선택 날짜 시작 행 탐색
        start_row = next(
            (i + 1 for i, row in enumerate(abc_raw)
             if _is_date_header_row(row, selected_date)), -1
        )
        if start_row == -1:
            return [], {}

        # 종료 행 탐색
        # 날짜 헤더는 A~C에 있고 학생 행의 D~S가 더 길 수 있음.
        # 그래서 기본값을 len(abc_raw)가 아닌 len(ds_raw)로 설정해야
        # 학생 행이 누락되지 않음.
        end_row = len(ds_raw)
        for i in range(start_row, len(abc_raw)):
            if (_is_date_header_row(abc_raw[i])
                    and not _is_date_header_row(abc_raw[i], selected_date)):
                end_row = i   # 다음 날짜의 0-indexed 위치 (ds_raw와 동일 기준)
                break

        # D~S 슬라이스 (Python slice는 범위 초과를 자동으로 안전하게 처리)
        raw_data = ds_raw[start_row - 1: end_row]

        filtered_data = []
        row_map = {}
        for i, row in enumerate(raw_data):
            actual_idx = start_row - 1 + i
            if actual_idx < len(abc_raw) and _is_date_header_row(abc_raw[actual_idx]):
                continue
            if len(row) < 2:
                continue
            name_raw = str(row[1])
            if not name_raw.strip() or '학생명' in name_raw or '---' in name_raw:
                continue
            row = list(row)
            row[1] = name_raw.strip()   # 양쪽 공백만 제거, 내부 공백 유지
            filtered_data.append(row)
            row_map[len(filtered_data) - 1] = actual_idx + 1

        return filtered_data, row_map

    def mark_complete(
        self,
        actual_row: int,
        selected_date: str,
        name: str,
        status: str = 'ㅇ',
    ) -> bool:
        """
        해당 학생 행의 M열(13번째 열)에 status 기록.
        저장 버튼을 누른 시점의 행/학생명을 우선 검증해 업데이트한다.
        """
        sheet = self._get_sheet()
        # A~C 날짜 헤더와 E열 이름을 다시 읽어 정확한 행 재탐색
        batch = sheet.batch_get(['A:C', 'E:E'])
        abc_rows = batch[0]
        e_col = [row[0] if row else '' for row in batch[1]]

        def _write_and_verify(row_num: int) -> bool:
            sheet.update_cell(row_num, 13, status)
            actual = str(sheet.cell(row_num, 13).value or '').strip()
            return actual == str(status).strip()

        def _find_unique_matching_row() -> int:
            clean_name = _normalize_name(name)
            matched_rows: list[int] = []
            for i in range(start_r, max(len(abc_rows), len(e_col))):
                if i < len(abc_rows):
                    if (_is_date_header_row(abc_rows[i])
                            and not _is_date_header_row(abc_rows[i], selected_date)):
                        break
                if i < len(e_col):
                    cell_name = _normalize_name(str(e_col[i]))
                    if cell_name == clean_name:
                        matched_rows.append(i + 1)
            return matched_rows[0] if len(matched_rows) == 1 else -1

        start_r = next(
            (i for i, row in enumerate(abc_rows)
             if _is_date_header_row(row, selected_date)), -1
        )
        if start_r == -1:
            return False

        clean_name = _normalize_name(name)
        if actual_row and actual_row > 0:
            idx = actual_row - 1
            row_name = _normalize_name(str(e_col[idx] if idx < len(e_col) else ''))
            if row_name == clean_name and _row_belongs_to_date(abc_rows, idx, selected_date):
                return _write_and_verify(actual_row)

        fallback_row = _find_unique_matching_row()
        return bool(fallback_row > 0 and _write_and_verify(fallback_row))

    def load_first_class_list(self) -> list[dict]:
        """
        '첫수업명단' 시트에서 학생 목록을 반환.
        E열 = 학생명, R열 = 첫수업일.
        반환: [{'name': ..., 'first_class': ...}, ...]  (헤더/빈 행 제외)
        """
        client = self._get_client()
        spreadsheet_id = self.cfg.get('MAIN_SHEET', 'SPREADSHEET_ID')
        sheet = client.open_by_key(spreadsheet_id).worksheet('첫수업명단')

        batch = sheet.batch_get(['E:E', 'R:R'])
        e_col = [row[0] if row else '' for row in batch[0]]
        r_col = [row[0] if row else '' for row in batch[1]]

        max_len = max(len(e_col), len(r_col))
        result: list[dict] = []
        for i in range(max_len):
            name = (e_col[i] if i < len(e_col) else '').strip()
            date = (r_col[i] if i < len(r_col) else '').strip()
            if not name:
                continue
            # 헤더/구분선 필터
            if ('학생명' in name or name in ('이름', '성명', '학생이름')
                    or '---' in name):
                continue
            result.append({'name': name, 'first_class': date})
        return result

    def col_values(self, col: int) -> list[str]:
        return self._get_sheet().col_values(col)
