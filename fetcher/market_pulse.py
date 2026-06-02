"""
大盤環境溫度計 — 對「全市場」資料做彙整,產出今日盤勢概況。

用途:選股前先看市場是順風還逆風。個股再好,大盤大跌時短線也難做。
輸入:全市場 quotes / margin(上市+上櫃)+ 題材熱度/動能 + 當日三大法人(BFI82U 官方金額)。
輸出:寫進 meta.json 的 market_pulse,前端「今日盤勢」面板顯示。

各指標說明:
  漲跌家數   依當日漲跌價 change 計;紅多(漲>跌)=偏多頭氣氛
  三大法人   用 BFI82U 官方買賣金額(億元)。比舊版「Σ個股淨股數×收盤」估算準確
             (實測投信方向都可能相反),且可回填趨勢(見 sources/inst_history.py)
  融資增減   全市場融資餘額變化(張)+ 融資增加家數
  強勢題材   題材熱度(新聞則數)+ 海外同業動能 綜合排序前三
  綜合判讀   上漲家數佔比 + 法人是否站買方 → 順風 / 中性 / 逆風
"""
from __future__ import annotations


def _topic_score(name: str, heat: dict, mom: dict) -> float:
    """題材綜合分:新聞熱度×2 + 海外動能×1.5(與 sectors.best_topic_for 同精神)。"""
    h = heat.get(name, {}).get("heat", 0)
    m = mom.get(name, 0)
    return h * 2 + m * 1.5


def compute(quotes: dict, margin: dict, heat: dict, mom: dict, inst_today: dict | None = None) -> dict:
    inst_today = inst_today or {}

    # 1. 漲跌家數(只計有成交的個股)
    up = down = flat = 0
    for q in quotes.values():
        if q.get("close", 0) <= 0:
            continue
        ch = q.get("change", 0)
        if ch > 0:
            up += 1
        elif ch < 0:
            down += 1
        else:
            flat += 1

    # 2. 三大法人買賣超(億元,BFI82U 官方金額)
    foreign = inst_today.get("foreign_yi", 0.0)
    trust = inst_today.get("trust_yi", 0.0)
    dealer = inst_today.get("dealer_yi", 0.0)
    inst_total = round(foreign + trust + dealer, 1)

    # 3. 融資餘額變化(張)與融資增加家數
    mg_chg = 0.0
    mg_up = 0
    for m in margin.values():
        d = m.get("margin_bal", 0) - m.get("margin_prev", 0)
        mg_chg += d
        if d > 0:
            mg_up += 1

    # 4. 強勢題材前三
    ranked = sorted(heat.keys(), key=lambda n: _topic_score(n, heat, mom), reverse=True)
    hot_topics = [
        {"name": n, "heat": heat.get(n, {}).get("heat", 0), "mom": round(mom.get(n, 0), 1)}
        for n in ranked[:3]
    ]

    # 5. 綜合判讀:漲跌廣度 + 法人方向
    breadth = up / (up + down) if (up + down) else 0.5
    if breadth >= 0.6 and inst_total > 0:
        mood, mood_txt = "tailwind", "順風"
    elif breadth <= 0.4 and inst_total < 0:
        mood, mood_txt = "headwind", "逆風"
    else:
        mood, mood_txt = "neutral", "中性"

    return {
        "advancers": up, "decliners": down, "unchanged": flat,
        "breadth_pct": round(breadth * 100, 1),
        "inst_foreign": foreign, "inst_trust": trust,
        "inst_dealer": dealer, "inst_total": inst_total,
        "margin_chg_lots": round(mg_chg, 0),
        "margin_up_count": mg_up,
        "hot_topics": hot_topics,
        "mood": mood, "mood_text": mood_txt,
    }
