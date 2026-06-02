"""
主力 / 大戶籌碼來源 — FinMind(需免費 token),用於「資金面-大戶進出」。

⚠️ 為什麼需要 token:
   台灣「券商分點 / 集保大戶持股」沒有官方免費即時 API。FinMind 提供整理好的版本,
   免費方案需註冊取得 token(不花錢):
     1. 到 https://finmindtrade.com 註冊 → 會員中心取得 API token
     2. 本機:設環境變數  FINMIND_TOKEN=<你的token>
     3. 雲端:GitHub repo → Settings → Secrets and variables → Actions → New secret
            名稱 FINMIND_TOKEN,並在 daily.yml 的 Build 步驟加 env: FINMIND_TOKEN: ${{ secrets.FINMIND_TOKEN }}

【接入流程(拿到 token 後)】
   step 1  `python -m fetcher.sources.finmind` 跑 probe,確認回傳欄位與本檔假設一致
   step 2  欄位無誤 → 在 scoring 增 score_big_holders 並於 build 接入(目前刻意未接)
   step 3  若欄位不同 → 依 probe 結果調整 big_holders 解析,再接入
   原則:**未經 token 實測前,不把大戶資料接進評分**,避免「欄位猜錯」汙染分數。

【資料集】TaiwanStockHoldingSharesPer(集保股權分散表,每週更新)
   依 FinMind 官方文件,欄位為:date / stock_id / HoldingSharesLevel / people / percent / unit
   千張大戶 = 持股 > 1,000 張(>1,000,000 股)= HoldingSharesLevel "more than 1,000,001"
   本檔已依此文件結構寫好解析,但仍以 probe 實測為準。
"""
import json
import os
import urllib.parse
import urllib.request

API = "https://api.finmindtrade.com/api/v4/data"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DATASET = "TaiwanStockHoldingSharesPer"   # 集保股權分散表
BIG_LEVEL = "more than 1,000,001"          # 千張大戶級距(>1000 張)


def _num(s) -> float:
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


class FinMindSource:
    name = "finmind"

    def __init__(self):
        self.token = os.environ.get("FINMIND_TOKEN", "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _query(self, data_id: str, start: str) -> list:
        """打 FinMind data API,回 data 陣列;status 非 200 或連線失敗回 []。"""
        params = {"dataset": DATASET, "data_id": data_id, "start_date": start, "token": self.token}
        url = API + "?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
                j = json.loads(r.read().decode("utf-8"))
            # FinMind 回 {"status":200,"data":[...]};額度用盡/錯誤回非 200 + msg
            if j.get("status") != 200:
                return []
            return j.get("data", [])
        except Exception:  # noqa: BLE001 — 限流/逾時/JSON 壞 → 視為無資料,不影響評分
            return []

    def big_holders(self, codes: list[str], start: str) -> dict[str, dict]:
        """
        千張大戶持股比例與週變化。回 {code: {big_pct, big_chg, date}}。
          big_pct  最新一週千張大戶持股佔比(%)
          big_chg  較前一週的變化(百分點);正=大戶加碼、負=大戶減碼
        無 token 時回空,不影響評分。逐檔查詢(集保資料量小、每週一筆級距資料)。
        """
        if not self.enabled:
            return {}
        out: dict[str, dict] = {}
        for code in codes:
            rows = self._query(code, start)
            big = [r for r in rows if str(r.get("HoldingSharesLevel", "")).strip() == BIG_LEVEL]
            if not big:
                continue
            big.sort(key=lambda r: r.get("date", ""))
            latest = big[-1]
            prev = big[-2] if len(big) >= 2 else None
            pct = _num(latest.get("percent"))
            chg = pct - _num(prev.get("percent")) if prev else 0.0
            out[code] = {"big_pct": round(pct, 2), "big_chg": round(chg, 2), "date": latest.get("date")}
        return out

    def probe(self, code: str = "2330", start: str = "2025-01-01") -> None:
        """
        自我檢測:有 token 時抓一檔印出原始欄位與級距,供確認 dataset 結構。
        接入評分前先跑這個,核對欄位假設(HoldingSharesLevel / percent)是否正確。
        """
        if not self.enabled:
            print("未設 FINMIND_TOKEN — 請先取得 token 並設環境變數。")
            return
        rows = self._query(code, start)
        print(f"dataset={DATASET}  data_id={code}  回傳 {len(rows)} 列")
        if not rows:
            print("無資料(token 無效 / 額度用盡 / 該股無資料),請檢查 token。")
            return
        print("欄位:", list(rows[0].keys()))
        print("最後一列:", rows[-1])
        levels = sorted(set(str(r.get("HoldingSharesLevel", "")) for r in rows))
        print("出現的持股級距:", levels)
        print(f"本檔假設的千張大戶級距 {BIG_LEVEL!r} 是否存在:", BIG_LEVEL in levels)
        sample = self.big_holders([code], start)
        print("big_holders 解析結果:", sample)


if __name__ == "__main__":
    # 拿到 token 後執行:python -m fetcher.sources.finmind
    FinMindSource().probe()
