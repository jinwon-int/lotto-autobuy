#!/usr/bin/env python3
"""Lotto 6/45 winning checker for Strategy C v2 state files.

The checker reads the last purchase state written by lotto_buy.py. This avoids
comparing stale hard-coded numbers after Strategy C starts changing every draw.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from typing import Iterable, Sequence

from lotto_strategy import default_state_path, latest_draw_no, load_purchase_state


def get_winning_numbers(draw_no: int) -> dict:
    # `drwNo` on this endpoint can be ignored by the live service and return the
    # latest draw. `srchLtEpsd` is the draw-specific parameter verified against
    # the internal JSON endpoint.
    url = (
        "https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do"
        f"?srchLtEpsd={draw_no}&_={int(time.time() * 1000)}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36",
            "Accept": "application/json,text/javascript,*/*;q=0.01",
            "Referer": "https://www.dhlottery.co.kr/lt645/result",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    results = data.get("data", {}).get("list", [])
    if not results:
        raise RuntimeError(f"No results for draw {draw_no}")

    row = results[0]
    return {
        "draw_no": int(row["ltEpsd"]),
        "draw_date": f"{row['ltRflYmd'][:4]}-{row['ltRflYmd'][4:6]}-{row['ltRflYmd'][6:]}",
        "numbers": {
            int(row["tm1WnNo"]),
            int(row["tm2WnNo"]),
            int(row["tm3WnNo"]),
            int(row["tm4WnNo"]),
            int(row["tm5WnNo"]),
            int(row["tm6WnNo"]),
        },
        "bonus": int(row["bnsWnNo"]),
        "prize_1st": int(row.get("rnk1WnAmt", 0) or 0),
        "winners_1st": int(row.get("rnk1WnNope", 0) or 0),
    }


def check_rank(match_count: int, has_bonus: bool) -> str | None:
    if match_count == 6:
        return "🎉🎉🎉 1등 (잭팟!)"
    if match_count == 5 and has_bonus:
        return "🎊 2등"
    if match_count == 5:
        return "🎊 3등"
    if match_count == 4:
        return "💰 4등 (5만원)"
    if match_count == 3:
        return "💵 5등 (5천원)"
    return None


def evaluate_games(games: Iterable[Sequence[int]], winning_numbers: set[int], bonus: int) -> list[dict]:
    wins = []
    for index, game in enumerate(games, start=1):
        game_set = set(map(int, game))
        matched = sorted(game_set & winning_numbers)
        has_bonus = bonus in game_set
        rank = check_rank(len(matched), has_bonus)
        if rank:
            wins.append(
                {
                    "index": index,
                    "game": sorted(game_set),
                    "matched": matched,
                    "has_bonus": has_bonus,
                    "rank": rank,
                }
            )
    return wins


def build_win_message(state: dict, result: dict, wins: list[dict]) -> str:
    lines = [
        f"🎰 [{result['draw_date']}] 제{result['draw_no']}회 로또 6/45 당첨 확인",
        f"전략: {state['strategy']}",
        f"구매상태: {state.get('status', 'unknown')} / 구매회차: {state['draw_no']}",
        f"당첨번호: {', '.join(map(str, sorted(result['numbers'])))} + 보너스 {result['bonus']}",
        f"1등 당첨금: {result.get('prize_1st', 0):,}원 / 1등 당첨자: {result.get('winners_1st', 0)}명",
    ]
    for win in wins:
        lines.append(
            f"게임 {win['index']}: {','.join(map(str, win['game']))} → "
            f"맞춘 번호 {win['matched']} ({len(win['matched'])}개), "
            f"보너스 {'O' if win['has_bonus'] else 'X'} → {win['rank']}"
        )
    return "\n".join(lines)


def main() -> int:
    state_path = default_state_path()
    try:
        state = load_purchase_state(state_path)
    except FileNotFoundError:
        print(f"❌ 구매 state 파일 없음: {state_path}")
        return 1
    except Exception as exc:
        print(f"❌ 구매 state 로드 실패: {exc}")
        return 1

    if state.get("status") != "purchased":
        # Dry-run state records generated numbers for audit/dry-run verification,
        # but those tickets were not actually bought. Stay silent in no-agent
        # mode so simulated state never creates a false winning alert.
        return 0

    target_draw = int(state.get("draw_no") or latest_draw_no())
    try:
        result = get_winning_numbers(target_draw)
    except Exception:
        # If target draw is not available yet, try the latest calculated draw and
        # then the previous draw. This mirrors the old no-agent fallback behavior.
        for fallback in [latest_draw_no(), latest_draw_no() - 1]:
            try:
                result = get_winning_numbers(fallback)
                break
            except Exception:
                result = None
        if result is None:
            print(f"❌ 당첨번호 조회 실패: draw {target_draw}")
            return 1

    if int(state["draw_no"]) != int(result["draw_no"]):
        print(f"❌ 구매회차({state['draw_no']})와 당첨회차({result['draw_no']}) 불일치")
        return 1

    wins = evaluate_games(state["games"], result["numbers"], result["bonus"])
    if wins:
        print(build_win_message(state, result, wins))
    return 0


if __name__ == "__main__":
    sys.exit(main())
