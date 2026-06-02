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
from . import sectors, scoring, market_pulse
from .sources.margin_history import fetch_trend as fetch_margin_trend
from .sources.inst_history import fetch_trend as fetch_inst_trend
from .sources.stock_chip_history import fetch as fetch_stock_chips

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TOP_N = 40
CANDIDATES = 80
HISTORY_CAP = 60
CHART_DAYS = 30
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
        "smart": "、".join(smart) or "—",
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
    cand = cand[:CANDIDATES]
    print(f"  候選 {len(cand)} 檔")

    print("階段2:回補候選股 Yahoo 歷史 → 算技術面…")
    yh = hist_src.fetch([(c[0], "tpex" if c[0] in tpex_codes else "twse") for c in cand])
    print(f"  Yahoo 成功 {len(yh)}/{len(cand)} 檔")

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

    meta = {
        "updated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "trading_date": trading_date,
        "universe": len(cand), "shown": len(top),
        "market_split": {
            "twse": sum(1 for r in top if r["mkt"] == "twse"),
            "tpex": sum(1 for r in top if r["mkt"] == "tpex"),
        },
        "sources": {
            "twse": True, "tpex": bool(tp_q), "broker": broker.enabled,
            "fundamentals": bool(funds), "overseas": bool(ov_prices),
            "news": any(v["heat"] for v in heat.values()), "history": bool(yh),
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
    twse_top = [r["c"] for r in top if r["mkt"] == "twse"]
    try:
        chips = fetch_stock_chips(twse_top, 10)
    except Exception as e:  # noqa: BLE001 — 失敗不影響主資料
        chips = {}
        print(f"  個股籌碼失敗(略過):{e}")
    (DATA / "stock_chips.json").write_text(json.dumps(chips, ensure_ascii=False), encoding="utf-8")
    print(f"  個股籌碼 {len(chips)} 檔")

    rsi_ok = sum(1 for r in top if r["rsi"] != "—")
    print(f"完成:top {len(top)};技術面真值 {rsi_ok}/{len(top)};交易日 {trading_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
