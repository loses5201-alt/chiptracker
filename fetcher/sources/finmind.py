"""
主力 / 大戶籌碼來源 — FinMind(需免費 token),用於「資金面-大戶進出」。

⚠️ 為什麼需要 token:
   台灣「券商分點 / 集保大戶持股」沒有官方免費即時 API。FinMind 提供整理好的版本,
   免費方案需註冊取得 token(不花錢):
     1. 到 https://finmindtrade.com 註冊 → 會員中心取得 API token
     2. 本機:設環境變數 FINMIND_TOKEN=<你的token>
     3. 雲端:GitHub repo → Settings → Secrets and variables → Actions → New secret
            名稱 FINMIND_TOKEN,並在 daily.yml 的 Build 步驟加 env 傳入

目前 enabled 依 token 有無自動切換;無 token 時回空,評分不受影響。

【狀態】token 機制已備妥;實際 dataset 欄位待有 token 後實測校正再接入評分,
        以免重蹈「欄位猜錯」覆轍(誠實標註,不交付未驗證的資料進評分)。
"""
import json
import os
import urllib.parse
import urllib.request

API = "https://api.finmindtrade.com/api/v4/data"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DATASET = "TaiwanStockHoldingSharesPer"  # 集保股權分散表


class FinMindSource:
    name = "finmind"

    def __init__(self):
        self.token = os.environ.get("FINMIND_TOKEN", "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _query(self, data_id: str, start: str) -> list:
        params = {"dataset": DATASET, "data_id": data_id, "start_date": start, "token": self.token}
        url = API + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
            return json.loads(r.read().decode("utf-8")).get("data", [])

    def big_holders(self, codes: list[str], start: str) -> dict[str, dict]:
        """
        大戶持股比例(待校正)。回 {code: {big_pct, big_chg}}。
        無 token 時回空,不影響評分。實際欄位對應待有 token 後依回傳結構校正。
        """
        if not self.enabled:
            return {}
        out: dict[str, dict] = {}
        # TODO(有 token 後):依實際回傳欄位解析千張大戶持股比例與週變化
        return out
