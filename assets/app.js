// ChipTracker 前端邏輯(短線狙擊版)
// 職責:讀 data/*.json → 依分頁渲染。所有運算都在後端(fetcher)做完。

const SCORES = [
  { k: "s1", label: "法人", max: 25, color: "#3b82f6" },
  { k: "s2", label: "融資", max: 15, color: "#8b5cf6" },
  { k: "s3", label: "基本面", max: 20, color: "#22c55e" },
  { k: "s4", label: "國際", max: 20, color: "#06b6d4" },
  { k: "s5", label: "動能", max: 20, color: "#ec4899" },
];
const REC_TEXT = { strong: "強力建議", mid: "可留意", watch: "觀察" };
const TABS = [
  { k: "entry", t: "進場建議" },
  { k: "foreign", t: "法人動向" },
  { k: "fund", t: "基本面" },
  { k: "intl", t: "國際連動" },
  { k: "overview", t: "總覽" },
];

let STOCKS = [];
let META = {};
let view = "entry";

async function boot() {
  try {
    [STOCKS, META] = await Promise.all([
      fetch("data/stocks.json").then((r) => r.json()),
      fetch("data/meta.json").then((r) => r.json()),
    ]);
  } catch (e) {
    document.getElementById("content").innerHTML =
      '<div class="empty">尚無資料。請先讓 GitHub Actions 跑過一次,或本機執行 <code>python -m fetcher.build</code></div>';
    return;
  }
  renderMeta();
  renderTabs();
  render();
}

function renderMeta() {
  const upd = META.updated_at ? META.updated_at.replace("T", " ").slice(0, 16) : "—";
  const s = META.sources || {};
  document.getElementById("meta").innerHTML =
    `掃描母體 <b>${META.universe || 0}</b> 檔 · 交易日 <b>${META.trading_date || "—"}</b> · ` +
    `累積 <b>${META.history_days || 0}</b> 日 · ` +
    `基本面 <b>${s.fundamentals ? "✓" : "✗"}</b> · 國際 <b>${s.overseas ? "✓" : "✗"}</b> · ` +
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
  let list = [...STOCKS];
  if (view === "foreign") list.sort((a, b) => b.s1 - a.s1);
  if (view === "fund") list = list.filter((s) => s.yoy != null).sort((a, b) => b.s3 - a.s3);
  if (view === "intl") list = list.filter((s) => s.topic !== "—").sort((a, b) => b.s4 - a.s4);
  if (!list.length) { box.innerHTML = '<div class="empty">此分頁暫無符合資料(可能尚未累積或非追蹤題材)</div>' + footNote(); return; }
  box.innerHTML = `<div class="grid">${list.map(card).join("")}</div>` + footNote();
}

function scoreBar(s) {
  const brokerOn = META.sources && META.sources.broker;
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
  const topicTag = s.topic && s.topic !== "—"
    ? `<span class="badge topic">${s.topic}</span>` : "";
  return `<div class="card">
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
    <div class="pos-wrap">
      <div style="font-size:12px;color:#16a34a">20 日區間位置</div>
      <div class="pos-track"><span class="pos-dot" style="left:${s.pos}%"></span></div>
      <div class="pos-cap"><span>低</span><span>${s.pos}</span><span>高</span></div>
    </div>
    <div class="detail">
      <div class="dl"><span class="k">籌碼</span><span class="v">${s.smart}</span></div>
      ${s.yoy != null ? `<div class="dl"><span class="k">月營收 YoY</span><span class="v ${s.yoy >= 0 ? "up" : "down"}">${s.yoy >= 0 ? "+" : ""}${s.yoy}%</span></div>` : ""}
      ${s.ov != null ? `<div class="dl"><span class="k">海外同業(5日)</span><span class="v ${s.ov >= 0 ? "up" : "down"}">${s.ov >= 0 ? "+" : ""}${s.ov}%</span></div>` : ""}
      <div class="dl"><span class="k">進場區</span><span class="v">${s.entry}</span></div>
      <div class="dl"><span class="k">停損 / 目標</span><span class="v">${s.stop} / ${s.t1}→${s.t2}</span></div>
      <div class="dl"><span class="k">RSI / 量</span><span class="v">${s.rsi} / ${s.vol}</span></div>
    </div>
  </div>`;
}

function recColor(rec) {
  return { strong: "#ef4444", mid: "#d97706", watch: "#64748b" }[rec] || "#64748b";
}

function renderOverview(box) {
  const strong = STOCKS.filter((s) => s.rec === "strong").length;
  const mid = STOCKS.filter((s) => s.rec === "mid").length;
  const kpi = `<div class="kpi">
    <div class="box"><div class="n">${META.universe || 0}</div><div class="l">掃描母體</div></div>
    <div class="box"><div class="n" style="color:#ef4444">${strong}</div><div class="l">強力建議</div></div>
    <div class="box"><div class="n" style="color:#d97706">${mid}</div><div class="l">可留意</div></div>
    <div class="box"><div class="n">${META.history_days || 0}</div><div class="l">已累積交易日</div></div>
  </div>`;
  const rows = STOCKS.map((s) => `<tr>
    <td>${s.n}<span class="stock-code">${s.c}</span></td>
    <td>${s.close || "—"}</td>
    <td style="color:${recColor(s.rec)};font-weight:700">${s.score}</td>
    <td>${s.s1}</td><td>${s.s2}</td>
    <td class="${s.yoy >= 0 ? "up" : "down"}">${s.yoy != null ? s.yoy + "%" : "—"}</td>
    <td>${s.topic !== "—" ? s.topic : "—"}</td></tr>`).join("");
  box.innerHTML = kpi + `<table><thead><tr>
    <th>股票</th><th>收盤</th><th>總分</th><th>法人</th><th>融資</th><th>營收YoY</th><th>題材</th>
    </tr></thead><tbody>${rows}</tbody></table>` + footNote();
}

function footNote() {
  const s = META.sources || {};
  return `<div class="note">
    ⚠️ 本站為個人技術練習,所有評分與進出價皆由程式依公開資料自動估算,<b>非投資建議</b>,
    短線追高風險高,請自設停損。技術/動能需累積足夠交易日才有意義(目前 ${META.history_days || 0} 日)。
    分點(主力)資料${s.broker ? "已啟用" : "未啟用"};題材新聞面尚未納入。
    資料來源:證交所(法人/融資券/月營收/價量)+ Stooq(海外同業)。
  </div>`;
}

boot();
