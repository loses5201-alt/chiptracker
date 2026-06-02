"""
大盤三大法人買賣金額歷史 — 外資 / 投信 / 自營的「買賣超趨勢」。

為什麼:單日法人數字看不出意義,要看「連續買/賣超、近期趨勢」。
證交所 BFI82U(三大法人買賣金額統計)可指定日期,故能一次回填近 N 交易日,立即有趨勢。
順帶比 market_pulse 原本「Σ個股淨股數×收盤」的估算更準(這是官方買賣金額)。

來源:www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate=YYYYMMDD&type=day
欄位:單位名稱 / 買進金額 / 賣出金額 / 買賣差額(元)
單位名稱含:自營商(自行買賣)、自營商(避險)、投信、外資及陸資(不含外資自營商)、外資自營商
歸併(與 T86 / market_pulse 的三大法人定義一致):
  外資 = 含「外資」的列(外資及陸資 + 外資自營商)
  投信 = 含「投信」的列
  自營 = 含「自營商」但不含「外資」的列(自行買賣 + 避險)
單位:元 → 億元。
"""
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

RWD = "https://www.twse.com.tw/rwd/zh/fund/BFI82U"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json",
           "Referer": "https://www.twse.com.tw/"}
TPE = timezone(timedelta(hours=8))
_DIFF = 3  # 「買賣差額」欄位 index


def _num(s) -> float:
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _one_day(ds: str) -> dict | None:
    """抓單一交易日大盤三大法人買賣差額(億元);非交易日/失敗回 None。"""
    url = f"{RWD}?response=json&dayDate={ds}&type=day"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — 暫時性失敗,交由呼叫端跳過
        return None
    if j.get("stat") != "OK" or not j.get("data"):
        return None
    foreign = trust = dealer = 0.0
    for row in j["data"]:
        name = str(row[0])
        if "合計" in name:  # 跳過彙總列,避免三大法人重複計入
            continue
        diff = _num(row[_DIFF])
        if "外資" in name:
            foreign += diff
        elif "投信" in name:
            trust += diff
        elif "自營商" in name:
            dealer += diff
    e = lambda x: round(x / 1e8, 1)  # 元 → 億元
    return {"date": ds, "foreign_yi": e(foreign), "trust_yi": e(trust), "dealer_yi": e(dealer)}


def fetch_trend(days: int = 10, lookback: int = 24) -> list[dict]:
    """
    回近 days 個交易日的大盤三大法人買賣超(億元),舊→新排序。
    從今天往前掃最多 lookback 天(跳過假日),湊滿 days 筆即止。
    回 [{date, foreign_yi, trust_yi, dealer_yi}]。
    """
    out: list[dict] = []
    today = datetime.now(TPE).date()
    for back in range(lookback):
        if len(out) >= days:
            break
        ds = (today - timedelta(days=back)).strftime("%Y%m%d")
        rec = _one_day(ds)
        if rec:
            out.append(rec)
        else:
            time.sleep(0.3)
    out.reverse()
    return out
