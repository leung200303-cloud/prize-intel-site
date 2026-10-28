# 景品採購情報搜尋站 — 工程文件

日本夾公仔場主專用嘅情報索引站。第一階段只做索引＋搜尋，證明有流量才做 APP，AI 層最後。

## 檔案

| 檔案 | 內容 |
|---|---|
| [01_源頭清單_v0.3.xlsx](../01_源頭清單_v0.3.xlsx) | **主文件**：立項卡、31 條源頭、分類標籤、欄位草案、排除清單、爬取模式、PoC 模板、開發次序、二手價規則、HTML 核實結果 |
| [01_schema.sql](01_schema.sql) | PostgreSQL DDL：13 表、3 視圖、10 enum、7 函式、4 trigger |
| [02_seed.sql](02_seed.sql) | 種子資料：9 廠商（帶 alias）、18 系列線、48 作品、31 源頭｜廠商／作品由 `module1/aliases.py` 生成 |
| [03_dedup_rules.md](03_dedup_rules.md) | 三層去重規則、同款多名處理、人手 merge 流程、驗收指標 |
| **[tests.sql](tests.sql)** | **40 項 DB 驗收測試**（自我檢查，跑完 ROLLBACK 唔污染 DB） |
| **[sim_logic.py](sim_logic.py)** | **DB 邏輯模擬器**：冇真 PG 時驗證觸發器／約束推論（20 項） |
| **[run_local.ps1](run_local.ps1)** | 一鍵建 DB → schema → seed → 測試（Docker 或本機 psql） |
| [gen_seed.py](gen_seed.py) | 由 Excel 生成 02_seed.sql |
| [check_schema.py](check_schema.py) | 離線 SQL 檢查（FK、型別、trigger、translate 長度、私隱閘） |

## PoC（Step 3）

| 檔案 | 內容 |
|---|---|
| [poc/05_HTML核實報告.md](../poc/05_HTML核實報告.md) | **核實**：bsp 欄位定位、spec 三分支、一番くじ 冇 JAN、Step 4 工時重估 |
| [poc/04_Step3_報告.md](../poc/04_Step3_報告.md) | 報告：相似度分佈、L2 命中率、耗時推算、Step 4 估算 |
| [poc/03_PoC抽樣結果_v1.xlsx](../poc/03_PoC抽樣結果_v1.xlsx) | 40 款抽樣明細、相似度對照、欄位覆蓋率 |
| [poc/metrics.json](../poc/metrics.json) | 指標原始數據 |
| [poc/build_poc.py](../poc/build_poc.py) | 抽樣分析腳本（內含 pg_trgm 演算法實作） |

## 四條硬性約束

1. 只做日本景品，唔開其他地區
2. 唔主動爬問屋內部套裝／入貨條件（非公開，根本冇源）
3. 網站先測流量 → APP → AI 層，次序唔可以倒轉
4. **唔收集場主查詢**：搜尋／比對喺前端本地運算，`mv_search_index` 匯出靜態 JSON；
   schema 內冇 `user` / `query_log` / `search_history` / `purchase_record` 任何表

## 三個已鎖定決策

1. 二手價存**樣本價**（每款 3 條上限，強制 `captured_at`，>30 日標 `is_stale`）
2. **駿河屋 = 中古參考價基準線**（`reference_price`），mercari／yahoo = 成交樣本（`sold_sample`）
3. **一番くじ 同夾機景品分開**：`channel_type` 用 enum 唔用 tag，前端兩個 tab

## 進度

- [x] Step 1 源頭清單 Excel
- [x] Step 2 DB schema ＋ 去重規則
- [x] Step 3 人手抽樣 PoC（40 款）→ 發現 L3 標題比對訊號反向，需改「商品名抽取」
- [x] Step 3.5 HTML 核實 → bsp 冇 JAN、spec 三分支、一番くじ 冇 JAN 且要父子模型
- [x] Step 4 模塊 #1 商品名抽取層 + 雙別名（82 項測試）
- [x] Step 4 模塊 #2 bsp 解析器 + コレトレ spec 核實（67 項測試）
- [x] Step 4 模塊 #3 抓取層 + 排程 + ingest_run + 斷鏈告警（49 項測試）
- [ ] Step 4 模塊 #4 L2 指紋落庫 + merge_candidate（等真 PG）
- [x] 前端 MVP 靜態 Demo（106 款示範數據，零後端）
- [x] Beta 上架包：`web/demo/dist/`（standalone + robots + CSP `_headers`）＋ `deploy.ps1`
- [ ] **Cloudflare Pages 部署（此環境無網絡／無憑證，需用戶機執行）**
- [x] 自測走查（扮散客／場主，31 個搜尋詞）→ 補 36 IP、25 品牌別名、7 類搜尋缺口
- [x] 模塊 #4 真數據生成器 `pipeline/export_items.py`（fixtures 驗證 6 款真 item）

## 模塊 #1（Step 4 第一塊）— 商品名抽取層

| 檔案 | 內容 |
|---|---|
| [module1/REPORT.md](../module1/REPORT.md) | **報告**：輸出規格、雙別名表、82 項測試、官方名可得率 16.7% |
| [module1/aliases.py](../module1/aliases.py) | **雙別名表唯一真相**（9 廠商 + 48 作品），seed 由佢生成 |
| [module1/extract.py](../module1/extract.py) | 4 個 extractor + `NamingResult` |
| [module1/normalize.py](../module1/normalize.py) | 正規化、系列號（含羅馬數字）、尺寸、くじ偵測 |
| [module1/test_module1.py](../module1/test_module1.py) | 82 項測試 |
| [module1/run_demo.py](../module1/run_demo.py) | 跑 30 條 fixtures，出 results.csv/json |

核心契約：`raw_title` 只做追溯，`official_name` 才做比對；冇官方名 → `ready_for_matching=False`，唔准入自動合併。

## 模塊 #2（Step 4 第二塊）— bsp 解析器 + コレトレ spec 核實

| 檔案 | 內容 |
|---|---|
| [module2/REPORT.md](../module2/REPORT.md) | **報告**：實測 selector、三分支 spec、政策閘、67 項測試 |
| [module2/bsp.py](../module2/bsp.py) | bsp 列表＋詳情、三分支 spec、雙 breadcrumb 處理 |
| [module2/kore.py](../module2/kore.py) | コレトレ文章 spec 表／一覽頁「只抽連結」 |
| [module2/pipeline.py](../module2/pipeline.py) | 分派 + `guard_matchable()` 政策閘 + `summarize()` |
| [module2/htmlutil.py](../module2/htmlutil.py) | 零依賴 HTML 工具 |
| [module2/test_module2.py](../module2/test_module2.py) | 67 項測試 |

## 前端

| 檔案 | 內容 |
|---|---|
| [web/taxonomy.json](../web/taxonomy.json) | **分類索引樹**（由 aliases + schema 生成，唔准手改） |
| [module1/export_taxonomy.py](../module1/export_taxonomy.py) | taxonomy.json 生成器 |
| [docs/IA_審核備忘.md](../docs/IA_審核備忘.md) | IA 規格審核：4 個衝突／2 個法律風險／MVP 收斂建議 |

## 模塊 #3（Step 4 第三塊）— 抓取層 / 排程 / ingest_run / 斷鏈告警

| 檔案 | 內容 |
|---|---|
| [module3/REPORT.md](../module3/REPORT.md) | **報告**：retry/限速/robots、排程規則、三條告警、49 項測試 |
| [module3/fetcher.py](../module3/fetcher.py) | HTTP 抓取（可注入 transport、retry、per-host 限速、robots） |
| [module3/scheduler.py](../module3/scheduler.py) | `plan_jobs()` + `SourceRunner` |
| [module3/ingest.py](../module3/ingest.py) | `RunRecord`（對應 `ingest_run`）、分流、`PostgresRepo` stub |
| [module3/alerts.py](../module3/alerts.py) | `broken_link` / `zero_items` / `big_drop` |
| [module3/test_module3.py](../module3/test_module3.py) | 49 項測試（含同 module2 端到端整合） |

## Schema migrations

| 檔案 | 內容 |
|---|---|
| [migrations/0002_item_view_daily.sql](migrations/0002_item_view_daily.sql) | 方案 A：商品每日聚合瀏覽 + 7 日熱門榜視圖（無 user/IP/query） |

## 前端 MVP 靜態 Demo

| 檔案 | 內容 |
|---|---|
| [web/demo/README.md](../web/demo/README.md) | **說明**：點開、功能、私隱、數據誠實聲明 |
| [web/demo/standalone.html](../web/demo/standalone.html) | **雙擊即開**（全內聯，唔使 server／DB） |
| [web/demo/index.html](../web/demo/index.html) | 正式版入口（讀 `data/*.json`） |
| [web/demo/app.js](../web/demo/app.js) | 全部前端邏輯（零依賴） |
| [web/demo/build_demo.py](../web/demo/build_demo.py) | 生成示範索引 + standalone |
| [web/demo/screenshots/](../web/demo/screenshots/) | 四個畫面截圖 |

## DB 驗證狀態（重要）

| 檢查層 | 狀態 | 工具 |
|---|---|---|
| SQL 結構（FK／型別／trigger 引用／私隱閘） | ✅ 通過 | `check_schema.py`（13 表 / 121 欄位） |
| DB 邏輯推論（3 條上限、循環引用、kuji 約束、指紋） | ✅ 20/20 通過 | `sim_logic.py` |
| **真 PostgreSQL 執行（語法／約束互動／PL/pgSQL）** | ⛔ **未驗證** | `tests.sql`（40 項，待跑） |

**未驗證原因**：本機冇 Docker engine（`C:\docker\docker\docker.exe` 只係孤立 CLI，`dockerd` 係 Windows container 模式，
`no matching manifest for windows/amd64` 跑唔到 linux postgres image）、shell 完全冇網絡（curl 回 000）、
無 admin 權限、WSL 拒絕存取。→ **要裝 Docker Desktop（Linux container）或原生 PostgreSQL 先跑得到。**

裝好之後一鍵：
```powershell
pwsh -File run_local.ps1              # Docker 模式
pwsh -File run_local.ps1 -UseLocalPg   # 本機 psql 模式
```

## 重建方式

```powershell
$py = "C:\Users\loljhhj\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
& $py ..\build_xlsx.py        # 重建 Excel（改清單後跑）
& $py gen_seed.py             # 由 Excel 重建 seed
& $py check_schema.py         # 結構自檢
```

## 開 DB

```bash
# 需要 Docker Desktop 啟動
docker run -d --name prize-intel-pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
sleep 5
docker exec -i prize-intel-pg psql -U postgres -v ON_ERROR_STOP=1 < 01_schema.sql
docker exec -i prize-intel-pg psql -U postgres -v ON_ERROR_STOP=1 < 02_seed.sql
```

> ⚠️ `01_schema.sql` 未喺真 Postgres 上執行過（本機 Docker daemon 未啟動），
> 已用 `check_schema.py` 做離線結構檢查（13 表 / 115 欄位 / FK / trigger / 私隱閘全部通過）。
> 第一次開 DB 時要跑上面指令做真實驗證。
