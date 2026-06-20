import unittest

from lotto_buy import MAX_GAMES_PER_PURCHASE, STRATEGY_C_NUMBERS, LottoAutoBuy


PRIOR_TOP6 = {34, 27, 13, 12, 45, 18}


class StrategyCNumbersTest(unittest.TestCase):
    def test_strategy_c_has_five_distinct_valid_games(self):
        self.assertEqual(len(STRATEGY_C_NUMBERS), MAX_GAMES_PER_PURCHASE)
        self.assertEqual(len({tuple(game) for game in STRATEGY_C_NUMBERS}), MAX_GAMES_PER_PURCHASE)

        for game in STRATEGY_C_NUMBERS:
            self.assertEqual(len(game), 6)
            self.assertEqual(game, sorted(game))
            self.assertEqual(len(set(game)), 6)
            self.assertTrue(all(1 <= number <= 45 for number in game))

    def test_strategy_c_avoids_prior_top6_hot_numbers(self):
        used_numbers = {number for game in STRATEGY_C_NUMBERS for number in game}
        self.assertFalse(used_numbers & PRIOR_TOP6)

    def test_strategy_c_reduces_common_crowd_patterns(self):
        for game in STRATEGY_C_NUMBERS:
            high_numbers = [number for number in game if number > 31]
            self.assertGreaterEqual(len(high_numbers), 3)

            # Avoid obvious consecutive-number runs such as 1,2 or 33,34.
            for left, right in zip(game, game[1:]):
                self.assertGreater(right - left, 1)

    def test_get_strategy_numbers_returns_copy_and_honors_count(self):
        buyer = LottoAutoBuy()
        games = buyer.get_strategy_numbers(3)
        self.assertEqual(games, STRATEGY_C_NUMBERS[:3])
        games[0][0] = 99
        self.assertNotEqual(games[0], STRATEGY_C_NUMBERS[0])


if __name__ == '__main__':
    unittest.main()
