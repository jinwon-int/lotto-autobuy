"""Lotto 6/45 Winning Check Script (대교 cronjob, no_agent mode)
Runs every Saturday 22:00 KST. Always outputs a full result table.
Uses dhlottery.co.kr/lt645/selectPstLt645Info.do API."""
import datetime
import json
import urllib.request

STRATEGY_NAME = "Strategy C — 비인기 패턴 회피 + 분산 5조합"
OUR_GAMES = [
    {2, 19, 31, 33, 40, 44},
    {5, 21, 28, 35, 39, 43},
    {8, 23, 30, 32, 37, 42},
    {10, 24, 29, 36, 38, 41},
    {14, 20, 26, 33, 39, 44},
]
KST = datetime.timezone(datetime.timedelta(hours=9))


def fmt_game(game):
    return ",".join(str(n) for n in sorted(game))


def get_latest_draw_no():
    """Calculate latest draw number based on date.
    Lotto 645 started 2002-12-07 (Saturday), draw #1.
    Draws happen every Saturday.
    """
    first_draw = datetime.date(2002, 12, 7)
    today = datetime.datetime.now(KST).date()
    days_until_sat = (5 - today.weekday()) % 7
    this_saturday = today + datetime.timedelta(days=days_until_sat)
    weeks = (this_saturday - first_draw).days // 7
    return 1 + weeks


def get_winning_numbers(draw_no):
    """Fetch winning numbers for a given draw."""
    url = f"https://dhlottery.co.kr/lt645/selectPstLt645Info.do?drwNo={draw_no}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36"
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    results = data.get("data", {}).get("list", [])
    if not results:
        raise RuntimeError(f"No results for draw {draw_no}")

    r = results[0]
    return {
        "draw_no": r["ltEpsd"],
        "draw_date": f"{r['ltRflYmd'][:4]}-{r['ltRflYmd'][4:6]}-{r['ltRflYmd'][6:]}",
        "numbers": {r["tm1WnNo"], r["tm2WnNo"], r["tm3WnNo"],
                     r["tm4WnNo"], r["tm5WnNo"], r["tm6WnNo"]},
        "bonus": r["bnsWnNo"],
        "prize_1st": r.get("rnk1WnAmt", 0),
        "winners_1st": r.get("rnk1WnNope", 0),
    }


def check_rank(match_count, has_bonus):
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


def main():
    try:
        draw_no = get_latest_draw_no()
        result = get_winning_numbers(draw_no)
    except Exception:
        try:
            result = get_winning_numbers(draw_no - 1)
        except Exception as e:
            print(f"❌ 당첨번호 조회 실패: {e}")
            return

    win_set = result["numbers"]
    bonus = result["bonus"]
    wins = []
    for idx, game in enumerate(OUR_GAMES, start=1):
        matched = game & win_set
        match_count = len(matched)
        has_bonus = bonus in game
        rank = check_rank(match_count, has_bonus)
        if rank:
            wins.append((idx, game, matched, has_bonus, rank))

    prize = result.get("prize_1st", 0)
    winners = result.get("winners_1st", 0)
    print(f"🎰 [{result['draw_date']}] 제{result['draw_no']}회 로또 6/45 당첨 확인")
    print(f"전략: {STRATEGY_NAME}")
    print(f"당첨번호: {', '.join(map(str, sorted(win_set)))} + 보너스 {bonus}")
    print(f"1등 당첨금: {prize:,}원 / 1등 당첨자: {winners}명")
    print()
    print("| 게임 | 번호 | 맞춘 개수 | 결과 |")
    print("|:--:|------|:--:|:--:|")
    for idx, game in enumerate(OUR_GAMES, start=1):
        matched_nums = game & win_set
        match_count = len(matched_nums)
        has_bonus_flag = bonus in game
        rank = check_rank(match_count, has_bonus_flag)
        rank_text = rank if rank else "*꽝*"
        print(f"| {idx} | {fmt_game(game)} | {match_count} | {rank_text} |")
    if wins:
        print()
        for idx, game, matched, has_bonus_flag, rank in wins:
            print(
                f"🎊 게임 {idx}: {fmt_game(game)} → "
                f"맞춘 번호 {sorted(matched)} ({len(matched)}개), "
                f"보너스 {'O' if has_bonus_flag else 'X'} → {rank}"
            )
    else:
        print()
        print("😔 이번 주는 아쉽게도 당첨이 없습니다. 다음 주를 기약합니다!")


if __name__ == "__main__":
    main()
