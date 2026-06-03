"""
台股歷史價量來源 — Yahoo Finance,用於技術面與回測。

為什麼需要:證交所/櫃買 OpenAPI 只給「當日」,技術指標與回測都需要連續多日。
來源:query1.finance.yahoo.com/v8/finance/chart/<代號><後綴>,免金鑰。
  上市(twse)後綴 .TW;上櫃(tpex)後綴 .TWO  ← 兩者不同,用錯會抓不到。
效能:用 ThreadPoolExecutor 並行抓(純 stdlib),只對「候選股」抓,不打全市場。

回傳含 dates(YYYYMMDD),讓回測能用真實日期對齊推薦日,而非用價格近似(較準)。

market 參數:
  "twse" → 只試 .TW   "tpex" → 只試 .TWO
  None(未知,例如舊快照無市場別)→ 先 .TW 再 .TWO,兩者都試
"""
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TPE = timezone(timedelta(hours=8))


def _suffixes(market: str | None) -> list[str]:
    if market == "tpex":
        return [".TWO"]
    if market == "twse":
        return [".TW"]
    return [".TW", ".TWO"]


def _parse(j: dict) -> dict | None:
    """把 Yahoo chart JSON 解析成 {dates, closes, vols};資料不足回 None。"""
    result = j["chart"]["result"][0]
    ts = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    dates, closes, vols = [], [], []
    for t, c, v in zip(ts, quote["close"], quote["volume"]):
        if c is None:
            continue
        dates.append(datetime.fromtimestamp(t, TPE).strftime("%Y%m%d"))
        closes.append(round(float(c), 2))
        vols.append(float(v or 0))
    return {"dates": dates, "closes": closes, "vols": vols} if len(closes) >= 2 else None


def _fetch_one(arg, rng: str = "3mo") -> tuple[str, dict | None]:
    """
    抓單檔台股日線,回 (code, {dates, closes, vols});失敗回 (code, None)。
    arg 可為 code 字串,或 (code, market) tuple(供指定上市/上櫃後綴)。
    rng:Yahoo range 參數,技術面用 "3mo",回測需更長可傳 "6mo"/"1y"。
    """
    code, market = arg if isinstance(arg, tuple) else (arg, None)
    for sfx in _suffixes(market):
        try:
            url = f"{BASE}{code}{sfx}?range={rng}&interval=1d"
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15) as r:
                j = json.loads(r.read().decode("utf-8"))
            data = _parse(j)
            if data:
                return code, data
        except Exception:  # noqa: BLE001 — 換下一個後綴或放棄
            continue
    return code, None


def fetch_symbol(symbol: str, rng: str = "6mo") -> dict | None:
    """
    抓任意 Yahoo symbol 的日線(原樣,不加 .TW/.TWO 後綴),回 {dates, closes, vols}。
    供大盤指數使用,例如 ^TWII(加權指數),用於回測算超額報酬(alpha)。
    """
    try:
        url = f"{BASE}{symbol}?range={rng}&interval=1d"
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15) as r:
            j = json.loads(r.read().decode("utf-8"))
        return _parse(j)
    except Exception:  # noqa: BLE001
        return None


class PriceHistorySource:
    name = "yahoo_history"

    def fetch(self, items: list, workers: int = 10, rng: str = "3mo") -> dict[str, dict]:
        """
        並行抓多檔,回 {code: {dates, closes, vols}}(抓不到的略過)。
        items 可為 list[str] 或 list[(code, market)];rng 指定歷史長度(回測用 1y)。
        """
        out: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for code, data in ex.map(lambda a: _fetch_one(a, rng), items):
                if data:
                    out[code] = data
        return out
