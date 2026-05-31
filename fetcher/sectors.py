"""
題材對照表 — 連結「題材 ↔ 台股個股 ↔ 海外同業」。

這是「國際連動」與「題材面」共用的核心。維護這一份表,兩個面向都受益:
  - 國際連動:海外同業漲 → 表中對應台股加分
  - 題材標籤:個股卡片顯示所屬熱門題材

⚠️ 這份表需要人工維護(我先放幾個主要題材起步)。要新增題材/個股,
   直接改這個 dict 即可,不必動主程式。海外代碼用 Stooq 格式(美股 .us、韓股 .kr)。
"""

TOPICS: dict[str, dict] = {
    "記憶體": {
        "tw": ["2408", "3006", "8299", "2344", "2337", "4967"],  # 南亞科/晶豪科/群聯/華邦電/旺宏/十銓
        "oversea": ["MU", "000660.KS"],                          # 美光 / SK海力士(Yahoo 代碼)
    },
    "AI伺服器": {
        "tw": ["2330", "2317", "3231", "2376", "2356", "3017"],  # 台積電/鴻海/緯創/技嘉/英業達/奇鋐
        "oversea": ["NVDA", "SMCI", "AMD"],
    },
    "CoWoS封裝": {
        "tw": ["3711", "6488", "3081"],                          # 日月光投控/環球晶/聯亞
        "oversea": ["TSM"],
    },
    "蘋果供應鏈": {
        "tw": ["2317", "2382", "3008", "4938"],                  # 鴻海/廣達/大立光/和碩
        "oversea": ["AAPL"],
    },
}


def all_overseas_symbols() -> list[str]:
    """彙整所有題材用到的海外代碼(去重),供一次性抓取。"""
    syms: set[str] = set()
    for t in TOPICS.values():
        syms.update(t["oversea"])
    return sorted(syms)


def code_topics(code: str) -> list[str]:
    """回傳某台股代號所屬的題材清單(可能多個)。"""
    return [name for name, t in TOPICS.items() if code in t["tw"]]


def topic_overseas_momentum(prices: dict[str, float]) -> dict[str, float]:
    """
    依海外股價漲幅,算每個題材的「海外動能」(該題材所有海外標的平均漲幅%)。
    prices = {symbol: pct};某題材若無任何海外資料則不列入。
    """
    out: dict[str, float] = {}
    for name, t in TOPICS.items():
        vals = [prices[s] for s in t["oversea"] if s in prices]
        if vals:
            out[name] = round(sum(vals) / len(vals), 2)
    return out


def best_topic_for(code: str, topic_mom: dict[str, float]) -> tuple[str | None, float]:
    """
    某台股所屬題材中,挑「海外動能最強」的那個,回 (題材名, 動能%)。
    無所屬題材或無海外資料時回 (None, 0)。
    """
    topics = code_topics(code)
    best, best_mom = None, -999.0
    for t in topics:
        m = topic_mom.get(t)
        if m is not None and m > best_mom:
            best, best_mom = t, m
    if best is None:
        # 有題材但海外無資料 → 至少回題材名,動能 0
        return (topics[0] if topics else None), 0.0
    return best, best_mom
