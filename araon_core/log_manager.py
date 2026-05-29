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
        for folder in ('log', 'setup_log'):
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

