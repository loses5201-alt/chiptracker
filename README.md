# ChipTracker — 跟著大戶賺大錢

台股籌碼分析儀表板。**全自動、零伺服器、零金鑰**:每交易日由 GitHub Actions 抓取證交所
公開資料、計算籌碼評分、產出靜態 JSON,前端(GitHub Pages)只負責讀檔顯示。

🔗 線上版:https://loses5201-alt.github.io/chiptracker/

> ⚠️ 本站為個人技術練習,所有評分與進出價皆由程式依公開資料自動估算,**非投資建議**。

## 📱 手機當 App 用(PWA)

手機瀏覽器開上面網址 → 瀏覽器選單 → **「加入主畫面」**(iOS Safari:分享 → 加入主畫面)。
之後點主畫面圖示就是全螢幕 App:底部分頁列(潛伏/進場/期貨/自選+更多)、
離線也能看最後一次盤後資料。潛伏股「發動」推播由 Discord 負責(見下方推播設定)。

## 架構

```
GitHub Actions (每交易日 17:30 排程)
   └─ python -m fetcher.build    抓資料 → 算分 → 寫 data/*.json → 自動 commit
        └─ GitHub Pages          直接服務 index.html + data/*.json
```

- **前端**:`index.html` + `assets/`(原生 JS,無框架),只 `fetch` `data/*.json`。
- **後端**:`fetcher/`(純 Python 標準函式庫,零第三方相依)。
- **資料**:`data/`(由 Actions 自動更新並 commit)。

## 資料來源(皆證交所官方、免費)

| 資料 | 來源 | 對應評分 |
|------|------|----------|
| 個股日成交價量 | OpenAPI `STOCK_DAY_ALL` | s4 技術、s5 動能 |
| 三大法人買賣超 | RWD `fund/T86` | s1 法人 |
| 融資融券餘額 | OpenAPI `MI_MARGN` | s3 融資券 |
| 主力分點 | (預留,無官方免費源) | s2 中性值 |

評分六面向:s1 法人 22 / s2 融資 8 / s3 基本面 20 / s4 國際 20 / s5 題材 15 / s6 動能 15,
總分 ≥70 強力建議、≥55 可留意。s1/s3/s5 採 tanh 連續計分(防止入選股集體頂滿、失去排名鑑別)。
技術面/動能需累積足夠交易日後才有參考價值(歷史由 `data/history.json` 每日累積)。

## 驗證機制(不憑感覺、依數據)

- **單元測試**:`python -m unittest discover -s tests` — 鎖住評分已驗證行為,Actions 每日先跑
- **歷史回測**:`python -m analytics.historical_backtest` — 240 交易日回填五面向
  (含 MOPS 月營收歷史,依法定公布日延遲生效防 lookahead;報酬以訊號**次日**收盤進場)
- **權重健檢**:`data/weight_review.json` — 各面向填充率/區分度/相關,指出誰在排名、誰失效

## 本機執行

```powershell
# 產生資料
python -m fetcher.build

# 開站預覽
python -m http.server 8000
# 瀏覽器開 http://localhost:8000/
```

**一鍵看盤(Windows)**:直接雙擊專案根目錄的 **`啟動看盤.bat`** —— 會自動 `git pull` 抓最新資料、
開瀏覽器、啟動本機伺服器。關閉黑色視窗即停止。(直接雙擊 `index.html` 會因 `fetch` 本機 JSON
被瀏覽器擋而看不到資料,所以需要這個小伺服器。)

> 想直接看雲端最新版、免開伺服器:https://loses5201-alt.github.io/chiptracker/ (任何裝置瀏覽器皆可)。

## 部署備註

- GitHub → Settings → Actions → Workflow permissions 需設為 **Read and write**(讓 Actions 能 commit `data/`)。
- 首次可到 Actions 頁手動觸發 `daily-fetch` 跑一次。

## 手機推播設定(選用 — Discord)

潛伏股「發動」(放量突破)時,自動推一張訊息卡到 Discord 頻道,**手機裝 Discord App 就會收到通知**。
沒設定也不影響資料更新(`fetcher/notify.py` 偵測不到金鑰會自動略過)。

1. **建立 Webhook**:Discord 任一伺服器 → 你要收通知的頻道 → 編輯頻道 → 整合 → 建立 Webhook → 複製 Webhook URL。
2. **設成 GitHub Secret**:本 repo → Settings → Secrets and variables → Actions → New repository secret,
   名稱填 `DISCORD_WEBHOOK`、值貼 Webhook URL。
3. **手機收通知**:手機安裝 Discord App、登入同一伺服器、開啟該頻道通知即可。

之後每交易日 build 完會推「今日潛伏 Top5」;有股票發動時標紅推「🚀 發動快報」。同一交易日只推一次。
本機可先預覽訊息格式(不送出):`python -m fetcher.notify`。
