"""
評分權重健檢 — 描述六面向在入選股中的實際行為,輔助日後調權重。

核心問題:「滿分配置(法人22/融資8/基本面20/國際20/題材15/技術15)合理嗎?」
這支工具回答「描述性」的部分(現況),搭配 backtest 的面向預測力(規範性,需累積):
  - fill%     入選股在該面向平均佔滿分多少(普遍高=入選門檻;普遍低=該面向常缺)
  - 區分度    分數的離散程度(標準化);高=該面向在拉開排名,低=大家都差不多
  - corr      該面向分數與總分的相關;高=該面向主導了最終排名
判讀邏輯:某面向若「區分度低又與總分高度相關」代表它幾乎決定排名卻沒在篩選,
          權重可能過重;真正該不該調,須對照 backtest factor_power(預測力)。

執行:python -m analytics.weight_review   (於 repo 根目錄)
輸出 data/weight_review.json,供前端「回測」分頁的評分健檢表顯示。
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TPE = timezone(timedelta(hours=8))
# (欄位, 名稱, 滿分權重) — 與 scoring 一致
FACTORS = [("s1", "法人", 22), ("s2", "融資", 8), ("s3", "基本面", 20),
           ("s4", "國際", 20), ("s5", "題材", 15), ("s6", "動能", 15)]


def _pearson(xs: list, ys: list) -> float | None:
    """皮爾森相關係數(純 stdlib);任一邊無變異則回 None。"""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs)
    sy = sum((y - my) ** 2 for y in ys)
    if sx == 0 or sy == 0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return round(cov / (sx ** 0.5 * sy ** 0.5), 3)


def run() -> dict:
    f = DATA / "stocks.json"
    stocks = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    if not stocks:
        return _write({"status": "no_data", "msg": "尚無 stocks.json,請先跑 build。"})

    totals = [r.get("score", 0) for r in stocks]
    n = len(stocks)
    out = []
    for key, name, full in FACTORS:
        vals = [r.get(key, 0) for r in stocks]
        mean = sum(vals) / n
        std = (sum((v - mean) ** 2 for v in vals) / n) ** 0.5
        out.append({
            "key": key, "name": name, "weight": full,
            "mean": round(mean, 2),
            "fill_pct": round(mean / full * 100, 1),
            "discrim": round(std / full * 100, 1),   # 區分度(標準化 std)
            "corr_total": _pearson(vals, totals),
        })
    return _write({
        "status": "ok",
        "generated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "sample": n,
        "factors": out,
        "note": ("基於今日入選股。fill%=平均佔滿分比、區分度=分數離散程度(高=在拉開排名)、"
                 "corr=與總分相關。權重是否該調,需對照回測『面向預測力』累積後判斷:"
                 "高權重但低預測力→考慮降;低權重但高預測力→考慮升。"),
    })


def _write(result: dict) -> dict:
    DATA.mkdir(exist_ok=True)
    (DATA / "weight_review.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys
    r = run()
    if r["status"] == "ok":
        print(f"評分權重健檢(樣本 {r['sample']} 檔):")
        print(f"  {'面向':<6}{'滿分':>5}{'平均':>8}{'fill%':>8}{'區分度':>8}{'與總分相關':>12}")
        for x in r["factors"]:
            corr = x["corr_total"] if x["corr_total"] is not None else "—"
            print(f"  {x['name']:<6}{x['weight']:>5}{x['mean']:>8}{x['fill_pct']:>7}%{x['discrim']:>7}%{str(corr):>12}")
    else:
        print(r.get("msg", "無資料"))
    sys.exit(0)
