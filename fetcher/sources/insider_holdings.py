"""
董監事持股 / 設質比例(TWSE 公開資料)— 內部人風險訊號。

資料來源:證交所 OpenAPI `/opendata/t187ap11_L`(上市公司董監事持股餘額明細,免金鑰)。
每列是「一家公司的一位董監」,需依公司代號彙總。

為什麼用「設質比例」?
  董監是公司最核心的內部人。把自己的持股拿去「設質」(質押給銀行借錢)比例越高,
  代表內部人槓桿/資金壓力越大 —— 一旦股價下跌,容易被斷頭追繳、引發連鎖賣壓。
  設質比例高 = 風險旗標:做空標的加分、潛伏標的避雷(別跟著高質押的內部人埋伏)。

  設質比例 = Σ設質股數 / Σ董監目前持股 × 100(全公司董監加總)。

⚠️ 月更資料(資料年月 YYYYMM 民國),非日更 → 用於慢變的風險旗標剛好;
   不需累積(設質比例本身即可用,持股「增減」才需月累積,本期先做設質)。
⚠️ 僅上市(t187ap11_L);上櫃另有來源,暫不支援(標 None)。
"""
from __future__ import annotations
import json
import time
import urllib.request

URL = "https://openapi.twse.com.tw/v1/opendata/t187ap11_L"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _num(s) -> float:
    try:
        return float(str(s).replace(",", "").replace("%", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


def _fetch(tries: int = 4):
    last = "(none)"
    for i in range(tries):
        try:
            req = urllib.request.Request(URL, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 — 退避重試
            last = str(e)
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"董監持股 連 {tries} 次失敗:{last}")


def fetch() -> dict[str, dict]:
    """
    回傳 {code: {"pledge": 設質比例%, "shares": 董監總持股(股), "ym": 資料年月}}。
    依公司代號彙總全部董監的目前持股與設質股數。
    """
    rows = _fetch()
    agg: dict[str, dict] = {}
    for r in rows:
        code = str(r.get("公司代號", "")).strip()
        if not code:
            continue
        a = agg.setdefault(code, {"hold": 0.0, "pledge_sh": 0.0, "ym": str(r.get("資料年月", "")).strip()})
        a["hold"] += _num(r.get("目前持股"))
        a["pledge_sh"] += _num(r.get("設質股數"))
    out: dict[str, dict] = {}
    for code, a in agg.items():
        if a["hold"] <= 0:
            continue
        out[code] = {
            "pledge": round(a["pledge_sh"] / a["hold"] * 100, 1),
            "shares": a["hold"],
            "ym": a["ym"],
        }
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    data = fetch()
    print(f"公司數:{len(data)}")
    for c in ("2330", "2317", "2454", "3040"):
        print(f"  {c}: {data.get(c)}")
