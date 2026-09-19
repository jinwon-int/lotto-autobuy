#!/usr/bin/env python3
"""Defer dhlottery 90-day password-change nag without changing the password.

After a successful login the site may redirect to /mbrsrvc/ExpryPswdNoti.
The page's "다음에 변경" button calls POST /sy/updatePswdChgLate.do (30-day
deferral). dhapi 4.2.4 treats that redirect as login failure.

This module monkeypatches LotteryClient._login so the Friday cron can continue
the purchase. It never submits a new password.
"""
from __future__ import annotations

import json
import sys

EXPRY_URL_MARK = "ExpryPswdNoti"
DEFER_URL = "https://www.dhlottery.co.kr/sy/updatePswdChgLate.do"
DEFER_REFERER = "https://www.dhlottery.co.kr/mbrsrvc/ExpryPswdNoti"


def is_expiry_notice_error(message: str) -> bool:
    return EXPRY_URL_MARK in (message or "")


def defer_password_change(session, timeout: int = 10):
    """POST the same payload as fn_chgPwdLater. Raises on failure. No password."""
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/json;charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "AJAX": "true",
        "requestMenuUri": "/mbrsrvc/ExpryPswdNoti",
        "Origin": "https://www.dhlottery.co.kr",
        "Referer": DEFER_REFERER,
    }
    resp = session.post(DEFER_URL, headers=headers, json={}, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(
            f"비밀번호 다음에 변경 요청 실패 (Status: {resp.status_code})"
        )
    try:
        data = resp.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("비밀번호 다음에 변경 응답이 JSON이 아닙니다") from exc
    if not isinstance(data, dict):
        raise RuntimeError("비밀번호 다음에 변경 응답 형식이 올바르지 않습니다")
    if data.get("resultCode"):
        raise RuntimeError(
            f"비밀번호 다음에 변경이 거절됐습니다 ({data.get('resultCode')})"
        )
    return data


def finish_dhapi_login_session(client, timeout: int = 10) -> None:
    """Continue the tail of dhapi 4.2.4 _login after the expiry nag is deferred."""
    session = client._session
    session.get(f"{client._base_url}/main", timeout=timeout)
    session.get(client._game645_page, timeout=timeout, allow_redirects=True)


def wrap_login(original_login):
    def _login(self):
        try:
            return original_login(self)
        except RuntimeError as exc:
            if not is_expiry_notice_error(str(exc)):
                raise
            defer_password_change(self._session)
            print(
                "dhlottery password expiry notice: deferred with 다음에 변경 "
                "(no password change)",
                file=sys.stderr,
            )
            finish_dhapi_login_session(self)
            return None

    return _login


def install() -> None:
    from dhapi.port.lottery_client import LotteryClient

    if getattr(LotteryClient._login, "_expry_defer_installed", False):
        return
    patched = wrap_login(LotteryClient._login)
    patched._expry_defer_installed = True
    LotteryClient._login = patched


def main(argv: list[str] | None = None) -> None:
    install()
    args = list(sys.argv[1:] if argv is None else argv)
    sys.argv = ["dhapi", *args]
    from dhapi.main import main as dhapi_main

    dhapi_main()


if __name__ == "__main__":
    main()
