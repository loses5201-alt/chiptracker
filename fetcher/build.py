"""
ChipTracker 主程式 — 在 GitHub Actions 上每交易日收盤後執行。

兩階段流程(兼顧正確與速度):
  階段1:抓籌碼/基本面/海外 → 算 s1~s4(不需歷史)→ 初步排序取候選股。
  階段2:只對候選股用 Yahoo 回補近 3 月歷史 → 算 s5 技術動能 → 最終 top 40。
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
from .sources.price_history import PriceHistorySource
from . import sectors, scoring

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TOP_N = 40           # 最終放進儀表板的檔數
CANDIDATES = 80      # 階段1取多少檔進階段2回補歷史(>TOP_N 留緩衝)
HISTORY_CAP = 60
CHART_DAYS = 30      # stocks.json 每檔附幾日收盤供前端畫圖
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
    """每日累積當日收盤+量(Yahoo 失敗時的備援);同交易日重跑不重複。"""
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


def base_scores(q, inst, mg, fund, topic, tmom) -> dict:
    """階段1:算不需歷史的 s1~s4 與理由。"""
    volume = q.get("volume", 0)
    s1, n1 = scoring.score_institutional(inst, volume)
    s2, n2 = scoring.score_margin_short(mg, inst)
    s3, n3 = scoring.score_fundamental(fund)
    s4, n4 = scoring.score_overseas(topic, tmom)
    return {
        "s1": s1, "s2": s2, "s3": s3, "s4": s4,
        "base": s1 + s2 + s3 + s4,
        "notes": [n for n in (n1, n2, n3, n4) if n],
    }


def finalize(code, q, inst, fund, topic, tmom, bs, closes, vols) -> dict:
    """階段2:補 s5 技術動能,組成前端要的完整記錄。"""
    volume = q.get("volume", 0)
    avg_vol = (sum(vols[-5:]) / len(vols[-5:])) if len(vols) >= 2 else None
    s5, rsi, pos, n5 = scoring.score_momentum(closes, volume, avg_vol)
    total = bs["base"] + s5
    reasons = (bs["notes"] + ([n5] if n5 else []))[:4]
    close = q.get("close", 0)

    smart = []
    if inst.get("foreign"):
        smart.append(f"外資{'+' if inst['foreign']>=0 else ''}{fmt_lots(inst['foreign'])}")
    if inst.get("trust"):
        smart.append(f"投信{'+' if inst['trust']>=0 else ''}{fmt_lots(inst['trust'])}")

    return {
        "c": code, "n": q.get("name", ""), "topic": topic or "—",
        "rec": scoring.grade(total), "score": total,
        "s1": bs["s1"], "s2": bs["s2"], "s3": bs["s3"], "s4": bs["s4"], "s5": s5,
        "pos": pos if pos is not None else 50,
        "yoy": round(fund["yoy"], 1) if fund else None,
        "ov": round(tmom, 1) if topic else None,
        "smart": "、".join(smart) or "—",
        "reason": reasons or ["資料累積中"],
        "entry": f"{close*0.99:.1f}~{close*1.01:.1f}" if close else "—",
        "stop": f"{close*0.95:.1f}" if close else "—",
        "t1": f"{close*1.05:.1f}" if close else "—",
        "t2": f"{close*1.10:.1f}" if close else "—",
        "rsi": rsi if rsi is not None else "—",
        "vol": fmt_lots(volume), "close": close,
        "closes": closes[-CHART_DAYS:],  # 供前端畫 K 線走勢
    }


def main() -> int:
    DATA.mkdir(exist_ok=True)
    twse, tpex, broker = TwseSource(), TpexSource(), BrokerSource()
    funds_src, ov_src, hist_src = FundamentalsSource(), OverseasSource(), PriceHistorySource()

    print("階段1:抓籌碼/基本面/海外…")
    quotes = _merge(twse.daily_quotes(), tpex.daily_quotes())
    inst = _merge(twse.institutional(), tpex.institutional())
    margin = _merge(twse.margin(), tpex.margin())
    print(f"  價量 {len(quotes)} / 法人 {len(inst)} / 融資券 {len(margin)}")

    try:
        funds = funds_src.revenue()
    except Exception as e:  # noqa: BLE001
        funds = {}
        print(f"  基本面失敗(略過):{e}")
    ov_prices = ov_src.momentum(sectors.all_overseas_symbols())
    topic_mom = sectors.topic_overseas_momentum(ov_prices)
    print(f"  月營收 {len(funds)} / 海外 {len(ov_prices)} / 題材動能 {topic_mom}")

    trading_date = twse.trading_date or datetime.now(TPE).strftime("%Y%m%d")
    hist = update_history(load_history(), trading_date, quotes)

    # 階段1 算 s1~s4,挑候選
    cand = []
    for code, q in quotes.items():
        if q.get("close", 0) <= 0 or q.get("volume", 0) <= 0 or code.startswith("00"):
            continue
        topic, tmom = sectors.best_topic_for(code, topic_mom)
        bs = base_scores(q, inst.get(code, {}), margin.get(code, {}), funds.get(code), topic, tmom)
        cand.append((code, q, topic, tmom, bs))
    cand.sort(key=lambda x: x[4]["base"], reverse=True)
    cand = cand[:CANDIDATES]
    print(f"  候選 {len(cand)} 檔(母體中 s1~s4 最高者)")

    print("階段2:回補候選股 Yahoo 歷史 → 算技術面…")
    yh = hist_src.fetch([c[0] for c in cand])
    print(f"  Yahoo 成功 {len(yh)}/{len(cand)} 檔")

    records = []
    for code, q, topic, tmom, bs in cand:
        if code in yh:
            closes, vols = yh[code]["closes"], yh[code]["vols"]
        else:  # Yahoo 失敗 → 退回每日累積值
            closes = hist["closes"].get(code, [q["close"]])
            vols = hist["vols"].get(code, [])
        records.append(finalize(code, q, inst.get(code, {}), funds.get(code), topic, tmom, bs, closes, vols))

    records.sort(key=lambda r: r["score"], reverse=True)
    top = records[:TOP_N]

    (DATA / "history.json").write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    (DATA / "stocks.json").write_text(json.dumps(top, ensure_ascii=False, indent=1), encoding="utf-8")
    meta = {
        "updated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "trading_date": trading_date,
        "universe": len(cand), "shown": len(top),
        "sources": {
            "twse": True, "tpex": False, "broker": broker.enabled,
            "fundamentals": bool(funds), "overseas": bool(ov_prices),
            "history": bool(yh),
        },
        "topic_momentum": topic_mom,
        "yahoo_ok": len(yh),
    }
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    rsi_ok = sum(1 for r in top if r["rsi"] != "—")
    print(f"完成:top {len(top)};技術面有真值 {rsi_ok}/{len(top)};交易日 {trading_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
