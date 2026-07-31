import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_WRAPPER = REPO_ROOT / "lotto-buy-live.sh"


class TermuxRuntimeTest(unittest.TestCase):
    def test_live_wrapper_fails_before_purchase_when_runtime_is_missing(self):
        with TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["HOME"] = tmp
            env["LOTTO_PYTHON"] = str(Path(tmp) / "missing" / "python")
            result = subprocess.run(
                ["bash", str(LIVE_WRAPPER)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("runtime missing", result.stderr)

    def test_live_wrapper_uses_dedicated_runtime_and_forces_live_mode(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            bin_dir = home / "venv" / "bin"
            bin_dir.mkdir(parents=True)
            capture = home / "capture.txt"
            fake_python = bin_dir / "python"
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                'printf "dry_run=%s\\n" "$DRY_RUN" > "$LOTTO_TEST_CAPTURE"\n'
                'printf "state_file=%s\\n" "$LOTTO_STATE_FILE" >> "$LOTTO_TEST_CAPTURE"\n'
                'printf "script=%s\\n" "$1" >> "$LOTTO_TEST_CAPTURE"\n',
                encoding="utf-8",
            )
            fake_python.chmod(0o700)
            fake_dhapi = bin_dir / "dhapi"
            fake_dhapi.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_dhapi.chmod(0o700)
            credentials = home / ".dhapi" / "credentials"
            credentials.parent.mkdir()
            credentials.write_text("[default]\n", encoding="utf-8")
            credentials.chmod(0o600)

            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "DRY_RUN": "true",
                    "LOTTO_PYTHON": str(fake_python),
                    "LOTTO_TEST_CAPTURE": str(capture),
                }
            )
            result = subprocess.run(
                ["bash", str(LIVE_WRAPPER)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            captured = capture.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dry_run=false", captured)
        self.assertIn(f"state_file={home}/.hermes/state/lotto-last-purchase.json", captured)
        self.assertIn(f"script={REPO_ROOT}/lotto_buy.py", captured)


if __name__ == "__main__":
    unittest.main()
