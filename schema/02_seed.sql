-- =====================================================================
-- 景品採購情報搜尋站 / Prize Intel — 02_seed.sql
-- 自動生成，請勿手改：
--   廠商／作品／別名 ← module1/aliases.py（單一真相）
--   源頭清單        ← 01_源頭清單_v0.3.xlsx
-- =====================================================================

BEGIN;

-- 廠商 9 間（aliases 解決「品牌名 vs 公司名」）
INSERT INTO maker (code, name_jp, name_en, aliases, sort_order) VALUES
  ('bandai_spirits', 'BANDAI SPIRITS（バンプレスト）', 'Bandai Spirits', ARRAY['バンプレスト', 'BANPRESTO', 'バンダイスピリッツ', 'BANDAI SPIRITS', 'BANDAI SPIRITS（バンプレスト）', 'Bandai Spirits']::text[], 10),
  ('sega_fave', 'セガ フェイブ', 'Sega Fave', ARRAY['セガ', 'SEGA', 'セガフェイブ', 'セガ フェイブ', 'Sega Fave']::text[], 20),
  ('taito', 'タイトー', 'Taito', ARRAY['TAITO', '株式会社タイトー', 'タイトー', 'Taito']::text[], 30),
  ('furyu', 'フリュー', 'FuRyu', ARRAY['FURYU', 'フリュー', 'FuRyu']::text[], 40),
  ('eikoh', 'エイコー', 'Eikoh', ARRAY['EIKOH', 'エイコー', 'Eikoh']::text[], 50),
  ('system_service', 'システムサービス', 'System Service', ARRAY['SYSTEM SERVICE', 'システムサービス', 'System Service']::text[], 60),
  ('konami_ags', 'コナミアーケードゲームス', 'Konami Amusement', ARRAY['コナミ', 'KONAMI', 'コナミアミューズメント', 'コナミアーケードゲームス', 'Konami Amusement']::text[], 70),
  ('kitan_club', '奇譚クラブ', 'Kitan Club', ARRAY['KITAN CLUB', '奇譚クラブ', 'Kitan Club']::text[], 80),
  ('other', 'その他', 'Other', ARRAY['TAKARA', 'TAKARA TOMY', 'タカラトミー', 'その他', 'Other']::text[], 999)
ON CONFLICT (code) DO NOTHING;

-- 系列線 25 條（場主真正嘅搜尋入口）
INSERT INTO brand_line (code, maker_code, name_jp, name_en, sort_order) VALUES
  ('maximatic', 'bandai_spirits', 'MAXIMATIC', 'MAXIMATIC', 10),
  ('grandista', 'bandai_spirits', 'Grandista', 'Grandista', 20),
  ('vibration_stars', 'bandai_spirits', 'VIBRATION STARS', 'Vibration Stars', 30),
  ('memorable_saga', 'bandai_spirits', 'Memorable Saga', 'Memorable Saga', 40),
  ('spiritflicks', 'bandai_spirits', 'SPIRITFLICKS', 'Spiritflicks', 50),
  ('banpresto_figure', 'bandai_spirits', 'BANPRESTO FIGURE', 'Banpresto Figure', 60),
  ('brc', 'bandai_spirits', 'BATTLE RECORD COLLECTION', 'Battle Record Collection', 70),
  ('glitter_glamours', 'bandai_spirits', 'GLITTER&GLAMOURS', 'Glitter & Glamours', 80),
  ('glasscape', 'bandai_spirits', 'Glasscape', 'Glasscape', 90),
  ('espresto', 'bandai_spirits', 'ESPRESTO', 'Espresto', 100),
  ('sofvimates', 'bandai_spirits', 'SOFVIMATES', 'Sofvimates', 110),
  ('banpre_kuji', 'bandai_spirits', 'バンプレくじ', 'Banpre Kuji', 120),
  ('naruto72', 'bandai_spirits', 'NARUTO 72 series', 'NARUTO 72 series', 130),
  ('luminasta', 'sega_fave', 'Luminasta', 'Luminasta', 10),
  ('spm', 'sega_fave', 'SPM（スーパープレミアムフィギュア）', 'Super Premium Figure', 20),
  ('yumemirize', 'sega_fave', 'Yumemirize', 'Yumemirize', 30),
  ('desktop_x2', 'sega_fave', 'Desktop×Desktop', 'Desktop x Desktop', 40),
  ('desktop_cute', 'taito', 'Desktop Cute', 'Desktop Cute', 10),
  ('amp_plus', 'taito', 'AMP＋', 'AMP+', 20),
  ('noodle_stopper', 'furyu', 'ぬーどるストッパーフィギュア', 'Noodle Stopper', 10),
  ('bicute_bunnies', 'furyu', 'BiCute Bunnies', 'BiCute Bunnies', 20),
  ('bicute_dark', 'furyu', 'BiCute Dark', 'BiCute Dark', 30),
  ('kurippy', 'furyu', 'くりっぴぃ', 'Kurippy', 40),
  ('melffy', 'furyu', 'melffy', 'melffy', 50),
  ('tenitol', 'furyu', 'TENITOL', 'TENITOL', 60)
ON CONFLICT (code) DO NOTHING;

-- 作品 48 套（日文原名做 key，中英譯名／後綴變體入 aliases）
INSERT INTO ip_work (code, title_jp, title_en, title_zh, aliases) VALUES
  ('kimetsu', '鬼滅の刃', 'Demon Slayer', '鬼滅之刃', ARRAY['鬼滅の刃', 'Kimetsu', 'Demon Slayer', '鬼滅之刃']::text[]),
  ('one_piece', 'ONE PIECE', 'One Piece', '海賊王', ARRAY['ワンピース', 'ONE PIECE', '海賊王', 'One Piece']::text[]),
  ('jujutsu', '呪術廻戦', 'Jujutsu Kaisen', '咒術迴戰', ARRAY['呪術廻戦', '呪術', 'Jujutsu Kaisen', '咒術迴戰']::text[]),
  ('dragon_ball', 'ドラゴンボール', 'Dragon Ball', '龍珠', ARRAY['ドラゴンボール シリーズ', 'ドラゴンボール', 'DRAGON BALL', '龍珠', 'Dragon Ball']::text[]),
  ('naruto', 'NARUTO-ナルト- 疾風伝', 'Naruto Shippuden', '火影忍者', ARRAY['NARUTO-ナルト- 疾風伝', 'NARUTO', 'ナルト', '火影忍者', 'Naruto Shippuden']::text[]),
  ('chiikawa', 'ちいかわ', 'Chiikawa', '吉伊卡哇', ARRAY['ちいかわ', 'Chiikawa', '吉伊卡哇']::text[]),
  ('sanrio', 'サンリオキャラクターズ', 'Sanrio Characters', 'Sanrio', ARRAY['サンリオキャラクターズ', 'サンリオ', 'Sanrio Characters', 'Sanrio']::text[]),
  ('blue_archive', 'ブルーアーカイブ', 'Blue Archive', '蔚藍檔案', ARRAY['ブルーアーカイブ', 'Blue Archive', '蔚藍檔案']::text[]),
  ('uma_musume', 'ウマ娘 プリティーダービー', 'Uma Musume', '賽馬娘', ARRAY['ウマ娘', 'ウマ娘 プリティーダービー', 'Uma Musume', '賽馬娘']::text[]),
  ('touhou', '東方Project', 'Touhou Project', '東方Project', ARRAY['東方Project', '東方', 'Touhou Project']::text[]),
  ('evangelion', 'ヱヴァンゲリヲン新劇場版', 'Evangelion', '新世紀福音戰士', ARRAY['ヱヴァンゲリヲン', 'ヱヴァンゲリヲン新劇場版', 'Evangelion', '新世紀福音戰士']::text[]),
  ('k_on', 'けいおん！', 'K-On!', 'K-ON！', ARRAY['けいおん！', 'けいおん', 'K-ON!', 'K-On!', 'K-ON！']::text[]),
  ('zootopia', 'ズートピア', 'Zootopia', '優獸大都會', ARRAY['ズートピア', 'Zootopia', '優獸大都會']::text[]),
  ('minecraft', 'マインクラフト', 'Minecraft', 'Minecraft', ARRAY['マインクラフト', 'Minecraft']::text[]),
  ('toy_story', 'トイ・ストーリー', 'Toy Story', '反斗奇兵', ARRAY['トイ・ストーリー', 'Toy Story', '反斗奇兵']::text[]),
  ('kingdom', 'キングダム', 'Kingdom', '王者天下', ARRAY['キングダム', 'Kingdom', '王者天下']::text[]),
  ('hunter', 'HUNTER×HUNTER', 'Hunter x Hunter', '全職獵人', ARRAY['HUNTER×HUNTER', 'Hunter x Hunter', '全職獵人']::text[]),
  ('overlord', 'オーバーロード', 'Overlord', 'Overlord', ARRAY['オーバーロード', 'Overlord']::text[]),
  ('lycoris', 'リコリス・リコイル', 'Lycoris Recoil', 'Lycoris Recoil', ARRAY['リコリス・リコイル', 'Lycoris Recoil']::text[]),
  ('dandadan', 'ダンダダン', 'Dandadan', 'Dandadan', ARRAY['ダンダダン', 'Dandadan']::text[]),
  ('kamen_rider', '仮面ライダー', 'Kamen Rider', '幪面超人', ARRAY['仮面ライダー', 'Kamen Rider', '幪面超人']::text[]),
  ('ultraman', 'ウルトラマンシリーズ', 'Ultraman', '超人', ARRAY['ウルトラマン', 'ウルトラマンシリーズ', 'Ultraman', '超人']::text[]),
  ('irodori', 'いちご100％', 'Strawberry 100%', '草莓100%', ARRAY['いちご100％', 'いちご100%', 'Strawberry 100%', '草莓100%']::text[]),
  ('to_love_ru', 'To LOVEる', 'To Love-Ru', '出包王女', ARRAY['To LOVEる ダークネス', 'To LOVEる', '出包王女', 'To Love-Ru']::text[]),
  ('kisekoi', 'その着せ替え人形は恋をする', 'My Dress-Up Darling', '戀上換裝娃娃', ARRAY['その着せ替え人形は恋をする', '着せ恋', '戀上換裝娃娃', 'My Dress-Up Darling']::text[]),
  ('blue_lock', 'ブルーロック', 'Blue Lock', '藍色監獄', ARRAY['ブルーロック', 'Blue Lock', '藍色監獄']::text[]),
  ('doraemon', 'ドラえもん', 'Doraemon', '多啦A夢', ARRAY['ドラえもん', 'Doraemon', '多啦A夢']::text[]),
  ('pokemon', 'ポケットモンスター', 'Pokemon', '寵物小精靈', ARRAY['ポケモンモンスターシリーズ', 'ポケットモンスター', 'ポケモン', 'Pokemon', '寵物小精靈']::text[]),
  ('precure', 'プリキュア', 'Precure', '光之美少女', ARRAY['プリキュア', 'Precure', '光之美少女']::text[]),
  ('one_punch', 'ワンパンマン', 'One Punch Man', '一拳超人', ARRAY['ワンパンマン', 'One Punch Man', '一拳超人']::text[]),
  ('kusuriya', '薬屋のひとりごと', 'Apothecary Diaries', '藥屋少女的呢喃', ARRAY['薬屋のひとりごと', '薬屋', 'Apothecary Diaries', '藥屋少女的呢喃']::text[]),
  ('baki', '刃牙', 'Baki', '刃牙', ARRAY['刃牙', 'Baki']::text[]),
  ('kochikame', 'こちら葛飾区亀有公園前派出所', 'Kochikame', '烏龍派出所', ARRAY['こちら葛飾区亀有公園前派出所', 'こち亀', 'Kochikame', '烏龍派出所']::text[]),
  ('thoroughbred', 'サラブレッドコレクション', 'Thoroughbred Collection', '賽馬收藏', ARRAY['サラブレッドコレクション', 'Thoroughbred Collection', '賽馬收藏']::text[]),
  ('chainsaw_man', 'チェンソーマン', 'Chainsaw Man', '電鋸人', ARRAY['チェンソーマン', 'Chainsaw Man', '電鋸人']::text[]),
  ('gakuen_idolmaster', '学園アイドルマスター', 'Gakuen Idolmaster', '學園偶像大師', ARRAY['学園アイドルマスター', '学マス', 'Gakuen Idolmaster', '學園偶像大師']::text[]),
  ('star_kirby', '星のカービィ', 'Kirby', '星之卡比', ARRAY['星のカービィ', 'カービィ', 'Kirby', '星之卡比']::text[]),
  ('suzumiya', '涼宮ハルヒの憂鬱', 'Haruhi Suzumiya', '涼宮春日的憂鬱', ARRAY['涼宮ハルヒの憂鬱', '涼宮ハルヒ', 'Haruhi Suzumiya', '涼宮春日的憂鬱']::text[]),
  ('hokuto', '北斗の拳', 'Fist of the North Star', '北斗之拳', ARRAY['北斗の拳', 'FIST OF THE NORTH STAR', 'Fist of the North Star', '北斗之拳']::text[]),
  ('gundam_seed', '機動戦士ガンダムSEED', 'Gundam SEED', '機動戰士高達SEED', ARRAY['機動戦士ガンダムSEED', 'ガンダムSEED', 'Gundam SEED', '機動戰士高達SEED']::text[]),
  ('needy_girl', 'NEEDY GIRL OVERDOSE', 'Needy Girl Overdose', '主播女孩重度依賴', ARRAY['NEEDY GIRL OVERDOSE', 'NEEDY STREAMER OVERLOAD', 'Needy Girl Overdose', '主播女孩重度依賴']::text[]),
  ('lovot', 'LOVOT', 'LOVOT', 'LOVOT', ARRAY['LOVOT']::text[]),
  ('nyanko', 'にゃんこ大戦争', 'Battle Cats', '貓咪大戰爭', ARRAY['にゃんこ大戦争', 'Battle Cats', '貓咪大戰爭']::text[]),
  ('shingeki', '進撃の巨人', 'Attack on Titan', '進擊的巨人', ARRAY['進撃の巨人', 'Attack on Titan', '進擊的巨人']::text[]),
  ('toaru', 'とある科学の超電磁砲', 'A Certain Scientific Railgun', '科學超電磁砲', ARRAY['とある科学の超電磁砲T', 'とある科学の超電磁砲', 'A Certain Scientific Railgun', '科學超電磁砲']::text[]),
  ('saki', '咲-Saki-', 'Saki', '咲-Saki-', ARRAY['咲-Saki-', 'Saki']::text[]),
  ('tensura', '転生したらスライムだった件', 'That Time I Got Reincarnated as a Slime', '關於我轉生變成史萊姆這檔事', ARRAY['転生したらスライムだった件', '転スラ', 'That Time I Got Reincarnated as a Slime', '關於我轉生變成史萊姆這檔事']::text[]),
  ('kingdom_hearts', 'KINGDOM HEARTS', 'Kingdom Hearts', '王國之心', ARRAY['KINGDOM HEARTS', 'Kingdom Hearts', '王國之心']::text[])
ON CONFLICT (code) DO NOTHING;

-- 源頭 registry（31 條，對應 Excel 01_源頭清單）
INSERT INTO source (code, layer, name_jp, url, content_type, covers,
                    update_freq, anti_bot, crawl_mode, priority, verified, notes) VALUES
  ('bsp_prize', 'A', 'バンプレストナビ', 'https://bsp-prize.jp/', '官方', '新品予告、item 詳情、取扱店', '週次', '低', 'auto_daily', 0, true, '靜態 HTML，結構穩定，主力源'),
  ('ichiban_kuji', 'A', '一番くじ倶楽部', 'https://1kuji.com/', '官方', '一番くじ 月別 lineup、檢索', '月次＋不定期', '中', 'auto_daily', 0, true, '前端渲染，要先搵 JSON endpoint'),
  ('sega_plaza', 'A', 'セガプラザ', 'https://segaplaza.jp/', '官方', 'プライズ／くじ、店舗別取扱', '日次', '中', 'auto_daily', 0, true, '店舗頁 query 多，注意 rate limit'),
  ('taito_prize', 'A', 'タイトープライズ', 'https://taito.co.jp/taito-prize/', '官方', 'ブランド別 item 一覽', '週次', '低', 'auto_daily', 0, true, '品牌線分類清楚，好抽'),
  ('furyu', 'A', 'フリュー 官網', 'https://www.furyu.jp/', '官方', 'プライズ／グッズ', '週次', '低', 'auto_daily', 1, false, 'プライズ專頁路徑待確認'),
  ('eikoh', 'A', 'エイコー 官網', NULL, '官方', 'プライズ', '月次', '低', 'weekly', 1, false, 'URL 待補；プライズフェア 7 社之一'),
  ('system_service', 'A', 'システムサービス 官網', NULL, '官方', 'プライズ（フィギュア主力）', '月次', '低', 'weekly', 1, false, 'URL 待補；美少女フィギュア多'),
  ('konami_ags', 'A', 'コナミアーケードゲームス', NULL, '官方', 'プライズ', '月次', '低', 'weekly', 2, false, 'URL 待補；非光榮 Koei'),
  ('kitan_club', 'A', '奇譚クラブ', 'https://kitanclub.com/', '官方', 'ガチャ／プライズ', '月次', '低', 'weekly', 2, false, 'ガチャ為主，景品量少'),
  ('prtimes', 'A', 'PR TIMES', 'https://prtimes.jp/', '新聞稿', '各廠 press release（フリュー／エイコー 常用）', '日次', '中', 'auto_daily', 1, true, '補官網漏發嘅新作公告'),
  ('dengeki_prizefair', 'B', '電撃ホビーウェブ プライズフェア特集', 'https://hobby.dengeki.com/prizefair/', '媒體特集', '7 廠合同內見會全廠速報（未來 3 個月 lineup）', '年 4 回', '低', 'event_driven', 0, true, '最高 ROI。一次拿齊 7 廠預告'),
  ('dengeki_news', 'B', '電撃ホビーウェブ NEWS', 'https://hobby.dengeki.com/news/', '媒體', '新作報導、發售情報', '日次', '低', 'auto_daily', 1, true, '官方圖多，適合抽圖＋標題'),
  ('am_journal', 'B', '月刊アミューズメント・ジャーナル', 'http://am-j.co.jp/', '業界紙', '業界動向、新作情報', '月次', '低', 'manual', 2, true, '紙本／付費為主'),
  ('hobby_watch', 'B', 'ホビーウォッチ', 'https://hobby.watch.impress.co.jp/', '媒體', '新作新聞', '日次', '低', 'auto_daily', 1, true, '報導結構化程度高'),
  ('nijimen', 'B', 'にじめん', 'https://nijimen.kusuguru.co.jp/', '媒體', '女性向動漫 news', '日次', '低', 'auto_daily', 2, true, NULL),
  ('medery', 'B', 'Medery（ure.pia.co.jp）', 'https://ure.pia.co.jp/', '媒體', 'プライズ 新作', '日次', '低', 'auto_daily', 2, true, NULL),
  ('kore_tore', 'C', 'コレトレ!!', 'https://kore-tore.com/', '民間まとめ', '月別全種一覽（2026/10 有 779 種）、作品別、分類、131 頁 archive', '日次', '低', 'auto_daily', 0, true, '最接近現有競品；WordPress 有 /feed/ RSS'),
  ('kaho_memo', 'C', 'カホメモ', 'https://kaho-memo.com/', '個人 blog', '新作プライズ速報，寫得齊', '日次', '低', 'auto_daily', 1, true, '補コレトレ漏嘅款'),
  ('personal_blogs', 'C', '個人 プライズ blog 群', '例：batsumaru020908.com', '個人 blog', '不定期、質素參差', '不定期', '低', 'skip', 2, false, '低優先，只做人工發現線索'),
  ('mercari', 'D', 'メルカリ', 'https://jp.mercari.com/', '二手成交', '售出價、成交速度', '即時', '高', 'link_only', 0, true, 'ToS 禁全量爬；只存 keyword 深連結 ＋ 每款最多 3 條成交樣本'),
  ('yahoo_auction', 'D', 'Yahoo!オークション', 'https://auctions.yahoo.co.jp/', '二手成交', '落札價', '即時', '高', 'link_only', 0, true, '檢索 API 有償／需申請；只存連結 ＋ 樣本（≤3 條）'),
  ('surugaya', 'D', '駿河屋', 'https://www.suruga-ya.jp/', '中古小賣', '中古售價＋庫存', '日次', '中', 'weekly', 1, true, '有 rate limit；**中古參考價基準線**（reference_price 主力）'),
  ('mandarake', 'D', 'まんだらけ', 'https://www.mandarake.co.jp/', '中古', '售價', '日次', '中', 'weekly', 2, false, NULL),
  ('lashinbang', 'D', 'らしんばん', 'https://www.lashinbang.com/', '中古', '售價', '日次', '中', 'weekly', 2, false, NULL),
  ('paypay_flea', 'D', 'PayPayフリマ', 'https://paypayfleamarket.yahoo.co.jp/', '二手', '售出價', '即時', '高', 'link_only', 1, true, '同 メルカリ 邏輯'),
  ('amazon_jp', 'D', 'Amazon JP', 'https://www.amazon.co.jp/', '新品／轉賣', '價格', '即時', '高', 'link_only', 2, true, '只用嚟標記「有冇轉賣」'),
  ('b2b_channel', 'E', 'BtoBプラットフォーム 業界チャネル', 'https://b2b-ch.infomart.co.jp/', 'BtoB news', 'プライズフェア合同內見會公告、廠商公告', '不定期', '會員制', 'manual', 1, true, '會員制，唔爬；人工睇'),
  ('hiroichi', 'E', 'ヒロイチ（TOY''SHIROICHI）', 'https://hiroichi.jp/', '卸 catalog', '卸商品目錄', '不定期', '部分公開', 'manual', 2, true, NULL),
  ('standby', 'E', 'スタンバイ', 'https://stand-by.biz/amusement-prizes/', 'BtoB 服務', 'プライズ品／アミューズメント營運頁', '不定期', '公開頁有限', 'manual', 2, true, NULL),
  ('jaia', 'E', 'JAIA 日本アミューズメント産業協会', 'https://jaia.jp/', '業界團體', '統計、白書（宏觀非單品）', '年次', '低', 'manual', 2, true, '做行業背景數字用'),
  ('prizefair_main', 'E', 'プライズフェア（主辦）', NULL, '事件', '年 4 回業者內覽會', '年 4 回', '業者身份', 'manual', 1, false, '非公開，靠 B1 報導間接取得')
ON CONFLICT (code) DO NOTHING;

COMMIT;
