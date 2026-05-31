# ChipTracker — 跟著大戶賺大錢

台股籌碼分析儀表板。**全自動、零伺服器、零金鑰**:每交易日由 GitHub Actions 抓取證交所
公開資料、計算籌碼評分、產出靜態 JSON,前端(GitHub Pages)只負責讀檔顯示。

🔗 線上版:https://loses5201-alt.github.io/chiptracker/

> ⚠️ 本站為個人技術練習,所有評分與進出價皆由程式依公開資料自動估算,**非投資建議**。

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

評分 s1~s5 滿分分別為 30 / 20 / 15 / 20 / 15,總分 ≥72 強力建議、≥55 可留意。
技術面/動能需累積足夠交易日後才有參考價值(歷史由 `data/history.json` 每日累積)。

## 本機執行

```powershell
# 產生資料
python -m fetcher.build

# 開站預覽
python -m http.server 8000
# 瀏覽器開 http://localhost:8000/
```

## 部署備註

- GitHub → Settings → Actions → Workflow permissions 需設為 **Read and write**(讓 Actions 能 commit `data/`)。
- 首次可到 Actions 頁手動觸發 `daily-fetch` 跑一次。
