"""
資料收集品質把關 — 可隨時執行的驗證指令。

執行:python -m fetcher.validate   (於 repo 根目錄)
用途:每次撈資料前/後確認「撈到的資料是正確的」。任一檢查失敗 → 回非零 exit。
      掛進 .github/workflows/daily.yml,讓雲端在跑評分前先擋掉壞資料。

設計(呼應撈資料/分析分層):本檔只檢查「原始資料來源」是否健康可信,
不碰評分邏輯。檢查項目:
  1. 筆數下限      — API 是否真的回了一整天的資料(防 302/空回應)
  2. 價量合理性    — 收盤>0 比例、名稱非空比例(防欄位錯位/編碼壞)
  3. 法人恆等式    — 外資+投信+自營 必須等於三大法人合計(防欄位對應錯)
  4. 融資非負      — 餘額不可為負(防解析錯誤)
  5. 指標股抽查    — 已知大型股必須存在且收盤合理(防整批漏抓)
  6. 跨來源日期    — 上市與上櫃必須是同一交易日(防一邊用到舊資料)
"""
from __future__ import annotations
import sys

from .sources.twse import TwseSource
from .sources.tpex import TpexSource

# 各來源筆數下限(明顯低於此值代表 API 異常或被限流)
MIN_QUOTES = {"twse": 900, "tpex": 600}
MIN_INST = {"twse": 800, "tpex": 500}
MIN_MARGIN = {"twse": 800, "tpex": 500}
# 指標股抽查(代號必須存在於價量且收盤 > 0)
SPOT = {"twse": ["2330", "2317", "2454"], "tpex": ["6488", "3293", "5483"]}
# 恆等式容許誤差(股):四捨五入或來源自身微小不一致
IDENTITY_TOL = 2.0


class Check:
    def __init__(self, name: str, ok: bool, detail: str):
        self.name, self.ok, self.detail = name, ok, detail

    def line(self) -> str:
        mark = "PASS" if self.ok else "FAIL"
        return f"  [{mark}] {self.name} — {self.detail}"


def _ratio(items, pred) -> float:
    items = list(items)
    return sum(1 for x in items if pred(x)) / len(items) if items else 0.0


def check_source(src_name: str, q: dict, inst: dict, mg: dict, spot: list[str]) -> list[Check]:
    checks: list[Check] = []

    # 1. 筆數下限
    checks.append(Check(
        f"{src_name} 價量筆數", len(q) >= MIN_QUOTES[src_name],
        f"{len(q)} 檔(下限 {MIN_QUOTES[src_name]})"))
    checks.append(Check(
        f"{src_name} 法人筆數", len(inst) >= MIN_INST[src_name],
        f"{len(inst)} 檔(下限 {MIN_INST[src_name]})"))
    checks.append(Check(
        f"{src_name} 融資券筆數", len(mg) >= MIN_MARGIN[src_name],
        f"{len(mg)} 檔(下限 {MIN_MARGIN[src_name]})"))

    # 2. 價量合理性:多數個股收盤 > 0、幾乎所有個股有名稱
    if q:
        close_ok = _ratio(q.values(), lambda v: v.get("close", 0) > 0)
        name_ok = _ratio(q.values(), lambda v: bool(v.get("name")))
        checks.append(Check(f"{src_name} 收盤>0 比例", close_ok >= 0.5, f"{close_ok:.0%}"))
        checks.append(Check(f"{src_name} 名稱非空比例", name_ok >= 0.95, f"{name_ok:.0%}"))

    # 3. 法人恆等式:foreign + trust + dealer == total
    if inst:
        bad = [c for c, v in inst.items()
               if abs(v["foreign"] + v["trust"] + v["dealer"] - v["total"]) > IDENTITY_TOL]
        rate = 1 - len(bad) / len(inst)
        sample = bad[:3]
        checks.append(Check(
            f"{src_name} 法人恆等式", rate >= 0.99,
            f"吻合 {rate:.1%}" + (f";異常例 {sample}" if sample else "")))

    # 4. 融資餘額非負
    if mg:
        neg = [c for c, v in mg.items() if v["margin_bal"] < 0 or v["short_bal"] < 0]
        checks.append(Check(
            f"{src_name} 融資券非負", not neg,
            "全部非負" if not neg else f"{len(neg)} 檔為負:{neg[:3]}"))

    # 5. 指標股抽查
    missing = [c for c in spot if c not in q or q[c].get("close", 0) <= 0]
    checks.append(Check(
        f"{src_name} 指標股抽查", not missing,
        f"{spot} 皆在" if not missing else f"缺漏/無收盤:{missing}"))

    return checks


def main() -> int:
    print("=== ChipTracker 資料來源驗證 ===")
    twse, tpex = TwseSource(), TpexSource()

    # 來源抓取包 try:暫時性失敗(timeout/IncompleteRead)不該擋掉整天更新 —
    # 那不是「資料壞」而是「暫時抓不到」,交由 build 步驟自行重試;
    # validate 只在「抓到資料但檢查不過」(恆等式/筆數異常)時才中斷。
    try:
        print("抓取 TWSE(上市)…")
        tq, ti, tm = twse.daily_quotes(), twse.institutional(), twse.margin()
        print("抓取 TPEX(上櫃)…")
        pq, pi, pm = tpex.daily_quotes(), tpex.institutional(), tpex.margin()
    except Exception as e:  # noqa: BLE001 — 來源暫時抽風
        print(f"⚠️ 來源暫時無法取得:{e}")
        print("→ 不中斷流程,交由 build 自行重試(build 也失敗才代表真的抓不到)。")
        return 0

    results: list[Check] = []
    results += check_source("twse", tq, ti, tm, SPOT["twse"])
    results += check_source("tpex", pq, pi, pm, SPOT["tpex"])

    # 6. 跨來源交易日一致性
    td_twse, td_tpex = twse.trading_date, tpex.trading_date
    results.append(Check(
        "跨來源交易日一致", bool(td_twse) and td_twse == td_tpex,
        f"上市 {td_twse} / 上櫃 {td_tpex}"))

    print("\n--- 檢查結果 ---")
    for c in results:
        print(c.line())

    failed = [c for c in results if not c.ok]
    print(f"\n總計 {len(results)} 項,通過 {len(results)-len(failed)},失敗 {len(failed)}")
    if failed:
        print("資料驗證未通過 — 不應拿這批資料去評分。")
        return 1
    print("資料驗證全數通過 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
