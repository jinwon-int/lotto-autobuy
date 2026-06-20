import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lotto_check import build_win_message, check_rank, evaluate_games, get_winning_numbers, main
from lotto_strategy import STRATEGY_ID, build_dhapi_command, generate_strategy_c_games, save_purchase_state


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class LottoCheckTest(unittest.TestCase):
    def test_get_winning_numbers_uses_draw_specific_internal_api(self):
        captured_urls = []
        payload = {
            "resultCode": None,
            "resultMessage": None,
            "data": {
                "list": [
                    {
                        "ltEpsd": 1120,
                        "ltRflYmd": "20240518",
                        "tm1WnNo": 2,
                        "tm2WnNo": 19,
                        "tm3WnNo": 26,
                        "tm4WnNo": 31,
                        "tm5WnNo": 38,
                        "tm6WnNo": 41,
                        "bnsWnNo": 34,
                        "rnk1WnAmt": 2522165250,
                        "rnk1WnNope": 11,
                    }
                ]
            },
        }

        def fake_urlopen(request, timeout):
            captured_urls.append(request.full_url)
            return FakeResponse(payload)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = get_winning_numbers(1120)

        self.assertIn("srchLtEpsd=1120", captured_urls[0])
        self.assertEqual(result["draw_no"], 1120)
        self.assertEqual(result["numbers"], {2, 19, 26, 31, 38, 41})
        self.assertEqual(result["bonus"], 34)

    def test_checker_skips_dry_run_state_without_network_or_output(self):
        games = generate_strategy_c_games(draw_no=1229)
        with TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "lotto-last-purchase.json"
            save_purchase_state(
                state_path,
                draw_no=1229,
                games=games,
                status="dry_run",
                command=build_dhapi_command(games),
            )
            stdout = io.StringIO()
            with patch("lotto_check.default_state_path", return_value=state_path), patch(
                "urllib.request.urlopen"
            ) as urlopen, redirect_stdout(stdout):
                rc = main()

        self.assertEqual(rc, 0)
        self.assertEqual(stdout.getvalue(), "")
        urlopen.assert_not_called()

    def test_check_rank_matches_lotto_rules(self):
        self.assertEqual(check_rank(6, False), "🎉🎉🎉 1등 (잭팟!)")
        self.assertEqual(check_rank(5, True), "🎊 2등")
        self.assertEqual(check_rank(5, False), "🎊 3등")
        self.assertEqual(check_rank(4, False), "💰 4등 (5만원)")
        self.assertEqual(check_rank(3, False), "💵 5등 (5천원)")
        self.assertIsNone(check_rank(2, True))

    def test_evaluate_games_reports_only_winning_games(self):
        games = [
            [1, 2, 3, 4, 5, 6],
            [10, 20, 30, 32, 40, 44],
        ]
        wins = evaluate_games(games, {1, 2, 3, 7, 8, 9}, bonus=4)
        self.assertEqual(len(wins), 1)
        self.assertEqual(wins[0]["index"], 1)
        self.assertEqual(wins[0]["matched"], [1, 2, 3])
        self.assertTrue(wins[0]["has_bonus"])
        self.assertEqual(wins[0]["rank"], "💵 5등 (5천원)")

    def test_build_win_message_includes_state_draw_and_game(self):
        state = {
            "strategy": STRATEGY_ID,
            "draw_no": 1229,
            "status": "purchased",
        }
        result = {
            "draw_no": 1229,
            "draw_date": "2026-06-20",
            "numbers": {1, 2, 3, 4, 5, 6},
            "bonus": 7,
            "prize_1st": 2_000_000_000,
            "winners_1st": 12,
        }
        wins = [
            {
                "index": 2,
                "game": [1, 2, 3, 10, 20, 30],
                "matched": [1, 2, 3],
                "has_bonus": False,
                "rank": "💵 5등 (5천원)",
            }
        ]
        message = build_win_message(state, result, wins)
        self.assertIn("구매회차: 1229", message)
        self.assertIn("게임 2: 1,2,3,10,20,30", message)
        self.assertIn("2,000,000,000원", message)


if __name__ == "__main__":
    unittest.main()
