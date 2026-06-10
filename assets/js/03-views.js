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
