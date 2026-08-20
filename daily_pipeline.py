"""
매일 실행되는 메인 파이프라인
1. 한국/미국 거래대금 상위 종목 + 미국 대표 ETF 유니버스 선정
2. 종목별 120일 캔들차트(20/60일선, RSI14, MACD) 생성 -> charts/*.png
3. Custom_Rule 기준으로 자동 등급 판정(S/A/B/매수제외)
4. reports/YYYY-MM-DD.md 리포트 생성
5. 텔레그램으로 요약 알림 발송

GitHub Actions에서 매일 실행되는 것을 전제로 작성되었습니다.
"""

import datetime
import os
import re
import sys
import time
import traceback

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))
from indicators import add_all_indicators, build_candle_chart
from rules import evaluate
import universe as U

CHART_DIR = os.path.join(os.path.dirname(__file__), "..", "charts")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
HISTORY_DAYS_CALENDAR = 300  # 최소 180 거래일 확보 목적(20/60일선 계산 버퍼 포함)

GRADE_ORDER = {"S": 0, "A": 1, "B": 2, "매수제외": 3}


def safe_filename(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_.-]", "_", name)


def fetch_kr_ohlcv(ticker: str) -> pd.DataFrame:
    from pykrx import stock

    end = datetime.date.today()
    start = end - datetime.timedelta(days=HISTORY_DAYS_CALENDAR)
    df = stock.get_market_ohlcv_by_date(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), ticker)
    df = df.rename(
        columns={"시가": "Open", "고가": "High", "저가": "Low", "종가": "Close", "거래량": "Volume"}
    )
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def fetch_us_ohlcv(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=False)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return df


def analyze_one(item: dict) -> dict:
    market = item["market"]
    ticker = item["ticker"]
    name = item.get("name", ticker)

    if market == "KR":
        df = fetch_kr_ohlcv(ticker)
        currency = "원"
    else:
        df = fetch_us_ohlcv(ticker)
        currency = "$"

    if df is None or len(df) < 65:
        raise RuntimeError(f"데이터 부족({0 if df is None else len(df)}행)")

    df = add_all_indicators(df)

    chart_name = f"{ticker}_{safe_filename(name)}.png"
    chart_path = os.path.join(CHART_DIR, chart_name)
    title = f"{name} ({ticker}) - {market}"
    build_candle_chart(df, title, chart_path)

    verdict = evaluate(df)
    close = df["Close"].iloc[-1]

    return {
        "market": market,
        "type": item.get("type", "STOCK"),
        "ticker": ticker,
        "name": name,
        "currency": currency,
        "close": close,
        "grade": verdict.grade,
        "score": verdict.score,
        "pattern_summary": verdict.pattern_summary,
        "buy_price": verdict.buy_price,
        "stop_loss": verdict.stop_loss,
        "reasons": verdict.reasons,
        "cautions": verdict.cautions,
        "chart_file": chart_name,
    }


def fmt_price(v, currency):
    if v is None or pd.isna(v):
        return "-"
    if currency == "원":
        return f"{v:,.0f}원"
    return f"${v:,.2f}"


def build_report(results: list[dict], run_date: str) -> str:
    results_sorted = sorted(
        results, key=lambda r: (GRADE_ORDER.get(r["grade"], 9), -r["score"])
    )

    lines = [f"# 📊 Daily 종목/ETF 기술적 분석 리포트 ({run_date})", ""]
    lines.append(
        f"- 분석 종목 수: {len(results)}개 (KR 주식 / US 주식 / US ETF, 시장별 거래대금 상위 {U.TOP_N}개)"
    )
    lines.append("- 등급 기준: `claude/매매규칙-Custom_Rule.md` 규칙을 코드로 그대로 구현 (규칙 기반 자동판정)")
    lines.append("- ⚠️ 투자 참고용 정보이며 투자 조언이 아닙니다. 최종 매매 판단과 책임은 본인에게 있습니다.")
    lines.append("")
    lines.append("| 시장 | 종목명 | 종가 | 기술적 패턴 요약 | 등급 | 추천 매수가 | 손절가 | 주의사항 |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for r in results_sorted:
        cautions = " / ".join(r["cautions"]) if r["cautions"] else "-"
        lines.append(
            "| {market} | {name}({ticker}) | {close} | {pattern} | {grade} | {buy} | {stop} | {caution} |".format(
                market=r["market"],
                name=r["name"],
                ticker=r["ticker"],
                close=fmt_price(r["close"], r["currency"]),
                pattern=r["pattern_summary"],
                grade=r["grade"],
                buy=fmt_price(r["buy_price"], r["currency"]),
                stop=fmt_price(r["stop_loss"], r["currency"]),
                caution=cautions,
            )
        )

    errors = [r for r in results if r.get("error")]
    if errors:
        lines.append("")
        lines.append("## 분석 실패 종목")
        for r in errors:
            lines.append(f"- {r['name']}({r['ticker']}): {r['error']}")

    return "\n".join(lines)


def build_telegram_message(results: list[dict], run_date: str) -> str:
    picks = [r for r in results if r["grade"] in ("S", "A")]
    picks.sort(key=lambda r: (GRADE_ORDER.get(r["grade"], 9), -r["score"]))

    lines = [f"📊 {run_date} 매수 관심 종목 ({len(picks)}개)"]
    for r in picks[:15]:
        lines.append(
            f"[{r['grade']}] {r['name']}({r['market']}) 매수 {fmt_price(r['buy_price'], r['currency'])} "
            f"/ 손절 {fmt_price(r['stop_loss'], r['currency'])}"
        )
    if not picks:
        lines.append("오늘은 S/A 등급 종목이 없습니다.")
    lines.append("")
    lines.append(f"전체 리포트: reports/{run_date}.md (저장소 참고)")
    return "\n".join(lines)


def send_telegram(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[telegram] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정 - 알림 발송을 건너뜁니다.")
        return
    # 텔레그램 메시지 4096자 제한 대응
    for i in range(0, len(message), 3800):
        chunk = message[i : i + 3800]
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": chunk},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[telegram] 발송 실패: {resp.status_code} {resp.text}")
        time.sleep(0.5)


def main():
    os.makedirs(CHART_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    run_date = datetime.date.today().strftime("%Y-%m-%d")

    print("[1/4] 유니버스 선정 중...")
    kr = U.get_kr_stock_universe()
    for item in kr:
        item["type"] = "STOCK"
    us = U.get_us_stock_universe()
    etf = U.get_us_etf_universe()
    full_universe = kr + us + etf
    print(f" - KR 주식 {len(kr)} / US 주식 {len(us)} / US ETF {len(etf)} (총 {len(full_universe)}종목)")

    print("[2/4] 종목별 차트 생성 및 규칙 판정 중...")
    results = []
    for idx, item in enumerate(full_universe, 1):
        label = f"{item.get('name', item['ticker'])}({item['ticker']})"
        try:
            r = analyze_one(item)
            results.append(r)
            print(f"  ({idx}/{len(full_universe)}) {label}: {r['grade']} (score={r['score']})")
        except Exception as e:
            print(f"  ({idx}/{len(full_universe)}) {label}: 실패 - {e}")
            results.append(
                {
                    "market": item["market"],
                    "type": item.get("type", "STOCK"),
                    "ticker": item["ticker"],
                    "name": item.get("name", item["ticker"]),
                    "currency": "원" if item["market"] == "KR" else "$",
                    "close": None,
                    "grade": "매수제외",
                    "score": -99,
                    "pattern_summary": "데이터 오류",
                    "buy_price": None,
                    "stop_loss": None,
                    "reasons": [],
                    "cautions": [str(e)],
                    "chart_file": None,
                    "error": str(e),
                }
            )
        time.sleep(0.3)  # 데이터 소스 과다 호출 방지

    print("[3/4] 리포트 생성 중...")
    report_md = build_report(results, run_date)
    report_path = os.path.join(REPORT_DIR, f"{run_date}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f" - 저장: {report_path}")

    print("[4/4] 텔레그램 알림 발송 중...")
    tg_message = build_telegram_message(results, run_date)
    send_telegram(tg_message)

    print("완료.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
