"""
櫃買中心(TPEX)資料來源 — 上櫃股票。

與 TwseSource 完全對等,回傳值結構一致(以股票代號為 key),
build.py 的 _merge() 會自動把上櫃股票與上市股票合併納入評分,主程式不必改。

資料來源(皆為櫃買官方 OpenAPI、免金鑰、免費、合規):
  價量   /tpex_mainboard_daily_close_quotes   (上櫃個股當日收盤行情)
  法人   /tpex_3insti_daily_trading           (上櫃三大法人買賣超,單位:股)
  融資券 /tpex_mainboard_margin_balance       (上櫃融資融券餘額,單位:張)

與 TWSE 的兩個關鍵差異(已在本檔吸收,不外溢到主程式):
  1. 日期是民國年(如 "1150601" = 2026/06/01),本檔轉成西元供對齊。
  2. 價量端點含大量權證/ETN(代號非 4 碼數字),只保留 4 碼純數字的上櫃普通股。

三大法人欄位語意(實測 6488 環球晶 2026/06/01 驗證恆等式 foreign+trust+dealer=total):
  foreign = 外資及陸資(不含外資自營)+ 外資自營  ← 與 TWSE 的 foreign 定義一致
  trust   = 投信   dealer = 自營商合計   total = 三大法人合計
"""
import json
import time
import urllib.request
from .base import BaseSource

OPENAPI = "https://www.tpex.org.tw/openapi/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}

# 三大法人 difference 欄位(櫃買原始 key 帶不規則空格,需逐字精確匹配)
_F_FOREIGN_EXDEALER = "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference"
_F_FOREIGN_DEALER = "ForeignDealers-Difference"
_F_TRUST = "SecuritiesInvestmentTrustCompanies-Difference"
_F_DEALER = "Dealers-Difference"
_F_TOTAL = "TotalDifference"


def _num(s) -> float:
    """櫃買數字常帶逗號、或為 '--'/'----'/空字串,統一轉 float;失敗回 0。"""
    if s is None:
        return 0.0
    try:
        cleaned = str(s).replace(",", "").replace("-", "").strip() if set(str(s)) <= set("-, ") else str(s).replace(",", "").strip()
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _roc_to_ad(roc: str) -> str:
    """民國年日期 '1150601' → 西元 '20260601'。非預期格式則原樣回傳。"""
    roc = (roc or "").strip()
    if len(roc) == 7 and roc.isdigit():
        return str(int(roc[:3]) + 1911) + roc[3:]
    return roc


def _is_common_stock(code: str) -> bool:
    """只認 4 碼純數字的上櫃普通股,濾掉權證(6碼英數)、ETN 等。"""
    return len(code) == 4 and code.isdigit()


def _openapi(path: str, tries: int = 4) -> list:
    """
    打櫃買 OpenAPI 並回傳 list。
    價量端點回應大(~4MB),雲端偶發 IncompleteRead(連線被截斷)→ 退避重試;
    timeout 拉長到 60 秒,給大回應足夠傳輸時間。
    """
    last = "(none)"
    for i in range(tries):
        try:
            req = urllib.request.Request(f"{OPENAPI}{path}", headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 — 含 IncompleteRead/限流,退避重試
            last = str(e)
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"TPEX OpenAPI {path} 連 {tries} 次失敗:{last}")


class TpexSource(BaseSource):
    name = "tpex"

    def __init__(self):
        # 記下價量端點回報的交易日(西元),供 build/validate 與 TWSE 對齊
        self.trading_date: str | None = None

    def daily_quotes(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for row in _openapi("/tpex_mainboard_daily_close_quotes"):
            code = str(row.get("SecuritiesCompanyCode", "")).strip()
            if not _is_common_stock(code):
                continue
            if self.trading_date is None:
                self.trading_date = _roc_to_ad(row.get("Date", ""))
            out[code] = {
                "name": (row.get("CompanyName") or "").strip(),
                "open": _num(row.get("Open")),
                "high": _num(row.get("High")),
                "low": _num(row.get("Low")),
                "close": _num(row.get("Close")),
                "volume": _num(row.get("TradingShares")),  # 單位:股
                "change": _num(row.get("Change")),         # 當日漲跌價(供大盤漲跌家數)
            }
        return out

    def institutional(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for row in _openapi("/tpex_3insti_daily_trading"):
            code = str(row.get("SecuritiesCompanyCode", "")).strip()
            if not _is_common_stock(code):
                continue
            foreign = _num(row.get(_F_FOREIGN_EXDEALER)) + _num(row.get(_F_FOREIGN_DEALER))
            out[code] = {
                "foreign": foreign,
                "trust": _num(row.get(_F_TRUST)),
                "dealer": _num(row.get(_F_DEALER)),
                "total": _num(row.get(_F_TOTAL)),
            }
        return out

    def margin(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for row in _openapi("/tpex_mainboard_margin_balance"):
            code = str(row.get("SecuritiesCompanyCode", "")).strip()
            if not _is_common_stock(code):
                continue
            out[code] = {
                "margin_bal": _num(row.get("MarginPurchaseBalance")),
                "margin_prev": _num(row.get("MarginPurchaseBalancePreviousDay")),
                "short_bal": _num(row.get("ShortSaleBalance")),
                "short_prev": _num(row.get("ShortSaleBalancePreviousDay")),
            }
        return out
