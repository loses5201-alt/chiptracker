// 主力潛伏/做空標的/查詢自選/頁尾/主題切換
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
  const strong = SHORTS.filter((s) => s.rec === "strong").length;
  const hiPledge = SHORTS.filter((s) => (s.pledge || 0) >= 40).length;
  const rc = {};
  SHORTS.forEach((s) => (s.reason || []).forEach((r) => { rc[r] = (rc[r] || 0) + 1; }));
  const topR = Object.entries(rc).sort((a, b) => b[1] - a[1])[0];
  const analysis = `<div class="list-analysis short"><div class="la-t">📊 做空標的分析</div><div class="la-b">今日 <b>${SHORTS.length}</b> 檔做空訊號,其中 <b class="down">${strong}</b> 檔強訊號${hiPledge ? `、<b>${hiPledge}</b> 檔董監設質≥40%(股價跌易斷頭追繳、助跌)` : ""}。最常見做空理由:<b>${topR ? topR[0] : "—"}</b>。做空優先挑「漲多+營收沒跟上+法人出貨」三者俱全的,風險高務必停損。</div></div>`;
  box.innerHTML = intro + analysis + `<div class="grid">${SHORTS.map((s, i) => shortCard(s, i)).join("")}</div>` + footNote();
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

