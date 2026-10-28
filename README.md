# 景品情報索引 Beta (prize-intel)

日本夾公仔機（クレーンゲーム）景品採購情報索引。

## 結構
- `web/demo/` — 前端（純 vanilla JS，無 build step）：`index.html` `app.js` `styles.css` `config.json`
- `web/demo/build_demo.py` — 產生 `dist/`（把 CSS/JS/items.json 內聯成單檔）
- `web/taxonomy.json` — 分類/篩選資料（由 `module1/export_taxonomy.py` 生成）
- `module1/` — 名稱解析、別名、分類法
- `module2/` — 來源頁解析（bsp / kore-tore / 一番くじ）
- `module3/` — 排程抓取、重試、告警
- `pipeline/` — 由解析結果生成 `items.json`
- `schema/` — PostgreSQL schema + seed + 測試
- `docs/` `beta/` — IA 備忘、Beta 回饋流程

## 前端改動界線（給設計/UI Agent）
可以改：
- `web/demo/styles.css`
- `web/demo/index.html` 的結構與卡片模板
- `web/demo/config.json`（聯絡 email、版本號）

唔好改：
- `web/demo/app.js` 內的搜尋/篩選/排序/資料載入邏輯（`window.ITEMS`、`_meta`、`localStorage` 鍵名 `pi.*`）
- `items.json` 資料結構與欄位名
- 任何 `pipeline/` `module*/` 邏輯

## 部署
Cloudflare Pages（Direct Upload）：
```bash
python web/demo/build_demo.py --items <items.json>
npx wrangler pages deploy web/demo/dist --project-name=prize-intel-beta
```
正式站：https://prize-intel-beta.pages.dev

## 隱私底線
無帳號、無追蹤、無外部請求；搜尋全部喺瀏覽器端完成。改 UI 唔可以加入 analytics / 第三方字體 / CDN。
