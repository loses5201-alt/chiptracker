"""
證交所(TWSE)資料來源 — 上市股票。

資料來源(皆為證交所官方、免金鑰、免費、合規):
  價量   OpenAPI  /exchangeReport/STOCK_DAY_ALL   (最近交易日快照)
  融資券 OpenAPI  /exchangeReport/MI_MARGN        (最近交易日快照)
  法人   RWD JSON /rwd/zh/fund/T86                (需 date,個股別三大法人買賣超)

為什麼法人走 RWD 而不走 OpenAPI?
  證交所 v1 OpenAPI 的 T86(個股別三大法人)已下架(回 404),
  但舊版 RWD data service 仍提供同一份資料,且能指定交易日 → 改用之。
歷史(20 日均線、位置)由 build.py 每日累積而成。
"""
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from .base import BaseSource

OPENAPI = "https://openapi.twse.com.tw/v1"
RWD = "https://www.twse.com.tw/rwd/zh"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Referer": "https://www.twse.com.tw/zh/trading/foreign/t86.html",
}
TPE = timezone(timedelta(hours=8))

# RWD T86 data 為陣列的陣列,欄位固定順序(實測自 fields):
#   0 證券代號 / 4 外陸資買賣超 / 7 外資自營商買賣超 / 10 投信買賣超
#   11 自營商買賣超(合計) / 18 三大法人買賣超
_I_CODE, _I_FOREIGN, _I_FDEALER, _I_TRUST, _I_DEALER, _I_TOTAL = 0, 4, 7, 10, 11, 18


def _num(s) -> float:
    """證交所數字常帶逗號、或為 '--'/空字串,統一轉 float;失敗回 0。"""
    if s is None:
        return 0.0
    try:
        cleaned = str(s).replace(",", "").replace("--", "").strip()
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _openapi(path: str, tries: int = 4):
    """打 OpenAPI 端點,回傳 list。偶發 302→404.html 屬暫時性,退避重試。"""
    url = f"{OPENAPI}{path}"
    last = "(none)"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as r:
                if not r.geturl().rstrip("/").endswith(path.rstrip("/")):
                    raise ValueError("redirected away (暫時性 302)")
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 — 任何錯誤都重試
            last = str(e)
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"OpenAPI {path} 連 {tries} 次失敗:{last}")


class TwseSource(BaseSource):
    name = "twse"

    def __init__(self):
        # institutional() 會把實際抓到的交易日寫在這,供 build.py 當累積去重依據
        self.trading_date: str | None = None

    def daily_quotes(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for row in _openapi("/exchangeReport/STOCK_DAY_ALL"):
            code = row.get("Code")
            if not code:
                continue
            out[code] = {
                "name": (row.get("Name") or "").strip(),
                "open": _num(row.get("OpeningPrice")),
                "high": _num(row.get("HighestPrice")),
                "low": _num(row.get("LowestPrice")),
                "close": _num(row.get("ClosingPrice")),
                "volume": _num(row.get("TradeVolume")),  # 單位:股
                "change": _num(row.get("Change")),       # 當日漲跌價(供大盤漲跌家數)
            }
        return out

    def institutional(self) -> dict[str, dict]:
        """
        三大法人買賣超(單位:股),走 RWD T86。
        從今天往前找最多 8 天,取第一個有資料的交易日(避開週末/隔日尚未公布)。
        每天最多重試數次以避開偶發的 very_busy 限流。
        """
        out: dict[str, dict] = {}
        today = datetime.now(TPE).date()
        data = None
        for back in range(8):
            ds = (today - timedelta(days=back)).strftime("%Y%m%d")
            url = f"{RWD}/fund/T86?response=json&date={ds}&selectType=ALL"
            for attempt in range(3):
                try:
                    req = urllib.request.Request(url, headers=HEADERS)
                    with urllib.request.urlopen(req, timeout=30) as r:
                        j = json.loads(r.read().decode("utf-8"))
                    if j.get("stat") == "OK" and j.get("data"):
                        self.trading_date = ds
                        data = j["data"]
                        break
                    # stat 非 OK(假日無資料)→ 不重試,直接換前一天
                    break
                except Exception:  # noqa: BLE001 — 限流/逾時 → 退避重試
                    time.sleep(2 * (attempt + 1))
            if data:
                break
        if not data:
            return out
        for row in data:
            if len(row) <= _I_TOTAL:
                continue
            code = str(row[_I_CODE]).strip()
            if not code:
                continue
            out[code] = {
                "foreign": _num(row[_I_FOREIGN]) + _num(row[_I_FDEALER]),
                "trust": _num(row[_I_TRUST]),
                "dealer": _num(row[_I_DEALER]),
                "total": _num(row[_I_TOTAL]),
            }
        return out

    def margin(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for row in _openapi("/exchangeReport/MI_MARGN"):
            code = row.get("股票代號")
            if not code:
                continue
            out[code] = {
                "margin_bal": _num(row.get("融資今日餘額")),
                "margin_prev": _num(row.get("融資前日餘額")),
                "short_bal": _num(row.get("融券今日餘額")),
                "short_prev": _num(row.get("融券前日餘額")),
            }
        return out
