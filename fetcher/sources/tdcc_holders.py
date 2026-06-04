"""
集保戶股權分散表(TDCC)— 千張大戶持股比例。

資料來源:TDCC OpenData(臺灣集中保管結算所,免金鑰、每週更新)
  https://opendata.tdcc.com.tw/getOD.ashx?id=1-5

為什麼用這個?
  「主力潛伏」要抓的是「大戶在發動前默默吃貨」。但 T86 三大法人 ≠ 真正的大戶
  (法人只是其中一種、且當沖/造市會抵消)。集保分散表直接給「持股 ≥1,000 張(千張)
  的股東佔該股的比例」,這是市場公認的「大戶籌碼」指標 —— 大戶比例週週升高、
  股價卻還沒漲,才是真正的吸籌訊號。

CSV 欄位(固定順序):
  0 資料日期(YYYYMMDD) / 1 證券代號(帶尾空格,需 strip) / 2 持股分級(1~17) /
  3 人數 / 4 股數 / 5 占集保庫存數比例(%)
分級含義(實測 2026-05 確認):
  1=1~999股 … 14=800,001~1,000,000股 / 15=1,000,001股以上(千張大戶)/
  16=差異數調整(可忽略)/ 17=合計(占比恆 100%)
→ 大戶比例 = 分級 15 的占比(已是百分比,直接取用)。

⚠️ 全市場單檔 CSV 約 2.3MB(~6.8萬列)→ 比照 tpex 教訓必須退避重試,
   避免雲端偶發 IncompleteRead 直接拋例外中斷整日更新。
⚠️ TDCC 只提供「最新一週」,無法回填歷史 → 週變化由 build 每次累積
   data/tdcc_history.json 而來(同 history.json 累積模式)。
"""
from __future__ import annotations
import csv
import io
import time
import urllib.request

URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_I_DATE, _I_CODE, _I_LEVEL, _I_PCT = 0, 1, 2, 5
_BIG_LEVEL = "15"   # 千張大戶(1,000,001 股以上)


def _num(s) -> float:
    """占比常為 '0.00'/空字串,統一轉 float;失敗回 0。"""
    try:
        v = str(s).replace(",", "").strip()
        return float(v) if v else 0.0
    except (ValueError, TypeError):
        return 0.0


def _download(tries: int = 4) -> str:
    """下載整份 CSV(大檔),偶發連線截斷 → 退避重試(記取 tpex IncompleteRead 教訓)。"""
    last = "(none)"
    for i in range(tries):
        try:
            req = urllib.request.Request(URL, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=90) as r:
                # 資料列皆 ASCII(日期/代號/數字),標題雖為 big5 亂碼但不影響解析
                return r.read().decode("utf-8-sig", errors="replace")
        except Exception as e:  # noqa: BLE001 — 任何錯誤都重試
            last = str(e)
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"TDCC OpenData 連 {tries} 次失敗:{last}")


def fetch() -> dict[str, dict]:
    """
    回傳 {code: {"ratio": 千張大戶占比%, "date": "YYYYMMDD"}}。
    只取分級 15(千張大戶),代號 strip 尾空格。失敗時上層自行容錯(回 {} 不致命)。
    """
    text = _download()
    reader = csv.reader(io.StringIO(text))
    next(reader, None)   # 跳過標題列
    out: dict[str, dict] = {}
    for row in reader:
        if len(row) <= _I_PCT or row[_I_LEVEL].strip() != _BIG_LEVEL:
            continue
        code = row[_I_CODE].strip()
        if not code:
            continue
        out[code] = {"ratio": _num(row[_I_PCT]), "date": row[_I_DATE].strip()}
    return out


if __name__ == "__main__":
    # 單獨驗欄位/級距:python -m fetcher.sources.tdcc_holders
    data = fetch()
    print(f"檔數:{len(data)}")
    for c in ("2330", "2317", "6488", "8299"):
        print(f"  {c}: {data.get(c)}")
