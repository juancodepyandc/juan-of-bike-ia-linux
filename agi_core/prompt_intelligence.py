"""AuroraIA AGI Cognitive Prompt & Ontology Director.

Ce module implémente l'intelligence sémantique et ontologique de compréhension
des demandes humaines courtes (en français ou multilingues) pour les moteurs
Image (FLUX.2-dev), 3D (TRELLIS.2-4B / Hunyuan3D / Blender), Vidéo (Wan2.2) et
Animation (UniRig / HY-Motion-1.0) :

1. Ontologie intrinsèque du sujet (`subject_ontology`) :
   - Détecte si le sujet demandé est par nature un personnage d'animé/manga/animation,
     un personnage/asset de jeu vidéo, une personne réelle / sujet photographique,
     une créature fantastique, ou une pièce mécanique / produit réel.
2. Règle de fidélité de style et d'override explicite (`effective_render_mode`) :
   - Si le sujet est intrinsèquement animé/stylisé : il est généré DIRECTEMENT dans
     son vrai style animé/cel-shadé natif (proportions fidèles, yeux expressifs,
     aplats/ombrages animés propres, ZÉRO pores de peau humaine photoréalistes),
     SAUF si l'utilisateur demande explicitement des textures de personne réelle /
     live-action / peau réaliste (`explicit_real_textures_override=True`).
   - Si le sujet est intrinsèquement réel (humain, portrait, objet physique, paysage) :
     il est généré DIRECTEMENT en photoréalisme physique natif (vraie micro-texture
     de peau, optique réelle, matériaux PBR), SAUF si l'utilisateur demande
     explicitement une stylisation (animé, manga, cartoon, pixel art).
3. Distinction Création vs Modification (`operation_mode`) :
   - En mode `modification` (ou `reproduction`), verrouille 100 % de l'identité,
     du style ontologique d'origine, de la pose et de la composition non mentionnés,
     et n'applique que le delta demandé sans jamais dénaturer le sujet.
4. Traduction & Expansion Anglaise Profonde (`english_expanded_prompt`) :
   - Un humain écrit souvent une idée courte en français (« fais-moi un perso animé
     mage de feu », « Goku avec des textures de personne réelle », « change sa veste
     en noir »). Le directeur traduit intégralement en anglais fluide et développe
     intelligemment le cahier des charges artistique et géométrique sans jargon
     robotique contradictoire.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.request
from typing import Any


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(ch) != "Mn"
    )


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents(text).lower()).strip()


# Signaux d'univers, d'archétypes et d'entités intrinsèquement Animé / Manga / Stylisé
ANIME_UNIVERSE_AND_CHARACTER_PATTERNS = re.compile(
    r"\b("
    r"anime|manga|manhwa|webtoon|shonen|shojo|seinen|isekai|chibi|cel[- ]?shad(?:ed|ing)|"
    r"ghibli|makoto\s*shinkai|ufotable|mappa|toei|kyoani|studio\s*trigger|pixar|disney|cartoon|dessin\s*anime|"
    r"natsu|lucy\s*heartfilia|erza|gray\s*fullbuster|happy\s*exceed|wendy\s*marvell|fairy\s*tail|"
    r"goku|son\s*goku|vegeta|gohan|trunks|piccolo|frieza|freezer|broly|bulma|shenron|saiyan|super\s*saiyan|dragon\s*ball|"
    r"luffy|monkey\s*d|zoro|roronoa|sanji|nami|robin|chopper|usopp|brook|franky|jinbe|shanks|ace|law|kaido|gear\s*5|one\s*piece|"
    r"naruto|sasuke|sakura|kakashi|itachi|madara|obito|hinata|gaara|jiraiya|minato|pain|akatsuki|sharingan|konoha|"
    r"ichigo|rukia|ai[z]en|byakuya|kenpachi|ulquiorra|bleach|bankai|shinigami|"
    r"tanjiro|nezuko|zenitsu|inosuke|rengoku|giyu|muzan|shinobu|mitsuri|tengen|hashira|demon\s*slayer|kimetsu|"
    r"gojo|satoru\s*gojo|sukuna|yuji\s*itadori|megumi|nobara|toji|geto|yuta|maki|jujutsu\s*kaisen|"
    r"eren|mikasa|levi|armin|reiner|titan|attaque\s*des\s*titans|attack\s*on\s*titan|shingeki|"
    r"saitama|genos|tatsumaki|garou|one\s*punch|"
    r"gon|killua|kirua|kurapika|hisoka|meruem|chrollo|hunter\s*x\s*hunter|"
    r"deku|midoriya|bakugo|todoroki|all\s*might|shigaraki|my\s*hero\s*academia|boku\s*no\s*hero|"
    r"asta|yuno|yami|noelle|black\s*clover|"
    r"denji|makima|power|aki|chainsaw\s*man|"
    r"frieren|fern|stark|himmel|"
    r"anya|yor\s*forger|loid\s*forger|spy\s*x\s*family|"
    r"sung\s*jin[- ]?woo|solo\s*leveling|igris|beru|"
    r"edward\s*elric|alphonse\s*elric|roy\s*mustang|fullmetal|"
    r"light\s*yagami|ryuk|l\s*lawliet|misa|death\s*note|"
    r"lelouch|code\s*geass|rem|emilia|subaru|re\s*zero|"
    r"kirito|asuna|sword\s*art\s*online|rimuru|tensura|ainz|overlord|"
    r"jotaro|dio\s*brando|giorno|josuke|jolyne|jojo|"
    r"pikachu|charizard|dracaufeu|mewtwo|lucario|eevee|ectoplasma|gengar|pokemon|"
    r"hatsune\s*miku|vocaloid|genshin|raiden\s*shogun|furina|nahida|zhongli|hu\s*tao|arlecc?hino|honkai|"
    r"link|zelda|ganondorf|hyrule|mario|luigi|peach|bowser|yoshi|sonic|tails|knuckles|shadow\s*the\s*hedgehog|"
    r"cloud\s*strife|tifa|sephiroth|aerith|final\s*fantasy|2b|nier\s*automata|jinx|vi\s*arcane|ekko|arcane"
    r")\b",
    re.IGNORECASE,
)

# Demande explicite de textures humaines réelles / live-action sur un sujet animé/stylisé
EXPLICIT_REAL_TEXTURES_OVERRIDE_RE = re.compile(
    r"\b("
    r"texture[s]?\s+(?:de\s+)?(?:personne|peau|humain[e]?|vrai[e]?)\s+r[eé]el(?:le)?s?|"
    r"texture[s]?\s+r[eé]aliste[s]?\s+(?:de\s+peau|humaine|personne)|"
    r"peau\s+(?:humaine\s+)?r[eé]elle|vrai[e]?\s+peau\s+humaine|"
    r"en\s+(?:vrai[e]?\s+)?(?:personne|humain)\s+r[eé]el(?:le)?|"
    r"version\s+(?:personne\s+)?r[eé]elle|rendu\s+personne\s+r[eé]elle|"
    r"live[- ]?action|cosplay\s+r[eé]aliste|photorealistic\s+human\s+skin|"
    r"real\s+human\s+(?:skin\s+)?textures?|realistic\s+skin\s+pores|"
    r"comme\s+une?\s+vrai[e]?\s+(?:personne|humain)|"
    r"avec\s+(?:des\s+)?textures?\s+(?:de\s+personne\s+)?r[eé]el(?:le)?s?"
    r")\b",
    re.IGNORECASE,
)

# Demande explicite de stylisation animé/cartoon/pixel sur un sujet réel
EXPLICIT_STYLIZED_OVERRIDE_RE = re.compile(
    r"\b("
    r"en\s+(?:style\s+|version\s+)?(?:anime|manga|cartoon|dessin\s+anime|ghibli|pixar|chibi|pixel\s*art|low[- ]?poly|bd|comics?)|"
    r"style\s+(?:anime|manga|cartoon|ghibli|pixar|chibi|pixel\s*art|cel[- ]?shading)|"
    r"transforme\s+en\s+(?:anime|manga|cartoon|dessin)|"
    r"version\s+(?:anime|manga|cartoon|stylis[eé]e?)"
    r")\b",
    re.IGNORECASE,
)

# Détection d'intention de modification / retouche
MODIFICATION_INTENT_RE = re.compile(
    r"(?:^|\b)("
    r"modifi(?:e|er|cation)|chang(?:e|er)|ajout(?:e|er)|rajout(?:e|er)|"
    r"enl[eè]v(?:e|er)|retir(?:e|er)|supprim(?:e|er)|remplac(?:e|er)|"
    r"met(?:s|tre)[- ]?(?:lui|le|la|les)?|transform(?:e|er)|corrige(?:r)?|"
    r"garde(?:r)?\s+(?:le\s+m[eê]me|la\s+m[eê]me|exactement)|"
    r"sans\s+changer|conserve(?:r)?|m[eê]me\s+(?:personnage|sujet|objet|pose)|"
    r"plus\s+(?:grand|petit|sombre|clair|large|fin)|"
    r"make\s+(?:him|her|it|the)|change\s+the|add\s+a|remove\s+the|replace\s+the|keep\s+the\s+same"
    r")\b",
    re.IGNORECASE,
)

# Détection d'intention de reproduction fidèle
REPRODUCTION_INTENT_RE = re.compile(
    r"\b("
    r"reprodui(?:s|re)|fais[- ]?moi\s+ce\s+(?:personnage|sujet|mod[eè]le)|"
    r"identique\s+[aà]|comme\s+sur\s+la\s+photo|exactement\s+ce\s+perso|"
    r"replicate|exact\s+copy\s+of"
    r")\b",
    re.IGNORECASE,
)

# Détection d'archétypes de personnages (humains ou stylisés)
CHARACTER_SUBJECT_RE = re.compile(
    r"\b("
    r"perso|personnage|character|hero[s]?|heroine|guerrier[e]?|warrior|mage|sorcier[e]?|"
    r"chevalier|knight|ninja|samourai|samurai|pirate|assassin|paladin|archer|voleur|"
    r"homme|femme|garcon|fille|enfant|vieillard|portrait|visage|humain[e]?|personne|"
    r"man|woman|boy|girl|human|person|portrait|face|avatar|figurine"
    r")\b",
    re.IGNORECASE,
)

MECHANICAL_CAD_RE = re.compile(
    r"\b("
    r"engrenage|gear|poulie|pulley|courroie|belt|verin|actuator|charniere|hinge|"
    r"bielle|linkage|roulement|bearing|vis|ecrou|bride|flange|support\s+mecanique|"
    r"boitier\s+pc|carte\s+mere|motherboard|strimer|cable|connecteur|gpu|rtx|ventirad|"
    r"stl|cao|cad|imprimable|printable|piece\s+mecanique"
    r")\b",
    re.IGNORECASE,
)

GAME_ASSET_RE = re.compile(
    r"\b("
    r"pixel\s*art|sprite|spritesheet|tileset|isometrique|isometric|low[- ]?poly|"
    r"icone\s+de\s+jeu|game\s+asset|game\s+prop|inventory\s+icon|pbr\s+texture|seamless\s+texture"
    r")\b",
    re.IGNORECASE,
)

# Dictionnaire sémantique FR -> EN enrichi pour traduction naturelle & précise hors-ligne / fallback
FR_TO_EN_PHRASES: list[tuple[str, str]] = [
    (r"\b(?:fais[- ]?moi|fait[- ]?moi|cree[- ]?moi|creer|genere[- ]?moi|generer|dessine[- ]?moi|je\s+veux|je\s+voudrais|peux[- ]?tu\s+faire)\b", ""),
    (r"\bavec\s+des\s+textures?\s+de\s+personne\s+r[eé]elle\b", "with photorealistic real human skin textures and natural pores"),
    (r"\btextures?\s+de\s+personne\s+r[eé]elle\b", "photorealistic real human skin textures and natural pores"),
    (r"\btextures?\s+r[eé]elles?\b", "authentic physical real-world textures"),
    (r"\bpersonne\s+r[eé]elle\b", "real living human person"),
    (r"\bun\s+perso\s+d[' ]?anim[eé]\b", "an authentic anime character"),
    (r"\bun\s+personnage\s+d[' ]?anim[eé]\b", "an authentic anime character"),
    (r"\bun\s+perso\s+anim[eé]\b", "an authentic anime character"),
    (r"\bun\s+personnage\s+anim[eé]\b", "an authentic anime character"),
    (r"\ben\s+anim[eé]\b", "in authentic anime style"),
    (r"\ben\s+manga\b", "in authentic manga style"),
    (r"\bun\s+perso\b", "a character"),
    (r"\bun\s+personnage\b", "a character"),
    (r"\bune\s+personne\b", "a real person"),
    (r"\bqui\s+marche\b", "walking in a natural balanced stride"),
    (r"\bqui\s+court\b", "running dynamically with athletic momentum"),
    (r"\bqui\s+danse\b", "performing an expressive dance pose"),
    (r"\bqui\s+saute\b", "leaping mid-air in a dynamic jump"),
    (r"\bqui\s+vole\b", "floating and flying gracefully mid-air"),
    (r"\bqui\s+se\s+bat\b", "in a dynamic martial combat stance"),
    (r"\bqui\s+lance\s+du\s+feu\b", "casting swirling incandescent flames from their hands"),
    (r"\ben\s+feu\b", "wreathed in dynamic glowing flames"),
    (r"\bde\s+feu\b", "of fire"),
    (r"\bde\s+glace\b", "of frost and crystalline ice"),
    (r"\bde\s+foudre\b", "of crackling lightning"),
    (r"\bd[' ]?ombre\b", "of shadow"),
    (r"\bchevalier\s+noir\b", "dark armored knight"),
    (r"\bchevalier\b", "armored knight"),
    (r"\bguerrier\b", "warrior"),
    (r"\bguerriere\b", "female warrior"),
    (r"\bmage\b", "arcane mage"),
    (r"\bsorcier\b", "sorcerer"),
    (r"\bsorciere\b", "sorceress"),
    (r"\bsamourai\b", "samurai"),
    (r"\bchapeau\s+de\s+paille\b", "iconic straw hat"),
    (r"\bcheveux\s+roses?\b", "spiky salmon-pink hair"),
    (r"\bcheveux\s+blonds?\b", "golden blonde hair"),
    (r"\bcheveux\s+noirs?\b", "jet-black hair"),
    (r"\bcheveux\s+blancs?\b", "silver-white hair"),
    (r"\bcheveux\s+rouges?\b", "crimson red hair"),
    (r"\bcheveux\s+bleus?\b", "cobalt blue hair"),
    (r"\byeux\s+bleus?\b", "vivid blue eyes"),
    (r"\byeux\s+verts?\b", "emerald green eyes"),
    (r"\byeux\s+rouges?\b", "glowing crimson eyes"),
    (r"\bveste\s+noire?\b", "tailored black jacket"),
    (r"\bveste\s+rouge\b", "crimson jacket"),
    (r"\bmanteau\s+long\b", "long flowing coat"),
    (r"\barmure\s+complete\b", "full articulated plate armor"),
    (r"\barmure\b", "ornate armor"),
    (r"\bepee\b", "sword"),
    (r"\bkatana\b", "forged katana blade"),
    (r"\bbaton\s+magique\b", "arcane staff"),
    (r"\bdans\s+une\s+foret\b", "in an atmospheric ancient forest"),
    (r"\bsur\s+une\s+falaise\b", "standing on a dramatic rocky cliffside"),
    (r"\bdans\s+une\s+ville\b", "in a detailed urban street environment"),
    (r"\bde\s+nuit\b", "at night under dramatic moonlight"),
    (r"\bau\s+coucher\s+du\s+soleil\b", "at golden hour sunset"),
    (r"\bportrait\s+d[' ]?un[e]?\b", "portrait of a"),
    (r"\bdans\s+son\s+atelier\b", "in his traditional workshop"),
    (r"\bsans\s+changer\s+le\s+reste\b", "without altering any other aspect of the subject or scene"),
    (r"\bmodifie\s+la\s+couleur\b", "modify the color"),
    (r"\bchange\s+la\s+couleur\b", "change the color"),
    (r"\bbleu\s+nuit\b", "midnight blue"),
    (r"\bvieil(?:le)?\b|\bvieux\b", "elderly"),
    (r"\bhorloger\b", "master watchmaker"),
    (r"\bsuisse\b", "Swiss"),
    (r"\batelier\b", "artisan workshop"),
    (r"\bchange\s+sa\b", "change their"),
    (r"\bchange\s+son\b", "change their"),
    (r"\bajoute\s+un[e]?\b", "add a"),
    (r"\benleve\s+le\b", "remove the"),
    (r"\benleve\s+la\b", "remove the"),
    (r"\bgarde\s+le\s+meme\b", "preserve the exact same"),
]

FR_STOPWORD_CLEANUP: list[tuple[str, str]] = [
    (r"\bde\s+sa\b|\bde\s+son\b", "of their"),
    (r"\bsa\b|\bson\b", "their"),
    (r"\bd[' ]?un[e]?\b", "of a"),
    (r"\bavec\b", "with"),
    (r"\bsans\b", "without"),
    (r"\bdans\b", "in"),
    (r"\bsur\b", "on"),
    (r"\bsous\b", "under"),
    (r"\bdevant\b", "in front of"),
    (r"\bderriere\b", "behind"),
    (r"\bentre\b", "between"),
    (r"\bpour\b", "for"),
    (r"\bmais\b", "but"),
    (r"\bet\b", "and"),
    (r"\bou\b", "or"),
    (r"\ben\b", "into"),
    (r"\btr[eè]s\b", "very"),
    (r"\bplus\b", "more"),
    (r"\bmoins\b", "less"),
    (r"\bgrand[e]?\b", "tall"),
    (r"\bpetit[e]?\b", "small"),
    (r"\bbeau\b|\bbelle\b", "striking"),
    (r"\bsombre\b", "dark"),
    (r"\blumineux\b|\blumineuse\b", "luminous"),
    (r"\br[eé]aliste\b", "photorealistic"),
    (r"\brouge[s]?\b", "crimson red"),
    (r"\bbleu[e]?s?\b", "deep blue"),
    (r"\bvert[e]?s?\b", "emerald green"),
    (r"\bnoir[e]?s?\b", "obsidian black"),
    (r"\bblanc(?:he)?s?\b", "pure white"),
    (r"\bdor[eé][e]?s?\b", "burnished gold"),
    (r"\bargent[eé][e]?s?\b", "polished silver"),
    (r"\bviolet(?:te)?s?\b", "royal violet"),
    (r"\bhomme\b", "man"),
    (r"\bfemme\b", "woman"),
    (r"\bgarcon\b", "young man"),
    (r"\bfille\b", "young woman"),
    (r"\bvisage\b", "face"),
    (r"\bregard\b", "gaze"),
    (r"\bsourire\b", "confident smile"),
    (r"\bmain[s]?\b", "hands"),
    (r"\bbras\b", "arms"),
    (r"\bjambes?\b", "legs"),
    (r"\bcheveux\b", "hair"),
    (r"\byeux\b", "eyes"),
    (r"\bpeau\b", "skin"),
    (r"\btenue\b|\bvetements?\b|\bhabits?\b", "outfit"),
    (r"\bveste\b", "jacket"),
    (r"\bmanteau\b", "coat"),
    (r"\bpantalon\b", "trousers"),
    (r"\bchaussures?\b", "footwear"),
    (r"\bchapeau\b", "hat"),
    (r"\blunettes?\b", "glasses"),
    (r"\bmontre\b", "mechanical watch"),
    (r"\bvoiture\b", "car"),
    (r"\bmoto\b", "motorcycle"),
    (r"\bvelo\b", "bicycle"),
    (r"\bmaison\b", "house"),
    (r"\bchateau\b", "castle"),
    (r"\bpaysage\b", "landscape"),
    (r"\bmontagne[s]?\b", "mountains"),
    (r"\bmer\b|\bocean\b", "ocean"),
    (r"\bplage\b", "coastal beach"),
    (r"\bforet\b", "forest"),
    (r"\bchat\b", "cat"),
    (r"\bchien\b", "dog"),
    (r"\bloup\b", "wolf"),
    (r"\bdragon\b", "dragon"),
    (r"\boiseau\b", "bird"),
]


# Connaissances visuelles canoniques pour les personnages/univers connus afin que même un prompt
# ultra-court ("Natsu", "Goku", "Luffy") soit développé avec ses vrais attributs visuels en anglais
CANONICAL_CHARACTER_LORE: dict[str, str] = {
    "natsu": "Natsu Dragneel from Fairy Tail, athletic young anime fire mage with spiky salmon-pink hair, sharp dark eyes, iconic white-and-black checkered scale scarf around his neck, open black sleeveless waistcoat with gold trim over bare muscular chest, white knee-length trousers, black open-toed sandals, red Fairy Tail guild mark on his right shoulder",
    "lucy": "Lucy Heartfilia from Fairy Tail, expressive anime celestial spirit mage with golden blonde hair tied in side tails, warm brown eyes, iconic blue-and-white fitted top, pleated skirt, leather belt with golden Celestial Spirit keys and whip",
    "goku": "Son Goku from Dragon Ball, muscular anime martial artist with iconic wild spiky jet-black hair, determined dark eyes, signature bright orange martial arts gi over a royal blue undershirt, blue wristbands, blue sash belt, and martial arts boots",
    "vegeta": "Vegeta from Dragon Ball, proud Saiyan prince with tall flame-shaped spiky black hair, sharp widow's peak, intense frowned gaze, royal blue bodysuit under white-and-gold Saiyan battle armor with shoulder pauldrons, white gloves and boots",
    "luffy": "Monkey D. Luffy from One Piece, energetic anime pirate captain wearing his signature woven straw hat with a red ribbon, tousled black hair, small scar under his left eye, open red vest, blue denim shorts, yellow sash, and sandals",
    "zoro": "Roronoa Zoro from One Piece, muscular anime swordsman with cropped green hair, three gold earrings on his left ear, scar over his left eye, dark green coat, crimson haramaki sash holding three katana swords at his waist",
    "naruto": "Naruto Uzumaki from Naruto, spirited anime ninja with spiky bright yellow-blond hair, cobalt blue eyes, three whisker marks on each cheek, Konoha metal headband, orange-and-black zip-up ninja jumpsuit, and ninja sandals",
    "sasuke": "Sasuke Uchiha from Naruto, composed anime ninja with spiky black hair framing his face, dark Sharingan eyes, high-collared Uchiha outfit with rope belt and Kusanagi sword",
    "gojo": "Satoru Gojo from Jujutsu Kaisen, tall slender anime sorcerer with snow-white spiky hair, luminous sky-blue Six Eyes (or signature black blindfold), dark high-necked Jujutsu High uniform jacket",
    "tanjiro": "Tanjiro Kamado from Demon Slayer, kind-hearted anime swordsman with burgundy-tipped ruffled black hair, dark red eyes, flame-like scar on his forehead, hanafuda earrings, green-and-black checkered haori coat over a dark Demon Slayer corps uniform, carrying a black Nichirin katana",
    "nezuko": "Nezuko Kamado from Demon Slayer, anime girl with long black hair fading to flame-orange at the tips, soft pink eyes, bamboo muzzle tied with a red ribbon, pink geometric-patterned kimono with red-and-white checkered obi",
    "ichigo": "Ichigo Kurosaki from Bleach, tall anime Soul Reaper with spiky bright orange hair, brown eyes, black shihakusho kimono robe with white sash and oversized Zangetsu cleaver sword",
    "saitama": "Saitama from One Punch Man, anime hero with a smooth bald head, calm deadpan expression, bright yellow one-piece superhero jumpsuit with a white zipper, flowing white cape, red gloves and red boots",
    "eren": "Eren Yeager from Attack on Titan, intense anime soldier with dark brown hair, striking green eyes, Survey Corps cropped brown leather jacket with Wings of Freedom emblem, white trousers, vertical maneuvering harness and dual blades",
    "levi": "Levi Ackerman from Attack on Titan, sharp-featured anime captain with undercut black hair, steel-grey eyes, white cravat, Survey Corps jacket, green cloak, and dual ODM gear blades",
    "mikasa": "Mikasa Ackerman from Attack on Titan, agile anime soldier with chin-length black hair, dark eyes, iconic crimson red scarf, Survey Corps leather jacket and ODM gear",
    "frieren": "Frieren, slender elven anime mage with long silver-white twin-tails, green eyes, pointed elf ears, white-and-gold striped capelet over a white tunic платье, carrying her red-gemmed golden mage staff",
    "pikachu": "Pikachu from Pokemon, vibrant yellow electric mouse creature with long black-tipped ears, red cheek pouches, brown back stripes, and a lightning-bolt-shaped tail",
    "link": "Link from The Legend of Zelda, agile Hylian hero with pointed ears, blonde hair, Champion's tunic with leather cross-straps, Hylian shield and Master Sword",
}


def translate_french_to_english_core(raw_text: str) -> str:
    """Traduit une requête française (ou bilingue) en anglais fluide tout en injectant
    les descriptions canoniques si un personnage/univers connu est détecté."""
    text = (raw_text or "").strip()
    if not text:
        return ""

    norm = _norm(text)

    # Inject canonical lore if a known character is mentioned
    canonical_matches: list[str] = []
    for key, desc in CANONICAL_CHARACTER_LORE.items():
        if re.search(rf"\b{re.escape(key)}\b", norm):
            canonical_matches.append(desc)

    working = _strip_accents(text)
    for pattern, repl in FR_TO_EN_PHRASES:
        working = re.sub(pattern, repl, working, flags=re.IGNORECASE)

    for pattern, repl in FR_STOPWORD_CLEANUP:
        working = re.sub(pattern, repl, working, flags=re.IGNORECASE)

    # Clean articles at boundaries when preceded by English words
    working = re.sub(r"\b(un|une)\b", "a", working, flags=re.IGNORECASE)
    working = re.sub(r"\b(le|la|les)\b", "the", working, flags=re.IGNORECASE)
    working = re.sub(r"\b(du|des|de la|de l')\b", "of the", working, flags=re.IGNORECASE)
    working = re.sub(r"\s+([,.;!?])", r"\1", working)
    working = re.sub(r"\s{2,}", " ", working).strip(" ,.;:-")

    if canonical_matches:
        canon_str = "; ".join(canonical_matches)
        if len(working.split()) <= 4:
            return canon_str
        return f"{canon_str} — {working}"

    return working or text


def _call_local_ollama_director(
    raw_prompt: str,
    target_module: str,
    subject_ontology: str,
    effective_render_mode: str,
    operation_mode: str,
    has_reference: bool,
    conversation_context: str = "",
    timeout_s: float = 4.5,
) -> dict[str, str] | None:
    """Interroge Ollama local (si actif et rapide) pour affiner la traduction et
    l'expansion anglaise tout en respectant strictement la décision ontologique."""
    system_rules = (
        "/no_think\n"
        "You are the Cognitive Prompt & Ontology Director of AuroraIA.\n"
        "Translate and expand the user's request into fluent, vivid, domain-accurate ENGLISH.\n"
        f"- Target module: {target_module}\n"
        f"- Detected subject ontology: {subject_ontology}\n"
        f"- Mandatory render mode: {effective_render_mode}\n"
        f"- Operation mode: {operation_mode}\n"
        "STRICT ONTOLOGICAL RULES:\n"
        "1. If Mandatory render mode is 'native_anime_stylized': keep the character 100% in its authentic native anime/manga/stylized aesthetic (clean linework, cel-shaded or stylized anime shading, expressive anime eyes, stylized hair locks). NEVER add realistic human skin pores, photography lenses, or live-action traits.\n"
        "2. If Mandatory render mode is 'hybrid_anime_with_real_textures': preserve the anime character's exact iconic costume, hair silhouette, and identity, while applying realistic human skin micro-texture, pores, subsurface scattering, and physical fabric materials as explicitly requested.\n"
        "3. If Mandatory render mode is 'native_photorealistic': render with true-to-life physical photorealism, natural human skin texture (if human), optical depth, and realistic PBR materials.\n"
        "4. If Mandatory render mode is 'hybrid_real_to_stylized': preserve the subject's recognizable identity while rendering in the requested stylized/anime/pixel medium.\n"
        "5. If Operation mode is 'modification': lock 100% of the existing subject's identity, native style, pose, and unmentioned elements; describe ONLY the requested modification integrated seamlessly.\n"
        "Output ONLY valid JSON: {\"english_subject\": \"...\", \"english_expanded_prompt\": \"...\", \"reasoning_fr\": \"...\"}"
    )
    user_msg = f"User prompt: {raw_prompt}"
    if conversation_context:
        user_msg += f"\nRecent context: {conversation_context[:500]}"
    if has_reference:
        user_msg += "\nHas visual reference attached: true"

    payload = json.dumps({
        "model": "qwen2.5:7b",
        "messages": [
            {"role": "system", "content": system_rules},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "options": {"temperature": 0.15, "num_predict": 320, "num_ctx": 2048},
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            content = (data.get("message") or {}).get("content") or ""
            content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                parsed = json.loads(match.group(0))
                if isinstance(parsed.get("english_expanded_prompt"), str) and len(parsed["english_expanded_prompt"].strip()) > 20:
                    return parsed
    except Exception:
        pass
    return None


def analyze_and_direct_prompt(
    raw_prompt: str,
    target_module: str = "image",
    mode_hint: str | None = None,
    requested_style: str | None = None,
    has_reference: bool = False,
    conversation_context: str = "",
    use_llm: bool = False,
) -> dict[str, Any]:
    """Analyse l'ontologie du sujet, détecte les overrides explicites de texture/style,
    distingue création vs modification, et produit un prompt anglais complet et fidèle."""
    clean_raw = (raw_prompt or "").strip()
    norm = _norm(clean_raw)
    ctx_norm = _norm(conversation_context)
    req_style_norm = _norm(requested_style or "")

    # 1. Détection Création vs Modification vs Reproduction
    is_reproduction = (
        mode_hint == "replicate"
        or bool(REPRODUCTION_INTENT_RE.search(norm))
    )
    is_modification = (
        not is_reproduction
        and (
            mode_hint in {"edit", "modification", "style_transfer"}
            or bool(MODIFICATION_INTENT_RE.search(norm))
        )
    )
    operation_mode = (
        "reproduction" if is_reproduction
        else "modification" if is_modification
        else "creation"
    )

    # 2. Détection de l'ontologie intrinsèque du sujet (dans le prompt actuel OU héritée du contexte si modification)
    has_anime_signal_in_prompt = bool(ANIME_UNIVERSE_AND_CHARACTER_PATTERNS.search(norm))
    has_anime_signal_in_ctx = is_modification and bool(ANIME_UNIVERSE_AND_CHARACTER_PATTERNS.search(ctx_norm))
    has_anime_style_selected = any(tok in req_style_norm for tok in ("anime", "manga", "ghibli", "cel"))

    is_game_asset = bool(GAME_ASSET_RE.search(norm)) or any(
        tok in req_style_norm for tok in ("pixel", "isometric", "low-poly", "low_poly")
    )
    is_mechanical_cad = bool(MECHANICAL_CAD_RE.search(norm))
    is_character = bool(CHARACTER_SUBJECT_RE.search(norm)) or has_anime_signal_in_prompt or has_anime_signal_in_ctx

    # 3. Détection des overrides explicites demandés par l'utilisateur
    explicit_real_textures_override = bool(EXPLICIT_REAL_TEXTURES_OVERRIDE_RE.search(norm))
    explicit_stylized_override = bool(EXPLICIT_STYLIZED_OVERRIDE_RE.search(norm)) or has_anime_style_selected

    # Détermination de l'ontologie intrinsèque du sujet
    if is_mechanical_cad:
        subject_ontology = "mechanical_cad_engineering"
    elif is_game_asset:
        subject_ontology = "game_character_or_asset"
    elif has_anime_signal_in_prompt or has_anime_signal_in_ctx:
        # Même si l'utilisateur n'a pas tapé le mot "anime" (ex: "Natsu", "Goku", "Luffy"),
        # ou s'il a dit "un perso animé", l'ontologie native est anime_manga_character.
        subject_ontology = "anime_manga_character"
    elif is_character:
        subject_ontology = "real_human_subject"
    else:
        subject_ontology = "real_world_object_or_scene"

    # 4. Calcul du mode de rendu effectif (Règle d'or de l'utilisateur)
    # - Sujet animé -> rendu animé natif direct SAUF si textures de personne réelle demandées exprès
    # - Sujet réel  -> rendu photoréaliste natif direct SAUF si stylisation animé/cartoon demandée exprès
    if subject_ontology == "anime_manga_character":
        if explicit_real_textures_override:
            effective_render_mode = "hybrid_anime_with_real_textures"
            style_category = "photo_realistic"
        else:
            effective_render_mode = "native_anime_stylized"
            style_category = "stylized_manga_ink" if "manga" in norm and "noir et blanc" in norm else "stylized_anime_ghibli"
    elif subject_ontology == "game_character_or_asset":
        effective_render_mode = "native_game_stylized"
        style_category = "game_asset_pixel_art" if "pixel" in norm else "game_asset_3d_prop"
    elif subject_ontology == "mechanical_cad_engineering":
        effective_render_mode = "native_engineering_pbr"
        style_category = "photo_realistic"
    else:
        # Sujet intrinsèquement réel (personne réelle, portrait, objet physique, paysage)
        if explicit_stylized_override and not explicit_real_textures_override:
            effective_render_mode = "hybrid_real_to_stylized"
            style_category = "stylized_anime_ghibli"
        else:
            effective_render_mode = "native_photorealistic"
            style_category = "photo_realistic"

    # 5. Traduction en anglais du cœur de la demande
    english_core = translate_french_to_english_core(clean_raw)

    # 6. Construction déterministe haute-fidélité en anglais selon (target_module, effective_render_mode, operation_mode)
    if operation_mode == "modification":
        if effective_render_mode == "native_anime_stylized":
            style_lock = (
                "STRICT MODIFICATION LOCK (ANIME ONTOLOGY): Preserve 100% of the existing anime character's "
                "identity, facial proportions, cel-shaded linework, pose, framing, and unmentioned costume colors. "
                "Do NOT convert the character into a photorealistic human or add real skin pores."
            )
            negative_prompt = (
                "photorealistic human skin pores, live-action photo, 3d plastic doll, uncanny valley, "
                "identity drift, altered pose, extra limbs, blurry linework, deformed hands, watermark"
            )
        elif effective_render_mode == "hybrid_anime_with_real_textures":
            style_lock = (
                "TARGETED TEXTURE MODIFICATION (ANIME TO REAL HUMAN SKIN): Preserve the exact iconic anime character "
                "silhouette, hairstyle geometry, pose, and costume design, while upgrading the surfaces to "
                "photorealistic real human skin micro-texture, natural pores, subsurface scattering, and physical fabric weaves."
            )
            negative_prompt = (
                "flat 2d cel shading, cartoon outlines, plastic doll skin, lost character identity, "
                "wrong hairstyle, deformed anatomy, blurry, watermark"
            )
        else:
            style_lock = (
                "STRICT MODIFICATION LOCK (PHOTOREALISTIC ONTOLOGY): Preserve 100% of the original subject's "
                "identity, facial structure, natural body proportions, lighting, and background. "
                "Apply ONLY the requested change seamlessly with physically accurate materials and shadows."
            )
            negative_prompt = (
                "anime, cartoon, cel shading, plastic airbrushed skin, identity change, warped proportions, "
                "sticker look, ghost artifacts, extra fingers, watermark"
            )

        english_expanded = (
            f"Targeted modification request: {english_core}. "
            f"{style_lock} "
            f"Ensure seamless perspective, consistent lighting direction, and natural contact shadows."
        )
        reasoning_fr = (
            f"Modification détectée ({effective_render_mode}) : verrouillage strict du sujet existant "
            f"et application chirurgicale du changement en anglais."
        )

    elif target_module == "3d":
        if effective_render_mode == "native_anime_stylized":
            english_expanded = (
                f"Full-body 3D character reference of {english_core}, rendered in authentic native anime/stylized "
                f"3D aesthetic. Faithful anime facial proportions with crisp expressive eyes, clean defined nose and jawline, "
                f"sculpted stylized hair locks with sharp silhouette separation, and iconic costume geometry with vibrant "
                f"cel-shaded PBR material zones. Centered full-body three-quarter view on a solid black studio background, "
                f"clear separation between arms, fingers, and legs for skeletal rigging, zero photorealistic skin pores or "
                f"uncanny live-action textures."
            )
            negative_prompt = (
                "photorealistic skin pores, old wrinkles, live-action cosplay photo, uncanny valley human face, "
                "melted blob, chibi marshmallow, cropped legs, fused fingers, cluttered background, text, watermark"
            )
            reasoning_fr = (
                "Personnage/sujet animé détecté : génération 3D directe dans son vrai style animé/stylisé natif "
                "(sans textures de peau humaine réelle non demandées)."
            )
        elif effective_render_mode == "hybrid_anime_with_real_textures":
            english_expanded = (
                f"Full-body 3D character reference of {english_core}, combining the character's exact iconic anime "
                f"silhouette, signature hairstyle, and official costume design with explicit photorealistic real human "
                f"skin textures, fine epidermal pores, natural subsurface scattering, and physically based fabric, leather, "
                f"and metal micro-textures. Centered full-body three-quarter angle on a solid black studio background, "
                f"anatomically articulated hands and separated limbs ready for 3D reconstruction and rigging."
            )
            negative_prompt = (
                "flat 2d cartoon cel-shading, plastic toy skin, generic face losing character identity, "
                "melted geometry, fused limbs, cropped feet, watermark"
            )
            reasoning_fr = (
                "Personnage animé avec demande explicite de textures de personne réelle : préservation de l'identité "
                "et du design animé avec application de vraies textures cutanées et matériaux PBR réalistes."
            )
        elif effective_render_mode == "native_engineering_pbr":
            english_expanded = (
                f"Precision 3D engineering and product reference of {english_core}. Crisp hard-surface CAD geometry, "
                f"clean bevels, mechanically accurate part separation, distinct metallic and polymer PBR material zones, "
                f"three-quarter orthographic-friendly studio angle on a solid black background revealing front, side, and top volume."
            )
            negative_prompt = (
                "melted organic surfaces, asymmetric distortion, blurry edges, cartoon style, cluttered scene, text, watermark"
            )
            reasoning_fr = (
                "Pièce mécanique / produit technique détecté : expansion 3D orientée géométrie CAO hard-surface et PBR."
            )
        else:
            english_expanded = (
                f"Full-body photorealistic 3D reference of {english_core}. True-to-life physical proportions (1:7.5 adult "
                f"humanoid ratio if human), authentic natural skin micro-texture with fine pores, realistic hair strands, "
                f"and physically accurate fabric and surface materials with strong albedo contrast. Centered three-quarter "
                f"volumetric studio view on a solid black background with crisp edge separation and directional key and rim lighting."
            )
            negative_prompt = (
                "anime, cartoon, cel-shaded, chibi, plastic doll skin, airbrushed wax face, melted blob, "
                "fused fingers, cropped body, watermark"
            )
            reasoning_fr = (
                "Sujet réel détecté : génération 3D photoréaliste physique directe avec proportions et textures réelles."
            )

    else:
        # Image / Video / Drawing modules
        if effective_render_mode == "native_anime_stylized":
            english_expanded = (
                f"Masterpiece official-grade anime key visual of {english_core}. Authentic native anime character design "
                f"with crisp expressive linework, vibrant cel-shaded color separation, luminous expressive anime eyes, "
                f"dynamic sculpted hair silhouette, and faithful costume details. Set within a richly illustrated, cohesive "
                f"anime environment with layered foreground-to-background atmospheric depth and dramatic cinematic anime lighting. "
                f"Pure 2D/cel-shaded anime fidelity, no realistic human skin pores."
            )
            negative_prompt = (
                "photorealistic human skin pores, live-action photography, 3d CGI doll, uncanny valley, "
                "muddy shading, off-model face, deformed hands, extra fingers, empty background, watermark"
            )
            reasoning_fr = (
                "Sujet animé détecté : développement artistique en anglais dans son style animé/cel-shadé authentique "
                "(aucune texture de peau humaine réelle forcée)."
            )
        elif effective_render_mode == "hybrid_anime_with_real_textures":
            english_expanded = (
                f"High-end live-action cinematic portrait and full-scene realization of {english_core}, faithfully preserving "
                f"the character's iconic anime hairstyle silhouette, costume colors, and signature identity while rendering "
                f"with explicit photorealistic real human skin texture, fine natural pores, lifelike eyes with corneal reflections, "
                f"and tactile real-world fabric, leather, and metal weave. Framed in a richly detailed, physically lit environment "
                f"with natural optical depth of field."
            )
            negative_prompt = (
                "flat 2d cel-shading, cartoon lineart, plastic airbrushed skin, generic cosplay losing character traits, "
                "deformed anatomy, extra fingers, watermark"
            )
            reasoning_fr = (
                "Sujet animé + override explicite « textures de personne réelle » : fusion de l'identité canonique "
                "du personnage avec une vraie texture de peau humaine photoréaliste."
            )
        elif effective_render_mode == "hybrid_real_to_stylized":
            english_expanded = (
                f"Expressive stylized anime/illustrated adaptation of {english_core}, preserving the recognizable identity, "
                f"posture, and key traits of the subject while translating the rendering into crisp anime linework, "
                f"vibrant cel-shaded lighting, and a richly illustrated background environment."
            )
            negative_prompt = (
                "raw unstylized photograph, uncanny realistic skin pores, muddy colors, deformed hands, watermark"
            )
            reasoning_fr = (
                "Sujet réel avec demande explicite de stylisation animée : adaptation fidèle en esthétique animée."
            )
        elif effective_render_mode == "native_game_stylized":
            english_expanded = (
                f"Production-ready video game art of {english_core}. Crisp readable silhouette, deliberate stylized materials "
                f"and clean lighting, tailored for immediate game engine integration."
            )
            negative_prompt = "blurry edges, noisy artifacts, cropped silhouette, watermark"
            reasoning_fr = "Asset de jeu vidéo détecté : développement en anglais optimisé pour la lisibilité en jeu."
        else:
            is_human_portrait = is_character
            if is_human_portrait:
                english_expanded = (
                    f"Authentic editorial documentary photograph of {english_core}. Natural directional illumination casting "
                    f"soft physical shadows that reveal genuine human skin micro-texture, fine natural pores, subtle organic "
                    f"imperfections, and expressive eyes with crisp catchlights. Set in a fully realized, atmospheric real-world "
                    f"environment with foreground-to-background depth, captured on an 85mm prime lens with true-to-life color science "
                    f"and zero artificial plastic smoothing."
                )
            else:
                english_expanded = (
                    f"High-precision documentary-grade photograph of {english_core}. Physically accurate lighting with "
                    f"natural specular highlights, tactile real-world surface micro-textures, grounded contact shadows, and "
                    f"rich environmental depth from foreground to horizon, captured with sharp optical clarity and organic tonal balance."
                )
            negative_prompt = (
                "anime, cartoon, cel-shading, 3d render, CGI doll, plastic airbrushed skin, wax face, "
                "oversaturated HDR, deformed anatomy, extra fingers, blurry, watermark"
            )
            reasoning_fr = (
                "Sujet réel détecté : développement en anglais en photoréalisme physique natif (vraie texture de peau et lumière optique)."
            )

    llm_used = False
    if use_llm:
        llm_res = _call_local_ollama_director(
            raw_prompt=clean_raw,
            target_module=target_module,
            subject_ontology=subject_ontology,
            effective_render_mode=effective_render_mode,
            operation_mode=operation_mode,
            has_reference=has_reference,
            conversation_context=conversation_context,
        )
        if llm_res:
            english_expanded = llm_res["english_expanded_prompt"].strip()
            if llm_res.get("english_subject"):
                english_core = llm_res["english_subject"].strip()
            if llm_res.get("reasoning_fr"):
                reasoning_fr = llm_res["reasoning_fr"].strip()
            llm_used = True

    return {
        "ok": True,
        "raw_prompt": clean_raw,
        "target_module": target_module,
        "operation_mode": operation_mode,
        "subject_ontology": subject_ontology,
        "effective_render_mode": effective_render_mode,
        "explicit_real_textures_override": explicit_real_textures_override,
        "explicit_stylized_override": explicit_stylized_override,
        "preserve_native_anime_style": effective_render_mode == "native_anime_stylized",
        "preserve_native_real_style": effective_render_mode == "native_photorealistic",
        "lock_unmentioned_attributes": operation_mode in {"modification", "reproduction"},
        "style_category": style_category,
        "english_subject": english_core,
        "english_expanded_prompt": english_expanded,
        "negative_prompt": negative_prompt,
        "reasoning_fr": reasoning_fr,
        "llm_used": llm_used,
    }
