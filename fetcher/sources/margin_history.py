"""
大盤信用交易餘額歷史 — 融資 / 融券餘額的「總量趨勢」。

為什麼需要:單日融資數字看不出意義,要看「現在總量多少 + 是不是逐日增加」。
證交所 RWD 信用交易統計(selectType=MS)可指定日期,因此能一次回填近 N 交易日,
不必從零累積 → 使用者立即看得到一週趨勢。

來源:www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?selectType=MS&date=YYYYMMDD
表格(tables[0])欄位:項目 / 買進 / 賣出 / 現金(券)償還 / 前日餘額 / 今日餘額
  data[0] 融資(交易單位=張)、data[1] 融券(張)、data[2] 融資金額(仟元)
單位:餘額為「張」;融資金額仟元 → 本檔轉億元。
"""
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

RWD = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
TPE = timezone(timedelta(hours=8))
_BAL = 5  # 「今日餘額」欄位 index


def _num(s) -> float:
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def fetch_trend(days: int = 10, lookback: int = 24) -> list[dict]:
    """
    回近 days 個交易日的大盤信用交易餘額,舊→新排序。
    從今天往前掃最多 lookback 天(跳過假日/無資料日),湊滿 days 筆即止。
    回 [{date, margin_lots, short_lots, margin_yi}]。
    """
    out: list[dict] = []
    today = datetime.now(TPE).date()
    for back in range(lookback):
        if len(out) >= days:
            break
        ds = (today - timedelta(days=back)).strftime("%Y%m%d")
        url = f"{RWD}?response=json&date={ds}&selectType=MS"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 — 暫時性失敗,跳過該日
            time.sleep(1)
            continue
        if j.get("stat") != "OK":
            continue
        tables = j.get("tables") or []
        if not tables or not tables[0].get("data") or len(tables[0]["data"]) < 3:
            continue
        data = tables[0]["data"]
        out.append({
            "date": ds,
            "margin_lots": _num(data[0][_BAL]),   # 融資餘額(張)
            "short_lots": _num(data[1][_BAL]),    # 融券餘額(張)
            "margin_yi": round(_num(data[2][_BAL]) / 1e5, 1),  # 融資金額(億元)
        })
    out.reverse()  # 舊 → 新,方便畫趨勢
    return out
