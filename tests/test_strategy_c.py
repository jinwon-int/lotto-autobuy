import unittest

from lotto_buy import MAX_GAMES_PER_PURCHASE, LottoAutoBuy
from lotto_strategy import PRIOR_TOP6_HOT_NUMBERS, generate_strategy_c_games, validate_strategy_c_games


class StrategyCNumbersTest(unittest.TestCase):
    def test_strategy_c_v2_has_five_distinct_valid_games(self):
        games = generate_strategy_c_games(draw_no=1229)
        validate_strategy_c_games(games)
        self.assertEqual(len(games), MAX_GAMES_PER_PURCHASE)
        self.assertEqual(len({tuple(game) for game in games}), MAX_GAMES_PER_PURCHASE)

        for game in games:
            self.assertEqual(len(game), 6)
            self.assertEqual(game, sorted(game))
            self.assertEqual(len(set(game)), 6)
            self.assertTrue(all(1 <= number <= 45 for number in game))

    def test_strategy_c_v2_avoids_prior_top6_hot_numbers(self):
        games = generate_strategy_c_games(draw_no=1229)
        used_numbers = {number for game in games for number in game}
        self.assertFalse(used_numbers & PRIOR_TOP6_HOT_NUMBERS)

    def test_strategy_c_v2_reduces_common_crowd_patterns(self):
        games = generate_strategy_c_games(draw_no=1229)
        for game in games:
            high_numbers = [number for number in game if number > 31]
            self.assertGreaterEqual(len(high_numbers), 2)

            # Avoid obvious consecutive-number runs such as 1,2 or 33,34.
            for left, right in zip(game, game[1:]):
                self.assertGreater(right - left, 1)

    def test_get_strategy_numbers_returns_copy_and_honors_count(self):
        buyer = LottoAutoBuy()
        games = buyer.get_strategy_numbers(3, draw_no=1229)
        self.assertEqual(len(games), 3)
        original_first = games[0][:]
        games[0][0] = 99
        self.assertEqual(buyer.get_strategy_numbers(3, draw_no=1229)[0], original_first)


if __name__ == '__main__':
    unittest.main()
