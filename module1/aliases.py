# -*- coding: utf-8 -*-
"""雙別名表：maker alias + ip_work alias。

⚠️ 呢個檔案係「唯一真相」：
   - schema/gen_seed.py 直接 import 呢兩個表去生成 02_seed.sql
   - Step 4 各解析器都經 resolve_maker() / resolve_ip() 落 code
   改別名只需改呢一個檔案。

PoC（Step 3）實測到嘅後綴差異全部喺 aliases 入面處理：
   ドラゴンボール シリーズ   → dragon_ball
   ポケモンモンスターシリーズ → pokemon
   ワンピース（無後綴）      → one_piece
"""
from __future__ import annotations

from normalize import match_key, strip_ip_suffix

# (code, name_jp, name_en, aliases[], sort_order)
MAKERS: list[tuple[str, str, str, list[str], int]] = [
    # ⚠️ 刻意唔放「バンダイ」做 alias：會誤中「バンダイナムコアミューズメント」（機台營運商）
    ("bandai_spirits", "BANDAI SPIRITS（バンプレスト）", "Bandai Spirits",
     ["バンプレスト", "バンプレ", "BANPRESTO", "バンダイスピリッツ", "BANDAI SPIRITS"], 10),
    ("sega_fave", "セガ フェイブ", "Sega Fave",
     ["セガ", "SEGA", "セガフェイブ", "セガ フェイブ"], 20),
    ("taito", "タイトー", "Taito", ["TAITO", "株式会社タイトー"], 30),
    ("furyu", "フリュー", "FuRyu", ["FURYU", "フリュー"], 40),
    ("eikoh", "エイコー", "Eikoh", ["EIKOH", "エイコー"], 50),
    ("system_service", "システムサービス", "System Service", ["SYSTEM SERVICE"], 60),
    ("konami_ags", "コナミアーケードゲームス", "Konami Amusement",
     ["コナミ", "KONAMI", "コナミアミューズメント"], 70),
    ("kitan_club", "奇譚クラブ", "Kitan Club", ["KITAN CLUB"], 80),
    # 2026-10-28 決策：TAKARA TOMY 唔獨立成 maker，併入 other
    ("other", "その他", "Other", ["TAKARA", "TAKARA TOMY", "タカラトミー"], 999),
]

# 系列線 (code, maker_code, name_jp, name_en, sort_order)
# ⚠️ 呢個係唯一真相：schema/gen_seed.py 同 module1/export_taxonomy.py 都係 import 佢。
#    （之前有兩份 copy，出現 18 vs 17 唔一致，2026-10-28 合併）
BRANDS: list[tuple[str, str, str, str, int]] = [
    ("maximatic", "bandai_spirits", "MAXIMATIC", "MAXIMATIC", 10),
    ("grandista", "bandai_spirits", "Grandista", "Grandista", 20),
    ("vibration_stars", "bandai_spirits", "VIBRATION STARS", "Vibration Stars", 30),
    ("memorable_saga", "bandai_spirits", "Memorable Saga", "Memorable Saga", 40),
    ("spiritflicks", "bandai_spirits", "SPIRITFLICKS", "Spiritflicks", 50),
    ("banpresto_figure", "bandai_spirits", "BANPRESTO FIGURE", "Banpresto Figure", 60),
    ("brc", "bandai_spirits", "BATTLE RECORD COLLECTION", "Battle Record Collection", 70),
    ("glitter_glamours", "bandai_spirits", "GLITTER&GLAMOURS", "Glitter & Glamours", 80),
    ("glasscape", "bandai_spirits", "Glasscape", "Glasscape", 90),
    ("espresto", "bandai_spirits", "ESPRESTO", "Espresto", 100),
    ("sofvimates", "bandai_spirits", "SOFVIMATES", "Sofvimates", 110),
    ("banpre_kuji", "bandai_spirits", "バンプレくじ", "Banpre Kuji", 120),
    ("naruto72", "bandai_spirits", "NARUTO 72 series", "NARUTO 72 series", 130),
    ("luminasta", "sega_fave", "Luminasta", "Luminasta", 10),
    ("spm", "sega_fave", "SPM（スーパープレミアムフィギュア）", "Super Premium Figure", 20),
    ("yumemirize", "sega_fave", "Yumemirize", "Yumemirize", 30),
    ("desktop_x2", "sega_fave", "Desktop×Desktop", "Desktop x Desktop", 40),
    ("desktop_cute", "taito", "Desktop Cute", "Desktop Cute", 10),
    ("amp_plus", "taito", "AMP＋", "AMP+", 20),
    ("noodle_stopper", "furyu", "ぬーどるストッパーフィギュア", "Noodle Stopper", 10),
    ("bicute_bunnies", "furyu", "BiCute Bunnies", "BiCute Bunnies", 20),
    ("bicute_dark", "furyu", "BiCute Dark", "BiCute Dark", 30),
    ("kurippy", "furyu", "くりっぴぃ", "Kurippy", 40),
    ("melffy", "furyu", "melffy", "melffy", 50),
    ("tenitol", "furyu", "TENITOL", "TENITOL", 60),
]

# 系列線別名（片假名／常見寫法）。用嚟令「ルミナスタ」「マキシマティック」都搜到。
BRAND_ALIASES: dict[str, list[str]] = {
    "maximatic": ["マキシマティック"],
    "grandista": ["グランディスタ"],
    "vibration_stars": ["バイブレーションスターズ"],
    "memorable_saga": ["メモラブルサーガ"],
    "spiritflicks": ["スピリットフリックス"],
    "banpresto_figure": ["バンプレストフィギュア"],
    "brc": ["バトルレコードコレクション"],
    "glitter_glamours": ["グリッターアンドグラマラス"],
    "glasscape": ["グラスケープ"],
    "espresto": ["エスプレスト"],
    "sofvimates": ["ソフビメイツ"],
    "banpre_kuji": ["バンプレくじ", "バンプレストくじ"],
    "naruto72": ["NARUTO72"],
    "luminasta": ["ルミナスタ"],
    "spm": ["スーパープレミアムフィギュア", "SPM"],
    "yumemirize": ["ユメミライズ"],
    "desktop_x2": ["デスクトップ"],
    "desktop_cute": ["デスクトップキュート"],
    "amp_plus": ["アンプラス"],
    "noodle_stopper": ["ヌードルストッパー", "ぬーどるすとっぱー"],
    "bicute_bunnies": ["ビキュートバニーズ"],
    "bicute_dark": ["ビキュートダーク"],
    "kurippy": ["クリッピー"],
    "melffy": ["メルフィ"],
    "tenitol": ["テニトル"],
}

# 明確排除（防止日後有人「順手」加返入 maker 表）
# 理由見 docs/IA_審核備忘.md 第三節
EXCLUDED_MAKERS: list[dict] = [
    {"name": "Namco（バンダイナムコアミューズメント）",
     "reason": "機台營運商，唔係景品製造商"},
    {"name": "Good Smile Company",
     "reason": "scale figure／ねんどろいど，唔做夾機景品；加入會污染 prize 定位"},
]

# (code, title_jp, title_en, title_zh, aliases[])
WORKS: list[tuple[str, str, str, str, list[str]]] = [
    ("kimetsu", "鬼滅の刃", "Demon Slayer", "鬼滅之刃", ["鬼滅の刃", "Kimetsu"]),
    ("one_piece", "ONE PIECE", "One Piece", "海賊王", ["ワンピース", "ONE PIECE", "海賊王"]),
    ("jujutsu", "呪術廻戦", "Jujutsu Kaisen", "咒術迴戰", ["呪術廻戦", "呪術"]),
    ("dragon_ball", "ドラゴンボール", "Dragon Ball", "龍珠",
     ["ドラゴンボール シリーズ", "ドラゴンボール", "DRAGON BALL", "龍珠"]),
    ("naruto", "NARUTO-ナルト- 疾風伝", "Naruto Shippuden", "火影忍者",
     ["NARUTO-ナルト- 疾風伝", "NARUTO", "ナルト", "火影忍者"]),
    ("chiikawa", "ちいかわ", "Chiikawa", "吉伊卡哇", ["ちいかわ"]),
    ("sanrio", "サンリオキャラクターズ", "Sanrio Characters", "Sanrio",
     ["サンリオキャラクターズ", "サンリオ"]),
    ("blue_archive", "ブルーアーカイブ", "Blue Archive", "蔚藍檔案", ["ブルーアーカイブ"]),
    ("uma_musume", "ウマ娘 プリティーダービー", "Uma Musume", "賽馬娘", ["ウマ娘"]),
    ("touhou", "東方Project", "Touhou Project", "東方Project", ["東方Project", "東方"]),
    ("evangelion", "ヱヴァンゲリヲン新劇場版", "Evangelion", "新世紀福音戰士", ["ヱヴァンゲリヲン"]),
    ("k_on", "けいおん！", "K-On!", "K-ON！", ["けいおん！", "けいおん", "K-ON!"]),
    ("zootopia", "ズートピア", "Zootopia", "優獸大都會", ["ズートピア"]),
    ("minecraft", "マインクラフト", "Minecraft", "Minecraft", ["マインクラフト", "Minecraft"]),
    ("toy_story", "トイ・ストーリー", "Toy Story", "反斗奇兵", ["トイ・ストーリー"]),
    ("kingdom", "キングダム", "Kingdom", "王者天下", ["キングダム"]),
    ("hunter", "HUNTER×HUNTER", "Hunter x Hunter", "全職獵人", ["HUNTER×HUNTER"]),
    ("overlord", "オーバーロード", "Overlord", "Overlord", ["オーバーロード"]),
    ("lycoris", "リコリス・リコイル", "Lycoris Recoil", "Lycoris Recoil", ["リコリス・リコイル"]),
    ("dandadan", "ダンダダン", "Dandadan", "Dandadan", ["ダンダダン"]),
    ("kamen_rider", "仮面ライダー", "Kamen Rider", "幪面超人", ["仮面ライダー"]),
    ("ultraman", "ウルトラマンシリーズ", "Ultraman", "超人", ["ウルトラマン"]),
    ("irodori", "いちご100％", "Strawberry 100%", "草莓100%", ["いちご100％", "いちご100%"]),
    ("to_love_ru", "To LOVEる", "To Love-Ru", "出包王女",
     ["To LOVEる ダークネス", "To LOVEる", "出包王女"]),
    ("kisekoi", "その着せ替え人形は恋をする", "My Dress-Up Darling", "戀上換裝娃娃",
     ["その着せ替え人形は恋をする", "着せ恋", "戀上換裝娃娃"]),
    ("blue_lock", "ブルーロック", "Blue Lock", "藍色監獄", ["ブルーロック"]),
    ("doraemon", "ドラえもん", "Doraemon", "多啦A夢", ["ドラえもん"]),
    ("pokemon", "ポケットモンスター", "Pokemon", "寵物小精靈",
     ["ポケモンモンスターシリーズ", "ポケットモンスター", "ポケモン", "Pokemon"]),
    ("precure", "プリキュア", "Precure", "光之美少女", ["プリキュア"]),
    ("one_punch", "ワンパンマン", "One Punch Man", "一拳超人", ["ワンパンマン"]),
    # ---- Step 3 PoC 抽樣新增 ----
    ("kusuriya", "薬屋のひとりごと", "Apothecary Diaries", "藥屋少女的呢喃", ["薬屋のひとりごと", "薬屋"]),
    ("baki", "刃牙", "Baki", "刃牙", ["刃牙"]),
    ("kochikame", "こちら葛飾区亀有公園前派出所", "Kochikame", "烏龍派出所",
     ["こちら葛飾区亀有公園前派出所", "こち亀"]),
    ("thoroughbred", "サラブレッドコレクション", "Thoroughbred Collection", "賽馬收藏",
     ["サラブレッドコレクション"]),
    ("chainsaw_man", "チェンソーマン", "Chainsaw Man", "電鋸人", ["チェンソーマン"]),
    ("gakuen_idolmaster", "学園アイドルマスター", "Gakuen Idolmaster", "學園偶像大師",
     ["学園アイドルマスター", "学マス"]),
    ("star_kirby", "星のカービィ", "Kirby", "星之卡比", ["星のカービィ", "カービィ"]),
    ("suzumiya", "涼宮ハルヒの憂鬱", "Haruhi Suzumiya", "涼宮春日的憂鬱",
     ["涼宮ハルヒの憂鬱", "涼宮ハルヒ"]),
    ("hokuto", "北斗の拳", "Fist of the North Star", "北斗之拳",
     ["北斗の拳", "FIST OF THE NORTH STAR"]),
    ("gundam_seed", "機動戦士ガンダムSEED", "Gundam SEED", "機動戰士高達SEED",
     ["機動戦士ガンダムSEED", "ガンダムSEED"]),
    ("needy_girl", "NEEDY GIRL OVERDOSE", "Needy Girl Overdose", "主播女孩重度依賴",
     ["NEEDY GIRL OVERDOSE", "NEEDY STREAMER OVERLOAD"]),
    ("lovot", "LOVOT", "LOVOT", "LOVOT", ["LOVOT"]),
    ("nyanko", "にゃんこ大戦争", "Battle Cats", "貓咪大戰爭", ["にゃんこ大戦争"]),
    ("shingeki", "進撃の巨人", "Attack on Titan", "進擊的巨人", ["進撃の巨人"]),
    ("toaru", "とある科学の超電磁砲", "A Certain Scientific Railgun", "科學超電磁砲",
     ["とある科学の超電磁砲T", "とある科学の超電磁砲"]),
    ("saki", "咲-Saki-", "Saki", "咲-Saki-", ["咲-Saki-"]),
    ("tensura", "転生したらスライムだった件", "That Time I Got Reincarnated as a Slime",
     "關於我轉生變成史萊姆這檔事", ["転生したらスライムだった件", "転スラ"]),
    ("kingdom_hearts", "KINGDOM HEARTS", "Kingdom Hearts", "王國之心", ["KINGDOM HEARTS"]),
    # ---- 2026-10-28 自測（扮散客／場主搜尋）補漏 ----
    ("frieren", "葬送のフリーレン", "Frieren", "葬送的芙莉蓮", ["フリーレン", "葬送のフリーレン"]),
    ("oshi_no_ko", "【推しの子】", "Oshi no Ko", "我推的孩子", ["推しの子", "オシのコ"]),
    ("spy_family", "SPY×FAMILY", "Spy x Family", "間諜家家酒",
     ["スパイファミリー", "スパイ×ファミリー", "アーニャ"]),
    ("tokyo_revengers", "東京リベンジャーズ", "Tokyo Revengers", "東京復仇者",
     ["東リベ", "東京リベンジャー"]),
    ("haikyu", "ハイキュー!!", "Haikyu!!", "排球少年", ["ハイキュー", "排球"]),
    ("heroaca", "僕のヒーローアカデミア", "My Hero Academia", "我的英雄學院",
     ["ヒロアカ", "僕のヒーロー"]),
    ("bleach", "BLEACH", "Bleach", "死神", ["ブリーチ"]),
    ("gintama", "銀魂", "Gintama", "銀魂", ["銀魂"]),
    ("hololive", "ホロライブ", "Hololive", "hololive", ["ホロ", "hololive"]),
    ("nijisanji", "にじさんじ", "Nijisanji", "彩虹社", ["にじさんじ"]),
    ("lovelive", "ラブライブ！", "Love Live!", "LoveLive!", ["ラブライブ", "LoveLive"]),
    ("idolmaster", "アイドルマスター", "The Idolmaster", "偶像大師",
     ["アイマス", "デレステ", "シャニマス", "ミリオンライブ"]),
    ("utapri", "うたの☆プリンスさまっ♪", "Uta no Prince-sama", "歌之王子殿下", ["うたプリ"]),
    ("sumikko", "すみっコぐらし", "Sumikko Gurashi", "角落小夥伴",
     ["すみっコ", "すみっこぐらし", "角落生物"]),
    ("opanchu", "おぱんちゅうさぎ", "Opanchu Usagi", "內褲兔", ["おぱんちゅ"]),
    ("mofusand", "mofusand", "mofusand", "mofusand", ["モフサンド", "モフサンド"]),
    ("kaiju_no8", "怪獣8号", "Kaiju No. 8", "怪獸8號", ["怪獣８号", "怪獣8"]),
    ("dungeon_meshi", "ダンジョン飯", "Delicious in Dungeon", "迷宮飯",
     ["ダンジョン飯", "ダンジョンめし"]),
    ("ranma", "らんま1/2", "Ranma 1/2", "亂馬1/2", ["らんま", "らんま½"]),
    ("urusei", "うる星やつら", "Urusei Yatsura", "福星小子", ["うる星"]),
    ("inuyasha", "犬夜叉", "Inuyasha", "犬夜叉", ["犬夜叉"]),
    ("jojo", "ジョジョの奇妙な冒険", "JoJo's Bizarre Adventure", "JOJO的奇妙冒險",
     ["ジョジョ", "JOJO"]),
    ("fate", "Fate/Grand Order", "Fate/Grand Order", "FGO", ["FGO", "フェイト", "Fate"]),
    ("monster_hunter", "モンスターハンター", "Monster Hunter", "魔物獵人", ["モンハン"]),
    ("zelda", "ゼルダの伝説", "The Legend of Zelda", "薩爾達傳說", ["ゼルダ"]),
    ("mario", "スーパーマリオ", "Super Mario", "超級瑪利歐", ["マリオ"]),
    ("dragon_quest", "ドラゴンクエスト", "Dragon Quest", "勇者鬥惡龍", ["ドラクエ", "DQ"]),
    ("disney_tsum", "ディズニーツムツム", "Disney Tsum Tsum", "Tsum Tsum", ["ツムツム"]),
    ("detective_conan", "名探偵コナン", "Detective Conan", "名偵探柯南", ["コナン"]),
    ("shinchan", "クレヨンしんちゃん", "Crayon Shin-chan", "蠟筆小新", ["しんちゃん"]),
    ("sazae", "サザエさん", "Sazae-san", "海螺小姐", ["サザエ"]),
    ("chibimaruko", "ちびまる子ちゃん", "Chibi Maruko-chan", "櫻桃小丸子", ["まる子"]),
    ("slamdunk", "SLAM DUNK", "Slam Dunk", "灌籃高手", ["スラムダンク"]),
    ("gundam", "機動戦士ガンダム", "Mobile Suit Gundam", "機動戰士高達", ["ガンダム"]),
    ("sailor_moon", "美少女戦士セーラームーン", "Sailor Moon", "美少女戰士", ["セーラームーン"]),
    ("cardcaptor", "カードキャプターさくら", "Cardcaptor Sakura", "庫洛魔法使", ["さくら"]),
    ("arknights", "アークナイツ", "Arknights", "明日方舟", ["アークナイツ", "明日方舟"]),
    ("ao_no_hako", "アオのハコ", "Blue Box", "青之蘆葦", ["アオのハコ"]),
    ("seishun_buta", "青春ブタ野郎シリーズ", "Rascal Does Not Dream", "青春豬頭少年", ["青ブタ", "青春ブタ"]),
    ("sadako", "貞子", "Sadako", "貞子", ["貞子"]),
    ("nikke", "勝利の女神NIKKE", "Goddess of Victory: Nikke", "勝利女神", ["NIKKE"]),
    ("fairytail", "FAIRY TAIL", "Fairy Tail", "妖精的尾巴", ["フェアリーテイル"]),
    ("moomin", "ムーミン", "Moomin", "姆明", ["ムーミン"]),
    ("kagurabachi", "カグラバチ", "Kagurabachi", "神樂鉢", ["カグラバチ"]),
    ("ouran", "桜蘭高校ホスト部", "Ouran High School Host Club", "櫻蘭高校男公關部", ["桜蘭"]),
    ("obungu", "お文具といっしょ", "Obungu to Issho", "與文具在一起", ["お文具"]),
    ("made_in_abyss", "メイドインアビス", "Made in Abyss", "來自深淵", ["メイドインアビス"]),
    ("kuma_pooh", "くまのプーさん", "Winnie the Pooh", "小熊維尼", ["プーさん"]),
    ("monsters_inc", "モンスターズ・インク", "Monsters, Inc.", "怪獸公司", ["モンスターズインク"]),
    ("coco", "リメンバー・ミー", "Coco", "玩轉極樂園", ["リメンバーミー"]),
    ("glay", "GLAY", "GLAY", "GLAY", ["GLAY"]),
    ("xstellar", "XStellar", "XStellar", "XStellar", ["XStellar"]),
]

# 明確排除嘅 IP（唔做主分類；防止有人「見動漫就加」）
EXCLUDED_IPS: list[dict] = [
    {"name": "原神", "reason": "日本夾機景品幾乎冇（主要中國市場），加入會拉低篩選準確度"},
    {"name": "崩壞：星穹鐵道", "reason": "同上，非日本 prize 主流"},
]


def _build_index(rows, alias_picker):
    """建 alias → code 索引，長 alias 先行（最長匹配優先）。"""
    idx: list[tuple[str, str, str]] = []
    for row in rows:
        code = row[0]
        for alias in alias_picker(row):
            key = match_key(alias)
            if key:
                idx.append((key, code, alias))
    idx.sort(key=lambda x: len(x[0]), reverse=True)
    return idx


_MAKER_IDX = _build_index(MAKERS, lambda r: [r[1], r[2], *r[3]] if r[2] else [r[1], *r[3]])
_IP_IDX = _build_index(WORKS, lambda r: [r[1], r[2], r[3], *r[4]])
_MAKER_NAMES = {r[0]: r[1] for r in MAKERS}
_IP_NAMES = {r[0]: r[1] for r in WORKS}


def _resolve(text: str | None, idx, strip_suffix: bool = False) -> dict | None:
    if not text:
        return None
    candidates = [match_key(text)]
    if strip_suffix:
        stripped = strip_ip_suffix(text)
        if stripped and stripped != text:
            candidates.append(match_key(stripped))

    for key, code, alias in idx:          # 已按長度 desc
        if any(key in c for c in candidates):
            return {"code": code, "match": alias, "method": "alias_containment"}
    return None


def resolve_maker(text: str | None) -> dict | None:
    """由任意文字（商品名／spec 表／報導句子）解析廠商 code。"""
    return _resolve(text, _MAKER_IDX)


def resolve_ip(text: str | None) -> dict | None:
    """由任意文字解析作品 code。

    先試别名包含匹配；再試剝走「シリーズ」後綴。
    """
    return _resolve(text, _IP_IDX, strip_suffix=True)


def resolve_ips(text: str | None) -> list[dict]:
    """回傳**全部**命中嘅作品（按 alias 長度 desc）。

    為咗處理真實情況：電撃PF 一段報導可以同時講幾個 IP
    （例：「『星のカービィ』…『仮面ライダーカブト』…」），
    單一 code 會靜靜咁丟資料。
    """
    if not text:
        return []
    candidates = [match_key(text)]
    stripped = strip_ip_suffix(text)
    if stripped and stripped != text:
        candidates.append(match_key(stripped))

    found: list[dict] = []
    seen: set[str] = set()
    for key, code, alias in _IP_IDX:
        if code in seen:
            continue
        if any(key in c for c in candidates):
            found.append({"code": code, "match": alias, "method": "alias_containment"})
            seen.add(code)
    return found


def maker_name(code: str | None) -> str | None:
    return _MAKER_NAMES.get(code) if code else None


def ip_name(code: str | None) -> str | None:
    return _IP_NAMES.get(code) if code else None
