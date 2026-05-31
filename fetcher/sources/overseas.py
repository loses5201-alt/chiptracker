"""
海外同業股價來源 — 用於「國際連動」面向。

來源:Yahoo Finance chart API(query1.finance.yahoo.com/v8/finance/chart/<代碼>),免金鑰。
  美股:直接用代號(MU、NVDA);韓股:加 .KS(000660.KS,SK 海力士)。
  (原本想用 Stooq,但其免費 CSV 2026 起改需 API key,故改用 Yahoo。)
邏輯:海外同業近期上漲 → 台股同題材個股有機會連帶表現
      (例:MU/SK海力士漲 → 台廠記憶體可能跟漲)。
"""
import json
import urllib.request

BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _pct_change(symbol: str, lookback: int = 5) -> float | None:
    """抓某海外標的日線,回最近 lookback 個交易日的漲跌幅(%)。抓不到回 None。"""
    try:
        url = f"{BASE}{symbol}?range=1mo&interval=1d"
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=25) as r:
            j = json.loads(r.read().decode("utf-8"))
        result = j["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]  # 去掉停牌的 null
        if len(closes) < lookback + 1:
            return None
        old, last = closes[-(lookback + 1)], closes[-1]
        if old <= 0:
            return None
        return round((last - old) / old * 100, 2)
    except Exception:  # noqa: BLE001 — 海外源失敗不應拖垮整體
        return None


class OverseasSource:
    name = "overseas"

    def momentum(self, symbols: list[str], lookback: int = 5) -> dict[str, float]:
        """回 {symbol: 近 lookback 日漲幅%},抓不到的標的略過。"""
        out: dict[str, float] = {}
        for sym in symbols:
            pct = _pct_change(sym, lookback)
            if pct is not None:
                out[sym] = pct
        return out
