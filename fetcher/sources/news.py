"""
題材新聞來源 — Google News RSS(免金鑰),用於「題材面」。

邏輯:對每個題材的關鍵字搜尋新聞,算「近期熱度」(近 3 日新聞則數),
      熱度高 = 市場正在炒作該題材 → 該題材個股加分,並在卡片顯示最新新聞標題。
      這正是「黃仁勳來台 → AI 題材發酵」這類消息面的自動偵測。

並行抓取(ThreadPoolExecutor,純 stdlib);任何題材失敗都不影響其他。
"""
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

RSS = "https://news.google.com/rss/search"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TPE = timezone(timedelta(hours=8))
RECENT_DAYS = 3  # 「近期」定義:幾天內的新聞算熱度


def _fetch_topic(item: tuple[str, str]) -> tuple[str, dict]:
    """抓單一題材新聞,回 (題材, {heat, titles})。heat=近 RECENT_DAYS 日則數。"""
    name, kw = item
    try:
        q = urllib.parse.quote(f"{kw} 股")
        url = f"{RSS}?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=20) as r:
            raw = r.read().decode("utf-8")
    except Exception:  # noqa: BLE001
        return name, {"heat": 0, "titles": []}

    # 逐則解析 <item> 內的 title 與 pubDate
    items = re.findall(r"<item>(.*?)</item>", raw, re.S)
    now = datetime.now(timezone.utc)
    recent, titles = 0, []
    for it in items:
        tm = re.search(r"<title>(.*?)</title>", it, re.S)
        dm = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        title = (tm.group(1).strip() if tm else "").replace("<![CDATA[", "").replace("]]>", "")
        is_recent = False
        if dm:
            try:
                pub = parsedate_to_datetime(dm.group(1).strip())
                if (now - pub) <= timedelta(days=RECENT_DAYS):
                    is_recent = True
            except Exception:  # noqa: BLE001
                pass
        if is_recent:
            recent += 1
        if title and len(titles) < 5:
            titles.append(title)
    return name, {"heat": recent, "titles": titles}


class NewsSource:
    name = "news"

    def topic_heat(self, topics: dict[str, str], workers: int = 8) -> dict[str, dict]:
        """
        topics = {題材名: 關鍵字}。回 {題材: {heat, titles}}。
        heat 為近 RECENT_DAYS 日新聞則數(市場熱度代理指標)。
        """
        out: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for name, data in ex.map(_fetch_topic, list(topics.items())):
                out[name] = data
        return out
