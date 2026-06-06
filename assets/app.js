// ChipTracker 前端邏輯(短線狙擊·六面向)
// 職責:讀 data/*.json → 依分頁渲染 + 點卡片看詳情。所有運算都在後端做完。

const SCORES = [
  { k: "s1", label: "法人", max: 22, color: "#3b82f6" },
  { k: "s2", label: "融資", max: 8, color: "#8b5cf6" },
  { k: "s3", label: "基本面", max: 20, color: "#22c55e" },
  { k: "s4", label: "國際", max: 20, color: "#06b6d4" },
  { k: "s5", label: "題材", max: 15, color: "#f59e0b" },
  { k: "s6", label: "動能", max: 15, color: "#ec4899" },
];
const REC_TEXT = { strong: "強力建議", mid: "可留意", watch: "觀察" };
const SHORT_TEXT = { strong: "強烈做空", mid: "留意做空", watch: "觀察" };
const STEALTH_TEXT = { strong: "強力潛伏", mid: "潛伏中", watch: "觀察" };
const TABS = [
  { k: "stealth", t: "主力潛伏" },
  { k: "entry", t: "進場建議" },
  { k: "futures", t: "期貨風向" },
  { k: "foreign", t: "法人動向" },
  { k: "fund", t: "基本面" },
  { k: "topic", t: "題材熱度" },
  { k: "intl", t: "國際連動" },
  { k: "backtest", t: "回測" },
  { k: "overview", t: "總覽" },
  { k: "short", t: "做空標的" },
  { k: "watch", t: "查詢/自選" },
];

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
    el.addEventListener("click", () => { view = el.dataset.k; renderTabs(); render(); })
  );
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
  const pulse = view === "entry" ? marketPulse() : "";
  box.innerHTML = pulse + `<div class="grid">${list.map((s, i) => card(s, i)).join("")}</div>` + footNote();
  box.querySelectorAll(".card").forEach((el) =>
    el.addEventListener("click", () => openDetail(el.dataset.code))
  );
}

// ── 六面向雷達圖(純 SVG,無外部相依)──
// viewBox 比繪圖區寬,左右各留 padX 給標籤文字,避免「基本面」之類被切。
function radar(s, size = 150, showLabels = true) {
  const padX = showLabels ? 34 : 8;   // 水平留白(標籤用)
  const vbW = size + padX * 2;          // viewBox 寬度
  const cx = vbW / 2, cy = size / 2, R = size / 2 - (showLabels ? 22 : 8);
  const n = SCORES.length;
  const ang = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  const ptAt = (i, rad) => [cx + Math.cos(ang(i)) * rad, cy + Math.sin(ang(i)) * rad];

  // 背景同心六邊形格線(4 層)
  let grid = "";
  for (let g = 1; g <= 4; g++) {
    const rr = (R * g) / 4;
    const poly = SCORES.map((_, i) => ptAt(i, rr).map((v) => v.toFixed(1)).join(",")).join(" ");
    grid += `<polygon points="${poly}" fill="none" stroke="#e2e8f0" stroke-width="1"/>`;
  }
  // 軸線
  let axes = "";
  for (let i = 0; i < n; i++) {
    const [x, y] = ptAt(i, R);
    axes += `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="#e2e8f0" stroke-width="1"/>`;
  }
  // 資料多邊形
  const dataPts = SCORES.map((d, i) => {
    const val = Math.max(0, Math.min(1, s[d.k] / d.max));
    return ptAt(i, R * val).map((v) => v.toFixed(1)).join(",");
  });
  const poly = `<polygon points="${dataPts.join(" ")}" fill="url(#radarFill)" stroke="#6366f1" stroke-width="2" stroke-linejoin="round"/>`;
  // 頂點圓點(用各維顏色)
  let dots = "";
  SCORES.forEach((d, i) => {
    const val = Math.max(0, Math.min(1, s[d.k] / d.max));
    const [x, y] = ptAt(i, R * val);
    dots += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${d.color}"/>`;
  });
  // 維度標籤
  let labels = "";
  if (showLabels) {
    SCORES.forEach((d, i) => {
      const [x, y] = ptAt(i, R + 14);
      const anchor = Math.abs(x - cx) < 6 ? "middle" : x > cx ? "start" : "end";
      labels += `<text x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="${anchor}" font-size="11" fill="#64748b" font-weight="500">${d.label}</text>`;
    });
  }
  return `<svg viewBox="0 0 ${vbW} ${size}" class="radar" width="${vbW}" height="${size}">
    <defs><radialGradient id="radarFill"><stop offset="0%" stop-color="#6366f1" stop-opacity="0.35"/><stop offset="100%" stop-color="#818cf8" stop-opacity="0.12"/></radialGradient></defs>
    ${grid}${axes}${poly}${dots}${labels}</svg>`;
}

// 市場別標籤(上市/上櫃)。舊資料無 mkt 欄位時不顯示,避免誤標。
function mktTag(mkt) {
  if (mkt === "tpex") return `<span class="mkt otc">上櫃</span>`;
  if (mkt === "twse") return `<span class="mkt listed">上市</span>`;
  return "";
}

function card(s, idx) {
  const badges = (s.reason || []).slice(0, 3).map((r) => `<span class="badge">${r}</span>`).join("");
  const topicTag = s.topic && s.topic !== "—" ? `<span class="badge topic">${s.topic}</span>` : "";
  const newsLine = s.news && s.news.length
    ? `<div class="card-news">📰 ${s.news[0]}</div>` : "";
  const chg = s.yoy != null ? s.yoy : null;
  const ch = CHIPS && CHIPS[s.c] ? CHIPS[s.c] : null;
  const streakTag = ch && Math.abs(ch.inst_buy_streak) >= 3 ? streakBadge(ch.inst_buy_streak) : "";
  return `<div class="card" data-code="${s.c}" style="--i:${idx}">
    <div class="rank-badge ${s.rec}">${idx + 1}</div>
    <div class="card-top">
      <div class="ct-left">
        <div class="stock-name">${s.n}<span class="stock-code">${s.c}</span>${mktTag(s.mkt)}</div>
        <div class="px-row"><span class="stock-px">${s.close || "—"}</span> ${topicTag}</div>
      </div>
      <div class="ct-right">
        <div class="score-ring ${s.rec}"><span>${s.score}</span><small>分</small></div>
        <div class="pill ${s.rec}">${REC_TEXT[s.rec]}</div>
      </div>
    </div>
    <div class="card-mid">
      <div class="radar-wrap">${radar(s, 158)}</div>
    </div>
    <div class="mid-stats">
      ${statBox("月營收", s.yoy != null ? (s.yoy >= 0 ? "+" : "") + s.yoy + "%" : "—", s.yoy != null ? s.yoy >= 0 : null)}
      ${statBox("海外", s.ov != null ? (s.ov >= 0 ? "+" : "") + s.ov + "%" : "—", s.ov != null ? s.ov >= 0 : null)}
      ${statBox("RSI", s.rsi, null)}
      ${statBox("位置", s.pos, null)}
    </div>
    <div class="badges">${streakTag}${badges}</div>
    ${newsLine}
    <div class="card-hint">點擊看完整走勢與進出場 ›</div>
  </div>`;
}

// 卡片指標小格(2×2,label 左 + 值右,不擠不換行)
function statBox(k, v, positive) {
  const cls = positive === null ? "" : positive ? "up" : "down";
  return `<div class="ms-box"><span class="ms-k">${k}</span><span class="ms-v ${cls}">${v}</span></div>`;
}

function recColor(rec) {
  return { strong: "#ef4444", mid: "#d97706", watch: "#64748b" }[rec] || "#64748b";
}

// ── K 線走勢(純 SVG 折線)──
function sparkline(closes, w = 540, h = 180) {
  if (!closes || closes.length < 2) return '<div class="empty" style="padding:30px">尚無歷史走勢</div>';
  const min = Math.min(...closes), max = Math.max(...closes), range = (max - min) || 1, pad = 14;
  const pts = closes.map((c, i) => {
    const x = pad + (i / (closes.length - 1)) * (w - 2 * pad);
    const y = pad + (1 - (c - min) / range) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const up = closes[closes.length - 1] >= closes[0];
  const color = up ? "#ef4444" : "#22c55e";
  const area = `${pad},${h - pad} ` + pts.join(" ") + ` ${w - pad},${h - pad}`;
  const last = pts[pts.length - 1].split(",");
  return `<svg viewBox="0 0 ${w} ${h}" class="spark" preserveAspectRatio="none">
    <defs><linearGradient id="sparkG" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${color}" stop-opacity="0.28"/><stop offset="100%" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    <polygon points="${area}" fill="url(#sparkG)"/>
    <polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="${last[0]}" cy="${last[1]}" r="4" fill="${color}"/>
  </svg>
  <div class="spark-cap"><span>${closes.length}日前 ${min}</span><span>最高 ${max}</span><span style="color:${color};font-weight:600">現價 ${closes[closes.length - 1]}</span></div>`;
}

function scoreBar(s) {
  return SCORES.map((d) => {
    const pct = Math.round((s[d.k] / d.max) * 100);
    return `<div class="score-row">
      <span class="score-label">${d.label}</span>
      <span class="score-track"><span class="score-fill" style="width:${pct}%;background:${d.color}"></span></span>
      <span class="s-val">${s[d.k]}/${d.max}</span></div>`;
  }).join("");
}

// 法人連買/連賣天數徽章(signed:正連買紅、負連賣綠)
function streakBadge(st) {
  if (!st) return "";
  const buy = st > 0;
  return `<span class="streak-badge ${buy ? "up" : "down"}">法人${buy ? "連買" : "連賣"}${Math.abs(st)}天</span>`;
}
// 融資餘額近期變化說明
function marginNote(arr) {
  if (!arr || arr.length < 2) return "";
  const f = arr[0], l = arr[arr.length - 1];
  const pct = f ? (l - f) / f * 100 : 0;
  return `${arr.length}日 ${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

// 自動生成「為何推薦」白話分析:依各面向分數與指標組合成一段話 + 風險提示。
function analyzeStock(s) {
  const parts = [];
  if (s.s1 / 22 >= 0.75 && s.smart && s.smart !== "—") parts.push(`法人買盤偏多(${s.smart})`);
  if (s.yoy != null && s.yoy >= 20) parts.push(`月營收年增 <b>${s.yoy}%</b>、基本面強`);
  if (s.topic && s.topic !== "—") {
    let t = `屬 <b>${s.topic}</b> 題材`;
    if (s.ov != null && s.ov > 0) t += `、海外同業近期 +${s.ov}%`;
    if (s.heat) t += `、新聞熱度 ${s.heat} 則`;
    parts.push(t);
  }
  if (s.s6 / 15 >= 0.7) parts.push(`技術動能轉強(RSI ${s.rsi})`);
  if (s.s2 / 8 >= 0.7) parts.push("融資券籌碼配合");
  const recTxt = { strong: "強力建議", mid: "可留意", watch: "觀察" }[s.rec] || "";
  const lead = `<b>${s.n}</b>(${s.c})以 <b>${s.score} 分</b>列為「${recTxt}」,主要因為:`;
  const body = parts.length ? parts.join("、") + "。" : "六面向分數綜合達標。";
  const risks = [];
  if (s.pos >= 85) risks.push(`位階偏高(區間位置 ${s.pos}),宜等拉回或嚴設停損`);
  if (typeof s.rsi === "number" && s.rsi >= 80) risks.push(`RSI ${s.rsi} 過熱`);
  if (s.s1 / 22 < 0.4) risks.push("法人參與度偏低");
  if (s.yoy != null && s.yoy < 0) risks.push(`月營收年減 ${s.yoy}%`);
  const riskTxt = risks.length ? `<div class="why-risk">⚠️ 留意:${risks.join("、")}。</div>` : "";
  return `<div class="why">${lead}${body}${riskTxt}</div>`;
}

function openDetail(code) {
  const s = STOCKS.find((x) => x.c === code);
  if (!s) return;
  const topicTag = s.topic && s.topic !== "—" ? `<span class="badge topic">${s.topic}</span>` : "";
  const newsBlock = s.news && s.news.length
    ? `<div class="m-section">📰 ${s.topic} 相關新聞(近期)</div>
       <div class="news-list">${s.news.map((t) => `<div class="news-item">${t}</div>`).join("")}</div>`
    : "";
  const ch = CHIPS && CHIPS[s.c] ? CHIPS[s.c] : null;
  const hasMargin = ch && ch.margin && ch.margin.some((v) => v > 0);
  const turnTag = ch && ch.turn ? `<span class="streak-badge ${ch.turn === "初買" ? "up" : "down"}">${ch.turn}</span>` : "";
  let costRow = "";
  if (ch && ch.cost && s.close) {
    const diff = (s.close - ch.cost) / ch.cost * 100;
    const below = diff < 0;
    const note = below ? `跌破法人成本 ${diff.toFixed(1)}%` : `高於成本 +${diff.toFixed(1)}%`;
    costRow = `<div class="ct-row"><span class="ct-k">法人成本</span>
      <b style="font-family:'JetBrains Mono',monospace;font-size:14px">${ch.cost}</b>
      <span class="ct-note" style="${below ? "color:#f59e0b;font-weight:600" : ""}">${note}</span></div>`;
  }
  const chipBlock = ch && ch.inst && ch.inst.length >= 2
    ? `<div class="m-section">籌碼趨勢(近 ${ch.inst.length} 交易日,法人單位:股)</div>
       <div class="chip-trend">
         <div class="ct-row"><span class="ct-k">三大法人</span>${miniSpark(ch.inst, 150, 30)}${streakBadge(ch.inst_buy_streak)}${turnTag}</div>
         ${hasMargin
        ? `<div class="ct-row"><span class="ct-k">融資餘額</span>${miniSpark(ch.margin, 150, 30)}<span class="ct-note">${marginNote(ch.margin)}</span></div>`
        : `<div class="ct-row"><span class="ct-k">融資餘額</span><span class="ct-note">上櫃融資歷史暫不支援</span></div>`}
         ${costRow}
       </div>`
    : "";
  const peers = (ALL_STOCKS || []).filter((x) => x.topic === s.topic && s.topic !== "—")
    .sort((a, b) => b.base - a.base).slice(0, 8);
  const peerBlock = (s.topic !== "—" && peers.length > 1)
    ? `<div class="m-section">${s.topic} 同題材比較(base 基礎分)</div>
       <div class="peer-list">${peers.map((p) => {
        const me = p.c === s.c;
        const inTop = STOCKS.find((x) => x.c === p.c);
        return `<div class="peer-row${me ? " me" : ""}"${inTop && !me ? ` data-peer="${p.c}"` : ""}>
          <span class="peer-name">${p.n}<span class="stock-code">${p.c}</span>${me ? " ◀ 本檔" : ""}</span>
          <span class="peer-bar"><span style="width:${Math.min(100, p.base)}%"></span></span>
          <span class="peer-score">${p.base}</span></div>`;
      }).join("")}</div>`
    : "";
  document.getElementById("modal-body").innerHTML = `
    <div class="m-head">
      <div>
        <div class="m-name">${s.n}<span class="stock-code">${s.c}</span>${mktTag(s.mkt)} ${topicTag}</div>
        <div class="m-px">${s.close || "—"} <span class="pill ${s.rec}">${REC_TEXT[s.rec]} ${s.score}分</span></div>
      </div>
      <button class="m-close" id="m-close">✕</button>
    </div>
    ${analyzeStock(s)}
    <div class="m-grid">
      <div>
        <div class="m-section">六面向體質</div>
        <div class="m-radar">${radar(s, 220)}</div>
      </div>
      <div>
        <div class="m-section">各項得分</div>
        ${scoreBar(s)}
      </div>
    </div>
    <div class="m-section">近 ${s.closes ? s.closes.length : 0} 日走勢</div>
    ${sparkline(s.closes)}
    ${chipBlock}
    ${peerBlock}
    ${newsBlock}
    <div class="m-section">籌碼與基本面</div>
    <div class="dl"><span class="k">三大法人</span><span class="v">${s.smart}</span></div>
    <div class="dl"><span class="k">外資投信</span><span class="v">${s.align || "—"}</span></div>
    ${s.conc != null ? `<div class="dl"><span class="k">法人吃貨佔量</span><span class="v ${s.conc >= 0 ? "up" : "down"}">${s.conc >= 0 ? "+" : ""}${s.conc}%</span></div>` : ""}
    ${s.yoy != null ? `<div class="dl"><span class="k">月營收 YoY</span><span class="v ${s.yoy >= 0 ? "up" : "down"}">${s.yoy >= 0 ? "+" : ""}${s.yoy}%</span></div>` : ""}
    ${s.ov != null ? `<div class="dl"><span class="k">海外同業(5日)</span><span class="v ${s.ov >= 0 ? "up" : "down"}">${s.ov >= 0 ? "+" : ""}${s.ov}%</span></div>` : ""}
    <div class="dl"><span class="k">RSI</span><span class="v">${s.rsi}</span></div>
    <div class="dl"><span class="k">20日位置</span><span class="v">${s.pos}</span></div>
    <div class="m-section">參考進出場(程式估算,非投資建議)</div>
    <div class="trade-grid">
      <div class="tg-box"><div class="tg-k">進場區</div><div class="tg-v">${s.entry}</div></div>
      <div class="tg-box down"><div class="tg-k">停損 -5%</div><div class="tg-v">${s.stop}</div></div>
      <div class="tg-box up"><div class="tg-k">目標 +5%</div><div class="tg-v">${s.t1}</div></div>
      <div class="tg-box up"><div class="tg-k">目標 +10%</div><div class="tg-v">${s.t2}</div></div>
    </div>
    <div class="m-reason">${(s.reason || []).map((r) => `<span class="badge">${r}</span>`).join("")}</div>
  `;
  document.getElementById("modal").classList.add("show");
  document.getElementById("m-close").addEventListener("click", closeModal);
  document.querySelectorAll("[data-peer]").forEach((el) =>
    el.addEventListener("click", () => openDetail(el.dataset.peer)));
  if (location.hash !== "#" + code) history.replaceState(null, "", "#" + code);  // 可分享/重整保留
}

function setupModal() {
  const m = document.getElementById("modal");
  m.addEventListener("click", (e) => { if (e.target === m) closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
}
function closeModal() {
  document.getElementById("modal").classList.remove("show");
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
}

function renderTopic(box) {
  const heat = META.topic_heat || {};
  const ranked = Object.entries(heat).sort((a, b) => b[1] - a[1]);
  const maxHeat = Math.max(1, ...ranked.map((r) => r[1]));
  const bars = ranked.map(([name, h]) => {
    const stocks = STOCKS.filter((s) => s.topic === name);
    const chips = stocks.slice(0, 8).map((s) =>
      `<span class="t-chip ${s.rec}" data-code="${s.c}">${s.n} <b>${s.score}</b></span>`).join("");
    return `<div class="topic-row">
      <div class="topic-head"><span class="topic-name">${name}</span>
        <span class="topic-heat">🔥 ${h} 則新聞</span></div>
      <div class="topic-track"><span class="topic-fill" style="width:${(h / maxHeat) * 100}%"></span></div>
      <div class="topic-chips">${chips || '<span class="no-stock">候選股中無此題材</span>'}</div>
    </div>`;
  }).join("");
  box.innerHTML = `<div class="topic-wrap">${bars}</div>` + footNote();
  box.querySelectorAll(".t-chip").forEach((el) =>
    el.addEventListener("click", () => openDetail(el.dataset.code))
  );
}

// 評分面向健檢表(誰在主導排名),即時可看,放回測頁頂部。
function weightReviewBlock() {
  const w = WREVIEW;
  if (!w || w.status !== "ok") return "";
  const rows = w.factors.map((f) => {
    const corr = f.corr_total != null ? f.corr_total : "—";
    const hi = f.corr_total != null && f.corr_total >= 0.5 ? "bt-ret up" : "";
    return `<tr><td class="bt-grp">${f.name}</td><td>${f.weight}</td>
      <td>${f.fill_pct}%</td><td>${f.discrim}%</td><td><span class="${hi}">${corr}</span></td></tr>`;
  }).join("");
  return `<div class="m-section">評分面向健檢(誰在主導排名)</div>
    <div class="table-wrap"><table class="bt-table"><thead><tr>
      <th>面向</th><th>配置滿分</th><th>平均佔比</th><th>區分度</th><th>與總分相關</th>
    </tr></thead><tbody>${rows}</tbody></table></div>
    <div class="note">${w.note || ""}</div>`;
}

// 歷史回測區(離線跑的真實歷史驗證,即時可看,不必等每日快照累積)
function historicalBlock() {
  const h = HPERF;
  if (!h || h.status !== "ok") return "";
  const W = h.windows;
  const qLabel = { q1: "最低分 q1", q2: "q2", q3: "q3", q4: "q4", q5: "最高分 q5" };
  const qRows = ["q1", "q2", "q3", "q4", "q5"].map((q) =>
    `<tr><td class="bt-grp">${qLabel[q]}</td>${W.map((w) => {
      const d = h.quintile[q][String(w)];
      if (!d || d.avg == null) return `<td class="bt-na">—</td>`;
      const cls = d.avg >= 0 ? "up" : "down";
      const a = d.alpha != null ? `α${d.alpha >= 0 ? "+" : ""}${d.alpha} ` : "";
      return `<td><span class="bt-ret ${cls}">${d.avg >= 0 ? "+" : ""}${d.avg}%</span><span class="bt-sub">${a}勝${d.win_rate}%</span></td>`;
    }).join("")}</tr>`).join("");
  const mono = W.map((w) => {
    const q5 = h.quintile.q5[String(w)], q1 = h.quintile.q1[String(w)];
    const diff = (q5 && q1 && q5.alpha != null && q1.alpha != null) ? q5.alpha - q1.alpha : null;
    const strict = h.monotonic[String(w)];
    let t, c;
    if (diff === null) { t = "資料不足"; c = "na"; }
    else if (strict === true) { t = "✓ 完全單調"; c = "ok"; }
    else if (diff > 0) { t = `✓ 高分較優(+${diff.toFixed(1)})`; c = "ok"; }
    else { t = "✗ 無區分"; c = "bad"; }
    return `<div class="mono-box ${c}"><div class="mono-w">${w}日</div><div class="mono-t">${t}</div></div>`;
  }).join("");
  const topAlpha = W.map((w) => `${w}日 ${h.top[String(w)] && h.top[String(w)].alpha != null ? (h.top[String(w)].alpha >= 0 ? "+" : "") + h.top[String(w)].alpha : "—"}`).join(" · ");
  const goodCount = W.filter((w) => {
    const q5 = h.quintile.q5[String(w)], q1 = h.quintile.q1[String(w)];
    return q5 && q1 && q5.alpha != null && q1.alpha != null && q5.alpha > q1.alpha;
  }).length;
  const conclusion = goodCount >= 2
    ? `<div class="note" style="border-left:4px solid #22c55e"><b>✓ 本期發現:</b>放大樣本(${h.universe} 檔 × ${h.test_days} 交易日,涵蓋更多市況)後評分顯示<b>預測力</b> — 高分組 q5 的後續超額報酬高於低分組 q1、勝率亦隨分數遞增。先前小樣本/純多頭期看到的「無區分力」是樣本不足 + beta 蓋過所致。top${h.top_n} 超額穩定為正。</div>`
    : `<div class="note" style="border-left:4px solid #f59e0b"><b>⚠️ 本期發現:</b>五分位區分力有限,top${h.top_n} 超額為正但整體待強化;完整預測力可能還需題材新聞面(無歷史)。</div>`;
  const st = h.strategy || { top20: [], bench20: [] };
  const avg = (a) => a.length ? (a.reduce((x, y) => x + y, 0) / a.length).toFixed(2) : "—";
  return `<div class="m-section">📈 歷史回測(${h.test_days} 個交易日樣本 · ${(h.date_range || []).join(" ~ ")})</div>
    <div class="note" style="margin-top:0">標的池:成交值前 ${h.universe} 大上市股;歷史評分 = ${h.factors_used}</div>
    <div class="m-section" style="font-size:12.5px">評分五分位後續報酬(最高分 q5 應高於最低分 q1 = 評分有效)</div>
    <div class="table-wrap"><table class="bt-table"><thead><tr><th>分位</th>${W.map((w) => `<th>${w} 日</th>`).join("")}</tr></thead><tbody>${qRows}</tbody></table></div>
    <div class="m-section" style="font-size:12.5px">評分預測力(q5 ≥ q4 ≥ q3 ≥ q2 ≥ q1?)</div>
    <div class="mono-grid">${mono}</div>
    ${conclusion}
    <div class="note">top${h.top_n} 超額報酬(vs 大盤):${topAlpha}。<br>
      策略(每交易日買 top${h.top_n}、持有20日)平均報酬 <b>${avg(st.top20)}%</b> vs 同期大盤 <b>${avg(st.bench20)}%</b>。${h.note}</div>`;
}

// 主力潛伏回測:潛伏分高的股,埋伏後真的會發動嗎?(金色,呼應潛伏分頁)
function stealthBacktestBlock() {
  const h = STEALTH_BT;
  if (!h || h.status !== "ok") return "";
  const W = h.windows;
  const qLabel = { q1: "最低分 q1", q2: "q2", q3: "q3", q4: "q4", q5: "最高分 q5" };
  const qRows = ["q1", "q2", "q3", "q4", "q5"].map((q) =>
    `<tr><td class="bt-grp">${qLabel[q]}</td>${W.map((w) => {
      const d = h.quintile[q][String(w)];
      if (!d || d.avg == null) return `<td class="bt-na">—</td>`;
      const cls = d.avg >= 0 ? "up" : "down";
      const a = d.alpha != null ? `α${d.alpha >= 0 ? "+" : ""}${d.alpha} ` : "";
      return `<td><span class="bt-ret ${cls}">${d.avg >= 0 ? "+" : ""}${d.avg}%</span><span class="bt-sub">${a}勝${d.win_rate}%</span></td>`;
    }).join("")}</tr>`).join("");
  // 發動率 + 領先天數摘要卡
  const trigCards = W.map((w) => {
    const v = h.trigger_rate[String(w)];
    return `<div class="mono-box ${v != null && v >= 50 ? "ok" : "na"}"><div class="mono-w">${w}日內</div>
      <div class="mono-t">${v != null ? v + "% 發動" : "—"}</div></div>`;
  }).join("");
  // 潛伏 top vs 動能 top 超額對照
  const cmpRows = [
    { k: "stealth_top", t: "主力潛伏 top", c: "#f59e0b" },
    { k: "momentum_top", t: "動能選股 top（對照）", c: "#64748b" },
  ].map((g) => `<tr><td class="bt-grp"><span class="dot" style="background:${g.c}"></span>${g.t}</td>
    ${W.map((w) => {
      const d = h[g.k][String(w)];
      if (!d || d.alpha == null) return `<td class="bt-na">—</td>`;
      const cls = d.alpha >= 0 ? "up" : "down";
      return `<td><span class="bt-ret ${cls}">α${d.alpha >= 0 ? "+" : ""}${d.alpha}</span><span class="bt-sub">勝${d.win_rate}%</span></td>`;
    }).join("")}</tr>`).join("");
  // 結論:潛伏 top 是否多數窗口超額為正
  const stPos = W.filter((w) => { const d = h.stealth_top[String(w)]; return d && d.alpha != null && d.alpha > 0; }).length;
  const lead = h.lead_days_median;
  const concl = stPos >= Math.ceil(W.length / 2)
    ? `<div class="note" style="border-left:4px solid #f59e0b"><b>✓ 潛伏邏輯有效:</b>主力潛伏 top 多數窗口超額報酬為正${lead != null ? `,埋伏後中位數 <b>${lead} 個交易日</b>內首次達 +${h.lead_pct}%` : ""} — 確實能提前抓到發動前的標的。</div>`
    : `<div class="note" style="border-left:4px solid #f59e0b"><b>⚠️ 潛伏邏輯待強化:</b>top 超額尚不穩定,將依此回測調整潛伏評分權重(低基期/連買/量縮),再以集保大戶資料強化。</div>`;
  return `<div class="m-section">🪙 主力潛伏回測（${h.test_days} 個交易日樣本 · ${(h.date_range || []).join(" ~ ")}）</div>
    <div class="note" style="margin-top:0">驗證核心問題:<b>潛伏分高的股,埋伏後真的會「發動」嗎?</b>標的池成交值前 ${h.universe} 大上市股。</div>
    <div class="m-section" style="font-size:12.5px">潛伏分五分位後續報酬(最高分 q5 應高於最低分 q1)</div>
    <div class="table-wrap"><table class="bt-table"><thead><tr><th>分位</th>${W.map((w) => `<th>${w} 日</th>`).join("")}</tr></thead><tbody>${qRows}</tbody></table></div>
    <div class="m-section" style="font-size:12.5px">發動率(潛伏 top 埋伏後最高漲幅 ≥ ${h.trigger_pct}% 的比例)</div>
    <div class="mono-grid">${trigCards}</div>
    <div class="m-section" style="font-size:12.5px">主力潛伏 vs 動能選股 超額報酬對照(證明「提前」的價值)</div>
    <div class="table-wrap"><table class="bt-table"><thead><tr><th>策略</th>${W.map((w) => `<th>${w} 日</th>`).join("")}</tr></thead><tbody>${cmpRows}</tbody></table></div>
    ${concl}`;
}

// 回測分頁:驗證「分數越高、後續越會漲嗎?」
function renderBacktest(box) {
  const sb = stealthBacktestBlock();
  const wr = weightReviewBlock();
  const hb = historicalBlock();
  if (!PERF || PERF.status !== "ok") {
    const msg = PERF && PERF.msg ? PERF.msg : "回測資料尚未產生。";
    box.innerHTML = sb + wr + hb + `<div class="bt-intro">
      <h3>📊 推薦成效回測</h3>
      <p>這裡會驗證一件最重要的事:<b>分數越高的股票,之後真的越會漲嗎?</b></p>
      <p class="bt-wait">${msg}</p>
      <p class="bt-note">原理:每天把推薦清單存檔,之後用真實股價算「推薦日後 5/10/20/60 個交易日」的收益率,
      再按 強力建議 / 可留意 / 觀察 分組比較。今天才開始累積,約 <b>1 週後</b>看到 5 日結果、
      <b>1 個月後</b>看到 20 日結果。系統每交易日自動累積,你不用做任何事。</p>
    </div>` + footNote();
    return;
  }
  const W = PERF.windows || [5, 10, 20, 60];
  const G = [
    { k: "strong", t: "強力建議", c: "#ef4444" },
    { k: "mid", t: "可留意", c: "#d97706" },
    { k: "watch", t: "觀察", c: "#64748b" },
  ];
  const cell = (g, w) => {
    const d = (PERF.groups[g.k] || {})[w] || {};
    if (d.avg == null) return `<td class="bt-na">—</td>`;
    const cls = d.avg >= 0 ? "up" : "down";
    const a = d.alpha;
    return `<td><span class="bt-ret ${cls}">${d.avg >= 0 ? "+" : ""}${d.avg}%</span>
      <span class="bt-sub">α ${a != null ? (a >= 0 ? "+" : "") + a : "—"} · 勝${d.win_rate}% · n=${d.n}</span></td>`;
  };
  const rows = G.map((g) => `<tr>
    <td class="bt-grp"><span class="dot" style="background:${g.c}"></span>${g.t}</td>
    ${W.map((w) => cell(g, w)).join("")}
  </tr>`).join("");

  // 單調性判讀(分數是否有預測力)
  const mono = PERF.monotonic || {};
  const monoCards = W.map((w) => {
    const v = mono[String(w)];
    const txt = v === true ? "✓ 有預測力" : v === false ? "✗ 待調整" : "資料不足";
    const cls = v === true ? "ok" : v === false ? "bad" : "na";
    return `<div class="mono-box ${cls}"><div class="mono-w">${w}日</div><div class="mono-t">${txt}</div></div>`;
  }).join("");

  // 市場別表(上市 vs 上櫃)
  const MK = [{ k: "twse", t: "上市" }, { k: "tpex", t: "上櫃" }];
  const bm = PERF.by_market || {};
  const mkCell = (m, w) => {
    const d = (bm[m.k] || {})[w] || {};
    if (d.avg == null) return `<td class="bt-na">—</td>`;
    const cls = d.avg >= 0 ? "up" : "down";
    return `<td><span class="bt-ret ${cls}">${d.avg >= 0 ? "+" : ""}${d.avg}%</span>
      <span class="bt-sub">勝${d.win_rate}% · n=${d.n}</span></td>`;
  };
  const mkRows = MK.map((m) => `<tr>
    <td class="bt-grp">${m.t}</td>${W.map((w) => mkCell(m, w)).join("")}</tr>`).join("");

  // 面向預測力表(各面向高分股 vs 低分股的超額報酬差)
  const FP = PERF.factor_power || {};
  const fpRows = Object.keys(FP).map((name) => `<tr>
    <td class="bt-grp">${name}</td>
    ${W.map((w) => {
      const v = FP[name][String(w)];
      if (v == null) return `<td class="bt-na">—</td>`;
      const cls = v >= 0 ? "up" : "down";
      return `<td><span class="bt-ret ${cls}">${v >= 0 ? "+" : ""}${v}</span></td>`;
    }).join("")}</tr>`).join("");

  box.innerHTML = sb + wr + hb + `
    <div class="bt-head">
      <div><h3>📊 推薦成效回測</h3>
        <p class="bt-meta">累積 ${PERF.snapshot_days} 個交易日 · 評估 ${PERF.recommendations_seen} 筆推薦 ·
        ${PERF.date_range ? PERF.date_range.join(" ~ ") : ""}</p></div>
    </div>
    <div class="m-section">各組平均收益率(推薦日後 N 個交易日)</div>
    <div class="table-wrap"><table class="bt-table"><thead><tr>
      <th>分組</th>${W.map((w) => `<th>${w} 日</th>`).join("")}
    </tr></thead><tbody>${rows}</tbody></table></div>
    <div class="m-section">評分預測力(強力建議 ≥ 可留意 ≥ 觀察?)</div>
    <div class="mono-grid">${monoCards}</div>
    <div class="m-section">市場別表現(上市 vs 上櫃)</div>
    <div class="table-wrap"><table class="bt-table"><thead><tr>
      <th>市場</th>${W.map((w) => `<th>${w} 日</th>`).join("")}
    </tr></thead><tbody>${mkRows}</tbody></table></div>
    <div class="m-section">六面向預測力(高分股 − 低分股 的超額報酬,正值=該面向越能預測上漲)</div>
    <div class="table-wrap"><table class="bt-table"><thead><tr>
      <th>面向</th>${W.map((w) => `<th>${w} 日</th>`).join("")}
    </tr></thead><tbody>${fpRows}</tbody></table></div>
    <div class="note">${PERF.note || ""} 「有預測力」代表該窗口下分數越高、平均報酬越高,
    是評分有效的證據;α=超越大盤幅度;樣本數(n)太小時結果僅供參考。</div>
  ` + footNote();
}

// 今日選股橫斷面特徵:六面向平均、題材分布、平均技術指標。從 STOCKS 即時算。
function overviewProfile() {
  const n = STOCKS.length || 1;
  const bars = SCORES.map((d) => {
    const v = STOCKS.reduce((a, s) => a + (s[d.k] || 0), 0) / n;
    const pct = Math.round((v / d.max) * 100);
    return `<div class="score-row"><span class="score-label">${d.label}</span>
      <span class="score-track"><span class="score-fill" style="width:${pct}%;background:${d.color}"></span></span>
      <span class="s-val">${v.toFixed(1)}/${d.max}</span></div>`;
  }).join("");

  const tc = {};
  STOCKS.forEach((s) => { if (s.topic && s.topic !== "—") tc[s.topic] = (tc[s.topic] || 0) + 1; });
  const topics = Object.entries(tc).sort((a, b) => b[1] - a[1]);
  const maxT = Math.max(1, ...topics.map((t) => t[1]));
  const topicBars = topics.map(([nm, c]) =>
    `<div class="pt-row"><span class="pt-name">${nm}</span>
      <span class="pt-track"><span class="pt-fill" style="width:${(c / maxT) * 100}%"></span></span>
      <span class="pt-c">${c}</span></div>`).join("") || '<span class="muted">無題材標記</span>';

  const numRsi = STOCKS.filter((s) => typeof s.rsi === "number");
  const avgRsi = numRsi.length ? (numRsi.reduce((a, s) => a + s.rsi, 0) / numRsi.length).toFixed(0) : "—";
  const avgPos = (STOCKS.reduce((a, s) => a + (s.pos || 0), 0) / n).toFixed(0);
  const ms = META.market_split || {};
  return `<div class="profile">
    <div class="prof-col"><div class="prof-h">今日選股 · 六面向平均</div>${bars}</div>
    <div class="prof-col"><div class="prof-h">題材分布(檔數)</div>
      <div class="prof-topics">${topicBars}</div>
      <div class="prof-misc">平均 RSI <b>${avgRsi}</b> · 平均區間位置 <b>${avgPos}</b> · 上市 <b>${ms.twse || 0}</b> / 上櫃 <b>${ms.tpex || 0}</b></div>
    </div>
  </div>`;
}

function renderOverview(box) {
  const strong = STOCKS.filter((s) => s.rec === "strong").length;
  const mid = STOCKS.filter((s) => s.rec === "mid").length;
  const kpi = `<div class="kpi">
    <div class="box"><div class="n">${META.universe || 0}</div><div class="l">掃描候選</div></div>
    <div class="box"><div class="n" style="color:#ef4444">${strong}</div><div class="l">強力建議</div></div>
    <div class="box"><div class="n" style="color:#d97706">${mid}</div><div class="l">可留意</div></div>
    <div class="box"><div class="n">${META.yahoo_ok || 0}</div><div class="l">技術面回補</div></div>
  </div>`;
  const rows = STOCKS.map((s, i) => `<tr data-code="${s.c}">
    <td class="rank">${i + 1}</td>
    <td>${s.n}<span class="stock-code">${s.c}</span>${mktTag(s.mkt)}</td>
    <td>${s.close || "—"}</td>
    <td><span class="score-pill ${s.rec}">${s.score}</span></td>
    <td>${s.s1}</td>
    <td class="${s.yoy >= 0 ? "up" : "down"}">${s.yoy != null ? s.yoy + "%" : "—"}</td>
    <td>${s.topic && s.topic !== "—" ? s.topic : "—"}</td></tr>`).join("");
  box.innerHTML = marketPulse() + kpi + overviewProfile() + `<div class="table-wrap"><table><thead><tr>
    <th>#</th><th>股票</th><th>收盤</th><th>總分</th><th>法人</th><th>營收YoY</th><th>題材</th>
    </tr></thead><tbody>${rows}</tbody></table></div>` + footNote();
  box.querySelectorAll("tbody tr").forEach((el) =>
    el.addEventListener("click", () => openDetail(el.dataset.code))
  );
}

// 大盤指標 mini 走勢(中性藍紫,不套紅綠 — 融資增減無絕對好壞,看趨勢方向即可)
function miniSpark(vals, w = 116, h = 26) {
  if (!vals || vals.length < 2) return "";
  const min = Math.min(...vals), max = Math.max(...vals), rng = (max - min) || 1, pad = 2;
  const pts = vals.map((v, i) => {
    const x = pad + (i / (vals.length - 1)) * (w - 2 * pad);
    const y = pad + (1 - (v - min) / rng) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const up = vals[vals.length - 1] >= vals[0];
  const c = up ? "#8b5cf6" : "#0ea5e9";
  return `<svg viewBox="0 0 ${w} ${h}" class="mini-spark" preserveAspectRatio="none"><polyline points="${pts.join(" ")}" fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

// 連續同向天數(法人連買/連賣):從最新往回數連續正或負的天數
function streak(vals) {
  if (!vals || !vals.length) return { n: 0, dir: 0 };
  const last = vals[vals.length - 1];
  const dir = last > 0 ? 1 : last < 0 ? -1 : 0;
  if (!dir) return { n: 0, dir: 0 };
  let n = 0;
  for (let i = vals.length - 1; i >= 0; i--) {
    if ((dir > 0 && vals[i] > 0) || (dir < 0 && vals[i] < 0)) n++; else break;
  }
  return { n, dir };
}

// 大盤環境溫度計面板(三大法人走勢+連買天數、融資週趨勢)。選股前先看順風逆風。
function marketPulse() {
  const p = META.market_pulse;
  if (!p) return "";
  const cls = (v) => (v >= 0 ? "up" : "down");
  const total = p.advancers + p.decliners + p.unchanged || 1;
  const chips = (p.hot_topics || []).map((t) =>
    `<span class="pulse-topic">${t.name}${t.heat ? ` 🔥${t.heat}` : ""}</span>`).join("");

  // 融資餘額:優先用回填的週趨勢(總量+逐日走勢),沒有才退回當日變化
  // 三大法人:當日金額 + 近10日走勢 + 連買/連賣天數(BFI82U 回填)
  const itr = MTREND && MTREND.inst ? MTREND.inst : [];
  const instItem = (label, key, fallback) => {
    const arr = itr.map((d) => d[key]);
    const cur = arr.length ? arr[arr.length - 1] : fallback;
    const st = streak(arr);
    const stTxt = st.n >= 2 ? `<span class="inst-streak ${st.dir > 0 ? "up" : "down"}">${st.dir > 0 ? "連買" : "連賣"}${st.n}</span>` : "";
    return `<div class="inst-item"><span class="ii-k">${label}</span><b class="${cur >= 0 ? "up" : "down"}">${cur >= 0 ? "+" : ""}${Math.round(cur)}億</b>${arr.length >= 2 ? miniSpark(arr, 56, 18) : ""}${stTxt}</div>`;
  };

  let marginRow;
  const mt = MTREND && MTREND.margin && MTREND.margin.length >= 2 ? MTREND.margin : null;
  if (mt) {
    const arr = mt.map((d) => d.margin_lots);
    const cur = arr[arr.length - 1], first = arr[0];
    const pct = first ? (cur - first) / first * 100 : 0;
    marginRow = `<div class="pulse-margin">
      <span class="pm-k">融資餘額</span><b class="pm-v">${(cur / 10000).toFixed(1)}萬張</b>
      ${miniSpark(arr)}
      <span class="pm-trend ${pct >= 0 ? "rise" : "fall"}">${mt.length}日 ${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%</span></div>`;
  } else {
    const m = p.margin_chg_lots;
    const lots = (m >= 0 ? "+" : "") + (Math.abs(m) >= 10000 ? (m / 10000).toFixed(1) + "萬張" : Math.round(m) + "張");
    marginRow = `<div class="pulse-margin"><span class="pm-k">融資(當日)</span> <b class="${cls(m)}">${lots}</b></div>`;
  }

  return `<div class="pulse ${p.mood}">
    <div class="pulse-mood"><div class="pm-tag">${p.mood_text}</div><div class="pm-sub">今日盤勢</div></div>
    <div class="pulse-body">
      <div class="pulse-breadth">
        <div class="pb-bar">
          <span class="pb-up" style="width:${(p.advancers / total) * 100}%"></span>
          <span class="pb-fl" style="width:${(p.unchanged / total) * 100}%"></span>
          <span class="pb-dn" style="width:${(p.decliners / total) * 100}%"></span>
        </div>
        <div class="pb-cap"><span class="up">▲ ${p.advancers}</span>
          <span class="muted">平 ${p.unchanged}</span>
          <span class="down">▼ ${p.decliners}</span> · 上漲廣度 <b>${p.breadth_pct}%</b></div>
      </div>
      <div class="pulse-inst">
        ${instItem("外資", "foreign_yi", p.inst_foreign)}
        ${instItem("投信", "trust_yi", p.inst_trust)}
        ${instItem("自營", "dealer_yi", p.inst_dealer)}
      </div>
      ${marginRow}
      <div class="pulse-topics">強勢題材 ${chips}</div>
      ${META.quarter_end ? `<div class="pulse-qe">📅 季底投信作帳期 — 留意投信連買的中型股</div>` : ""}
    </div>
  </div>`;
}

// ── 期貨風向(台指期三大法人未平倉 + P/C 比)──
function fmtKou(n) {
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return sign + Math.abs(n).toLocaleString() + " 口";
}

function futOiCard(label, val, day, series) {
  const dir = val > 0 ? "多" : val < 0 ? "空" : "—";
  const cls = val > 0 ? "up" : val < 0 ? "down" : "";
  const st = streak(series);
  const stTxt = st && st.n >= 2
    ? `<span class="fut-streak ${st.dir > 0 ? "up" : "down"}">連續淨${st.dir > 0 ? "多" : "空"}${st.n}日</span>` : "";
  const dayTxt = day != null ? `<span class="fut-day ${day >= 0 ? "up" : "down"}">當日 ${day >= 0 ? "+" : "−"}${Math.abs(day).toLocaleString()}</span>` : "";
  return `<div class="fut-oi">
    <div class="fo-head"><span class="fo-k">${label}</span><span class="fo-tag ${cls}">淨${dir}單</span></div>
    <div class="fo-val ${cls}">${fmtKou(val)}</div>
    <div class="fo-foot">${series.length >= 2 ? miniSpark(series, 70, 22) : ""}${dayTxt}${stTxt}</div>
  </div>`;
}

function renderFutures(box) {
  const f = FUTURES;
  if (!f || !f.tx) {
    box.innerHTML = '<div class="empty" style="padding:50px">期貨資料尚未產生(下次自動更新後出現)</div>' + footNote();
    return;
  }
  const h = f.history || [];
  const moodCls = f.verdict === "偏多" ? "bull" : f.verdict === "偏空" ? "bear" : "neutral";
  // P/C 未平倉比判讀:偏高(>120)=避險買權多、籌碼偏多支撐;偏低(<80)=樂觀過頭偏空
  const pc = f.pc.oi_ratio;
  const pcRead = pc >= 120 ? "偏多(避險 Put 多、低點有撐)" : pc <= 80 ? "偏空(樂觀過頭)" : "中性";
  const pcCls = pc >= 120 ? "up" : pc <= 80 ? "down" : "";

  const intro = `<div class="fut-intro"><b>📊 期貨風向(大盤多空)</b> — 個股籌碼看「誰買哪檔」,期貨籌碼看「大戶對整個大盤的押注」。<b>外資台指期未平倉</b>是台股最重要的多空風向球;搭配個股潛伏/做空一起看。資料日 ${f.date}。程式訊號、非投資建議。</div>`;

  const verdict = `<div class="fut-verdict ${moodCls}">
    <div class="fv-tag">${f.verdict}</div>
    <div class="fv-reason">${f.verdict_reason}</div>
  </div>`;

  const oiCards = `<div class="fut-oi-grid">
    ${futOiCard("外資台指期", f.tx.foreign, f.tx.foreign_day, h.map((x) => x.foreign))}
    ${futOiCard("投信台指期", f.tx.trust, f.tx.trust_day, h.map((x) => x.trust))}
    ${futOiCard("自營台指期", f.tx.dealer, f.tx.dealer_day, h.map((x) => x.dealer))}
  </div>`;

  const pcBlock = `<div class="fut-pc">
    <div class="fpc-row"><span class="fpc-k">選擇權 Put/Call 未平倉比</span>
      <b class="fpc-v ${pcCls}">${pc}%</b><span class="fpc-read">${pcRead}</span>
      ${h.length >= 2 ? miniSpark(h.map((x) => x.pc_oi), 80, 22) : ""}</div>
    <div class="fpc-row"><span class="fpc-k">成交量 P/C 比</span><b class="fpc-v">${f.pc.vol_ratio}%</b></div>
  </div>`;

  box.innerHTML = intro + verdict + oiCards + pcBlock +
    `<div class="fut-note">📖 怎麼看:外資台指期<b>淨多單(綠/正)</b>=大戶押大盤漲、<b>淨空單(紅/負)</b>=押跌;
     看「連續加/減碼」比看單日更準。P/C 未平倉比偏高常代表低檔有避險買盤支撐。趨勢需逐日累積(目前 ${h.length} 日)。</div>` +
    footNote();
}

// 載入骨架(資料抓取期間的佔位,取代純文字「載入中」)
function renderSkeleton() {
  const sk = `<div class="sk-card"><div class="sk-line w60"></div><div class="sk-line w40"></div>
    <div class="sk-radar"></div><div class="sk-line"></div><div class="sk-line w80"></div></div>`;
  document.getElementById("content").innerHTML = `<div class="grid">${sk.repeat(6)}</div>`;
}

// ── 主力潛伏(起漲前布局:大戶吃貨、還沒發動)──
// 此股是否已被標記「發動」(Phase C 追蹤)
function isTriggered(code) {
  const e = STEALTH_WATCH && STEALTH_WATCH.watch && STEALTH_WATCH.watch[code];
  return !!(e && e.triggered_date);
}

// 埋伏進度條(Phase D):用 60 日區間位置視覺化「離發動還多遠」潛伏 → 蓄勢 → 發動
function stealthProgress(s) {
  const trig = isTriggered(s.c);
  const pos = s.pos != null ? s.pos : 50;
  const pct = trig ? 100 : Math.max(4, Math.min(96, pos));
  const stage = trig ? "已發動" : pos < 35 ? "深埋伏" : pos <= 65 ? "蓄勢中" : "將發動";
  return `<div class="stealth-prog${trig ? " fired" : ""}">
    <div class="sp-track"><div class="sp-fill" style="width:${pct}%"></div><div class="sp-dot" style="left:${pct}%"></div></div>
    <div class="sp-foot"><div class="sp-labels"><span>潛伏</span><span>蓄勢</span><span>發動</span></div><div class="sp-stage">${trig ? "🚀 " : ""}${stage}</div></div>
  </div>`;
}

// 集保千張大戶持股顯示:「X%」或「X% ▲+Y」(週變化,null=資料未滿兩週)
function bigText(s) {
  if (s.big == null) return "—";
  if (s.big_chg == null) return s.big + "%";
  const arrow = s.big_chg > 0 ? "▲+" : s.big_chg < 0 ? "▼" : "±";
  return `${s.big}% <small style="opacity:.85">${arrow}${Math.abs(s.big_chg)}</small>`;
}

function stealthCard(s, idx) {
  const badges = (s.reason || []).map((r) => `<span class="badge stealth">${r}</span>`).join("");
  return `<div class="card stealth" data-code="${s.c}" style="--i:${idx}">
    <div class="rank-badge stealth">${idx + 1}</div>
    <div class="card-top">
      <div class="ct-left">
        <div class="stock-name">${s.n}<span class="stock-code">${s.c}</span>${mktTag(s.mkt)}</div>
        <div class="px-row"><span class="stock-px">${s.close || "—"}</span></div>
      </div>
      <div class="ct-right">
        <div class="score-ring stealth"><span>${s.score}</span><small>伏</small></div>
        <div class="pill stealth">${STEALTH_TEXT[s.rec]}</div>
      </div>
    </div>
    <div class="mid-stats">
      ${statBox("月營收", s.yoy != null ? (s.yoy >= 0 ? "+" : "") + s.yoy + "%" : "—", s.yoy != null ? s.yoy >= 0 : null)}
      ${statBox("千張大戶", bigText(s), s.big_chg != null ? s.big_chg >= 0 : null)}
    </div>
    <div class="badges">${badges}</div>
    ${stealthProgress(s)}
    <div class="short-trade">布局 ${s.entry} · 停損 ${s.stop} · 目標 ${s.t1}/${s.t2}</div>
    <div class="card-hint">點擊看走勢與布局計畫 ›</div>
  </div>`;
}

function renderStealth(box) {
  if (!STEALTH || !STEALTH.length) {
    box.innerHTML = '<div class="empty" style="padding:50px">今日無明顯潛伏標的(法人尚未明顯在低基期吃貨)</div>' + footNote();
    return;
  }
  const intro = `<div class="stealth-intro"><b>🎯 主力潛伏(起漲前布局)</b> — 法人默默吃貨、股價還在低基期沒發動,跟著大戶提前埋伏。<b>這是「跟著大戶賺大錢」的核心</b>。需耐心(可能先盤整),此為程式訊號、非投資建議,務必停損。</div>`;
  box.innerHTML = intro + firedBlock() + `<div class="grid">${STEALTH.map((s, i) => stealthCard(s, i)).join("")}</div>` + footNote();
  box.querySelectorAll(".card, .fired-card").forEach((el) =>
    el.addEventListener("click", () => openStealthDetail(el.dataset.code)));
}

// 🚀 已發動區(Phase C):從埋伏到發動的實際案例,作為「跟著大戶提前埋伏」的活體驗證
function firedBlock() {
  const w = STEALTH_WATCH && STEALTH_WATCH.watch;
  if (!w) return "";
  const fired = Object.entries(w)
    .filter(([, e]) => e.triggered_date)
    .map(([c, e]) => ({ c, ...e }))
    .sort((a, b) => (b.cur_ret ?? 0) - (a.cur_ret ?? 0));
  if (!fired.length) return "";
  const cards = fired.map((e) => {
    const ret = e.cur_ret ?? e.trig_ret ?? 0;
    const days = e.age != null ? e.age : "—";
    return `<div class="fired-card" data-code="${e.c}">
      <div class="fc-top"><span class="fc-name">${e.n}<span class="stock-code">${e.c}</span></span>
        <span class="fc-ret ${ret >= 0 ? "up" : "down"}">${ret >= 0 ? "+" : ""}${ret}%</span></div>
      <div class="fc-meta">進榜 ${e.enter_px}(${fmtDate(e.enter_date)})→ 發動 ${fmtDate(e.triggered_date)} · 埋伏 ${days} 日</div>
    </div>`;
  }).join("");
  return `<div class="fired-wrap"><div class="fired-head">🚀 已發動 <small>埋伏後出現放量突破訊號的潛伏股(${fired.length})</small></div>
    <div class="fired-grid">${cards}</div></div>`;
}

function fmtDate(d) {
  return d && d.length === 8 ? `${d.slice(4, 6)}/${d.slice(6, 8)}` : (d || "—");
}

function openStealthDetail(code) {
  const s = STEALTH.find((x) => x.c === code);
  if (!s) return;
  document.getElementById("modal-body").innerHTML = `
    <div class="m-head">
      <div>
        <div class="m-name">${s.n}<span class="stock-code">${s.c}</span>${mktTag(s.mkt)}</div>
        <div class="m-px">${s.close || "—"} <span class="pill stealth">${STEALTH_TEXT[s.rec]} ${s.score}分</span></div>
      </div>
      <button class="m-close" id="m-close">✕</button>
    </div>
    <div class="note" style="border-left:4px solid #f0b429">🎯 主力潛伏:法人默默吃貨、股價還沒發動。提前布局需耐心(可能先盤整),非投資建議,務必停損。</div>
    <div class="m-section">埋伏進度</div>
    ${stealthProgress(s)}
    <div class="m-section">潛伏理由</div>
    <div class="m-reason">${(s.reason || []).map((r) => `<span class="badge stealth">${r}</span>`).join("")}</div>
    ${s.big != null ? `<div class="dl"><span class="k">千張大戶持股</span><span class="v ${s.big_chg != null && s.big_chg >= 0 ? "up" : s.big_chg != null ? "down" : ""}">${s.big}%${s.big_chg != null ? `(週${s.big_chg >= 0 ? "+" : ""}${s.big_chg}%)` : "(週變化累積中)"}</span></div>` : ""}
    ${s.yoy != null ? `<div class="dl"><span class="k">月營收 YoY</span><span class="v ${s.yoy >= 0 ? "up" : "down"}">${s.yoy >= 0 ? "+" : ""}${s.yoy}%</span></div>` : ""}
    <div class="m-section">近 ${s.closes ? s.closes.length : 0} 日走勢</div>
    ${sparkline(s.closes)}
    <div class="m-section">參考布局進出場(程式估算,非建議)</div>
    <div class="trade-grid">
      <div class="tg-box"><div class="tg-k">布局區</div><div class="tg-v">${s.entry}</div></div>
      <div class="tg-box down"><div class="tg-k">停損</div><div class="tg-v">${s.stop}</div></div>
      <div class="tg-box up"><div class="tg-k">目標+10%</div><div class="tg-v">${s.t1}</div></div>
      <div class="tg-box up"><div class="tg-k">目標+20%</div><div class="tg-v">${s.t2}</div></div>
    </div>`;
  document.getElementById("modal").classList.add("show");
  document.getElementById("m-close").addEventListener("click", closeModal);
}

// ── 做空標的(高檔回落 / 業績轉弱)──
function shortCard(s, idx) {
  const badges = (s.reason || []).map((r) => `<span class="badge short">${r}</span>`).join("");
  return `<div class="card short" data-code="${s.c}" style="--i:${idx}">
    <div class="rank-badge short">${idx + 1}</div>
    <div class="card-top">
      <div class="ct-left">
        <div class="stock-name">${s.n}<span class="stock-code">${s.c}</span>${mktTag(s.mkt)}</div>
        <div class="px-row"><span class="stock-px">${s.close || "—"}</span></div>
      </div>
      <div class="ct-right">
        <div class="score-ring short"><span>${s.score}</span><small>空</small></div>
        <div class="pill short">${SHORT_TEXT[s.rec]}</div>
      </div>
    </div>
    <div class="mid-stats">
      ${statBox("月營收", s.yoy != null ? (s.yoy >= 0 ? "+" : "") + s.yoy + "%" : "—", s.yoy != null ? s.yoy >= 0 : null)}
      ${statBox("董監設質", s.pledge != null ? s.pledge + "%" : "—", s.pledge != null ? !(s.pledge >= 40) : null)}
    </div>
    <div class="badges">${badges}</div>
    <div class="short-trade">空 ${s.entry} · 停損 ${s.stop}(漲) · 目標 ${s.t1}/${s.t2}(跌)</div>
    <div class="card-hint">點擊看走勢與做空計畫 ›</div>
  </div>`;
}

function renderShorts(box) {
  if (!SHORTS || !SHORTS.length) {
    box.innerHTML = '<div class="empty" style="padding:50px">今日無明顯做空標的</div>' + footNote();
    return;
  }
  const intro = `<div class="short-intro"><b>⚠️ 做空訊號(高檔回落 / 業績轉弱)</b> — 做空風險高(軋空、損失無上限),此為程式訊號、非投資建議,務必嚴設停損。</div>`;
  box.innerHTML = intro + `<div class="grid">${SHORTS.map((s, i) => shortCard(s, i)).join("")}</div>` + footNote();
  box.querySelectorAll(".card").forEach((el) =>
    el.addEventListener("click", () => openShortDetail(el.dataset.code)));
}

function openShortDetail(code) {
  const s = SHORTS.find((x) => x.c === code);
  if (!s) return;
  document.getElementById("modal-body").innerHTML = `
    <div class="m-head">
      <div>
        <div class="m-name">${s.n}<span class="stock-code">${s.c}</span>${mktTag(s.mkt)}</div>
        <div class="m-px">${s.close || "—"} <span class="pill short">${SHORT_TEXT[s.rec]} ${s.score}分</span></div>
      </div>
      <button class="m-close" id="m-close">✕</button>
    </div>
    <div class="note" style="border-left:4px solid #f59e0b">⚠️ 做空訊號,非投資建議。軋空風險高、損失無上限,務必設停損。</div>
    <div class="m-section">做空理由</div>
    <div class="m-reason">${(s.reason || []).map((r) => `<span class="badge short">${r}</span>`).join("")}</div>
    ${s.yoy != null ? `<div class="dl"><span class="k">月營收 YoY</span><span class="v ${s.yoy >= 0 ? "up" : "down"}">${s.yoy >= 0 ? "+" : ""}${s.yoy}%</span></div>` : ""}
    <div class="m-section">近 ${s.closes ? s.closes.length : 0} 日走勢</div>
    ${sparkline(s.closes)}
    <div class="m-section">參考做空進出場(程式估算,非建議)</div>
    <div class="trade-grid">
      <div class="tg-box"><div class="tg-k">空單進場</div><div class="tg-v">${s.entry}</div></div>
      <div class="tg-box up"><div class="tg-k">停損 漲5%</div><div class="tg-v">${s.stop}</div></div>
      <div class="tg-box down"><div class="tg-k">目標 跌5%</div><div class="tg-v">${s.t1}</div></div>
      <div class="tg-box down"><div class="tg-k">目標 跌10%</div><div class="tg-v">${s.t2}</div></div>
    </div>`;
  document.getElementById("modal").classList.add("show");
  document.getElementById("m-close").addEventListener("click", closeModal);
}

// ── 全市場查詢 + 自選股(localStorage)──
function getWatch() { try { return JSON.parse(localStorage.getItem("ct-watch") || "[]"); } catch { return []; } }
function toggleWatch(c) { const w = getWatch(); localStorage.setItem("ct-watch", JSON.stringify(w.includes(c) ? w.filter((x) => x !== c) : [...w, c])); }
function findStock(code) { return (ALL_STOCKS || []).find((s) => s.c === code); }

function stockRow(s) {
  if (!s) return "";
  const watched = getWatch().includes(s.c);
  const inTop = STOCKS.find((x) => x.c === s.c);
  return `<div class="srow"${inTop ? ` data-detail="${s.c}"` : ""}>
    <button class="sr-star ${watched ? "on" : ""}" data-star="${s.c}">${watched ? "★" : "☆"}</button>
    <span class="sr-name">${s.n}<span class="stock-code">${s.c}</span>${mktTag(s.mkt)}</span>
    <span class="sr-topic">${s.topic && s.topic !== "—" ? s.topic : ""}</span>
    <span class="sr-score">${s.base}<small>分</small></span>
    ${inTop ? '<span class="sr-in">推薦中</span>' : ""}</div>`;
}

function renderWatchlist(box) {
  const total = ALL_STOCKS ? ALL_STOCKS.length : 0;
  const wl = getWatch();
  const watchRows = wl.length
    ? wl.map((c) => stockRow(findStock(c))).join("")
    : '<div class="empty" style="padding:24px">尚無自選股 — 搜尋後點 ☆ 加入追蹤</div>';
  box.innerHTML = `
    <div class="search-bar"><input id="stock-search" type="search" autocomplete="off" placeholder="🔍 輸入代號或名稱,查全市場 ${total} 檔評分"></div>
    <div class="m-section">⭐ 自選股 (${wl.length})</div>
    <div id="watch-list" class="srows">${watchRows}</div>
    <div class="m-section">搜尋結果</div>
    <div id="search-result" class="srows"><div class="muted" style="padding:14px">在上方輸入關鍵字…</div></div>
  ` + footNote();

  const input = document.getElementById("stock-search");
  const result = document.getElementById("search-result");
  const bindRows = () => {
    box.querySelectorAll(".sr-star").forEach((el) => el.addEventListener("click", (e) => {
      e.stopPropagation(); toggleWatch(el.dataset.star); renderWatchlist(box);
    }));
    box.querySelectorAll("[data-detail]").forEach((el) => el.addEventListener("click", () => openDetail(el.dataset.detail)));
  };
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    if (!q) { result.innerHTML = '<div class="muted" style="padding:14px">在上方輸入關鍵字…</div>'; return; }
    const hits = (ALL_STOCKS || []).filter((s) => s.c.includes(q) || s.n.toLowerCase().includes(q)).slice(0, 30);
    result.innerHTML = hits.length ? hits.map(stockRow).join("") : '<div class="empty" style="padding:20px">查無此股(僅含當日有量的個股)</div>';
    bindRows();
  });
  bindRows();
}

function footNote() {
  const s = META.sources || {};
  return `<div class="note">
    ⚠️ 本站為個人技術練習,所有評分與進出價皆由程式依公開資料自動估算,<b>非投資建議</b>,
    短線追高風險高,請自設停損。
    題材熱度為新聞則數的代理指標;分點(主力)資料${s.broker ? "已啟用" : "未啟用"}。
    資料來源:證交所(上市)+ 櫃買中心(上櫃)法人/融資券/價量、證交所月營收 + Yahoo Finance(台股歷史/海外同業)+ Google News(題材新聞)。
  </div>`;
}

// 深色 / 淺色切換,選擇記在 localStorage(body 開頭的 inline script 負責首載防閃)
function setupTheme() {
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  const sync = () => { btn.textContent = document.body.classList.contains("dark") ? "☀️" : "🌙"; };
  sync();
  btn.addEventListener("click", () => {
    document.body.classList.toggle("dark");
    localStorage.setItem("ct-theme", document.body.classList.contains("dark") ? "dark" : "light");
    sync();
  });
}

boot();
