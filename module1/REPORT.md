# 模塊 #1 — 商品名抽取層 + 雙別名映射

> Step 4 第一塊。同 DB 完全解耦（純解析層，唔碰 SQL），輸出餵去 L2/L3 去重。
> 測試：`test_module1.py` **82/82 通過**、`run_demo.py` **30/30 fixtures 全中**

---

## 一、點解要有呢一層

Step 3 PoC 實測（`poc/04_Step3_報告.md`）：

| 類別 | 標題相似度 |
|---|---|
| 真同款（bsp ↔ コレトレ） | 平均 **0.116** |
| 假同款（同系列唔同角色） | 平均 **0.349** |

**訊號係反嘅。** 原因：一邊係官方商品名，一邊係文章標題（帶 SEO 廢話）。
所以規格寫死：

```
raw_title      = 頁面原標題          → 只做追溯，永遠唔參與比對
official_name  = 抽出嚟嘅官方商品名  → 唯一可以做比對嘅輸入
```

冇 `official_name` 嘅資料 **`ready_for_matching = False`**，唔准入 L2 自動合併。

---

## 二、檔案

| 檔案 | 作用 |
|---|---|
| `normalize.py` | 全形→半形、片假名→平假名、拆裝飾符號、剝「シリーズ」後綴、**系列號（含羅馬數字）**、尺寸、くじ偵測 |
| `aliases.py` | **雙別名表唯一真相**：9 廠商（含品牌名）+ 48 作品（含中英譯名／後綴變體） |
| `extract.py` | 4 個 extractor + `NamingResult` dataclass |
| `fixtures.json` | 30 條真實驗證資料（bsp 4 頁 DOM、コレトレ spec 表、PoC 真實標題） |
| `run_demo.py` | 跑 fixtures、出 `results.json` / `results.csv` |
| `test_module1.py` | 82 項測試（單元 52 + fixtures 30） |

---

## 三、輸出規格（Step 4 其他解析器要跟）

```python
NamingResult(
    raw_title        : str           # 頁面原標題，原封不動
    official_name    : str | None    # 乾淨官方商品名；None = 唔准自動比對
    name_source      : str           # bsp_breadcrumb / bsp_title_tag /
                                     # kore_spec_table / dengeki_none / none
    maker_code       : str | None    # 已過 alias，對應 maker.code
    maker_match      : str | None    # 命中邊個別名（除錯用）
    maker_method     : str | None    # hint / alias_containment / source_default
    ip_code          : str | None    # 對應 ip_work.code
    ip_match, ip_method
    size_cm          : float | None  # 多尺寸取最大
    size_text        : str | None    # 尺寸原文（多角色品保留全部）
    series_group     : str | None    # 系列號，統一阿拉伯數字 "2" / "3"
    is_kuji          : bool
    warnings         : list[str]
)
```

`ready_for_matching` property = `official_name is not None`。

### 各源頭嘅官方名來源

| 源頭 | 來源 | 實測命中 |
|---|---|---|
| bsp-prize | JSON-LD `BreadcrumbList` 最後一項（backup：`<title>` 前段） | **4/4** |
| コレトレ（文章頁） | spec 表「商品名」欄 | **1/1** |
| コレトレ（月別一覽頁） | ❌ 冇 → `None` + `no_spec_table` | 0/11 |
| 電撃プライズフェア | ❌ 只有描述句 → `None` + `report_description_only` | 0/14 |

---

## 四、雙別名表（重點）

### Maker：解決「品牌名 vs 公司名」

| 輸入 | code |
|---|---|
| バンプレスト / BANPRESTO / バンダイスピリッツ | `bandai_spirits` |
| セガ / セガ フェイブ | `sega_fave` |
| タイトー / コナミ / フリュー / エイコー / システムサービス | 各自 code |

呢個就係 PoC 講嘅「L2 斷點 6/6 都喺 maker」。而家 8/8 測試通過。

### IP：嚴格處理 PoC 撞到嘅後綴差異

| 實際寫法 | 解析 |
|---|---|
| `ドラゴンボール シリーズ`（bsp breadcrumb） | `dragon_ball` |
| `ポケモンモンスターシリーズ`（bsp breadcrumb） | `pokemon` |
| `ワンピース`（無後綴） | `one_piece` |
| `【ナルト】`（短別名） | `naruto` |
| `『着せ恋』`（簡稱） | `kisekoi` |
| `To LOVEる ダークネス`（子標題） | `to_love_ru` |
| `機動戦士ガンダムSEED` | `gundam_seed`（唔會撞其他高達） |

作品由 30 套擴到 **48 套**，`schema/02_seed.sql` 直接由 `aliases.py` 生成（單一真相，冇重複維護）。

### 系列號：羅馬數字係必須

| 商品名 | series_group |
|---|---|
| `MAXIMATIC GIYU TOMIOKAⅡ` | `2` |
| `MAXIMATIC TANJIRO KAMADOⅢ` | `3` |
| `...RORONOA ZORO Ⅲ-`（尾隨連字號） | `3` |
| `DRAGON BALL SPIRITFLICKS 03` | `3` |
| `vol.2` / `第2弾` | `2` |

> 一開始寫漏「尾隨連字號」case，`ZORO Ⅲ-` 抽唔到 → 測試即刻捉到，已修。

---

## 五、實測結果

```
欄位準確率（30 fixtures）
  official_name  30/30  100.0%
  name_source    30/30  100.0%
  maker_code     30/30  100.0%
  ip_code        30/30  100.0%
  size_cm        30/30  100.0%
  series_group   30/30  100.0%
  is_kuji        30/30  100.0%

按來源
  bsp       n=4   official_name 4/4  maker 4/4  ip 4/4  size 4/4
  kore      n=12  official_name 1/12 maker 1/12 ip 12/12 size 2/2
  dengeki   n=14  official_name 0/14 maker 14/14 ip 14/14 size —
```

> 注意：`maker 30/30` 入面有 11 條係「正確判定為 None」。**實際解析到廠商值只有 5/30**，
> 因為コレトレ 月別頁標題完全唔寫廠商——呢個係資料本質，唔係 bug。

### 最重要嘅一個數：官方名可得率 16.7%（5/30）

| 資料形態 | 有官方名？ | 影響 |
|---|---|---|
| bsp-prize item 頁 | ✅ 100% | 可直接去重 |
| コレトレ 文章頁（有 spec 表） | ✅ 100% | 要逐篇開文章頁，成本高 |
| コレトレ 月別一覽頁 | ❌ 0% | 只能做「發現」，要再入文章頁攞 spec 表 |
| 電撃プライズフェア | ❌ 0% | 只能做「預告提示」，唔入正式 item |

**呢個直接影響爬蟲設計**：月別一覽頁（146 款/月）唔可以只爬一覽頁，必須跟入文章頁抽 spec 表，
否則成個月 146 款全部冇得自動去重。呢個成本要計入 Step 4。

---

## 六、整合契約（Step 4 各解析器點用）

```python
# 1. 解析器只負責抽原始資料
raw = {"raw_title": ..., "spec_rows": [...], "breadcrumb": [...], ...}

# 2. 交俾模塊 #1
from module1.extract import run
result = run({"extractor": "kore", "payload": raw})

# 3. 只有 ready_for_matching 才准入 L2 自動合併
if result.ready_for_matching:
    upsert_item(result)          # title_jp = result.official_name
    item_source.raw_title = result.raw_title   # 原標題留喺來源表
else:
    enqueue_candidate(result)    # 入 merge_candidate，人手覆核
```

`official_name` 對應 `item.title_jp`；`raw_title` 對應 `item_source.raw_title`。
`official_name_source` 欄位直接存 `result.name_source`。

---

## 七、限制 / 未做

1. **コレトレ 文章頁 spec 表嘅 DOM 未實測**——fixtures 用嘅 spec 表內容係由文章頁文字抽，
   未確認實際 HTML selector（Step 3.5 只核實咗 bsp）。Step 4 寫該解析器時要開 page 確認。
2. **電撃プライズフェア 官方名 0%**，已定性為「預告提示」，唔會做去重輸入。
3. **角色抽取未做**——`primary_character_id` 仍要靠解析器另外抽（bsp 有 `/character/CH` 連結，
   多角色品要靠描述文）。
4. **商品名清洗規則只覆蓋實測到嘅樣式**；遇到新品牌線（例 `Figuno`、`FIGURIZMα`）要加 brand_line。
5. **未接 DB**：`upsert_item` / `enqueue_candidate` 係契約，未實作（等 Step 4 爬蟲層）。

---

## 八、下一步

1. Step 4 模塊 #2：bsp-prize 解析器（列表＋詳情，spec 三分支）→ 直接調用 `extract_bsp()`
2. 開コレトレ 文章頁確認 spec 表 selector（補 Step 3.5 遺留）
3. 有 PG 之後補跑 `schema/tests.sql` 40 項
