"""
回測引擎 — 驗證 ChipTracker 推薦股的實際後續表現。

核心問題:「分數高的股票,之後真的比較會漲嗎?哪個面向最準?」
做法:讀每日推薦快照(data/daily/*.json),用 Yahoo 抓含日期的股價,
      以「推薦日」精準對齊,算多時間窗(5/10/20/60 交易日)收益率。
輸出 data/performance.json,供前端「回測」分頁顯示。

執行:python -m analytics.backtest   (於 repo 根目錄)

四個分析維度:
  1. 強度分組   strong/mid/watch 各窗口平均收益、勝率,並驗證單調性(分數越高越會漲)
  2. 超額報酬   個股收益 − 同期大盤(加權指數)收益 = alpha,排除大盤齊漲齊跌的干擾
  3. 市場別     上市(twse) vs 上櫃(tpex)推薦表現是否不同
  4. 面向預測力 六面向(法人/融資/基本面/國際/題材/技術)各自高分組 vs 低分組的
                超額報酬差 → 找出最有預測力的面向(差越大越能預測上漲)

注意:後三項需快照含 mkt / s 欄位(新版 build 才有),且需累積足夠交易日樣本才有意義。
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median

from fetcher.sources.price_history import _fetch_one, fetch_symbol

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DAILY = DATA / "daily"
WINDOWS = [5, 10, 20, 60]
GROUPS = ["strong", "mid", "watch"]
MARKETS = ["twse", "tpex"]
FACTOR_NAMES = ["法人", "融資", "基本面", "國際", "題材", "技術"]  # 對應 s1~s6
BENCHMARK = "^TWII"  # 加權指數,算超額報酬的基準
MIN_SPLIT = 6        # 面向預測力:高低分組各需足夠樣本才計算
TPE = timezone(timedelta(hours=8))


def _load_snapshots() -> list[tuple[str, list]]:
    """讀所有每日快照,回 [(交易日YYYYMMDD, 推薦清單)],依日期排序。"""
    if not DAILY.exists():
        return []
    out = []
    for f in sorted(DAILY.glob("*.json")):
        try:
            out.append((f.stem, json.loads(f.read_text(encoding="utf-8"))))
        except Exception:  # noqa: BLE001
            continue
    return out


def _series(code: str, market: str | None, cache: dict, rng: str = "6mo") -> dict | None:
    """取個股含日期的收盤序列(快取,回測窗最長 60 日 → 用 6mo 確保夠長)。"""
    if code not in cache:
        _, data = _fetch_one((code, market), rng)
        cache[code] = data  # 可能為 None
    return cache[code]


def _forward_returns(series: dict, rec_date: str) -> dict[int, float | None]:
    """
    以 rec_date(推薦日)為基準,算之後各窗口收益率(%)。
    用真實日期對齊:找到 dates 中 == rec_date 的索引,取其後第 w 個交易日。
    對不上(該股當天停牌或資料缺)或窗口尚未到期 → 該窗口回 None。
    """
    dates, closes = series["dates"], series["closes"]
    try:
        i = dates.index(rec_date)
    except ValueError:
        return {w: None for w in WINDOWS}
    base = closes[i]
    out: dict[int, float | None] = {}
    for w in WINDOWS:
        j = i + w
        out[w] = round((closes[j] - base) / base * 100, 2) if (j < len(closes) and base > 0) else None
    return out


def run() -> dict:
    """執行回測,回傳統計並寫 data/performance.json。"""
    snapshots = _load_snapshots()
    if not snapshots:
        return _write({"status": "no_data",
                       "msg": "尚無每日快照。請先讓 build 跑幾個交易日累積 data/daily/,回測才有原料。"})

    cache: dict[str, dict | None] = {}
    index = fetch_symbol(BENCHMARK, "1y")  # 大盤序列(算 alpha 用),抓一次共用
    idx_cache: dict[str, dict] = {}

    def index_fr(rec_date: str) -> dict[int, float | None]:
        if rec_date not in idx_cache:
            idx_cache[rec_date] = _forward_returns(index, rec_date) if index else {w: None for w in WINDOWS}
        return idx_cache[rec_date]

    g_ret = {g: {w: [] for w in WINDOWS} for g in GROUPS}
    g_alpha = {g: {w: [] for w in WINDOWS} for g in GROUPS}
    m_ret = {m: {w: [] for w in WINDOWS} for m in MARKETS}
    factor_samples: list[tuple[list, dict]] = []  # [(六面向分數, {window: alpha})]
    counted = 0
    dates_all = [d for d, _ in snapshots]

    for rec_date, recs in snapshots:
        ifr = index_fr(rec_date)
        for r in recs:
            code, rec, mkt = r.get("c"), r.get("rec"), r.get("mkt")
            series = _series(code, mkt, cache)
            if not series:
                continue
            fr = _forward_returns(series, rec_date)
            counted += 1
            alpha: dict[int, float] = {}
            for w in WINDOWS:
                if fr[w] is None:
                    continue
                if rec in g_ret:
                    g_ret[rec][w].append(fr[w])
                if mkt in m_ret:
                    m_ret[mkt][w].append(fr[w])
                if ifr.get(w) is not None:
                    a = round(fr[w] - ifr[w], 2)
                    alpha[w] = a
                    if rec in g_alpha:
                        g_alpha[rec][w].append(a)
            s = r.get("s")
            if s and len(s) == 6 and alpha:
                factor_samples.append((s, alpha))

    result = {
        "status": "ok",
        "generated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "snapshot_days": len(snapshots),
        "date_range": [dates_all[0], dates_all[-1]] if dates_all else [],
        "recommendations_seen": counted,
        "windows": WINDOWS,
        "benchmark": BENCHMARK,
        "benchmark_ok": bool(index),
        "groups": {g: _group_stats(g_ret[g], g_alpha[g]) for g in GROUPS},
        "by_market": {m: _market_stats(m_ret[m]) for m in MARKETS},
        "factor_power": _factor_power(factor_samples),
        "monotonic": _check_monotonic(g_ret),
        "note": ("收益率=推薦日收盤後 N 交易日漲跌幅%;alpha=同期超越大盤幅度;"
                 "面向預測力=該面向高分股 vs 低分股的 alpha 差。需累積足夠交易日樣本才有統計意義。"),
    }
    return _write(result)


def _group_stats(ret: dict[int, list], alpha: dict[int, list]) -> dict:
    """單一強度分組各窗口統計:平均收益、勝率、樣本數、平均超額報酬。"""
    out = {}
    for w in WINDOWS:
        arr, aarr = ret[w], alpha[w]
        out[str(w)] = {
            "avg": round(sum(arr) / len(arr), 2) if arr else None,
            "win_rate": round(sum(1 for x in arr if x > 0) / len(arr) * 100, 1) if arr else None,
            "alpha": round(sum(aarr) / len(aarr), 2) if aarr else None,
            "n": len(arr),
        }
    return out


def _market_stats(ret: dict[int, list]) -> dict:
    """單一市場別各窗口統計:平均收益、勝率、樣本數。"""
    out = {}
    for w in WINDOWS:
        arr = ret[w]
        out[str(w)] = {
            "avg": round(sum(arr) / len(arr), 2) if arr else None,
            "win_rate": round(sum(1 for x in arr if x > 0) / len(arr) * 100, 1) if arr else None,
            "n": len(arr),
        }
    return out


def _factor_power(samples: list[tuple[list, dict]]) -> dict:
    """
    各面向預測力:把樣本依該面向分數中位數切高/低兩半,
    比較兩半的平均超額報酬(alpha),差值為正且越大 → 該面向越能預測上漲。
    樣本不足(任一半 < MIN_SPLIT)→ None。
    """
    out: dict[str, dict] = {}
    for i, name in enumerate(FACTOR_NAMES):
        row: dict[str, float | None] = {}
        for w in WINDOWS:
            pairs = [(s[i], a[w]) for s, a in samples if w in a]
            if len(pairs) < MIN_SPLIT * 2:
                row[str(w)] = None
                continue
            med = median(p[0] for p in pairs)
            high = [a for sc, a in pairs if sc >= med]
            low = [a for sc, a in pairs if sc < med]
            if len(high) < MIN_SPLIT or len(low) < MIN_SPLIT:
                row[str(w)] = None
                continue
            row[str(w)] = round(sum(high) / len(high) - sum(low) / len(low), 2)
        out[name] = row
    return out


def _check_monotonic(buckets: dict) -> dict[str, bool | None]:
    """
    驗證評分預測力:每個窗口,strong 平均報酬是否 ≥ mid ≥ watch(單調遞增)。
    True=評分有預測力;False=沒有;None=樣本不足。
    """
    out = {}
    for w in WINDOWS:
        avgs = []
        for g in GROUPS:
            arr = buckets[g][w]
            avgs.append(sum(arr) / len(arr) if arr else None)
        out[str(w)] = None if any(a is None for a in avgs) else avgs[0] >= avgs[1] >= avgs[2]
    return out


def _write(result: dict) -> dict:
    DATA.mkdir(exist_ok=True)
    (DATA / "performance.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys
    r = run()
    if r["status"] == "ok":
        print(f"回測完成:{r['snapshot_days']} 天快照、{r['recommendations_seen']} 筆推薦評估"
              f"(大盤基準 {'OK' if r['benchmark_ok'] else '抓取失敗'})")
        for g in GROUPS:
            cells = " | ".join(
                f"{w}日 avg={r['groups'][g][str(w)]['avg']}% α={r['groups'][g][str(w)]['alpha']} n={r['groups'][g][str(w)]['n']}"
                for w in WINDOWS)
            print(f"  {g:6}: {cells}")
        print(f"  市場別: {r['by_market']}")
        print(f"  面向預測力: {r['factor_power']}")
        print(f"  評分單調性(strong≥mid≥watch): {r['monotonic']}")
    else:
        print(r["msg"])
    sys.exit(0)
