-- =====================================================================
-- 景品採購情報搜尋站 — DB 驗收測試套件
-- 適用：PostgreSQL 14+
-- 用法：psql -v ON_ERROR_STOP=1 -f tests.sql
--
-- 全部測試喺單一 transaction 內執行，最後 ROLLBACK，唔會污染 DB。
-- 任何一項失敗 → 最後會 RAISE EXCEPTION，exit code 非 0。
--
-- 前提：已跑 01_schema.sql + 02_seed.sql
-- =====================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TEMP TABLE t_result (
    id       serial  PRIMARY KEY,
    name     text    NOT NULL,
    expected text    NOT NULL,
    actual   text    NOT NULL,
    ok       boolean NOT NULL
);

CREATE FUNCTION pg_temp.chk(p_name text, p_cond boolean, p_detail text DEFAULT '')
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO t_result (name, expected, actual, ok)
    VALUES (p_name, 'true',
            coalesce(nullif(p_detail, ''), p_cond::text),
            coalesce(p_cond, false));
END $$;

CREATE FUNCTION pg_temp.expect_ok(p_name text, p_sql text)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_state text; v_msg text;
BEGIN
    BEGIN
        EXECUTE p_sql;
        INSERT INTO t_result (name, expected, actual, ok)
        VALUES (p_name, 'success', 'success', true);
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS v_state = RETURNED_SQLSTATE, v_msg = MESSAGE_TEXT;
        INSERT INTO t_result (name, expected, actual, ok)
        VALUES (p_name, 'success', 'raise ' || v_state || ' ' || left(v_msg, 90), false);
    END;
END $$;

CREATE FUNCTION pg_temp.expect_fail(p_name text, p_sql text, p_sqlstate text DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_state text; v_msg text;
BEGIN
    BEGIN
        EXECUTE p_sql;
        INSERT INTO t_result (name, expected, actual, ok)
        VALUES (p_name, 'raise ' || coalesce(p_sqlstate, 'any'),
                'success（唔應該成功）', false);
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS v_state = RETURNED_SQLSTATE, v_msg = MESSAGE_TEXT;
        INSERT INTO t_result (name, expected, actual, ok)
        VALUES (p_name, 'raise ' || coalesce(p_sqlstate, 'any'),
                'raise ' || v_state || ' ' || left(v_msg, 90),
                (p_sqlstate IS NULL OR v_state = p_sqlstate));
    END;
END $$;

-- ---------------------------------------------------------------------
-- T01–T04 種子資料
-- ---------------------------------------------------------------------
SELECT pg_temp.chk('T01 maker 種子 = 9',       (SELECT count(*) FROM maker) = 9);
SELECT pg_temp.chk('T02 brand_line 種子 = 18', (SELECT count(*) FROM brand_line) = 18);
-- ⚠️ ip_work 數量會隨 module1/aliases.py 增加而變，改完 aliases 要同步呢個數
SELECT pg_temp.chk('T03 ip_work 種子 = 48',    (SELECT count(*) FROM ip_work) = 48);
SELECT pg_temp.chk('T04 source 種子 = 31',     (SELECT count(*) FROM source) = 31);
SELECT pg_temp.chk('T05 maker alias 有 バンプレスト',
    EXISTS (SELECT 1 FROM maker WHERE code = 'bandai_spirits' AND 'バンプレスト' = ANY (aliases)));
SELECT pg_temp.chk('T06 バンプレスト 可解析到 bandai_spirits',
    (SELECT code FROM maker WHERE name_jp = 'BANDAI SPIRITS（バンプレスト）') = 'bandai_spirits');

-- ---------------------------------------------------------------------
-- T07–T11 item trigger（normalized_title / title_hash / fingerprint）
-- ---------------------------------------------------------------------
INSERT INTO item (id, maker_code, brand_line_code, channel_type, category,
                  title_jp, ip_work_code, release_month, size_cm)
VALUES ('11111111-1111-1111-1111-111111111111', 'bandai_spirits', 'maximatic',
        'prize', 'figure', 'アニメ「鬼滅の刃」 MAXIMATIC GIYU TOMIOKAⅡ',
        'kimetsu', '2026-10', 19);

SELECT pg_temp.chk('T07 normalized_title 已生成',
    (SELECT normalized_title <> '' FROM item WHERE id = '11111111-1111-1111-1111-111111111111'),
    (SELECT left(normalized_title, 40) FROM item WHERE id = '11111111-1111-1111-1111-111111111111'));

SELECT pg_temp.chk('T08 title_hash 64 hex',
    (SELECT length(title_hash) = 64 FROM item WHERE id = '11111111-1111-1111-1111-111111111111'));

SELECT pg_temp.chk('T09 match_fingerprint 64 hex',
    (SELECT length(match_fingerprint) = 64 FROM item WHERE id = '11111111-1111-1111-1111-111111111111'));

-- 同 spec、唔同標題 → 指紋應該一樣（L2 設計前提）
INSERT INTO item (id, maker_code, brand_line_code, channel_type, category,
                  title_jp, ip_work_code, release_month, size_cm)
VALUES ('22222222-2222-2222-2222-222222222222', 'bandai_spirits', 'maximatic',
        'prize', 'figure', '【鬼滅の刃】冨岡義勇のMAXIMATICフィギュアがオンクレに登場！',
        'kimetsu', '2026-10', 19);

SELECT pg_temp.chk('T10 同 spec 唔同標題 → 指紋相同',
    (SELECT a.match_fingerprint = b.match_fingerprint
       FROM item a, item b
      WHERE a.id = '11111111-1111-1111-1111-111111111111'
        AND b.id = '22222222-2222-2222-2222-222222222222'));

SELECT pg_temp.chk('T11 唔同標題 → title_hash 唔同',
    (SELECT a.title_hash <> b.title_hash
       FROM item a, item b
      WHERE a.id = '11111111-1111-1111-1111-111111111111'
        AND b.id = '22222222-2222-2222-2222-222222222222'));

-- ---------------------------------------------------------------------
-- T12 JAN 唯一性
-- ---------------------------------------------------------------------
UPDATE item SET jan_code = '4901234567894' WHERE id = '11111111-1111-1111-1111-111111111111';

SELECT pg_temp.expect_fail('T12 JAN 重複要報 23505', $sql$
    INSERT INTO item (maker_code, channel_type, category, title_jp, release_month, jan_code)
    VALUES ('taito', 'prize', 'figure', '重複 JAN 測試', '2026-11', '4901234567894')
$sql$, '23505');

SELECT pg_temp.expect_fail('T13 JAN 格式錯要報 23514', $sql$
    INSERT INTO item (maker_code, channel_type, category, title_jp, release_month, jan_code)
    VALUES ('taito', 'prize', 'figure', '壞 JAN', '2026-11', '12345')
$sql$, '23514');

-- ---------------------------------------------------------------------
-- T14–T18 price_ref 3 條上限 + 基準線保留
-- ---------------------------------------------------------------------
INSERT INTO price_ref (item_id, platform, basis, price_yen, captured_at)
VALUES ('11111111-1111-1111-1111-111111111111', 'surugaya', 'reference_price', 5000, '2026-10-01');
INSERT INTO price_ref (item_id, platform, basis, price_yen, captured_at)
VALUES ('11111111-1111-1111-1111-111111111111', 'mercari', 'sold_sample', 6000, '2026-10-05');
INSERT INTO price_ref (item_id, platform, basis, price_yen, captured_at)
VALUES ('11111111-1111-1111-1111-111111111111', 'yahoo_auction', 'sold_sample', 7000, '2026-10-10');

SELECT pg_temp.chk('T14 3 條價樣本',
    (SELECT count(*) = 3 FROM price_ref WHERE item_id = '11111111-1111-1111-1111-111111111111'));

-- 插第 4 條 → 應該踢走最舊成交樣本（mercari 6000），保留 surugaya 基準
INSERT INTO price_ref (item_id, platform, basis, price_yen, captured_at)
VALUES ('11111111-1111-1111-1111-111111111111', 'paypay_flea', 'sold_sample', 8000, '2026-10-12');

SELECT pg_temp.chk('T15 插第 4 條後仍然只有 3 條',
    (SELECT count(*) = 3 FROM price_ref WHERE item_id = '11111111-1111-1111-1111-111111111111'),
    (SELECT count(*)::text FROM price_ref WHERE item_id = '11111111-1111-1111-1111-111111111111'));

SELECT pg_temp.chk('T16 最舊成交樣本（mercari）被淘汰',
    NOT EXISTS (SELECT 1 FROM price_ref
                 WHERE item_id = '11111111-1111-1111-1111-111111111111' AND platform = 'mercari'));

SELECT pg_temp.chk('T17 surugaya 基準線仍然保留',
    EXISTS (SELECT 1 FROM price_ref
             WHERE item_id = '11111111-1111-1111-1111-111111111111'
               AND platform = 'surugaya' AND basis = 'reference_price'));

SELECT pg_temp.chk('T18 最新成交樣本（paypay）保留',
    EXISTS (SELECT 1 FROM price_ref
             WHERE item_id = '11111111-1111-1111-1111-111111111111' AND platform = 'paypay_flea'));

-- 同平台基準線重複 → 23505
SELECT pg_temp.expect_fail('T19 基準線重複要報 23505', $sql$
    INSERT INTO price_ref (item_id, platform, basis, price_yen, captured_at)
    VALUES ('11111111-1111-1111-1111-111111111111', 'surugaya', 'reference_price', 5200, '2026-10-20')
$sql$, '23505');

-- UPSERT 基準線應該成功（正式做法）
SELECT pg_temp.expect_ok('T20 基準線 UPSERT 成功', $sql$
    INSERT INTO price_ref (item_id, platform, basis, price_yen, captured_at)
    VALUES ('11111111-1111-1111-1111-111111111111', 'surugaya', 'reference_price', 4800, '2026-10-20')
    ON CONFLICT (item_id, platform) WHERE basis = 'reference_price'
    DO UPDATE SET price_yen = EXCLUDED.price_yen, captured_at = EXCLUDED.captured_at
$sql$);

SELECT pg_temp.chk('T21 UPSERT 後基準價 = 4800',
    (SELECT price_yen = 4800 FROM price_ref
      WHERE item_id = '11111111-1111-1111-1111-111111111111' AND basis = 'reference_price'));

-- ---------------------------------------------------------------------
-- T22–T23 過期價 is_stale（唔刪，只標記）
-- ---------------------------------------------------------------------
INSERT INTO price_ref (item_id, platform, basis, price_yen, captured_at)
VALUES ('22222222-2222-2222-2222-222222222222', 'surugaya', 'reference_price', 3000,
        CURRENT_DATE - INTERVAL '40 days');

SELECT pg_temp.chk('T22 40 日前價格 is_stale = true',
    (SELECT is_stale FROM v_price_current
      WHERE item_id = '22222222-2222-2222-2222-222222222222'));

SELECT pg_temp.chk('T23 過期價仍然存在（保留歷史）',
    (SELECT count(*) = 1 FROM price_ref WHERE item_id = '22222222-2222-2222-2222-222222222222'));

-- ---------------------------------------------------------------------
-- T24–T28 一番くじ 父子結構
-- ---------------------------------------------------------------------
INSERT INTO item (id, maker_code, channel_type, category, title_jp, release_month,
                  is_kuji_pool, ip_work_code)
VALUES ('33333333-3333-3333-3333-333333333333', 'bandai_spirits', 'ichiban_kuji',
        'figure', '一番くじ テスト 獎池', '2027-01', true, 'one_piece');

INSERT INTO item (id, maker_code, channel_type, category, title_jp, release_month,
                  parent_item_id, prize_tier, ip_work_code)
VALUES ('44444444-4444-4444-4444-444444444444', 'bandai_spirits', 'ichiban_kuji',
        'figure', 'A賞 テスト', '2027-01',
        '33333333-3333-3333-3333-333333333333', 'A賞', 'one_piece');

SELECT pg_temp.chk('T24 賞品正確掛喺獎池',
    (SELECT parent_item_id = '33333333-3333-3333-3333-333333333333'
       FROM item WHERE id = '44444444-4444-4444-4444-444444444444'));

-- 獎池唔可以有 parent
SELECT pg_temp.expect_fail('T25 獎池有 parent 要報 23514', $sql$
    UPDATE item SET parent_item_id = '44444444-4444-4444-4444-444444444444'
     WHERE id = '33333333-3333-3333-3333-333333333333'
$sql$, '23514');

-- 有 prize_tier 但冇 parent
SELECT pg_temp.expect_fail('T26 prize_tier 冇 parent 要報 23514', $sql$
    INSERT INTO item (maker_code, channel_type, category, title_jp, release_month, prize_tier)
    VALUES ('taito', 'ichiban_kuji', 'figure', '孤兒賞品', '2027-02', 'B賞')
$sql$, '23514');

-- 夾機景品唔可以掛喺池下面
SELECT pg_temp.expect_fail('T27 prize 通道做賞品要報 23514', $sql$
    INSERT INTO item (maker_code, channel_type, category, title_jp, release_month,
                      parent_item_id, prize_tier)
    VALUES ('taito', 'prize', 'figure', '錯通道賞品', '2027-02',
            '33333333-3333-3333-3333-333333333333', 'C賞')
$sql$, '23514');

-- ---------------------------------------------------------------------
-- T28–T31 循環 parent 引用（Step 3.5 補嘅漏洞）
-- ---------------------------------------------------------------------
-- 建三層鏈：6666 ← 7777 ← 8888（全部 ichiban_kuji，非 pool）
INSERT INTO item (id, maker_code, channel_type, category, title_jp, release_month)
VALUES ('66666666-6666-6666-6666-666666666666', 'taito', 'ichiban_kuji',
        'figure', '鏈 L1', '2027-03');
INSERT INTO item (id, maker_code, channel_type, category, title_jp, release_month,
                  parent_item_id, prize_tier)
VALUES ('77777777-7777-7777-7777-777777777777', 'taito', 'ichiban_kuji',
        'figure', '鏈 L2', '2027-03',
        '66666666-6666-6666-6666-666666666666', 'L2');
INSERT INTO item (id, maker_code, channel_type, category, title_jp, release_month,
                  parent_item_id, prize_tier)
VALUES ('88888888-8888-8888-8888-888888888888', 'taito', 'ichiban_kuji',
        'figure', '鏈 L3', '2027-03',
        '77777777-7777-7777-7777-777777777777', 'L3');

SELECT pg_temp.chk('T28 三層鏈建立成功',
    (SELECT count(*) = 3 FROM item
      WHERE id IN ('66666666-6666-6666-6666-666666666666',
                   '77777777-7777-7777-7777-777777777777',
                   '88888888-8888-8888-8888-888888888888')));

-- A→B→C→A 循環：CHECK 擋唔住，要靠 trigger
SELECT pg_temp.expect_fail('T29 循環引用 A→B→C→A 要報 23514', $sql$
    UPDATE item SET parent_item_id = '88888888-8888-8888-8888-888888888888'
     WHERE id = '66666666-6666-6666-6666-666666666666'
$sql$, '23514');

-- 自我引用
SELECT pg_temp.expect_fail('T30 自我引用要報 23514', $sql$
    UPDATE item SET parent_item_id = '66666666-6666-6666-6666-666666666666'
     WHERE id = '66666666-6666-6666-6666-666666666666'
$sql$, '23514');

-- 正常更新 parent（非循環）應該成功
SELECT pg_temp.expect_ok('T31 正常改 parent 成功', $sql$
    UPDATE item SET parent_item_id = '33333333-3333-3333-3333-333333333333'
     WHERE id = '77777777-7777-7777-7777-777777777777'
$sql$);

-- ---------------------------------------------------------------------
-- T32–T34 級聯刪除
-- ---------------------------------------------------------------------
INSERT INTO item_source (item_id, source_code, source_url, raw_title)
VALUES ('22222222-2222-2222-2222-222222222222', 'bsp_prize',
        'https://bsp-prize.jp/item/2830561/', 'アニメ「鬼滅の刃」 MAXIMATIC GIYU TOMIOKAⅡ');

SELECT pg_temp.chk('T32 item_source 已寫入',
    (SELECT count(*) = 1 FROM item_source WHERE item_id = '22222222-2222-2222-2222-222222222222'));

DELETE FROM item WHERE id = '22222222-2222-2222-2222-222222222222';

SELECT pg_temp.chk('T33 刪 item → item_source 級聯清空',
    (SELECT count(*) = 0 FROM item_source WHERE item_id = '22222222-2222-2222-2222-222222222222'));

SELECT pg_temp.chk('T34 刪 item → price_ref 級聯清空',
    (SELECT count(*) = 0 FROM price_ref WHERE item_id = '22222222-2222-2222-2222-222222222222'));

-- ---------------------------------------------------------------------
-- T35–T38 私隱閘（schema 層封死）
-- ---------------------------------------------------------------------
SELECT pg_temp.chk('T35 冇使用者／查詢紀錄表',
    (SELECT count(*) = 0 FROM information_schema.tables
      WHERE table_schema = 'public'
        AND table_name IN ('user','users','account','accounts','session','sessions',
                           'query_log','query_logs','search_history','search_log',
                           'purchase_record','purchase_records','favorite','favorites',
                           'user_profile','analytics_event','analytics_events')));

SELECT pg_temp.chk('T36 全庫冇 user_id／session_id／ip 欄位',
    (SELECT count(*) = 0 FROM information_schema.columns
      WHERE table_schema = 'public'
        AND column_name IN ('user_id','session_id','visitor_id','ip_address','ip')));

SELECT pg_temp.chk('T37 page_view_daily 只有 2 欄（day, views）',
    (SELECT count(*) = 2 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'page_view_daily'));

INSERT INTO page_view_daily (day, views) VALUES (CURRENT_DATE, 120)
ON CONFLICT (day) DO UPDATE SET views = page_view_daily.views + EXCLUDED.views;

SELECT pg_temp.chk('T38 匿名彙總可累加',
    (SELECT views >= 120 FROM page_view_daily WHERE day = CURRENT_DATE));

-- ---------------------------------------------------------------------
-- T39–T40 前端索引（私隱設計落地點）
-- ---------------------------------------------------------------------
REFRESH MATERIALIZED VIEW mv_search_index;

SELECT pg_temp.chk('T39 mv_search_index 有 payload',
    (SELECT payload IS NOT NULL FROM mv_search_index LIMIT 1));

SELECT pg_temp.chk('T40 mv_search_index 只有 1 列（單一 JSON 檔）',
    (SELECT count(*) = 1 FROM mv_search_index));

-- ---------------------------------------------------------------------
-- T41–T45 商品級瀏覽聚合（方案 A）＋私隱邊界
-- ---------------------------------------------------------------------
SELECT pg_temp.chk('T41 item_view_daily 只有 3 欄',
    (SELECT count(*) = 3 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'item_view_daily'));

SELECT pg_temp.chk('T42 item_view_daily 冇 user/ip/query 欄位',
    (SELECT count(*) = 0 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'item_view_daily'
        AND column_name IN ('user_id','session_id','visitor_id','ip_address','ip',
                            'user_agent','ua','query','query_string','referrer')));

INSERT INTO item_view_daily (item_id, day, views)
VALUES ('11111111-1111-1111-1111-111111111111', CURRENT_DATE, 3)
ON CONFLICT (item_id, day) DO UPDATE SET views = item_view_daily.views + EXCLUDED.views;

INSERT INTO item_view_daily (item_id, day, views)
VALUES ('11111111-1111-1111-1111-111111111111', CURRENT_DATE, 4)
ON CONFLICT (item_id, day) DO UPDATE SET views = item_view_daily.views + EXCLUDED.views;

SELECT pg_temp.chk('T43 同日重複提交會累加（3+4=7）',
    (SELECT views = 7 FROM item_view_daily
      WHERE item_id = '11111111-1111-1111-1111-111111111111' AND day = CURRENT_DATE));

INSERT INTO item_view_daily (item_id, day, views)
VALUES ('11111111-1111-1111-1111-111111111111', CURRENT_DATE - 1, 5);

SELECT pg_temp.chk('T44 7 日榜會彙總多日',
    (SELECT views_7d = 12 FROM v_item_popular_7d
      WHERE item_id = '11111111-1111-1111-1111-111111111111'));

SELECT pg_temp.chk('T45 IP 聚合榜唔會漏（kimetsu）',
    (SELECT item_count >= 1 FROM v_ip_popular_7d WHERE ip_work_code = 'kimetsu'));

DELETE FROM item WHERE id = '11111111-1111-1111-1111-111111111111';

SELECT pg_temp.chk('T46 刪 item → item_view_daily 級聯清空',
    (SELECT count(*) = 0 FROM item_view_daily
      WHERE item_id = '11111111-1111-1111-1111-111111111111'));

-- ---------------------------------------------------------------------
-- 結果
-- ---------------------------------------------------------------------
\echo ''
\echo '================ DB 驗收結果 ================'
SELECT id, CASE WHEN ok THEN 'PASS' ELSE 'FAIL' END AS result, name, expected, actual
  FROM t_result ORDER BY id;

SELECT count(*) FILTER (WHERE ok)      AS passed,
       count(*) FILTER (WHERE NOT ok)  AS failed,
       count(*)                        AS total
  FROM t_result;

DO $$
DECLARE v_failed integer;
BEGIN
    SELECT count(*) INTO v_failed FROM t_result WHERE NOT ok;
    IF v_failed > 0 THEN
        RAISE EXCEPTION '% 項測試失敗', v_failed;
    END IF;
    RAISE NOTICE '全部 % 項測試通過', (SELECT count(*) FROM t_result);
END $$;

ROLLBACK;
