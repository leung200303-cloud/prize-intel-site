# 給 UI / 設計 Agent（Manus）嘅工作範圍

呢個 repo 係**景品情報索引 Beta**（日本夾公仔機景品採購情報索引）嘅完整源碼。

## 可以改（只限呢啲）
| 檔案 | 可改內容 |
|---|---|
| `web/demo/styles.css` | 全部樣式、顏色、間距、排版、響應式 |
| `web/demo/index.html` | 結構、卡片模板、文案、無障礙屬性 |
| `web/demo/config.json` | `contact_email`、`beta_version` |

## 唔可以改（改咗會壞功能）
| 檔案 | 原因 |
|---|---|
| `web/demo/app.js` | 搜尋、篩選、排序、分頁、`localStorage` 鍵名（`pi.favs` / `pi.history` / `pi.recentQ` / `pi.view`）、`window.ITEMS` / `_meta` 讀取邏輯 |
| `web/items.json`、`dist/` | 資料結構同產物（由 `build_demo.py` 生成） |
| `module1/` `module2/` `module3/` `pipeline/` `schema/` | 資料管線同 DB，屬後端範圍 |
| `.github/` | CI / 部署設定 |

## 硬性約束（唔可以破壞）
1. **零外部請求**：唔可以加 CDN、Google Fonts、analytics、追蹤 script、外部圖片。
2. **單檔可離線**：`build_demo.py` 會把 CSS/JS/JSON 內聯成 `standalone.html`，新樣式唔可以依賴 runtime fetch。
3. **隱私**：無 cookie、無 user id、無 query log；排名只係匿名每日瀏覽熱度。
4. **CSP**：`_headers` 用 `default-src 'none'`，任何新資源都要內聯。

## 改動流程
1. fork 或開 branch：`ui/<描述>`
2. 只改上面「可以改」嘅檔案
3. 本機預覽：`python web/demo/build_demo.py --items web/items.json` → 開 `web/demo/standalone.html`
4. 開 PR 到 `main`，描述改咗邊啲 CSS/模板
5. **部署由 Harness 做**（`wrangler pages deploy`），Manus 唔需要 Cloudflare 權限

## 現況
- 正式站：https://prize-intel-beta.pages.dev
- 前端：純 vanilla JS，無 build step、無框架
- 資料：103 款真樣本（夾機 26 + 一番くじ 77）
