#!/usr/bin/env python3
"""
Lotto 6/45 Auto Buy with Hermes notification.

Strategy C v2 generates a new audited anti-crowd set for each draw and stores
that exact purchase in a state file so the winning-number checker compares the
right games later.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests
import yaml

from lotto_strategy import (
    MAX_GAMES_PER_PURCHASE,
    build_dhapi_command,
    default_state_path,
    generate_strategy_c_games,
    latest_draw_no,
    load_purchase_state,
    save_purchase_state,
)


class LottoAutoBuy:
    def __init__(self):
        self.config = self.load_config()
        self.hermes_webhook = self.config.get("hermes_webhook")
        self.state_file = Path(self.config.get("state_file") or default_state_path()).expanduser()

        # dry_run resolves from env first (DRY_RUN), then config.yaml, default true (safe)
        env_dry_run = os.getenv("DRY_RUN")
        if env_dry_run is not None:
            self.dry_run = self._parse_dry_run(env_dry_run)
        else:
            self.dry_run = self._parse_dry_run(self.config.get("dry_run", True))

    @staticmethod
    def _parse_dry_run(value: Any) -> bool:
        """Fail-safe dry-run parser.

        Real purchase requires an explicit normalized false value. Everything
        else remains dry-run so typos like "true ", "1", or "yes" cannot buy.
        """
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() != "false"

    @staticmethod
    def _expand_env(value: Any) -> Any:
        """Replace ${VAR} placeholders with the matching environment variable.

        Returns None when a placeholder cannot be resolved so callers can
        fall back to defaults instead of using the literal "${VAR}" text.
        """
        if isinstance(value, str):
            expanded = os.path.expandvars(value)
            if "${" in expanded:  # unresolved placeholder, e.g. env var not set
                return None
            return expanded
        return value

    def load_config(self) -> Dict:
        config = {}
        try:
            with open("config.yaml", "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            pass

        # Expand ${VAR} placeholders loaded from yaml (safe_load keeps them literal)
        config = {k: self._expand_env(v) for k, v in config.items()}
        # Drop keys that failed to resolve so setdefault fallbacks apply
        config = {k: v for k, v in config.items() if v is not None}

        # Fall back to env vars when a value is missing or left as a placeholder
        config.setdefault("hermes_webhook", os.getenv("HERMES_WEBHOOK"))
        config.setdefault("game_count", int(os.getenv("GAME_COUNT", MAX_GAMES_PER_PURCHASE)))
        config.setdefault("draw_no", os.getenv("LOTTO_DRAW_NO"))
        config.setdefault("seed_salt", os.getenv("LOTTO_SEED_SALT", ""))
        config.setdefault("state_file", os.getenv("LOTTO_STATE_FILE"))
        return config

    def notify(self, message: str, status: str = "info", data: Dict | None = None):
        if not self.hermes_webhook:
            print(f"[{status.upper()}] {message}")
            if data:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            return
        try:
            payload = {
                "message": f"[Lotto AutoBuy] {message}",
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "data": data or {},
            }
            requests.post(self.hermes_webhook, json=payload, timeout=10)
        except Exception as e:
            print(f"Notification failed: {e}")

    def resolve_draw_no(self) -> int:
        configured = self.config.get("draw_no")
        if configured:
            return int(configured)
        return latest_draw_no()

    def load_recent_games(self, draw_no: int) -> List[List[int]]:
        if not self.state_file.exists():
            return []
        try:
            state = load_purchase_state(self.state_file)
        except Exception as exc:
            self.notify(f"Ignoring unreadable prior state: {exc}", "info")
            return []
        # Same draw should be reproducible, not forced away from itself.
        if int(state.get("draw_no", 0)) == int(draw_no):
            return []
        return state.get("games", [])

    def get_strategy_numbers(
        self,
        game_count: int = MAX_GAMES_PER_PURCHASE,
        *,
        draw_no: int | None = None,
    ) -> List[List[int]]:
        draw = draw_no or self.resolve_draw_no()
        return generate_strategy_c_games(
            draw_no=draw,
            game_count=game_count,
            recent_games=self.load_recent_games(draw),
            seed_salt=str(self.config.get("seed_salt") or ""),
        )

    def purchase(self, game_count: int = MAX_GAMES_PER_PURCHASE) -> bool:
        if game_count > MAX_GAMES_PER_PURCHASE:
            self.notify(
                f"game_count {game_count} exceeds max {MAX_GAMES_PER_PURCHASE}; capping",
                "info",
            )
            game_count = MAX_GAMES_PER_PURCHASE
        if game_count < 1:
            self.notify(f"Invalid game_count {game_count}; nothing to buy", "error")
            return False

        draw_no = self.resolve_draw_no()
        games = self.get_strategy_numbers(game_count, draw_no=draw_no)
        command = build_dhapi_command(games)
        command_text = " ".join(shlex.quote(part) for part in command)

        self.notify(
            f"Starting Strategy C v2 purchase for draw {draw_no} "
            f"({game_count} games, dry_run={self.dry_run})",
            "info",
            {"draw_no": draw_no, "games": games, "command": command},
        )

        if self.dry_run:
            state = save_purchase_state(
                self.state_file,
                draw_no=draw_no,
                games=games,
                status="dry_run",
                command=command,
            )
            self.notify(
                "Dry-run only; no purchase executed. State written for verification.",
                "success",
                {"state_file": str(self.state_file), "state": state, "command_text": command_text},
            )
            return True

        try:
            result = subprocess.run(command, text=True, capture_output=True, check=True, timeout=120)
        except subprocess.CalledProcessError as exc:
            self.notify(
                "dhapi purchase failed",
                "error",
                {
                    "command": command,
                    "returncode": exc.returncode,
                    "stdout": exc.stdout[-1000:] if exc.stdout else "",
                    "stderr": exc.stderr[-1000:] if exc.stderr else "",
                },
            )
            return False
        except Exception as exc:
            self.notify(f"Purchase exception: {exc}", "error", {"command": command})
            return False

        state = save_purchase_state(
            self.state_file,
            draw_no=draw_no,
            games=games,
            status="purchased",
            command=command,
        )
        self.notify(
            "Strategy C v2 purchase completed and state saved",
            "success",
            {
                "state_file": str(self.state_file),
                "state": state,
                "stdout": result.stdout[-1000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
            },
        )
        return True


def main():
    print(f"[{datetime.now()}] Lotto 6/45 AutoBuy started")
    buyer = LottoAutoBuy()

    try:
        success = buyer.purchase(buyer.config.get("game_count", MAX_GAMES_PER_PURCHASE))
        if success:
            buyer.notify("Lotto 6/45 AutoBuy completed successfully", "success")
        else:
            buyer.notify("Lotto 6/45 AutoBuy failed", "error")
            sys.exit(1)
    except Exception as e:
        buyer.notify(f"Critical error: {str(e)}", "error")
        print(f"Critical Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
