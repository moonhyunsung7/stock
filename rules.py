scripts/rules.py
"""
매매 규칙 엔진 (Custom_Rule)
- 프로젝트 문서 `claude/매매규칙-Custom_Rule.md` 의 기준을 코드로 그대로 구현한 것입니다.
- 규칙을 바꾸고 싶다면 이 파일의 SCORE 배점과 하드 제외 조건만 수정하면 됩니다.

등급: S / A / B / 매수제외
"""

from dataclasses import dataclass, field
import pandas as pd
import numpy as np


@dataclass
class Verdict:
    grade: str
    score: int
    reasons: list = field(default_factory=list)
    cautions: list = field(default_factory=list)
    buy_price: float = None
    stop_loss: float = None
    pattern_summary: str = ""


def _pct(a, b):
    if b == 0 or pd.isna(b):
        return np.nan
    return (a - b) / b * 100


def evaluate(df: pd.DataFrame) -> Verdict:
    """df 는 add_all_indicators() 를 거친, 최근 데이터가 마지막 행인 DataFrame."""
    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else row

    close = row["Close"]
    ma20 = row["MA20"]
    ma60 = row["MA60"]
    rsi = row["RSI14"]
    macd = row["MACD"]
    macd_sig = row["MACD_SIGNAL"]
    hist = row["MACD_HIST"]
    prev_hist = prev["MACD_HIST"]
    vol = row["Volume"]

    vol20 = df["Volume"].tail(21).iloc[:-1].mean()  # 최근 20일(당일 제외) 평균 거래량
    vol_ratio = vol / vol20 if vol20 and not pd.isna(vol20) else np.nan

    score = 0
    reasons = []
    cautions = []
    hard_exclude = False

    # 1) 이동평균선 배열 상태 -------------------------------------------------
    if pd.isna(ma20) or pd.isna(ma60):
        cautions.append("60일 데이터 부족으로 이평선 신뢰도 낮음")
    else:
        if close > ma20 > ma60:
            score += 2
            reasons.append("정배열(주가>20일선>60일선)")
        elif close > ma20:
            score += 1
            reasons.append("20일선 위에서 거래 중이나 완전 정배열은 아님")
        elif close < ma60:
            hard_exclude = True
            cautions.append("60일선 붕괴(하락 추세 위험)")

        gap20 = _pct(close, ma20)
        if not pd.isna(gap20):
            if gap20 > 15:
                score -= 1
                cautions.append(f"20일선 이격도 과대(+{gap20:.1f}%) — 추격매수 주의")
            elif gap20 < -10:
                cautions.append(f"20일선 대비 {gap20:.1f}% 이탈 — 되돌림 구간")

    # 2) 거래량/거래대금 변화 --------------------------------------------------
    if not pd.isna(vol_ratio):
        if vol_ratio >= 1.5:
            score += 2
            reasons.append(f"거래량 급증(20일 평균 대비 {vol_ratio*100:.0f}%)")
        elif vol_ratio >= 1.2:
            score += 1
            reasons.append(f"거래량 증가(20일 평균 대비 {vol_ratio*100:.0f}%)")
        elif vol_ratio < 0.7:
            score -= 1
            cautions.append("거래량 저조 — 관심 미흡")

    # 3) RSI(14) --------------------------------------------------------------
    if not pd.isna(rsi):
        if 50 <= rsi <= 70:
            score += 2
            reasons.append(f"RSI {rsi:.0f} — 건강한 상승 모멘텀")
        elif 70 < rsi <= 80:
            score += 1
            cautions.append(f"RSI {rsi:.0f} — 과매수 근접, 추격매수 주의")
        elif rsi > 80:
            hard_exclude = True
            cautions.append(f"RSI {rsi:.0f} — 심한 과매수 구간")
        elif rsi < 30:
            hard_exclude = True
            cautions.append(f"RSI {rsi:.0f} — 약세/과매도, 추세 전환 확인 필요")

    # 4) MACD -------------------------------------------------------------
    golden_cross_recent = False
    if len(df) >= 6:
        recent = df.tail(6)
        cross_up = (recent["MACD"] - recent["MACD_SIGNAL"])
        golden_cross_recent = bool(((cross_up.shift(1) < 0) & (cross_up >= 0)).any())

    if not pd.isna(macd) and not pd.isna(macd_sig):
        if golden_cross_recent:
            score += 2
            reasons.append("최근 5거래일 내 MACD 골든크로스")
        elif macd > macd_sig and hist >= prev_hist:
            score += 1
            reasons.append("MACD 상승 모멘텀 유지")
        elif macd < macd_sig and hist <= prev_hist:
            score -= 2
            cautions.append("MACD 데드크로스 진행/하락폭 확대")
            if macd < macd_sig and hist < prev_hist and hist < 0:
                hard_exclude = True

    # 등급 산정 ----------------------------------------------------------------
    if hard_exclude:
        grade = "매수제외"
    elif score >= 7:
        grade = "S"
    elif score >= 5:
        grade = "A"
    elif score >= 3:
        grade = "B"
    else:
        grade = "매수제외"

    # 매수가 / 손절가 -----------------------------------------------------------
    buy_price = None
    stop_loss = None
    if grade != "매수제외":
        if not pd.isna(ma20) and close > ma20 * 1.02:
            buy_price = round(ma20 * 1.01, 2)  # 눌림목 지지매수 대기가
        else:
            buy_price = round(close, 2)

        low20 = df["Low"].tail(20).min()
        candidates = [v for v in [ma60, low20 * 0.99] if v and not pd.isna(v)]
        if candidates:
            stop_loss = round(min(candidates) * 0.99, 2)

    pattern_summary = ", ".join(reasons[:3]) if reasons else (cautions[0] if cautions else "특이사항 없음")

    return Verdict(
        grade=grade,
        score=score,
        reasons=reasons,
        cautions=cautions,
        buy_price=buy_price,
        stop_loss=stop_loss,
        pattern_summary=pattern_summary,
    )
