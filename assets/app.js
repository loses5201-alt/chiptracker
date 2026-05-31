// ChipTracker 前端邏輯
// 職責很單純:讀 data/*.json → 依分頁渲染畫面。所有運算都在後端(fetcher)做完了。

// 五項評分的標籤、滿分、顏色(對齊原版配色語彙)
const SCORES = [
  { k: "s1", label: "法人", max: 30, color: "#3b82f6" },
  { k: "s2", label: "分點", max: 20, color: "#8b5cf6" },
  { k: "s3", label: "融資券", max: 15, color: "#f59e0b" },
  { k: "s4", label: "技術", max: 20, color: "#22c55e" },
  { k: "s5", label: "動能", max: 15, color: "#ec4899" },
];
const REC_TEXT = { strong: "強力建議", mid: "可留意", watch: "觀察" };
const TABS = [
  { k: "entry", t: "進場建議" },
  { k: "foreign", t: "法人動向" },
  { k: "margin", t: "融資券" },
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
  const broker = META.sources && META.sources.broker ? "已啟用" : "未啟用";
  document.getElementById("meta").innerHTML =
    `掃描母體 <b>${META.universe || 0}</b> 檔(已排除 ETF) · ` +
    `交易日 <b>${META.trading_date || "—"}</b> · ` +
    `已累積 <b>${META.history_days || 0}</b> 個交易日 · ` +
    `分點資料 <b>${broker}</b> · 更新 ${upd}`;
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
  if (view === "margin") list.sort((a, b) => b.s3 - a.s3);
  box.innerHTML = `<div class="grid">${list.map(card).join("")}</div>` + footNote();
}

function scoreBar(s) {
  // s2(分點)資料源未啟用時淡化標示,誠實呈現「目前是中性值」
  const brokerOn = META.sources && META.sources.broker;
  return SCORES.map((d) => {
    const off = d.k === "s2" && !brokerOn;
    const pct = Math.round((s[d.k] / d.max) * 100);
    return `<div class="score-row">
      <span class="score-label ${off ? "off" : ""}">${d.label}</span>
      <span class="score-track"><span class="score-fill" style="width:${pct}%;background:${off ? "#cbd5e1" : d.color}"></span></span>
      <span class="s-val">${s[d.k]}/${d.max}</span></div>`;
  }).join("");
}

function card(s) {
  const badges = (s.reason || []).map((r) => `<span class="badge">${r}</span>`).join("");
  return `<div class="card">
    <div class="card-top">
      <div>
        <div class="stock-name">${s.n}<span class="stock-code">${s.c}</span></div>
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
    <div class="box"><div class="n">${META.universe || 0}</div><div class="l">掃描母體(不含 ETF)</div></div>
    <div class="box"><div class="n" style="color:#ef4444">${strong}</div><div class="l">強力建議</div></div>
    <div class="box"><div class="n" style="color:#d97706">${mid}</div><div class="l">可留意</div></div>
    <div class="box"><div class="n">${META.history_days || 0}</div><div class="l">已累積交易日</div></div>
  </div>`;
  const rows = STOCKS.map((s) => `<tr>
    <td>${s.n}<span class="stock-code">${s.c}</span></td>
    <td>${s.close || "—"}</td>
    <td style="color:${recColor(s.rec)};font-weight:700">${s.score}</td>
    <td>${s.s1}</td><td>${s.s3}</td><td>${s.pos}</td>
    <td style="text-align:left">${s.smart}</td></tr>`).join("");
  box.innerHTML = kpi + `<table><thead><tr>
    <th>股票</th><th>收盤</th><th>總分</th><th>法人</th><th>融資券</th><th>位置</th><th>籌碼</th>
    </tr></thead><tbody>${rows}</tbody></table>` + footNote();
}

function footNote() {
  const brokerOn = META.sources && META.sources.broker;
  return `<div class="note">
    ⚠️ 本站為個人技術練習,所有評分與進場/停損/目標價皆由程式依公開資料自動估算,
    <b>非投資建議</b>。技術面與動能需累積足夠交易日後才有參考價值
    (目前累積 ${META.history_days || 0} 日)。
    分點(主力)資料目前${brokerOn ? "已啟用" : "未啟用,以中性值計分"}。
    資料來源:臺灣證券交易所公開資料(三大法人 T86、融資融券 MI_MARGN、個股日成交)。
  </div>`;
}

boot();
