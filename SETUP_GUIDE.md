# 📈 Daily 주식·ETF 차트분석 자동알림 — 설치 가이드

이 키트는 **매일 자동으로** 한국·미국 거래대금 상위 종목과 미국 대표 ETF의 캔들차트(20/60일선, RSI14, MACD)를 그리고,
`Custom_Rule.md` 기준으로 S/A/B/매수제외 등급을 자동 판정한 뒤, 텔레그램으로 요약 알림을 보내줍니다.
비용은 0원이며(GitHub Actions 무료 티어), 완전히 무인 자동화됩니다.

전체 과정은 약 15~20분 정도 걸립니다. 순서대로 따라 하시면 됩니다.

---

## 1단계. GitHub 계정 만들기 (5분)

1. https://github.com/signup 접속
2. 이메일(alchem1024@gmail.com 사용 가능), 비밀번호, 사용자명 입력 후 계정 생성
3. 이메일 인증 코드 확인

## 2단계. 저장소(repository) 만들기 (2분)

1. 로그인 후 우측 상단 `+` → `New repository` 클릭
2. Repository name: 예) `stock-daily-alert`
3. **Private** 선택 (본인만 볼 수 있도록 비공개 권장)
4. `Create repository` 클릭

## 3단계. 키트 파일 업로드 (3분)

받으신 `stock-alert-kit.zip` 파일의 압축을 풀면 아래와 같은 구조입니다.

```
stock-alert-kit/
├── .github/workflows/daily-alert.yml   ← 매일 자동실행 설정
├── scripts/
│   ├── daily_pipeline.py               ← 메인 실행 스크립트
│   ├── universe.py                     ← 종목 선정 로직
│   ├── indicators.py                   ← 지표 계산 + 차트 생성
│   └── rules.py                        ← 매매규칙(Custom_Rule) 자동판정 엔진
├── requirements.txt                    ← 설치할 파이썬 라이브러리 목록
├── Custom_Rule.md                      ← 매매 규칙 문서
├── charts/                             ← (자동 생성됨, 빈 폴더)
└── reports/                            ← (자동 생성됨, 빈 폴더)
```

1. 새로 만든 저장소 페이지에서 `Add file` → `Upload files` 클릭
2. 압축 푼 `stock-alert-kit` 폴더 안의 **모든 파일/폴더를 그대로 드래그 앤 드롭**
   - 주의: `stock-alert-kit` 폴더 자체가 아니라 그 **안의 내용물**을 올려야 합니다.
   - `.github` 폴더처럼 이름이 `.`으로 시작하는 폴더도 함께 끌어다 놓으면 자동으로 인식됩니다. (파일 탐색기에서 숨김 폴더가 안 보이면, 압축 프로그램에서 바로 드래그하거나 `git` 명령으로 올리는 것을 추천합니다.)
3. `Commit changes` 클릭

> 💡 git 명령을 쓸 줄 아신다면 이 방법이 더 확실합니다:
> ```
> cd stock-alert-kit
> git init
> git add .
> git commit -m "init"
> git branch -M main
> git remote add origin https://github.com/사용자명/stock-daily-alert.git
> git push -u origin main
> ```

## 4단계. 텔레그램 봇 만들기 (5분) — 푸시 알림용

1. 휴대폰에서 텔레그램 앱 설치 (없다면)
2. 텔레그램에서 `@BotFather` 검색 후 대화 시작
3. `/newbot` 입력 → 봇 이름 입력(예: `내주식알림봇`) → 봇 아이디 입력(예: `my_stock_alert_bot`, 반드시 `bot`으로 끝나야 함)
4. BotFather가 `HTTP API 토큰`을 알려줍니다. 예: `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxx` — **이 값을 복사해두세요 (TELEGRAM_BOT_TOKEN)**
5. 방금 만든 봇 이름을 검색해서 대화창을 열고 아무 메시지나 하나 보냅니다 (예: "안녕").
6. 브라우저에서 아래 주소 접속 (토큰 부분을 본인 것으로 교체):
   `https://api.telegram.org/bot본인토큰/getUpdates`
7. 응답 JSON에서 `"chat":{"id": 123456789, ...}` 부분의 숫자를 복사 — **이 값이 TELEGRAM_CHAT_ID 입니다.**

## 5단계. GitHub 저장소에 비밀값(Secrets) 등록 (2분)

1. 저장소 페이지 → `Settings` → 좌측 메뉴 `Secrets and variables` → `Actions`
2. `New repository secret` 클릭
   - Name: `TELEGRAM_BOT_TOKEN` / Value: 4단계에서 복사한 토큰
3. 다시 `New repository secret` 클릭
   - Name: `TELEGRAM_CHAT_ID` / Value: 4단계에서 복사한 chat id

## 6단계. 자동실행 확인 및 수동 테스트 (3분)

1. 저장소 상단 탭 `Actions` 클릭
2. 좌측에 `Daily Stock/ETF Chart Alert` 워크플로우가 보이면 클릭
3. 오른쪽 `Run workflow` 버튼 → `Run workflow` 클릭 (수동 1회 실행 — 테스트용)
4. 2~5분 정도 후 실행이 끝나면(초록 체크) 텔레그램으로 알림이 도착합니다.
5. 저장소의 `charts/` 폴더에 종목별 PNG 차트, `reports/` 폴더에 당일 리포트(.md)가 자동으로 쌓입니다.

이후에는 **매일 06:30 (한국시간) 자동 실행**되며(평일만), 별도 조작이 필요 없습니다.

---

## 자주 조정하는 항목

| 바꾸고 싶은 것 | 수정할 파일/위치 |
|---|---|
| 실행 시각 | `.github/workflows/daily-alert.yml` 의 `cron: "30 21 * * 1-5"` (UTC 기준, KST = UTC+9) |
| 시장별 종목 수 (현재 20개) | `scripts/universe.py` 상단 `TOP_N = 20` |
| 매매 등급 기준(배점/임계값) | `Custom_Rule.md` + `scripts/rules.py` 함께 수정 |
| ETF 후보 목록 | `scripts/universe.py` 의 `US_ETF_CANDIDATES` 리스트 |

## 문제가 생기면

- Actions 탭에서 실행 기록(빨간 X)을 클릭하면 어느 단계에서 오류가 났는지 로그로 확인할 수 있습니다.
- 흔한 원인: Secrets 이름 오타, pykrx/yfinance 일시적 접속 지연(자동 재시도 없음 — 다음날 다시 정상 실행됨), Wikipedia 페이지 구조 변경(스크립트에 폴백 종목 리스트가 내장되어 있어 완전히 멈추지는 않습니다).
- 이 대화(Claude Cowork)로 오류 로그를 붙여넣어 주시면 원인 분석과 수정까지 도와드립니다.
