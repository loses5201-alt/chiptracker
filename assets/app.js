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
  { k: "overview", t: "總覽" },
];

let STOCKS = [];
let META = {};
let view = "entry";

async function boot() {
  try {
    [STOCKS, META] = await Promise.all([
      fetch("data/stocks.json?_=" + Date.now()).then((r) => r.json()),
      fetch("data/meta.json?_=" + Date.now()).then((r) => r.json()),
    ]);
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
  document.getElementById("meta").innerHTML =
    `掃描候選 <b>${META.universe || 0}</b> 檔 · 交易日 <b>${META.trading_date || "—"}</b> · ` +
    `技術 <b>${s.history ? "✓" : "—"}</b> · 基本 <b>${s.fundamentals ? "✓" : "—"}</b> · ` +
    `國際 <b>${s.overseas ? "✓" : "—"}</b> · 新聞 <b>${s.news ? "✓" : "—"}</b> · ` +
    `分點 <b>${s.broker ? "✓" : "未啟用"}</b> · 更新 ${upd}`;
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
  let list = [...STOCKS];
  if (view === "foreign") list.sort((a, b) => b.s1 - a.s1);
  if (view === "fund") list = list.filter((s) => s.yoy != null).sort((a, b) => b.s3 - a.s3);
  if (view === "intl") list = list.filter((s) => s.topic && s.topic !== "—").sort((a, b) => b.s4 - a.s4);
  if (!list.length) { box.innerHTML = '<div class="empty">此分頁暫無符合資料</div>' + footNote(); return; }
  box.innerHTML = `<div class="grid">${list.map(card).join("")}</div>` + footNote();
  box.querySelectorAll(".card").forEach((el) =>
    el.addEventListener("click", () => openDetail(el.dataset.code))
  );
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

function card(s) {
  const badges = (s.reason || []).map((r) => `<span class="badge">${r}</span>`).join("");
  const topicTag = s.topic && s.topic !== "—" ? `<span class="badge topic">${s.topic}</span>` : "";
  const newsLine = s.news && s.news.length
    ? `<div class="card-news">📰 ${s.news[0]}</div>` : "";
  return `<div class="card" data-code="${s.c}">
    <div class="card-top">
      <div>
        <div class="stock-name">${s.n}<span class="stock-code">${s.c}</span> ${topicTag}</div>
        <div class="stock-px">${s.close || "—"}</div>
      </div>
      <div style="text-align:right">
        <div class="score-num" style="color:${recColor(s.rec)}">${s.score}</div>
        <div class="pill ${s.rec}">${REC_TEXT[s.rec]}</div>
      </div>
    </div>
    <div class="badges">${badges}</div>
    ${scoreBar(s)}
    ${newsLine}
    <div class="pos-wrap">
      <div style="font-size:12px;color:#16a34a">20 日區間位置</div>
      <div class="pos-track"><span class="pos-dot" style="left:${s.pos}%"></span></div>
      <div class="pos-cap"><span>低</span><span>${s.pos}</span><span>高</span></div>
    </div>
    <div class="detail">
      <div class="dl"><span class="k">籌碼</span><span class="v">${s.smart}</span></div>
      ${s.yoy != null ? `<div class="dl"><span class="k">月營收 YoY</span><span class="v ${s.yoy >= 0 ? "up" : "down"}">${s.yoy >= 0 ? "+" : ""}${s.yoy}%</span></div>` : ""}
      ${s.ov != null ? `<div class="dl"><span class="k">海外同業(5日)</span><span class="v ${s.ov >= 0 ? "up" : "down"}">${s.ov >= 0 ? "+" : ""}${s.ov}%</span></div>` : ""}
      <div class="dl"><span class="k">RSI / 量</span><span class="v">${s.rsi} / ${s.vol}</span></div>
    </div>
    <div class="card-hint">點擊看走勢與新聞 ›</div>
  </div>`;
}

function recColor(rec) {
  return { strong: "#ef4444", mid: "#d97706", watch: "#64748b" }[rec] || "#64748b";
}

// ── K 線走勢(純 SVG 折線)──
function sparkline(closes, w = 540, h = 170) {
  if (!closes || closes.length < 2) return '<div class="empty" style="padding:30px">尚無歷史走勢</div>';
  const min = Math.min(...closes), max = Math.max(...closes), range = (max - min) || 1, pad = 12;
  const pts = closes.map((c, i) => {
    const x = pad + (i / (closes.length - 1)) * (w - 2 * pad);
    const y = pad + (1 - (c - min) / range) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const up = closes[closes.length - 1] >= closes[0];
  const color = up ? "#ef4444" : "#22c55e";
  const area = `${pad},${h - pad} ` + pts.join(" ") + ` ${w - pad},${h - pad}`;
  return `<svg viewBox="0 0 ${w} ${h}" class="spark" preserveAspectRatio="none">
    <polygon points="${area}" fill="${color}1a"/>
    <polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>
  </svg>
  <div class="spark-cap"><span>${closes.length}日前 ${min}</span><span>最高 ${max}</span><span>現價 ${closes[closes.length - 1]}</span></div>`;
}

function openDetail(code) {
  const s = STOCKS.find((x) => x.c === code);
  if (!s) return;
  const topicTag = s.topic && s.topic !== "—" ? `<span class="badge topic">${s.topic}</span>` : "";
  const newsBlock = s.news && s.news.length
    ? `<div class="m-section">📰 ${s.topic} 相關新聞(近期)</div>
       <div class="news-list">${s.news.map((t) => `<div class="news-item">${t}</div>`).join("")}</div>`
    : "";
  document.getElementById("modal-body").innerHTML = `
    <div class="m-head">
      <div>
        <div class="m-name">${s.n}<span class="stock-code">${s.c}</span> ${topicTag}</div>
        <div class="m-px">${s.close || "—"} <span class="pill ${s.rec}">${REC_TEXT[s.rec]} ${s.score}</span></div>
      </div>
      <button class="m-close" id="m-close">✕</button>
    </div>
    <div class="m-section">近 ${s.closes ? s.closes.length : 0} 日走勢</div>
    ${sparkline(s.closes)}
    <div class="m-section">六面向評分</div>
    ${scoreBar(s)}
    ${newsBlock}
    <div class="m-section">籌碼與基本面</div>
    <div class="dl"><span class="k">三大法人</span><span class="v">${s.smart}</span></div>
    ${s.yoy != null ? `<div class="dl"><span class="k">月營收 YoY</span><span class="v ${s.yoy >= 0 ? "up" : "down"}">${s.yoy >= 0 ? "+" : ""}${s.yoy}%</span></div>` : ""}
    ${s.ov != null ? `<div class="dl"><span class="k">海外同業(5日)</span><span class="v ${s.ov >= 0 ? "up" : "down"}">${s.ov >= 0 ? "+" : ""}${s.ov}%</span></div>` : ""}
    <div class="dl"><span class="k">RSI</span><span class="v">${s.rsi}</span></div>
    <div class="dl"><span class="k">20日位置</span><span class="v">${s.pos}</span></div>
    <div class="m-section">參考進出場(程式估算,非投資建議)</div>
    <div class="dl"><span class="k">進場區</span><span class="v">${s.entry}</span></div>
    <div class="dl"><span class="k">停損 -5%</span><span class="v down">${s.stop}</span></div>
    <div class="dl"><span class="k">目標 +5% / +10%</span><span class="v up">${s.t1} → ${s.t2}</span></div>
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

// 題材熱度分頁:依新聞熱度排序,顯示題材榜 + 熱題個股
function renderTopic(box) {
  const heat = META.topic_heat || {};
  const ranked = Object.entries(heat).sort((a, b) => b[1] - a[1]);
  const maxHeat = Math.max(1, ...ranked.map((r) => r[1]));
  const bars = ranked.map(([name, h]) => {
    const stocks = STOCKS.filter((s) => s.topic === name);
    const chips = stocks.slice(0, 6).map((s) =>
      `<span class="t-chip" data-code="${s.c}">${s.n} ${s.score}</span>`).join("");
    return `<div class="topic-row">
      <div class="topic-head"><span class="topic-name">${name}</span>
        <span class="topic-heat">🔥 ${h} 則</span></div>
      <div class="topic-track"><span class="topic-fill" style="width:${(h / maxHeat) * 100}%"></span></div>
      <div class="topic-chips">${chips || '<span style="color:#cbd5e1;font-size:12px">候選股中無此題材</span>'}</div>
    </div>`;
  }).join("");
  box.innerHTML = `<div class="topic-wrap">${bars}</div>` + footNote();
  box.querySelectorAll(".t-chip").forEach((el) =>
    el.addEventListener("click", () => openDetail(el.dataset.code))
  );
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
  const rows = STOCKS.map((s) => `<tr data-code="${s.c}">
    <td>${s.n}<span class="stock-code">${s.c}</span></td>
    <td>${s.close || "—"}</td>
    <td style="color:${recColor(s.rec)};font-weight:700">${s.score}</td>
    <td>${s.s1}</td>
    <td class="${s.yoy >= 0 ? "up" : "down"}">${s.yoy != null ? s.yoy + "%" : "—"}</td>
    <td>${s.topic && s.topic !== "—" ? s.topic : "—"}</td></tr>`).join("");
  box.innerHTML = kpi + `<table><thead><tr>
    <th>股票</th><th>收盤</th><th>總分</th><th>法人</th><th>營收YoY</th><th>題材</th>
    </tr></thead><tbody>${rows}</tbody></table>` + footNote();
  box.querySelectorAll("tbody tr").forEach((el) =>
    el.addEventListener("click", () => openDetail(el.dataset.code))
  );
}

function footNote() {
  const s = META.sources || {};
  return `<div class="note">
    ⚠️ 本站為個人技術練習,所有評分與進出價皆由程式依公開資料自動估算,<b>非投資建議</b>,
    短線追高風險高,請自設停損。
    題材熱度為新聞則數的代理指標,不代表個股利多;分點(主力)資料${s.broker ? "已啟用" : "未啟用"}。
    資料來源:證交所(法人/融資券/月營收/價量)+ Yahoo Finance(台股歷史/海外同業)+ Google News(題材新聞)。
  </div>`;
}

boot();
