"""
プロンプトテンプレートシステム

7テーマ x 5コース = 35パターンの最適化されたプロンプトテンプレート。
画像生成（Gemini/Imagen）および動画生成（Runway i2v）の両方に対応。

各テンプレートには以下のキーを含む:
  - base: シーンの基本描写（英語）
  - imagen_modifier: Imagen用の追加修飾（16:9→4.6:1クロップ考慮）
  - gemini_modifier: Geminiテンプレートガイド用の追加指示
  - video_motion: 動画生成時のモーション指示
  - color_palette: 推奨カラーパレット（HEXリスト）
  - mood: 感情/雰囲気キーワード

使い方:
    from workers.prompt_templates import get_prompt, get_video_motion, PROMPT_TEMPLATES

    # 画像生成プロンプトを取得
    prompt = get_prompt("ocean", "welcome", provider="gemini")

    # 動画モーション指示を取得
    motion = get_video_motion("ocean", "welcome")
"""

from typing import Optional


PROMPT_TEMPLATES: dict[str, dict[str, dict[str, str | list[str]]]] = {
    # =========================================================================
    # ZEN (禅)
    # =========================================================================
    "zen": {
        "welcome": {
            "base": (
                "Serene Zen garden viewed from directly above, "
                "raked white sand with flowing parallel lines stretching across the entire width, "
                "scattered cherry blossom petals in soft pink, "
                "small moss-covered stones arranged asymmetrically, "
                "ink wash painting gradually appearing on the sand surface, "
                "meditative tranquility, Japanese wabi-sabi aesthetic"
            ),
            "imagen_modifier": (
                "Concentrate all visual content in the center horizontal band, "
                "top and bottom 25% should be uniform raked sand texture only, "
                "panoramic ultra-wide composition flowing left to right"
            ),
            "gemini_modifier": (
                "Match the template layout precisely, fill the golden border area with content, "
                "keep plate positions clear of major elements, "
                "seamless panoramic flow across all four zones"
            ),
            "video_motion": (
                "Slow meditative motion: sand raking lines slowly extending left to right, "
                "cherry blossom petals drifting gently downward with slight horizontal drift, "
                "ink wash painting gradually appearing and fading, "
                "seamless looping ambient motion"
            ),
            "color_palette": ["#F5F0E8", "#D4A5A5", "#5C4033", "#8B9467", "#2C2C2C"],
            "mood": "meditative, serene, wabi-sabi, contemplative",
        },
        "appetizer": {
            "base": (
                "Top-down view of a pristine stream flowing across a Zen rock garden, "
                "crystal clear water with visible pebbles beneath, "
                "miniature bamboo water feature (shishi-odoshi), "
                "fresh green bamboo leaves scattered on wet stone, "
                "small zen stones stacked in cairns, "
                "delicate Japanese culinary presentation aesthetic"
            ),
            "imagen_modifier": (
                "Horizontal stream flow from left to right across the center band, "
                "upper and lower regions are dry raked sand, "
                "all elements confined to middle 50% of height"
            ),
            "gemini_modifier": (
                "Water stream should flow horizontally through the center of the template, "
                "zen stones positioned between plate markers, "
                "maintain the ultra-wide panoramic feel"
            ),
            "video_motion": (
                "Gentle water flow from left to right, subtle ripples around stones, "
                "bamboo leaves gently bobbing on the water surface, "
                "shishi-odoshi tipping slowly, "
                "continuous flowing motion suitable for seamless loop"
            ),
            "color_palette": ["#4A7C59", "#87CEEB", "#D4C5A9", "#2F4F4F", "#F0E6D3"],
            "mood": "fresh, natural, delicate, refined",
        },
        "soup": {
            "base": (
                "Bird's-eye view of steam rising and transforming into a misty mountain landscape, "
                "autumn foliage in red and gold scattered across the surface, "
                "distant temple silhouettes emerging from fog, "
                "traditional Japanese sumi-e brushwork style, "
                "warm steam wisps creating organic patterns"
            ),
            "imagen_modifier": (
                "Mountain silhouettes along the center horizontal line, "
                "steam rising from bottom center, autumn leaves concentrated in middle band, "
                "top and bottom are empty misty gradients"
            ),
            "gemini_modifier": (
                "Misty atmosphere should fill the template area, "
                "mountain silhouettes as a thin horizontal band through the middle, "
                "steam effects are subtle and translucent"
            ),
            "video_motion": (
                "Steam wisps slowly rising and drifting horizontally, "
                "fog gently rolling through mountain valleys, "
                "autumn leaves slowly descending with gentle rotation, "
                "ethereal slow-motion atmospheric movement"
            ),
            "color_palette": ["#C0392B", "#E67E22", "#F1C40F", "#7F8C8D", "#ECF0F1"],
            "mood": "warm, nostalgic, contemplative, atmospheric",
        },
        "main": {
            "base": (
                "Dramatic ink brush dragon painting itself across a wide surface, "
                "bold black sumi ink strokes on cream paper texture, "
                "dragon transforming into powerful ocean waves (ukiyo-e style), "
                "dynamic calligraphy strokes sweeping horizontally, "
                "red seal stamp (hanko) accent, "
                "powerful Japanese artistic tradition"
            ),
            "imagen_modifier": (
                "Dragon body stretches horizontally across the full width, "
                "ink splatters confined to center band, "
                "cream/white paper texture fills the background uniformly"
            ),
            "gemini_modifier": (
                "Ink dragon should flow across all four zones of the template, "
                "calligraphy strokes follow the horizontal axis, "
                "bold and dramatic but respecting plate positions"
            ),
            "video_motion": (
                "Ink brush strokes painting themselves in real-time from left to right, "
                "dragon body undulating with fluid motion, "
                "waves crashing dynamically, ink droplets splattering, "
                "energetic brushwork animation"
            ),
            "color_palette": ["#1A1A1A", "#F5F0E0", "#C0392B", "#2C3E50", "#7F8C8D"],
            "mood": "powerful, dynamic, artistic, dramatic",
        },
        "dessert": {
            "base": (
                "Massive cherry blossom storm viewed from above, "
                "thousands of pink petals swirling in a horizontal vortex, "
                "petals gradually forming congratulatory kanji characters, "
                "golden light particles streaming horizontally, "
                "celebration atmosphere with sakura blizzard, "
                "luminous and festive Japanese spring"
            ),
            "imagen_modifier": (
                "Petal vortex centered horizontally, golden particles in center band, "
                "kanji formation in the middle third, "
                "softer petal density at top and bottom edges"
            ),
            "gemini_modifier": (
                "Cherry blossoms should fill the entire template area, "
                "golden light concentrated in the center band, "
                "festive climax atmosphere across all zones"
            ),
            "video_motion": (
                "Cherry blossom petals swirling in a horizontal cyclone, "
                "golden particles streaming left to right, "
                "kanji characters materializing from petal clusters, "
                "accelerating festive motion building to a crescendo"
            ),
            "color_palette": ["#FFB7C5", "#FFD700", "#FF69B4", "#FFF0F5", "#DAA520"],
            "mood": "celebratory, luminous, festive, climactic",
        },
    },

    # =========================================================================
    # FIRE (炎)
    # =========================================================================
    "fire": {
        "welcome": {
            "base": (
                "Glowing embers and sparks igniting into elegant flame patterns on a dark surface, "
                "warm amber and deep crimson tones spreading from scattered ember clusters, "
                "dramatic theatrical lighting with subtle smoke wisps, "
                "volcanic glass-like dark background"
            ),
            "imagen_modifier": (
                "Embers scattered in center horizontal band, flames rising within middle 50%, "
                "dark background extends to edges, "
                "no bright content in top/bottom 25%"
            ),
            "gemini_modifier": (
                "Ember clusters positioned between plate markers, "
                "flame patterns flow horizontally through the template center, "
                "dark background respects the template border"
            ),
            "video_motion": (
                "Embers slowly igniting one by one from left to right, "
                "flames flickering with natural fire movement, "
                "sparks drifting upward with gentle random motion, "
                "warm pulsing glow, slow atmospheric buildup"
            ),
            "color_palette": ["#FF4500", "#FF8C00", "#8B0000", "#1A0A00", "#FFD700"],
            "mood": "dramatic, warm, theatrical, igniting",
        },
        "appetizer": {
            "base": (
                "Top-down aerial view of volcanic landscape with lava rivers flowing horizontally, "
                "intricate branching lava patterns glowing orange-red on black basalt surface, "
                "ember particles floating above the lava channels, "
                "crystalline mineral formations along lava edges"
            ),
            "imagen_modifier": (
                "Lava rivers flow horizontally through the center, "
                "black basalt fills upper and lower regions, "
                "branching patterns spread within middle band"
            ),
            "gemini_modifier": (
                "Lava channels should weave between the plate positions, "
                "branching patterns span across all four zones, "
                "dark basalt background fills inactive areas"
            ),
            "video_motion": (
                "Lava flowing slowly from left to right through channels, "
                "molten surface pulsing with heat, "
                "ember particles rising and drifting, "
                "crystalline edges glinting with reflected lava glow"
            ),
            "color_palette": ["#FF4500", "#CC3300", "#000000", "#FF6600", "#FFD700"],
            "mood": "volcanic, intense, passionate, elemental",
        },
        "soup": {
            "base": (
                "Hundreds of candlelight flames arranged in flowing formation across the surface, "
                "golden glow creating mesmerizing wave patterns, "
                "reflections on polished dark surface, "
                "intimate romantic atmosphere with warm bokeh"
            ),
            "imagen_modifier": (
                "Candle flames arranged in horizontal rows in center band, "
                "golden reflections extend vertically but dim toward edges, "
                "dark polished surface in upper/lower regions"
            ),
            "gemini_modifier": (
                "Candlelight formations flow across all four template zones, "
                "warm golden glow fills the center content area, "
                "reflections visible in plate position areas"
            ),
            "video_motion": (
                "Candle flames gently flickering in synchronized waves, "
                "golden light pulsing rhythmically from left to right, "
                "reflections shimmering on polished surface, "
                "slow mesmerizing dance of light"
            ),
            "color_palette": ["#FFD700", "#FFA500", "#8B6914", "#1A0A00", "#FFFACD"],
            "mood": "romantic, intimate, mesmerizing, warm",
        },
        "main": {
            "base": (
                "Epic fire burst erupting from the center spreading outward, "
                "phoenix wings unfurling across the full width in deep reds and oranges, "
                "spectacular and powerful energy display, "
                "flame tendrils forming intricate feather-like patterns"
            ),
            "imagen_modifier": (
                "Phoenix wings extend horizontally across entire width, "
                "fire burst centered vertically in middle band, "
                "wing tips reach left and right edges, "
                "dark background above and below"
            ),
            "gemini_modifier": (
                "Phoenix body centered in the template, wings spreading to zone 1 and zone 4, "
                "dramatic but plate positions remain relatively dark, "
                "maximum visual impact across the panorama"
            ),
            "video_motion": (
                "Explosive fire burst expanding outward from center, "
                "phoenix wings unfurling with powerful sweeping motion, "
                "flame tendrils writhing dynamically, "
                "ember shower cascading, peak dramatic energy"
            ),
            "color_palette": ["#FF0000", "#FF4500", "#FF8C00", "#8B0000", "#FFD700"],
            "mood": "epic, powerful, spectacular, climactic",
        },
        "dessert": {
            "base": (
                "Fireworks display cascading across the entire surface, "
                "sparkler trails writing luminous patterns horizontally, "
                "grand celebration finale with fire and golden light, "
                "champagne sparkle effects mixed with warm fire tones"
            ),
            "imagen_modifier": (
                "Firework bursts distributed across center band, "
                "sparkler trails flow horizontally, "
                "celebration effects concentrated in middle 60%"
            ),
            "gemini_modifier": (
                "Firework bursts positioned across all four zones, "
                "sparkler trails connect the zones horizontally, "
                "festive grand finale atmosphere filling the template"
            ),
            "video_motion": (
                "Fireworks launching and bursting in sequence left to right, "
                "sparkler trails writing glowing patterns, "
                "golden confetti falling, "
                "celebratory explosion of light and fire"
            ),
            "color_palette": ["#FFD700", "#FF4500", "#FF69B4", "#FFFFFF", "#FF8C00"],
            "mood": "celebratory, spectacular, grand, festive",
        },
    },

    # =========================================================================
    # OCEAN (海)
    # =========================================================================
    "ocean": {
        "welcome": {
            "base": (
                "Deep ocean floor viewed from directly above, "
                "crystal clear water with sunlight caustic patterns dancing on sandy bottom, "
                "schools of tropical fish swimming in formation, "
                "sea grass gently swaying, scattered shells and starfish, "
                "bioluminescent plankton dots creating a magical underwater glow"
            ),
            "imagen_modifier": (
                "Fish schools swim horizontally through center band, "
                "caustic light patterns concentrated in middle area, "
                "uniform sandy bottom in upper and lower regions"
            ),
            "gemini_modifier": (
                "Fish schools flow across all four template zones, "
                "caustic light patterns fill the content area, "
                "sea grass positioned near plate markers at the bottom edge"
            ),
            "video_motion": (
                "Gentle wave-like motion of caustic light patterns, "
                "bioluminescent particles floating slowly, "
                "fish schools gliding smoothly from left to right, "
                "sea grass swaying with subtle current, "
                "calm ambient underwater movement"
            ),
            "color_palette": ["#006994", "#40E0D0", "#F0E68C", "#00CED1", "#1A3A4A"],
            "mood": "serene, magical, underwater, inviting",
        },
        "appetizer": {
            "base": (
                "Vibrant coral reef panorama viewed from above, "
                "colorful tropical fish migrating horizontally among coral formations, "
                "sea anemones with clownfish, bioluminescent plankton trails, "
                "purple and orange soft corals, brain coral textures, "
                "rich underwater biodiversity"
            ),
            "imagen_modifier": (
                "Coral formations in center horizontal band, "
                "fish migration paths horizontal, "
                "deeper blue water fills upper and lower edges"
            ),
            "gemini_modifier": (
                "Coral reef stretches continuously across all four zones, "
                "fish swimming between coral heads near plate positions, "
                "vibrant colors fill the entire template content area"
            ),
            "video_motion": (
                "Tropical fish swimming in schools from left to right, "
                "sea anemones gently swaying with current, "
                "bioluminescent trails fading in and out, "
                "soft coral polyps pulsing rhythmically"
            ),
            "color_palette": ["#FF6347", "#FF8C00", "#9370DB", "#00CED1", "#1E3A5F"],
            "mood": "vibrant, lively, diverse, colorful",
        },
        "soup": {
            "base": (
                "Deep ocean scene with ethereal jellyfish floating across the view, "
                "bioluminescent creatures creating blue and purple light trails, "
                "deep sea currents carrying luminescent particles, "
                "translucent jellyfish bells pulsing with inner light, "
                "mysterious deep-sea atmosphere"
            ),
            "imagen_modifier": (
                "Jellyfish distributed across center band, "
                "bioluminescent trails flow horizontally, "
                "deep dark blue fills the upper and lower regions"
            ),
            "gemini_modifier": (
                "Jellyfish positioned between plate areas across the template, "
                "bioluminescent light trails connect the four zones, "
                "deep dark background with ethereal glow"
            ),
            "video_motion": (
                "Jellyfish pulsing and drifting slowly with gentle current, "
                "bioluminescent particles streaming horizontally, "
                "deep sea creatures flickering with inner light, "
                "slow ethereal dreamlike movement"
            ),
            "color_palette": ["#4B0082", "#0000CD", "#00BFFF", "#FF00FF", "#0A0A2A"],
            "mood": "ethereal, mysterious, deep, bioluminescent",
        },
        "main": {
            "base": (
                "Majestic manta rays gliding across the view from above, "
                "whale song vibrations visualized as expanding concentric light rings, "
                "deep ocean blue with shafts of sunlight penetrating from above, "
                "smaller fish parting to make way for the mantas, "
                "awe-inspiring scale and grace"
            ),
            "imagen_modifier": (
                "Manta rays positioned in center band gliding horizontally, "
                "light rings expand from center outward, "
                "deep blue gradient fills all areas"
            ),
            "gemini_modifier": (
                "Manta rays gliding across the panorama spanning zones 1 to 4, "
                "light rings centered in the template, "
                "grand scale ocean scene with depth"
            ),
            "video_motion": (
                "Manta rays gliding gracefully from right to left, "
                "concentric light rings expanding slowly from center, "
                "sunlight shafts slowly shifting angle, "
                "schools of fish parting dynamically, "
                "majestic slow-motion underwater ballet"
            ),
            "color_palette": ["#000080", "#1E90FF", "#87CEEB", "#FFFFFF", "#0A1628"],
            "mood": "majestic, awe-inspiring, grand, graceful",
        },
        "dessert": {
            "base": (
                "Ocean surface at golden sunset with dolphins leaping in silhouette, "
                "water surface transforming into sparkling champagne bubbles, "
                "golden and coral sunset reflections on gentle waves, "
                "joyful celebration with marine life, "
                "magical transition from ocean to celebration"
            ),
            "imagen_modifier": (
                "Sunset horizon line in center, dolphins leaping in middle band, "
                "golden reflections spread horizontally, "
                "champagne bubbles rising from center"
            ),
            "gemini_modifier": (
                "Sunset glow fills the entire template, "
                "dolphins leaping at intervals across the four zones, "
                "bubbles and sparkles create festive atmosphere"
            ),
            "video_motion": (
                "Dolphins leaping in sequence from left to right, "
                "champagne bubbles effervescing upward, "
                "golden sunset light rippling on water surface, "
                "joyful energetic celebration motion"
            ),
            "color_palette": ["#FFD700", "#FF6347", "#FF8C00", "#FFF8DC", "#FF1493"],
            "mood": "joyful, celebratory, golden, festive",
        },
    },

    # =========================================================================
    # FOREST (森)
    # =========================================================================
    "forest": {
        "welcome": {
            "base": (
                "Morning mist drifting through an ancient forest canopy viewed from above, "
                "golden sunbeams filtering through dense green leaves, "
                "moss-covered stones and fallen logs on forest floor, "
                "morning dewdrops glistening on spider webs, "
                "ferns unfurling in dappled light"
            ),
            "imagen_modifier": (
                "Forest floor textures in center band, sunbeams as vertical shafts, "
                "dense canopy creates uniform dark green at top and bottom, "
                "mist concentrated in center horizontal area"
            ),
            "gemini_modifier": (
                "Forest floor scene fills the template content area, "
                "sunbeam shafts fall between plate positions, "
                "moss and fern textures create a continuous panorama"
            ),
            "video_motion": (
                "Morning mist slowly drifting from left to right, "
                "sunbeams gradually intensifying, "
                "dewdrops catching light with subtle sparkle, "
                "gentle ambient forest awakening motion"
            ),
            "color_palette": ["#228B22", "#90EE90", "#FFD700", "#8B4513", "#F0FFF0"],
            "mood": "peaceful, misty, morning, enchanted",
        },
        "appetizer": {
            "base": (
                "Enchanted forest floor with mushrooms growing in clusters, "
                "ferns and wildflowers in a carpet of green, "
                "small forest creatures (squirrels, rabbits, hedgehogs) peeking from foliage, "
                "dappled sunlight through canopy, "
                "fairy-tale forest floor ecosystem"
            ),
            "imagen_modifier": (
                "Mushroom clusters and wildlife in center band, "
                "green carpet extends uniformly to edges, "
                "dappled light spots scattered in middle area"
            ),
            "gemini_modifier": (
                "Mushroom clusters positioned near plate areas, "
                "forest creatures placed between zones, "
                "continuous green carpet across the panorama"
            ),
            "video_motion": (
                "Mushrooms slowly growing in time-lapse, "
                "ferns gently unfurling, "
                "small creatures poking heads out and retreating, "
                "dappled sunlight slowly shifting, "
                "gentle nature time-lapse motion"
            ),
            "color_palette": ["#8B4513", "#90EE90", "#FFD700", "#FF6347", "#F5F5DC"],
            "mood": "whimsical, enchanted, lively, natural",
        },
        "soup": {
            "base": (
                "Gentle rain falling on broad tropical leaves viewed from above, "
                "ripples expanding in forest puddles and pools, "
                "foggy green atmosphere with muted colors, "
                "rain droplets forming patterns on leaf surfaces, "
                "meditative rainy forest calm"
            ),
            "imagen_modifier": (
                "Rain puddles and leaves in center band, "
                "uniform dark green canopy in upper/lower regions, "
                "fog diffuses all edges"
            ),
            "gemini_modifier": (
                "Rain puddles positioned across the template zones, "
                "broad leaves create continuous texture, "
                "foggy atmosphere softens the entire scene"
            ),
            "video_motion": (
                "Rain droplets falling and creating ripples in puddles, "
                "leaves swaying under rain impact, "
                "fog slowly rolling through the scene, "
                "meditative continuous rain pattern"
            ),
            "color_palette": ["#2E8B57", "#708090", "#A9A9A9", "#556B2F", "#D3D3D3"],
            "mood": "meditative, rainy, calm, atmospheric",
        },
        "main": {
            "base": (
                "Thousands of fireflies emerging at twilight in an ancient forest, "
                "row of massive gnarled trees stretching across the panorama, "
                "firefly bioluminescence creating trails of golden-green light, "
                "magical Ghibli-inspired forest at dusk, "
                "enchanted atmosphere with warm and cool tones"
            ),
            "imagen_modifier": (
                "Tree trunks as vertical elements in center band, "
                "fireflies concentrated in middle area between trees, "
                "dark twilight sky at top, dark forest floor at bottom"
            ),
            "gemini_modifier": (
                "Ancient trees positioned to frame each zone, "
                "firefly clouds filling the spaces between trees, "
                "magical twilight glow across the entire template"
            ),
            "video_motion": (
                "Fireflies blinking on and off in random patterns, "
                "drifting slowly in warm air currents, "
                "light trails forming and fading, "
                "magical pulsing rhythm of bioluminescence, "
                "enchanted twilight atmosphere building"
            ),
            "color_palette": ["#ADFF2F", "#FFD700", "#2F4F4F", "#8B4513", "#191970"],
            "mood": "magical, enchanted, twilight, Ghibli-inspired",
        },
        "dessert": {
            "base": (
                "Aurora borealis rippling above a forest canopy seen from above, "
                "flowers blooming in time-lapse across the forest floor, "
                "magical nature celebration with bioluminescent plants, "
                "curtains of green and purple light reflecting on forest pools, "
                "peak enchantment moment"
            ),
            "imagen_modifier": (
                "Aurora patterns in upper half, blooming flowers in center and lower areas, "
                "reflections connecting upper and lower regions, "
                "magical light suffusing the entire scene"
            ),
            "gemini_modifier": (
                "Aurora light fills the upper portion of the template, "
                "flowers bloom across all four zones, "
                "magical luminous celebration across the panorama"
            ),
            "video_motion": (
                "Aurora curtains rippling and shifting colors slowly, "
                "flowers opening in accelerated time-lapse, "
                "bioluminescent plants pulsing in harmony, "
                "magical particles rising from blooming flowers, "
                "climactic nature celebration"
            ),
            "color_palette": ["#00FF7F", "#9370DB", "#FF69B4", "#00CED1", "#1C1C3C"],
            "mood": "magical, celebratory, luminous, enchanted",
        },
    },

    # =========================================================================
    # GOLD (黄金)
    # =========================================================================
    "gold": {
        "welcome": {
            "base": (
                "Liquid gold flowing and forming elegant Art Deco geometric patterns, "
                "diamond dust particles floating in warm golden light, "
                "polished black marble surface with gold inlay, "
                "opulent luxury atmosphere, "
                "Gatsby-era glamour with modern sophistication"
            ),
            "imagen_modifier": (
                "Gold patterns flowing horizontally through center band, "
                "black marble extends to top and bottom, "
                "diamond particles concentrated in middle area"
            ),
            "gemini_modifier": (
                "Art Deco gold patterns flow across all four template zones, "
                "black marble background fills inactive areas, "
                "luxury atmosphere respecting plate positions"
            ),
            "video_motion": (
                "Liquid gold slowly flowing and forming geometric patterns, "
                "diamond dust particles drifting with gentle sparkle, "
                "Art Deco lines drawing themselves, "
                "opulent slow-motion metallic flow"
            ),
            "color_palette": ["#FFD700", "#DAA520", "#000000", "#C0C0C0", "#FFFFF0"],
            "mood": "opulent, luxurious, glamorous, sophisticated",
        },
        "appetizer": {
            "base": (
                "Champagne bubbles rising in warm golden light across the view, "
                "crystal glass reflections creating rainbow prism effects, "
                "Art Deco geometric patterns forming from bubble trails, "
                "sophisticated celebration atmosphere, "
                "golden amber tones with crystal clarity"
            ),
            "imagen_modifier": (
                "Bubbles rising vertically but distributed horizontally across center, "
                "crystal reflections in middle band, "
                "dark background at top and bottom"
            ),
            "gemini_modifier": (
                "Champagne bubbles distributed across all template zones, "
                "crystal reflections creating highlights near plate positions, "
                "elegant geometry connecting the zones"
            ),
            "video_motion": (
                "Champagne bubbles rising steadily with effervescent motion, "
                "crystal reflections slowly rotating and casting rainbow light, "
                "Art Deco patterns slowly materializing, "
                "elegant upward floating movement"
            ),
            "color_palette": ["#FFD700", "#FAEBD7", "#F0E68C", "#8B7355", "#2C2C2C"],
            "mood": "sophisticated, effervescent, elegant, celebratory",
        },
        "soup": {
            "base": (
                "Treasure cascading across a dark velvet surface, "
                "golden light spreading from ornate chalice at center, "
                "jewels (rubies, emeralds, sapphires) scattered among gold coins, "
                "rich warm tones with deep shadows, "
                "treasure discovery atmosphere"
            ),
            "imagen_modifier": (
                "Treasure spread horizontally across center band, "
                "golden light radiates from center, "
                "dark velvet fills upper and lower regions"
            ),
            "gemini_modifier": (
                "Treasure elements distributed across the template zones, "
                "golden light illuminates the center content area, "
                "dark background creates dramatic contrast"
            ),
            "video_motion": (
                "Golden light slowly expanding from center, "
                "jewels catching light with twinkling reflections, "
                "coins gently settling with metallic glints, "
                "warm pulsing treasure glow"
            ),
            "color_palette": ["#FFD700", "#DC143C", "#228B22", "#4169E1", "#1A1A1A"],
            "mood": "rich, warm, treasure, discovery",
        },
        "main": {
            "base": (
                "Grand chandelier crystals refracting rainbow light from above, "
                "Art Deco ballroom ceiling with intricate gold filigree patterns, "
                "crystal prisms casting spectacular light beams across the surface, "
                "Gatsby-era peak luxury, "
                "maximum opulence and grandeur"
            ),
            "imagen_modifier": (
                "Chandelier crystals and light beams in center band, "
                "gold filigree patterns extend horizontally, "
                "dark ceiling areas at top and bottom"
            ),
            "gemini_modifier": (
                "Crystal light refractions span across all four template zones, "
                "gold filigree creates a continuous decorative border, "
                "spectacular light show filling the content area"
            ),
            "video_motion": (
                "Chandelier crystals slowly rotating and casting shifting rainbow beams, "
                "light patterns sweeping across the surface from left to right, "
                "gold filigree patterns glinting, "
                "spectacular revolving light show"
            ),
            "color_palette": ["#FFD700", "#FFFFFF", "#FF69B4", "#87CEEB", "#2C1A00"],
            "mood": "spectacular, grand, opulent, dazzling",
        },
        "dessert": {
            "base": (
                "Gold leaf confetti and diamond sparkles raining down, "
                "champagne toast fireworks erupting in golden bursts, "
                "peak luxury celebration with metallic confetti streamers, "
                "Art Deco grand finale with maximum sparkle, "
                "ultimate golden celebration moment"
            ),
            "imagen_modifier": (
                "Gold confetti falling through center band, "
                "firework bursts distributed horizontally, "
                "sparkle effects concentrated in middle area"
            ),
            "gemini_modifier": (
                "Gold confetti and fireworks fill the entire template, "
                "celebration effects distributed across all zones, "
                "maximum sparkle and festive energy"
            ),
            "video_motion": (
                "Gold leaf confetti cascading downward, "
                "fireworks bursting in golden explosions, "
                "diamond sparkles twinkling rapidly, "
                "champagne bubbles rising amid celebration, "
                "maximum festive energy finale"
            ),
            "color_palette": ["#FFD700", "#FFFFFF", "#FF4500", "#FF69B4", "#C0C0C0"],
            "mood": "ultimate celebration, peak luxury, festive, grand finale",
        },
    },

    # =========================================================================
    # SPACE (宇宙)
    # =========================================================================
    "space": {
        "welcome": {
            "base": (
                "Slow drift through a vibrant nebula cloud in deep space, "
                "stars appearing as bright points across the cosmic dust, "
                "swirling gas clouds in purple, blue, and pink, "
                "cosmic dust particles illuminated by distant starlight, "
                "awe-inspiring deep space vista"
            ),
            "imagen_modifier": (
                "Nebula clouds concentrated in center band, "
                "star field extends to all edges but denser in center, "
                "darkest space regions at top and bottom"
            ),
            "gemini_modifier": (
                "Nebula clouds flow across all four template zones, "
                "star field creates continuous cosmic panorama, "
                "deep space darkness frames the content area"
            ),
            "video_motion": (
                "Slow forward drift through nebula clouds, "
                "stars slowly passing by with parallax depth, "
                "cosmic dust particles floating gently, "
                "nebula gas swirling in slow motion, "
                "awe-inspiring cosmic drift"
            ),
            "color_palette": ["#4B0082", "#191970", "#FF69B4", "#87CEEB", "#0A0A1A"],
            "mood": "awe-inspiring, cosmic, vast, mysterious",
        },
        "appetizer": {
            "base": (
                "Planetary ring system viewed from above stretching across the view, "
                "asteroid field with crystalline mineral formations reflecting starlight, "
                "deep purple and blue cosmic background, "
                "ice crystals and metallic asteroids, "
                "alien geological wonder"
            ),
            "imagen_modifier": (
                "Planetary rings as horizontal bands through center, "
                "asteroids scattered in middle area, "
                "deep space fills upper and lower regions"
            ),
            "gemini_modifier": (
                "Ring system stretches across all template zones as a horizontal feature, "
                "asteroids positioned between plate markers, "
                "cosmic background fills the template area"
            ),
            "video_motion": (
                "Planetary rings slowly rotating, "
                "asteroids gently tumbling with crystalline reflections, "
                "ice crystals catching starlight, "
                "slow orbital motion with depth parallax"
            ),
            "color_palette": ["#4B0082", "#0000CD", "#C0C0C0", "#87CEEB", "#0A0A1A"],
            "mood": "alien, crystalline, vast, wondrous",
        },
        "soup": {
            "base": (
                "Aurora borealis rippling across the cosmic void, "
                "northern lights in ethereal greens and purples with pink edges, "
                "cosmic energy waves pulsing rhythmically, "
                "star field visible through translucent aurora curtains, "
                "mesmerizing celestial light show"
            ),
            "imagen_modifier": (
                "Aurora curtains as horizontal waves in center band, "
                "star field visible through and around aurora, "
                "darkest space at top and bottom edges"
            ),
            "gemini_modifier": (
                "Aurora curtains ripple across all four template zones, "
                "green and purple light fills the content area, "
                "star field provides depth behind the aurora"
            ),
            "video_motion": (
                "Aurora curtains rippling and flowing from left to right, "
                "colors shifting between green, purple, and pink, "
                "cosmic energy waves pulsing, "
                "mesmerizing slow-motion celestial dance"
            ),
            "color_palette": ["#00FF7F", "#9370DB", "#FF69B4", "#00CED1", "#0A0A2A"],
            "mood": "mesmerizing, ethereal, celestial, hypnotic",
        },
        "main": {
            "base": (
                "Supernova explosion expanding in slow motion from center, "
                "spiral galaxy arms forming from the stellar debris, "
                "shock waves rippling outward with rainbow-spectrum light, "
                "cosmic scale spectacle of stellar birth and death, "
                "ultimate astronomical event"
            ),
            "imagen_modifier": (
                "Supernova burst centered, shock waves expanding horizontally, "
                "galaxy arm formation in center band, "
                "deep space fills upper and lower edges"
            ),
            "gemini_modifier": (
                "Supernova centered in the template, "
                "shock waves reaching zones 1 and 4 at the edges, "
                "galaxy formation visible across the full panorama"
            ),
            "video_motion": (
                "Supernova explosion expanding outward in slow motion, "
                "spiral galaxy arms slowly forming and rotating, "
                "shock waves rippling concentrically, "
                "cosmic debris scattering, "
                "epic slow-motion stellar event"
            ),
            "color_palette": ["#FF4500", "#FFD700", "#FFFFFF", "#4B0082", "#0A0A1A"],
            "mood": "epic, cosmic, spectacular, awe-inspiring",
        },
        "dessert": {
            "base": (
                "Shooting stars streaking across the cosmic panorama, "
                "constellation patterns forming celebration shapes (champagne glass, stars), "
                "cosmic fireworks in every color of the spectrum, "
                "nebula clouds parting to reveal a brilliant star cluster, "
                "grand cosmic finale celebration"
            ),
            "imagen_modifier": (
                "Shooting stars as horizontal streaks in center band, "
                "constellation patterns in middle area, "
                "cosmic fireworks distributed across width"
            ),
            "gemini_modifier": (
                "Shooting stars streak across all four template zones, "
                "constellation formations distributed evenly, "
                "cosmic fireworks create festive atmosphere across the panorama"
            ),
            "video_motion": (
                "Shooting stars streaking rapidly from right to left, "
                "constellations lighting up in sequence, "
                "cosmic firework bursts in multiple colors, "
                "nebula parting dramatically, "
                "grand cosmic celebration finale"
            ),
            "color_palette": ["#FFFFFF", "#FFD700", "#FF69B4", "#00BFFF", "#0A0A2A"],
            "mood": "grand finale, celebratory, cosmic, spectacular",
        },
    },

    # =========================================================================
    # FAIRYTALE (おとぎ話)
    # =========================================================================
    "fairytale": {
        "welcome": {
            "base": (
                "Giant storybook pages opening and unfolding across the surface, "
                "illustrated castle with towers and flags appearing from the pages, "
                "fairy dust sparkles and golden particle trails, "
                "watercolor illustration style with warm storybook palette, "
                "whimsical and magical opening chapter"
            ),
            "imagen_modifier": (
                "Book pages and castle in center band, "
                "fairy dust trails horizontal, "
                "parchment/cream background extends to edges"
            ),
            "gemini_modifier": (
                "Storybook pages unfold across the template zones, "
                "castle illustration centered, fairy dust connecting the zones, "
                "warm parchment background fills inactive areas"
            ),
            "video_motion": (
                "Book pages slowly turning and unfolding from left to right, "
                "castle illustration drawing itself into existence, "
                "fairy dust particles twinkling and drifting, "
                "magical storybook opening animation"
            ),
            "color_palette": ["#FFD700", "#FF69B4", "#87CEEB", "#F5DEB3", "#8B4513"],
            "mood": "whimsical, magical, storybook, inviting",
        },
        "appetizer": {
            "base": (
                "Enchanted garden stretching across the view from above, "
                "oversized talking flowers with expressive petals, "
                "butterflies carrying tiny lanterns creating light trails, "
                "toadstools and fairy rings, cobblestone garden paths, "
                "storybook illustration style with rich colors"
            ),
            "imagen_modifier": (
                "Garden elements in center band, flower faces at center height, "
                "butterfly trails flow horizontally, "
                "green garden ground fills top and bottom"
            ),
            "gemini_modifier": (
                "Enchanted garden fills all four template zones, "
                "butterflies with lanterns fly between zones, "
                "flower characters positioned near plate markers"
            ),
            "video_motion": (
                "Flowers gently swaying and turning their faces, "
                "butterflies with lanterns flying in graceful paths left to right, "
                "fairy ring mushrooms slowly pulsing with inner glow, "
                "gentle enchanted garden life"
            ),
            "color_palette": ["#FF69B4", "#FFD700", "#90EE90", "#9370DB", "#FF6347"],
            "mood": "enchanted, playful, colorful, whimsical",
        },
        "soup": {
            "base": (
                "Wizard's workshop viewed from above with magical potion brewing, "
                "swirling colored liquids in crystal vials and cauldron, "
                "spell book with glowing runes, floating magical ingredients, "
                "purple and gold magical energy, cozy candlelit atmosphere, "
                "mysterious yet inviting sorcery scene"
            ),
            "imagen_modifier": (
                "Potion apparatus and books in center band, "
                "swirling colors concentrated in middle area, "
                "dark wooden workshop surface at edges"
            ),
            "gemini_modifier": (
                "Workshop items distributed across the template zones, "
                "magical energy trails connect elements horizontally, "
                "cozy dark background with warm candlelight"
            ),
            "video_motion": (
                "Potion liquids swirling in cauldron with color changes, "
                "magical sparkles rising from spell book, "
                "floating ingredients slowly orbiting, "
                "candle flames gently flickering, "
                "cozy magical workshop ambiance"
            ),
            "color_palette": ["#9370DB", "#FFD700", "#8B4513", "#FF4500", "#2C1A3C"],
            "mood": "mysterious, cozy, magical, enchanting",
        },
        "main": {
            "base": (
                "Friendly dragon flying across a fantasy sky viewed from above, "
                "dragon casting a dramatic shadow on clouds below, "
                "then revealing a playful smile and colorful scales, "
                "magical adventure landscape with floating islands, "
                "epic yet playful fantasy panorama"
            ),
            "imagen_modifier": (
                "Dragon flying horizontally through center band, "
                "cloud floor in lower portion, floating islands scattered, "
                "bright sky fills upper region"
            ),
            "gemini_modifier": (
                "Dragon spans zones 2 and 3 of the template, "
                "floating islands in zones 1 and 4, "
                "cloud floor and adventure sky fill the panorama"
            ),
            "video_motion": (
                "Dragon flying from left to right with wing flaps, "
                "clouds slowly drifting below, "
                "floating islands gently bobbing, "
                "dragon shadow moving across the cloud floor, "
                "epic adventure flight motion"
            ),
            "color_palette": ["#228B22", "#FFD700", "#FF6347", "#87CEEB", "#9370DB"],
            "mood": "epic, playful, adventurous, fantastical",
        },
        "dessert": {
            "base": (
                "Fairy tale castle at night with fireworks lighting up the sky, "
                "magical creatures (fairies, unicorns, pixies) celebrating, "
                "rainbow bridges and sparkling towers, "
                "happy ever after scene with maximum enchantment, "
                "grand storybook finale celebration"
            ),
            "imagen_modifier": (
                "Castle and fireworks in center band, "
                "magical creatures distributed horizontally, "
                "night sky with stars at top, enchanted ground at bottom"
            ),
            "gemini_modifier": (
                "Castle centered in the template, fireworks in all four zones, "
                "magical creatures celebrating near plate positions, "
                "maximum festive enchantment across the panorama"
            ),
            "video_motion": (
                "Fireworks launching and bursting in colorful patterns, "
                "magical creatures dancing and flying, "
                "castle towers sparkling with enchanted light, "
                "rainbow bridges glowing, "
                "joyful fairy tale grand finale"
            ),
            "color_palette": ["#FFD700", "#FF69B4", "#9370DB", "#00CED1", "#191970"],
            "mood": "joyful, magical, celebratory, happy ending",
        },
    },
}


# =========================================================================
# ヘルパー関数
# =========================================================================

COURSE_ORDER = ["welcome", "appetizer", "soup", "main", "dessert"]
THEME_LIST = list(PROMPT_TEMPLATES.keys())


def get_template(theme: str, course: str) -> dict[str, str | list[str]]:
    """指定テーマ・コースのプロンプトテンプレートを取得する。

    Args:
        theme: テーマ名 (例: "ocean", "zen")
        course: コース名 (例: "welcome", "main")

    Returns:
        テンプレート辞書

    Raises:
        KeyError: テーマまたはコースが存在しない場合
    """
    if theme not in PROMPT_TEMPLATES:
        raise KeyError(f"Unknown theme: {theme}. Available: {THEME_LIST}")
    if course not in PROMPT_TEMPLATES[theme]:
        raise KeyError(f"Unknown course: {course}. Available: {COURSE_ORDER}")
    return PROMPT_TEMPLATES[theme][course]


def get_prompt(
    theme: str,
    course: str,
    provider: str = "gemini",
    extra_hint: Optional[str] = None,
) -> str:
    """画像生成用の最終プロンプトを構築する。

    Args:
        theme: テーマ名
        course: コース名
        provider: プロバイダー ("gemini", "imagen", "runway")
        extra_hint: 追加のヒント文（料理名など）

    Returns:
        最適化された英語プロンプト文字列
    """
    tmpl = get_template(theme, course)
    base = tmpl["base"]

    if provider == "imagen":
        prompt = f"{base}. {tmpl['imagen_modifier']}"
    elif provider in ("gemini", "gemini_pro"):
        prompt = f"{base}. {tmpl['gemini_modifier']}"
    else:
        prompt = base

    if extra_hint:
        prompt += f", inspired by the dish: {extra_hint}"

    return prompt


def get_video_motion(theme: str, course: str) -> str:
    """動画生成用のモーション指示プロンプトを取得する。

    Args:
        theme: テーマ名
        course: コース名

    Returns:
        モーション指示の英語プロンプト
    """
    tmpl = get_template(theme, course)
    return tmpl["video_motion"]


def get_color_palette(theme: str, course: str) -> list[str]:
    """指定テーマ・コースの推奨カラーパレットを取得する。

    Args:
        theme: テーマ名
        course: コース名

    Returns:
        HEXカラーコードのリスト
    """
    tmpl = get_template(theme, course)
    return tmpl["color_palette"]


def get_mood(theme: str, course: str) -> str:
    """指定テーマ・コースの雰囲気キーワードを取得する。

    Args:
        theme: テーマ名
        course: コース名

    Returns:
        カンマ区切りの雰囲気キーワード
    """
    tmpl = get_template(theme, course)
    return tmpl["mood"]
