"""
ChipTracker 主程式 — 在 GitHub Actions 上每交易日收盤後執行。

流程:抓資料 → 累積歷史 → 計算 s1~s5 評分 → 排名 → 寫出 data/*.json。
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
from . import scoring

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TOP_N = 40            # 取前 N 檔放進儀表板
HISTORY_CAP = 60      # 每檔最多保留幾日收盤,供均線/位置計算
TPE = timezone(timedelta(hours=8))  # 顯示用台北時區


def _merge(*dicts: dict) -> dict:
    """把多個來源(上市、上櫃…)的 {code: data} 合併成一份。"""
    out: dict = {}
    for d in dicts:
        out.update(d)
    return out


def load_history() -> dict:
    f = DATA / "history.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"last_date": None, "closes": {}}


def update_history(hist: dict, trading_date: str, quotes: dict) -> dict:
    """把今日收盤價 append 進歷史;同一交易日重跑不會重複累加。"""
    if trading_date and trading_date == hist.get("last_date"):
        return hist  # 今天已收錄過,直接沿用(避免重跑灌爆)
    closes = hist.get("closes", {})
    for code, q in quotes.items():
        if q.get("close", 0) <= 0:
            continue
        arr = closes.setdefault(code, [])
        arr.append(q["close"])
        if len(arr) > HISTORY_CAP:
            del arr[:-HISTORY_CAP]
    hist["closes"] = closes
    hist["last_date"] = trading_date
    return hist


def fmt_lots(shares: float) -> str:
    """股數轉「張」顯示(1 張 = 1000 股)。"""
    lots = shares / 1000
    if abs(lots) >= 10000:
        return f"{lots/10000:.1f}萬張"
    return f"{lots:,.0f}張"


def build_record(code, q, inst, mg, conc, closes) -> dict:
    """把單一檔股票的各路資料,組成前端要的一筆記錄。"""
    volume = q.get("volume", 0)
    s1, n1 = scoring.score_institutional(inst, volume)
    s2, n2 = scoring.score_broker(conc)
    s3, n3 = scoring.score_margin(mg)
    s4, n4 = scoring.score_technical(closes, volume, None)
    s5, rsi, pos, n5 = scoring.score_momentum(closes)
    total = s1 + s2 + s3 + s4 + s5

    reasons = [n for n in (n1, n2, n3, n4, n5) if n][:3]
    close = q.get("close", 0)
    smart_bits = []
    if inst.get("foreign"):
        smart_bits.append(f"外資{'+' if inst['foreign']>=0 else ''}{fmt_lots(inst['foreign'])}")
    if inst.get("trust"):
        smart_bits.append(f"投信{'+' if inst['trust']>=0 else ''}{fmt_lots(inst['trust'])}")

    return {
        "c": code,
        "n": q.get("name", ""),
        "sec": "—",  # 類股別:此端點未提供,後續可補產業對照表
        "rec": scoring.grade(total),
        "score": total,
        "s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5,
        "pos": pos if pos is not None else 50,
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
    print("抓取證交所資料中…")
    twse, tpex, broker = TwseSource(), TpexSource(), BrokerSource()

    quotes = _merge(twse.daily_quotes(), tpex.daily_quotes())
    inst = _merge(twse.institutional(), tpex.institutional())
    margin = _merge(twse.margin(), tpex.margin())
    conc = broker.concentration() if broker.enabled else {}
    print(f"  價量 {len(quotes)} 檔 / 法人 {len(inst)} 檔 / 融資券 {len(margin)} 檔")

    # 交易日標記:優先用法人(T86)實際抓到的交易日,沒有才退回系統日期。
    # 這比系統日期更準(例如連假、盤後資料尚未更新時)。
    trading_date = twse.trading_date or datetime.now(TPE).strftime("%Y%m%d")
    hist = update_history(load_history(), trading_date, quotes)
    (DATA / "history.json").write_text(
        json.dumps(hist, ensure_ascii=False), encoding="utf-8")

    records = []
    for code, q in quotes.items():
        if q.get("close", 0) <= 0 or q.get("volume", 0) <= 0:
            continue
        # 排除 ETF / ETN(代號以 00 開頭),讓榜單聚焦個股籌碼。
        # 日後若想納入,把這兩行拿掉即可。
        if code.startswith("00"):
            continue
        rec = build_record(
            code, q,
            inst.get(code, {}), margin.get(code, {}),
            conc.get(code), hist["closes"].get(code, [q["close"]]),
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
        "sources": {"twse": True, "tpex": False, "broker": broker.enabled},
        "history_days": len(next(iter(hist["closes"].values()), [])),
    }
    (DATA / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"完成:寫出 {len(top)} 檔到 data/stocks.json(母體 {len(records)} 檔)")
    print(f"歷史已累積 {meta['history_days']} 個交易日;交易日={trading_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
