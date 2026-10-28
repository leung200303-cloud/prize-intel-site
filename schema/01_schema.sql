-- =====================================================================
-- 景品採購情報搜尋站 / Prize Intel — PostgreSQL schema v0.1
-- Step 2：DB schema（含三層去重支援）
-- 引擎：PostgreSQL 14+　編碼：UTF8
-- ---------------------------------------------------------------------
-- 【私隱設計 — 硬性約束，唔准改】
-- 本 schema 故意不含以下任何表，日後亦唔准加入：
--   user / account / session / query_log / search_history /
--   purchase_record / favorite / user_profile / analytics_event
--
-- 搜尋與比對係前端（瀏覽器）本地運算：前端下載 mv_search_index 匯出嘅
-- 靜態 JSON 索引，喺 client 做 filter / sort。伺服器只供應靜態檔，
-- 唔接收、唔記錄任何查詢字串。
--
-- 唯一允許嘅流量統計係匿名彙總 page_view_daily
-- （只存「日期 + 總數」，無 IP、無 session、無 UA）。
-- ---------------------------------------------------------------------
-- 設計原則
--  1. item 係唯一主體；來源差異全部收喺 item_source（一品多源）
--  2. 二手價唔存「一個價」，只存 price_ref 樣本（每款硬上限 3 條）
--  3. channel_type 係頂層強制分流：prize（夾機）／ichiban_kuji（抽獎）
--     兩者搜尋結果同行情邏輯完全唔同，DB 層用 enum 唔用 tag
--  4. 去重分三層：JAN → 複合指紋 → trigram 模糊；只有第 1、2 層可自動合併
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------
-- 0. ENUM 型別
-- ---------------------------------------------------------------------
CREATE TYPE source_layer AS ENUM ('A', 'B', 'C', 'D', 'E');

CREATE TYPE crawl_mode AS ENUM (
    'auto_daily',       -- 每日自動
    'weekly',           -- 每週
    'event_driven',     -- 事件驅動（プライズフェア）
    'link_only',        -- 只生成外部連結，唔抓內容
    'manual',           -- 人手補錄
    'skip'              -- 唔爬
);

CREATE TYPE channel_type AS ENUM (
    'prize',            -- 夾機景品
    'ichiban_kuji',     -- 一番くじ（抽獎）
    'gacha',            -- 扭蛋
    'retail'            -- 一般販售
);

CREATE TYPE item_category AS ENUM (
    'figure', 'plush', 'mascot', 'goods', 'cushion', 'towel',
    'tableware', 'lamp', 'acrylic_stand', 'colored_paper', 'keychain', 'other'
);

CREATE TYPE item_status AS ENUM ('announced', 'on_sale', 'resale', 'discontinued');

CREATE TYPE market_region AS ENUM ('JP', 'OVERSEAS');

CREATE TYPE price_platform AS ENUM (
    'surugaya',         -- 駿河屋：中古參考價基準線
    'mercari',          -- メルカリ：成交樣本
    'yahoo_auction',    -- Yahoo!オークション：成交樣本
    'paypay_flea', 'mandarake', 'lashinbang', 'amazon', 'other'
);

CREATE TYPE price_basis AS ENUM (
    'reference_price',  -- 通路定價／標價（駿河屋為主）
    'sold_sample'       -- 實際成交樣本
);

CREATE TYPE merge_status AS ENUM ('pending', 'merged', 'rejected', 'deferred');

CREATE TYPE ingest_status AS ENUM ('running', 'success', 'partial', 'failed');

-- ---------------------------------------------------------------------
-- 1. 來源登記（同 Excel「01_源頭清單」一一對應，係爬蟲 registry）
-- ---------------------------------------------------------------------
CREATE TABLE source (
    code          varchar(40)  PRIMARY KEY,
    layer         source_layer NOT NULL,
    name_jp       text         NOT NULL,
    url           text,
    content_type  text,
    covers        text,
    update_freq   text,
    anti_bot      text,
    crawl_mode    crawl_mode   NOT NULL,
    priority      smallint     NOT NULL CHECK (priority BETWEEN 0 AND 2),
    verified      boolean      NOT NULL DEFAULT false,
    enabled       boolean      NOT NULL DEFAULT true,
    notes         text,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now()
);
COMMENT ON TABLE source IS '源頭登記表；crawl_mode / priority 驅動排程器';

-- ---------------------------------------------------------------------
-- 2. 維度表：廠商 / 系列線 / 作品 / 角色
-- ---------------------------------------------------------------------
CREATE TABLE maker (
    code       varchar(40) PRIMARY KEY,
    name_jp    text        NOT NULL UNIQUE,
    name_en    text,
    -- Step 3 核實新增：民問站／spec 表寫嘅係「ブランド名」而唔係公司名
    -- 例：バンプレスト → bandai_spirits、セガ → sega_fave
    -- L2 指紋斷點 6/6 都喺呢個位，冇 alias 就永遠對唔上
    aliases    text[]      NOT NULL DEFAULT '{}',
    sort_order smallint    NOT NULL DEFAULT 100
);
COMMENT ON COLUMN maker.aliases IS '廠商別名（品牌名／簡稱／英文），解析時先過 alias 再落 code';

CREATE TABLE brand_line (
    code       varchar(40) PRIMARY KEY,
    maker_code varchar(40) REFERENCES maker (code),
    name_jp    text        NOT NULL,
    name_en    text,
    sort_order smallint    NOT NULL DEFAULT 100
);
COMMENT ON TABLE brand_line IS '系列線（Luminasta / MAXIMATIC…）；比 maker 更貼近場主搜尋習慣';

CREATE TABLE ip_work (
    code     varchar(40) PRIMARY KEY,
    title_jp text        NOT NULL,
    title_en text,
    title_zh text,
    aliases  text[]      NOT NULL DEFAULT '{}'
);

CREATE TABLE character (
    id           bigserial  PRIMARY KEY,
    ip_work_code varchar(40) NOT NULL REFERENCES ip_work (code),
    name_jp      text        NOT NULL,
    name_roman   text,
    aliases      text[]      NOT NULL DEFAULT '{}',
    UNIQUE (ip_work_code, name_jp)
);

-- ---------------------------------------------------------------------
-- 3. 主體：item
-- ---------------------------------------------------------------------
CREATE TABLE item (
    id                    uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    jan_code              varchar(13)  CHECK (jan_code ~ '^[0-9]{13}$'),
    maker_code            varchar(40)  NOT NULL REFERENCES maker (code),
    brand_line_code       varchar(40)  REFERENCES brand_line (code),
    channel_type          channel_type NOT NULL,
    category              item_category NOT NULL,
    title_jp              text         NOT NULL CHECK (btrim(title_jp) <> ''),
    title_zh              text,
    -- Step 3 核實新增：title_jp 存「官方商品名」，頁面原標題留在 item_source.raw_title
    -- 來源：bsp-prize → JSON-LD BreadcrumbList 最後一項；コレトレ → spec 表「商品名」欄
    -- 冇呢個欄位就係 PoC 發現嘅 L3 訊號反向問題根源
    official_name_source  text,
    normalized_title      text         NOT NULL DEFAULT '',
    title_hash            char(64),
    ip_work_code          varchar(40)  REFERENCES ip_work (code),
    primary_character_id  bigint       REFERENCES character (id),
    release_date          date,
    release_month         varchar(7)   NOT NULL
                          CHECK (release_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    size_cm               numeric(5,1) CHECK (size_cm > 0),
    -- 多尺寸品（例：ポケモン ぬいぐるみ 一款 3 角色、15/16/16cm）→ size_cm 存最大值，原文留呢度
    size_text             text,
    size_label            text,
    series_group          text,
    -- Step 3 核實新增：一番くじ係「一個獎池 + 多個賞品」，唔係一款貨
    -- 池 = is_kuji_pool true；賞品 parent_item_id 指向池，prize_tier 存 A賞／B賞／ラストワン賞
    parent_item_id        uuid         REFERENCES item (id),
    prize_tier            text,
    is_kuji_pool          boolean      NOT NULL DEFAULT false,
    is_resale             boolean      NOT NULL DEFAULT false,
    status                item_status  NOT NULL DEFAULT 'announced',
    market_region         market_region NOT NULL DEFAULT 'JP',
    image_url             text,
    aliases               text[]       NOT NULL DEFAULT '{}',
    match_fingerprint     char(64),
    confidence            smallint     NOT NULL DEFAULT 60 CHECK (confidence BETWEEN 0 AND 100),
    first_seen            timestamptz  NOT NULL DEFAULT now(),
    last_seen             timestamptz  NOT NULL DEFAULT now(),
    created_at            timestamptz  NOT NULL DEFAULT now(),
    updated_at            timestamptz  NOT NULL DEFAULT now(),
    search_vector         tsvector GENERATED ALWAYS AS (
                              to_tsvector('simple',
                                  coalesce(title_jp, '') || ' ' || coalesce(title_zh, ''))
                          ) STORED
);
COMMENT ON TABLE item IS '情報主體：一款貨 = 一筆；跨站重複靠 item_source + 三層去重收斂';
COMMENT ON COLUMN item.image_url IS '只存官方圖 URL，唔 re-host（版權）';
COMMENT ON COLUMN item.match_fingerprint IS '第 2 層複合鍵指紋（唔含標題），由 trigger 維護';

-- 第 1 層：JAN 唯一（可空）
CREATE UNIQUE INDEX uq_item_jan ON item (jan_code) WHERE jan_code IS NOT NULL;
-- 第 2 層：複合指紋 / 標題雜湊（唔設 unique：命中後由 ingest 層決定自動合併定入隊）
CREATE INDEX idx_item_fingerprint ON item (match_fingerprint) WHERE match_fingerprint IS NOT NULL;
CREATE INDEX idx_item_title_hash ON item (title_hash) WHERE title_hash IS NOT NULL;
-- 第 3 層：模糊比對
CREATE INDEX idx_item_title_trgm ON item USING gin (normalized_title gin_trgm_ops);
-- 檢索
CREATE INDEX idx_item_search_vector ON item USING gin (search_vector);
CREATE INDEX idx_item_release_month ON item (release_month);
CREATE INDEX idx_item_browse ON item (channel_type, status, release_month DESC);
CREATE INDEX idx_item_maker ON item (maker_code);
CREATE INDEX idx_item_brand ON item (brand_line_code);
CREATE INDEX idx_item_ip ON item (ip_work_code);
-- 一番くじ 父子關係（池 → 賞品）
CREATE INDEX idx_item_parent ON item (parent_item_id) WHERE parent_item_id IS NOT NULL;
CREATE INDEX idx_item_kuji_pool ON item (channel_type) WHERE is_kuji_pool;
ALTER TABLE item
    ADD CONSTRAINT chk_item_no_self_parent
    CHECK (parent_item_id IS NULL OR parent_item_id <> id);

-- 一番くじ 父子結構約束（Step 3.5 核實後新增）
-- 獎池：is_kuji_pool = true，自己唔可以有 parent
ALTER TABLE item
    ADD CONSTRAINT chk_kuji_pool_has_no_parent
    CHECK (NOT (is_kuji_pool AND parent_item_id IS NOT NULL));
-- 賞品：有 prize_tier 就一定要有 parent
ALTER TABLE item
    ADD CONSTRAINT chk_prize_tier_needs_parent
    CHECK (prize_tier IS NULL OR parent_item_id IS NOT NULL);
-- 只有一番くじ 通道先可以有 parent（唔准夾機景品掛喺池下面）
ALTER TABLE item
    ADD CONSTRAINT chk_kuji_parent_channel
    CHECK (parent_item_id IS NULL OR channel_type = 'ichiban_kuji');

-- 角色多值（display / 篩選用；匹配權威仍以 primary_character_id 為準）
CREATE TABLE item_character (
    item_id      uuid   NOT NULL REFERENCES item (id) ON DELETE CASCADE,
    character_id bigint NOT NULL REFERENCES character (id),
    is_primary   boolean NOT NULL DEFAULT false,
    PRIMARY KEY (item_id, character_id)
);

-- ---------------------------------------------------------------------
-- 4. 一品多源
-- ---------------------------------------------------------------------
CREATE TABLE item_source (
    id                bigserial   PRIMARY KEY,
    item_id           uuid        NOT NULL REFERENCES item (id) ON DELETE CASCADE,
    source_code       varchar(40) NOT NULL REFERENCES source (code),
    source_url        text        NOT NULL,
    raw_title         text        NOT NULL,
    raw_payload       jsonb,
    extractor_version text,
    first_seen        timestamptz NOT NULL DEFAULT now(),
    last_seen         timestamptz NOT NULL DEFAULT now(),
    is_active         boolean     NOT NULL DEFAULT true,
    UNIQUE (item_id, source_code, source_url)
);
CREATE INDEX idx_item_source_item ON item_source (item_id);
CREATE INDEX idx_item_source_source ON item_source (source_code, last_seen DESC);

-- ---------------------------------------------------------------------
-- 5. 二手價樣本（每款硬上限 3 條）
--    決策：surugaya = 基準線（reference_price），mercari/yahoo = 成交樣本
-- ---------------------------------------------------------------------
CREATE TABLE price_ref (
    id              bigserial      PRIMARY KEY,
    item_id         uuid           NOT NULL REFERENCES item (id) ON DELETE CASCADE,
    platform        price_platform NOT NULL,
    basis           price_basis    NOT NULL,
    price_yen       integer        NOT NULL CHECK (price_yen > 0 AND price_yen < 10000000),
    condition_label text,
    captured_at     date           NOT NULL,
    source_url      text,
    note            text,
    created_at      timestamptz    NOT NULL DEFAULT now(),
    -- 同一樣本重複抓取時用 ON CONFLICT DO NOTHING
    UNIQUE (item_id, platform, captured_at, price_yen)
);
COMMENT ON TABLE price_ref IS '每款最多 3 條樣本；>30 日由 v_price_current 標 is_stale，唔刪（保留歷史）';

CREATE INDEX idx_price_ref_item ON price_ref (item_id, captured_at DESC);
CREATE INDEX idx_price_ref_platform ON price_ref (platform, captured_at DESC);

-- 基準線每平台只保留一條（UPSERT）
CREATE UNIQUE INDEX uq_price_baseline
    ON price_ref (item_id, platform)
    WHERE basis = 'reference_price';

-- 上限 3 條：插入第 4 條時，優先淘汰最舊嘅「成交樣本」，保留基準線
CREATE OR REPLACE FUNCTION enforce_price_ref_cap()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM price_ref WHERE item_id = NEW.item_id;

    IF v_count >= 3 THEN
        DELETE FROM price_ref
         WHERE id IN (
             SELECT id
               FROM price_ref
              WHERE item_id = NEW.item_id
              -- false（成交樣本）排前 → 先刪；再按最舊
              ORDER BY (basis = 'reference_price') ASC, captured_at ASC, id ASC
              LIMIT v_count - 2
         );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_price_ref_cap
    BEFORE INSERT ON price_ref
    FOR EACH ROW EXECUTE FUNCTION enforce_price_ref_cap();

-- ---------------------------------------------------------------------
-- 6. 去重：候選隊列 + 合併紀錄
-- ---------------------------------------------------------------------
CREATE TABLE merge_candidate (
    id              bigserial    PRIMARY KEY,
    item_a          uuid         NOT NULL REFERENCES item (id) ON DELETE CASCADE,
    item_b          uuid         NOT NULL REFERENCES item (id) ON DELETE CASCADE,
    similarity      numeric(4,3) NOT NULL CHECK (similarity BETWEEN 0 AND 1),
    reason          text         NOT NULL,
    status          merge_status NOT NULL DEFAULT 'pending',
    reviewed_by     text,
    reviewed_at     timestamptz,
    resolution_note text,
    created_at      timestamptz  NOT NULL DEFAULT now(),
    CHECK (item_a < item_b),
    UNIQUE (item_a, item_b)
);
COMMENT ON TABLE merge_candidate IS '第 3 層只入呢個隊列，永不自動合併';

CREATE INDEX idx_merge_pending ON merge_candidate (status, similarity DESC)
    WHERE status = 'pending';

CREATE TABLE merge_log (
    id          bigserial   PRIMARY KEY,
    survivor_id uuid        NOT NULL REFERENCES item (id) ON DELETE CASCADE,
    merged_id   uuid        NOT NULL,
    layer       smallint    NOT NULL CHECK (layer IN (1, 2, 3)),
    detail      jsonb       NOT NULL DEFAULT '{}',
    merged_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_merge_log_survivor ON merge_log (survivor_id);

-- ---------------------------------------------------------------------
-- 7. 爬蟲執行紀錄（監控斷鏈；無任何使用者資料）
-- ---------------------------------------------------------------------
CREATE TABLE ingest_run (
    id            bigserial     PRIMARY KEY,
    source_code   varchar(40)   NOT NULL REFERENCES source (code),
    started_at    timestamptz   NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    status        ingest_status NOT NULL DEFAULT 'running',
    items_seen    integer       NOT NULL DEFAULT 0,
    items_new     integer       NOT NULL DEFAULT 0,
    items_updated integer       NOT NULL DEFAULT 0,
    candidates    integer       NOT NULL DEFAULT 0,
    error_count   integer       NOT NULL DEFAULT 0,
    notes         text
);
CREATE INDEX idx_ingest_source_time ON ingest_run (source_code, started_at DESC);

-- ---------------------------------------------------------------------
-- 8. 匿名彙總流量（唯一允許嘅 analytics）
-- ---------------------------------------------------------------------
CREATE TABLE page_view_daily (
    day   date    PRIMARY KEY,
    views bigint  NOT NULL DEFAULT 0 CHECK (views >= 0)
);
COMMENT ON TABLE page_view_daily IS '只存每日總數。禁存 IP / UA / session / 查詢字串';

-- ---------------------------------------------------------------------
-- 8b. 商品級每日聚合瀏覽數（方案 A，2026-10-28 決策）
--     用途：7 日熱門榜、IP 聚合瀏覽榜
--     ⚠️ 私隱邊界：只准「商品 × 日」聚合計數。
--        禁存 user_id / session / IP / UA / 查詢字串 / referrer 完整 URL。
--        寫入方式：前端只提交 item_id（無任何識別碼），後端只做 +1 累加。
-- ---------------------------------------------------------------------
CREATE TABLE item_view_daily (
    item_id uuid   NOT NULL REFERENCES item (id) ON DELETE CASCADE,
    day     date   NOT NULL,
    views   bigint NOT NULL DEFAULT 1 CHECK (views >= 0),
    PRIMARY KEY (item_id, day)
);
COMMENT ON TABLE item_view_daily IS
    '商品每日聚合瀏覽數。只准 (item_id, day, views)；禁任何使用者識別資訊';

CREATE INDEX idx_item_view_day ON item_view_daily (day, views DESC);

-- 7 日熱門榜（給前端讀；可按 channel_type 分「景品／一番くじ」兩個 tab）
CREATE VIEW v_item_popular_7d AS
SELECT i.id            AS item_id,
       i.title_jp,
       i.channel_type,
       i.ip_work_code,
       i.release_month,
       sum(v.views)::bigint AS views_7d
  FROM item_view_daily v
  JOIN item i ON i.id = v.item_id
 WHERE v.day > CURRENT_DATE - INTERVAL '7 days'
 GROUP BY i.id, i.title_jp, i.channel_type, i.ip_work_code, i.release_month;

-- IP 聚合瀏覽榜（⚠️ 唔係「查詢量」，係商品瀏覽量按 IP 彙總）
CREATE VIEW v_ip_popular_7d AS
SELECT i.ip_work_code,
       sum(v.views)::bigint AS views_7d,
       count(DISTINCT i.id)  AS item_count
  FROM item_view_daily v
  JOIN item i ON i.id = v.item_id
 WHERE v.day > CURRENT_DATE - INTERVAL '7 days'
   AND i.ip_work_code IS NOT NULL
 GROUP BY i.ip_work_code;

-- ---------------------------------------------------------------------
-- 9. 函式：標題正規化 / 指紋
-- ---------------------------------------------------------------------
-- 片假名 → 平假名（ァ..ヶ = U+30A1..U+30F6，減 96）
CREATE OR REPLACE FUNCTION kana_fold(p_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT coalesce(string_agg(
               CASE WHEN ascii(ch) BETWEEN 12449 AND 12534
                    THEN chr(ascii(ch) - 96) ELSE ch END,
               '' ORDER BY ord), '')
      FROM regexp_split_to_table(coalesce(p_text, ''), '') WITH ORDINALITY AS t(ch, ord);
$$;

-- 標題正規化：全形→半形、統一大小寫、拆裝飾符號、壓空白
CREATE OR REPLACE FUNCTION normalize_title(p_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT regexp_replace(
               btrim(
                   kana_fold(
                       lower(
                           translate(
                               coalesce(p_text, ''),
                               'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９',
                               'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
                           )
                       )
                   )
               ),
               '[[:space:]　【】\[\]（）()「」『』・･\-–—_/／:：!！?？★☆♪♡♥、,，.。~〜]+',
               '',
               'g'
           );
$$;

-- 第 2 層複合指紋：廠商｜系列線｜作品｜主角色｜發售月｜系列群組｜尺寸桶
-- 唔含標題 → 標題差異唔會影響命中；尺寸以 5cm 為一桶
-- series_group 係防誤併閘：同一角色同月同系列嘅 vol.1 / vol.2 必須分開
CREATE OR REPLACE FUNCTION compute_fingerprint(
    p_maker  text,
    p_brand  text,
    p_ip     text,
    p_char   bigint,
    p_month  text,
    p_series text,
    p_size   numeric
)
RETURNS char(64)
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT encode(
               digest(
                   coalesce(p_maker, '') || '|' ||
                   coalesce(p_brand, '') || '|' ||
                   coalesce(p_ip, '')    || '|' ||
                   coalesce(p_char::text, '') || '|' ||
                   coalesce(p_month, '') || '|' ||
                   coalesce(normalize_title(p_series), 'NA') || '|' ||
                   coalesce((round(p_size / 5) * 5)::text, 'NA'),
                   'sha256'
               ),
               'hex'
           );
$$;

-- 寫入時自動維護 normalized_title / title_hash / match_fingerprint
CREATE OR REPLACE FUNCTION item_before_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.normalized_title := normalize_title(NEW.title_jp);
    NEW.title_hash := encode(digest(NEW.normalized_title, 'sha256'), 'hex');
    NEW.match_fingerprint := compute_fingerprint(
        NEW.maker_code,
        NEW.brand_line_code,
        NEW.ip_work_code,
        NEW.primary_character_id,
        NEW.release_month,
        NEW.series_group,
        NEW.size_cm
    );
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_item_before_write
    BEFORE INSERT OR UPDATE ON item
    FOR EACH ROW EXECUTE FUNCTION item_before_write();

-- 防循環 parent 引用
-- ⚠️ CHECK (parent_item_id <> id) 只擋得住「自我引用」，擋唔住 A→B→A、A→B→C→A
--    呢個係 Step 3.5 補返嘅漏洞：要遞歸向上行，撞返自己就報錯
CREATE OR REPLACE FUNCTION prevent_parent_cycle()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_cursor uuid    := NEW.parent_item_id;
    v_depth  integer := 0;
BEGIN
    WHILE v_cursor IS NOT NULL LOOP
        IF v_cursor = NEW.id THEN
            RAISE EXCEPTION 'parent_item_id 形成循環引用（item %）', NEW.id
                USING ERRCODE = '23514';
        END IF;

        v_depth := v_depth + 1;
        IF v_depth > 5 THEN
            RAISE EXCEPTION 'parent_item_id 層級過深（>5 層），item %', NEW.id
                USING ERRCODE = '23514';
        END IF;

        SELECT i.parent_item_id INTO v_cursor FROM item i WHERE i.id = v_cursor;
    END LOOP;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_item_parent_cycle
    BEFORE INSERT OR UPDATE OF parent_item_id ON item
    FOR EACH ROW EXECUTE FUNCTION prevent_parent_cycle();

-- 通用 updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_source_updated_at
    BEFORE UPDATE ON source
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------
-- 10. 視圖
-- ---------------------------------------------------------------------
-- 未過期（<=30 日）價格樣本
CREATE VIEW v_price_current AS
SELECT p.*,
       (p.captured_at < CURRENT_DATE - INTERVAL '30 days') AS is_stale
  FROM price_ref p;

-- 搜尋 / 展示用寬表（後端 admin 用）
CREATE VIEW v_item_search AS
SELECT i.id,
       i.jan_code,
       i.maker_code,
       mk.name_jp                                   AS maker_name,
       i.brand_line_code,
       bl.name_jp                                   AS brand_name,
       i.channel_type,
       i.category,
       i.title_jp,
       i.title_zh,
       i.ip_work_code,
       w.title_jp                                   AS ip_title_jp,
       i.release_month,
       i.release_date,
       i.size_cm,
       i.size_label,
       i.status,
       i.is_resale,
       i.image_url,
       i.confidence,
       i.last_seen,
       ARRAY(
           SELECT c.name_jp
             FROM item_character ic
             JOIN character c ON c.id = ic.character_id
            WHERE ic.item_id = i.id
            ORDER BY ic.is_primary DESC, c.name_jp
       ) AS characters,
       (SELECT min(p.price_yen)  FROM v_price_current p
         WHERE p.item_id = i.id AND p.basis = 'sold_sample' AND NOT p.is_stale) AS sold_min_30d,
       (SELECT max(p.price_yen)  FROM v_price_current p
         WHERE p.item_id = i.id AND p.basis = 'sold_sample' AND NOT p.is_stale) AS sold_max_30d,
       (SELECT p.price_yen       FROM v_price_current p
         WHERE p.item_id = i.id AND p.basis = 'reference_price' AND NOT p.is_stale
         ORDER BY p.captured_at DESC LIMIT 1) AS baseline_price,
       (SELECT p.captured_at     FROM v_price_current p
         WHERE p.item_id = i.id AND p.basis = 'reference_price'
         ORDER BY p.captured_at DESC LIMIT 1) AS baseline_captured_at
  FROM item i
  LEFT JOIN maker      mk ON mk.code = i.maker_code
  LEFT JOIN brand_line bl ON bl.code = i.brand_line_code
  LEFT JOIN ip_work    w  ON w.code  = i.ip_work_code;

-- 前端靜態索引：每晚 refresh，匯出 JSON 俾瀏覽器本地搜尋
CREATE MATERIALIZED VIEW mv_search_index AS
SELECT jsonb_agg(
           jsonb_build_object(
               'id',           i.id,
               'jan',          i.jan_code,
               'maker',        i.maker_code,
               'brand',        i.brand_line_code,
               'channel',      i.channel_type,
               'cat',          i.category,
               'title',        i.title_jp,
               'titleZh',      i.title_zh,
               'norm',         i.normalized_title,
               'ip',           i.ip_work_code,
               'month',        i.release_month,
               'size',         i.size_cm,
               'status',       i.status,
               'resale',       i.is_resale,
               'img',          i.image_url,
               'chars',        (SELECT jsonb_agg(c.name_jp)
                                  FROM item_character ic
                                  JOIN character c ON c.id = ic.character_id
                                 WHERE ic.item_id = i.id),
               'price',        (SELECT jsonb_build_object(
                                           'base', p.price_yen,
                                           'date', p.captured_at)
                                  FROM v_price_current p
                                 WHERE p.item_id = i.id
                                   AND p.basis = 'reference_price'
                                 ORDER BY p.captured_at DESC LIMIT 1),
               'sold',         (SELECT jsonb_agg(jsonb_build_object(
                                           'px', s.price_yen,
                                           'd',  s.captured_at))
                                  FROM v_price_current s
                                 WHERE s.item_id = i.id
                                   AND s.basis = 'sold_sample'
                                   AND NOT s.is_stale)
           )
           ORDER BY i.release_month DESC, i.created_at DESC
       ) AS payload,
       now() AS refreshed_at
  FROM item i;

COMMENT ON MATERIALIZED VIEW mv_search_index IS
    '前端本地搜尋索引。單列 JSON。伺服器唔記錄 query → 私隱底線落地點';

COMMIT;
