"""
籌碼評分引擎(短線狙擊版)— 把各來源原始資料算成 s1~s5 五項與總分。

對齊使用者的短線四面向 + 技術動能(總分 100):
  s1 法人籌碼 (0-25)  外資+投信買超強度              來源 T86
  s2 融資動能 (0-15)  ★短線:融資增+法人同買=資金進場  來源 MI_MARGN + T86
  s3 基本面   (0-20)  月營收年增率 YoY               來源 月營收彙總
  s4 國際連動 (0-20)  所屬題材海外同業近 5 日漲幅      來源 Stooq + 題材表
  s5 技術動能 (0-20)  站上均線、量增、RSI、區間位置    來源 累積價量

設計原則:每項獨立、各有上限,缺資料退讓給中性值,不讓單一缺漏拖垮整體。
注意:s2 與前一版相反——短線把「融資增加」視為偏多(資金進場),非「融資減才好」。
"""
from __future__ import annotations
from . import indicators as ind


def score_institutional(inst: dict, volume_shares: float) -> tuple[int, str | None]:
    """s1:法人籌碼(0-25)。三大法人合計買超佔當日成交量比重。"""
    if not inst or volume_shares <= 0:
        return 0, None
    total = inst.get("total", 0.0)
    ratio = total / volume_shares
    s = max(0, min(25, round(12 + ratio * 260)))  # 0% → 12 分中性
    note = None
    if inst.get("foreign", 0) > 0 and inst.get("trust", 0) > 0:
        note = "外資投信同買"
    elif total > 0:
        note = "法人偏多"
    elif total < 0:
        note = "法人偏空"
    return s, note


def score_margin_short(mg: dict, inst: dict) -> tuple[int, str | None]:
    """
    s2:融資動能(0-15)★短線邏輯。
    融資溫和增 + 法人同步買 = 資金齊發,最強;
    融資爆增但法人沒買(散戶獨推)= 過熱,扣分;
    融券增加 = 潛在軋空力道,加分。
    """
    if not mg:
        return 7, None
    margin_chg = mg.get("margin_bal", 0) - mg.get("margin_prev", 0)
    short_chg = mg.get("short_bal", 0) - mg.get("short_prev", 0)
    margin_prev = mg.get("margin_prev", 0) or 1
    margin_pct = margin_chg / margin_prev  # 融資增減幅
    inst_buy = inst.get("total", 0) > 0

    s, notes = 7, []
    if 0 < margin_pct <= 0.10:            # 融資溫和增(≤10%)
        s += 4
        notes.append("融資進場")
    elif margin_pct > 0.10:               # 融資爆增
        if inst_buy:
            s += 3
            notes.append("資金齊發")
        else:
            s -= 3
            notes.append("散戶獨推")      # 過熱警示
    elif margin_pct < 0:                  # 融資減(短線視為動能轉弱)
        s -= 2
    if margin_pct > 0 and inst_buy:       # 融資增 + 法人買 = 加成
        s += 3
        if "資金齊發" not in notes:
            notes.append("融資法人齊買")
    if short_chg > 0:                     # 融券增 → 軋空題材
        s += 2
        notes.append("券增")
    return max(0, min(15, s)), ("、".join(notes) or None)


def score_fundamental(fund: dict | None) -> tuple[int, str | None]:
    """s3:基本面(0-20)。月營收 YoY 年增率。"""
    if not fund:
        return 8, None  # 無資料中性
    yoy = fund.get("yoy", 0.0)
    # YoY 0% → 8 分;每 +10% 約 +2.4 分,夾 0~20
    s = max(0, min(20, round(8 + yoy * 0.24)))
    note = None
    if yoy >= 30:
        note = f"營收年增{yoy:.0f}%"
    elif yoy >= 10:
        note = f"營收增{yoy:.0f}%"
    elif yoy < -10:
        note = f"營收衰退{yoy:.0f}%"
    return s, note


def score_overseas(topic: str | None, topic_mom: float) -> tuple[int, str | None]:
    """s4:國際連動(0-20)。所屬題材海外同業近 5 日漲幅。"""
    if topic is None:
        return 8, None  # 不屬任何追蹤題材 → 中性
    # 海外漲 0% → 8 分;每漲 1% 約 +1.5 分,夾 0~20
    s = max(0, min(20, round(8 + topic_mom * 1.5)))
    note = None
    if topic_mom >= 3:
        note = f"{topic}海外強({topic_mom:+.1f}%)"
    elif topic_mom <= -3:
        note = f"{topic}海外弱({topic_mom:+.1f}%)"
    else:
        note = topic  # 至少標示題材
    return s, note


def score_momentum(closes: list[float], volume: float, avg_vol: float | None) -> tuple[int, int | None, int | None, str | None]:
    """s5:技術動能(0-20)。站上均線 + 量增 + RSI + 區間位置。回 (分數, rsi, pos, note)。"""
    if not closes:
        return 10, None, None, None
    s, notes = 0, []
    last = closes[-1]
    ma5, ma20 = ind.sma(closes, 5), ind.sma(closes, 20)
    rsi = ind.rsi(closes)
    pos = ind.position_in_range(closes, 20)

    if ma5 is not None and last >= ma5:
        s += 5
        notes.append("站上5日線")
    if ma20 is not None and last >= ma20:
        s += 4
        notes.append("站上月線")
    if ma5 is not None and ma20 is not None and ma5 >= ma20:
        s += 3  # 多頭排列
    if avg_vol and volume > avg_vol * 1.3:
        s += 3
        notes.append("量增")
    if rsi is not None:
        if 50 <= rsi <= 75:
            s += 3  # 強勢未過熱(短線偏好)
        elif rsi > 80:
            s -= 2
            notes.append("過熱")
    if pos is not None and pos >= 60:
        s += 2  # 位於區間中上 = 強勢
    if ma20 is None:
        s = max(s, 10)  # 歷史不足給中性底分
    return max(0, min(20, s)), rsi, pos, ("、".join(notes) or None)


def grade(score: int) -> str:
    """總分(滿分 100)轉建議強度。"""
    if score >= 70:
        return "strong"
    if score >= 55:
        return "mid"
    return "watch"
