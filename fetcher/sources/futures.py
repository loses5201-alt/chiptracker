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
from collections import defaultdict

BASE = "https://openapi.taifex.com.tw/v1"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TX = "臺股期貨"     # 大台指(本國最具代表性的大盤期貨)
MTX_NAME = "小型臺指期貨"   # 小台(散戶愛玩,算散戶多空比用)
SSF_NAME = "股票期貨"       # 個股期貨整體
MTX_CODE = "MTX"   # 小台在每日行情/大額交易人的契約代號
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


def _inst_net(rows: list, contract_name: str) -> dict:
    """某契約三大法人未平倉淨額(口)。回 {foreign,trust,dealer}。"""
    by = {r.get("Item"): r for r in rows if r.get("ContractCode") == contract_name}
    return {
        "foreign": _num((by.get(_FOREIGN) or {}).get("OpenInterest(Net)")),
        "trust": _num((by.get(_TRUST) or {}).get("OpenInterest(Net)")),
        "dealer": _num((by.get(_DEALER) or {}).get("OpenInterest(Net)")),
    }


def fetch() -> dict:
    """
    回傳當日期貨籌碼總覽:
      tx     臺股期貨三大法人未平倉淨額 + 當日增減
      pc     臺指選擇權 P/C 比
      retail 散戶多空比(小台:-法人小台淨/小台總OI)— 反指標
      big5   前五大特定法人台指期淨部位(大額交易人)— 外資主力多空
      ssf    法人個股期貨整體淨 + 個股期貨未平倉前十大(含股名)
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

    # 散戶多空比(小台):散戶淨 ≈ -法人淨;比 = -法人小台淨 / 小台總未平倉 × 100。正=散戶偏多(反指偏空)
    mtx_inst = _inst_net(rows, MTX_NAME)
    mtx_inst_net = mtx_inst["foreign"] + mtx_inst["trust"] + mtx_inst["dealer"]
    fut_report = _get("/DailyMarketReportFut")
    mtx_oi = sum(_num(r.get("OpenInterest")) for r in fut_report if r.get("Contract") == MTX_CODE)
    retail_ratio = round(-mtx_inst_net / mtx_oi * 100, 1) if mtx_oi else 0.0

    # 前五大特定法人台指期淨(大額交易人:TX、全月份合計 999912、特定法人 TypeOfTraders=1)
    lt = _get("/OpenInterestOfLargeTradersFutures")
    b5 = next((r for r in lt if r.get("Contract") == "TX"
               and r.get("SettlementMonth") == "999912" and r.get("TypeOfTraders") == "1"), {})
    big5_net = _num(b5.get("Top5Buy")) - _num(b5.get("Top5Sell"))

    # 法人個股期貨整體淨 + 個股期貨未平倉前十大(DailyMarketReportFut OI 依契約加總 + SSFLists 對股名)
    ssf_net = _inst_net(rows, SSF_NAME)
    ssf_map = {r.get("Contract"): r for r in _get("/SSFLists")}
    # 依「股票代號」加總(同一檔可能有大型/小型多個期貨契約 → 合併,避免同股重複出現)
    by_stock: dict[str, dict] = {}
    for r in fut_report:
        m = ssf_map.get(r.get("Contract"))
        if m:
            sc = m.get("StockCode")
            e = by_stock.setdefault(sc, {"name": m.get("StockName"), "oi": 0})
            e["oi"] += _num(r.get("OpenInterest"))
    ssf_top = [{"code": sc, "name": v["name"], "oi": v["oi"]}
               for sc, v in sorted(by_stock.items(), key=lambda x: x[1]["oi"], reverse=True)[:10]]

    return {
        "date": date or (str(pc.get("Date")) if pc.get("Date") else ""),
        "tx": {
            "foreign": net_oi(_FOREIGN), "trust": net_oi(_TRUST), "dealer": net_oi(_DEALER),
            "foreign_day": net_day(_FOREIGN), "trust_day": net_day(_TRUST), "dealer_day": net_day(_DEALER),
        },
        "pc": {
            "oi_ratio": _fnum(pc.get("PutCallOIRatio%")),
            "vol_ratio": _fnum(pc.get("PutCallVolumeRatio%")),
        },
        "retail": {"ratio": retail_ratio, "mtx_oi": mtx_oi, "inst_net": mtx_inst_net},
        "big5": {"tx_net": big5_net, "market_oi": _num(b5.get("OIOfMarket"))},
        "ssf": {"foreign": ssf_net["foreign"], "trust": ssf_net["trust"], "dealer": ssf_net["dealer"],
                "top": ssf_top},
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
