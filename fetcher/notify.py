"""
Discord 推播 — 把「主力潛伏發動快報」推到手機。

設計:GitHub Actions 跑完 build 後呼叫。讀環境變數 DISCORD_WEBHOOK(GitHub Secret),
POST 一張 Discord embed 訊息卡到指定頻道。**Discord 手機 App 會自動推播到你手機**,
所以股票「發動」時手機就會跳通知,不必另外開網站。

零相依(純 stdlib urllib),零金鑰外洩風險(webhook 走 GitHub Secret,不進程式碼)。
沒設 webhook 時自動略過(本機跑 / 還沒設 Secret 都不會壞 build)。
同一交易日只推一次(data/notify_state.json 去重,避免手動重跑洗版)。

本機預覽訊息格式(不需 webhook,印出 payload):
    python -m fetcher.notify
"""
from __future__ import annotations
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = "https://loses5201-alt.github.io/chiptracker/"
GOLD, RED = 0xF59E0B, 0xEF4444


def _fmt_date(d: str) -> str:
    return f"{d[4:6]}/{d[6:8]}" if d and len(d) == 8 else (d or "—")


def build_payload(stealth: list, watch: dict, trading_date: str) -> dict:
    """
    組 Discord embed。優先序:🚀 已發動(實際放量突破,真正「抓到了」的)→
    🎯 今日主推(分數最高的潛伏股,帶數據理由)→ 其他潛伏精選。
    """
    w = (watch or {}).get("watch", {})
    fired = [
        {"c": c, **e} for c, e in w.items()
        if e.get("triggered_date") == trading_date
    ]
    has_fire = bool(fired)
    fields = []

    # 🚀 已發動 — 真正的主角(實際放量突破,從埋伏抓到起漲)
    if has_fire:
        lines = []
        for e in sorted(fired, key=lambda x: x.get("cur_ret", 0), reverse=True):
            ret = e.get("cur_ret", e.get("trig_ret", 0))
            sign = "+" if ret >= 0 else ""
            lines.append(f"**{e['n']}** `{e['c']}` 進榜 {e.get('enter_px','?')} → {sign}{ret}%(埋伏 {e.get('age','?')} 日)")
        fields.append({"name": f"🚀 發動快報 · {len(fired)} 檔放量突破(從埋伏抓到起漲)",
                       "value": "\n".join(lines)[:1024], "inline": False})

    top = stealth or []
    # 🎯 今日主推 — 分數最高那檔,帶「為什麼是這檔」的數據理由
    if top:
        s = top[0]
        big = f"千張大戶 {s['big']}%" + (f"(週{'+' if (s.get('big_chg') or 0) >= 0 else ''}{s['big_chg']}%)" if s.get("big_chg") is not None else "") if s.get("big") is not None else ""
        why = "、".join((s.get("reason") or [])[:3]) or "法人低基期吃貨"
        detail = f"**{s['n']}** `{s['c']}`　{s['score']}伏 · 區間位置 {s.get('pos','?')}\n" \
                 f"📊 {why}" + (f"\n🏦 {big}" if big else "")
        fields.append({"name": "🎯 今日主推潛伏(大戶低基期布局)", "value": detail[:1024], "inline": False})

    # 其他潛伏(2~5 名,精簡列)
    rest = top[1:5]
    if rest:
        lines = []
        for i, s in enumerate(rest, 2):
            big = f" · 大戶{s['big']}%" if s.get("big") is not None else ""
            lines.append(f"{i}. **{s['n']}** `{s['c']}` · {s['score']}伏{big} · 位置{s.get('pos','?')}")
        fields.append({"name": "📋 其他潛伏觀察", "value": "\n".join(lines)[:1024], "inline": False})

    title = f"🚀 主力潛伏發動快報 · {_fmt_date(trading_date)}" if has_fire \
        else f"🎯 主力潛伏精選 · {_fmt_date(trading_date)}"
    return {
        "username": "ChipTracker",
        "embeds": [{
            "title": title,
            "url": SITE,
            "color": RED if has_fire else GOLD,
            "description": "大戶在低基期默默吃貨、還沒發動的股票。點標題開網站看走勢與布局計畫。",
            "fields": fields or [{"name": "今日無潛伏標的", "value": "法人尚未明顯在低基期吃貨。", "inline": False}],
            "footer": {"text": "潛伏=提前埋伏候選(回測純多頭無超額),非投資建議,務必停損"},
        }],
    }


def _post(webhook: str, payload: dict) -> int:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "ChipTracker/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def notify(stealth: list, watch: dict, trading_date: str) -> str:
    """讀 DISCORD_WEBHOOK 推播;無金鑰或當日已推則略過。回傳狀態字串供 log。"""
    webhook = os.environ.get("DISCORD_WEBHOOK", "").strip()
    if not webhook:
        return "略過(未設 DISCORD_WEBHOOK)"
    state_f = DATA / "notify_state.json"
    state = json.loads(state_f.read_text(encoding="utf-8")) if state_f.exists() else {}
    if state.get("last_pushed") == trading_date:
        return "略過(今日已推播)"
    try:
        code = _post(webhook, build_payload(stealth, watch, trading_date))
        state_f.write_text(json.dumps({"last_pushed": trading_date}, ensure_ascii=False), encoding="utf-8")
        return f"推播成功(HTTP {code})"
    except Exception as e:  # noqa: BLE001 — 推播失敗不該影響 build
        return f"推播失敗(略過):{e}"


if __name__ == "__main__":
    # 本機預覽:用現有 data 檔組訊息並印出(不送出),確認格式
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows console 預設 cp950 無法印 emoji
    except Exception:  # noqa: BLE001
        pass
    st = json.loads((DATA / "stealth.json").read_text(encoding="utf-8")) if (DATA / "stealth.json").exists() else []
    wf = DATA / "stealth_watch.json"
    wt = json.loads(wf.read_text(encoding="utf-8")) if wf.exists() else {"watch": {}}
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8")) if (DATA / "meta.json").exists() else {}
    td = meta.get("trading_date", "20260604")
    print(json.dumps(build_payload(st, wt, td), ensure_ascii=False, indent=2))
