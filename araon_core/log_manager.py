# Copyright (c) 2026 swseokx. All rights reserved.

"""
araon_core/log_manager.py
통합 로그 관리 — 시스템 로그 + 셋업 로그를 단일 클래스로 처리
"""

import os
from datetime import datetime


class LogManager:
    """
    로그 파일 구조:
      log/YYYY-MM-DD.log          — 시스템(디버그) 로그
      setup_log/setup_YYYY-MM-DD.log — 개통/AS 실적 로그
    """

    def __init__(self, base_path: str):
        self.base_path = base_path
        for folder in ('log', 'setup_log', 'admission_log'):
            os.makedirs(os.path.join(base_path, folder), exist_ok=True)

    # ------------------------------------------------------------------
    # 시스템 로그
    # ------------------------------------------------------------------
    def write_system(self, msg: str):
        now = datetime.now()
        log_msg = f"[{now.strftime('%H:%M:%S')}] {msg}"
        log_path = os.path.join(
            self.base_path, 'log', f"{now.strftime('%Y-%m-%d')}.log"
        )
        try:
            with open(log_path, 'a+', encoding='utf-8') as f:
                f.write(log_msg + '\n')
        except OSError:
            pass
        print(log_msg)
        return log_msg  # UI 표시용으로 반환

    def read_system_today(self) -> str:
        log_path = os.path.join(
            self.base_path, 'log', f"{datetime.now().strftime('%Y-%m-%d')}.log"
        )
        if not os.path.exists(log_path):
            return '오늘 기록된 로그 파일이 없습니다.'
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return content if content.strip() else '파일은 존재하지만 내용이 비어있습니다.'
        except OSError as e:
            return f'로그 파일을 읽는 중 오류: {e}'

    # ------------------------------------------------------------------
    # 셋업(개통/AS) 로그
    # ------------------------------------------------------------------
    def write_setup(self, category: str, name: str, memo: str):
        """
        category: '개통' | 'AS'
        """
        now = datetime.now()
        memo_single = memo.replace('\n', ' ').strip()
        entry = (
            f"[{now.strftime('%H:%M:%S')}][{category}] {name} 완료"
            f" | {memo_single}\n"
        )
        log_path = os.path.join(
            self.base_path, 'setup_log', f"setup_{now.strftime('%Y-%m-%d')}.log"
        )
        try:
            with open(log_path, 'a+', encoding='utf-8') as f:
                f.write(entry)
        except OSError as e:
            self.write_system(f'셋업 로그 쓰기 실패: {e}')

    # ------------------------------------------------------------------
    # 입학식 로그
    # ------------------------------------------------------------------
    def write_admission(self, ot_time: str, name: str, checklist_str: str,
                        lms_ok: bool, sheet_ok: bool):
        """
        입학식 OT 처리 결과를 admission_log/admission_YYYY-MM-DD.log 에 기록.
        checklist_str: 예) '카톡O/레벨O/노트X/첫수업4/14/폼O/시간표O/배정X'
        """
        now = datetime.now()
        lms_tag   = 'LMS✓' if lms_ok   else 'LMS✗'
        sheet_tag = '시트✓' if sheet_ok else '시트✗'
        entry = (
            f"[{now.strftime('%H:%M:%S')}][입학식][{ot_time}] {name} "
            f"| {checklist_str} | {lms_tag} {sheet_tag}\n"
        )
        log_path = os.path.join(
            self.base_path, 'admission_log',
            f"admission_{now.strftime('%Y-%m-%d')}.log"
        )
        try:
            with open(log_path, 'a+', encoding='utf-8') as f:
                f.write(entry)
        except OSError as e:
            self.write_system(f'입학식 로그 쓰기 실패: {e}')
