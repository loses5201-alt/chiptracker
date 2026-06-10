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
import math

from . import indicators as ind


def score_institutional(inst: dict, volume_shares: float) -> tuple[float, str | None]:
    """s1:法人籌碼(0-22)。三大法人合計買超佔當日成交量比重。"""
    if not inst or volume_shares <= 0:
        return 0, None
    total = inst.get("total", 0.0)
    ratio = total / volume_shares
    # tanh 壓縮取代線性:原 ratio*240 在買超佔量 4.6% 即頂滿 → 入選股人人 22 分
    # (weight_review 實測 discrim=0,最重因子完全沒在排名)。改後 3%→16、6%→19、
    # 12%→21.6,極端才貼近滿分,排名拉得開;賣超側對稱遞減。
    s = round(11 + 11 * math.tanh(ratio / 0.06), 1)
    s = max(0.0, min(22.0, s))
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


def score_fundamental(fund: dict | None) -> tuple[float, str | None]:
    """s3:基本面(0-20)。月營收 YoY 年增率。"""
    if not fund:
        return 8, None
    yoy = fund.get("yoy", 0.0)
    # tanh 壓縮取代線性:原 yoy≥50% 即滿分 → 入選股 mean 19.65/20 飽和(discrim 4.9)。
    # 改後 50%→14.7、100%→18.2、200%→19.8,高成長股之間仍分得出高下;
    # 衰退側對稱:-40% 約 2.5 分,不會一路扣到 0 失去鑑別。
    s = round(8 + 12 * math.tanh(yoy / 80.0), 1)
    s = max(0.0, min(20.0, s))
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


def score_topic_news(topic: str | None, heat: int) -> tuple[float, str | None]:
    """
    s5:題材熱度(0-15)★題材面。所屬題材近 3 日新聞則數。
    熱度高 = 市場正在炒作該題材(如黃仁勳來台帶動 AI)。
    """
    if topic is None:
        return 6, None
    # tanh 壓縮:原 heat≥18 則即滿分,大題材(AI 伺服器動輒 17+ 則)全擠在頂。
    # 改後 6 則→9.4、17 則→14.0、30 則→14.9,熱與爆熱仍分得開。
    s = round(6 + 9 * math.tanh(heat / 12.0), 1)
    s = max(0.0, min(15.0, s))
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


def score_short(inst: dict, mg: dict, closes: list, vol: float, avg_vol: float | None,
                fund: dict | None, topic: str | None = None, topic_heat: int = 0,
                pledge: float | None = None) -> tuple[int, list[str]]:
    """
    做空評分(0-100)。鎖定「大牛市跟風假漲」:乖離過高 + 實質營收沒跟上 + 無題材 + 法人出貨。
    pledge:董監設質比例%(內部人質押槓桿),高設質=斷頭追繳風險→做空加分。None=無資料。
    ⚠️ 做空風險高(軋空、損失無上限),此為訊號非建議,務必設停損。
    """
    s, reasons = 0, []
    rsi = ind.rsi(closes)
    pos = ind.position_in_range(closes, 20)
    ma5, ma20 = ind.sma(closes, 5), ind.sma(closes, 20)
    last = closes[-1] if closes else 0
    bias20 = ((last - ma20) / ma20 * 100) if (ma20 and last) else 0   # 乖離率(對月線)
    yoy = fund.get("yoy", 0) if fund else 0

    # 1. 乖離率過高 — 漲過頭(0-14)
    if bias20 >= 20:
        s += 14
        reasons.append(f"乖離過高(+{bias20:.0f}%)")
    elif bias20 >= 12:
        s += 8
        reasons.append(f"乖離偏高(+{bias20:.0f}%)")
    # 2. 跟風假漲 — 漲多但實質營收沒跟上(0-22)★核心
    if bias20 >= 12 and yoy < 10:
        s += 22
        reasons.append("漲多但營收未跟上")
    elif yoy < 0:
        s += 12
        reasons.append(f"營收年減{yoy:.0f}%")
    # 3. 無題材支撐 — 純資金跟風(0-12)★核心
    if not topic:
        s += 8
        reasons.append("無題材支撐")
    elif topic_heat < 3:
        s += 5
        reasons.append("題材退燒")
    # 4. 高檔過熱(0-16)
    if pos is not None and pos >= 90:
        s += 8
        reasons.append(f"高檔(區間{pos})")
    if rsi is not None and rsi >= 80:
        s += 8
        reasons.append(f"超買(RSI{rsi})")
    # 5. 法人出貨(0-18):三大法人賣超佔成交量比
    if inst and vol > 0:
        r = inst.get("total", 0) / vol
        if r < 0:
            s += min(18, round(-r * 180))
            reasons.append("法人賣超")
    # 6. 技術轉弱(0-10)
    if ma5 is not None and last and last < ma5:
        s += 5
        reasons.append("跌破5日線")
    if ma5 is not None and ma20 is not None and ma5 < ma20:
        s += 5
        reasons.append("均線下彎")
    # 7. 融資套牢(0-6):融資增 + 法人賣 = 散戶套在頂部
    if mg and mg.get("margin_bal", 0) - mg.get("margin_prev", 0) > 0 and inst.get("total", 0) < 0:
        s += 6
        reasons.append("融資套牢")
    # 8. 董監高設質(0-8):內部人質押槓桿高,股價跌易被斷頭追繳→助跌
    if pledge is not None:
        if pledge >= 60:
            s += 8; reasons.append(f"董監高質押{pledge:.0f}%")
        elif pledge >= 40:
            s += 4; reasons.append(f"董監質押{pledge:.0f}%")
    return min(100, s), reasons[:5]


def short_grade(score: int) -> str:
    """做空訊號強度。"""
    if score >= 60:
        return "strong"
    if score >= 45:
        return "mid"
    return "watch"


def score_stealth(inst: dict, mg: dict, closes: list, vol: float, avg_vol: float | None,
                  big: dict | None = None, inst_streak: int = 0,
                  pledge: float | None = None) -> tuple[int, list[str]]:
    """
    主力潛伏(主力吸籌·底部轉強初期)— 跟著大戶在發動前布局的核心評分。
    抓「大戶/法人默默吃貨 + 股價剛從打底區站上均線轉強、量能溫和放大、但還沒漲多」的發動初期。
    與「深度抄底」不同:不追最低的破底弱勢股(弱勢易續弱),也不追高位過熱股。
    ⚠️ 歷史回測修正版(原「位置越低+量縮越加分」被驗為反向,改獎勵打底完成+轉強)。
    ⚠️ 仍是訊號非建議;潛伏股可能盤更久或不發動,需耐心與停損。

    big:Phase B 集保千張大戶資料 {ratio, week_chg}(週變化,單位 %)。None=無資料/回測。
        大戶 ≠ 法人:T86 法人買超只是當日機構動向,集保千張大戶比例週週升高才是「真吸籌」。
        ⚠️ TDCC 無法回填歷史 → 此因子只能前向累積驗證,故權重保守、缺資料時自動退讓。
    """
    s, reasons = 0, []
    pos = ind.position_in_range(closes, 60)   # 60 日區間看基期高低
    rsi = ind.rsi(closes)
    ma20 = ind.sma(closes, 20)
    ma5 = ind.sma(closes, 5)
    last = closes[-1] if closes else 0
    bias = ((last - ma20) / ma20 * 100) if (ma20 and last) else 0
    itotal = inst.get("total", 0) if inst else 0

    # 1. 法人吸籌(核心):默默買 + 連續買 + 散戶退場 = 大戶在布局
    if vol > 0 and itotal > 0:
        s += min(22, round(itotal / vol * 220)); reasons.append("法人吃貨")
    if inst_streak >= 3:
        s += min(16, inst_streak * 3); reasons.append(f"法人連買{inst_streak}天")
    if mg and itotal > 0 and mg.get("margin_bal", 0) - mg.get("margin_prev", 0) < 0:
        s += 12; reasons.append("散戶退場法人進")
    # 2. 中低基期:打底完成剛起步最佳(不追高、也不抄破底弱勢股)
    #    ⚠️ 回測修正:原本「位置越低越加分」會選到弱勢續弱股(q5 反而最差),
    #    改成獎勵「打底完成的中低位」,最低位(可能仍在破底)只小加。
    if pos is not None:
        if 30 <= pos <= 65:
            s += 18; reasons.append(f"打底完成(位置{pos})")
        elif pos < 30:
            s += 8; reasons.append(f"低基期(位置{pos})")
        elif pos <= 80:
            s += 4
        else:
            s -= 12   # 高位追高,扣分
    # 3. 底部轉強訊號(主力發動初期):站上月線 + 短均上彎(取代原「量縮、貼均線沒漲」)
    if ma20 and last and last > ma20:
        s += 10; reasons.append("站上月線轉強")
    if ma5 and ma20 and ma5 > ma20:
        s += 6
    if bias >= 15:
        s -= 8        # 乖離過大(已漲多)扣分
    # 3b. 均線糾結:原想加分(壓縮蓄勢),但 run_stealth 回測(universe300/160日)證實
    #     加分後 q5(高分)後續報酬反而變差、q1 變好,四窗口同向 → 不予計分(不憑感覺、依數據)。
    #     ma_convergence 指標保留供資訊顯示,不影響評分。
    # 4. 量能溫和放大 = 主力進場痕跡(非量縮;量縮其實是沒人理會的弱勢股)
    if avg_vol and avg_vol > 0 and itotal > 0:
        ratio = vol / avg_vol
        if 1.0 <= ratio <= 2.2:
            s += 8; reasons.append("量溫放大主力進")
        elif ratio > 2.8:
            s -= 6     # 爆量(可能追高/出貨)
    # 5. RSI 轉強未過熱(脫離弱勢、尚未過熱)
    if rsi is not None:
        if 50 <= rsi <= 68:
            s += 8; reasons.append("動能轉強未過熱")
        elif rsi > 75:
            s -= 8
    # 6. 集保千張大戶吸籌(Phase B 真大戶訊號)— 大戶比例週升 + 股價沒漲多 = 默默吃貨
    #    比 T86 法人買超更貼近「主力」;權重保守(無法回填歷史,僅前向驗證)。
    if big:
        wchg = big.get("week_chg")
        if wchg is not None:
            if wchg >= 0.4 and bias < 8:
                s += 14; reasons.append(f"大戶吸籌(週+{wchg:.1f}%)")
            elif wchg >= 0.15:
                s += 7; reasons.append(f"大戶增持(週+{wchg:.1f}%)")
            elif wchg <= -0.4:
                s -= 8; reasons.append(f"大戶減持(週{wchg:.1f}%)")
    # 7. 董監高設質避雷:內部人質押槓桿高,別跟著埋伏(股價弱易引發斷頭賣壓)
    if pledge is not None and pledge >= 60:
        s -= 10; reasons.append(f"董監高質押避雷{pledge:.0f}%")
    return max(0, min(100, s)), reasons[:5]


def stealth_grade(score: int) -> str:
    if score >= 55:
        return "strong"
    if score >= 40:
        return "mid"
    return "watch"


def grade(score: int) -> str:
    """總分(滿分 100)轉建議強度。"""
    if score >= 70:
        return "strong"
    if score >= 55:
        return "mid"
    return "watch"
