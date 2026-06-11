"""
券商分點(主力進出)資料來源。【預留,資料源未定】

⚠️ 重要:券商分點買賣「沒有官方免費來源」。
   可行方向:
     1. FinMind 等第三方 API 的付費/贊助方案(合規、穩定)
     2. 爬神秘金字塔 / Goodinfo(違反對方服務條款、易壞,不建議)

【2026-06-10 評估結論(Claude 盤點)】
   - TWSE/TPEX OpenAPI、data.gov.tw:皆無分點買賣明細 → 免費合規來源確認不存在
   - FinMind TaiwanStockTradingDailyReport(分點日報):「贊助會員」限定(付費),
     免費 token 拿不到;若 Noc 決定贊助,設 FINMIND_TOKEN 後在此實作即可接上
   - 替代訊號已在用:集保千張大戶(TDCC 官方,週頻)+ T86 法人連買 — 覆蓋了
     「主力吸籌」的大部分資訊量,分點屬加分項非必需
   → 【已決定 2026-06-10】不花錢:維持未啟用,主力訊號以集保大戶+法人連買為準。
     此檔保留是為了未來若有免費合規來源出現,可無痛接上。

在你決定資料源之前,這個 connector 回傳空字典,
評分時 s2(主力分點)會以「中性值」計算,並在 meta 中標記為未啟用。
等資料源確定,只要實作這支檔案,主程式即可無痛接上。
"""


class BrokerSource:
    name = "broker"
    enabled = False  # 資料源確定並實作後改成 True

    def concentration(self) -> dict[str, dict]:
        """主力分點集中度。回傳 {code: {buy_lots, sell_lots, concentration}}。"""
        return {}
