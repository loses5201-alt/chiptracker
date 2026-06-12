// 期貨風向分頁 + 瀏覽器端 TAIFEX enrich(台灣IP補抓地理敏感端點)
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

// 期貨擴充 enrich:地理敏感端點(雲端 US runner 常被 TAIFEX 擋)改由「使用者瀏覽器(台灣IP)
// 直接抓」(TAIFEX 開 CORS *)。build 只給可靠核心,這裡補散戶多空比/前五大特定法人/個股期貨。
let FUT_ENRICHED = false;
const TAIFEX = "https://openapi.taifex.com.tw/v1";
function fnum(s) { return parseFloat(String(s).replace(/,/g, "")) || 0; }

async function enrichFutures() {
  if (!FUTURES || FUT_ENRICHED) return;
  FUT_ENRICHED = true;   // 只跑一次,避免每次切分頁重抓(813KB 行情檔)
  const get = (p) => fetch(TAIFEX + p).then((r) => r.text()).then((t) => (t.trim() ? JSON.parse(t) : null)).catch(() => null);
  try {
    const needPc = !FUTURES.pc || FUTURES.pc.oi_ratio == null;
    const [pc, fm, lt, ssfl] = await Promise.all([
      needPc ? get("/PutCallRatio") : Promise.resolve(null),
      get("/DailyMarketReportFut"), get("/OpenInterestOfLargeTradersFutures"), get("/SSFLists"),
    ]);
    let changed = false;
    if (pc && pc[0]) { FUTURES.pc = { oi_ratio: fnum(pc[0]["PutCallOIRatio%"]), vol_ratio: fnum(pc[0]["PutCallVolumeRatio%"]) }; changed = true; }
    if (fm && fm.length) {
      const mtxOi = fm.filter((r) => r.Contract === "MTX").reduce((a, r) => a + fnum(r.OpenInterest), 0);
      if (mtxOi && FUTURES.mtx_net != null) {
        FUTURES.retail = { ratio: Math.round(-FUTURES.mtx_net / mtxOi * 1000) / 10, mtx_oi: mtxOi, inst_net: FUTURES.mtx_net };
        changed = true;
      }
      if (ssfl && ssfl.length) {
        const map = {}; ssfl.forEach((r) => { map[r.Contract] = r; });
        const byStock = {};
        fm.forEach((r) => { const m = map[r.Contract]; if (m) { (byStock[m.StockCode] = byStock[m.StockCode] || { name: m.StockName, oi: 0 }).oi += fnum(r.OpenInterest); } });
        FUTURES.ssf = FUTURES.ssf || {};
        FUTURES.ssf.top = Object.entries(byStock).sort((a, b) => b[1].oi - a[1].oi).slice(0, 10).map(([sc, v]) => ({ code: sc, name: v.name, oi: v.oi }));
        changed = true;
      }
    }
    if (lt && lt.length) {
      const b = lt.find((r) => r.Contract === "TX" && r.SettlementMonth === "999912" && r.TypeOfTraders === "1");
      if (b) { FUTURES.big5 = { tx_net: fnum(b.Top5Buy) - fnum(b.Top5Sell), market_oi: fnum(b.OIOfMarket) }; changed = true; }
    }
    if (changed && view === "futures") renderFutures(document.getElementById("content"));
  } catch (e) { /* 瀏覽器抓不到(非台灣IP/離線)→ 維持 build 核心,缺的顯示資料暫缺 */ }
}

function renderFutures(box) {
  const f = FUTURES;
  if (!f || !f.tx) {
    box.innerHTML = '<div class="empty" style="padding:50px">期貨資料尚未產生(下次自動更新後出現)</div>' + footNote();
    return;
  }
  const h = f.history || [];
  const pc = f.pc ? f.pc.oi_ratio : null;        // 各面向可能因端點暫缺為 null,互不影響
  const retail = f.retail || null, big5 = f.big5 || null, ssf = f.ssf || {};
  const rRatio = retail ? retail.ratio : null, b5net = big5 ? big5.tx_net : null;

  // 綜合多空訊號分析:各面向轉「多/空」票統計傾向。缺資料的面向不投票(null 不當 0,避免誤判)
  const sig = [];
  const add = (cond, side, txt) => { if (cond) sig.push({ side, txt }); };
  add(f.tx.foreign > 10000, "多", "外資台指期淨多單"); add(f.tx.foreign < -10000, "空", "外資台指期淨空單");
  add(b5net != null && b5net > 3000, "多", "前五大特定法人偏多"); add(b5net != null && b5net < -3000, "空", "前五大特定法人偏空");
  add(rRatio != null && rRatio > 15, "空", "散戶偏多(反指標)"); add(rRatio != null && rRatio < -15, "多", "散戶偏空(反指標)");
  add(pc != null && pc >= 120, "多", "P/C比偏高(低檔有撐)"); add(pc != null && pc <= 80, "空", "P/C比偏低(過度樂觀)");
  const bull = sig.filter((s) => s.side === "多").length, bear = sig.filter((s) => s.side === "空").length;
  const compCls = bull > bear ? "bull" : bear > bull ? "bear" : "neutral";
  const compTag = bull > bear ? "偏多" : bear > bull ? "偏空" : "中性";

  const intro = `<div class="fut-intro"><b>期貨風向(大盤多空)</b> — 個股籌碼看「誰買哪檔」,期貨籌碼看「大戶對整個大盤的押注」。下方<b>綜合判讀</b>把外資/大戶/散戶/選擇權各面向匯總成多空傾向。資料日 ${f.date}。程式訊號、非投資建議。</div>`;

  // 綜合判讀面板(多空票數 + 各訊號)
  const sigChips = sig.map((s) => `<span class="sig-chip ${s.side === "多" ? "up" : "down"}">${s.txt}</span>`).join("");
  const verdict = `<div class="fut-verdict ${compCls}">
    <div class="fv-tag">${compTag}</div>
    <div class="fv-mid"><div class="fv-tally"><b class="up">${bull}</b> 多 <span class="muted">/</span> <b class="down">${bear}</b> 空</div>
      <div class="fv-sigs">${sigChips || "今日訊號不明顯"}</div></div>
  </div>`;

  const oiCards = `<div class="fut-sec-t">台指期三大法人未平倉</div><div class="fut-oi-grid">
    ${futOiCard("外資台指期", f.tx.foreign, f.tx.foreign_day, h.map((x) => x.foreign))}
    ${futOiCard("投信台指期", f.tx.trust, f.tx.trust_day, h.map((x) => x.trust))}
    ${futOiCard("自營台指期", f.tx.dealer, f.tx.dealer_day, h.map((x) => x.dealer))}
  </div>`;

  // 大戶 vs 散戶(缺資料的卡片顯示「資料暫缺」,不影響另一張)
  const b5Read = b5net == null ? "資料暫缺" : b5net > 3000 ? "押多" : b5net < -3000 ? "押空" : "中性";
  const rRead = rRatio == null ? "資料暫缺" : rRatio > 15 ? "散戶偏多 → 反指偏空" : rRatio < -15 ? "散戶偏空 → 反指偏多" : "散戶中性";
  const b5Spark = miniSpark(h.map((x) => x.big5).filter((v) => v != null), 90, 22);
  const rSpark = miniSpark(h.map((x) => x.retail).filter((v) => v != null), 90, 22);
  const vsBlock = `<div class="fut-sec-t">大戶 vs 散戶</div><div class="fut-vs">
    <div class="fvs-card">
      <div class="fvs-k">前五大特定法人 · 台指期淨(外資主力)</div>
      <div class="fvs-v ${(b5net || 0) >= 0 ? "up" : "down"}">${b5net == null ? "—" : fmtKou(b5net)}</div>
      <div class="fvs-read">${b5Read}</div>${b5Spark}
    </div>
    <div class="fvs-card">
      <div class="fvs-k">散戶多空比(小台,反指標)</div>
      <div class="fvs-v ${(rRatio || 0) >= 0 ? "up" : "down"}">${rRatio == null ? "—" : (rRatio >= 0 ? "+" : "") + rRatio + "%"}</div>
      <div class="fvs-read">${rRead}</div>${rSpark}
    </div>
  </div>`;

  // 選擇權 P/C(缺資料顯示 —)
  const pcRead = pc == null ? "資料暫缺" : pc >= 120 ? "偏多(避險 Put 多、低點有撐)" : pc <= 80 ? "偏空(樂觀過頭)" : "中性";
  const pcCls = pc == null ? "" : pc >= 120 ? "up" : pc <= 80 ? "down" : "";
  const pcSpark = miniSpark(h.map((x) => x.pc_oi).filter((v) => v != null), 80, 22);
  const pcBlock = `<div class="fut-sec-t">選擇權情緒</div><div class="fut-pc">
    <div class="fpc-row"><span class="fpc-k">Put/Call 未平倉比</span>
      <b class="fpc-v ${pcCls}">${pc == null ? "—" : pc + "%"}</b><span class="fpc-read">${pcRead}</span>${pcSpark}</div>
    <div class="fpc-row"><span class="fpc-k">成交量 P/C 比</span><b class="fpc-v">${f.pc && f.pc.vol_ratio != null ? f.pc.vol_ratio + "%" : "—"}</b></div>
  </div>`;

  // 個股期貨
  const ssfRows = (ssf.top || []).map((s, i) =>
    `<tr><td class="sr-rank">${i + 1}</td><td class="sr-name">${s.name}<span class="ssf-code">${s.code}</span></td><td class="sr-oi">${(s.oi || 0).toLocaleString()} 口</td></tr>`).join("");
  const ssfBlock = `<div class="fut-sec-t">個股期貨</div><div class="fut-ssf">
    <div class="fssf-inst">
      <span class="fssf-i">法人整體未平倉:</span>
      <span class="fssf-i">外資 <b class="${(ssf.foreign || 0) >= 0 ? "up" : "down"}">${fmtKou(ssf.foreign || 0)}</b></span>
      <span class="fssf-i">投信 <b class="${(ssf.trust || 0) >= 0 ? "up" : "down"}">${fmtKou(ssf.trust || 0)}</b></span>
      <span class="fssf-i">自營 <b class="${(ssf.dealer || 0) >= 0 ? "up" : "down"}">${fmtKou(ssf.dealer || 0)}</b></span>
    </div>
    <div class="fssf-sub">未平倉前十大(大戶布局的個股)</div>
    <table class="ssf-table"><tbody>${ssfRows || '<tr><td colspan="3">—</td></tr>'}</tbody></table>
  </div>`;

  const enriching = !FUT_ENRICHED && (rRatio == null || b5net == null || !(ssf.top && ssf.top.length));
  box.innerHTML = intro + verdict + oiCards + vsBlock + pcBlock + ssfBlock +
    `<div class="fut-note">怎麼看:<b>外資台指期/前五大特定法人</b>淨多(紅/正)=大戶押漲、淨空(綠/負)=押跌;
     <b>散戶多空比</b>是反指標(散戶越偏多越要小心);<b>P/C 未平倉比</b>偏高常代表低檔有撐;
     <b>個股期貨未平倉</b>大的個股是大戶在期貨市場重押的標的。趨勢需逐日累積(目前 ${h.length} 日)。${enriching ? '<br><span class="fut-loading">散戶/大額交易人/個股期貨資料載入中(由瀏覽器即時向期交所取得)…</span>' : ""}</div>` +
    footNote();
  enrichFutures();   // 由瀏覽器(台灣IP)補抓地理敏感端點,完成後自動重繪
}

// 載入骨架(資料抓取期間的佔位,取代純文字「載入中」)
function renderSkeleton() {
  const sk = `<div class="sk-card"><div class="sk-line w60"></div><div class="sk-line w40"></div>
    <div class="sk-radar"></div><div class="sk-line"></div><div class="sk-line w80"></div></div>`;
  document.getElementById("content").innerHTML = `<div class="grid">${sk.repeat(6)}</div>`;
}

// ── 主力潛伏(起漲前布局:大戶吃貨、還沒發動)──
