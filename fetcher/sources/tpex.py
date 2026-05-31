"""
櫃買中心(TPEX)資料來源 — 上櫃股票。【尚未實作,預留】

設計上與 TwseSource 完全對等:只要把櫃買 OpenAPI 的端點與欄位填進來,
build.py 就會自動把上櫃股票一起納入,不需改動主程式。

目前回傳空字典,代表「暫不納入上櫃」,讓整條流程能先以上市資料完整跑起來。
待確認櫃買 OpenAPI 端點與欄位後再補。
"""
from .base import BaseSource


class TpexSource(BaseSource):
    name = "tpex"

    def daily_quotes(self) -> dict[str, dict]:
        return {}

    def institutional(self) -> dict[str, dict]:
        return {}

    def margin(self) -> dict[str, dict]:
        return {}
