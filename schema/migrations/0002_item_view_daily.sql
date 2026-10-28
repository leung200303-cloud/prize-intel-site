-- =====================================================================
-- Migration 0002 — item_view_daily（方案 A 決策，2026-10-28）
--
-- 用途：7 日熱門榜 + IP 聚合瀏覽榜
-- 私隱：只存 (item_id, day, views) 每日聚合；無 user / session / IP / query
--
-- 套用：psql -v ON_ERROR_STOP=1 -f 0002_item_view_daily.sql
-- 呢個 migration 係 idempotent（IF NOT EXISTS）
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS item_view_daily (
    item_id uuid   NOT NULL REFERENCES item (id) ON DELETE CASCADE,
    day     date   NOT NULL,
    views   bigint NOT NULL DEFAULT 1 CHECK (views >= 0),
    PRIMARY KEY (item_id, day)
);

COMMENT ON TABLE item_view_daily IS
    '商品每日聚合瀏覽數。只准 (item_id, day, views)；禁任何使用者識別資訊';

CREATE INDEX IF NOT EXISTS idx_item_view_day ON item_view_daily (day, views DESC);

CREATE OR REPLACE VIEW v_item_popular_7d AS
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

CREATE OR REPLACE VIEW v_ip_popular_7d AS
SELECT i.ip_work_code,
       sum(v.views)::bigint AS views_7d,
       count(DISTINCT i.id)  AS item_count
  FROM item_view_daily v
  JOIN item i ON i.id = v.item_id
 WHERE v.day > CURRENT_DATE - INTERVAL '7 days'
   AND i.ip_work_code IS NOT NULL
 GROUP BY i.ip_work_code;

COMMIT;
