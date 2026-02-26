"""
シーンプリセットライブラリ

プロジェクションマッピング用の事前作成シーンテンプレート。
ユーザーがストーリーボードを素早く作成するための出発点として使用する。

カテゴリ:
  自然      — ocean, forest, volcano, aurora, sakura, rain, snow, desert
  都市      — neon city, futuristic, steampunk, underwater city
  ファンタジー — dragon, fairy tale, space odyssey, enchanted garden
  季節      — spring bloom, summer festival, autumn leaves, winter wonderland
  抽象      — geometric flow, liquid gold, crystal formations, color explosion

使い方:
    from workers.scene_presets import get_presets, get_preset_by_id, SCENE_PRESETS

    # 全プリセットを取得
    all_presets = get_presets()

    # カテゴリでフィルター
    nature_presets = get_presets(category="自然")

    # キーワード検索
    ocean_presets = get_presets(search="ocean")

    # IDで取得
    preset = get_preset_by_id("ocean_deep")
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ScenePreset:
    id: str                    # e.g., "ocean_deep"
    category: str              # e.g., "自然"
    name_ja: str               # e.g., "深海の世界"
    name_en: str               # e.g., "Deep Ocean World"
    description_ja: str        # Japanese visual description (2-3 sentences)
    prompt_en: str             # English prompt optimized for Gemini image generation
    mood: str                  # calm/dramatic/mysterious/etc.
    camera_angle: str          # bird_eye/wide/close_up/pan/dynamic
    color_tone: str            # warm/cool/vivid/neutral
    suggested_duration: int    # seconds
    suggested_transition: str  # crossfade/cut/fade_black/fade_white
    tags: list[str]            # searchable tags


SCENE_PRESETS: list[ScenePreset] = [

    # =========================================================================
    # 自然 (Nature)
    # =========================================================================

    ScenePreset(
        id="ocean_deep",
        category="自然",
        name_ja="深海の世界",
        name_en="Deep Ocean World",
        description_ja=(
            "漆黒の深海を、生命発光する生物たちが静かに漂う幻想的な光景。"
            "クラゲの傘が青紫の光を放ちながら水平に流れ、微細な発光プランクトンが星屑のように広がる。"
            "底知れない深海の神秘と、静謐な美しさが共存する世界。"
        ),
        prompt_en=(
            "Ultra-wide bird's-eye view of abyssal deep ocean, "
            "bioluminescent jellyfish drifting horizontally in dark indigo water, "
            "blue and violet glowing ctenophores casting ethereal light trails, "
            "swarms of luminescent plankton forming constellations in the abyss, "
            "distant anglerfish lure pulsing in deep darkness, "
            "translucent siphonophores stretching across the panorama like living threads, "
            "extreme depth, cold haunting beauty, cinematic underwater photography"
        ),
        mood="mysterious",
        camera_angle="bird_eye",
        color_tone="cool",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["ocean", "deep sea", "bioluminescent", "jellyfish", "dark", "underwater"],
    ),

    ScenePreset(
        id="forest_ancient",
        category="自然",
        name_ja="太古の森",
        name_en="Ancient Forest Floor",
        description_ja=(
            "樹齢数百年の巨木が並ぶ原生林を真上から見下ろす。"
            "苔むした地面に朝露が宝石のように輝き、シダ植物が複雑な模様を描く。"
            "差し込む光の柱が霧の中に幾何学的な美しさを生み出している。"
        ),
        prompt_en=(
            "Overhead aerial view straight down into ancient primeval forest floor, "
            "centuries-old moss-covered roots spreading like rivers across rich dark earth, "
            "intricate fern fronds unfurling in perfect spirals, dewdrops glistening like diamonds, "
            "shafts of golden morning light piercing through dense canopy creating god rays, "
            "fallen logs covered in velvet green moss, tiny wildflowers in cream and white, "
            "earthy textures of bark and lichen, deep forest stillness, "
            "National Geographic macro photography quality"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="neutral",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["forest", "moss", "ancient", "nature", "morning", "peaceful"],
    ),

    ScenePreset(
        id="volcano_lava",
        category="自然",
        name_ja="溶岩の大地",
        name_en="Volcanic Lava Flow",
        description_ja=(
            "活火山の麓を流れる溶岩が、暗黒の玄武岩を切り裂いて赤熱の川を描く。"
            "冷えた溶岩の表面に亀裂が走り、その内側からオレンジの灼熱が漏れ出す。"
            "硫黄の煙が流れる中、地球の根源的なエネルギーが解放される瞬間。"
        ),
        prompt_en=(
            "Top-down aerial view of active volcanic lava field at night, "
            "glowing rivers of molten lava flowing horizontally through black basalt landscape, "
            "intricate branching channels of orange-red incandescent magma, "
            "cooling lava crust cracking to reveal fiery interior beneath, "
            "sulfur steam vents glowing amber, ember sparks lifting and fading, "
            "stark contrast between coal-black rock and intense molten glow, "
            "raw geological power, cinematic volcanic photography"
        ),
        mood="dramatic",
        camera_angle="bird_eye",
        color_tone="warm",
        suggested_duration=20,
        suggested_transition="fade_black",
        tags=["volcano", "lava", "fire", "dramatic", "geological", "night"],
    ),

    ScenePreset(
        id="aurora_arctic",
        category="自然",
        name_ja="北極光のカーテン",
        name_en="Arctic Aurora Curtains",
        description_ja=(
            "北極圏の凍った湖面に、オーロラの神秘的なカーテンが映り込む。"
            "緑と紫の光が天と地を繋ぎ、氷の表面には幾何学的な亀裂模様が走る。"
            "宇宙と大地が一体となる、一生に一度出会えるかもしれない奇跡の光景。"
        ),
        prompt_en=(
            "Bird's-eye view of frozen arctic lake surface at night with aurora borealis reflection, "
            "vibrant emerald green and violet aurora curtains rippling across a star-filled sky, "
            "mirror-perfect reflection of northern lights on smooth black ice, "
            "geometric crack patterns in the ice surface catching aurora colors, "
            "fresh snowdrift textures at the edges, frozen air bubbles trapped beneath the ice, "
            "profound silence and cosmic scale, ethereal polar atmosphere, "
            "long-exposure astrophotography aesthetic"
        ),
        mood="mysterious",
        camera_angle="wide",
        color_tone="cool",
        suggested_duration=35,
        suggested_transition="crossfade",
        tags=["aurora", "arctic", "northern lights", "ice", "reflection", "cosmic"],
    ),

    ScenePreset(
        id="sakura_blizzard",
        category="自然",
        name_ja="桜吹雪の宴",
        name_en="Cherry Blossom Blizzard",
        description_ja=(
            "満開の桜が一斉に散り、まるで春の吹雪のように花びらが舞い踊る。"
            "薄紅色の絨毯が地面を覆い、光の中でひとつひとつの花びらが輝く。"
            "日本の春の最も美しい瞬間を、真上から捉えた幻想的な光景。"
        ),
        prompt_en=(
            "Overhead top-down view of cherry blossom storm in full bloom, "
            "thousands of delicate pink petals swirling in horizontal currents of spring wind, "
            "layer upon layer of sakura petals creating a flowing pink river across the frame, "
            "ground beneath completely carpeted in soft pink and white, "
            "individual petals catching warm golden light with translucent glow, "
            "ancient twisted cherry branches visible at edges, "
            "Japanese hanami festival atmosphere, painterly impressionist quality"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="warm",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["sakura", "cherry blossom", "spring", "Japan", "petals", "pink"],
    ),

    ScenePreset(
        id="rain_tropical",
        category="自然",
        name_ja="熱帯の雨",
        name_en="Tropical Rain on Broad Leaves",
        description_ja=(
            "熱帯雨林の大きな葉の上に、温かい雨粒が奏でるリズミカルなシンフォニー。"
            "葉脈に沿って流れる雨水が銀色の流れを作り、水面に無数の波紋が広がる。"
            "緑の饗宴の中で、雨が命の恵みを大地に届ける瞬間。"
        ),
        prompt_en=(
            "Close-up top-down view of tropical rainforest floor during monsoon rain, "
            "giant elephant ear leaves with complex vein networks channeling streams of rainwater, "
            "countless silver raindrop impacts creating expanding circular ripples in leaf puddles, "
            "rivulets of water flowing along leaf veins like tiny rivers, "
            "lush deep green with translucent backlit sections of thin leaves, "
            "raindrops suspended mid-fall catching light, vibrant life in every drop, "
            "macro photography intimacy, tropical atmosphere"
        ),
        mood="calm",
        camera_angle="close_up",
        color_tone="cool",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["rain", "tropical", "leaves", "water", "green", "nature"],
    ),

    ScenePreset(
        id="snow_crystal",
        category="自然",
        name_ja="雪の結晶の世界",
        name_en="Snowflake Crystal Kingdom",
        description_ja=(
            "真上から見た雪景色に、完璧な幾何学構造を持つ雪の結晶が降り積もる。"
            "それぞれの結晶が六角形の対称美を持ち、青白い光の中で輝く。"
            "静寂と完璧な秩序が共存する、純白の幾何学的世界。"
        ),
        prompt_en=(
            "Macro top-down view of pristine snowflakes landing on dark surface, "
            "individual snowflakes with perfect hexagonal symmetry in extraordinary detail, "
            "each crystal unique — dendrite arms, stellar plates, hollow columns, "
            "blue-white light refracting through ice crystal lattices creating prismatic sparkle, "
            "accumulating layer of fresh snow with visible crystal structure throughout, "
            "absolute silence and geometric perfection, "
            "microscope photography aesthetic at cinematic scale"
        ),
        mood="calm",
        camera_angle="close_up",
        color_tone="cool",
        suggested_duration=30,
        suggested_transition="fade_white",
        tags=["snow", "crystal", "winter", "geometric", "white", "peaceful"],
    ),

    ScenePreset(
        id="desert_dunes",
        category="自然",
        name_ja="砂漠の詩",
        name_en="Desert Dune Poetry",
        description_ja=(
            "サハラ砂漠の広大な砂丘を真上から見ると、風が刻んだ詩が広がっている。"
            "砂粒が描く有機的な曲線が縞模様となり、夕日の光が影のコントラストを強調する。"
            "地球が書いた壮大な絵画、シンプルの中に宿る無限の美しさ。"
        ),
        prompt_en=(
            "Aerial top-down view of Sahara desert sand dunes at golden hour, "
            "sweeping crescent-shaped barchans with razor-sharp ridgelines casting dramatic shadows, "
            "wind-rippled sand textures creating perfect parallel striations across the panorama, "
            "warm amber and sienna tones gradating to deep ochre in shadow troughs, "
            "lone camel caravan track crossing diagonally as a narrative element, "
            "vast emptiness suggesting infinite scale, "
            "National Geographic aerial documentary quality"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="warm",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["desert", "sand", "dunes", "golden", "minimalist", "aerial"],
    ),

    # =========================================================================
    # 都市 (Urban)
    # =========================================================================

    ScenePreset(
        id="neon_tokyo",
        category="都市",
        name_ja="東京ネオン迷宮",
        name_en="Tokyo Neon Labyrinth",
        description_ja=(
            "夜の東京を真上から見下ろすと、無数のネオンサインが巨大な迷宮を描く。"
            "赤と青の看板が路地に反射し、人々の流れが光の川となって街を走る。"
            "眠らない都市の圧倒的なエネルギーが、光と影のコントラストで浮かび上がる。"
        ),
        prompt_en=(
            "Ultra-wide aerial top-down view of Tokyo at night, Shinjuku or Shibuya district, "
            "dense grid of neon signs in red, pink, electric blue and white flooding narrow alleys, "
            "long-exposure light trails from taxis and pedestrians weaving through crossroads, "
            "Japanese kanji and katakana signage glowing with intense saturation, "
            "steam rising from ramen shop vents catching neon colors, "
            "tiny convenience store fluorescent rectangles punctuating the dark rooftops, "
            "cyberpunk density, Blade Runner meets Hiroshi Sugimoto, "
            "cinematic night photography with exceptional clarity"
        ),
        mood="dramatic",
        camera_angle="bird_eye",
        color_tone="vivid",
        suggested_duration=20,
        suggested_transition="cut",
        tags=["neon", "Tokyo", "night", "city", "cyberpunk", "Japan", "urban"],
    ),

    ScenePreset(
        id="city_futuristic",
        category="都市",
        name_ja="2150年の都市",
        name_en="City of 2150",
        description_ja=(
            "百年後の未来都市を空から見下ろすと、有機的な建築と植物が融合している。"
            "透明なチューブを走る磁気浮上列車が光の軌跡を残し、緑の屋上庭園が広がる。"
            "テクノロジーと自然が調和した、人類の理想の未来都市。"
        ),
        prompt_en=(
            "Futuristic city aerial top-down view circa 2150, "
            "biomechanical architecture with living green facades of vertical gardens and moss walls, "
            "transparent hyperloop tubes weaving between towers with maglev pods leaving light trails, "
            "hexagonal solar panel arrays on rooftops with embedded communal gardens, "
            "bioluminescent pathways connecting pedestrian plazas far below, "
            "soft blue-white energy conduits running between structures like neural networks, "
            "drone swarms forming organized delivery corridors, "
            "utopian solarpunk aesthetic, cinematic concept art quality"
        ),
        mood="mysterious",
        camera_angle="bird_eye",
        color_tone="cool",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["futuristic", "city", "solarpunk", "technology", "green", "utopia"],
    ),

    ScenePreset(
        id="steampunk_foundry",
        category="都市",
        name_ja="蒸気機関の鉄都",
        name_en="Steampunk Iron Foundry",
        description_ja=(
            "ヴィクトリア朝の技術が極限まで発展した世界の工場地帯を見下ろす。"
            "巨大な歯車と蒸気管が複雑に絡み合い、煙突からは金色の蒸気が舞い上がる。"
            "真鍮と銅の輝きが炉の赤熱に照らされ、機械文明の壮大な詩が紡がれる。"
        ),
        prompt_en=(
            "Aerial top-down view of Victorian steampunk industrial foundry district, "
            "massive interlocking brass gears and copper pipes spanning the entire panorama, "
            "furnace blast orange glow through round porthole windows in iron structures, "
            "steam billowing from ornate chimney stacks in rhythmic puffs, "
            "intricate clockwork mechanisms visible on rooftops — springs, escapements, cams, "
            "airship mooring towers with dirigibles tethered at various heights, "
            "amber oil lamp street lights casting warm pools in cobblestone alleys, "
            "industrial romanticism, detailed mechanical artistry"
        ),
        mood="dramatic",
        camera_angle="bird_eye",
        color_tone="warm",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["steampunk", "Victorian", "gears", "mechanical", "brass", "industrial"],
    ),

    ScenePreset(
        id="underwater_city",
        category="都市",
        name_ja="海底都市アトランティス",
        name_en="Atlantis Underwater City",
        description_ja=(
            "海の底に沈んだ伝説の都市アトランティスを、深海から見上げるように俯瞰する。"
            "古代の建築に珊瑚や海藻が絡まり、発光する魚の群れが街の路地を行き交う。"
            "失われた文明と生命の海が融合した、時を超えた神秘の世界。"
        ),
        prompt_en=(
            "Top-down aerial view of submerged ancient city deep underwater, "
            "Greco-Roman architecture colonized by coral reefs — columns draped in sea fans, "
            "schools of vibrant tropical fish navigating flooded marble-paved plazas, "
            "bioluminescent algae coating once-grand archways and temple facades, "
            "shafts of filtered sunlight descending from the ocean surface far above, "
            "giant sea turtles drifting past sunken amphitheaters, "
            "barnacle-encrusted statues partially buried in white sand, "
            "mythological wonder, National Geographic underwater archaeology quality"
        ),
        mood="mysterious",
        camera_angle="bird_eye",
        color_tone="cool",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["underwater", "Atlantis", "ancient", "coral", "ocean", "mythology"],
    ),

    # =========================================================================
    # ファンタジー (Fantasy)
    # =========================================================================

    ScenePreset(
        id="dragon_mountain",
        category="ファンタジー",
        name_ja="龍の山脈",
        name_en="Dragon Mountain Range",
        description_ja=(
            "雲海を越えて聳える孤高の山脈を、古代の龍が飛翔する。"
            "龍の翼が夕陽を受けて赤銅色に輝き、その影が山肌を滑るように走る。"
            "天と山の間を自在に駆ける龍の姿は、この世ならぬ力と自由の象徴。"
        ),
        prompt_en=(
            "Sweeping aerial panoramic view of jagged mountain peaks above cloud sea at sunset, "
            "ancient Eastern dragon with iridescent copper-green scales soaring horizontally, "
            "massive wingspan casting dramatic shadow across the cloud surface below, "
            "dragon's sinuous body curving gracefully through the panorama left to right, "
            "distant mountains in multiple atmospheric haze layers in purples and blues, "
            "cloud sea glowing gold and rose from hidden sun, "
            "wyvern silhouettes in background following at distance, "
            "epic fantasy art, Makoto Shinkai meets Studio Ghibli quality"
        ),
        mood="dramatic",
        camera_angle="pan",
        color_tone="warm",
        suggested_duration=30,
        suggested_transition="fade_black",
        tags=["dragon", "mountain", "fantasy", "epic", "sunset", "flying"],
    ),

    ScenePreset(
        id="fairy_tale_forest",
        category="ファンタジー",
        name_ja="妖精の森の宴",
        name_en="Fairy Banquet in Enchanted Forest",
        description_ja=(
            "月明かりの森で、小さな妖精たちが光る花々に囲まれて宴を開いている。"
            "蛍の光と妖精の翅から放たれる輝きが、夜の森を幻想的に染め上げる。"
            "きのこのテーブルを囲む妖精たちの笑い声が、木霊のように森に響く。"
        ),
        prompt_en=(
            "Top-down aerial view of moonlit enchanted forest clearing, "
            "fairy banquet on giant mushroom caps with glowing bioluminescent tops, "
            "dozens of tiny luminous fairies with iridescent wings gathered around feast tables, "
            "spiral pathways of glowing flowers winding between ancient tree roots, "
            "fireflies weaving light trails through the scene creating living constellations, "
            "dewdrop lanterns hanging from spiderweb threads catching moonlight, "
            "miniature doors in tree trunks glowing warm amber, "
            "Studio Ghibli pastoral fantasy, warm and whimsical"
        ),
        mood="mysterious",
        camera_angle="bird_eye",
        color_tone="cool",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["fairy", "forest", "fantasy", "magical", "glowing", "whimsical"],
    ),

    ScenePreset(
        id="space_odyssey",
        category="ファンタジー",
        name_ja="銀河の旅人",
        name_en="Galactic Odyssey",
        description_ja=(
            "無限の宇宙を旅する宇宙船が、色鮮やかな星雲の中を航行する。"
            "紫と青のガス雲が幾重にも重なり、誕生したばかりの星々が輝きを放つ。"
            "人類の夢と冒険心が、壮大な宇宙の叙事詩として描かれる。"
        ),
        prompt_en=(
            "Ultra-wide panoramic view drifting through a spectacular emission nebula, "
            "brilliant turquoise and magenta gas pillars like cosmic mountains stretching across, "
            "a lone spacecraft silhouette navigating through the nebula leaving ion trail, "
            "thousands of foreground stars with diffraction spikes in blue and gold, "
            "proto-stars igniting inside dark molecular cloud pillars, "
            "distant galaxy visible through gaps in the nebula as a smear of light, "
            "Hubble Space Telescope color palette but cinematic composition, "
            "profound cosmic scale, awe-inspiring deep space"
        ),
        mood="mysterious",
        camera_angle="pan",
        color_tone="vivid",
        suggested_duration=35,
        suggested_transition="crossfade",
        tags=["space", "nebula", "galaxy", "cosmic", "spaceship", "odyssey"],
    ),

    ScenePreset(
        id="enchanted_garden",
        category="ファンタジー",
        name_ja="魔法の庭園",
        name_en="Enchanted Secret Garden",
        description_ja=(
            "誰も知らない秘密の庭園に、この世のものとは思えない花々が咲き誇る。"
            "クリスタルの花弁が内側から発光し、水晶の露が宝石のように光を集める。"
            "庭園全体が生きているように脈打ち、魔法と自然が渾然一体となった世界。"
        ),
        prompt_en=(
            "Overhead view of a secret magical garden glowing with inner light, "
            "oversized flowers with translucent crystal petals refracting rainbow light internally, "
            "meandering stone pathways overgrown with luminescent moss between floral clusters, "
            "giant water lily pads floating on mirror-still ponds reflecting a lilac sky, "
            "topiary animals frozen mid-movement — unicorn, phoenix, celestial deer, "
            "golden pollen drifting like snow through shafts of enchanted light, "
            "hidden clockwork fountain at center spraying iridescent water arcs, "
            "Arthur Rackham meets modern CGI concept art"
        ),
        mood="mysterious",
        camera_angle="bird_eye",
        color_tone="vivid",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["garden", "fantasy", "crystal", "magical", "flowers", "secret"],
    ),

    # =========================================================================
    # 季節 (Seasonal)
    # =========================================================================

    ScenePreset(
        id="spring_bloom",
        category="季節",
        name_ja="春の百花繚乱",
        name_en="Spring Bloom Tapestry",
        description_ja=(
            "春の訪れとともに、野山を覆うように無数の花々が一斉に開花する。"
            "菜の花の黄色、チューリップの赤、スミレの紫が絨毯を織り成す。"
            "空から見下ろすと、大地そのものが巨大な花の絵画となっている。"
        ),
        prompt_en=(
            "Aerial top-down view of vast spring flower field in peak bloom, "
            "panoramic tapestry of tulips in red, yellow, and purple, "
            "canola flower meadows in brilliant gold creating striped patterns with violet lavender, "
            "cherry blossom petals from nearby trees drifting across the scene, "
            "winding narrow paths through the flowers with occasional flower-pickers, "
            "wild poppies and daisies filling gaps in a confetti of natural color, "
            "vibrant full-spectrum color explosion, "
            "drone photography quality at golden hour with long horizontal shadows"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="vivid",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["spring", "flowers", "bloom", "colorful", "field", "season"],
    ),

    ScenePreset(
        id="summer_festival",
        category="季節",
        name_ja="夏祭りの夜",
        name_en="Summer Festival Night",
        description_ja=(
            "夜の花火大会と縁日の灯籠が、夏の夜空と川面を彩る。"
            "浴衣の人波が屋台の間を流れ、金魚すくいの水面に提灯が映り込む。"
            "日本の夏の最も熱い夜が、上空から色鮮やかに広がる。"
        ),
        prompt_en=(
            "Aerial top-down view of Japanese summer matsuri festival at night, "
            "paper lanterns in red and white strung between bamboo poles creating a warm canopy, "
            "rows of festival stalls selling yakitori and kakigori glowing amber and red, "
            "river surface reflecting firework bursts in rippling gold and crimson below, "
            "crowds in patterned yukata moving between stalls like a flowing river of color, "
            "taiko drum circle visible in a cleared plaza with performers, "
            "goldfish in illuminated tanks at stalls catching the light, "
            "Hiroshige woodblock print meets drone photography"
        ),
        mood="dramatic",
        camera_angle="bird_eye",
        color_tone="warm",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["summer", "festival", "Japan", "matsuri", "fireworks", "night"],
    ),

    ScenePreset(
        id="autumn_leaves",
        category="季節",
        name_ja="紅葉の錦秋",
        name_en="Autumn Crimson Tapestry",
        description_ja=(
            "山一面を覆う紅葉が、赤・橙・金の三色の錦を織り成す。"
            "山道を歩く人影が紅葉の絨毯の上を行き、落ち葉が風に舞う。"
            "日本の秋の最も美しい瞬間を、空から切り取った絵画のような光景。"
        ),
        prompt_en=(
            "Aerial top-down panoramic view of Japanese maple forest in peak autumn color, "
            "dense canopy of crimson, flame orange, and burnished gold leaves with no green remaining, "
            "ancient stone path winding through the color creating a grey-white ribbon through the red, "
            "fallen leaves carpeting the ground beneath in layered depth of color, "
            "thin stream visible catching the warm leaf-filtered light in amber tones, "
            "a single red torii gate partially visible through the canopy, "
            "morning mist clinging to valleys between color hills, "
            "seasonal mono no aware, exceptional aerial photography"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="warm",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["autumn", "maple", "red", "leaves", "Japan", "seasonal"],
    ),

    ScenePreset(
        id="winter_wonderland",
        category="季節",
        name_ja="銀世界の奇跡",
        name_en="Winter Wonderland at Dawn",
        description_ja=(
            "大雪の翌朝、世界は完全な白と静寂に包まれている。"
            "木々の枝に積もった雪が朝日を受けて虹色に輝き、雪原には風が描いた紋様が広がる。"
            "すべての音を吸い込んだ雪の世界が、清らかな新しい始まりを告げる。"
        ),
        prompt_en=(
            "Aerial top-down view of pristine winter landscape at first light after heavy snowfall, "
            "snow-laden conifer branches creating white geometric patterns on dark trunks below, "
            "unblemished snow surface with complex wind-sculpted sastrugi formations, "
            "frozen stream traced by a darker line winding through the white panorama, "
            "first pale golden light of dawn casting long blue shadows across snow ridges, "
            "tiny fox tracks crossing the pristine snow — the only sign of life, "
            "absolute silence made visible, "
            "Ansel Adams meets Hiroshi Hamaya winter photography"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="cool",
        suggested_duration=30,
        suggested_transition="fade_white",
        tags=["winter", "snow", "dawn", "peaceful", "white", "minimalist"],
    ),

    # =========================================================================
    # 抽象 (Abstract)
    # =========================================================================

    ScenePreset(
        id="geometric_flow",
        category="抽象",
        name_ja="幾何学的流動",
        name_en="Geometric Flow Field",
        description_ja=(
            "コンピューターアルゴリズムが生成した有機的な幾何学模様が、水のように流れる。"
            "数学的法則に従いながらも自由に蛇行する線の群れが、見る者を催眠状態に誘う。"
            "秩序と混沌の狭間で生まれる、デジタルアートの新しい美学。"
        ),
        prompt_en=(
            "Abstract ultra-wide digital art of generative flow field visualization, "
            "thousands of curved particle lines following mathematical vector field equations, "
            "colors cycling through deep navy to electric teal to bright white along flow paths, "
            "emergent organic patterns resembling ocean currents or wind maps, "
            "varying line density creating luminous focal points across the panorama, "
            "some areas dense with tangled light, others sparse and airy, "
            "subtle turbulence and vortex formations at nodes, "
            "Tyler Hobbs Fidenza aesthetic, generative art quality"
        ),
        mood="calm",
        camera_angle="wide",
        color_tone="cool",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["abstract", "geometric", "flow", "digital", "generative", "mathematical"],
    ),

    ScenePreset(
        id="liquid_gold",
        category="抽象",
        name_ja="液体黄金の海",
        name_en="Liquid Gold Sea",
        description_ja=(
            "液体化した黄金が緩やかに波打ちながら広大な海を形成する。"
            "光が表面で踊るように反射し、深みには溶けたガラスのような透明感が宿る。"
            "物質の境界が曖昧になった先に現れる、究極の豊かさと美の象徴。"
        ),
        prompt_en=(
            "Top-down abstract view of vast liquid gold sea surface in slow motion, "
            "molten metallic gold with perfect mirror reflectivity and gentle undulating waves, "
            "highlights burning brilliant white where crests catch imaginary light source, "
            "deep trough shadows in rich dark amber and burnt sienna, "
            "surface tension effects at edge of frame revealing gold is fluid not solid, "
            "occasional deeper swirl revealing copper and bronze undertones, "
            "small rose-gold ripple from invisible droplet impact at center, "
            "luxury material visualization, Refik Anadol meets Zaha Hadid aesthetic"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="warm",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["gold", "liquid", "abstract", "luxury", "metallic", "fluid"],
    ),

    ScenePreset(
        id="crystal_formations",
        category="抽象",
        name_ja="クリスタルの宮殿",
        name_en="Crystal Palace Interior",
        description_ja=(
            "巨大な水晶の洞窟を上空から見下ろすと、無数の結晶が光を乱反射させている。"
            "自然が作り上げた完璧な幾何学が、虹色の光を四方に放ちながら輝く。"
            "鉱物の神秘と、光の魔法が融合した、地底の秘密の宮殿。"
        ),
        prompt_en=(
            "Top-down aerial view inside a vast crystal cave cavern, "
            "floor-to-ceiling selenite and quartz crystal formations in white and pale amber, "
            "hexagonal and prismatic crystal towers clustering across the panorama, "
            "internal light refraction creating rainbow spectrum caustics on cave floor, "
            "translucent crystal walls glowing with trapped bioluminescence, "
            "perfect geometric growth patterns — natural fractals visible at all scales, "
            "some crystals deep indigo-violet, others pure white or smoky quartz, "
            "Cave of Crystals Mexico meets Naica Mine, documentary quality"
        ),
        mood="mysterious",
        camera_angle="bird_eye",
        color_tone="cool",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["crystal", "abstract", "cave", "geometric", "rainbow", "mineral"],
    ),

    ScenePreset(
        id="color_explosion",
        category="抽象",
        name_ja="色彩の大爆発",
        name_en="Color Explosion Symphony",
        description_ja=(
            "全ての色が同時に爆発し、宇宙的なスケールで広がっていく。"
            "颜料と光が渾然一体となって舞い上がり、見たこともない色の嵐を生み出す。"
            "人間の感覚の限界を超えた、色彩の純粋なエネルギーの解放。"
        ),
        prompt_en=(
            "Ultra-wide abstract color explosion from center radiating outward, "
            "high-speed photography of paint collision — cyan, magenta, yellow, electric violet, "
            "liquid paint droplets frozen mid-explosion with perfect spherical forms, "
            "color ribbons stretching horizontally like aurora streamers at high velocity, "
            "spectrum transitions happening across the full width — warm left to cool right, "
            "fine ink particles creating haze between the primary color explosions, "
            "a single moment of pure chromatic energy captured at 1/10000th second, "
            "Fabian Oefner meets Alberto Seveso fluid art photography"
        ),
        mood="dramatic",
        camera_angle="wide",
        color_tone="vivid",
        suggested_duration=15,
        suggested_transition="cut",
        tags=["abstract", "color", "explosion", "vivid", "paint", "dynamic"],
    ),

    # =========================================================================
    # Additional presets to reach 30+
    # =========================================================================

    ScenePreset(
        id="ocean_coral_reef",
        category="自然",
        name_ja="珊瑚礁の万華鏡",
        name_en="Coral Reef Kaleidoscope",
        description_ja=(
            "陽光差し込む浅い珊瑚礁を真上から見ると、万華鏡のような色彩が広がる。"
            "ピンクの脳珊瑚、橙のクマノミ、紫のウミウシが色彩のパッチワークを描く。"
            "生命の多様性と、自然の造形美が共存する、海の宝箱。"
        ),
        prompt_en=(
            "Perfect top-down aerial view of shallow tropical coral reef in crystalline water, "
            "brain coral in dusty rose and cream surrounded by staghorn coral in chartreuse, "
            "clownfish pairs hovering over bulbous anemone clusters in orange and white, "
            "parrotfish in iridescent turquoise-green grazing on coral, "
            "nudibranch in electric violet crawling across pale sand, "
            "perfect visibility showing every coral polyp through lens-flat water, "
            "caustic light patterns dancing across the reef surface from gentle swell above, "
            "Rich Carey underwater photography, National Geographic quality"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="vivid",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["coral", "reef", "ocean", "colorful", "tropical", "marine life"],
    ),

    ScenePreset(
        id="ink_abstract",
        category="抽象",
        name_ja="墨流しの宇宙",
        name_en="Ink Marbling Cosmos",
        description_ja=(
            "日本の伝統技法「墨流し」が宇宙的なスケールで広がっていく。"
            "墨と絵の具が水面で踊るように広がり、渦巻き模様が銀河を思わせる。"
            "東洋の美学と宇宙の神秘が、一枚の紙の上で出会う瞬間。"
        ),
        prompt_en=(
            "Top-down aerial view of suminagashi ink marbling art at massive scale, "
            "black India ink and metallic gold paint floating on water surface, "
            "concentric ring patterns from each ink drop creating galaxy-like formations, "
            "comb-dragged lines transforming rings into feathered chevron patterns, "
            "deep burgundy and midnight blue secondary colors diffusing at edges, "
            "silver metallic ink catching imagined light with shimmer, "
            "the entire panorama one continuous flowing marbling composition, "
            "Suminagashi traditional Japanese art meets contemporary luxury design"
        ),
        mood="mysterious",
        camera_angle="bird_eye",
        color_tone="neutral",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["ink", "marbling", "abstract", "Japanese", "cosmic", "black gold"],
    ),

    ScenePreset(
        id="bioluminescent_bay",
        category="自然",
        name_ja="発光の入り江",
        name_en="Bioluminescent Bay",
        description_ja=(
            "夜の入り江に入ると、足元の水が青く光り始める。"
            "素手で波を立てるたびに、プランクトンが発光して蛍のような光の軌跡を残す。"
            "地球最古の生命体が作り出す、自然界最大の奇跡の一つ。"
        ),
        prompt_en=(
            "Top-down view of bioluminescent bay at night, Vieques Puerto Rico or Maldives, "
            "electric blue neon glow of dinoflagellate plankton lighting every wave ripple, "
            "kayak paddle strokes leaving luminous blue-white vortex trails in dark water, "
            "each wave crest a ribbon of cold fire in deep ocean darkness, "
            "stars reflected on undisturbed sections of dark water surface, "
            "distant shore outline visible only by dim village lights, "
            "the entire panorama: dark water punctuated by ghostly blue bioluminescence, "
            "rare natural phenomenon, long-exposure night photography"
        ),
        mood="mysterious",
        camera_angle="bird_eye",
        color_tone="cool",
        suggested_duration=30,
        suggested_transition="fade_black",
        tags=["bioluminescent", "bay", "night", "glow", "ocean", "plankton"],
    ),

    ScenePreset(
        id="cherry_tea_ceremony",
        category="季節",
        name_ja="茶の湯と桜",
        name_en="Tea Ceremony under Sakura",
        description_ja=(
            "満開の桜の木の下、野点の茶席が静かに設けられている。"
            "風に舞う花びらが黒楽の茶碗の上を過ぎ、薄緑の抹茶に一枚が落ちる。"
            "日本の美意識の集大成、一期一会の場が持つ静謐な緊張感。"
        ),
        prompt_en=(
            "Top-down bird's-eye view of open-air tea ceremony under flowering cherry trees, "
            "black lacquered tea tray with matcha bowl, chasen, and natsume on tatami mat, "
            "falling sakura petals mid-flight creating soft pink haze above the tea setting, "
            "raked white gravel garden surrounding the ceremony area with stepping stones, "
            "bamboo water basin (tsukubai) with moss and stone lantern visible at edge, "
            "single petal landing precisely on the rim of the matcha bowl, "
            "wabi-sabi aesthetic — quiet perfection of impermanence, "
            "Kengo Kuma meets Eikoh Hosoe photography"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="neutral",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["tea", "ceremony", "sakura", "Japanese", "zen", "wabi-sabi"],
    ),

    ScenePreset(
        id="neon_rain_reflection",
        category="都市",
        name_ja="雨に濡れたネオン",
        name_en="Neon Reflections in Rain",
        description_ja=(
            "雨上がりの夜、濡れたアスファルトがネオンサインを完璧に映し出す。"
            "水たまりに揺れる光が油絵のような抽象画を描き、雨粒が世界を歪める。"
            "都市と光と雨が三位一体となって生み出す、都会の最も美しい瞬間。"
        ),
        prompt_en=(
            "Top-down aerial view of rain-slicked city street at night, Hong Kong or Osaka, "
            "wet asphalt acting as a perfect mirror for a canopy of neon signs above, "
            "reflected reds, blues, and greens rippling in puddles across the entire panorama, "
            "rain still falling — individual droplet impacts disrupting the reflections, "
            "long-exposure light trails from taxis and motorcycles painting the wet surface, "
            "raincoat silhouettes navigating between pools of inverted neon color, "
            "oil-film iridescence in shallow puddles at intersections, "
            "Gregory Crewdson meets urban night photography"
        ),
        mood="dramatic",
        camera_angle="bird_eye",
        color_tone="vivid",
        suggested_duration=25,
        suggested_transition="cut",
        tags=["neon", "rain", "reflection", "city", "night", "urban"],
    ),

    ScenePreset(
        id="salt_flat_mirror",
        category="自然",
        name_ja="天空の鏡",
        name_en="Sky Mirror Salt Flat",
        description_ja=(
            "薄い水膜が張ったウユニ塩湖が、空全体を完璧に映し出す。"
            "天と地の区別がなくなり、雲の中を歩いているような錯覚が生まれる。"
            "地球上で最も広大な鏡が作り出す、現実と幻想が溶け合う世界。"
        ),
        prompt_en=(
            "Aerial top-down view of Salar de Uyuni salt flat at blue hour with perfect reflection, "
            "infinite flat mirror surface reflecting vivid blue sky and cotton cumulus clouds, "
            "almost no horizon — seamless transition between world and sky, "
            "thin sheet of water covering the hexagonal salt crust creating perfect reflections, "
            "a lone Toyota Land Cruiser creating a tiny wake near the center, "
            "pink flamingos visible as magenta dots on the distant salt plain, "
            "Bolivia's world at the edge of reality, "
            "perfect symmetry creating profound disorientation"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="cool",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["salt flat", "reflection", "sky", "mirror", "Bolivia", "surreal"],
    ),

    ScenePreset(
        id="japanese_garden_koi",
        category="自然",
        name_ja="錦鯉の庭",
        name_en="Koi Garden Tapestry",
        description_ja=(
            "日本庭園の池を上から見ると、錦鯉が絵の具を溶かしたように泳いでいる。"
            "紅白・紅三色・黄金の鯉が重なり合い、生きた日本画が動いている。"
            "石と水と生命が作り出す、日本美学の精髄。"
        ),
        prompt_en=(
            "Perfect overhead top-down view of Japanese garden koi pond, "
            "crystal-clear water revealing stone-and-pebble bottom with water lily pads, "
            "large nishikigoi koi in vivid red-and-white kohaku pattern, "
            "metallic gin-rin scales catching light like sequins across the orange showa sanke, "
            "ogon solid gold koi glowing like ingots through the water, "
            "trailing gossamer koi fins creating underwater brushstroke trails, "
            "weeping willow reflections adding green wavering lines to the composition, "
            "living Japanese painting, Ogata Korin meets contemporary photography"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="vivid",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["koi", "Japanese garden", "fish", "pond", "colorful", "peaceful"],
    ),

    ScenePreset(
        id="sandstorm_abstract",
        category="抽象",
        name_ja="砂嵐の詩",
        name_en="Poetry of a Sandstorm",
        description_ja=(
            "砂嵐が抽象芸術を描く。砂粒が渦を巻き、光の屈折が神秘的なパターンを生む。"
            "デザート・ピンクとオレンジの色調が、まるで宇宙の星雲のように広がる。"
            "破壊と創造が同時に起きる、砂の詩。"
        ),
        prompt_en=(
            "Abstract aerial view of massive sandstorm as pure visual texture, "
            "swirling columns of terracotta, sienna, and pale ochre sand in dynamic motion, "
            "vortex structures forming and dissolving across the full panoramic width, "
            "backlit sand particles creating luminous haze of rose gold and amber, "
            "darker sand whirlpools drilling into lighter background like ink drops in water, "
            "fractal-like patterns at multiple scales from macro swirls to individual grain clusters, "
            "Saharan haboob seen as pure abstract expressionist painting, "
            "Richard Long land art meets natural phenomenon"
        ),
        mood="dramatic",
        camera_angle="wide",
        color_tone="warm",
        suggested_duration=20,
        suggested_transition="fade_black",
        tags=["sandstorm", "abstract", "desert", "dynamic", "warm", "earth"],
    ),

    ScenePreset(
        id="northern_market_lanterns",
        category="都市",
        name_ja="燈籠の市",
        name_en="Lantern Market at Night",
        description_ja=(
            "台湾や中国の伝統的な夜市では、無数の提灯が空を彩る。"
            "赤・金・橙の提灯が重なり合い、その下では活気ある人々の往来が続く。"
            "アジアの夜の祭りが持つ、温かくて賑やかな生命のエネルギー。"
        ),
        prompt_en=(
            "Aerial top-down view of Asian night market covered by dense canopy of paper lanterns, "
            "hundreds of traditional red and gold lanterns strung at varying heights creating layers, "
            "warm amber light from each lantern illuminating the narrow market lane below, "
            "steam from hot food stalls rising to soften the lantern glow into haze, "
            "the crowd below in traditional attire visible between the lantern layers, "
            "red silk tassels hanging from each lantern catching air currents, "
            "intricate painted patterns on lantern surfaces visible in close ones, "
            "Vivian Maier meets Rene Burri street photography aesthetic"
        ),
        mood="dramatic",
        camera_angle="bird_eye",
        color_tone="warm",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["lantern", "market", "Asian", "night", "warm", "festive"],
    ),

    ScenePreset(
        id="ice_cave_blue",
        category="自然",
        name_ja="氷の大聖堂",
        name_en="Ice Cathedral",
        description_ja=(
            "アイスランドの氷河内部に生まれた氷の洞窟は、青い大聖堂のようだ。"
            "圧縮された何万年もの氷が、深いセルリアンブルーを帯びて天井に広がる。"
            "時間が止まった場所で、地球の記憶が青の光として解放される。"
        ),
        prompt_en=(
            "Top-down view inside Icelandic glacier ice cave ceiling looking up into blue vault, "
            "compressed ancient glacial ice in deep cerulean and sapphire blue overhead, "
            "thousands of years of compressed air bubbles creating swirling white cloud patterns, "
            "light filtering through the glacier surface above casting ethereal blue glow, "
            "ice stalactites hanging down with crystalline water drips suspended, "
            "melt water channels carved into the cave floor below visible as dark lines, "
            "translucent sections glowing like stained glass in a Gothic cathedral, "
            "Ryan McGinley meets glaciology documentary photography"
        ),
        mood="mysterious",
        camera_angle="bird_eye",
        color_tone="cool",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["ice", "cave", "Iceland", "blue", "glacier", "cathedral"],
    ),

    ScenePreset(
        id="autumn_river_reflection",
        category="季節",
        name_ja="紅葉川の鏡面",
        name_en="Autumn River Mirror",
        description_ja=(
            "紅葉した山々が川面に完璧に映り込み、川が燃えているように見える。"
            "静水に映る赤と金の逆さ世界が、川の蛇行に沿って続いていく。"
            "日本の秋と水が作り出す、絵画よりも美しい現実の一瞬。"
        ),
        prompt_en=(
            "Aerial top-down view of autumn mountain river with perfect foliage reflection, "
            "still black water perfectly mirroring crimson maple and amber ginkgo banks above, "
            "the reflection indistinguishable from reality — double world of color, "
            "gentle current lines breaking the reflection into impressionist strokes at bends, "
            "single autumn leaf floating on the surface creating tiny ripple rings, "
            "submerged stones visible through clear shallow sections in cool blue-grey, "
            "fallen leaves accumulating in an eddy pool in one corner — a natural mosaic, "
            "Hiroshi Hamaya autumn photography meets contemporary aerial art"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="warm",
        suggested_duration=30,
        suggested_transition="crossfade",
        tags=["autumn", "river", "reflection", "maple", "Japan", "mirror"],
    ),

    ScenePreset(
        id="galaxy_spiral",
        category="抽象",
        name_ja="渦巻銀河の夢",
        name_en="Spiral Galaxy Dream",
        description_ja=(
            "渦巻銀河を直上から俯瞰すると、宇宙の数十億の星が壮大な渦を描いている。"
            "銀河腕の間に暗黒星雲が漂い、中心核の白熱した輝きが全体を照らす。"
            "我々が住む天の川銀河の姿を、外の宇宙から眺める夢の光景。"
        ),
        prompt_en=(
            "Directly overhead view of Milky Way-type spiral galaxy in deep space, "
            "tightly wound spiral arms of blue-white young stars curving outward from brilliant core, "
            "dark dust lane rifts separating the spiral arms in deep chocolate brown, "
            "globular star clusters visible as fuzzy balls orbiting the outer halo, "
            "background galaxies of all orientations scattered throughout the black sky, "
            "core blazing in yellow-white with intense star density gradient, "
            "star-forming regions glowing in hydrogen-alpha pink at the spiral tips, "
            "Hubble Ultra Deep Field meets Atacama ALMA observatory quality"
        ),
        mood="mysterious",
        camera_angle="bird_eye",
        color_tone="cool",
        suggested_duration=35,
        suggested_transition="fade_black",
        tags=["galaxy", "space", "cosmic", "spiral", "stars", "abstract"],
    ),

    ScenePreset(
        id="monsoon_aerial",
        category="自然",
        name_ja="モンスーンの大地",
        name_en="Monsoon Aerial View",
        description_ja=(
            "モンスーンの雨季、熱帯の大地は蛇行する川と洪水原で覆われる。"
            "上空から見ると、大地が水と緑のパッチワークに変貌し、川が生命を運ぶ。"
            "自然の力が大地を塗り替える、ダイナミックな季節の変化。"
        ),
        prompt_en=(
            "Aerial top-down view of tropical monsoon landscape from high altitude, "
            "sinuous river channels braided across floodplain in silver and brown, "
            "emerald rice paddy terraces in various stages of flooding reflecting the clouded sky, "
            "oxbow lakes in turquoise-green isolated from the main channel, "
            "red laterite soil exposed on hillsides between dark jungle sections, "
            "temporary waterfalls visible as white threads on distant slopes, "
            "monsoon cloudscape shadows moving across the patchwork landscape, "
            "Yann Arthus-Bertrand Earth from Above aerial photography"
        ),
        mood="calm",
        camera_angle="bird_eye",
        color_tone="neutral",
        suggested_duration=25,
        suggested_transition="crossfade",
        tags=["monsoon", "aerial", "river", "tropical", "rain", "landscape"],
    ),
]


# =========================================================================
# ヘルパー関数
# =========================================================================

def get_presets(
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> list[ScenePreset]:
    """プリセットライブラリを取得する（カテゴリ・キーワードフィルター対応）。

    Args:
        category: カテゴリ名でフィルター (例: "自然", "都市")。None で全カテゴリ。
        search: タグ・名前・説明を対象としたキーワード検索。None で全件。

    Returns:
        フィルター済みの ScenePreset リスト（挿入順）。
    """
    results = SCENE_PRESETS

    if category:
        results = [p for p in results if p.category == category]

    if search:
        query = search.lower()
        results = [
            p for p in results
            if (
                query in p.name_ja.lower()
                or query in p.name_en.lower()
                or query in p.description_ja.lower()
                or query in p.prompt_en.lower()
                or any(query in tag.lower() for tag in p.tags)
                or query in p.id.lower()
                or query in p.mood.lower()
            )
        ]

    return results


def get_preset_by_id(preset_id: str) -> Optional[ScenePreset]:
    """IDでプリセットを取得する。

    Args:
        preset_id: プリセットID (例: "ocean_deep")

    Returns:
        一致する ScenePreset、または None。
    """
    for preset in SCENE_PRESETS:
        if preset.id == preset_id:
            return preset
    return None


def get_categories() -> list[str]:
    """利用可能なカテゴリ一覧を返す（重複なし・挿入順）。

    Returns:
        カテゴリ名のリスト。
    """
    seen: set[str] = set()
    categories: list[str] = []
    for preset in SCENE_PRESETS:
        if preset.category not in seen:
            seen.add(preset.category)
            categories.append(preset.category)
    return categories
