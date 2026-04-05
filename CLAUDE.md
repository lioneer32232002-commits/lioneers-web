# 新竹攻城獅 2025-26 賽季數據分析網站

## 專案目標
建立一個部署在 GitHub Pages 的靜態網站，以視覺化方式呈現新竹攻城獅本賽季的球員數據、比賽紀錄與進階分析，供球迷參考使用。無後端，純前端（HTML / CSS / JavaScript）。

---

## 技術架構
- **前端**：純靜態網站（Vanilla HTML + CSS + JS），無框架
- **圖表**：Chart.js 4.4.0（CDN 引入）
- **資料處理**：Python 3（NumPy、SciPy）— 離線產生 JSON
- **OG 圖片生成**：Node.js + `@napi-rs/canvas`
- **部署平台**：GitHub Pages（`/.nojekyll` 已設定）
- **資料格式**：`processed_data.json`（由 Python 腳本產生）

---

## 檔案結構（當前完整版）

```
lioneers-web/
├── index.html              # 單頁應用主頁（1344 行，含所有視覺化）
├── processed_data.json     # 前端讀取的預處理數據（~35KB）
├── process_data.py         # Python 資料管線腳本（656 行）
├── generate-og.js          # Node.js OG 圖片生成腳本（112 行）
├── og-image.png            # Social 分享圖片（1200×630 px）
├── robots.txt              # SEO 設定
├── .nojekyll               # 停用 GitHub Pages Jekyll 處理
├── .gitignore              # 排除 node_modules、.env 等
├── CLAUDE.md               # 本文件
└── data/                   # 原始逐場比賽資料
    ├── lioneer_player.txt  # 球員基本資料
    ├── lioneer.basic.txt   # 隊伍基線統計
    ├── 0307.txt ~ 0322.txt # 比賽資料（MM/DD 格式）
    └── 202501XX.txt ...    # 比賽資料（ISO 格式）
```

---

## 資料管線工作流程

### 更新資料步驟
1. 將新比賽的原始 JSON 資料放入 `data/` 目錄（命名格式：`MMDD.txt` 或 `YYYYMMDD.txt`）
2. 執行 Python 腳本重新生成 `processed_data.json`：
   ```bash
   python3 process_data.py
   ```
3. （可選）重新生成 OG 圖片：
   ```bash
   node generate-og.js
   ```
4. 將 `processed_data.json`（與 `og-image.png`）提交並推送，GitHub Pages 即自動更新

### process_data.py 核心功能
- 解析 `data/` 目錄下所有比賽檔案（排除 `EXCLUDE_FILES` 清單中的彙總檔案）
- 彙整 11 項球員統計：得分、籃板、助攻、抄截、火鍋、失誤、正負值、投籃%、三分%、三分數、罰球%
- 計算 ORtg / DRtg / NetRtg（全聯盟各隊）
- 建立球員對各對手正負值熱圖（heatmap）
- **蒙地卡羅模擬**（NumPy 向量化，100,000 次迭代）：
  - 模擬剩餘賽季（共 36 場制）
  - 第 1–3 名直接晉級季後賽，第 4–5 名進挑戰賽（Bo3，第 4 名有一勝優勢）
  - 半決賽 Bo5（主客 2-2-1），總冠軍賽 Bo7（主客 2-2-1-1-1）
  - 主場優勢：+5% 勝率
  - 輸出：進季後賽、進挑戰賽、進四強、進決賽、奪冠機率
- **統計分析**：
  - 各統計指標的 ROC 曲線與 AUC（勝負預測能力）
  - Youden's J 最佳閾值偵測
  - Mann-Whitney U 檢定（非參數，顯著指標篩選）
  - Rank-biserial correlation 效果量（r）
- **情境分析**：依三分%、失誤、助攻、投籃% 排名分為 4 類情境，計算各情境均值/標準差

### processed_data.json 結構
```json
{
  "meta":           { "generated", "total_games", "games_remaining" },
  "team_stats":     { "wins", "losses", "avg_pts", "avg_opp_pts", "win_rate" },
  "standings":      [ { "team", "wins", "losses", "games_played" } ],
  "league_rtg":     [ { "team", "ortg", "drtg", "netrtg" } ],
  "vs_summary":     { "<opponent>": { "w", "l", "avg_lion", "avg_opp" } },
  "heatmap":        [ { "player", "values": { "<opponent>": ±value } } ],
  "player_avg":     { "<player>": { "score", "rebounds", "assists", "efficiency", "plus_minus", ... } },
  "simulation":     { "prob_playoff", "prob_playin", "prob_semis", "prob_final", "prob_champ", "projected_wins" },
  "roc":            { "<stat>": { "auc", "curve", "threshold", "best": { "tpr", "fpr" } } },
  "scenario_chart": [ { "label", "lion_mean", "opp_mean", "lion_std", "opp_std", "win_rate", "stats" } ],
  "mann_whitney":   [ { "stat", "p_value", "effect_r", "wins", "losses", "significant" } ],
  "games":          [ { "date", "opp", "lion_score", "opp_score", "won" } ],
  "next_game":      { "opponent", "date", "win_prob_adjusted", ... }
}
```

---

## index.html 頁面架構

### 頁面 9 大分析模組（依順序）
| ID | 區塊名稱 | 說明 |
|---|---|---|
| `#next-game` | 下場比賽預測 | 勝率、歷史對戰紀錄 |
| — | 四情境得分預測 | Best/Ideal/Fair/Low 情境柱狀圖（Chart.js） |
| `#standings` | 聯盟積分榜 | 全聯盟 W-L-GP，季後賽入場標示 |
| — | 聯盟效率分析 | ORtg、DRtg、NetRtg 視覺化橫條 |
| — | 對手交手紀錄 | 各隊 W-L、均分、分差 |
| `#heatmap` | 正負值熱圖 | 球員對各對手正負值（色彩映射） |
| `#players` | 球員本季均值 | PPG、RPG、APG、抄截、火鍋、失誤、效率、正負值 |
| — | ROC 曲線分析 | 各統計指標預測勝負能力（Chart.js） |
| — | Mann-Whitney 分析 | 顯著統計指標（p < 0.05）散點圖 |

### JavaScript 渲染函式（index.html 內嵌）
```
renderStatsBar()          // 統計快覽列
renderForecastBar()       // 預測列（模擬結果）
renderNextGame()          // 下場預測
renderScenarioChart()     // 四情境圖（Chart.js）
renderStandings()         // 積分榜
renderLeagueRtg()         // 聯盟效率
renderVsSummary()         // 對手交手紀錄
renderHeatmap()           // 正負值熱圖
renderPlayerAvg()         // 球員均值表
renderROC()               // ROC 曲線（Chart.js）
renderMannWhitney()       // Mann-Whitney 散點圖（Chart.js）
renderUpdates()           // 最新動態（近 5 場）
```
資料來源統一從 `processed_data.json` 以 `fetch(..., { cache: 'no-store' })` 載入。

---

## 設計規範

### CSS 變數（色彩系統）
| 變數名稱 | 色碼 | 用途 |
|---|---|---|
| `--site-bg` | `#1a0a2e` | 頁面底色（深紫） |
| `--site-bg2` | `#3b1a6e` | 次要背景 |
| `--site-purple` | `#7b3fc4` | 主要強調色 |
| `--site-gold` | `#00e5ff` | 數字、標題強調（青藍色） |
| `--gold` | `#f0c040` | 次要金色強調 |

### 響應式斷點
- 桌機：最大寬度 `820px`（內容欄）
- 手機：`375px+`，表格支援水平滾動

### 文字處理
- 內嵌 JavaScript 函式自動在 CJK 字元與半形字元間插入空白（`addCJKSpacing()`）

### 背景裝飾
- SVG 電路板圖案（低透明度覆蓋層）

---

## 目前進度（截至 2026-04-05）

### 已完成
- [x] 完整單頁應用，9 個數據分析模組全部上線
- [x] Python 資料管線（蒙地卡羅模擬、ROC、Mann-Whitney、情境分析）
- [x] 所有視覺化元件（熱圖、ROC 曲線、情境柱狀圖、Mann-Whitney 散點圖）
- [x] OG 圖片自動生成（Node.js）
- [x] 響應式設計（手機、平板、桌機）
- [x] GitHub Pages 部署設定（`.nojekyll`、`robots.txt`）
- [x] 28 場比賽資料已處理

### 目前賽況（資料截至 2026-04-02）
- 戰績：16 勝 12 敗（勝率 57.14%）
- 聯盟排名：第 3 名
- 剩餘場數：8 場
- 預測總勝場：21 場
- 進季後賽機率：92%
- 奪冠機率：32%

---

## 開發指引（AI 助手注意事項）

### 修改資料展示
- **不要**直接在 `index.html` 硬編碼數字，所有數據來自 `processed_data.json`
- 修改資料結構時，需同步更新 `process_data.py`（產生端）與 `index.html`（消費端）的對應欄位

### 新增分析模組
1. 在 `process_data.py` 新增計算邏輯，並在輸出 dict 加入對應鍵值
2. 重新執行腳本生成 `processed_data.json`
3. 在 `index.html` 中新增對應 HTML 結構與 `render*()` 函式
4. 在頁面載入後的主函式呼叫新渲染函式

### 樣式修改
- 優先使用 CSS 變數（`var(--site-bg)` 等），不要使用硬編碼色碼
- 卡片元件使用 `glassmorphism` 風格：`backdrop-filter: blur()`、半透明背景

### 圖表（Chart.js）
- 所有圖表使用 Chart.js 4.4.0（CDN：`https://cdn.jsdelivr.net/npm/chart.js`）
- 配色遵循深色主題：背景透明或半透明，線條/點使用 `--site-gold` 或 `--site-purple`

### 新增比賽資料
```bash
# 1. 將新比賽資料放入 data/
# 2. 重新生成 JSON
python3 process_data.py
# 3. （可選）更新 OG 圖片
node generate-og.js
# 4. 提交更新
git add processed_data.json og-image.png
git commit -m "update: 加入 MMDD 比賽資料"
git push origin main
```

### 不應修改的檔案
- `data/*.txt`：原始資料，只增不改
- `og-image.png`：由腳本生成，不要手動編輯
- `.nojekyll`：GitHub Pages 必要設定，不要刪除

---

## 備註
- 資料來源：TPBL 官方 API（原始 JSON，手動下載後存入 `data/`）
- 非官方粉絲製作，純數據整理用途
- OG 圖片 URL 指向 Cloudflare Pages（含版本快取破壞參數）
