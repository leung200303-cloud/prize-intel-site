# 模塊 #3 — HTTP 抓取層、排程、ingest_run 對接、斷鏈告警

> Step 4 第三塊。**49/49 測試通過**（全部用注入 transport，唔需要網絡）
> 相關 schema 變更：`item_view_daily`（方案 A）＋ migration `0002`

---

## 一、檔案

| 檔案 | 作用 |
|---|---|
| `fetcher.py` | UA／timeout／retry＋指數 backoff／per-host 限速／robots.txt（含 cache） |
| `scheduler.py` | `plan_jobs()` 按 `crawl_mode` 決定今日跑邊啲源；`SourceRunner` 抓→解析→分流→寫 run→告警 |
| `ingest.py` | `RunRecord`（同 `ingest_run` 1:1）、`InMemoryRepo`、`PostgresRepo`（未接 DB 明確 raise） |
| `alerts.py` | 三條規則：`broken_link` / `zero_items` / `big_drop`，可寫 log |
| `test_module3.py` | 49 項測試 |

---

## 二、抓取層

### retry 規則

| 情況 | 行為 |
|---|---|
| 200 | 立即成功 |
| 429 / 500 / 502 / 503 / 504 | 重試，backoff = `0.5 × 2^(n-1)` 秒（最多 3 次） |
| 其他 4xx（403/404…） | **唔重試**（重試都唔會得） |
| 網絡錯誤（DNS／timeout） | 重試 |
| robots.txt Disallow | **blocked，唔發請求** |

### 限速同 robots

- `RateLimiter`：**per-host** 最小間隔（同一個 host 第二次要等），唔同 host 唔互相拖。
- `RobotsCache`：抓 `robots.txt` 抽 `User-agent: *` 嘅 `Disallow`，有 TTL cache；攞唔到 robots.txt 時當冇限制（業界慣例）。
- 全部用注入 `transport`（`transport(url, ua, timeout) -> (status, body)`），所以**冇網絡都測得**。

---

## 三、排程規則

| `crawl_mode` | 排程行為 |
|---|---|
| `auto_daily` | 每日跑（由外部 cron 觸發；模塊負責「今日要跑邊啲源」） |
| `weekly` | 逢**星期一**跑 |
| `event_driven` | 只在 `force=True` 跑（プライズフェア 年 4 回，人手觸發） |
| `link_only` / `manual` / `skip` | **唔會產生 job** |
| 冇 `url` | 跳過 |

Job 按 `priority`（P0→0）再按 `code` 排序，確保 P0 源先跑。

---

## 四、ingest_run 對接

`RunRecord` 欄位同 schema `ingest_run` 一一對應，生命週期：

```
running → success / partial / failed
```

- `success`：冇錯
- `partial`：解析器爆咗但抓到頁（**唔會當成功**）
- `failed`：抓取失敗

### 分流入庫規則（對應 module2 政策閘）

| 情況 | 結果 | 計數 |
|---|---|---|
| 有 `official_name` | `staged`（同 official_name 重複 → `updated`） | `items_new` / `items_updated` |
| 冇 `official_name` | `candidate`（入 merge 隊列／預告看板） | `candidates` |
| `index_only` 或 `is_item=False` | `skipped`（唔入 item） | — |

`PostgresRepo` 未接 DB 時**明確 raise**，附安裝步驟。唔會靜默假裝寫入成功。

---

## 五、斷鏈告警（三條規則）

| code | 觸發 | level | 代表 |
|---|---|---|---|
| `broken_link` | 連續 **3** 次抓取失敗 | critical | 源頭死咗／封 IP／網址改咗 |
| `zero_items` | 抓取成功但 `items_seen = 0` | warning | **版面改咗，selector 要修** |
| `big_drop` | 產量跌超過 **50%**（baseline ≥ 10） | warning | 靜靜哋少咗貨（分頁改咗／部分商品下架） |

`zero_items` 係最實用嗰條：抓取層完全正常（HTTP 200），但解析出 0 筆——呢種「靜靜死」靠 HTTP status 完全捉唔到。

告警可寫 `alerts.log`（每行一個 JSON），日後接 webhook／Slack 只需換 `AlertSink`。

---

## 六、測試捉到嘅三個 bug（都係實測先發現）

1. **`attempts` 回傳錯**：404 明明試咗 1 次，卻回報 3 次（hardcode 咗 `max_attempts`）。
2. **網絡錯誤唔重試**：`OSError` 之後 `status=0`，`0` 唔在 `RETRY_STATUS` 就被 `break` → DNS 抖一下即刻放棄。
3. **告警重複觸發**：`repo.history()` 已包含 current run，evaluator 再加 1 → 第 2 次失敗就當第 3 次，`broken_link` 出兩次。

三個都係「睇 code 覺得冇問題」嗰種，寫測試先現形。

---

## 七、測試覆蓋（49 項）

| 組 | 內容 | 數 |
|---|---|---|
| A | retry / 429 / 4xx / 網絡錯誤 / robots / 限速 | 14 |
| B | ingest 分流、run 生命週期、PostgresRepo 明確失敗 | 10 |
| C | 三條告警規則、告警寫檔、JSON 合法 | 7 |
| D | 排程（星期一／星期二／event force／無 url） | 3 |
| E | runner 成功／失敗／解析器爆 | 11 |
| F | **同 module2 整合**：bsp 列表 HTML → 3 款入庫 | 4 |

F 組係真正嘅端到端：真 HTML fixture → module2 解析 → module1 命名 → module3 分流 → `RunRecord` 計數。

---

## 八、未做（清楚列出）

1. **真 DB 未接**：`PostgresRepo` 只係 stub。等有 PostgreSQL 之後補 cursor 實作。
2. **未寫 cron / systemd timer**：`plan_jobs()` 只決定「今日跑邊啲」，實際觸發要外部排程（建議 cron 每朝 06:00 JST 跑一次）。
3. **冇並發**：現時係順序跑。因為有 per-host 限速，而且源頭唔多（P0 得 5 個），順序已經夠；日後可加 thread pool。
4. **告警未接通知渠道**：只寫 log。接 Slack／Discord webhook 係換 `AlertSink.emit()`。
5. **`item_view_daily` 寫入 API 未做**：schema + migration 已好，但前端 +1 接口屬模塊 #4／前端範圍。
6. **item 去重鍵用 `official_name`（in-memory）**，未用 DB 指紋；DB 版要改成 `match_fingerprint`。

---

## 九、下一步

1. **模塊 #4**：L2 指紋落庫 + `merge_candidate` 寫入（等真 PG）
2. 或先做 **前端 MVP**：`taxonomy.json` + `mv_search_index` 靜態索引，驗證流量（唔需要 DB 都可以用 JSON 起 demo）
3. 有 PG 之後：`run_local.ps1` 跑 46 項 DB 測試 → 補 `PostgresRepo`
