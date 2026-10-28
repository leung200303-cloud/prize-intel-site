# 模塊 #2 — bsp-prize 解析器 + コレトレ spec 表核實

> Step 4 第二塊。全程調用 module1 `extract.py` / `aliases.py`：`official_name` 係唯一去重輸入，`raw_title` 只留溯源。
> 測試：**67/67 通過**（module1 回歸 82/82 亦全過）

---

## 一、實測 selector（Playwright 讀真 DOM，2026-10-28）

### bsp-prize（4 頁核實）

| 位置 | Selector | 實測 |
|---|---|---|
| 列表卡 | `div.topProducts_item`（內含 `a[href="/item/N/"]`） | 3 卡全中 |
| 列表商品名 | `p.topProducts_name` | ✅ 即係官方商品名 |
| 列表發售文字 | `p.topProducts_note`（`2026年10月29日（木）<br>より順次登場予定`） | ✅ |
| 詳情官方商品名 | `script[type=application/ld+json]` → `BreadcrumbList` 最後一項 | ✅ 最穩 |
| 詳情作品 | 同一 breadcrumb 入面 `/title/IPxxxx/` 嗰項 | ✅ |
| 詳情角色 | 另一條 breadcrumb 入面 `/character/CHxxxx/` | ✅（くじ 頁先有） |
| 商品仕様 | `dl.productDetail_spec` > `dd`（`<br>` 分行） | ✅ 三分支 |
| 描述 | `div.productDetail_body` > `p` | ✅ 多角色品靠呢度 |
| 發售日 | 文字 regex `(\d{4})年(\d{1,2})月(\d{1,2})日…より順次登場/発売予定` | ✅（避開 selector 改版） |
| JAN／品番 | — | ❌ **4 頁零命中** |

### コレトレ文章頁（1 頁核實）

| 位置 | Selector | 實測 |
|---|---|---|
| 文章標題 | `h1`（`div.post_content > h1.entry-title`） | ⚠️ **只可做 raw_title** |
| spec 表 | `div.post_content > table`（無 class，`<th>`/`<td>` 兩欄） | ✅ |
| 官方商品名 | spec 表 `商品名` 列 | ✅ 唯一正確來源 |
| 其他欄 | `作品名` / `種類` / `サイズ` / `メーカー` | ✅ |

> Step 3.5 遺留嘅「コレトレ spec 表 selector 未核實」已補完。

---

## 二、三個 spec 分支分開處理（唔強行統一）

| 分支 | 實測原文 | 處理 |
|---|---|---|
| `figure` | `・全4種` / `・約10cm` | `kinds=4`、`size_cm=10` |
| `plush_multi` | `・全3種` / `・ピカチュウ…約15cm、ドーブル：約16cm、チラーミィ：約16cm` | `size_cm=16`（最大）、**`size_text` 原文完整保留**、`sizes=[15,16]` |
| `kuji` | `■発売日：2027年3月27日(土)…` / `■メーカー希望小売価格：1回10,000円（税込）` | `release_text`、`price_per_play=10000`；尺寸由描述文抽（約34cm） |

`detect_spec_branch()` 判斷次序：有「発売日 + 1回」→ `kuji`；≥2 個唔同 `約Ncm` → `plush_multi`；有 `全N種` 或單一尺寸 → `figure`；否則 `unknown`。

輸出同時保留 `spec.raw_lines`，任何分支都唔會丟原文。

---

## 三、政策閘（寫成代碼，唔靠自律）

```python
POLICY = {
  "kore-tore": {"index": "只做索引，禁止 L2", "matchable_from_index": False},
  "dengeki-prizefair": {"role": "預告看板 only", "matchable": False},
}

guard_matchable(result, stage):   # 自動比對前最後一道閘
    is_item=False / board=preview  → raise PolicyViolation
    official_name is None          → raise
    status == index_only           → raise
```

三個源頭嘅實際行為：

| 源頭 | 抽出 | official_name | 可否自動比對 |
|---|---|---|---|
| bsp 列表 | item_id / 商品名 / 發售文字 | ✅（卡片商品名） | ⚠️ 可以，但**強制 `needs_detail=True`** 補 size |
| bsp 詳情 | 商品名 + 三分支 spec + 角色 | ✅ | ✅ |
| コレトレ文章 | spec 表 5 欄 | ✅ | ✅ |
| コレトレ一覽 | **只有連結** | ❌ 完全冇欄位 | ❌ 強制跳文章頁 |
| 電撃PF | 廠商 + 描述 | ❌ | ❌ 只入預告看板 |

---

## 四、實測捉到嘅四個真問題

### ① くじ 頁有兩個 `BreadcrumbList`（最陰險）
```
block1: トップ → 作品タイトル → ワンピース        → 商品名   ← 要呢個
block2: トップ → キャラクター   → ジュラキュール・ミホーク → 商品名
```
如果照「第一條 breadcrumb」寫，`crumb[-2]` 會變角色名 → IP 判斷被污染（`one_piece` 變 `None` 或錯）。
**已修**：按 `@id` 含 `/title/IP` 揀作品鏈，`/character/CH` 揀角色鏈。測試 E01–E03 鎖死。

### ② bsp 列表 `data-new_item_id` ≠ 商品 ID
```
data-new_item_id="8629"   ← bsp 內部序號
href="/item/2844853/"     ← 真正商品 ID
```
用錯就全部 detail_url 都錯。已改用 href，內部序號另存 `bsp_internal_id`。

### ③ 電撃PF 一段可以含多個 IP
```
エイコー：『星のカービィ』ドーナツ型ライトや、『仮面ライダーカブト』のプライズアイテムを展示！
```
原本 `resolve_ip()` 只回一個 code → 第二個 IP 靜靜消失。
**已加 `resolve_ips()` / `NamingResult.ip_codes`**（按 alias 長度 desc 回全部命中）。
呢個亦影響 module1 輸出：`ip_code` 保留做主要分類，`ip_codes` 保留全部。

### ④ 多角色多尺寸
`size_cm` 單一數值表達唔到「3 個角色 15/16/16cm」。
**已處理**：`size_cm` = 最大、`size_text` = 原文、`sizes[]` = 全部；schema 早已留 `size_text`。

---

## 五、測試

```
module2/test_module2.py   67/67 PASS
module1/test_module1.py   82/82 PASS（無回歸）
module1/run_demo.py       30/30 fixtures 全中
```

覆蓋範圍：htmlutil 6、bsp 列表 8、figure 13、plush 5、kuji 11、コレトレ文章 9、
コレトレ一覽 5、電撃PF 8、統計 2。

---

## 六、檔案

| 檔案 | 作用 |
|---|---|
| `htmlutil.py` | 平衡區塊抽取、ld+json、dl/table、文字化（零第三方依賴） |
| `bsp.py` | 列表 + 詳情解析、三分支 spec、雙 breadcrumb 處理、發售日 regex |
| `kore.py` | 文章頁 spec 表、一覽頁「只抽連結」 |
| `pipeline.py` | 分派 + 政策閘 + `summarize()`（餵 `ingest_run`） |
| `fixtures/*.html` | 真實擷取 HTML（6 個） |
| `test_module2.py` | 67 項測試 |

---

## 七、模塊 #2 明確**唔做**（按約束 5）

- ❌ 角色抽取（`primary_character_id`）——預留，模塊 #3 做
- ❌ DB upsert / `merge_candidate` 寫入
- ❌ 爬蟲排程／重試／UA 輪換（下一步先寫）
- ❌ コレトレ 一覽頁標題清洗（根本唔會用嚟比對）

---

## 八、下一步

1. **模塊 #3**：HTTP 抓取層 + 排程（`ingest_run` 對接）＋ 重試／斷鏈告警
2. **模塊 #4**：L2 指紋落庫 + `merge_candidate` 寫入（真 PG 上線後）
3. 有 PG 之後補跑 `schema/tests.sql` 40 項
