"""
분석 대상 종목 유니버스 선정
- 한국 주식: pykrx 로 코스피+코스닥 전 종목의 당일 거래대금 상위 N개 (ETF/ETN/스팩 제외)
- 미국 주식: S&P500 + 나스닥100 구성종목 중 최근 거래대금(종가*거래량) 상위 N개
- 미국 ETF: 대표 대형 ETF(지수/섹터/배당) 후보군 중 최근 거래대금 상위 N개
"""

import datetime
import io
import time

import pandas as pd
import requests

TOP_N = 20  # 시장별 종목 수 (필요시 조정)

UA = {"User-Agent": "Mozilla/5.0 (compatible; StockAlertBot/1.0)"}

# 미국 ETF 후보군 (S&P500 / 나스닥100 / 배당·섹터 대표 ETF)
US_ETF_CANDIDATES = [
    "SPY", "VOO", "IVV", "QQQ", "QQQM", "DIA", "IWM", "VTI", "SCHD", "VYM",
    "VIG", "JEPI", "JEPQ", "DGRO", "HDV", "XLK", "XLF", "XLE", "XLV", "XLY",
    "XLI", "XLU", "XLP", "XLB", "XLRE", "XLC", "SMH", "SOXX", "ARKK", "GLD",
    "SLV", "TLT", "IEF", "HYG", "LQD", "EEM", "EFA", "VEA", "VWO", "VNQ",
]


def _kr_top_stocks(n: int = TOP_N) -> list[dict]:
    from pykrx import stock

    today = datetime.date.today()
    d = today
    df = None
    # 최근 영업일 데이터가 나올 때까지 최대 7일 역행 조회 (휴장일 대비)
    for _ in range(7):
        ds = d.strftime("%Y%m%d")
        try:
            cand = stock.get_market_ohlcv_by_ticker(ds, market="ALL")
        except Exception:
            cand = None
        if cand is not None and not cand.empty and cand["거래대금"].sum() > 0:
            df = cand
            break
        d -= datetime.timedelta(days=1)

    if df is None:
        raise RuntimeError("KRX 거래대금 데이터를 가져오지 못했습니다.")

    df = df.sort_values("거래대금", ascending=False)
    result = []
    for ticker, row in df.iterrows():
        name = stock.get_market_ticker_name(ticker)
        # ETF/ETN/스팩/리츠 등 종목명 패턴 배제 (개별주만 선별)
        if any(kw in name for kw in ["ETN", "스팩", "리츠", "KODEX", "TIGER", "KBSTAR", "ACE", "SOL "]):
            continue
        result.append({"market": "KR", "ticker": ticker, "name": name})
        if len(result) >= n:
            break
    return result


def _sp500_tickers() -> list[str]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(requests.get(url, headers=UA, timeout=15).text)
    return tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()


def _nasdaq100_tickers() -> list[str]:
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tables = pd.read_html(requests.get(url, headers=UA, timeout=15).text)
    for t in tables:
        cols = [str(c) for c in t.columns]
        if any("Ticker" in c or "Symbol" in c for c in cols):
            col = [c for c in cols if "Ticker" in c or "Symbol" in c][0]
            return t[col].astype(str).str.replace(".", "-", regex=False).tolist()
    return []


def _us_dollar_volume_rank(tickers: list[str], n: int) -> list[dict]:
    import yfinance as yf

    tickers = sorted(set(tickers))
    data = yf.download(
        tickers, period="5d", interval="1d", group_by="ticker",
        auto_adjust=False, threads=True, progress=False,
    )

    rows = []
    for t in tickers:
        try:
            sub = data[t] if isinstance(data.columns, pd.MultiIndex) else data
            sub = sub.dropna()
            if sub.empty:
                continue
            last = sub.iloc[-1]
            dollar_vol = float(last["Close"]) * float(last["Volume"])
            rows.append({"ticker": t, "dollar_vol": dollar_vol})
        except Exception:
            continue

    rows.sort(key=lambda r: r["dollar_vol"], reverse=True)
    top = rows[:n]

    out = []
    for r in top:
        out.append({"market": "US", "ticker": r["ticker"], "name": r["ticker"]})
    return out


def get_kr_stock_universe(n: int = TOP_N) -> list[dict]:
    return _kr_top_stocks(n)


def get_us_stock_universe(n: int = TOP_N) -> list[dict]:
    try:
        tickers = list(set(_sp500_tickers()) | set(_nasdaq100_tickers()))
    except Exception:
        # Wikipedia 스크래핑 실패 시 대형주 위주 축소 후보군으로 폴백
        tickers = [
            "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "AVGO", "BRK-B",
            "JPM", "LLY", "V", "UNH", "XOM", "MA", "COST", "HD", "PG", "NFLX",
            "AMD", "ADBE", "CRM", "PEP", "KO", "WMT", "BAC", "CSCO", "TMO", "ABBV",
        ]
    universe = _us_dollar_volume_rank(tickers, n)
    for item in universe:
        item["type"] = "STOCK"
    return universe


def get_us_etf_universe(n: int = TOP_N) -> list[dict]:
    universe = _us_dollar_volume_rank(US_ETF_CANDIDATES, n)
    for item in universe:
        item["type"] = "ETF"
        item["market"] = "US-ETF"
    return universe


def build_full_universe() -> list[dict]:
    kr = get_kr_stock_universe()
    for item in kr:
        item["type"] = "STOCK"
    us = get_us_stock_universe()
    etf = get_us_etf_universe()
    return kr + us + etf
