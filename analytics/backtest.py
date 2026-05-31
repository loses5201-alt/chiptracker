"""
回測引擎 — 驗證 ChipTracker 推薦股的實際後續表現。

核心問題:「分數高的股票,之後真的比較會漲嗎?」
做法:讀每日推薦快照(data/daily/*.json),用 Yahoo 抓含日期的股價,
      以「推薦日」精準對齊,算多時間窗(5/10/20/60 交易日)收益率,
      再依建議強度(strong/mid/watch)分組統計。
輸出 data/performance.json,供前端「回測」分頁顯示。

執行:python -m analytics.backtest   (於 repo 根目錄)

對應使用者「多窗口 + 勝率 + 分組」需求:
  - 多窗口:推薦日後 +5/+10/+20/+60 交易日收益率
  - 勝率:各組各窗口「收益>0」比例
  - 分組:strong/mid/watch 分開 → 驗證「分數越高報酬越高」的單調性(monotonic)

(對比大盤超額報酬為日後可加選項,目前未納入。)
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fetcher.sources.price_history import _fetch_one

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DAILY = DATA / "daily"
WINDOWS = [5, 10, 20, 60]
GROUPS = ["strong", "mid", "watch"]
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


def _series(code: str, cache: dict, rng: str = "6mo") -> dict | None:
    """取個股含日期的收盤序列(快取,回測窗最長 60 日 → 用 6mo 確保夠長)。"""
    if code not in cache:
        _, data = _fetch_one(code, rng)
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
    buckets = {g: {w: [] for w in WINDOWS} for g in GROUPS}
    counted, matured = 0, 0
    dates_all = [d for d, _ in snapshots]

    for rec_date, recs in snapshots:
        for r in recs:
            code, rec = r.get("c"), r.get("rec")
            if rec not in buckets:
                continue
            series = _series(code, cache)
            if not series:
                continue
            fr = _forward_returns(series, rec_date)
            counted += 1
            for w in WINDOWS:
                if fr[w] is not None:
                    buckets[rec][w].append(fr[w])
                    if w == WINDOWS[0]:
                        matured += 1

    result = {
        "status": "ok",
        "generated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "snapshot_days": len(snapshots),
        "date_range": [dates_all[0], dates_all[-1]] if dates_all else [],
        "recommendations_seen": counted,
        "windows": WINDOWS,
        "groups": {g: _group_stats(buckets[g]) for g in GROUPS},
        "monotonic": _check_monotonic(buckets),
        "note": ("收益率=推薦日收盤後 N 交易日漲跌幅%。需累積足夠交易日(最短窗 "
                 f"{WINDOWS[0]} 日、最長 {WINDOWS[-1]} 日)樣本才有統計意義。"),
    }
    return _write(result)


def _group_stats(window_data: dict[int, list]) -> dict:
    """單一分組各窗口統計:平均收益、勝率、樣本數。"""
    out = {}
    for w in WINDOWS:
        arr = window_data[w]
        if arr:
            out[str(w)] = {
                "avg": round(sum(arr) / len(arr), 2),
                "win_rate": round(sum(1 for x in arr if x > 0) / len(arr) * 100, 1),
                "n": len(arr),
            }
        else:
            out[str(w)] = {"avg": None, "win_rate": None, "n": 0}
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
        if any(a is None for a in avgs):
            out[str(w)] = None
        else:
            out[str(w)] = avgs[0] >= avgs[1] >= avgs[2]  # strong >= mid >= watch
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
        print(f"回測完成:{r['snapshot_days']} 天快照、{r['recommendations_seen']} 筆推薦評估")
        for g in GROUPS:
            cells = " | ".join(
                f"{w}日 avg={r['groups'][g][str(w)]['avg']}% 勝{r['groups'][g][str(w)]['win_rate']}% n={r['groups'][g][str(w)]['n']}"
                for w in WINDOWS)
            print(f"  {g:6}: {cells}")
        print(f"  評分單調性(strong≥mid≥watch): {r['monotonic']}")
    else:
        print(r["msg"])
    sys.exit(0)
