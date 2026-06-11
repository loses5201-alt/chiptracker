// 分頁:題材/回測(健檢+歷史+潛伏回測)/總覽/大盤溫度計
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
  const totalNews = ranked.reduce((a, r) => a + r[1], 0);
  const hot = ranked[0];
  const analysis = hot ? `<div class="list-analysis"><div class="la-t">📊 題材熱度分析</div><div class="la-b">今日最熱題材 <b class="up">${hot[0]}</b>(🔥 ${hot[1]} 則新聞、推薦股 ${STOCKS.filter((s) => s.topic === hot[0]).length} 檔),全題材近 3 日共 <b>${totalNews}</b> 則新聞。題材熱度高=市場資金正聚焦,但<b>追題材要搭配法人買超</b>,別追在熱度退燒的題材尾聲。</div></div>` : "";
  box.innerHTML = analysis + `<div class="topic-wrap">${bars}</div>` + footNote();
  box.querySelectorAll(".t-chip").forEach((el) =>
    el.addEventListener("click", () => openDetail(el.dataset.code))
  );
}

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
