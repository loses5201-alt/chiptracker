"""
基本面資料來源 — 上市公司月營收(年增率 YoY)。

來源:證交所 OpenAPI /opendata/t187ap05_L(上市公司每月營業收入彙總表),免金鑰。
短線意義:月營收是「最即時」的成長訊號(每月 10 號前出上月),YoY 正成長代表公司
          基本面有撐,搭配籌碼動能更不易追到基本面崩壞的股票。
"""
import json
import urllib.request

URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _num(s) -> float:
    if s is None:
        return 0.0
    try:
        cleaned = str(s).replace(",", "").replace("%", "").strip()
        return float(cleaned) if cleaned and cleaned not in ("不適用", "--") else 0.0
    except ValueError:
        return 0.0


class FundamentalsSource:
    name = "fundamentals"

    def revenue(self) -> dict[str, dict]:
        """
        回傳 {code: {yoy, mom, industry, month}}。
        yoy = 營收去年同月增減(%);同一公司若出現多筆,取資料年月最新者。
        """
        req = urllib.request.Request(URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = json.loads(r.read().decode("utf-8"))

        out: dict[str, dict] = {}
        for row in rows:
            code = (row.get("公司代號") or "").strip()
            if not code:
                continue
            month = (row.get("資料年月") or "").strip()
            # 同一檔取最新月份
            if code in out and month <= out[code]["month"]:
                continue
            out[code] = {
                "yoy": _num(row.get("營業收入-去年同月增減(%)")),
                "mom": _num(row.get("營業收入-上月比較增減(%)")),
                "industry": (row.get("產業別") or "").strip(),
                "month": month,
            }
        return out
