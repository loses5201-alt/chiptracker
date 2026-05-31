"""
技術指標計算 — 純函式,輸入收盤價序列,輸出指標。

刻意不依賴 pandas/numpy,用純 Python 實作,維持零第三方相依。
所有函式對「資料不足」都會優雅退讓(回傳 None),由呼叫端決定如何處理。
"""
from __future__ import annotations


def sma(closes: list[float], period: int) -> float | None:
    """簡單移動平均。資料不足回 None。"""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def rsi(closes: list[float], period: int = 14) -> float | None:
    """相對強弱指標 RSI。資料不足(需 period+1 筆)回 None。"""
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return round(100 - 100 / (1 + rs), 1)


def position_in_range(closes: list[float], window: int = 20) -> int | None:
    """
    最新收盤價在近 window 日高低區間中的位置,回 0~100。
    0 = 在區間最低、100 = 在區間最高。資料不足回 None。
    """
    if len(closes) < 2:
        return None
    seg = closes[-window:]
    lo, hi = min(seg), max(seg)
    if hi == lo:
        return 50
    return round((seg[-1] - lo) / (hi - lo) * 100)
