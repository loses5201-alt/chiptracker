"""
台指期貨籌碼(TAIFEX 期交所)— 大盤多空風向。

資料來源:期交所 OpenAPI(臺灣期貨交易所,免金鑰)
  https://openapi.taifex.com.tw/v1
  /MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate
      三大法人各期貨契約未平倉(我們取「臺股期貨」=大台 TX)
  /PutCallRatio
      臺指選擇權 Put/Call 比

為什麼看這個?
  個股籌碼看「誰在買哪檔」,期貨籌碼看「大戶對整個大盤的多空押注」。
  外資台指期未平倉淨額是台股最重要的多空風向球:
    淨多單(正)= 外資押大盤漲、淨空單(負)= 押大盤跌。
  Put/Call 未平倉比(PutOI/CallOI)是選擇權情緒:偏高常代表低點支撐(避險買 Put 過多)。
  → 個股潛伏/做空訊號,搭配大盤期貨風向一起看,勝率更高。

⚠️ OpenAPI 只給最新一日 → 趨勢(近 N 日)由 build 每日累積 data/futures.json(同 history.json)。
⚠️ 大 CSV/偶發連線問題比照既有 source 退避重試。
"""
from __future__ import annotations
import json
import time
import urllib.request

BASE = "https://openapi.taifex.com.tw/v1"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TX = "臺股期貨"   # 大台指(本國最具代表性的大盤期貨)
# 三大法人 Item 名稱(期交所固定用字)
_FOREIGN, _TRUST, _DEALER = "外資及陸資", "投信", "自營商"


def _num(s) -> int:
    try:
        return int(str(s).replace(",", "").strip() or 0)
    except (ValueError, TypeError):
        return 0


def _fnum(s) -> float:
    try:
        return float(str(s).replace(",", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


def _get(path: str, tries: int = 4):
    last = "(none)"
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + path, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 — 退避重試
            last = str(e)
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"TAIFEX {path} 連 {tries} 次失敗:{last}")


def fetch() -> dict:
    """
    回傳當日台指期三大法人未平倉淨額(口) + P/C 比。
    {date, tx:{foreign,trust,dealer,foreign_day,trust_day,dealer_day}, pc:{oi_ratio,vol_ratio}}
    """
    rows = _get("/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate")
    tx = {r.get("Item"): r for r in rows if r.get("ContractCode") == TX}
    date = next((r.get("Date") for r in rows if r.get("ContractCode") == TX), "")

    def net_oi(item: str) -> int:
        return _num((tx.get(item) or {}).get("OpenInterest(Net)"))

    def net_day(item: str) -> int:
        return _num((tx.get(item) or {}).get("TradingVolume(Net)"))

    pc_rows = _get("/PutCallRatio")
    pc = pc_rows[0] if pc_rows else {}

    return {
        "date": date or _num(pc.get("Date")) and str(pc.get("Date")) or "",
        "tx": {
            "foreign": net_oi(_FOREIGN), "trust": net_oi(_TRUST), "dealer": net_oi(_DEALER),
            "foreign_day": net_day(_FOREIGN), "trust_day": net_day(_TRUST), "dealer_day": net_day(_DEALER),
        },
        "pc": {
            "oi_ratio": _fnum(pc.get("PutCallOIRatio%")),
            "vol_ratio": _fnum(pc.get("PutCallVolumeRatio%")),
        },
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
