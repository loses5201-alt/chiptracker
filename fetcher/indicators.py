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


def ma_convergence(closes: list[float], periods=(5, 10, 20)) -> float | None:
    """
    均線糾結度:多條均線彼此越靠近(糾結),回傳的離散度(%)越小。
    離散度 = (最大均線 − 最小均線) / 最新價 × 100。
    糾結(數值小,如 <2.5%)代表多空在此區間僵持、能量壓縮 → 一旦帶量突破常是發動點,
    正是「主力潛伏·打底蓄勢」的量化訊號。資料不足或價為 0 回 None。
    """
    mas = [sma(closes, p) for p in periods]
    if any(m is None for m in mas):
        return None
    last = closes[-1] if closes else 0
    if not last:
        return None
    return round((max(mas) - min(mas)) / last * 100, 2)


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
