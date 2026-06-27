import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lotto_check import (
    build_result_message,
    build_win_message,
    check_rank,
    evaluate_all_games,
    evaluate_games,
    get_winning_numbers,
    main,
)
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

    def test_evaluate_all_games_includes_no_win_entries(self):
        games = [
            [1, 2, 3, 4, 5, 6],
            [10, 20, 30, 32, 40, 44],
        ]
        outcomes = evaluate_all_games(games, {1, 2, 3, 7, 8, 9}, bonus=4)
        self.assertEqual(len(outcomes), 2)
        # winning entry preserved
        self.assertEqual(outcomes[0]["rank"], "💵 5등 (5천원)")
        # no-win entry surfaced (rank=None) instead of being dropped
        self.assertIsNone(outcomes[1]["rank"])
        self.assertEqual(outcomes[1]["matched"], [])

    def test_build_result_message_includes_no_win_games(self):
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
        outcomes = [
            {
                "index": 1,
                "game": [10, 20, 30, 31, 32, 33],
                "matched": [],
                "has_bonus": False,
                "rank": None,
            },
            {
                "index": 2,
                "game": [1, 2, 3, 10, 20, 30],
                "matched": [1, 2, 3],
                "has_bonus": False,
                "rank": "💵 5등 (5천원)",
            },
        ]
        message = build_result_message(state, result, outcomes)
        self.assertIn("게임 1: 10,20,30,31,32,33", message)
        self.assertIn("꽝", message)
        self.assertIn("게임 2: 1,2,3,10,20,30", message)
        self.assertIn("💵 5등 (5천원)", message)
        self.assertIn("총평: 당첨 1건 / 총 2게임", message)

    def test_main_prints_full_report_even_when_no_win(self):
        # Regression guard: PR #9 fixed silent-on-no-win for the dash version;
        # the underscore checker (added in #11) reintroduced the bug because
        # `if wins: print(...)` skipped output entirely on no-win weeks. The
        # no-agent cron delivery saw empty stdout and sent nothing to Telegram.
        # Use the real Strategy C generator (which save_purchase_state validates)
        # and synthesize winning numbers disjoint from every generated game so
        # the result is guaranteed 꽝 across all 5 games.
        games = generate_strategy_c_games(draw_no=1229)
        used: set[int] = set()
        for game in games:
            used.update(int(n) for n in game)
        available = sorted(set(range(1, 46)) - used)
        self.assertGreaterEqual(
            len(available),
            7,
            "Strategy C v2 should leave >=7 numbers free of the 5 generated games",
        )
        win_numbers = available[:6]
        bonus = available[6]
        payload = {
            "data": {
                "list": [
                    {
                        "ltEpsd": 1229,
                        "ltRflYmd": "20260620",
                        "tm1WnNo": win_numbers[0],
                        "tm2WnNo": win_numbers[1],
                        "tm3WnNo": win_numbers[2],
                        "tm4WnNo": win_numbers[3],
                        "tm5WnNo": win_numbers[4],
                        "tm6WnNo": win_numbers[5],
                        "bnsWnNo": bonus,
                        "rnk1WnAmt": 1_500_000_000,
                        "rnk1WnNope": 10,
                    }
                ]
            }
        }

        with TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "lotto-last-purchase.json"
            save_purchase_state(
                state_path,
                draw_no=1229,
                games=games,
                status="purchased",
                command=build_dhapi_command(games),
            )
            stdout = io.StringIO()
            with patch("lotto_check.default_state_path", return_value=state_path), patch(
                "urllib.request.urlopen", side_effect=lambda req, timeout: FakeResponse(payload)
            ), redirect_stdout(stdout):
                rc = main()

        self.assertEqual(rc, 0)
        out = stdout.getvalue()
        # Header must always print, even on no-win
        self.assertIn("제1229회 로또 6/45 당첨 확인", out)
        self.assertIn("구매회차: 1229", out)
        # 꽝 line must surface so the user sees the actual result for every game
        self.assertIn("꽝", out)
        self.assertIn(f"총평: 당첨 0건 / 총 {len(games)}게임", out)
        # No winning rank tag emojis should appear on any per-game line.
        # (Plain "N등" is excluded because the header line "1등 당첨금" /
        # "1등 당첨자" is informational, not a per-game win.)
        for losing_emoji in ("🎉🎉🎉", "🎊", "💰", "💵"):
            self.assertNotIn(losing_emoji, out)

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
