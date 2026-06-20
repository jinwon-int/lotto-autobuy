import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from lotto_strategy import (
    MAX_GAMES_PER_PURCHASE,
    PRIOR_TOP6_HOT_NUMBERS,
    build_dhapi_command,
    format_game,
    generate_strategy_c_games,
    load_purchase_state,
    save_purchase_state,
    validate_strategy_c_games,
)


class StrategyCV2GenerationTest(unittest.TestCase):
    def test_generation_is_deterministic_per_draw_but_changes_by_draw(self):
        games_1229_a = generate_strategy_c_games(draw_no=1229)
        games_1229_b = generate_strategy_c_games(draw_no=1229)
        games_1230 = generate_strategy_c_games(draw_no=1230)

        self.assertEqual(games_1229_a, games_1229_b)
        self.assertNotEqual(games_1229_a, games_1230)

    def test_generated_games_satisfy_anti_crowd_constraints(self):
        games = generate_strategy_c_games(draw_no=1229)
        validate_strategy_c_games(games)

        self.assertEqual(len(games), MAX_GAMES_PER_PURCHASE)
        self.assertEqual(len({tuple(game) for game in games}), MAX_GAMES_PER_PURCHASE)

        for game in games:
            self.assertEqual(game, sorted(game))
            self.assertEqual(len(game), 6)
            self.assertEqual(len(set(game)), 6)
            self.assertTrue(all(1 <= number <= 45 for number in game))
            self.assertFalse(set(game) & PRIOR_TOP6_HOT_NUMBERS)
            self.assertGreaterEqual(len([n for n in game if n > 31]), 2)
            self.assertLessEqual(len([n for n in game if n <= 31]), 4)
            self.assertGreaterEqual(sum(n % 2 for n in game), 2)
            self.assertLessEqual(sum(n % 2 for n in game), 4)
            for left, right in zip(game, game[1:]):
                self.assertGreater(right - left, 1)

        for i, game in enumerate(games):
            for other in games[i + 1:]:
                self.assertLessEqual(len(set(game) & set(other)), 2)

    def test_generation_can_avoid_recently_purchased_combinations(self):
        previous = generate_strategy_c_games(draw_no=1229)
        next_games = generate_strategy_c_games(draw_no=1230, recent_games=previous)
        self.assertFalse({tuple(g) for g in previous} & {tuple(g) for g in next_games})

    def test_dhapi_command_uses_one_argument_per_game(self):
        games = generate_strategy_c_games(draw_no=1229, game_count=2)
        command = build_dhapi_command(games)

        self.assertEqual(command[:2], ["dhapi", "buy-lotto645"])
        self.assertEqual(command[-1], "-y")
        self.assertEqual(command[2:-1], [format_game(game) for game in games])
        self.assertEqual(len(command), 5)

    def test_purchase_state_round_trips_with_draw_and_games(self):
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
            loaded = load_purchase_state(state_path)

        self.assertEqual(loaded["schema_version"], 1)
        self.assertEqual(loaded["strategy"], "strategy-c-v2-dynamic-anti-crowd")
        self.assertEqual(loaded["draw_no"], 1229)
        self.assertEqual(loaded["status"], "dry_run")
        self.assertEqual(loaded["games"], games)
        self.assertEqual(loaded["command"], build_dhapi_command(games))
