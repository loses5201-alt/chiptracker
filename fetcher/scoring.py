"""
籌碼評分引擎(短線狙擊·六面向)— 把各來源原始資料算成 s1~s6 與總分(滿分 100)。

對齊使用者的短線需求:資金面 + 基本面 + 國際局勢 + 題材面,外加技術動能。
  s1 法人籌碼 (0-22)  外資+投信買超強度              來源 T86
  s2 融資動能 (0-8)   ★短線:融資增+法人同買=資金進場  來源 MI_MARGN + T86
  s3 基本面   (0-20)  月營收年增率 YoY               來源 月營收彙總
  s4 國際連動 (0-20)  所屬題材海外同業近 5 日漲幅      來源 Yahoo + 題材表
  s5 題材熱度 (0-15)  ★所屬題材近 3 日新聞則數          來源 Google News RSS
  s6 技術動能 (0-15)  站上均線、量增、RSI、區間位置    來源 Yahoo 歷史

設計原則:每項獨立、各有上限,缺資料退讓給中性值,不讓單一缺漏拖垮整體。
"""
from __future__ import annotations
from . import indicators as ind


def score_institutional(inst: dict, volume_shares: float) -> tuple[int, str | None]:
    """s1:法人籌碼(0-22)。三大法人合計買超佔當日成交量比重。"""
    if not inst or volume_shares <= 0:
        return 0, None
    total = inst.get("total", 0.0)
    ratio = total / volume_shares
    s = max(0, min(22, round(11 + ratio * 240)))
    note = None
    if inst.get("foreign", 0) > 0 and inst.get("trust", 0) > 0:
        note = "外資投信同買"
    elif total > 0:
        note = "法人偏多"
    elif total < 0:
        note = "法人偏空"
    return s, note


def score_margin_short(mg: dict, inst: dict) -> tuple[int, str | None]:
    """s2:融資動能(0-8)★短線。融資溫和增+法人同買=資金齊發。"""
    if not mg:
        return 4, None
    margin_chg = mg.get("margin_bal", 0) - mg.get("margin_prev", 0)
    short_chg = mg.get("short_bal", 0) - mg.get("short_prev", 0)
    margin_prev = mg.get("margin_prev", 0) or 1
    margin_pct = margin_chg / margin_prev
    inst_buy = inst.get("total", 0) > 0

    s, notes = 4, []
    if 0 < margin_pct <= 0.10:
        s += 2
        notes.append("融資進場")
    elif margin_pct > 0.10:
        if inst_buy:
            s += 1
            notes.append("資金齊發")
        else:
            s -= 2
            notes.append("散戶獨推")
    elif margin_pct < 0:
        s -= 1
    if margin_pct > 0 and inst_buy:
        s += 1
        if "資金齊發" not in notes:
            notes.append("融資法人齊買")
    if short_chg > 0:
        s += 1
        notes.append("券增")
    return max(0, min(8, s)), ("、".join(notes) or None)


def score_fundamental(fund: dict | None) -> tuple[int, str | None]:
    """s3:基本面(0-20)。月營收 YoY 年增率。"""
    if not fund:
        return 8, None
    yoy = fund.get("yoy", 0.0)
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
        return 8, None
    s = max(0, min(20, round(8 + topic_mom * 1.5)))
    note = None
    if topic_mom >= 3:
        note = f"{topic}海外強({topic_mom:+.1f}%)"
    elif topic_mom <= -3:
        note = f"{topic}海外弱({topic_mom:+.1f}%)"
    return s, note


def score_topic_news(topic: str | None, heat: int) -> tuple[int, str | None]:
    """
    s5:題材熱度(0-15)★題材面。所屬題材近 3 日新聞則數。
    熱度高 = 市場正在炒作該題材(如黃仁勳來台帶動 AI)。
    """
    if topic is None:
        return 6, None
    s = max(0, min(15, round(6 + heat * 0.5)))
    note = None
    if heat >= 15:
        note = f"{topic}題材爆量({heat}則)"
    elif heat >= 6:
        note = f"{topic}題材發酵"
    return s, note


def score_momentum(closes: list[float], volume: float, avg_vol: float | None) -> tuple[int, int | None, int | None, str | None]:
    """s6:技術動能(0-15)。站上均線 + 量增 + RSI + 區間位置。回 (分數, rsi, pos, note)。"""
    if not closes:
        return 8, None, None, None
    s, notes = 0, []
    last = closes[-1]
    ma5, ma20 = ind.sma(closes, 5), ind.sma(closes, 20)
    rsi = ind.rsi(closes)
    pos = ind.position_in_range(closes, 20)

    if ma5 is not None and last >= ma5:
        s += 4
        notes.append("站上5日線")
    if ma20 is not None and last >= ma20:
        s += 3
        notes.append("站上月線")
    if ma5 is not None and ma20 is not None and ma5 >= ma20:
        s += 2
    if avg_vol and volume > avg_vol * 1.3:
        s += 3
        notes.append("量增")
    if rsi is not None:
        if 50 <= rsi <= 75:
            s += 2
        elif rsi > 80:
            s -= 2
            notes.append("過熱")
    if pos is not None and pos >= 60:
        s += 1
    if ma20 is None:
        s = max(s, 8)
    return max(0, min(15, s)), rsi, pos, ("、".join(notes) or None)


def grade(score: int) -> str:
    """總分(滿分 100)轉建議強度。"""
    if score >= 70:
        return "strong"
    if score >= 55:
        return "mid"
    return "watch"
