import os
import unittest
from unittest.mock import patch

from lotto_buy import LottoAutoBuy


class LottoBuySafetyTest(unittest.TestCase):
    def test_dry_run_requires_explicit_false_to_buy(self):
        unsafe_values = ["true", "TRUE", "true ", "1", "yes", "", " definitely-not-false "]
        for value in unsafe_values:
            with self.subTest(value=value):
                with patch.dict(os.environ, {"DRY_RUN": value}, clear=False):
                    self.assertTrue(LottoAutoBuy().dry_run)

    def test_dry_run_false_disables_dry_run(self):
        with patch.dict(os.environ, {"DRY_RUN": "false"}, clear=False):
            self.assertFalse(LottoAutoBuy().dry_run)


if __name__ == "__main__":
    unittest.main()
