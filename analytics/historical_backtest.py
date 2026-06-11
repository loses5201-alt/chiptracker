"""
歷史回測引擎 — 不等資料累積,用「過去可回填的面向」驗證評分預測力。

核心問題:這套評分選出來的股票,過去一段時間真的比較會漲嗎?
做法:
  1. universe:取最新交易日成交值前 N 大上市股(流動性足、短線可操作)
  2. 回填:近 LOOKBACK 交易日的個股法人(T86)、融資(MI_MARGN)、價量(Yahoo)
  3. 對每個可回測交易日 t,用「當下」資料重算簡化評分,選 top,看 t 之後 5/10/20 日報酬
  4. 統計:評分五分位的後續報酬(驗證「分數越高越會漲」)、top 組勝率/超額報酬

誠實限制:基本面(月營收)與題材新聞無歷史可回填,故歷史評分只用
  s1 法人 + s2 融資 + s6 技術(可回填的三面向),滿分 45。
  這驗證的是「籌碼+技術」選股的預測力 — 本系統最核心的部分。

執行:python -m analytics.historical_backtest   (於 repo 根目錄,離線分析,約數分鐘)
輸出 data/historical_performance.json,供前端「回測」分頁顯示。
"""
from __future__ import annotations
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fetcher import scoring, sectors
from fetcher.sources.price_history import PriceHistorySource, fetch_symbol
from fetcher.sources.revenue_history import RevenueHistory   # 月營收歷史(s3 回填)
from fetcher.sources.stock_chip_history import _buy_streak  # 連買天數(與正式版同一套邏輯)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TPE = timezone(timedelta(hours=8))
OPENAPI = "https://openapi.twse.com.tw/v1"
RWD = "https://www.twse.com.tw/rwd/zh"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json",
           "Referer": "https://www.twse.com.tw/"}

UNIVERSE_N = 300        # 回測標的池:成交值前 N 大上市股
TPEX_N = 150            # 另納成交值前 N 大上櫃股(正式評分含上櫃,回測池跟上才公允)
TPEX_RWD = "https://www.tpex.org.tw/www/zh-tw"
MKT: dict[str, str] = {}   # code → "twse"/"tpex"(_universe 填,價量抓取與籌碼分流用)
LOOKBACK = 240          # 回填近 N 交易日(約一年,涵蓋多/空不同市況,避免純多頭小樣本假象)
WARMUP = 20             # 前段暖身(算均線/RSI 需要)
FORWARD = [5, 10, 20, 60]   # 後續報酬窗口(交易日)— 60 對齊前端每日快照回測的窗口
TOP_N = 10              # 每日選前幾名當「策略持股」
BENCHMARK = "^TWII"
# 防 lookahead:法人/融資是「盤後」公布,訊號日收盤根本買不到。
# 報酬一律以「訊號次日收盤」為進場基準(可實際執行的報酬),大盤基準同步位移。
ENTRY_LAG = 1

# 潛伏回測:潛伏要等發動,窗口拉長(5/10 日太短)
STEALTH_FORWARD = [10, 20, 40, 60]
TRIGGER_PCT = 10.0      # 發動門檻:埋伏後最高漲幅 ≥ 此值算「發動」
LEAD_PCT = 8.0          # 領先:埋伏後首次達此漲幅的交易日數
# 潛伏是中小型股策略(大型股法人本就重倉、無「偷偷吃貨」),回測用中型股池才公允
STEALTH_OFFSET = 150    # 成交值排名 offset(取 rank 150~150+UNIVERSE_N 的中型股)

# T86 個股法人欄位 index(同 sources/twse.py)
_FOREIGN, _FDEALER, _TRUST, _DEALER, _TOTAL = 4, 7, 10, 11, 18
# MI_MARGN 個股融資欄位:前日餘額5/今日餘額6;融券前日11/今日12
_MG_PREV, _MG_BAL, _SH_PREV, _SH_BAL = 5, 6, 11, 12


def _num(s) -> float:
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _get(url: str, tries: int = 3) -> dict | None:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            time.sleep(1.2 * (i + 1))
    return None


def _universe(n: int = UNIVERSE_N, offset: int = 0, tpex_n: int = TPEX_N) -> list[str]:
    """
    回測標的池 = 成交值排名 offset~offset+n 的上市普通股 + 前 tpex_n 大上櫃普通股。
    offset 只套用上市(上櫃整體即中小型,潛伏池不需再 offset)。
    同步填全域 MKT(code→市場),供價量抓取與籌碼端點分流。
    """
    j = _get(f"{OPENAPI}/exchangeReport/STOCK_DAY_ALL")
    rows = []
    for r in (j or []):
        code = str(r.get("Code", "")).strip()
        if len(code) == 4 and code.isdigit() and not code.startswith("00"):
            rows.append((code, _num(r.get("TradeValue"))))
    rows.sort(key=lambda x: x[1], reverse=True)
    out = [c for c, _ in rows[offset:offset + n]]
    MKT.update({c: "twse" for c in out})
    if tpex_n > 0:
        tj = _get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes")
        trows = []
        for r in (tj or []):
            code = str(r.get("SecuritiesCompanyCode", "")).strip()
            if len(code) == 4 and code.isdigit() and not code.startswith("00"):
                trows.append((code, _num(r.get("TransactionAmount"))))
        trows.sort(key=lambda x: x[1], reverse=True)
        tp = [c for c, _ in trows[:tpex_n] if c not in MKT]
        MKT.update({c: "tpex" for c in tp})
        out += tp
    return out


def _t86_day(ds: str, want: set) -> dict | None:
    """單日個股法人 {code: {foreign,trust,dealer,total}};非交易日回 None。"""
    j = _get(f"{RWD}/fund/T86?response=json&date={ds}&selectType=ALL")
    if not j or j.get("stat") != "OK" or not j.get("data"):
        return None
    out = {}
    for row in j["data"]:
        if len(row) <= _TOTAL:
            continue
        code = str(row[0]).strip()
        if code in want:
            out[code] = {
                "foreign": _num(row[_FOREIGN]) + _num(row[_FDEALER]),
                "trust": _num(row[_TRUST]), "dealer": _num(row[_DEALER]),
                "total": _num(row[_TOTAL]),
            }
    return out


def _tpex_inst_day(ds: str, want: set) -> dict:
    """單日上櫃個股三大法人(股)。欄位實測(6488 恆等式驗證):[10]外資及陸資合計、
    [13]投信、[22]自營商合計、[23]三大法人合計。失敗回 {}(不拖垮整體回填)。"""
    if not want:
        return {}
    d = f"{ds[:4]}/{ds[4:6]}/{ds[6:]}"
    j = _get(f"{TPEX_RWD}/insti/dailyTrade?type=Daily&sect=EW&date={d}&id=&response=json")
    if not j or j.get("stat") != "ok":
        return {}
    tbl = max(j.get("tables") or [], key=lambda t: len(t.get("data") or []), default=None)
    if not tbl or not tbl.get("data"):
        return {}
    out = {}
    for row in tbl["data"]:
        if len(row) <= 23:
            continue
        code = str(row[0]).strip()
        if code in want:
            out[code] = {"foreign": _num(row[10]), "trust": _num(row[13]),
                         "dealer": _num(row[22]), "total": _num(row[23])}
    return out


def _tpex_margin_full(ds: str, want: set) -> dict:
    """單日上櫃個股融資券(張)。欄位:[2]前資餘額、[6]資餘額、[10]前券餘額、[14]券餘額。
    單位與 TWSE(張)一致;評分只用相對變化,不受單位影響。失敗回 {}。"""
    if not want:
        return {}
    d = f"{ds[:4]}/{ds[4:6]}/{ds[6:]}"
    j = _get(f"{TPEX_RWD}/margin/balance?date={d}&response=json")
    if not j or j.get("stat") != "ok":
        return {}
    tbl = max(j.get("tables") or [], key=lambda t: len(t.get("data") or []), default=None)
    if not tbl or not tbl.get("data"):
        return {}
    out = {}
    for row in tbl["data"]:
        if len(row) <= 14:
            continue
        code = str(row[0]).strip()
        if code in want:
            out[code] = {"margin_bal": _num(row[6]), "margin_prev": _num(row[2]),
                         "short_bal": _num(row[14]), "short_prev": _num(row[10])}
    return out


def _margin_day(ds: str, want: set) -> dict:
    """單日個股融資 {code: {margin_bal,margin_prev,short_bal,short_prev}}。"""
    j = _get(f"{RWD}/marginTrading/MI_MARGN?response=json&date={ds}&selectType=ALL")
    if not j or j.get("stat") != "OK":
        return {}
    tables = j.get("tables") or []
    tbl = max(tables, key=lambda t: len(t.get("data") or []), default=None)
    if not tbl or not tbl.get("data"):
        return {}
    out = {}
    for row in tbl["data"]:
        if len(row) <= _SH_BAL:
            continue
        code = str(row[0]).strip()
        if code in want:
            out[code] = {
                "margin_bal": _num(row[_MG_BAL]), "margin_prev": _num(row[_MG_PREV]),
                "short_bal": _num(row[_SH_BAL]), "short_prev": _num(row[_SH_PREV]),
            }
    return out


def _backfill_chips(universe: list[str]) -> tuple[dict, dict, list[str]]:
    """
    回填近 LOOKBACK 交易日法人/融資。回 (inst_by_date, mg_by_date, trading_days舊→新)。

    ⚠️ 限流自癒:TWSE RWD 對大量回填會封鎖一段時間(實測連跑兩輪 240 天就中標),
    被封時 _t86_day 一路回 None,看起來像「連續非交易日」。台股最長連假約 10 天,
    連續 12+ 天無資料幾乎可斷定是限流 → 冷卻 90 秒重試,最多 4 次;仍不足則明示警告。
    """
    want = set(universe)
    want_tpex = {c for c in want if MKT.get(c) == "tpex"}
    inst_by_date, mg_by_date, days = {}, {}, []
    today = datetime.now(TPE).date()
    misses, cooldowns, back = 0, 0, 0
    while back < LOOKBACK * 2 and len(days) < LOOKBACK:
        ds = (today - timedelta(days=back)).strftime("%Y%m%d")
        inst = _t86_day(ds, want)
        if inst is None:
            misses += 1
            if misses >= 12 and cooldowns < 4:
                print(f"  ⚠️ 疑似被 TWSE 限流(連續 {misses} 天無資料),冷卻 90 秒後重試…")
                time.sleep(90)
                cooldowns += 1
                misses = 0
                continue   # 冷卻後重試同一天,不跳過
            time.sleep(0.3)
            back += 1
            continue
        misses = 0
        # 上櫃法人/融資(交易日以 T86 為準;TPEX 端點失敗回 {},不拖垮整體)
        inst.update(_tpex_inst_day(ds, want_tpex))
        mg = _margin_day(ds, want)
        mg.update(_tpex_margin_full(ds, want_tpex))
        inst_by_date[ds] = inst
        mg_by_date[ds] = mg
        days.append(ds)
        time.sleep(0.25)   # 平時也放慢,降低觸發封鎖的機率
        back += 1
    days.reverse()
    if len(days) < LOOKBACK:
        print(f"  ⚠️ 僅回填 {len(days)}/{LOOKBACK} 交易日(可能仍在限流期),統計力下降")
    return inst_by_date, mg_by_date, days


def _backfill_overseas() -> dict:
    """抓題材表所有海外標的歷史(Yahoo),供回測算各交易日的題材海外動能。"""
    out = {}
    for sym in sectors.all_overseas_symbols():
        d = fetch_symbol(sym, "2y")
        if d:
            out[sym] = d
    return out


def _topic_mom_at(ds: str, ov_hist: dict) -> dict:
    """台股交易日 ds 的各題材海外動能(海外標的近5日漲幅平均%)。
    海外標的以 <= ds 的最近交易日對齊(美股/台股日期不完全一致)。"""
    sym_mom = {}
    for sym, d in ov_hist.items():
        dates, closes = d["dates"], d["closes"]
        idx = next((i for i in range(len(dates) - 1, -1, -1) if dates[i] <= ds), None)
        if idx is None or idx < 5 or closes[idx - 5] <= 0:
            continue
        sym_mom[sym] = round((closes[idx] - closes[idx - 5]) / closes[idx - 5] * 100, 2)
    return sectors.topic_overseas_momentum(sym_mom)


def _simplified_score(inst, mg, closes, vol, avg_vol, topic=None, topic_mom=0.0,
                      yoy=None) -> float:
    """歷史可回填的五面向:s1 法人 + s2 融資 + s3 基本面 + s4 國際 + s6 技術(滿分 85)。
    s3 用 MOPS 月營收歷史(已含公布延遲防 lookahead);s4 用題材海外同業近5日動能;
    缺資料時各自退中性,離正式評分只差 s5 題材新聞(真無歷史)。"""
    s1, _ = scoring.score_institutional(inst, vol)
    s2, _ = scoring.score_margin_short(mg, inst)
    s3, _ = scoring.score_fundamental({"yoy": yoy} if yoy is not None else None)
    s4, _ = scoring.score_overseas(topic, topic_mom)
    s6, _, _, _ = scoring.score_momentum(closes, vol, avg_vol)
    return s1 + s2 + s3 + s4 + s6


def _forward(closes: list[float], i: int, w: int) -> float | None:
    """訊號日 i 之後的 w 日報酬,以次日收盤(i+ENTRY_LAG)為進場基準 — 見 ENTRY_LAG 註解。"""
    base = i + ENTRY_LAG
    j = base + w
    if j < len(closes) and base < len(closes) and closes[base] > 0:
        return round((closes[j] - closes[base]) / closes[base] * 100, 2)
    return None


def run(universe: list | None = None, write: bool = True) -> dict:
    universe = universe or _universe()
    print(f"歷史回測:universe {len(universe)} 檔…")
    if not universe:
        return _write({"status": "no_data", "msg": "無法取得 universe"})
    print(f"  universe {len(universe)} 檔;回填近 {LOOKBACK} 交易日籌碼…")
    inst_d, mg_d, days = _backfill_chips(universe)
    print(f"  籌碼回填 {len(days)} 交易日;抓 Yahoo 價量…")
    px = PriceHistorySource().fetch([(c, MKT.get(c, "twse")) for c in universe], workers=12, rng="1y")
    index = fetch_symbol(BENCHMARK, "1y")
    ov_hist = _backfill_overseas()
    rev = RevenueHistory()
    rev_n = rev.load(days[0], days[-1]) if days else 0
    print(f"  價量 {len(px)}/{len(universe)} 檔;大盤 {'OK' if index else '失敗'};"
          f"海外 {len(ov_hist)} 檔;月營收 {rev_n} 個月;開始回測…")

    # 可回測日:留前 WARMUP 暖身、後 max(FORWARD) 觀察
    test_days = days[WARMUP: len(days) - max(FORWARD)] if len(days) > WARMUP + max(FORWARD) else []
    if not test_days:
        # 回填不足(多半是被限流)→ 不覆寫既有結果檔,保住上一次的有效數據
        print(f"  ✗ 可回測日為 0(回填僅 {len(days)} 天),不覆寫既有結果,請稍後重跑")
        return {"status": "insufficient", "msg": f"回填僅 {len(days)} 交易日,不足以回測"}
    quint = {q: {w: [] for w in FORWARD} for q in range(5)}      # 五分位後續報酬(絕對)
    quint_a = {q: {w: [] for w in FORWARD} for q in range(5)}    # 五分位超額報酬(扣大盤)
    top_ret = {w: [] for w in FORWARD}                            # top N 報酬
    top_alpha = {w: [] for w in FORWARD}                          # top N 超額
    strat_dates, strat_top20, strat_bench20 = [], [], []
    idx_dates = index["dates"] if index else []
    idx_closes = index["closes"] if index else []

    for ds in test_days:
        tmom = _topic_mom_at(ds, ov_hist)
        scored = []  # (score, code, i_in_px)
        for code in universe:
            p = px.get(code)
            if not p or ds not in p["dates"]:
                continue
            i = p["dates"].index(ds)
            if i < 5:
                continue
            closes = p["closes"][:i + 1]
            vol = p["vols"][i]
            avg_vol = sum(p["vols"][i - 5:i]) / 5 if i >= 5 else None
            inst = inst_d.get(ds, {}).get(code, {})
            mg = mg_d.get(ds, {}).get(code, {})
            topic, tm = sectors.best_topic_for(code, tmom)
            sc = _simplified_score(inst, mg, closes, vol, avg_vol, topic, tm,
                                   rev.yoy_at(code, ds))
            scored.append((sc, code, i))
        if len(scored) < 10:
            continue
        # 大盤同日 forward(算超額)
        ib = idx_dates.index(ds) if ds in idx_dates else -1
        bench = {w: _forward(idx_closes, ib, w) if ib >= 0 else None for w in FORWARD}

        scored.sort(key=lambda x: x[0])
        n = len(scored)
        for rank, (sc, code, i) in enumerate(scored):
            q = min(4, rank * 5 // n)  # 0=最低分,4=最高分
            p = px[code]
            for w in FORWARD:
                fr = _forward(p["closes"], i, w)
                if fr is not None:
                    quint[q][w].append(fr)
                    if bench[w] is not None:
                        quint_a[q][w].append(fr - bench[w])
        # top N(分數最高)
        top = scored[-TOP_N:]
        for w in FORWARD:
            rs = [_forward(px[c]["closes"], i, w) for _, c, i in top]
            rs = [r for r in rs if r is not None]
            if rs:
                avg = sum(rs) / len(rs)
                top_ret[w].append(avg)
                if bench[w] is not None:
                    top_alpha[w].append(avg - bench[w])
        # 策略曲線:當日 top10 的 20 日報酬 vs 大盤
        rs20 = [_forward(px[c]["closes"], i, 20) for _, c, i in top]
        rs20 = [r for r in rs20 if r is not None]
        if rs20 and bench[20] is not None:
            strat_dates.append(ds)
            strat_top20.append(round(sum(rs20) / len(rs20), 2))
            strat_bench20.append(bench[20])

    result = {
        "status": "ok",
        "generated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "universe": len(universe), "trading_days": len(days),
        "test_days": len(test_days),
        "date_range": [days[0], days[-1]] if days else [],
        "windows": FORWARD, "top_n": TOP_N, "benchmark": BENCHMARK,
        "factors_used": "s1法人 + s2融資 + s3基本面 + s4國際 + s6技術(可回填五面向,滿分85)",
        "quintile": {f"q{q+1}": {str(w): _stat(quint[q][w], quint_a[q][w]) for w in FORWARD} for q in range(5)},
        "top": {str(w): _stat(top_ret[w], top_alpha[w]) for w in FORWARD},
        "monotonic": _monotonic(quint_a),
        "strategy": {"dates": strat_dates, "top20": strat_top20, "bench20": strat_bench20},
        "note": ("評分五分位 q1(最低)~q5(最高)的後續報酬;q5 明顯高於 q1 代表評分有預測力。"
                 "歷史評分含可回填五面向(僅缺題材新聞);標的池=上市前300+上櫃前150大(與正式評分"
                 "同樣涵蓋兩市場);報酬以「訊號次日收盤」進場計算(法人資料盤後公布,當日收盤買不到);"
                 "月營收依法定公布日延遲生效,無未來資訊。universe 以今日成交值排名選取,"
                 "極早期樣本可能有倖存者偏差。"),
    }
    return _write(result) if write else result


def _stat(arr: list, alpha: list | None = None) -> dict:
    if not arr:
        return {"avg": None, "win_rate": None, "n": 0}
    out = {"avg": round(sum(arr) / len(arr), 2),
           "win_rate": round(sum(1 for x in arr if x > 0) / len(arr) * 100, 1),
           "n": len(arr)}
    if alpha:
        out["alpha"] = round(sum(alpha) / len(alpha), 2)
    return out


def _monotonic(quint: dict, windows: list = FORWARD) -> dict:
    """各窗口:q5≥q4≥q3≥q2≥q1?(分數越高報酬越高=有預測力)"""
    out = {}
    for w in windows:
        avgs = [sum(quint[q][w]) / len(quint[q][w]) if quint[q][w] else None for q in range(5)]
        if any(a is None for a in avgs):
            out[str(w)] = None
        else:
            out[str(w)] = all(avgs[i] <= avgs[i + 1] for i in range(4))
    return out


# ───────────────────────── 潛伏回測(主力潛伏專用) ─────────────────────────

def _peak_gain(closes: list, i: int, w: int) -> float | None:
    """埋伏日 i 之後 w 個交易日內的最高漲幅%(用收盤近似最高)。"""
    if i >= len(closes) or closes[i] <= 0:
        return None
    seg = closes[i + 1:i + 1 + w]
    if not seg:
        return None
    return round((max(seg) - closes[i]) / closes[i] * 100, 2)


def _days_to(closes: list, i: int, w: int, thr: float) -> int | None:
    """埋伏後首次達 thr% 漲幅的交易日數(領先天數);未達回 None。"""
    if i >= len(closes) or closes[i] <= 0:
        return None
    for k in range(1, w + 1):
        if i + k < len(closes) and (closes[i + k] - closes[i]) / closes[i] * 100 >= thr:
            return k
    return None


def _median(arr: list) -> float | None:
    if not arr:
        return None
    s = sorted(arr)
    n = len(s)
    return s[n // 2] if n % 2 else round((s[n // 2 - 1] + s[n // 2]) / 2, 1)


def _streak_at(code: str, ds: str, inst_d: dict, days: list) -> int:
    """交易日 ds 當下的法人連買天數(近10日 total 序列套 _buy_streak)。"""
    series = []
    for d in days:
        if d > ds:
            break
        rec = inst_d.get(d, {}).get(code)
        if rec is not None:
            series.append(rec.get("total", 0))
    return _buy_streak(series[-10:])


def run_stealth(universe: list | None = None, write: bool = True) -> dict:
    """驗證主力潛伏:潛伏分高的股,埋伏後是否真的會發動(比大盤/比動能選股更強)。"""
    universe = universe or _universe()
    print(f"潛伏回測:universe {len(universe)} 檔…")
    if not universe:
        return _write_stealth({"status": "no_data", "msg": "無法取得 universe"})
    inst_d, mg_d, days = _backfill_chips(universe)
    print(f"  籌碼回填 {len(days)} 交易日;抓 Yahoo 價量…")
    px = PriceHistorySource().fetch([(c, MKT.get(c, "twse")) for c in universe], workers=12, rng="2y")
    index = fetch_symbol(BENCHMARK, "2y")
    ov_hist = _backfill_overseas()
    print(f"  價量 {len(px)}/{len(universe)} 檔;海外 {len(ov_hist)} 檔;開始潛伏回測…")

    W = STEALTH_FORWARD
    maxw = max(W)
    test_days = days[WARMUP: len(days) - maxw] if len(days) > WARMUP + maxw else []
    if not test_days:
        print(f"  ✗ 可回測日為 0(回填僅 {len(days)} 天),不覆寫既有結果,請稍後重跑")
        return {"status": "insufficient", "msg": f"回填僅 {len(days)} 交易日,不足以回測"}
    quint = {q: {w: [] for w in W} for q in range(5)}
    quint_a = {q: {w: [] for w in W} for q in range(5)}
    st_ret = {w: [] for w in W}; st_alpha = {w: [] for w in W}      # 潛伏 top
    mom_ret = {w: [] for w in W}; mom_alpha = {w: [] for w in W}    # 對照:動能 top
    trig = {w: [] for w in W}                                       # 發動(0/1)
    lead = []                                                       # 領先天數
    idx_dates = index["dates"] if index else []
    idx_closes = index["closes"] if index else []

    for ds in test_days:
        tmom = _topic_mom_at(ds, ov_hist)
        st_scored, mom_scored = [], []
        for code in universe:
            p = px.get(code)
            if not p or ds not in p["dates"]:
                continue
            i = p["dates"].index(ds)
            if i < WARMUP:
                continue
            closes = p["closes"][:i + 1]
            vol = p["vols"][i]
            avg_vol = sum(p["vols"][i - 5:i]) / 5 if i >= 5 else None
            inst = inst_d.get(ds, {}).get(code, {})
            mg = mg_d.get(ds, {}).get(code, {})
            streak = _streak_at(code, ds, inst_d, days)
            sc, _ = scoring.score_stealth(inst, mg, closes, vol, avg_vol, None, streak)
            st_scored.append((sc, code, i))
            topic, tm = sectors.best_topic_for(code, tmom)
            msc = _simplified_score(inst, mg, closes, vol, avg_vol, topic, tm)
            mom_scored.append((msc, code, i))
        if len(st_scored) < 10:
            continue
        ib = idx_dates.index(ds) if ds in idx_dates else -1
        bench = {w: _forward(idx_closes, ib, w) if ib >= 0 else None for w in W}

        # 潛伏分五分位後續報酬
        st_scored.sort(key=lambda x: x[0])
        n = len(st_scored)
        for rank, (sc, code, i) in enumerate(st_scored):
            q = min(4, rank * 5 // n)
            p = px[code]
            for w in W:
                fr = _forward(p["closes"], i, w)
                if fr is not None:
                    quint[q][w].append(fr)
                    if bench[w] is not None:
                        quint_a[q][w].append(fr - bench[w])
        # 潛伏 top:報酬 + 發動率 + 領先天數
        st_top = st_scored[-TOP_N:]
        for w in W:
            rs = [_forward(px[c]["closes"], i, w) for _, c, i in st_top]
            rs = [r for r in rs if r is not None]
            if rs:
                avg = sum(rs) / len(rs)
                st_ret[w].append(avg)
                if bench[w] is not None:
                    st_alpha[w].append(avg - bench[w])
            for _, c, i in st_top:
                pg = _peak_gain(px[c]["closes"], i, w)
                if pg is not None:
                    trig[w].append(1 if pg >= TRIGGER_PCT else 0)
        for _, c, i in st_top:
            k = _days_to(px[c]["closes"], i, maxw, LEAD_PCT)
            if k is not None:
                lead.append(k)
        # 對照:動能 top 同期報酬
        mom_scored.sort(key=lambda x: x[0])
        mom_top = mom_scored[-TOP_N:]
        for w in W:
            rs = [_forward(px[c]["closes"], i, w) for _, c, i in mom_top]
            rs = [r for r in rs if r is not None]
            if rs:
                avg = sum(rs) / len(rs)
                mom_ret[w].append(avg)
                if bench[w] is not None:
                    mom_alpha[w].append(avg - bench[w])

    result = {
        "status": "ok",
        "generated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "universe": len(universe), "trading_days": len(days), "test_days": len(test_days),
        "date_range": [days[0], days[-1]] if days else [],
        "windows": W, "top_n": TOP_N, "benchmark": BENCHMARK,
        "trigger_pct": TRIGGER_PCT, "lead_pct": LEAD_PCT,
        "quintile": {f"q{q+1}": {str(w): _stat(quint[q][w], quint_a[q][w]) for w in W} for q in range(5)},
        "stealth_top": {str(w): _stat(st_ret[w], st_alpha[w]) for w in W},
        "momentum_top": {str(w): _stat(mom_ret[w], mom_alpha[w]) for w in W},
        "trigger_rate": {str(w): (round(sum(trig[w]) / len(trig[w]) * 100, 1) if trig[w] else None) for w in W},
        "lead_days_median": _median(lead), "lead_n": len(lead),
        "monotonic": _monotonic(quint_a, W),
        "note": ("潛伏分五分位後續報酬(q5最高分);發動率=潛伏top埋伏後最高漲幅≥門檻比例;"
                 "領先天數=首次達標的中位數交易日;momentum_top 為動能選股對照組。"),
    }
    return _write_stealth(result) if write else result


def _write_stealth(result: dict) -> dict:
    DATA.mkdir(exist_ok=True)
    (DATA / "stealth_backtest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def _write(result: dict) -> dict:
    DATA.mkdir(exist_ok=True)
    (DATA / "historical_performance.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 終端 cp950 印不出 ≥/α(兩條路徑都要)
    except Exception:  # noqa: BLE001
        pass
    if "--stealth" in sys.argv:
        # 大型股池(offset=0)對潛伏不公平;預設用中型股池,加 --large 才測大型對比
        off = 0 if "--large" in sys.argv else STEALTH_OFFSET
        uni = _universe(UNIVERSE_N, offset=off)
        print(f"潛伏回測標的池:成交值 rank {off}~{off + UNIVERSE_N}（{'大型' if off == 0 else '中型'}股)")
        r = run_stealth(uni)
        if r["status"] == "ok":
            print(f"\n潛伏回測:universe {r['universe']} / 回測 {r['test_days']} 日 / {r['date_range']}")
            print("潛伏分五分位後續報酬(q1最低 → q5最高):")
            for q in range(1, 6):
                cells = " | ".join(f"{w}日 {r['quintile'][f'q{q}'][str(w)]['avg']}%"
                                   f"(α{r['quintile'][f'q{q}'][str(w)].get('alpha')})" for w in r["windows"])
                print(f"  q{q}: {cells}")
            print("發動率(埋伏後最高漲幅>=%d%%): " % int(r["trigger_pct"])
                  + " | ".join(f"{w}日 {r['trigger_rate'][str(w)]}%" for w in r["windows"]))
            print(f"領先天數中位數(首達+{int(r['lead_pct'])}%): {r['lead_days_median']} 日(n={r['lead_n']})")
            print("潛伏top vs 動能top 超額α:")
            for w in r["windows"]:
                print(f"  {w}日: 潛伏 α={r['stealth_top'][str(w)].get('alpha')} | "
                      f"動能 α={r['momentum_top'][str(w)].get('alpha')}")
            print(f"單調性(q5≥…≥q1): {r['monotonic']}")
        else:
            print(r.get("msg"))
        sys.exit(0)
    r = run()
    if r["status"] == "ok":
        print(f"\n完成:universe {r['universe']} / 回測 {r['test_days']} 日 / {r['date_range']}")
        print("五分位後續報酬(q1最低分 → q5最高分):")
        for q in range(1, 6):
            cells = " | ".join(f"{w}日 {r['quintile'][f'q{q}'][str(w)]['avg']}%(勝{r['quintile'][f'q{q}'][str(w)]['win_rate']}%)" for w in FORWARD)
            print(f"  q{q}: {cells}")
        print(f"top{r['top_n']} 超額: " + " | ".join(f"{w}日 α={r['top'][str(w)].get('alpha')}" for w in FORWARD))
        print(f"單調性(q5≥…≥q1): {r['monotonic']}")
    else:
        print(r.get("msg"))
    sys.exit(0)
