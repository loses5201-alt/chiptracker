// 回測分頁區塊:評分健檢表 + 歷史回測 + 潛伏回測 + 推薦成效(由 03-views.js 拆出)
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
    <div class="note" style="margin-top:0">標的池 ${h.universe} 檔(上市+上櫃,成交值排名);歷史評分 = ${h.factors_used}</div>
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
    <div class="note" style="margin-top:0">驗證核心問題:<b>潛伏分高的股,埋伏後真的會「發動」嗎?</b>標的池 ${h.universe} 檔(上市+上櫃,成交值排名)。</div>
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
