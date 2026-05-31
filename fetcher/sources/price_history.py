"""
台股歷史價量來源 — Yahoo Finance,用於技術面(均線/RSI/區間位置)。

為什麼需要:證交所 OpenAPI 只給「當日」,技術指標需要連續多日。原本靠每日累積要等
20 個交易日才準;改用 Yahoo 一次回補近 3 個月,技術面立刻有真值。

來源:query1.finance.yahoo.com/v8/finance/chart/<代號>.TW(上市加 .TW),免金鑰。
效能:用 ThreadPoolExecutor 並行抓(純 stdlib),只對「候選股」抓,不打全市場。
"""
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _fetch_one(code: str) -> tuple[str, dict | None]:
    """抓單檔台股近 3 月日線,回 (code, {closes, vols});失敗回 (code, None)。"""
    try:
        url = f"{BASE}{code}.TW?range=3mo&interval=1d"
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15) as r:
            j = json.loads(r.read().decode("utf-8"))
        result = j["chart"]["result"][0]
        quote = result["indicators"]["quote"][0]
        closes, vols = [], []
        for c, v in zip(quote["close"], quote["volume"]):
            if c is None:
                continue
            closes.append(round(float(c), 2))
            vols.append(float(v or 0))
        if len(closes) < 2:
            return code, None
        return code, {"closes": closes, "vols": vols}
    except Exception:  # noqa: BLE001 — 單檔失敗不影響其他
        return code, None


class PriceHistorySource:
    name = "yahoo_history"

    def fetch(self, codes: list[str], workers: int = 10) -> dict[str, dict]:
        """並行抓多檔,回 {code: {closes, vols}}(抓不到的略過)。"""
        out: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for code, data in ex.map(_fetch_one, codes):
                if data:
                    out[code] = data
        return out
