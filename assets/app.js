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
const TABS = [
  { k: "entry", t: "進場建議" },
  { k: "foreign", t: "法人動向" },
  { k: "fund", t: "基本面" },
  { k: "topic", t: "題材熱度" },
  { k: "intl", t: "國際連動" },
  { k: "backtest", t: "回測" },
  { k: "overview", t: "總覽" },
];

let STOCKS = [];
let META = {};
let PERF = null;
let WREVIEW = null;
let MTREND = null;
let CHIPS = null;
let HPERF = null;
let view = "entry";

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
  } catch (e) {
    document.getElementById("content").innerHTML =
      '<div class="empty">尚無資料。請先讓 GitHub Actions 跑過一次,或本機執行 <code>python -m fetcher.build</code></div>';
    return;
  }
  renderMeta();
  renderTabs();
  render();
  setupModal();
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
    chip(s.overseas, "國際") + chip(s.news, "新聞") + chip(s.broker, "分點") +
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
  const chipBlock = ch && ch.inst && ch.inst.length >= 2
    ? `<div class="m-section">籌碼趨勢(近 ${ch.inst.length} 交易日,法人單位:股)</div>
       <div class="chip-trend">
         <div class="ct-row"><span class="ct-k">三大法人</span>${miniSpark(ch.inst, 150, 30)}${streakBadge(ch.inst_buy_streak)}</div>
         <div class="ct-row"><span class="ct-k">融資餘額</span>${miniSpark(ch.margin, 150, 30)}<span class="ct-note">${marginNote(ch.margin)}</span></div>
       </div>`
    : (s.mkt === "tpex" ? `<div class="m-section">籌碼趨勢</div><div class="note">上櫃個股籌碼歷史暫不支援</div>` : "");
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
    ${newsBlock}
    <div class="m-section">籌碼與基本面</div>
    <div class="dl"><span class="k">三大法人</span><span class="v">${s.smart}</span></div>
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
}

function setupModal() {
  const m = document.getElementById("modal");
  m.addEventListener("click", (e) => { if (e.target === m) closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
}
function closeModal() { document.getElementById("modal").classList.remove("show"); }

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
    const v = h.monotonic[String(w)];
    const t = v === true ? "✓ 有預測力" : v === false ? "✗ 不單調" : "資料不足";
    const c = v === true ? "ok" : v === false ? "bad" : "na";
    return `<div class="mono-box ${c}"><div class="mono-w">${w}日</div><div class="mono-t">${t}</div></div>`;
  }).join("");
  const topAlpha = W.map((w) => `${w}日 ${h.top[String(w)] && h.top[String(w)].alpha != null ? (h.top[String(w)].alpha >= 0 ? "+" : "") + h.top[String(w)].alpha : "—"}`).join(" · ");
  const allFalse = W.every((w) => h.monotonic[String(w)] === false);
  const conclusion = allFalse
    ? `<div class="note" style="border-left:4px solid #f59e0b"><b>⚠️ 本期發現:</b>五分位無單調性 — 籌碼+技術評分在此區間(多頭)對大型股的區分力不足,真正的 alpha 可能來自尚未納入回測的題材/基本面。回測的價值是看見真相、避免自我感覺良好。</div>`
    : "";
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

// 回測分頁:驗證「分數越高、後續越會漲嗎?」
function renderBacktest(box) {
  const wr = weightReviewBlock();
  const hb = historicalBlock();
  if (!PERF || PERF.status !== "ok") {
    const msg = PERF && PERF.msg ? PERF.msg : "回測資料尚未產生。";
    box.innerHTML = wr + hb + `<div class="bt-intro">
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

  box.innerHTML = wr + hb + `
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
    </div>
  </div>`;
}

// 載入骨架(資料抓取期間的佔位,取代純文字「載入中」)
function renderSkeleton() {
  const sk = `<div class="sk-card"><div class="sk-line w60"></div><div class="sk-line w40"></div>
    <div class="sk-radar"></div><div class="sk-line"></div><div class="sk-line w80"></div></div>`;
  document.getElementById("content").innerHTML = `<div class="grid">${sk.repeat(6)}</div>`;
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
