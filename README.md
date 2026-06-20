# Lotto AutoBuy (로또 자동 구매)

동행복권 로또 6/45 자동 구매 + 당첨 확인 시스템.

## 현재 아키텍처 (2026-06-20~)

```
대교 (Seo S23 Ultra, Termux + Hermes)
├── Cron: 매주 토요일 18:00 KST → Strategy C v2 조합 생성 → dhapi buy-lotto645 → state 저장
└── Cron: 매주 토요일 22:00 KST → state의 구매번호 조회 → 당첨번호 비교 → Telegram 알림
```

- **GitHub Actions는 폐기됨** — 대교가 직접 구매/확인 처리
- **비용**: $0/월 (Actions 예산 불필요)
- GitHub Actions workflow는 `workflow_dispatch` 수동 fallback만 유지

## 구매 전략

현재 기본 전략은 **Strategy C v2 — 회차별 비인기 패턴 회피 + 분산 5조합**입니다.

| 항목 | 값 |
|------|------|
| 전략 | **매 회차 새 5조합 생성** |
| 목표 | “인생 역전 대박”을 노리되, TOP6/인기번호 몰빵의 공동당첨 분할 리스크 회피 |
| 1등 도달 확률 | 서로 다른 5조합 기준 `5 / 8,145,060` |
| 주간 비용 | 5,000원 (5게임 × 1,000원) |
| 운영 경로 | 대교 Hermes cronjob에서 `lotto_buy.py` 또는 동등 로직 실행 |
| state 파일 | 기본 `~/.hermes/state/lotto-last-purchase.json` |

## Strategy C v2 설계

### 핵심 흐름

1. 구매 시점에 해당 회차 번호(`draw_no`)를 계산한다.
2. `draw_no`를 seed로 사용해 **결정론적이지만 회차별로 달라지는** 5조합을 생성한다.
3. `dhapi buy-lotto645 <game1> ... <game5> -y`로 구매한다.
4. 구매 성공 또는 dry-run 결과를 state 파일에 저장한다.
5. 당첨 확인은 hard-coded 번호가 아니라 **state 파일의 해당 회차 구매번호**를 읽어 비교한다.

### 생성 제약

`lotto_strategy.py`가 다음 조건을 검증합니다.

- 5게임 모두 서로 다른 조합
- 각 게임은 1~45 범위의 정렬된 6개 고유 번호
- 이전 TOP6 hot-number 세트 `{34, 27, 13, 12, 45, 18}` 제외
- 게임별 고번호(`>31`) 최소 2개 포함
- 게임별 생일대 번호(`<=31`) 최대 4개
- 홀짝 균형: 홀수 2~4개
- 연속수 금지
- 짧은 등차 3연 패턴 금지
- 조합 합계 극단값 회피
- 게임 간 번호 중복 최대 2개
- 직전 state의 조합과 exact repeat 회피

### 왜 고정 5조합에서 바꿨나

고정 Strategy C는 TOP6 몰빵보다 낫지만, 시간이 지나면 다시 “항상 같은 5조합”이 됩니다. v2는 다음 문제를 해결합니다.

1. 매 회차 조합을 바꿔 장기 반복 패턴을 줄임
2. 구매번호를 state로 남겨 당첨 확인 정확성 보장
3. 생성은 deterministic per draw라 재현/감사 가능
4. `LOTTO_SEED_SALT`로 필요 시 노드별 seed 편차 가능

## 명령 예시

### Dry-run

```bash
DRY_RUN=true LOTTO_DRAW_NO=1229 LOTTO_STATE_FILE=/tmp/lotto-state.json python lotto_buy.py
```

- 실제 구매는 **정규화된 `DRY_RUN=false`일 때만** 실행됩니다.
- `DRY_RUN=true `, `DRY_RUN=1`, 빈 값, 오타 등은 모두 fail-safe dry-run입니다.
- dry-run state는 audit용이며 `lotto_check.py`는 실제 당첨 확인처럼 처리하지 않고 조용히 skip합니다.

### 실제 구매 fallback

```bash
DRY_RUN=false LOTTO_STATE_FILE=~/.hermes/state/lotto-last-purchase.json python lotto_buy.py
```

### 당첨 확인

```bash
LOTTO_STATE_FILE=~/.hermes/state/lotto-last-purchase.json python lotto_check.py
```

## 기술 스택

- **[dhapi](https://github.com/roeniss/dhlottery-api)** v4.2.4 — 동행복권 비공식 API
- **Hermes cronjob** — 스케줄링 및 알림 전달
- **Telegram** — 구매/당첨 결과 알림

## GitHub Actions (레거시, 수동 fallback용)

`.github/workflows/lotto-buy.yml`은 `workflow_dispatch`로만 수동 트리거 가능.
스케줄은 비활성화됨.

## 번호 변경 이력

| 날짜 | 번호 | 전략 | 사유 |
|------|------|------|------|
| 2026-06-20 | 회차별 자동 생성 | Strategy C v2: dynamic anti-crowd + state 저장 | 고정 조합 반복 제거, 당첨 확인 정확성 보장 |
| 2026-06-20 | 2,19,31,33,40,44 / 5,21,28,35,39,43 / 8,23,30,32,37,42 / 10,24,29,36,38,41 / 14,20,26,33,39,44 | Strategy C v1: 비인기 패턴 회피 + 분산 5조합 | TOP6 인기번호 몰빵의 공동당첨 분할 리스크 회피, 1등 도달 확률 5배 확보 |
| 2026-06-20 | 4,6,7,11,12,23 | 동일 ×5 | 인기번호 회피, 분할 리스크 최소화 |
| 2026-06-19 | 34,27,13,12,45,18 | 동일 ×5 | TOP 6 최다 출현 |
