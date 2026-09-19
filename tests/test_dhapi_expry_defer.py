import unittest
from unittest.mock import Mock

from dhapi_expry_defer import (
    DEFER_URL,
    defer_password_change,
    finish_dhapi_login_session,
    is_expiry_notice_error,
    wrap_login,
)


class ExpiryNoticeDetectionTest(unittest.TestCase):
    def test_matches_the_18_sep_cron_error(self):
        message = (
            "로그인에 실패했습니다. (Status: 200, URL: "
            "https://www.dhlottery.co.kr/mbrsrvc/ExpryPswdNoti)"
        )
        self.assertTrue(is_expiry_notice_error(message))

    def test_wrong_password_is_not_deferred(self):
        self.assertFalse(
            is_expiry_notice_error("로그인에 실패했습니다. 아이디 또는 비밀번호를 확인해주세요.")
        )


class DeferPasswordChangeTest(unittest.TestCase):
    def test_posts_empty_json_to_later_endpoint(self):
        session = Mock()
        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = {"data": {"userId": "x"}}
        session.post.return_value = resp

        data = defer_password_change(session)

        self.assertEqual(data["data"]["userId"], "x")
        session.post.assert_called_once()
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], DEFER_URL)
        self.assertEqual(kwargs["json"], {})
        self.assertNotIn("password", str(kwargs).lower())
        self.assertNotIn("userPswd", str(kwargs))

    def test_rejects_non_json_and_result_code(self):
        session = Mock()
        bad_status = Mock(status_code=500)
        session.post.return_value = bad_status
        with self.assertRaises(RuntimeError):
            defer_password_change(session)

        html = Mock(status_code=200)
        html.json.side_effect = ValueError("not json")
        session.post.return_value = html
        with self.assertRaises(RuntimeError):
            defer_password_change(session)

        refused = Mock(status_code=200)
        refused.json.return_value = {"resultCode": "FAIL"}
        session.post.return_value = refused
        with self.assertRaises(RuntimeError):
            defer_password_change(session)


class WrapLoginTest(unittest.TestCase):
    def test_defers_then_finishes_session_on_expiry_notice(self):
        original = Mock(side_effect=RuntimeError(
            "로그인에 실패했습니다. (Status: 200, URL: "
            "https://www.dhlottery.co.kr/mbrsrvc/ExpryPswdNoti)"
        ))
        client = Mock()
        client._base_url = "https://www.dhlottery.co.kr"
        client._game645_page = "https://ol.dhlottery.co.kr/olotto/game/game645.do"
        ok = Mock(status_code=200)
        ok.json.return_value = {"data": {}}
        client._session.post.return_value = ok

        wrap_login(original)(client)

        client._session.post.assert_called_once()
        self.assertEqual(client._session.post.call_args[0][0], DEFER_URL)
        client._session.get.assert_any_call(
            "https://www.dhlottery.co.kr/main", timeout=10
        )
        client._session.get.assert_any_call(
            client._game645_page, timeout=10, allow_redirects=True
        )

    def test_wrong_password_is_not_swallowed(self):
        original = Mock(
            side_effect=RuntimeError("로그인에 실패했습니다. 아이디 또는 비밀번호를 확인해주세요.")
        )
        client = Mock()
        with self.assertRaises(RuntimeError):
            wrap_login(original)(client)
        client._session.post.assert_not_called()

    def test_finish_login_hits_main_and_game_page(self):
        client = Mock()
        client._base_url = "https://www.dhlottery.co.kr"
        client._game645_page = "https://ol.dhlottery.co.kr/olotto/game/game645.do"
        finish_dhapi_login_session(client, timeout=3)
        self.assertEqual(client._session.get.call_count, 2)


class ExecCommandTest(unittest.TestCase):
    def test_lotto_buy_keeps_audit_command_and_wraps_exec(self):
        from lotto_buy import DHAPI_EXPRY_WRAPPER, dhapi_exec_command

        audit = ["dhapi", "buy-lotto645", "1,2,3,4,5,6", "-y"]
        exec_cmd = dhapi_exec_command(audit)
        self.assertEqual(exec_cmd[1], str(DHAPI_EXPRY_WRAPPER))
        self.assertEqual(exec_cmd[2:], ["buy-lotto645", "1,2,3,4,5,6", "-y"])
        self.assertEqual(audit[0], "dhapi")


if __name__ == "__main__":
    unittest.main()
