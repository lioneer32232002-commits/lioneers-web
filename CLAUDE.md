# 新竹攻城獅 2025-26 賽季數據分析網站

## 專案目標
建立一個部署在 Cloudflare Pages 的靜態網站，以視覺化方式呈現新竹攻城獅本賽季的球員數據、比賽紀錄與進階分析，供球迷參考使用。無後端，純前端（HTML / CSS / JavaScript）。

## 技術架構
- 純靜態網站（HTML + CSS + JS），不需要伺服器
- 圖表：Chart.js（CDN 引入）
- 部署平台：Cloudflare Pages（https://lioneers-web.pages.dev/）
- OG 圖片：Node.js + @napi-rs/canvas 產生（generate-og.js）
- 配色：深紫色系（`--site-bg: #1a0a2e` 為底色）

## 目前進度
- [x] 建立專案資料夾
- [x] `index.html` 首頁（含所有分析區塊）
- [x] `processed_data.json` 資料檔（每次賽季更新手動更新）
- [x] `generate-og.js` 自動產生 og-image.png
- [x] 部署到 Cloudflare Pages（上線中）
- [x] FB / LINE 分享縮圖（og:image）正常顯示

## 檔案結構（目前）
```
lioneers-web/
├── index.html              # 首頁（唯一頁面）
├── processed_data.json     # 所有數據（standings、simulation、heatmap 等）
├── og-image.png            # FB/LINE 分享縮圖（由 generate-og.js 產生）
├── generate-og.js          # OG 圖片產生腳本（Node.js）
├── robots.txt
├── .nojekyll
├── data/                   # 原始比賽 JSON（每場一檔）
└── CLAUDE.md
```

## 首頁區塊（index.html）
1. 統計快覽（勝場/敗場/均得分/均失分/剩餘場次）
2. 預測摘要（預測最終勝場 / 進季後賽機率 / 奪冠機率）
3. 下一場資訊
4. 聯盟排名（standings）
5. 聯盟每百回合效率（league_rtg，netrtg 排序）
6. 對各隊戰績卡片
7. 球員 vs 各對手 Plus/Minus 熱力圖
8. 球員 vs 各對手 PPP 熱力圖
9. 球員賽季均值表
10. ROC 曲線（得分預測）
11. 情境模擬圖表
12. Mann-Whitney 統計
13. 最新比賽紀錄

## 數據更新流程
1. 使用者提供新賽季 JSON 數據（貼上或放入 data/ 資料夾）
2. 跑 Python 腳本計算新的 ortg / drtg / netrtg / Monte Carlo 模擬
3. 更新 processed_data.json（standings、league_rtg、simulation、meta）
4. 更新 og:description（index.html 第 9 行）並將 og:image 版號 +1
5. 執行 `node generate-og.js` 重新產生 og-image.png
6. commit → push → merge PR → Cloudflare 自動部署

## 工作流程
- 使用者說「merge 過了」時，立即建下一個 PR 並回傳網址，不用等使用者再問。
- PR merge 成功後，只回報 Cloudflare 部署網址，不重複複述做了什麼。有異常才說明，沒問題就安靜。
- 每次修改完成後，直接 commit + push，不需停下來請使用者確認。使用者從真實網站自行驗證。

## 更新後驗證清單
每次 processed_data.json 或 index.html 有變動，commit 前必須明確列出：
1. **哪些區塊數據有變動**（例：standings 更新、simulation 機率改變）
2. **哪些區塊沒有異動**（明確說「其餘區塊數據不變」）
3. **og:image 版號是否已 +1**（每次更新必做，否則 FB/LINE 不重新抓圖）
4. **og:description 是否已更新**（index.html 第 9 行）

驗證通過才 commit，不通過不送 PR。

## 反模式清單（禁止事項）
以下是常見錯誤，每次修改前自我檢查：
- **聯盟名稱**：永遠寫 TPBL，不寫 PLG（PLG 是另一個聯盟）
- **熱力圖顏色**：只用已定義六色階（深紫→珊瑚紅），不用漸層或其他配色
- **數字呈現**：單一數字沒有上下文對比時不單獨呈現，需搭配排名或趨勢
- **排序方向**：所有有強弱之分的表格圖表，強的在上，不例外
- **og:image 版號**：更新內容卻忘記 +1 版號，視為 bug
- **Chart.js 版本**：不得使用浮動版本引用（如 `@latest`），必須釘死版號並附 integrity hash
- **Mann-Whitney 效應量圖說顏色**：橫條是青色（`#00e5ff`，即 `--site-gold`），圖說必須寫「青色 = 勝場較高」，不寫「紫色」
- **瀏覽次數功能**：已移除（counterapi.dev 停止服務），footer 不再有計數器，勿重新加入

## 技術規範
### Chart.js CDN 引用規則
必須釘死版號 + integrity hash，範例：
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"
        integrity="sha256-..." crossorigin="anonymous"></script>
```
版號變更時同步更新 integrity hash，防止 CDN 污染導致圖表靜默失效。

## UI／排序規則
- 所有表格、圖表，凡有強弱之分（數字高低或顏色深淺），一律從強到弱由上至下排序，讓使用者一眼看出最好的在最上面。
- 顏色色階排序：深紫（最高）→ 中紫 → 淺紫 → 淡灰 → 深灰 → 珊瑚紅（最低），加總色塊分數排序，不用平均值（避免被單一極端值拉偏）。
- 有 null 格的熱力圖：先以非 null 格數量多寡排序（數據越完整越可信），同樣數量再比色塊分數。避免出場少、null 多的球員因缺少負分而誤排前面。
- 圖例文字順序同排序方向：深紫=最高・中紫=…・珊瑚紅=最低，不用「A→B→C=說明」的格式。

## 設計規範
| 變數名稱 | 色碼 | 用途 |
|---|---|---|
| `--site-bg` | `#1a0a2e` | 頁面底色 |
| `--site-bg2` | `#240f40` | 次要背景 |
| `--site-purple` | `#7b3fc4` | 主要強調色 |
| `--site-gold` | `#00e5ff` | 數字、標題強調（青色） |

## 備註
- 資料來源：TPBL 官方網站（手動填入）
- 非官方粉絲製作，純數據整理用途
- og:image 版號需隨每次更新遞增（?v=N），否則 FB 不會重新抓圖
