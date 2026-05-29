# Copyright (c) 2026 swseokx. All rights reserved.

"""
araon_core/playwright_manager.py
LMS 작업용 Playwright 세션 래퍼.

Selenium 경로를 제거하지 않고 병행 적용하기 위한 최소 계층이다.
브라우저 설치/런타임 문제가 있으면 호출 측에서 Selenium fallback 을 탄다.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote


def _normalize_person_name(name: str) -> str:
    return re.sub(r'\s+', '', (name or '').strip()).lower()


def _is_same_person_name(expected: str, actual: str) -> bool:
    expected_key = _normalize_person_name(expected)
    actual_key = _normalize_person_name(actual)
    if not expected_key or not actual_key:
        return False
    return actual_key == expected_key or actual_key.startswith(expected_key + '(')


def extract_member_ref(raw: str) -> dict[str, str] | None:
    """LMS 상세 URL/JS href에서 안전한 member_id/member_seq/detail_url을 만든다."""
    raw = html.unescape(raw or '')
    mid = re.search(r'member_id=([^&\'",\s)]+)', raw, re.IGNORECASE)
    mseq = re.search(r'member_seq=(\d+)', raw, re.IGNORECASE)

    if not (mid and mseq):
        js_args = re.search(r"['\"](\d+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", raw)
        if js_args and not mseq:
            mseq_value = js_args.group(1)
            mid_value = js_args.group(2)
        else:
            return None
    else:
        mid_value = mid.group(1)
        mseq_value = mseq.group(1)

    member_id = unquote(html.unescape(mid_value)).strip()
    member_seq = re.sub(r'\D+', '', mseq_value)
    if not member_id or not member_seq:
        return None

    detail_url = (
        'https://www.lmsone.com/wcms/member/memManage/memWrite.asp'
        f'?mode=U&member_id={quote(member_id, safe="")}&member_seq={member_seq}'
    )
    return {
        'member_id': member_id,
        'member_seq': member_seq,
        'detail_url': detail_url,
    }


@dataclass
class PlaywrightLmsSession:
    """단일 LMS 브라우저 세션."""

    lms_id: str
    lms_pw: str
    headless: bool = False
    timeout_ms: int = 10000
    background: bool = False

    def __post_init__(self) -> None:
        self._pw: Any = None
        self.browser: Any = None
        self.context: Any = None
        self.page: Any = None

    def start(self) -> 'PlaywrightLmsSession':
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                'Playwright 패키지가 설치되어 있지 않습니다.'
            ) from exc

        self._pw = sync_playwright().start()
        launch_args = ['--disable-popup-blocking']
        if self.background:
            launch_args.append('--window-position=-32000,-32000')
        self.browser = self._pw.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )
        self.context = self.browser.new_context(
            viewport=None,
            ignore_https_errors=True,
        )
        self.context.on('dialog', lambda dialog: dialog.accept())
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.timeout_ms)
        return self

    def login(self) -> None:
        page = self._require_page()
        page.goto('https://www.lmsone.com/wcms/', wait_until='domcontentloaded')
        page.locator('#user_id').fill(self.lms_id)
        page.locator('#user_pw').fill(self.lms_pw)
        page.locator('.loginBtn a').click()
        page.wait_for_url(re.compile(r'.*wcms.*'), timeout=self.timeout_ms)

    def search_student_ref(self, name: str) -> dict[str, str] | None:
        page = self._require_page()
        page.goto(
            'https://www.lmsone.com/wcms/member/memManage/memList.asp',
            wait_until='domcontentloaded',
        )
        keyword = page.locator("input[name='keyword'], input[name='keyWord']").first
        keyword.fill(name)
        keyword.press('Enter')
        page.wait_for_load_state('domcontentloaded')
        page.wait_for_timeout(350)

        target_key = _normalize_person_name(name)
        fallback: dict[str, str] | None = None
        links = page.locator('table tbody tr a').all()
        for link in links:
            try:
                text = (link.text_content() or '').strip()
                link_key = _normalize_person_name(text)
                if link_key != target_key and not link_key.startswith(target_key + '('):
                    continue
                raw = (
                    link.get_attribute('href')
                    or link.get_attribute('onclick')
                    or ''
                )
                ref = extract_member_ref(raw)
                if ref and link_key == target_key:
                    return ref
                if ref and fallback is None:
                    fallback = ref
            except Exception:
                continue
        return fallback

    def open_student(self, name: str) -> bool:
        ref = self.search_student_ref(name)
        if not ref:
            return False
        return self.open_detail_by_url(ref['detail_url'], expected_name=name)

    def open_detail_by_url(self, detail_url: str, expected_name: str = '') -> bool:
        ref = extract_member_ref(detail_url)
        if not ref:
            return False
        page = self._require_page()
        page.goto(ref['detail_url'], wait_until='domcontentloaded')
        frame = self._detail_frame()
        if frame is None:
            page.reload(wait_until='domcontentloaded')
            frame = self._detail_frame()
        if frame is None:
            return False
        if expected_name:
            page_name = self._input_value(frame, '#user_nm')
            if page_name and not _is_same_person_name(expected_name, page_name):
                return False
        return True

    def extract_student_info(self, expected_name: str = '') -> dict[str, str]:
        info = {
            'id': '-', 'nm': '-', 'sch': '-', 'grd': '-',
            'p_nm': '-', 'hp': '-', 'p_hp': '-', 'history': '',
            'detail_url': '',
        }
        page = self._require_page()
        ref = extract_member_ref(page.url or '')
        if ref:
            info['detail_url'] = ref['detail_url']

        frame = self._detail_frame()
        if frame is None:
            return info

        info['id'] = self._input_value(frame, '#user_id') or '-'
        info['nm'] = self._input_value(frame, '#user_nm') or '-'
        if expected_name and info['nm'] != '-' and not _is_same_person_name(expected_name, info['nm']):
            raise RuntimeError(f'LMS 상세페이지 이름 불일치: {expected_name} != {info["nm"]}')
        info['sch'] = self._input_value(frame, '#school_nm') or '-'
        info['p_nm'] = self._input_value(frame, "[name='parents_nm']") or '-'
        info['grd'] = self._selected_text_or_value(frame, '#school_year_cd') or '-'

        hp1 = self._selected_text_or_value(frame, '#hp1')
        hp2 = self._input_value(frame, "[name='hp2'], #hp2")
        hp3 = self._input_value(frame, '#hp3')
        if hp1 or hp2 or hp3:
            info['hp'] = f'{hp1}-{hp2}-{hp3}'

        p1 = self._selected_text_or_value(frame, '#parents_hp1')
        p2 = self._input_value(frame, '#parents_hp2')
        p3 = self._input_value(frame, '#parents_hp3')
        if p1 or p2 or p3:
            info['p_hp'] = f'{p1}-{p2}-{p3}'

        try:
            rows = frame.locator('#memMagTable tbody tr').all()
            history = ''
            for idx in range(0, len(rows), 2):
                if idx + 1 >= len(rows):
                    continue
                header = rows[idx].locator('td').first.text_content()
                content = rows[idx + 1].text_content()
                header = (header or '').replace('M', '').replace('X', '').strip()
                content = (content or '').strip()
                if header or content:
                    history += f'■ {header}\n{content}\n' + '-' * 50 + '\n'
            info['history'] = history or '등록된 상담 이력이 없습니다.'
        except Exception:
            info['history'] = '이력을 불러오지 못했습니다.'

        return info

    def write_note(self, text: str) -> bool:
        frame = self._detail_frame()
        if frame is None:
            return False

    def get_member_gb(self) -> str:
        frame = self._detail_frame()
        if frame is None:
            return ''
        try:
            return (
                frame.locator('#member_gb').evaluate(
                    """el => {
                        if (el.tagName && el.tagName.toLowerCase() === 'select') {
                            const opt = el.options[el.selectedIndex];
                            return (opt && opt.value) || el.value || '';
                        }
                        return el.value || '';
                    }"""
                ) or ''
            ).strip()
        except Exception:
            return ''

    def save_attendance(self, sdate: str, edate: str) -> bool:
        frame = self._detail_frame()
        if frame is None:
            return False
        try:
            attend = frame.locator('#attend_yn').first
            if attend.count() > 0 and not attend.is_checked():
                attend.click()
            frame.evaluate(
                """([sdate, edate]) => {
                    const s = document.getElementsByName('attend_Sdate');
                    if (s.length) s[0].value = sdate;
                    const e = document.getElementsByName('attend_Edate');
                    if (e.length) e[0].value = edate;
                }""",
                [sdate, edate],
            )
            try:
                frame.locator("input[type='button'][name='학생정보저장']").first.click()
            except Exception:
                frame.evaluate("() => { if (typeof Submit === 'function') Submit(); }")
            self._require_page().wait_for_timeout(700)
            return True
        except Exception:
            return False
        try:
            frame.locator('#qna_content').fill(text)
            for selector, value in [
                ('#incall_gb', '417'),
                ('#qna_gb', 'etc'),
                ('#call_gb', '903'),
            ]:
                frame.locator(selector).select_option(value=value)
            frame.locator("input.button2g[value='저장']").click()
            self._require_page().wait_for_timeout(700)
            return True
        except Exception:
            return False

    def bring_to_front(self) -> None:
        try:
            page = self._require_page()
            page.bring_to_front()
        except Exception:
            pass

    @property
    def url(self) -> str:
        try:
            return self._require_page().url or ''
        except Exception:
            return ''

    def close(self) -> None:
        for obj in (self.context, self.browser):
            try:
                if obj:
                    obj.close()
            except Exception:
                pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    def _require_page(self):
        if self.page is None:
            raise RuntimeError('Playwright 세션이 시작되지 않았습니다.')
        return self.page

    def _detail_frame(self):
        page = self._require_page()
        for _attempt in range(20):
            for frame in [page.main_frame, *page.frames]:
                try:
                    if frame.locator('#user_id').count() > 0:
                        return frame
                except Exception:
                    continue
            page.wait_for_timeout(250)
        return None

    @staticmethod
    def _input_value(frame, selector: str) -> str:
        try:
            loc = frame.locator(selector).first
            if loc.count() == 0:
                return ''
            return (loc.input_value() or '').strip()
        except Exception:
            return ''

    @staticmethod
    def _selected_text_or_value(frame, selector: str) -> str:
        try:
            loc = frame.locator(selector).first
            if loc.count() == 0:
                return ''
            return loc.evaluate(
                """el => {
                    if (el.tagName && el.tagName.toLowerCase() === 'select') {
                        const opt = el.options[el.selectedIndex];
                        return (opt && (opt.text || opt.value)) || '';
                    }
                    return el.value || el.textContent || '';
                }"""
            ).strip()
        except Exception:
            return ''


class PlaywrightManager:
    """Playwright 세션 생성/종료 헬퍼."""

    @staticmethod
    def create_lms_session(
        lms_id: str,
        lms_pw: str,
        *,
        headless: bool = False,
        background: bool = False,
        timeout_ms: int = 10000,
    ) -> PlaywrightLmsSession:
        session = PlaywrightLmsSession(
            lms_id=lms_id,
            lms_pw=lms_pw,
            headless=headless,
            background=background,
            timeout_ms=timeout_ms,
        ).start()
        session.login()
        return session

    @staticmethod
    def create_browser_session(
        *,
        headless: bool = False,
        background: bool = False,
        user_data_dir: str | None = None,
        timeout_ms: int = 10000,
    ) -> dict[str, Any]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError('Playwright 패키지가 설치되어 있지 않습니다.') from exc

        pw = sync_playwright().start()
        args = ['--disable-popup-blocking']
        if background:
            args.append('--window-position=-32000,-32000')
        if user_data_dir:
            context = pw.chromium.launch_persistent_context(
                user_data_dir,
                headless=headless,
                args=args,
                viewport=None,
                ignore_https_errors=True,
            )
            browser = None
        else:
            browser = pw.chromium.launch(headless=headless, args=args)
            context = browser.new_context(viewport=None, ignore_https_errors=True)
        context.on('dialog', lambda dialog: dialog.accept())
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(timeout_ms)
        return {'playwright': pw, 'browser': browser, 'context': context, 'page': page}

    @staticmethod
    def safe_close_browser_session(session) -> None:
        if session is None:
            return
        try:
            context = session.get('context')
            if context:
                context.close()
        except Exception:
            pass
        try:
            browser = session.get('browser')
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            pw = session.get('playwright')
            if pw:
                pw.stop()
        except Exception:
            pass

    @staticmethod
    def safe_close(session) -> None:
        if session is None:
            return
        try:
            session.close()
        except Exception:
            pass
