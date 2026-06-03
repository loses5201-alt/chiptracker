"""
個股籌碼歷史 — top 推薦股近 N 交易日的法人買賣超 + 融資餘額趨勢。

為什麼:延續「看一段時間」原則到個股 — 法人「連續買超幾天」、融資是增是減,
比單日更能判斷主力是否持續進場。T86 / MI_MARGN 皆可指定日期 → 回填,不必累積。

來源(皆證交所 RWD,可指定日期;僅上市,上櫃 OpenAPI 無歷史):
  法人  /rwd/zh/fund/T86?date=&selectType=ALL          舊格式 data 陣列,row[0]代號 row[18]三大法人合計(股)
  融資  /rwd/zh/marginTrading/MI_MARGN?date=&selectType=ALL  新格式 tables[1],row[0]代號 row[6]融資今日餘額(張)

回 {code: {dates, inst[股], margin[張], inst_buy_streak}};inst_buy_streak 正=連買天數、負=連賣。
"""
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

TWSE = "https://www.twse.com.tw/rwd/zh"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json",
           "Referer": "https://www.twse.com.tw/"}
TPE = timezone(timedelta(hours=8))
_T86_TOTAL = 18   # T86 三大法人合計欄位 index
_MG_BAL = 6       # MI_MARGN 融資今日餘額欄位 index


def _num(s) -> float:
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _get(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _t86_day(ds: str, want: set) -> dict | None:
    """單日個股三大法人合計(股);非交易日回 None。"""
    j = _get(f"{TWSE}/fund/T86?response=json&date={ds}&selectType=ALL")
    if not j or j.get("stat") != "OK" or not j.get("data"):
        return None
    out = {}
    for row in j["data"]:
        if len(row) <= _T86_TOTAL:
            continue
        code = str(row[0]).strip()
        if code in want:
            out[code] = _num(row[_T86_TOTAL])
    return out


def _margin_day(ds: str, want: set) -> dict:
    """單日個股融資餘額(張);失敗回空。"""
    j = _get(f"{TWSE}/marginTrading/MI_MARGN?response=json&date={ds}&selectType=ALL")
    if not j or j.get("stat") != "OK":
        return {}
    tables = j.get("tables") or []
    # 找個股別融資融券彙總表(列數最多的那張)
    tbl = max(tables, key=lambda t: len(t.get("data") or []), default=None)
    if not tbl or not tbl.get("data"):
        return {}
    out = {}
    for row in tbl["data"]:
        if len(row) <= _MG_BAL:
            continue
        code = str(row[0]).strip()
        if code in want:
            out[code] = _num(row[_MG_BAL])
    return out


def _tpex_insti_day(ds: str, want: set) -> dict:
    """單日上櫃個股三大法人合計(股);ds 為 YYYYMMDD(內部轉櫃買的 YYYY/MM/DD)。失敗回空。
    來源:tpex.org.tw/www/zh-tw/insti/dailyTrade(可指定日期),欄位 row[23]=三大法人合計。"""
    if not want:
        return {}
    d = f"{ds[:4]}/{ds[4:6]}/{ds[6:]}"
    j = _get(f"https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={d}&id=&response=json")
    if not j or j.get("stat") != "ok":
        return {}
    tables = j.get("tables") or []
    tbl = max(tables, key=lambda t: len(t.get("data") or []), default=None)
    if not tbl or not tbl.get("data"):
        return {}
    out = {}
    for row in tbl["data"]:
        if len(row) <= 23:
            continue
        code = str(row[0]).strip()
        if code in want:
            out[code] = _num(row[23])
    return out


def _tpex_margin_day(ds: str, want: set) -> dict:
    """單日上櫃個股融資餘額(張);ds YYYYMMDD→櫃買 YYYY/MM/DD。欄位 row[6]=資餘額。"""
    if not want:
        return {}
    d = f"{ds[:4]}/{ds[4:6]}/{ds[6:]}"
    j = _get(f"https://www.tpex.org.tw/www/zh-tw/margin/balance?date={d}&response=json")
    if not j or j.get("stat") != "ok":
        return {}
    tbl = max(j.get("tables") or [], key=lambda t: len(t.get("data") or []), default=None)
    if not tbl or not tbl.get("data"):
        return {}
    out = {}
    for row in tbl["data"]:
        if len(row) <= 6:
            continue
        code = str(row[0]).strip()
        if code in want:
            out[code] = _num(row[6])
    return out


def _buy_streak(vals: list) -> int:
    """法人連續同向天數:正=連買、負=連賣、0=混。"""
    if not vals:
        return 0
    last = vals[-1]
    d = 1 if last > 0 else -1 if last < 0 else 0
    if not d:
        return 0
    n = 0
    for v in reversed(vals):
        if (d > 0 and v > 0) or (d < 0 and v < 0):
            n += 1
        else:
            break
    return n * d


def _turn_signal(vals: list) -> str | None:
    """法人轉折:近2日由賣轉買=「初買」(比連買更早的進場訊號);由買轉賣=「初賣」(早空訊號)。"""
    if len(vals) < 5:
        return None
    recent = sum(vals[-2:])
    prior = sum(vals[-7:-2]) if len(vals) >= 7 else sum(vals[:-2])
    if recent > 0 and prior < 0:
        return "初買"
    if recent < 0 and prior > 0:
        return "初賣"
    return None


def _ffill(vals: list) -> list:
    """融資餘額缺值(0,某日 MI_MARGN 抓取失敗)用前一日填;開頭缺用第一個有效值回填。
    (融資餘額不會真的是 0,0 一律視為缺資料,避免污染走勢與變化率)"""
    out, prev = [], None
    for v in vals:
        if v > 0:
            prev = v
        out.append(prev)
    first = next((x for x in out if x), 0)
    return [x if x else first for x in out]


def fetch(items: list, days: int = 10, lookback: int = 24) -> dict:
    """
    回 top 推薦股近 days 交易日籌碼歷史(舊→新)。
    items:[(code, mkt)] 或 [code](預設上市)。上市法人走 T86、融資走 MI_MARGN;
    上櫃法人走 TPEX dailyTrade、融資暫無(上櫃無免費融資歷史源)。
    交易日以上市 T86 為準對齊(top 通常含上市股)。
    """
    if not items:
        return {}
    pairs = [(x[0], x[1]) if isinstance(x, (tuple, list)) else (x, "twse") for x in items]
    codes = [c for c, _ in pairs]
    twse_want = {c for c, m in pairs if m == "twse"}
    tpex_want = {c for c, m in pairs if m == "tpex"}
    today = datetime.now(TPE).date()
    rows: list[tuple] = []  # (date, inst_map, margin_map)
    for back in range(lookback):
        if len(rows) >= days:
            break
        ds = (today - timedelta(days=back)).strftime("%Y%m%d")
        inst = _t86_day(ds, twse_want) if twse_want else None
        tp_inst = _tpex_insti_day(ds, tpex_want) if tpex_want else {}
        # 交易日判斷:有上市股看 T86(None=非交易日);全上櫃則看 TPEX 是否有資料
        if twse_want:
            if inst is None:
                time.sleep(0.2)
                continue
        elif not tp_inst:
            time.sleep(0.2)
            continue
        inst = inst or {}
        inst.update(tp_inst)
        mg = _margin_day(ds, twse_want) if twse_want else {}
        if tpex_want:
            mg.update(_tpex_margin_day(ds, tpex_want))
        rows.append((ds, inst, mg))
    rows.reverse()
    dates = [r[0] for r in rows]
    out = {}
    for code in codes:
        inst_series = [r[1].get(code, 0) for r in rows]
        out[code] = {
            "dates": dates,
            "inst": inst_series,                                   # 三大法人合計(股)
            "margin": _ffill([r[2].get(code, 0) for r in rows]),   # 融資餘額(張,缺值前填)
            "inst_buy_streak": _buy_streak(inst_series),
            "turn": _turn_signal(inst_series),
        }
    return out
