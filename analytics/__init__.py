"""
分析層 — 與 fetcher(撈資料)分離的第二部分。

fetcher/   負責「撈資料 + 每日評分 + 產出推薦快照」(data/daily/*.json)
analytics/ 負責「回測 + 驗證推薦的實際表現」(讀快照 → 算後續收益 → data/performance.json)

兩層唯一的介面是 data/daily/*.json 快照,徹底解耦:
改評分邏輯不影響回測,改回測方法不影響每日產出。
"""
