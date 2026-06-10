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
                body = r.read().decode("utf-8").strip()
            if not body:
                raise ValueError("空回應(暫時性,退避重試)")
            return json.loads(body)
        except Exception as e:  # noqa: BLE001 — 退避重試
            last = str(e)
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"TAIFEX {path} 連 {tries} 次失敗:{last}")


def _safe(path: str, default, gap: float = 3.0):
    """
    單一端點容錯:失敗回 default,不讓一個端點拖垮整個期貨功能(validate 架構教訓)。
    端點間留 gap 秒延遲 —— TAIFEX 對短時間內密集請求會限流(實測美國 runner 連打 5 端點,
    第一個成功、後續回空);拉開間隔大幅降低被擋機率。
    """
    try:
        time.sleep(gap)
        return _get(path)
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ TAIFEX {path} 取用失敗(該區塊略過):{e}")
        return default


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
    回傳當日期貨籌碼「可靠核心」(build 在 GitHub 美國 runner 跑):
      tx      臺股期貨三大法人未平倉淨額 + 當日增減
      mtx_net 小台三大法人未平倉淨額合計(供前端算散戶多空比)
      ssf     法人個股期貨整體淨(top 由前端補)
      pc      臺指選擇權 P/C 比(小、常可取;取不到由前端補)

    ⚠️ 架構決策:TAIFEX 對美國 IP 的部分端點會間歇限流/擋掉(實測 DailyMarketReportFut/
       OpenInterestOfLargeTradersFutures/SSFLists 在雲端常回空)。這些「地理敏感」的端點
       改由「使用者瀏覽器(台灣 IP)直接抓」(TAIFEX 有開 CORS *),build 只取最穩的
       三大法人總表端點。→ 散戶多空比/前五大特定法人/個股期貨前十大 由前端 enrich。
       好處:各端點不互相影響、核心永遠在、擴充即時且不受雲端 IP 限制。
    """
    rows = _safe("/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate", None, gap=0)
    if not rows:
        raise RuntimeError("三大法人期貨主資料取用失敗")
    tx = {r.get("Item"): r for r in rows if r.get("ContractCode") == TX}
    date = next((r.get("Date") for r in rows if r.get("ContractCode") == TX), "")

    def net_oi(item: str) -> int:
        return _num((tx.get(item) or {}).get("OpenInterest(Net)"))

    def net_day(item: str) -> int:
        return _num((tx.get(item) or {}).get("TradingVolume(Net)"))

    # P/C 比(小端點,雲端常可取;取不到回 None,前端補)
    pc_rows = _safe("/PutCallRatio", None)
    pc = (pc_rows[0] if pc_rows else {}) or {}
    pc_oi = _fnum(pc.get("PutCallOIRatio%")) if pc else None
    pc_vol = _fnum(pc.get("PutCallVolumeRatio%")) if pc else None

    mtx_inst = _inst_net(rows, MTX_NAME)
    mtx_net = mtx_inst["foreign"] + mtx_inst["trust"] + mtx_inst["dealer"]
    ssf_net = _inst_net(rows, SSF_NAME)

    return {
        "date": date or (str(pc.get("Date")) if pc.get("Date") else ""),
        "tx": {
            "foreign": net_oi(_FOREIGN), "trust": net_oi(_TRUST), "dealer": net_oi(_DEALER),
            "foreign_day": net_day(_FOREIGN), "trust_day": net_day(_TRUST), "dealer_day": net_day(_DEALER),
        },
        "pc": {"oi_ratio": pc_oi, "vol_ratio": pc_vol},
        "mtx_net": mtx_net,                 # 小台三大法人淨(前端算散戶多空比用)
        "retail": None,                     # 散戶多空比 → 前端 enrich(需小台總OI)
        "big5": None,                       # 前五大特定法人 → 前端 enrich
        "ssf": {"foreign": ssf_net["foreign"], "trust": ssf_net["trust"], "dealer": ssf_net["dealer"],
                "top": []},                 # 個股期貨前十大 → 前端 enrich
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
