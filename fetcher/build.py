"""
ChipTracker 主程式 — 在 GitHub Actions 上每交易日收盤後執行。

流程:抓資料(籌碼+基本面+海外) → 累積歷史 → 計算 s1~s5 評分 → 排名 → 寫 data/*.json。
前端只讀這些靜態 JSON,不需要任何後端伺服器。

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
from . import sectors, scoring

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TOP_N = 40
HISTORY_CAP = 60
TPE = timezone(timedelta(hours=8))


def _merge(*dicts: dict) -> dict:
    out: dict = {}
    for d in dicts:
        out.update(d)
    return out


def load_history() -> dict:
    f = DATA / "history.json"
    if f.exists():
        h = json.loads(f.read_text(encoding="utf-8"))
    else:
        h = {}
    # 補齊欄位,相容舊版只有 closes 的 history.json
    h.setdefault("last_date", None)
    h.setdefault("closes", {})
    h.setdefault("vols", {})
    return h


def update_history(hist: dict, trading_date: str, quotes: dict) -> dict:
    """把今日收盤價與成交量 append 進歷史;同一交易日重跑不重複累加。"""
    if trading_date and trading_date == hist.get("last_date"):
        return hist
    closes = hist.setdefault("closes", {})
    vols = hist.setdefault("vols", {})
    for code, q in quotes.items():
        if q.get("close", 0) <= 0:
            continue
        ca = closes.setdefault(code, [])
        ca.append(q["close"])
        if len(ca) > HISTORY_CAP:
            del ca[:-HISTORY_CAP]
        va = vols.setdefault(code, [])
        va.append(q.get("volume", 0))
        if len(va) > HISTORY_CAP:
            del va[:-HISTORY_CAP]
    hist["last_date"] = trading_date
    return hist


def fmt_lots(shares: float) -> str:
    lots = shares / 1000
    if abs(lots) >= 10000:
        return f"{lots/10000:.1f}萬張"
    return f"{lots:,.0f}張"


def build_record(code, q, inst, mg, fund, topic, topic_mom, closes, vols) -> dict:
    """組成單一檔股票要給前端的一筆記錄。"""
    volume = q.get("volume", 0)
    avg_vol = (sum(vols[-5:]) / len(vols[-5:])) if len(vols) >= 2 else None

    s1, n1 = scoring.score_institutional(inst, volume)
    s2, n2 = scoring.score_margin_short(mg, inst)
    s3, n3 = scoring.score_fundamental(fund)
    s4, n4 = scoring.score_overseas(topic, topic_mom)
    s5, rsi, pos, n5 = scoring.score_momentum(closes, volume, avg_vol)
    total = s1 + s2 + s3 + s4 + s5

    reasons = [n for n in (n1, n2, n3, n4, n5) if n][:4]
    close = q.get("close", 0)
    smart_bits = []
    if inst.get("foreign"):
        smart_bits.append(f"外資{'+' if inst['foreign']>=0 else ''}{fmt_lots(inst['foreign'])}")
    if inst.get("trust"):
        smart_bits.append(f"投信{'+' if inst['trust']>=0 else ''}{fmt_lots(inst['trust'])}")

    return {
        "c": code,
        "n": q.get("name", ""),
        "topic": topic or "—",
        "rec": scoring.grade(total),
        "score": total,
        "s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5,
        "pos": pos if pos is not None else 50,
        "yoy": round(fund["yoy"], 1) if fund else None,
        "ov": round(topic_mom, 1) if topic else None,
        "smart": "、".join(smart_bits) or "—",
        "reason": reasons or ["資料累積中"],
        "entry": f"{close*0.99:.1f}~{close*1.01:.1f}" if close else "—",
        "stop": f"{close*0.95:.1f}" if close else "—",
        "t1": f"{close*1.05:.1f}" if close else "—",
        "t2": f"{close*1.10:.1f}" if close else "—",
        "rsi": rsi if rsi is not None else "—",
        "vol": fmt_lots(volume),
        "close": close,
    }


def main() -> int:
    DATA.mkdir(exist_ok=True)
    twse, tpex, broker = TwseSource(), TpexSource(), BrokerSource()
    funds_src, ov_src = FundamentalsSource(), OverseasSource()

    print("抓取台股籌碼…")
    quotes = _merge(twse.daily_quotes(), tpex.daily_quotes())
    inst = _merge(twse.institutional(), tpex.institutional())
    margin = _merge(twse.margin(), tpex.margin())
    print(f"  價量 {len(quotes)} / 法人 {len(inst)} / 融資券 {len(margin)}")

    print("抓取基本面(月營收)…")
    try:
        funds = funds_src.revenue()
    except Exception as e:  # noqa: BLE001
        funds = {}
        print(f"  基本面抓取失敗(略過):{e}")
    print(f"  月營收 {len(funds)} 檔")

    print("抓取海外同業(國際連動)…")
    ov_prices = ov_src.momentum(sectors.all_overseas_symbols())
    topic_mom = sectors.topic_overseas_momentum(ov_prices)
    print(f"  海外 {len(ov_prices)} 檔 / 題材動能 {topic_mom}")

    trading_date = twse.trading_date or datetime.now(TPE).strftime("%Y%m%d")
    hist = update_history(load_history(), trading_date, quotes)
    (DATA / "history.json").write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")

    records = []
    for code, q in quotes.items():
        if q.get("close", 0) <= 0 or q.get("volume", 0) <= 0:
            continue
        if code.startswith("00"):  # 排除 ETF/ETN
            continue
        topic, tmom = sectors.best_topic_for(code, topic_mom)
        rec = build_record(
            code, q, inst.get(code, {}), margin.get(code, {}),
            funds.get(code), topic, tmom,
            hist["closes"].get(code, [q["close"]]),
            hist["vols"].get(code, []),
        )
        records.append(rec)

    records.sort(key=lambda r: r["score"], reverse=True)
    top = records[:TOP_N]
    (DATA / "stocks.json").write_text(
        json.dumps(top, ensure_ascii=False, indent=1), encoding="utf-8")

    meta = {
        "updated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "trading_date": trading_date,
        "universe": len(records),
        "shown": len(top),
        "sources": {
            "twse": True, "tpex": False, "broker": broker.enabled,
            "fundamentals": bool(funds), "overseas": bool(ov_prices),
        },
        "topic_momentum": topic_mom,
        "history_days": len(next(iter(hist["closes"].values()), [])),
    }
    (DATA / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"完成:寫出 {len(top)} 檔(母體 {len(records)});累積 {meta['history_days']} 日;交易日 {trading_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
