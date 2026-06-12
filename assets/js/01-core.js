// 核心:常數/狀態/載入/導覽(頂部分頁+底部 tab bar+更多抽屜)/路由
// ChipTracker 前端邏輯(短線狙擊·六面向)
// 職責:讀 data/*.json → 依分頁渲染 + 點卡片看詳情。所有運算都在後端做完。

const SCORES = [
  { k: "s1", label: "法人", max: 22, color: "#5b8def" },
  { k: "s2", label: "融資", max: 8, color: "#9b7ddf" },
  { k: "s3", label: "基本面", max: 20, color: "#2fae7d" },
  { k: "s4", label: "國際", max: 20, color: "#3fb6c9" },
  { k: "s5", label: "題材", max: 15, color: "#d9a23a" },
  { k: "s6", label: "動能", max: 15, color: "#d4669a" },
];
const REC_TEXT = { strong: "強力建議", mid: "可留意", watch: "觀察" };
const SHORT_TEXT = { strong: "強烈做空", mid: "留意做空", watch: "觀察" };
const STEALTH_TEXT = { strong: "強力潛伏", mid: "潛伏中", watch: "觀察" };
const TABS = [
  { k: "stealth", t: "主力潛伏", short: "潛伏" },
  { k: "entry", t: "進場建議", short: "進場" },
  { k: "futures", t: "期貨風向", short: "期貨" },
  { k: "foreign", t: "法人動向", short: "法人" },
  { k: "fund", t: "基本面", short: "基本面" },
  { k: "topic", t: "題材熱度", short: "題材" },
  { k: "intl", t: "國際連動", short: "國際" },
  { k: "backtest", t: "回測", short: "回測" },
  { k: "overview", t: "總覽", short: "總覽" },
  { k: "short", t: "做空標的", short: "做空" },
  { k: "watch", t: "查詢/自選", short: "自選" },
];
// 導覽圖示:內嵌 SVG 線稿(取代 emoji,跟著 currentColor 換色,維持零依賴)
const ICONS = {
  stealth: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>',
  entry: '<polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/>',
  futures: '<circle cx="12" cy="12" r="9"/><polygon points="15.5 8.5 13.5 13.5 8.5 15.5 10.5 10.5" fill="currentColor" stroke="none"/>',
  foreign: '<path d="M3 9l9-5 9 5"/><path d="M5 10v8M9.7 10v8M14.3 10v8M19 10v8"/><path d="M3 20h18"/>',
  fund: '<path d="M7 3h7l4 4v14H7z"/><path d="M10 12h5M10 16h5"/>',
  topic: '<path d="M12 3c4 4 6 6.5 6 10a6 6 0 0 1-12 0c0-3.5 2-6 6-10z"/>',
  intl: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z"/>',
  backtest: '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3"/>',
  overview: '<path d="M4 20h16M7 20v-7M12 20V5M17 20v-10"/>',
  short: '<polyline points="3 7 9 13 13 9 21 17"/><polyline points="15 17 21 17 21 11"/>',
  watch: '<path d="M12 3.5l2.7 5.5 6 .9-4.3 4.2 1 6-5.4-2.8-5.4 2.8 1-6L3.3 9.9l6-.9z"/>',
  more: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8"/>',
  moon: '<path d="M20 13A8 8 0 1 1 11 4a6.5 6.5 0 0 0 9 9z"/>',
};
function icon(k) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[k] || ""}</svg>`;
}
// 手機底部 tab bar 只放最常用 4 個(拇指可及),其餘收進「更多」抽屜;桌機維持頂部完整分頁
const PRIMARY = ["stealth", "entry", "futures", "watch"];

let STOCKS = [];
let META = {};
let PERF = null;
let WREVIEW = null;
let MTREND = null;
let CHIPS = null;
let HPERF = null;
let ALL_STOCKS = null;
let SHORTS = null;
let STEALTH = null;
let STEALTH_BT = null;
let STEALTH_WATCH = null;
let FUTURES = null;
let view = "stealth";

async function boot() {
  setupTheme();
  renderSkeleton();
  try {
    [STOCKS, META] = await Promise.all([
      fetch("data/stocks.json?_=" + Date.now()).then((r) => r.json()),
      fetch("data/meta.json?_=" + Date.now()).then((r) => r.json()),
    ]);
    // 回測資料可能還不存在(剛起步),失敗不影響主畫面
    PERF = await fetch("data/performance.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
    WREVIEW = await fetch("data/weight_review.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
    MTREND = await fetch("data/market_trend.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
    CHIPS = await fetch("data/stock_chips.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
    HPERF = await fetch("data/historical_performance.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
    ALL_STOCKS = await fetch("data/all_stocks.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
    SHORTS = await fetch("data/shorts.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
    STEALTH = await fetch("data/stealth.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
    STEALTH_BT = await fetch("data/stealth_backtest.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
    STEALTH_WATCH = await fetch("data/stealth_watch.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
    FUTURES = await fetch("data/futures.json?_=" + Date.now()).then((r) => r.json()).catch(() => null);
  } catch (e) {
    document.getElementById("content").innerHTML =
      '<div class="empty">尚無資料。請先讓 GitHub Actions 跑過一次,或本機執行 <code>python -m fetcher.build</code></div>';
    return;
  }
  renderMeta();
  renderTabs();
  renderBottomBar();
  render();
  setupModal();
  const deep = location.hash.slice(1);  // 深層連結:#代號 直接開個股詳情(分享/書籤/重整)
  if (deep && STOCKS.find((x) => x.c === deep)) openDetail(deep);
}

function renderMeta() {
  const upd = META.updated_at ? META.updated_at.replace("T", " ").slice(0, 16) : "—";
  const s = META.sources || {};
  const ms = META.market_split;
  const split = ms ? ` · 推薦含上市 <b>${ms.twse}</b>/上櫃 <b>${ms.tpex}</b>` : "";
  const chip = (on, t) => `<span class="src ${on ? "on" : "off"}">${t}</span>`;
  document.getElementById("meta").innerHTML =
    `<span class="meta-main">候選 <b>${META.universe || 0}</b> 檔 · 交易日 <b>${META.trading_date || "—"}</b>${split}</span>` +
    `<span class="meta-src">` +
    chip(s.tpex, "上櫃") + chip(s.history, "技術") + chip(s.fundamentals, "基本面") +
    chip(s.overseas, "國際") + chip(s.news, "新聞") + chip(s.tdcc, "大戶") + chip(s.futures, "期貨") + chip(s.broker, "分點") +
    `</span><span class="meta-upd">更新 ${upd}</span>`;
}

function renderTabs() {
  document.getElementById("tabs").innerHTML = TABS.map(
    (t) => `<button class="tab ${t.k === view ? "active" : ""}" data-k="${t.k}">${t.t}</button>`
  ).join("");
  document.querySelectorAll(".tab").forEach((el) =>
    el.addEventListener("click", () => switchView(el.dataset.k))
  );
}

// 統一切換入口:同步頂部分頁 + 底部 tab bar + 關抽屜 + 回頂(手機切頁停在半空很迷路)
function switchView(k) {
  view = k;
  closeMoreSheet();
  renderTabs();
  renderBottomBar();
  render();
  window.scrollTo({ top: 0 });
}

// ── 手機底部 tab bar + 「更多」抽屜(桌機由 CSS 隱藏)──
function renderBottomBar() {
  const bar = document.getElementById("bottombar");
  if (!bar) return;
  const inMore = !PRIMARY.includes(view);   // 目前頁面在「更多」群 → 高亮更多鈕
  const btn = (t) => `<button class="bb-item ${t.k === view ? "active" : ""}" data-k="${t.k}">
    <span class="bb-icon">${icon(t.k)}</span><span class="bb-label">${t.short}</span></button>`;
  bar.innerHTML = PRIMARY.map((k) => btn(TABS.find((t) => t.k === k))).join("") +
    `<button class="bb-item ${inMore ? "active" : ""}" id="bb-more">
      <span class="bb-icon">${icon("more")}</span><span class="bb-label">更多</span></button>`;
  bar.querySelectorAll(".bb-item[data-k]").forEach((el) =>
    el.addEventListener("click", () => switchView(el.dataset.k)));
  document.getElementById("bb-more").addEventListener("click", openMoreSheet);
}

function openMoreSheet() {
  const sheet = document.getElementById("more-sheet");
  if (!sheet) return;
  const items = TABS.filter((t) => !PRIMARY.includes(t.k));
  document.getElementById("more-body").innerHTML =
    `<div class="sheet-handle"></div><div class="sheet-title">更多功能</div>
     <div class="sheet-grid">${items.map((t) =>
      `<button class="sheet-item ${t.k === view ? "active" : ""}" data-k="${t.k}">
        <span class="si-icon">${icon(t.k)}</span><span class="si-label">${t.t}</span></button>`).join("")}</div>`;
  sheet.classList.add("show");
  sheet.querySelectorAll(".sheet-item").forEach((el) =>
    el.addEventListener("click", () => switchView(el.dataset.k)));
  sheet.onclick = (e) => { if (e.target === sheet) closeMoreSheet(); };
}

function closeMoreSheet() {
  const sheet = document.getElementById("more-sheet");
  if (sheet) sheet.classList.remove("show");
}

function render() {
  const box = document.getElementById("content");
  if (!STOCKS.length) { box.innerHTML = '<div class="empty">尚無資料</div>'; return; }
  if (view === "overview") return renderOverview(box);
  if (view === "topic") return renderTopic(box);
  if (view === "backtest") return renderBacktest(box);
  if (view === "stealth") return renderStealth(box);
  if (view === "futures") return renderFutures(box);
  if (view === "short") return renderShorts(box);
  if (view === "watch") return renderWatchlist(box);
  let list = [...STOCKS];
  if (view === "foreign") list.sort((a, b) => b.s1 - a.s1);
  if (view === "fund") list = list.filter((s) => s.yoy != null).sort((a, b) => b.s3 - a.s3);
  if (view === "intl") list = list.filter((s) => s.topic && s.topic !== "—").sort((a, b) => b.s4 - a.s4);
  if (!list.length) { box.innerHTML = '<div class="empty">此分頁暫無符合資料</div>' + footNote(); return; }
  const head = view === "entry" ? marketPulse() : listAnalysis(view, list);
  box.innerHTML = head + `<div class="grid">${list.map((s, i) => card(s, i)).join("")}</div>` + footNote();
  box.querySelectorAll(".card").forEach((el) =>
    el.addEventListener("click", () => openDetail(el.dataset.code))
  );
}

// 各分頁分析摘要(法人/基本面/國際)— 把卡片清單彙總成一句白話判讀
function listAnalysis(view, list) {
  if (!list || !list.length) return "";
  const avg = (arr, k) => arr.reduce((a, s) => a + (s[k] || 0), 0) / arr.length;
  let title = "", body = "";
  if (view === "foreign") {
    const sameBuy = list.filter((s) => s.align === "外資投信同買").length;
    const top = list[0];
    const conc = avg(list.slice(0, 40), "conc").toFixed(1);
    title = "法人動向分析";
    body = `今日 <b class="up">${sameBuy}</b> 檔<b>外資投信同買</b>(法人共識最強訊號)。法人吃貨最猛 <b>${top.n}</b> <span class="la-c">${top.c}</span>(法人分 ${top.s1});推薦股法人買超佔成交量平均 <b>${conc}%</b>。跟著外資投信同買、且佔比高的標的,是貼著法人布局的核心。`;
  } else if (view === "fund") {
    const hi = list.filter((s) => s.yoy >= 30).length;
    const top = [...list].sort((a, b) => (b.yoy ?? -999) - (a.yoy ?? -999))[0];
    title = "基本面分析";
    body = `有營收資料的 <b>${list.length}</b> 檔中,<b class="up">${hi}</b> 檔月營收年增 ≥30%(高成長股)。成長最猛 <b>${top.n}</b> <span class="la-c">${top.c}</span>(YoY <b class="up">+${top.yoy}%</b>);全體平均 YoY <b>${avg(list, "yoy").toFixed(0)}%</b>。月營收年增是基本面動能的領先指標。`;
  } else if (view === "intl") {
    const by = {};
    list.forEach((s) => { (by[s.topic] = by[s.topic] || []).push(s); });
    const ranked = Object.entries(by).map(([t, arr]) => [t, avg(arr, "ov"), arr.length]).sort((a, b) => b[1] - a[1]);
    const t0 = ranked[0];
    title = "國際連動分析";
    body = `關聯國際題材的 <b>${list.length}</b> 檔分布在 <b>${ranked.length}</b> 個題材。海外同業動能最強題材 <b class="up">${t0[0]}</b>(海外近5日均 ${t0[1] >= 0 ? "+" : ""}${t0[1].toFixed(1)}%、${t0[2]} 檔)。海外同業走強常領先台股同題材個股,題材輪動看這裡。`;
  } else return "";
  return `<div class="list-analysis"><div class="la-t">${title}</div><div class="la-b">${body}</div></div>`;
}

// ── 六面向雷達圖(純 SVG,無外部相依)──
