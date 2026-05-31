"""
台股歷史價量來源 — Yahoo Finance,用於技術面與回測。

為什麼需要:證交所 OpenAPI 只給「當日」,技術指標與回測都需要連續多日。
來源:query1.finance.yahoo.com/v8/finance/chart/<代號>.TW(上市加 .TW),免金鑰。
效能:用 ThreadPoolExecutor 並行抓(純 stdlib),只對「候選股」抓,不打全市場。

回傳含 dates(YYYYMMDD),讓回測能用真實日期對齊推薦日,而非用價格近似(較準)。
"""
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TPE = timezone(timedelta(hours=8))


def _fetch_one(code: str, rng: str = "3mo") -> tuple[str, dict | None]:
    """
    抓單檔台股日線,回 (code, {dates, closes, vols});失敗回 (code, None)。
    rng:Yahoo range 參數,技術面用 "3mo",回測需更長可傳 "6mo"/"1y"。
    dates 為 YYYYMMDD 字串,與 closes/vols 索引對齊。
    """
    try:
        url = f"{BASE}{code}.TW?range={rng}&interval=1d"
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15) as r:
            j = json.loads(r.read().decode("utf-8"))
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
        if len(closes) < 2:
            return code, None
        return code, {"dates": dates, "closes": closes, "vols": vols}
    except Exception:  # noqa: BLE001 — 單檔失敗不影響其他
        return code, None


class PriceHistorySource:
    name = "yahoo_history"

    def fetch(self, codes: list[str], workers: int = 10) -> dict[str, dict]:
        """並行抓多檔,回 {code: {dates, closes, vols}}(抓不到的略過)。"""
        out: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for code, data in ex.map(_fetch_one, codes):
                if data:
                    out[code] = data
        return out
