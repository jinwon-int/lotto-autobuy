"""Strategy C v2 helpers for Lotto 6/45.

The strategy is deterministic per draw number for auditability, but changes
between draws.  It avoids the previous hot-number set, obvious crowd patterns,
and stores the exact purchased games so the result checker compares the right
numbers later.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import random
import tempfile
from itertools import combinations
from pathlib import Path
from typing import Iterable, List, Sequence

MAX_GAMES_PER_PURCHASE = 5
STRATEGY_ID = "strategy-c-v2-dynamic-anti-crowd"
PRIOR_TOP6_HOT_NUMBERS = {34, 27, 13, 12, 45, 18}
KST = _dt.timezone(_dt.timedelta(hours=9))


def default_state_path() -> Path:
    return Path(os.getenv("LOTTO_STATE_FILE", "~/.hermes/state/lotto-last-purchase.json")).expanduser()


def latest_draw_no(now: _dt.datetime | None = None) -> int:
    """Return the expected Lotto 6/45 draw number for the current KST week."""
    first_draw = _dt.date(2002, 12, 7)
    current = (now or _dt.datetime.now(KST)).astimezone(KST).date()
    days_until_sat = (5 - current.weekday()) % 7
    this_saturday = current + _dt.timedelta(days=days_until_sat)
    return 1 + (this_saturday - first_draw).days // 7


def format_game(game: Sequence[int]) -> str:
    return ",".join(str(n) for n in sorted(game))


def build_dhapi_command(games: Sequence[Sequence[int]]) -> List[str]:
    validate_strategy_c_games(games, game_count=len(games))
    return ["dhapi", "buy-lotto645", *[format_game(game) for game in games], "-y"]


def _has_consecutive_numbers(game: Sequence[int]) -> bool:
    return any(right - left == 1 for left, right in zip(game, game[1:]))


def _has_obvious_arithmetic_triplet(game: Sequence[int]) -> bool:
    # Short-gap 3-term arithmetic progressions (e.g. 10,20,30 is less visually
    # card-pattern-like than 5,10,15, so only reject gaps up to 7).
    values = set(game)
    for a, b, c in combinations(sorted(values), 3):
        if b - a == c - b and b - a <= 7:
            return True
    return False


def _valid_single_game(game: Sequence[int]) -> bool:
    numbers = sorted(game)
    if len(numbers) != 6 or len(set(numbers)) != 6:
        return False
    if any(n < 1 or n > 45 for n in numbers):
        return False
    if set(numbers) & PRIOR_TOP6_HOT_NUMBERS:
        return False
    high_count = sum(1 for n in numbers if n > 31)
    low_count = 6 - high_count
    odd_count = sum(n % 2 for n in numbers)
    if high_count < 2 or low_count > 4:
        return False
    if odd_count < 2 or odd_count > 4:
        return False
    if _has_consecutive_numbers(numbers):
        return False
    if _has_obvious_arithmetic_triplet(numbers):
        return False
    # Avoid very low/high sums that humans and generators often cluster around
    # less intentionally. The normal 6-number mean is 138.
    if not 105 <= sum(numbers) <= 175:
        return False
    return True


def validate_strategy_c_games(
    games: Sequence[Sequence[int]],
    *,
    game_count: int = MAX_GAMES_PER_PURCHASE,
) -> None:
    if len(games) != game_count:
        raise ValueError(f"expected {game_count} games, got {len(games)}")
    normalized = [sorted(game) for game in games]
    if len({tuple(game) for game in normalized}) != len(normalized):
        raise ValueError("duplicate game combinations are not allowed")
    for game in normalized:
        if not _valid_single_game(game):
            raise ValueError(f"invalid Strategy C game: {game}")
    for left, right in combinations(normalized, 2):
        if len(set(left) & set(right)) > 2:
            raise ValueError(f"games overlap too much: {left} vs {right}")


def _recent_set(recent_games: Iterable[Sequence[int]] | None) -> set[tuple[int, ...]]:
    return {tuple(sorted(game)) for game in (recent_games or [])}


def generate_strategy_c_games(
    *,
    draw_no: int,
    game_count: int = MAX_GAMES_PER_PURCHASE,
    recent_games: Iterable[Sequence[int]] | None = None,
    seed_salt: str = "",
) -> List[List[int]]:
    """Generate deterministic anti-crowd games for a draw.

    Same draw number + salt returns the same games.  Different draw numbers
    produce different games.  `recent_games` can be supplied to avoid exact
    repeats from the previous stored purchase.
    """
    if game_count < 1 or game_count > MAX_GAMES_PER_PURCHASE:
        raise ValueError(f"game_count must be 1..{MAX_GAMES_PER_PURCHASE}")

    rng = random.Random(f"{STRATEGY_ID}:{draw_no}:{seed_salt}")
    low_pool = [n for n in range(1, 32) if n not in PRIOR_TOP6_HOT_NUMBERS]
    high_pool = [n for n in range(32, 46) if n not in PRIOR_TOP6_HOT_NUMBERS]
    recent = _recent_set(recent_games)
    games: List[List[int]] = []

    for _attempt in range(30000):
        if len(games) == game_count:
            validate_strategy_c_games(games, game_count=game_count)
            return games

        high_count = rng.choice([2, 3])
        low_count = 6 - high_count
        candidate = sorted(rng.sample(low_pool, low_count) + rng.sample(high_pool, high_count))
        candidate_tuple = tuple(candidate)
        if candidate_tuple in recent:
            continue
        if candidate_tuple in {tuple(game) for game in games}:
            continue
        if not _valid_single_game(candidate):
            continue
        if any(len(set(candidate) & set(existing)) > 2 for existing in games):
            continue
        games.append(candidate)

    raise RuntimeError("could not generate enough Strategy C games under constraints")


def save_purchase_state(
    path: str | Path,
    *,
    draw_no: int,
    games: Sequence[Sequence[int]],
    status: str,
    command: Sequence[str],
    generated_at: str | None = None,
) -> dict:
    validate_strategy_c_games(games, game_count=len(games))
    state = {
        "schema_version": 1,
        "strategy": STRATEGY_ID,
        "draw_no": int(draw_no),
        "generated_at": generated_at or _dt.datetime.now(KST).isoformat(),
        "status": status,
        "games": [list(map(int, game)) for game in games],
        "command": list(command),
    }
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(target.parent),
        prefix=f".{target.name}.",
        delete=False,
    ) as tmp:
        json.dump(state, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(target)
    return state


def load_purchase_state(path: str | Path) -> dict:
    target = Path(path).expanduser()
    data = json.loads(target.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported purchase state schema: {data.get('schema_version')}")
    if data.get("strategy") != STRATEGY_ID:
        raise ValueError(f"unsupported strategy: {data.get('strategy')}")
    games = [list(map(int, game)) for game in data.get("games", [])]
    validate_strategy_c_games(games, game_count=len(games))
    data["games"] = games
    return data
