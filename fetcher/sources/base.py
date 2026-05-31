"""
資料來源抽象層 — BaseSource。

所有外部資料來源(證交所 TWSE、櫃買 TPEX、分點資料商…)都必須繼承這個介面。
主程式 build.py 只認識這個介面,不認識任何特定 API 的細節。
好處:未來要換或加資料源(例如改用 FinMind),只要新增一個子類別,主程式不必動。
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class BaseSource(ABC):
    """單一資料來源。所有回傳值一律以「股票代號(str)」為 key,方便跨來源合併。"""

    name: str = "base"

    @abstractmethod
    def daily_quotes(self) -> dict[str, dict]:
        """個股當日價量。回傳 {code: {open, high, low, close, volume, name}}。"""
        ...

    @abstractmethod
    def institutional(self) -> dict[str, dict]:
        """三大法人買賣超(單位:股)。回傳 {code: {foreign, trust, dealer, total}}。"""
        ...

    @abstractmethod
    def margin(self) -> dict[str, dict]:
        """融資融券餘額。回傳 {code: {margin_bal, margin_prev, short_bal, short_prev}}。"""
        ...
