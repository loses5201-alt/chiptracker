"""
ChipTracker 主程式 — 在 GitHub Actions 上每交易日收盤後執行。

兩階段流程(兼顧正確與速度):
  階段1:抓籌碼/基本面/海外/新聞 → 算 s1~s5(不需個股歷史)→ 取候選股。
  階段2:只對候選股用 Yahoo 回補近 3 月歷史 → 算 s6 技術動能 → 最終 top 40。
前端只讀產出的靜態 JSON。

執行:python -m fetcher.build   (於 repo 根目錄)
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .sources.twse import TwseSource
from .sources.tpex import TpexSource
from .sources.broker import BrokerSource
from .sources.fundamentals import FundamentalsSource
from .sources.overseas import OverseasSource
from .sources.news import NewsSource
from .sources.price_history import PriceHistorySource
from . import sectors, scoring, market_pulse, indicators as ind
from .sources.margin_history import fetch_trend as fetch_margin_trend
from .sources.inst_history import fetch_trend as fetch_inst_trend
from .sources.stock_chip_history import fetch as fetch_stock_chips
from .sources import tdcc_holders
from .notify import notify

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TOP_N = 40
CANDIDATES = 120
SHORT_CANDIDATES = 100  # 做空候選池(放寬納入「業績未明顯成長」的跟風股)
SHORT_TOP = 30          # 做空清單顯示數
STEALTH_CANDIDATES = 100  # 主力潛伏候選池(法人吃貨的股)
STEALTH_TOP = 30          # 主力潛伏清單顯示數
HISTORY_CAP = 60
CHART_DAYS = 30
TDCC_CAP = 12  # 保留近 12 週千張大戶持股(算週變化用)
TRIG_HOLD = 5   # 潛伏股「發動」後保留幾個交易日供展示再移出
WATCH_MAX = 20  # 未發動且已掉出榜的潛伏股,追蹤上限交易日(超過視為沒發動,移出)
TPE = timezone(timedelta(hours=8))


def _merge(*dicts: dict) -> dict:
    out: dict = {}
    for d in dicts:
        out.update(d)
    return out


def load_history() -> dict:
    f = DATA / "history.json"
    h = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    h.setdefault("last_date", None)
    h.setdefault("closes", {})
    h.setdefault("vols", {})
    return h


def update_history(hist: dict, trading_date: str, quotes: dict) -> dict:
    if trading_date and trading_date == hist.get("last_date"):
        return hist
    closes, vols = hist["closes"], hist["vols"]
    for code, q in quotes.items():
        if q.get("close", 0) <= 0:
            continue
        ca = closes.setdefault(code, [])
        ca.append(q["close"])
        del ca[:-HISTORY_CAP]
        va = vols.setdefault(code, [])
        va.append(q.get("volume", 0))
        del va[:-HISTORY_CAP]
    hist["last_date"] = trading_date
    return hist


def update_tdcc(holders: dict) -> dict:
    """
    累積集保千張大戶持股週序列 → 回傳 {code: {ratio, week_chg}} 供潛伏評分。
    TDCC 只給最新一週,週變化靠每次 build 累積(同 history.json 模式);
    同一週內多次 build 不重複 append(以資料日期去重)。第一週 week_chg=None(無前一週)。
    """
    f = DATA / "tdcc_history.json"
    h = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"dates": [], "ratios": {}}
    dates, ratios = h["dates"], h["ratios"]
    if holders:
        wk = next(iter(holders.values())).get("date")   # 同一份 CSV 所有 code 同日
        if wk and wk not in dates:
            dates.append(wk)
            del dates[:-TDCC_CAP]
            for code, d in holders.items():
                arr = ratios.setdefault(code, [])
                arr.append(d["ratio"])
                del arr[:-TDCC_CAP]
            f.write_text(json.dumps(h, ensure_ascii=False), encoding="utf-8")
    out: dict[str, dict] = {}
    for code, arr in ratios.items():
        if not arr:
            continue
        cur, prev = arr[-1], (arr[-2] if len(arr) >= 2 else None)
        out[code] = {"ratio": cur, "week_chg": round(cur - prev, 2) if prev is not None else None}
    return out


def update_stealth_watch(stealth_top: list, quotes: dict, yh: dict, hist: dict,
                         trading_date: str) -> dict:
    """
    潛伏發動追蹤(Phase C,純網站標記)— 把每日潛伏在榜股累積成觀察清單,
    並偵測「發動」(從埋伏到該進場的訊號):放量 + 突破進榜價 +5% + 站上 20MA。
    用實際發動案例自我驗證選股(「跟著大戶」是否真能提前埋伏到起漲)。

    狀態檔 data/stealth_watch.json:{watch:{code:{進榜日/價/分、發動日、報酬、追蹤天數}}}。
    已在榜者保留首次進榜日;發動後保留 TRIG_HOLD 日再移出;未發動且掉榜超過 WATCH_MAX 日視為沒發動移出。
    同一交易日重複 build 不重複累進(以 last_date 去重)。
    """
    f = DATA / "stealth_watch.json"
    w = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"watch": {}, "last_date": None}
    watch = w.setdefault("watch", {})
    new_day = trading_date != w.get("last_date")   # 新交易日才推進 age/發動偵測
    today_codes = {s["c"] for s in stealth_top}

    # 1. 新進榜:首次出現才記錄進榜日/價/分(已在榜者不覆蓋,保留埋伏起點)
    for s in stealth_top:
        if s["c"] not in watch:
            watch[s["c"]] = {
                "n": s["n"], "mkt": s["mkt"], "enter_date": trading_date,
                "enter_px": s["close"], "enter_score": s["score"],
                "triggered_date": None, "age": 0, "since_trig": 0,
            }

    # 2. 逐檔更新最新報酬 + 偵測發動(僅新交易日推進,避免同日多次 build 累加)
    drop = []
    for code, e in watch.items():
        closes = (yh.get(code, {}) or {}).get("closes") or hist["closes"].get(code, [])
        vols = (yh.get(code, {}) or {}).get("vols") or hist["vols"].get(code, [])
        q = quotes.get(code, {})
        close = q.get("close") or (closes[-1] if closes else e["enter_px"])
        vol = q.get("volume", 0)
        ep = e.get("enter_px") or 0
        e["cur_ret"] = round((close / ep - 1) * 100, 1) if ep else 0
        e["in_top"] = code in today_codes
        if not new_day:
            continue
        e["age"] = e.get("age", 0) + 1
        ma20 = (sum(closes[-20:]) / 20) if len(closes) >= 20 else None
        avg5 = (sum(vols[-6:-1]) / 5) if len(vols) >= 6 else None
        if not e.get("triggered_date"):
            broke = ep and close >= ep * 1.05            # 突破進榜價 +5%
            volup = avg5 and vol >= avg5 * 1.5            # 放量 ≥1.5× 近5日均量
            above = ma20 and close >= ma20                # 站上 20MA
            if broke and volup and above:
                e["triggered_date"] = trading_date
                e["trig_ret"] = e["cur_ret"]
                e["since_trig"] = 0
            elif not e["in_top"] and e["age"] > WATCH_MAX:
                drop.append(code)                          # 太久沒發動又掉榜 → 視為沒發動
        else:
            e["since_trig"] = e.get("since_trig", 0) + 1
            if e["since_trig"] > TRIG_HOLD:
                drop.append(code)                          # 發動展示期滿 → 移出
    for code in drop:
        watch.pop(code, None)

    w["last_date"] = trading_date
    f.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")
    return w


def fmt_lots(shares: float) -> str:
    lots = shares / 1000
    return f"{lots/10000:.1f}萬張" if abs(lots) >= 10000 else f"{lots:,.0f}張"


def base_scores(q, inst, mg, fund, topic, tmom, heat) -> dict:
    """階段1:算不需個股歷史的 s1~s5 與理由。"""
    volume = q.get("volume", 0)
    s1, n1 = scoring.score_institutional(inst, volume)
    s2, n2 = scoring.score_margin_short(mg, inst)
    s3, n3 = scoring.score_fundamental(fund)
    s4, n4 = scoring.score_overseas(topic, tmom)
    s5, n5 = scoring.score_topic_news(topic, heat)
    return {
        "s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5,
        "base": s1 + s2 + s3 + s4 + s5,
        "notes": [n for n in (n1, n2, n3, n4, n5) if n],
    }


def finalize(code, q, inst, fund, topic, tmom, heat_data, bs, closes, vols, market) -> dict:
    """階段2:補 s6 技術動能,組成前端要的完整記錄。"""
    volume = q.get("volume", 0)
    avg_vol = (sum(vols[-5:]) / len(vols[-5:])) if len(vols) >= 2 else None
    s6, rsi, pos, n6 = scoring.score_momentum(closes, volume, avg_vol)
    total = bs["base"] + s6
    reasons = (bs["notes"] + ([n6] if n6 else []))[:4]
    close = q.get("close", 0)

    fg, tr = inst.get("foreign", 0), inst.get("trust", 0)
    align = "外資投信同買" if fg > 0 and tr > 0 else "外資投信同賣" if fg < 0 and tr < 0 else "外資投信分歧"
    conc = round(inst.get("total", 0) / volume * 100, 2) if volume > 0 else 0  # 法人買超佔當日量%(吃貨集中度)
    smart = []
    if inst.get("foreign"):
        smart.append(f"外資{'+' if inst['foreign']>=0 else ''}{fmt_lots(inst['foreign'])}")
    if inst.get("trust"):
        smart.append(f"投信{'+' if inst['trust']>=0 else ''}{fmt_lots(inst['trust'])}")

    return {
        "c": code, "n": q.get("name", ""), "mkt": market, "topic": topic or "—",
        "rec": scoring.grade(total), "score": total,
        "s1": bs["s1"], "s2": bs["s2"], "s3": bs["s3"], "s4": bs["s4"], "s5": bs["s5"], "s6": s6,
        "pos": pos if pos is not None else 50,
        "yoy": round(fund["yoy"], 1) if fund else None,
        "ov": round(tmom, 1) if topic else None,
        "heat": heat_data.get("heat", 0) if topic else 0,
        "news": heat_data.get("titles", []) if topic else [],
        "smart": "、".join(smart) or "—", "align": align, "conc": conc,
        "reason": reasons or ["資料累積中"],
        "entry": f"{close*0.99:.1f}~{close*1.01:.1f}" if close else "—",
        "stop": f"{close*0.95:.1f}" if close else "—",
        "t1": f"{close*1.05:.1f}" if close else "—",
        "t2": f"{close*1.10:.1f}" if close else "—",
        "rsi": rsi if rsi is not None else "—",
        "vol": fmt_lots(volume), "close": close,
        "closes": closes[-CHART_DAYS:],
    }


def main() -> int:
    DATA.mkdir(exist_ok=True)
    twse, tpex, broker = TwseSource(), TpexSource(), BrokerSource()
    funds_src, ov_src = FundamentalsSource(), OverseasSource()
    news_src, hist_src = NewsSource(), PriceHistorySource()

    print("階段1:抓籌碼/基本面/海外/新聞…")
    tw_q, tp_q = twse.daily_quotes(), tpex.daily_quotes()
    quotes = _merge(tw_q, tp_q)
    tpex_codes = set(tp_q)  # 標記市場別(上市/上櫃),供快照與回測分組
    inst = _merge(twse.institutional(), tpex.institutional())
    margin = _merge(twse.margin(), tpex.margin())
    print(f"  價量 {len(quotes)}(上市 {len(tw_q)}/上櫃 {len(tp_q)}) / 法人 {len(inst)} / 融資券 {len(margin)}")

    try:
        funds = funds_src.revenue()
    except Exception as e:  # noqa: BLE001
        funds = {}
        print(f"  基本面失敗(略過):{e}")
    ov_prices = ov_src.momentum(sectors.all_overseas_symbols())
    topic_mom = sectors.topic_overseas_momentum(ov_prices)
    heat = news_src.topic_heat({n: t["kw"] for n, t in sectors.TOPICS.items()})
    hot = sorted(heat.items(), key=lambda x: x[1]["heat"], reverse=True)[:3]
    print(f"  月營收 {len(funds)} / 海外 {len(ov_prices)} / 新聞熱題 {[h[0] for h in hot]}")

    trading_date = twse.trading_date or datetime.now(TPE).strftime("%Y%m%d")
    _now = datetime.now(TPE)
    quarter_end = _now.month in (3, 6, 9, 12) and _now.day >= 15  # 季底投信作帳期(投信拉抬持股美化淨值)
    hist = update_history(load_history(), trading_date, quotes)

    cand = []
    for code, q in quotes.items():
        if q.get("close", 0) <= 0 or q.get("volume", 0) <= 0 or code.startswith("00"):
            continue
        topic, tmom = sectors.best_topic_for(code, topic_mom, heat)
        h = heat.get(topic, {}).get("heat", 0) if topic else 0
        bs = base_scores(q, inst.get(code, {}), margin.get(code, {}), funds.get(code), topic, tmom, h)
        cand.append((code, q, topic, tmom, bs))
    cand.sort(key=lambda x: x[4]["base"], reverse=True)
    # 全市場基礎評分(供前端查詢/自選任一檔;s6 技術僅候選股回補,故全市場用 s1~s5 base)
    all_scored = [
        {"c": code, "n": q.get("name", ""), "mkt": "tpex" if code in tpex_codes else "twse",
         "close": q.get("close", 0), "base": bs["base"], "topic": topic or "—",
         "s1": bs["s1"], "s2": bs["s2"], "s3": bs["s3"], "s4": bs["s4"], "s5": bs["s5"]}
        for code, q, topic, tmom, bs in cand
    ]
    (DATA / "all_stocks.json").write_text(
        json.dumps(all_scored, ensure_ascii=False), encoding="utf-8")
    cand = cand[:CANDIDATES]
    # 做空候選:業績往下(月營收年減)或法人賣超 + 有量(可融券),取最弱一批
    short_cand = []
    for code, q in quotes.items():
        if q.get("close", 0) <= 0 or q.get("volume", 0) <= 0 or code.startswith("00"):
            continue
        f = funds.get(code)
        itotal = inst.get(code, {}).get("total", 0)
        yoy = f["yoy"] if f else 0
        # 做空候選:實質營收未明顯成長(yoy<10)或法人賣超 + 有量(跟風假漲常在此)
        if yoy < 10 or itotal < 0:
            sb = max(0, 12 - yoy) * 0.4 + (max(0, -itotal / q["volume"]) * 200 if q["volume"] > 0 else 0)
            short_cand.append((code, q, sb))
    short_cand.sort(key=lambda x: x[2], reverse=True)
    short_cand = short_cand[:SHORT_CANDIDATES]
    # 主力潛伏候選:法人買超(大戶吃貨)+ 有量;階段2 再用 stealth_score 篩低基期/未發動
    stealth_cand = []
    for code, q in quotes.items():
        if q.get("close", 0) <= 0 or q.get("volume", 0) <= 0 or code.startswith("00"):
            continue
        itotal = inst.get(code, {}).get("total", 0)
        if itotal > 0:
            stealth_cand.append((code, q, itotal / q["volume"]))
    stealth_cand.sort(key=lambda x: x[2], reverse=True)
    stealth_cand = stealth_cand[:STEALTH_CANDIDATES]
    print(f"  全市場評分 {len(all_scored)} / 做多候選 {len(cand)} / 做空候選 {len(short_cand)}")

    print("階段2:回補候選股 Yahoo 歷史 → 算技術面…")
    _mkt = lambda c: "tpex" if c in tpex_codes else "twse"
    _fetch_set = {c[0]: _mkt(c[0]) for c in cand}
    _fetch_set.update({c[0]: _mkt(c[0]) for c in short_cand})   # 做多+做空候選合併去重
    _fetch_set.update({c[0]: _mkt(c[0]) for c in stealth_cand})  # + 潛伏候選
    yh = hist_src.fetch(list(_fetch_set.items()))
    print(f"  Yahoo 成功 {len(yh)}/{len(_fetch_set)} 檔(做多+做空候選)")

    records = []
    for code, q, topic, tmom, bs in cand:
        if code in yh:
            closes, vols = yh[code]["closes"], yh[code]["vols"]
        else:
            closes = hist["closes"].get(code, [q["close"]])
            vols = hist["vols"].get(code, [])
        market = "tpex" if code in tpex_codes else "twse"
        records.append(finalize(
            code, q, inst.get(code, {}), funds.get(code), topic, tmom,
            heat.get(topic, {}) if topic else {}, bs, closes, vols, market))

    records.sort(key=lambda r: r["score"], reverse=True)
    top = records[:TOP_N]

    (DATA / "history.json").write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    (DATA / "stocks.json").write_text(json.dumps(top, ensure_ascii=False, indent=1), encoding="utf-8")

    # 做空清單:對做空候選算 short_score(高檔回落 + 業績轉弱 + 法人出貨)
    shorts = []
    for code, q, _ in short_cand:
        closes = yh[code]["closes"] if code in yh else hist["closes"].get(code, [q["close"]])
        vols = yh[code]["vols"] if code in yh else hist["vols"].get(code, [])
        avg_vol = (sum(vols[-5:]) / len(vols[-5:])) if len(vols) >= 2 else None
        s_topic, _stm = sectors.best_topic_for(code, topic_mom, heat)
        s_heat = heat.get(s_topic, {}).get("heat", 0) if s_topic else 0
        ss, sreasons = scoring.score_short(inst.get(code, {}), margin.get(code, {}),
                                           closes, q.get("volume", 0), avg_vol, funds.get(code), s_topic, s_heat)
        close = q.get("close", 0)
        shorts.append({
            "c": code, "n": q.get("name", ""), "mkt": _mkt(code),
            "score": ss, "rec": scoring.short_grade(ss), "close": close,
            "yoy": round(funds[code]["yoy"], 1) if funds.get(code) else None,
            "reason": sreasons or ["高檔轉弱"], "closes": closes[-CHART_DAYS:],
            "entry": f"{close*0.99:.1f}~{close*1.01:.1f}" if close else "—",
            "stop": f"{close*1.05:.1f}" if close else "—",   # 空單停損=上漲5%
            "t1": f"{close*0.95:.1f}" if close else "—",     # 目標=下跌5%
            "t2": f"{close*0.90:.1f}" if close else "—",
        })
    shorts.sort(key=lambda r: r["score"], reverse=True)
    shorts = shorts[:SHORT_TOP]
    (DATA / "shorts.json").write_text(json.dumps(shorts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  做空清單 {len(shorts)} 檔")

    # 每日快照:把今天的推薦另存一份帶交易日的檔,供日後回測(收益率/勝率/分組驗證)。
    # stocks.json 隔天會被覆蓋,快照則永久保留 → 這是回測的原料。
    # 存回測需要的欄位:代號/名稱/市場/分數/建議/收盤,另存六面向 s1~s6
    # → 讓回測能分析「哪個面向最有預測力」(高分面向後續是否真的較會漲)。
    snap_dir = DATA / "daily"
    snap_dir.mkdir(exist_ok=True)
    snapshot = [
        {"c": r["c"], "n": r["n"], "mkt": r["mkt"], "rec": r["rec"], "score": r["score"],
         "topic": r["topic"], "close": r["close"],
         "s": [r["s1"], r["s2"], r["s3"], r["s4"], r["s5"], r["s6"]]}
        for r in top
    ]
    (snap_dir / f"{trading_date}.json").write_text(
        json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    # 大盤趨勢(融資 + 三大法人),回填近 10 交易日 → 趨勢化判讀(不必累積)
    try:
        mtrend = fetch_margin_trend(10)
    except Exception as e:  # noqa: BLE001 — 趨勢失敗不影響主資料
        mtrend = []
        print(f"  融資趨勢失敗(略過):{e}")
    try:
        itrend = fetch_inst_trend(10)
    except Exception as e:  # noqa: BLE001
        itrend = []
        print(f"  法人趨勢失敗(略過):{e}")
    inst_today = itrend[-1] if itrend else {}

    # 集保千張大戶持股(Phase B):大戶比例週升 + 股價沒漲 = 真吸籌(比 T86 法人更貼近主力)
    try:
        big_holders = update_tdcc(tdcc_holders.fetch())
    except Exception as e:  # noqa: BLE001 — 失敗不影響主資料
        big_holders = {}
        print(f"  集保大戶失敗(略過):{e}")
    _bh_wk = sum(1 for d in big_holders.values() if d.get("week_chg") is not None)
    print(f"  集保大戶 {len(big_holders)} 檔(已有週變化 {_bh_wk} 檔)")

    meta = {
        "updated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "trading_date": trading_date,
        "quarter_end": quarter_end,
        "universe": len(cand), "shown": len(top),
        "market_split": {
            "twse": sum(1 for r in top if r["mkt"] == "twse"),
            "tpex": sum(1 for r in top if r["mkt"] == "tpex"),
        },
        "sources": {
            "twse": True, "tpex": bool(tp_q), "broker": broker.enabled,
            "fundamentals": bool(funds), "overseas": bool(ov_prices),
            "news": any(v["heat"] for v in heat.values()), "history": bool(yh),
            "tdcc": bool(big_holders),
        },
        "topic_momentum": topic_mom,
        "topic_heat": {n: d["heat"] for n, d in heat.items()},
        "yahoo_ok": len(yh),
        "market_pulse": market_pulse.compute(quotes, margin, heat, topic_mom, inst_today),
    }
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    # 大盤趨勢檔(融資 + 三大法人),供溫度計畫週趨勢
    (DATA / "market_trend.json").write_text(
        json.dumps({"updated": datetime.now(TPE).isoformat(timespec="seconds"),
                    "margin": mtrend, "inst": itrend},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  大盤趨勢:融資 {len(mtrend)} 日 / 法人 {len(itrend)} 日")

    # 個股籌碼歷史(top 上市股近10交易日法人/融資趨勢,延續「看一段時間」到個股)
    chip_targets = {r["c"]: r["mkt"] for r in top}
    for code, q, _ in stealth_cand:
        chip_targets[code] = _mkt(code)   # 潛伏候選也要法人連買天數
    try:
        chips = fetch_stock_chips(list(chip_targets.items()), 10)
    except Exception as e:  # noqa: BLE001 — 失敗不影響主資料
        chips = {}
        print(f"  個股籌碼失敗(略過):{e}")
    # 補算法人成本線:近期法人買超的加權均價(只計買超日)→ 供「股價 vs 法人成本」判讀
    for code, ch in chips.items():
        p = yh.get(code)
        if not p:
            continue
        num = den = 0.0
        for d, iv in zip(ch["dates"], ch["inst"]):
            if iv > 0 and d in p["dates"]:
                num += iv * p["closes"][p["dates"].index(d)]
                den += iv
        ch["cost"] = round(num / den, 2) if den else None
    (DATA / "stock_chips.json").write_text(json.dumps(chips, ensure_ascii=False), encoding="utf-8")
    print(f"  個股籌碼 {len(chips)} 檔")

    # 主力潛伏清單:大戶吃貨 + 低基期 + 還沒發動(跟著大戶提前布局,app 核心)
    stealth = []
    for code, q, _ in stealth_cand:
        closes = yh[code]["closes"] if code in yh else hist["closes"].get(code, [q["close"]])
        vols = yh[code]["vols"] if code in yh else hist["vols"].get(code, [])
        avg_vol = (sum(vols[-5:]) / len(vols[-5:])) if len(vols) >= 2 else None
        streak = chips.get(code, {}).get("inst_buy_streak", 0)
        big = big_holders.get(code)
        st, sr = scoring.score_stealth(inst.get(code, {}), margin.get(code, {}),
                                       closes, q.get("volume", 0), avg_vol, big, streak)
        close = q.get("close", 0)
        pos = ind.position_in_range(closes, 60)   # 60 日區間位置 → 埋伏進度條
        rsi = ind.rsi(closes)
        stealth.append({
            "c": code, "n": q.get("name", ""), "mkt": _mkt(code),
            "score": st, "rec": scoring.stealth_grade(st), "close": close,
            "yoy": round(funds[code]["yoy"], 1) if funds.get(code) else None,
            "pos": pos if pos is not None else 50,                    # 區間位置(埋伏進度)
            "rsi": rsi if rsi is not None else None,
            "big": round(big["ratio"], 1) if big else None,           # 千張大戶持股%
            "big_chg": big["week_chg"] if big else None,              # 週變化(None=資料未滿2週)
            "reason": sr or ["法人潛伏"], "closes": closes[-CHART_DAYS:],
            "entry": f"{close*0.98:.1f}~{close*1.02:.1f}" if close else "—",
            "stop": f"{close*0.93:.1f}" if close else "—",   # 潛伏停損較寬(盤整)
            "t1": f"{close*1.10:.1f}" if close else "—",     # 發動後目標較遠
            "t2": f"{close*1.20:.1f}" if close else "—",
        })
    stealth.sort(key=lambda r: r["score"], reverse=True)
    stealth = stealth[:STEALTH_TOP]
    (DATA / "stealth.json").write_text(json.dumps(stealth, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  主力潛伏 {len(stealth)} 檔")

    # 潛伏發動追蹤(Phase C):累積在榜股 → 偵測發動(放量+突破+站20MA),前端「已發動」區
    watch = {"watch": {}}
    try:
        watch = update_stealth_watch(stealth, quotes, yh, hist, trading_date)
        _trig = sum(1 for e in watch["watch"].values() if e.get("triggered_date"))
        print(f"  潛伏追蹤 {len(watch['watch'])} 檔(已發動 {_trig})")
    except Exception as e:  # noqa: BLE001 — 追蹤失敗不影響主資料
        print(f"  潛伏追蹤失敗(略過):{e}")

    # Discord 推播(發動快報推到手機):無 DISCORD_WEBHOOK 金鑰則自動略過
    print(f"  Discord 推播:{notify(stealth, watch, trading_date)}")

    rsi_ok = sum(1 for r in top if r["rsi"] != "—")
    print(f"完成:top {len(top)};技術面真值 {rsi_ok}/{len(top)};交易日 {trading_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
