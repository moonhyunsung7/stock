"""
기술적 지표 계산 유틸리티
- 이동평균선(MA20, MA60)
- RSI(14) : Wilder's smoothing 방식
- MACD(12, 26, 9)
"""

import pandas as pd
import numpy as np


def add_moving_averages(df: pd.DataFrame, windows=(20, 60)) -> pd.DataFrame:
    df = df.copy()
    for w in windows:
        df[f"MA{w}"] = df["Close"].rolling(window=w, min_periods=w).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Wilder's smoothing 방식의 RSI(14)."""
    df = df.copy()
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)  # 초기 구간 avg_loss=0 인 경우 중립값 처리
    df["RSI14"] = rsi
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    df = df.copy()
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    df["MACD"] = macd_line
    df["MACD_SIGNAL"] = signal_line
    df["MACD_HIST"] = hist
    return df


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = add_moving_averages(df)
    df = add_rsi(df)
    df = add_macd(df)
    return df


def build_candle_chart(df: pd.DataFrame, title: str, save_path: str):
    """mplfinance 로 캔들차트 + MA20/60 + 거래량 + RSI + MACD 패널을 그려 PNG 저장."""
    import mplfinance as mpf

    plot_df = df.tail(120).copy()

    add_plots = [
        mpf.make_addplot(plot_df["MA20"], color="#1f77b4", width=1.1, panel=0),
        mpf.make_addplot(plot_df["MA60"], color="#d62728", width=1.1, panel=0),
        mpf.make_addplot(plot_df["RSI14"], panel=2, color="#8e44ad", ylabel="RSI(14)"),
        mpf.make_addplot([70] * len(plot_df), panel=2, color="#999999", linestyle="--", width=0.7),
        mpf.make_addplot([30] * len(plot_df), panel=2, color="#999999", linestyle="--", width=0.7),
        mpf.make_addplot(plot_df["MACD"], panel=3, color="#2ca02c", ylabel="MACD"),
        mpf.make_addplot(plot_df["MACD_SIGNAL"], panel=3, color="#ff7f0e"),
        mpf.make_addplot(
            plot_df["MACD_HIST"],
            type="bar",
            panel=3,
            color=["#26a69a" if v >= 0 else "#ef5350" for v in plot_df["MACD_HIST"]],
            alpha=0.6,
        ),
    ]

    mc = mpf.make_marketcolors(
        up="#26a69a", down="#ef5350", edge="inherit", wick="inherit", volume="in"
    )
    style = mpf.make_mpf_style(
        base_mpf_style="yahoo", marketcolors=mc, gridstyle="--", gridcolor="#e6e6e6"
    )

    mpf.plot(
        plot_df,
        type="candle",
        style=style,
        addplot=add_plots,
        volume=True,
        panel_ratios=(3, 1, 1, 1),
        title=title,
        figsize=(13, 11),
        tight_layout=True,
        savefig=dict(fname=save_path, dpi=150, bbox_inches="tight"),
    )
