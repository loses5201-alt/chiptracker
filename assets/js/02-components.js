// 共用元件:雷達圖/卡片/走勢圖/分數條/個股詳情 modal
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
    grid += `<polygon points="${poly}" fill="none" stroke="var(--line)" stroke-width="1"/>`;
  }
  // 軸線
  let axes = "";
  for (let i = 0; i < n; i++) {
    const [x, y] = ptAt(i, R);
    axes += `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="var(--line)" stroke-width="1"/>`;
  }
  // 資料多邊形
  const dataPts = SCORES.map((d, i) => {
    const val = Math.max(0, Math.min(1, s[d.k] / d.max));
    return ptAt(i, R * val).map((v) => v.toFixed(1)).join(",");
  });
  const poly = `<polygon points="${dataPts.join(" ")}" fill="url(#radarFill)" stroke="var(--acc)" stroke-width="2" stroke-linejoin="round"/>`;
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
      labels += `<text x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="${anchor}" font-size="11" fill="var(--tx2)" font-weight="500">${d.label}</text>`;
    });
  }
  return `<svg viewBox="0 0 ${vbW} ${size}" class="radar" width="${vbW}" height="${size}">
    <defs><radialGradient id="radarFill"><stop offset="0%" stop-color="var(--acc)" stop-opacity="0.3"/><stop offset="100%" stop-color="var(--acc)" stop-opacity="0.08"/></radialGradient></defs>
    ${grid}${axes}${poly}${dots}${labels}</svg>`;
}

// 分數顯示統一取整(後端偶有浮點殘差,如 80.60000000000001)
function fmtScore(v) { return v != null ? Math.round(v) : "—"; }

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
    ? `<div class="card-news">${s.news[0]}</div>` : "";
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
        <div class="score-ring ${s.rec}"><span>${fmtScore(s.score)}</span><small>分</small></div>
        <div class="pill ${s.rec}">${REC_TEXT[s.rec]}</div>
      </div>
    </div>
    ${miniBars(s)}
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

// 六面向迷你橫條:卡片上取代雷達圖(橫條掃讀更快,雷達留在詳情 modal)
function miniBars(s) {
  return `<div class="mini-bars">${SCORES.map((d) => {
    const pct = Math.round(Math.max(0, Math.min(1, s[d.k] / d.max)) * 100);
    return `<div class="mb-row"><span class="mb-k">${d.label}</span>
      <span class="mb-track"><span class="mb-fill" style="width:${pct}%;background:${d.color}"></span></span>
      <span class="mb-v">${s[d.k]}/${d.max}</span></div>`;
  }).join("")}</div>`;
}

// 卡片指標小格(2×2,label 左 + 值右,不擠不換行)
function statBox(k, v, positive) {
  const cls = positive === null ? "" : positive ? "up" : "down";
  return `<div class="ms-box"><span class="ms-k">${k}</span><span class="ms-v ${cls}">${v}</span></div>`;
}

function recColor(rec) {
  return { strong: "var(--up)", mid: "var(--gold)", watch: "var(--tx3)" }[rec] || "var(--tx3)";
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
  const color = up ? "var(--up)" : "var(--dn)";
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
  const lead = `<b>${s.n}</b>(${s.c})以 <b>${fmtScore(s.score)} 分</b>列為「${recTxt}」,主要因為:`;
  const body = parts.length ? parts.join("、") + "。" : "六面向分數綜合達標。";
  const risks = [];
  if (s.pos >= 85) risks.push(`位階偏高(區間位置 ${s.pos}),宜等拉回或嚴設停損`);
  if (typeof s.rsi === "number" && s.rsi >= 80) risks.push(`RSI ${s.rsi} 過熱`);
  if (s.s1 / 22 < 0.4) risks.push("法人參與度偏低");
  if (s.yoy != null && s.yoy < 0) risks.push(`月營收年減 ${s.yoy}%`);
  const riskTxt = risks.length ? `<div class="why-risk">留意:${risks.join("、")}。</div>` : "";
  return `<div class="why">${lead}${body}${riskTxt}</div>`;
}

function openDetail(code) {
  const s = STOCKS.find((x) => x.c === code);
  if (!s) return;
  const topicTag = s.topic && s.topic !== "—" ? `<span class="badge topic">${s.topic}</span>` : "";
  const newsBlock = s.news && s.news.length
    ? `<div class="m-section">${s.topic} 相關新聞(近期)</div>
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
      <span class="ct-note" style="${below ? "color:var(--gold);font-weight:600" : ""}">${note}</span></div>`;
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
        <div class="m-px">${s.close || "—"} <span class="pill ${s.rec}">${REC_TEXT[s.rec]} ${fmtScore(s.score)}分</span></div>
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

