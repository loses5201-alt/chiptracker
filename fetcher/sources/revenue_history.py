"""
月營收歷史 — MOPS 公開月檔(免 token),供歷史回測回填 s3 基本面。

來源:https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{民國年}_{月}_0.html(上市,big5)
   每月一檔、全公司一次給齊,一年歷史只要 ~13 個請求,零金鑰零相依。
   ⚠️ 新版 mops.twse.com.tw 已撤掉 nas 靜態檔(404),要用 mopsov 備援域名。

防 lookahead:月營收法定公布期限是次月 10 日。回測在交易日 ds 查 yoy 時,
只能用「ds 當天已公布」的最新月份 — 即只取 M 滿足 (M+1 月 11 日) <= ds 的資料。
"""
from __future__ import annotations
import re
import time
import urllib.request

BASE = "https://mopsov.twse.com.tw/nas/t21/sii"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
# 列格式:<tr align=right><td align=center>2330</td><td align=left>台積電</td>
#         <td>當月營收</td><td>上月</td><td>去年當月</td><td>上月增減%</td><Td>去年同月增減%</Td>…
_CELL = re.compile(r"<td[^>]*>([^<]*)</td>", re.IGNORECASE)
_YOY_IDX = 6   # 去年同月增減(%) 的欄位序


def _num(s: str) -> float | None:
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def fetch_month(year: int, month: int) -> dict[str, float]:
    """抓某西元年月的上市全公司月營收 YoY%。回 {code: yoy};檔案不存在(未公布)回 {}。"""
    url = f"{BASE}/t21sc03_{year - 1911}_{month}_0.html"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=40) as r:
            txt = r.read().decode("big5", errors="replace")
    except Exception:  # noqa: BLE001 — 未公布/網路失敗 → 該月無資料
        return {}
    out: dict[str, float] = {}
    for row in txt.split("<tr")[1:]:
        cells = _CELL.findall(row)
        if len(cells) <= _YOY_IDX:
            continue
        code = cells[0].strip()
        if len(code) != 4 or not code.isdigit():
            continue
        yoy = _num(cells[_YOY_IDX])
        if yoy is not None:
            out[code] = yoy
    return out


class RevenueHistory:
    """回測用:載入一段期間的月營收,提供「交易日 ds 當下可知」的 yoy 查詢。"""

    def __init__(self):
        # {(year, month): {code: yoy}},僅保留有資料的月份
        self.months: dict[tuple[int, int], dict[str, float]] = {}

    def load(self, start_ds: str, end_ds: str) -> int:
        """載入覆蓋 [start_ds, end_ds](YYYYMMDD)回測區間所需的月份(含公布延遲緩衝)。"""
        # 區間起點當下可知的最舊月份 = start 往前推 2 個月(1 月 11 日才知道前一年 11 月不對 —
        # 1/11 知道去年 12 月;保險起見多抓一個月)
        y, m = int(start_ds[:4]), int(start_ds[4:6])
        m -= 2
        while m <= 0:
            m += 12
            y -= 1
        ey, em = int(end_ds[:4]), int(end_ds[4:6])
        n = 0
        while (y, m) <= (ey, em):
            data = fetch_month(y, m)
            if data:
                self.months[(y, m)] = data
                n += 1
            time.sleep(0.4)   # 對 MOPS 客氣點
            m += 1
            if m > 12:
                m, y = 1, y + 1
        return n

    def yoy_at(self, code: str, ds: str) -> float | None:
        """交易日 ds 當下「已公布」的最新月營收 YoY%。防 lookahead:M 月資料 M+1 月 11 日起才可用。"""
        y, m = int(ds[:4]), int(ds[4:6])
        day = int(ds[6:8])
        # ds 當天可用的最新月份:本月 11 日(含)以後可用上個月,否則用上上個月
        lag = 1 if day >= 11 else 2
        m -= lag
        while m <= 0:
            m += 12
            y -= 1
        # 該月沒抓到(公司未公布/檔案缺)就往前找,最多回溯 3 個月(再舊就失真,回 None 退中性)
        for _ in range(3):
            v = self.months.get((y, m), {}).get(code)
            if v is not None:
                return v
            m -= 1
            if m <= 0:
                m, y = 12, y - 1
        return None


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    # 自我檢測:抓 2026-04 印台積電 YoY,驗證欄位解析
    d = fetch_month(2026, 4)
    print(f"2026-04 上市公司數:{len(d)};2330 YoY = {d.get('2330')}%(預期 17.49)")
