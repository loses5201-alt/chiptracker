"""
題材對照表 — 連結「題材 ↔ 台股個股 ↔ 海外同業 ↔ 新聞關鍵字」。

這是「國際連動」與「題材新聞」共用的核心。維護這一份表,三個面向都受益:
  - 國際連動:海外同業漲 → 表中對應台股加分
  - 題材新聞:用 kw 關鍵字搜新聞,算題材熱度
  - 題材標籤:個股卡片顯示所屬熱門題材

⚠️ 需人工維護。要新增題材/個股,直接改 TOPICS dict,不必動主程式。
   海外代碼用 Yahoo 格式(美股直接代號、韓股 .KS、日股 .T、台股 .TW)。

2026-06 擴充背景:weight_review 實測 s4 國際/s5 題材填充率僅 40%、discrim=0 —
入選股幾乎都不在表上、半數題材又缺海外對照(動能恆 0)。本版把覆蓋從約 50 檔
拉到 100+ 檔、每個題材都補上海外同業,讓這兩個面向真正進入排名。
"""

TOPICS: dict[str, dict] = {
    "記憶體": {
        "kw": "記憶體 DRAM",
        "tw": ["2408", "3006", "8299", "2344", "2337", "4967", "5289", "2451",
               "3260", "8271"],
        "oversea": ["MU", "000660.KS", "WDC"],
    },
    "AI伺服器": {
        "kw": "AI伺服器",
        "tw": ["2330", "2317", "3231", "2376", "2356", "3017", "6669", "2382",
               "2308", "2301", "3706", "8210"],
        "oversea": ["NVDA", "SMCI", "AMD", "DELL"],
    },
    "晶圓代工": {
        "kw": "晶圓代工 先進製程",
        "tw": ["2330", "2303", "5347", "6770"],
        "oversea": ["TSM", "GFS"],
    },
    "IC設計": {
        "kw": "IC設計 晶片",
        "tw": ["2454", "3034", "3443", "6415", "8016", "3661"],
        "oversea": ["QCOM", "AVGO"],
    },
    "CoWoS先進封裝": {
        "kw": "CoWoS 先進封裝",
        "tw": ["3711", "6488", "3034", "3661", "2449", "6239", "6147"],
        "oversea": ["TSM", "ASML", "AMAT"],
    },
    "矽光子CPO": {
        "kw": "矽光子 CPO 光通訊",
        "tw": ["4979", "3163", "4977", "3450", "6510", "3081"],
        "oversea": ["COHR", "LITE"],
    },
    "散熱": {
        "kw": "散熱 液冷",
        "tw": ["3017", "3324", "8210", "6230", "3653", "2421"],
        "oversea": ["VRT"],
    },
    "機器人": {
        "kw": "機器人 人形機器人",
        "tw": ["2049", "1590", "2059", "1503", "1597", "4583"],
        "oversea": ["TER", "6954.T", "6506.T"],
    },
    "重電綠能": {
        "kw": "重電 電網",
        "tw": ["1503", "1504", "1513", "1519", "1514", "1605", "1609"],
        "oversea": ["GEV", "ETN"],
    },
    "軍工航太": {
        # 原表誤植 5530(龍巖,殯葬業)→ 移除,補亞航/寶一/神基
        "kw": "軍工 國防",
        "tw": ["2634", "2645", "8033", "2630", "8222", "3005"],
        "oversea": ["LMT", "RTX"],
    },
    "PCB": {
        "kw": "PCB 載板",
        "tw": ["3037", "2368", "3189", "8046", "6213", "2313", "5469"],
        "oversea": ["4062.T", "TTMI"],
    },
    "矽智財IP": {
        "kw": "矽智財 IP 設計",
        "tw": ["3443", "6533", "6643", "3035"],
        "oversea": ["ARM", "SNPS", "CDNS"],
    },
    "被動元件": {
        "kw": "被動元件 MLCC",
        "tw": ["2327", "2492", "2375", "6173"],
        "oversea": ["6981.T", "6762.T"],
    },
    "蘋果供應鏈": {
        "kw": "蘋果 iPhone 供應鏈",
        "tw": ["2317", "2382", "3008", "4938", "3406", "2354", "6456"],
        "oversea": ["AAPL"],
    },
    "低軌衛星": {
        "kw": "低軌衛星 衛星",
        "tw": ["2368", "3704", "6285", "2419", "3491", "4906"],
        "oversea": ["ASTS", "RKLB"],
    },
    "航運": {
        "kw": "航運 貨櫃 運價",
        "tw": ["2603", "2609", "2615", "2606", "2637"],
        "oversea": ["ZIM"],
    },
    "生技新藥": {
        "kw": "生技 新藥",
        "tw": ["6446", "1795", "6472", "4174", "4743"],
        "oversea": ["XBI"],
    },
}


def all_topics() -> list[str]:
    return list(TOPICS.keys())


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
    """依海外股價漲幅,算每個題材的「海外動能」(該題材海外標的平均漲幅%)。"""
    out: dict[str, float] = {}
    for name, t in TOPICS.items():
        vals = [prices[s] for s in t["oversea"] if s in prices]
        if vals:
            out[name] = round(sum(vals) / len(vals), 2)
    return out


def best_topic_for(code: str, topic_mom: dict[str, float], topic_heat: dict | None = None) -> tuple[str | None, float]:
    """
    某台股所屬題材中,挑「海外動能 + 新聞熱度」綜合最強的那個。
    回 (題材名, 海外動能%)。無所屬題材回 (None, 0)。
    """
    topics = code_topics(code)
    if not topics:
        return None, 0.0
    heat = topic_heat or {}

    def rank(t: str) -> float:
        return topic_mom.get(t, 0.0) * 1.5 + heat.get(t, {}).get("heat", 0) * 2

    best = max(topics, key=rank)
    return best, topic_mom.get(best, 0.0)
