"""
籌碼評分引擎 — 把各來源的原始資料,算成 s1~s5 五項分數與總分。

設計原則:每一項都獨立成函式、各有滿分上限,方便日後調權重或抽換邏輯。
缺資料時退讓給「中性值」,不讓某項缺漏拖垮整體(鬆耦合:好調、好換)。

評分表:
  s1 法人籌碼 (0-30)  外資+投信買超強度          來源 T86
  s2 主力分點 (0-20)  分點集中度                  來源 broker(未啟用→中性 10)
  s3 融資融券 (0-15)  券增/資減=籌碼乾淨(逆向)   來源 MI_MARGN
  s4 技術面   (0-20)  站上均線、量增              來源 累積價量
  s5 動能位置 (0-15)  RSI + 20 日位置             來源 累積價量
"""
from __future__ import annotations
from . import indicators as ind

S2_NEUTRAL = 10  # 主力分點資料源未啟用時的中性分


def score_institutional(inst: dict, volume_shares: float) -> tuple[int, str | None]:
    """s1:法人籌碼(0-30)。以三大法人合計買超佔當日成交量比重衡量。"""
    if not inst or volume_shares <= 0:
        return 0, None
    total = inst.get("total", 0.0)
    ratio = total / volume_shares  # 買超股數 / 當日成交股數
    raw = 15 + ratio * 300         # 0% → 15 分(中性),正向加分、負向扣分
    s = max(0, min(30, round(raw)))
    note = None
    if inst.get("foreign", 0) > 0 and inst.get("trust", 0) > 0:
        note = "外資投信同買"
    elif total > 0:
        note = "法人偏多"
    elif total < 0:
        note = "法人偏空"
    return s, note


def score_broker(conc: dict | None) -> tuple[int, str | None]:
    """s2:主力分點(0-20)。資料源未啟用時回中性值。"""
    if not conc:
        return S2_NEUTRAL, None
    c = conc.get("concentration", 0.0)
    return max(0, min(20, round(10 + c * 10))), ("主力進駐" if c > 0 else None)


def score_margin(mg: dict) -> tuple[int, str | None]:
    """s3:融資融券(0-15)。融券增加 / 融資減少 → 籌碼乾淨,逆向加分。"""
    if not mg:
        return 7, None
    margin_chg = mg.get("margin_bal", 0) - mg.get("margin_prev", 0)
    short_chg = mg.get("short_bal", 0) - mg.get("short_prev", 0)
    s, note = 7, None  # 中性起點
    if margin_chg < 0:           # 融資減 → 散戶退場,籌碼乾淨
        s += 4
        note = "融資減"
    if short_chg > 0:            # 融券增 → 潛在軋空力道
        s += 4
        note = (note + "、券增") if note else "融券增"
    if margin_chg > 0 and short_chg < 0:  # 散戶追、空方縮 → 偏弱
        s -= 4
    return max(0, min(15, s)), note


def score_technical(closes: list[float], volume: float, avg_vol: float | None) -> tuple[int, str | None]:
    """s4:技術面(0-20)。站上 5/20 日均線、量增為加分。"""
    if not closes:
        return 0, None
    s, notes = 0, []
    last = closes[-1]
    ma5, ma20 = ind.sma(closes, 5), ind.sma(closes, 20)
    if ma5 is not None and last >= ma5:
        s += 6
        notes.append("站上5日線")
    if ma20 is not None and last >= ma20:
        s += 6
        notes.append("站上月線")
    if ma5 is not None and ma20 is not None and ma5 >= ma20:
        s += 4  # 短均在長均之上 = 多頭排列
    if avg_vol and volume > avg_vol * 1.3:
        s += 4
        notes.append("量增")
    if ma20 is None:  # 歷史不足,給中性底分避免一律 0
        s = max(s, 8)
    return max(0, min(20, s)), ("、".join(notes) or None)


def score_momentum(closes: list[float]) -> tuple[int, int | None, int | None, str | None]:
    """s5:動能位置(0-15)。回 (分數, rsi, pos, note)。"""
    rsi = ind.rsi(closes)
    pos = ind.position_in_range(closes, 20)
    if rsi is None and pos is None:
        return 7, None, None, None  # 資料不足 → 中性
    s = 0
    if rsi is not None:
        if 50 <= rsi <= 70:
            s += 8  # 強勢但未過熱,最佳
        elif rsi < 50:
            s += 4
        else:
            s += 2  # 過熱(>70)
    if pos is not None:
        s += round(pos / 100 * 7)
    note = None
    if rsi is not None and rsi > 75:
        note = "過熱留意"
    return max(0, min(15, s)), rsi, pos, note


def grade(score: int) -> str:
    """總分轉建議強度。"""
    if score >= 72:
        return "strong"
    if score >= 55:
        return "mid"
    return "watch"
