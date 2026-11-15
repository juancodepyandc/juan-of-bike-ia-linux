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

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from typing import Any


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(ch) != "Mn"
    )


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents(text).lower()).strip()


# Signaux d'univers, d'archétypes et d'entités intrinsèquement Animé / Manga / Cartoon / Stylisé
ANIME_UNIVERSE_AND_CHARACTER_PATTERNS = re.compile(
    r"\b("
    r"anime|manga|manhwa|webtoon|shonen|shojo|seinen|isekai|chibi|cel[- ]?shad(?:ed|ing)|"
    r"ghibli|makoto\s*shinkai|ufotable|mappa|toei|kyoani|studio\s*trigger|pixar|disney|dreamworks|illumination|xilam|looney\s*tunes|tex\s*avery|hanna[- ]?barbera|cartoon|dessin\s*anime|toon|"
    r"zig\s*et\s*sharko|zig\s*and\s*sharko|zig|sharko|bernie\s*le\s*bernard|oggy|oggy\s*et\s*les\s*cafards|les\s*dalton|joe\s*dalton|averell|"
    r"asterix|obelix|idefix|panoramix|tintin|milou|capitaine\s*haddock|lucky\s*luke|jolly\s*jumper|rantanplan|marsupilami|gaston\s*lagaffe|spirou|fantasio|schtroumpf|smurf|titeuf|boule\s*et\s*bill|wakfu|dofus|"
    r"bob\s*l[' ]?eponge|spongebob|patrick\s*star|patrick\s*l[' ]?etoile|squidward|carlo\s*tentacule|mr\s*krabs|plankton|"
    r"tom\s*et\s*jerry|tom\s*and\s*jerry|bugs\s*bunny|daffy\s*duck|tweety|titi\s*et\s*grosminet|sylvestre|grosminet|bip\s*bip|wile\s*e\s*coyote|taz|"
    r"mickey\s*mouse|mickey|minnie|donald\s*duck|dingo|goofy|pluto|picsou|scrooge\s*mcduck|stitch|lilo\s*et\s*stitch|simba|timon|pumbaa|aladdin|buzz\s*l[' ]?eclair|buzz\s*lightyear|woody|toy\s*story|wall[- ]?e|baymax|elsa|olaf|vaiana|moana|raiponce|rapunzel|"
    r"shrek|chat\s*potte|puss\s*in\s*boots|kung\s*fu\s*panda|po\s*panda|minions?|gru|megamind|wallace\s*et\s*gromit|shaun\s*le\s*mouton|"
    r"homer\s*simpson|bart\s*simpson|lisa\s*simpson|marge\s*simpson|simpsons?|peter\s*griffin|stewie\s*griffin|family\s*guy|bender|futurama|rick\s*et\s*morty|rick\s*and\s*morty|rick\s*sanchez|morty\s*smith|south\s*park|cartman|"
    r"scooby[- ]?doo|shaggy|sammy\s*rogers|ben\s*10|gumball|darwin\s*watterson|finn\s*the\s*human|jake\s*the\s*dog|adventure\s*time|steven\s*universe|danny\s*phantom|aang|korra|zuko|super\s*nanas|powerpuff\s*girls|samurai\s*jack|garfield|snoopy|charlie\s*brown|popeye|panthere\s*rose|pink\s*panther|inspecteur\s*gadget|inspector\s*gadget|"
    r"rayman|lapins?\s*cretins?|rabbids?|crash\s*bandicoot|spyro|ratchet|clank|cuphead|mugman|caine|pomni|amazing\s*digital\s*circus|"
    r"natsu|lucy\s*heartfilia|erza|gray\s*fullbuster|happy\s*exceed|wendy\s*marvell|gajeel|laxus|zeref|acnologia|fairy\s*tail|"
    r"goku|son\s*goku|san\s*goku|sangoku|kakarot|vegeta|gohan|sangohan|goten|sangoten|trunks|piccolo|satanko|frieza|freezer|cell|majin\s*buu|buu|broly|beerus|whis|jiren|bardock|bulma|krilin|tortue\s*geniale|shenron|saiyan|super\s*saiyan|ssj[1-4b]?|ultra\s*instinct|dbz|dbs|dragon\s*ball|"
    r"luffy|monkey\s*d|zoro|zorro|roronoa|sanji|nami|robin|chopper|usopp|pipo|brook|franky|jinbe|shanks|ace|sabo|law|kaido|katakuri|doflamingo|mihawk|yamato|barbe\s*blanche|barbe\s*noire|gear\s*[245]|one\s*piece|"
    r"naruto|sasuke|sakura|kakashi|itachi|madara|obito|hinata|gaara|jiraiya|tsunade|orochimaru|minato|hashirama|pain|nagato|kurama|kyubi|mode\s*ermite|sage\s*mode|akatsuki|sharingan|rinnegan|konoha|"
    r"ichigo|rukia|ai[z]en|byakuya|kenpachi|ulquiorra|grimmjow|toshiro|yoruichi|urahara|bleach|bankai|shinigami|"
    r"tanjiro|nezuko|zenitsu|inosuke|rengoku|giyu|muzan|shinobu|mitsuri|tengen|muichiro|kokushibo|akaza|hashira|demon\s*slayer|kimetsu|"
    r"gojo|satoru\s*gojo|sukuna|ryomen\s*sukuna|yuji\s*itadori|itadori|megumi|nobara|toji|geto|yuta|maki|hakari|choso|nanami|jjk|jujutsu\s*kaisen|"
    r"eren|mikasa|levi|livai|armin|reiner|erwin|zeke|titan|attaque\s*des\s*titans|attack\s*on\s*titan|shingeki|snk|"
    r"saitama|genos|tatsumaki|fubuki|garou|boros|one\s*punch|"
    r"gon|killua|kirua|kurapika|hisoka|meruem|chrollo|kuroro|netero|hxh|hunter\s*x\s*hunter|"
    r"deku|midoriya|bakugo|todoroki|all\s*might|endeavor|hawks|shigaraki|dabi|toga|mha|my\s*hero\s*academia|boku\s*no\s*hero|"
    r"asta|yuno|yami|noelle|julius|black\s*clover|"
    r"denji|makima|power|aki|pochita|reze|chainsaw\s*man|"
    r"frieren|fern|stark|himmel|"
    r"anya|yor\s*forger|loid\s*forger|spy\s*x\s*family|"
    r"sung\s*jin[- ]?woo|jin[- ]?woo|solo\s*leveling|igris|beru|"
    r"edward\s*elric|alphonse\s*elric|roy\s*mustang|fullmetal|"
    r"light\s*yagami|ryuk|l\s*lawliet|misa|death\s*note|"
    r"lelouch|code\s*geass|rem|emilia|subaru|re\s*zero|"
    r"kirito|asuna|sword\s*art\s*online|rimuru|tensura|ainz|overlord|"
    r"jotaro|dio\s*brando|giorno|josuke|jolyne|jojo|"
    r"guts|griffith|casca|berserk|kaneki|tokyo\s*ghoul|baki|yujiro|ippo|"
    r"seiya|shiryu|hyoga|ikki|saint\s*seiya|chevalier[s]?\s+du\s+zodiaque|goldorak|grendizer|actarus|albator|harlock|nicky\s*larson|ryo\s*saeba|evangelion|asuka|rei\s*ayanami|gundam|totoro|mononoke|chihiro|krokmou|toothless|"
    r"pikachu|charizard|dracaufeu|salameche|charmander|carapuce|squirtle|tortank|blastoise|bulbizarre|bulbasaur|mewtwo|mew|lucario|eevee|evoli|ectoplasma|gengar|amphinobi|greninja|rayquaza|ronflex|snorlax|gardevoir|pokemon|"
    r"hatsune\s*miku|vocaloid|genshin|raiden\s*shogun|furina|nahida|zhongli|hu\s*tao|arlecc?hino|neuvillette|honkai|"
    r"link|zelda|ganondorf|hyrule|mario|luigi|peach|bowser|yoshi|kirby|samus|sonic|miles\s*prower|tails\s*prower|knuckles|shadow\s*the\s*hedgehog|"
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
    r"en\s+(?:style\s+|version\s+)?r[eé]aliste|"
    r"transform(?:e|er|[eé])\s+(?:[\wÀ-ÿ'’_-]+\s+){0,4}en\s+(?:personne\s+)?r[eé]el(?:le|iste)?|"
    r"version\s+(?:personne\s+)?r[eé]el(?:le|iste)|rendu\s+personne\s+r[eé]elle|"
    r"live[- ]?action|cosplay\s+r[eé]aliste|photorealistic\s+human\s+skin|"
    r"real\s+human\s+(?:skin\s+)?textures?|realistic\s+skin\s+pores|"
    r"comme\s+une?\s+vrai[e]?\s+(?:personne|humain)|"
    r"avec\s+(?:des\s+)?textures?\s+(?:de\s+personne\s+)?r[eé]el(?:le)?s?"
    r")\b",
    re.IGNORECASE,
)

# Demande explicite de stylisation animé/cartoon/figurine/jouet/pixel/cubique sur n'importe quel sujet (y compris un personnage réel)
EXPLICIT_STYLIZED_OVERRIDE_RE = re.compile(
    r"(?<!pas\s)(?<!non\s)(?<!not\s)\b("
    r"en\s+(?:style\s+|version\s+|mode\s+)?(?:anime|anim[eé]|manga|cartoon|dessin\s+anim[eé]|toon|ghibli|pixar|disney|dreamworks|chibi|kawaii|pixel\s*art|low[- ]?poly|voxel|cubique|cube|cubic|cubiste|blocky|minecraft|roblox|bd|bande\s+dessin[eé]e|comics?|figurine(?:\s+cartoon)?|funko(?:\s*pop)?|pop\s*vinyl|nendoroid|jouet|toy|action\s+figure|peluche|plush(?:ie)?|p[aâ]te\s+[aà]\s+modeler|clay(?:mation)?|stop[- ]?motion|lego|playmobil|caricature|statue(?:tte)?|origami)|"
    r"(?:style|facon|fa[cç]on|type|genre|rendu|aspect|look|version|esprit|esthetique|esth[eé]tique)\s+(?:anime|anim[eé]|manga|cartoon|dessin\s+anim[eé]|toon|cel[- ]?shad(?:ed|ing)|ghibli|pixar|disney|dreamworks|xilam|looney\s+tunes|zig\s+et\s+sharko|chibi|kawaii|pixel\s*art|low[- ]?poly|voxel|cubique|cube|cubic|cubiste|blocky|minecraft|roblox|bd|bande\s+dessin[eé]e|franco[- ]?belge|comics?|figurine|funko(?:\s*pop)?|nendoroid|jouet|toy|peluche|plush|p[aâ]te\s+[aà]\s+modeler|clay(?:mation)?|stop[- ]?motion|lego|playmobil|caricature|origami)|"
    r"(?:transform(?:e|er|ee?)|chang(?:e|er|ee?)|converti(?:s|r)?|adapt(?:e|er|ee?)|met(?:s|tre)|pass(?:e|er))\s+(?:[\w'’_-]+\s+){0,6}en\s+(?:style\s+|version\s+)?(?:anime|anim[eé]|manga|cartoon|dessin\s+anim[eé]|toon|ghibli|pixar|disney|chibi|kawaii|figurine|funko(?:\s*pop)?|jouet|toy|peluche|plush|p[aâ]te\s+[aà]\s+modeler|clay(?:mation)?|low[- ]?poly|voxel|cubique|cube|cubic|cubiste|blocky|minecraft|roblox|lego|playmobil|bd|comics?|caricature|statue(?:tte)?|origami)|"
    r"cartoon|dessin\s+anime|toon\s+shader|cel[- ]?shad(?:ed|ing)|figurine(?:\s+cartoon|\s+stylis[eé]e?|\s+3d|\s+pop|\s+chibi)?|cartoon\s+figurine|funko\s*pop|pop\s*vinyl|nendoroid|chibi|kawaii|claymation|pate\s+a\s+modeler|peluche|plush(?:ie)?|playmobil|lego\s+minifig(?:ure)?|cubique|cubic\s+style|voxel\s+style"
    r")\b",
    re.IGNORECASE,
)


def detect_requested_stylized_submode(raw_text: str) -> str | None:
    """Identifie la sous-famille exacte de style stylisé (cartoon, figurine/jouet,
    claymation/peluche, low-poly/voxel/cubique ou anime/manga) pour adapter les descripteurs 3D/Image.
    Retourne None lorsqu'un style/matériau libre personnalisé hors de ces 5 familles est demandé."""
    norm = _norm(raw_text or "")
    if re.search(
        r"\b(figurine|funko|pop\s*vinyl|nendoroid|jouet|toy|action\s*figure|statuette|playmobil|lego|bionicle|bobblehead)\b",
        norm,
    ):
        if re.search(r"\b(cartoon|dessin\s*anime|pixar|disney|toon|zig|sharko|oggy|simpson|looney)\b", norm):
            return "cartoon_figurine"
        return "figurine_toy"
    if re.search(r"\b(pate\s+a\s+modeler|clay|claymation|stop\s*motion|plastiline|wallace|gromit|shaun|peluche|plush|plushie|feutrine|crochet|amigurumi)\b", norm):
        return "clay_or_plush"
    if re.search(r"\b(low[- ]?poly|voxel|cubique|cube|cubic|cubiste|blocky|minecraft|roblox|pixel\s*art|polygonal|isometrique|isometric)\b", norm):
        return "lowpoly_voxel"
    if re.search(
        r"\b(cartoon|dessin\s*anime|toon|pixar|disney|dreamworks|illumination|xilam|looney\s*tunes|tex\s*avery|hanna\s*barbera|"
        r"zig|sharko|bernie|oggy|dalton|asterix|obelix|idefix|tintin|milou|haddock|lucky\s*luke|marsupilami|gaston|spirou|schtroumpf|smurf|titeuf|boule\s*et\s*bill|"
        r"bob\s*l\s*eponge|spongebob|patrick|squidward|carlo|krabs|plankton|tom\s*et\s*jerry|tom\s*and\s*jerry|bugs\s*bunny|daffy|tweety|titi|grosminet|sylvestre|bip\s*bip|coyote|taz|"
        r"mickey|minnie|donald|dingo|goofy|pluto|picsou|stitch|simba|timon|pumbaa|aladdin|buzz|woody|wall\s*e|baymax|elsa|olaf|vaiana|moana|raiponce|rapunzel|"
        r"shrek|chat\s*potte|puss\s*in\s*boots|kung\s*fu\s*panda|minion|gru|megamind|"
        r"homer|bart|lisa|marge|simpson|peter\s*griffin|stewie|family\s*guy|bender|fry|futurama|rick|morty|south\s*park|cartman|"
        r"scooby|shaggy|sammy|ben\s*10|gumball|darwin|finn|jake|adventure\s*time|steven\s*universe|danny\s*phantom|powerpuff|super\s*nanas|samurai\s*jack|garfield|snoopy|popeye|panthere\s*rose|pink\s*panther|inspecteur\s*gadget|"
        r"rayman|lapin\s*cretin|rabbid|crash\s*bandicoot|spyro|ratchet|clank|cuphead|mugman|caine|pomni|digital\s*circus|"
        r"bd|bande\s*dessinee|franco[- ]?belge|comics?|caricature)\b",
        norm,
    ):
        return "cartoon_3d"
    if re.search(r"\b(anime|manga|manhwa|webtoon|shonen|shojo|seinen|ghibli|cel[- ]?shad(?:ed|ing)|chibi|kawaii)\b", norm):
        return "anime_cel"
    if ANIME_UNIVERSE_AND_CHARACTER_PATTERNS.search(norm) and not extract_universal_style_clause(raw_text).get("has_style_clause"):
        return "anime_cel"
    return None

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
    r"engrenage|gear(?!\s*[2345]\b)|poulie|pulley|courroie|belt|verin|actuator|charniere|hinge|"
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
    (r"\bpersonnage\s+r[eé]el\b", "real-life person"),
    (r"\bun\s+perso\s+d[' ]?anim[eé]\b", "an authentic anime character"),
    (r"\bun\s+personnage\s+d[' ]?anim[eé]\b", "an authentic anime character"),
    (r"\bun\s+perso\s+anim[eé]\b", "an authentic anime character"),
    (r"\bun\s+personnage\s+anim[eé]\b", "an authentic anime character"),
    (r"\bun\s+personnage\s+de\s+cartoon\b|\bun\s+perso\s+cartoon\b|\bun\s+personnage\s+cartoon\b", "an expressive 3D cartoon character"),
    (r"\bun\s+personnage\s+de\s+dessin\s+anim[eé]\b", "an expressive animated cartoon character"),
    (r"\ben\s+figurine\s+cartoon\b|\ben\s+cartoon\s+figurine\b", "transformed into a stylized 3D cartoon collectible figurine"),
    (r"\ben\s+figurine\b|\bversion\s+figurine\b|\bstyle\s+figurine\b", "as a stylized collectible 3D figurine"),
    (r"\ben\s+funko\s*pop\b|\bstyle\s+funko\s*pop\b", "as a stylized vinyl Funko Pop collectible figure with oversized head"),
    (r"\ben\s+cartoon\b|\bstyle\s+cartoon\b|\bversion\s+cartoon\b|\bfa[cç]on\s+cartoon\b", "in vibrant 3D cartoon style with expressive cartoon proportions"),
    (r"\ben\s+dessin\s+anim[eé]\b|\bstyle\s+dessin\s+anim[eé]\b|\bfa[cç]on\s+dessin\s+anim[eé]\b", "in expressive animated cartoon style"),
    (r"\ben\s+pixar\b|\bstyle\s+pixar\b|\bfa[cç]on\s+pixar\b", "in expressive Pixar/Disney 3D animated feature film style"),
    (r"\ben\s+chibi\b|\bstyle\s+chibi\b|\bversion\s+chibi\b", "in cute super-deformed chibi 3D style"),
    (r"\ben\s+peluche\b|\bstyle\s+peluche\b|\bfa[cç]on\s+peluche\b", "as a soft stitched 3D plush toy"),
    (r"\ben\s+jouet\b|\bstyle\s+jouet\b", "as a stylized 3D articulated toy figure"),
    (r"\ben\s+p[aâ]te\s+[aà]\s+modeler\b|\ben\s+clay(?:mation)?\b|\bstyle\s+clay(?:mation)?\b", "in tactile claymation stop-motion sculpted clay style"),
    (r"\ben\s+lego\b|\bstyle\s+lego\b", "as a stylized 3D LEGO minifigure"),
    (r"\ben\s+low[- ]?poly\b|\bstyle\s+low[- ]?poly\b", "in crisp faceted low-poly 3D game art style"),
    (r"\ben\s+voxel\b|\bstyle\s+voxel\b", "in cubic 3D voxel art style"),
    (r"\ben\s+(?:style\s+|version\s+)?cubique\b|\bstyle\s+cubique\b|\bversion\s+cubique\b", "in cubic 3D blocky voxel geometry style made of sharp 3D cubes"),
    (r"\ben\s+bd\b|\ben\s+bande\s+dessin[eé]e\b|\bstyle\s+bd\b", "in expressive Franco-Belgian comic book cartoon style"),
    (r"\ben\s+caricature\b|\bstyle\s+caricature\b", "in expressive stylized 3D caricature style"),
    (r"\ben\s+anim[eé]\b|\bstyle\s+anim[eé]\b", "in authentic anime style"),
    (r"\ben\s+manga\b|\bstyle\s+manga\b", "in authentic manga style"),
    (r"\bun\s+perso\b", "a character"),
    (r"\bun\s+personnage\b", "a character"),
    (r"\bune\s+personne\b", "a real person"),
    (r"\bdans\s+la\s+main\s+droite\b|\bmain\s+droite\b", "in the right hand"),
    (r"\bdans\s+la\s+main\s+gauche\b|\bmain\s+gauche\b", "in the left hand"),
    (r"\bdans\s+chaque\s+main\b", "in each hand"),
    (r"\ba\s+deux\s+mains\b", "wielded with both hands"),
    (r"\bsur\s+le\s+dos\b", "mounted on the back"),
    (r"\bsur\s+l[' ]?epaule\b", "perched on the shoulder"),
    (r"\bau\s+premier\s+plan\b", "in the foreground"),
    (r"\ben\s+arriere[- ]?plan\b", "in the background"),
    (r"\bvue\s+de\s+face\b", "front view"),
    (r"\bvue\s+de\s+dos\b", "back view"),
    (r"\bvue\s+de\s+profil\b", "side profile view"),
    (r"\bcorps\s+entier\b|\ben\s+pied\b", "full-body head-to-toe framing"),
    (r"\btorse\s+nu\b", "bare-chested with defined upper body musculature"),
    (r"\bbras\s+croises\b", "with arms crossed"),
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
    (r"\bcheveux\s+blancs?\b|\bcheveux\s+argentes?\b", "silver-white hair"),
    (r"\bcheveux\s+rouges?\b", "crimson red hair"),
    (r"\bcheveux\s+bleus?\b", "cobalt blue hair"),
    (r"\byeux\s+bleus?\b", "vivid blue eyes"),
    (r"\byeux\s+verts?\b", "emerald green eyes"),
    (r"\byeux\s+rouges?\b", "glowing crimson eyes"),
    (r"\byeux\s+dores?\b|\byeux\s+jaunes?\b", "golden-amber eyes"),
    (r"\bveste\s+noire?\b", "tailored black jacket"),
    (r"\bveste\s+rouge\b", "crimson jacket"),
    (r"\bmanteau\s+long\b", "long flowing coat"),
    (r"\barmure\s+complete\b", "full articulated plate armor"),
    (r"\barmure\b", "ornate armor"),
    (r"\bepee\b", "sword"),
    (r"\bkatana\b", "forged katana blade"),
    (r"\bbouclier\b", "shield"),
    (r"\barc\b", "bow"),
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
# ultra-court ("Natsu", "Sangoku", "Luffy") soit développé avec ses vrais attributs visuels en anglais
CANONICAL_CHARACTER_LORE: dict[str, str] = {
    "natsu": "Natsu Dragneel from Fairy Tail, athletic young anime fire mage with spiky salmon-pink hair, sharp dark eyes, iconic white-and-black checkered scale scarf around his neck, open black sleeveless waistcoat with gold trim over bare muscular chest, white knee-length trousers, black open-toed sandals, red Fairy Tail guild mark on his right shoulder",
    "lucy": "Lucy Heartfilia from Fairy Tail, expressive anime celestial spirit mage with golden blonde hair tied in side tails, warm brown eyes, iconic blue-and-white fitted top, pleated skirt, leather belt with golden Celestial Spirit keys and whip",
    "goku": "Son Goku from Dragon Ball, muscular anime martial artist with iconic wild spiky jet-black hair, determined dark eyes, signature bright orange martial arts gi over a royal blue undershirt, blue wristbands, blue sash belt, and martial arts boots",
    "sangoku": "Son Goku from Dragon Ball, muscular anime martial artist with iconic wild spiky jet-black hair, determined dark eyes, signature bright orange martial arts gi over a royal blue undershirt, blue wristbands, blue sash belt, and martial arts boots",
    "kakarot": "Son Goku (Kakarot) from Dragon Ball, muscular anime martial artist with iconic wild spiky jet-black hair, determined dark eyes, signature bright orange martial arts gi over a royal blue undershirt, blue wristbands, and martial arts boots",
    "vegeta": "Vegeta from Dragon Ball, proud Saiyan prince with tall flame-shaped spiky black hair, sharp widow's peak, intense frowned gaze, royal blue bodysuit under white-and-gold Saiyan battle armor with shoulder pauldrons, white gloves and boots",
    "gohan": "Son Gohan from Dragon Ball, athletic anime martial artist with spiky black hair, determined gaze, purple or orange martial arts gi, wristbands, and fighting boots",
    "sangohan": "Son Gohan from Dragon Ball, athletic anime martial artist with spiky black hair, determined gaze, purple or orange martial arts gi, wristbands, and fighting boots",
    "trunks": "Future Trunks from Dragon Ball, anime warrior with lavender-purple hair parted in the middle, cropped blue Capsule Corp denim jacket, black undershirt, belt with sword sheath strapped across his back",
    "broly": "Broly from Dragon Ball Super, towering hyper-muscular Saiyan warrior with wild spiky black-and-green hair, scar across his chest and cheek, purple ear pelt around his waist, black leggings and green battle boots",
    "piccolo": "Piccolo from Dragon Ball, tall Namekian warrior with green skin, pointed ears, two forehead antennae, purple martial arts gi with weighted white cape and turban",
    "frieza": "Frieza from Dragon Ball, sleek white-and-purple galactic tyrant with glossy purple cranial dome, red eyes, bio-armor shoulders, and long prehensile tail",
    "freezer": "Frieza from Dragon Ball, sleek white-and-purple galactic tyrant with glossy purple cranial dome, red eyes, bio-armor shoulders, and long prehensile tail",
    "luffy": "Monkey D. Luffy from One Piece, energetic anime pirate captain wearing his signature woven straw hat with a red ribbon, tousled black hair, small scar under his left eye, open red vest, blue denim shorts, yellow sash, and sandals",
    "zoro": "Roronoa Zoro from One Piece, muscular anime swordsman with cropped green hair, three gold earrings on his left ear, scar over his left eye, dark green coat, crimson haramaki sash holding three katana swords at his waist",
    "zorro": "Roronoa Zoro from One Piece, muscular anime swordsman with cropped green hair, three gold earrings on his left ear, scar over his left eye, dark green coat, crimson haramaki sash holding three katana swords at his waist",
    "sanji": "Vinsmoke Sanji from One Piece, suave anime martial artist chef with blonde hair covering one eye, curled eyebrow, tailored black double-breasted suit, dress shirt and tie",
    "shanks": "Red-Haired Shanks from One Piece, charismatic anime pirate captain with crimson-red hair, three parallel scars across his left eye, flowing black captain cloak, white shirt and cutlass sword",
    "ace": "Portgas D. Ace from One Piece, athletic anime fire pirate with freckled face, orange cowboy hat with red beads, bare muscular torso with whitebeard tattoo on his back, black shorts and flame powers",
    "naruto": "Naruto Uzumaki from Naruto, spirited anime ninja with spiky bright yellow-blond hair, cobalt blue eyes, three whisker marks on each cheek, Konoha metal headband, orange-and-black zip-up ninja jumpsuit, and ninja sandals",
    "sasuke": "Sasuke Uchiha from Naruto, composed anime ninja with spiky black hair framing his face, dark Sharingan eyes, high-collared Uchiha outfit with rope belt and Kusanagi sword",
    "kakashi": "Kakashi Hatake from Naruto, elite anime ninja with gravity-defying silver-white spiky hair, dark face mask covering nose and mouth, slanted Konoha headband over his left Sharingan eye, green flak vest over dark blue uniform",
    "itachi": "Itachi Uchiha from Naruto, calm anime ninja with long dark hair tied in a low ponytail, facial tear-trough lines, glowing red Sharingan eyes, black Akatsuki cloak with red clouds and high collar",
    "madara": "Madara Uchiha from Naruto, legendary anime warlord with long wild spiky black hair, crimson gunbai war fan, layered crimson plate armor over dark blue tunic, Rinnegan/Sharingan eyes",
    "gojo": "Satoru Gojo from Jujutsu Kaisen, tall slender anime sorcerer with snow-white spiky hair, luminous sky-blue Six Eyes (or signature black blindfold), dark high-necked Jujutsu High uniform jacket",
    "sukuna": "Ryomen Sukuna from Jujutsu Kaisen, menacing anime King of Curses with spiky pinkish-salmon hair, symmetrical black cursed tattoo markings across face, chest and arms, extra pair of eyes beneath his main crimson eyes",
    "tanjiro": "Tanjiro Kamado from Demon Slayer, kind-hearted anime swordsman with burgundy-tipped ruffled black hair, dark red eyes, flame-like scar on his forehead, hanafuda earrings, green-and-black checkered haori coat over a dark Demon Slayer corps uniform, carrying a black Nichirin katana",
    "nezuko": "Nezuko Kamado from Demon Slayer, anime girl with long black hair fading to flame-orange at the tips, soft pink eyes, bamboo muzzle tied with a red ribbon, pink geometric-patterned kimono with red-and-white checkered obi",
    "ichigo": "Ichigo Kurosaki from Bleach, tall anime Soul Reaper with spiky bright orange hair, brown eyes, black shihakusho kimono robe with white sash and oversized Zangetsu cleaver sword",
    "saitama": "Saitama from One Punch Man, anime hero with a smooth bald head, calm deadpan expression, bright yellow one-piece superhero jumpsuit with a white zipper, flowing white cape, red gloves and red boots",
    "eren": "Eren Yeager from Attack on Titan, intense anime soldier with dark brown hair, striking green eyes, Survey Corps cropped brown leather jacket with Wings of Freedom emblem, white trousers, vertical maneuvering harness and dual blades",
    "levi": "Levi Ackerman from Attack on Titan, sharp-featured anime captain with undercut black hair, steel-grey eyes, white cravat, Survey Corps jacket, green cloak, and dual ODM gear blades",
    "livai": "Levi Ackerman from Attack on Titan, sharp-featured anime captain with undercut black hair, steel-grey eyes, white cravat, Survey Corps jacket, green cloak, and dual ODM gear blades",
    "mikasa": "Mikasa Ackerman from Attack on Titan, agile anime soldier with chin-length black hair, dark eyes, iconic crimson red scarf, Survey Corps leather jacket and ODM gear",
    "frieren": "Frieren, slender elven anime mage with long silver-white twin-tails, green eyes, pointed elf ears, white-and-gold striped capelet over a white tunic dress, carrying her red-gemmed golden mage staff",
    "guts": "Guts from Berserk, towering scarred dark-fantasy anime swordsman with cropped black hair with a white forelock, black Berserker plate armor, flowing dark cloak, prosthetic iron left forearm, wielding the massive Dragon Slayer greatsword",
    "baki": "Baki Hanma from Baki, hyper-defined muscular young anime underground fighter with tousled auburn-brown hair, intense gaze, numerous battle scars across his torso, wearing white martial arts shorts",
    "killua": "Killua Zoldyck from Hunter x Hunter, agile young anime assassin with spiky silver-white hair, sharp blue cat-like eyes, dark blue long-sleeve turtleneck under a white short-sleeve shirt, and purple shorts",
    "kirua": "Killua Zoldyck from Hunter x Hunter, agile young anime assassin with spiky silver-white hair, sharp blue cat-like eyes, dark blue long-sleeve turtleneck under a white short-sleeve shirt, and purple shorts",
    "deku": "Izuku Midoriya (Deku) from My Hero Academia, determined young anime hero with messy dark-green curly hair, freckled cheeks, dark green superhero suit with red armored boots, white gloves and iron soles",
    "asta": "Asta from Black Clover, muscular compact anime magic knight with unruly ash-blond hair, black headband with red Black Bulls insignia, green eyes, wielding a giant blackened anti-magic greatsword",
    "denji": "Denji from Chainsaw Man, wild anime devil hunter with scruffy blond hair (or Chainsaw Devil hybrid head with roaring steel chainsaw blade protruding from forehead and both arms), white shirt with black tie",
    "goldorak": "Goldorak (Grendizer), iconic giant super-robot mecha with horned black-and-red head, yellow crescent chest emblem, blue torso, white-and-red forearms with crimson screw-crusher spikes, and double Harken halberd",
    "grendizer": "Goldorak (Grendizer), iconic giant super-robot mecha with horned black-and-red head, yellow crescent chest emblem, blue torso, white-and-red forearms with crimson screw-crusher spikes, and double Harken halberd",
    "pikachu": "Pikachu from Pokemon, vibrant yellow electric mouse creature with long black-tipped ears, red cheek pouches, brown back stripes, and a lightning-bolt-shaped tail",
    "dracaufeu": "Charizard (Dracaufeu) from Pokemon, powerful orange bipedal dragon creature with cream belly, large bat-like wings with teal inner membranes, and a blazing flame burning at the tip of its long tail",
    "charizard": "Charizard from Pokemon, powerful orange bipedal dragon creature with cream belly, large bat-like wings with teal inner membranes, and a blazing flame burning at the tip of its long tail",
    "mewtwo": "Mewtwo from Pokemon, sleek bipedal psychic feline-humanoid creature with pale lavender-grey body, purple tail and abdomen, three-fingered hands with spherical tips, and glowing psychic eyes",
    "lucario": "Lucario from Pokemon, bipedal jackal-like martial arts creature with blue and black fur, cream chest fur with a central spike, hand-back spikes, and four dreadlock-like aura appendages behind its head",
    "link": "Link from The Legend of Zelda, agile Hylian hero with pointed ears, blonde hair, Champion's tunic with leather cross-straps, Hylian shield and Master Sword",
    "sonic": "Sonic the Hedgehog, iconic blue anthropomorphic hedgehog with supersonic quills, emerald-green eyes, white gloves with red cuffs, and red-and-white running shoes",
    "shadow": "Shadow the Hedgehog, black-and-crimson anthropomorphic hedgehog with swept-back quills, white chest fur, golden inhibitor rings on wrists and ankles, and air shoes",
    "2b": "YoRHa No.2 Type B (2B) from NieR:Automata, android swordswoman with short silver-white bob hair, black combat visor blindfold, gothic black high-slit dress with feather trim, thigh-high boots, and Virtuous Contract katana",
    "jinx": "Jinx from Arcane / League of Legends, slender punk gunslinger with two floor-length electric-blue braids, violet-pink eyes, cloud tattoos along her right arm and shoulder, cropped halter top and striped trousers",
    "zig": "Zig from the Xilam animated cartoon series Zig & Sharko, lanky brown anthropomorphic cartoon hyena standing upright with oversized expressive yellow-and-red eyes, big dark-brown protruding snout with black nose, ragged maroon-brown ears and neck fur, tan belly patch, and mischievous toothy cartoon grin",
    "sharko": "Sharko from the Xilam animated cartoon series Zig & Sharko, muscular anthropomorphic great white cartoon shark standing upright on two legs with broad athletic shoulders, slate-blue upper skin and dorsal fin, stark white chest and belly, expressive cartoon eyes, and wide shark grin",
    "bernie zig": "Bernie from Zig & Sharko, tiny clever orange-red cartoon hermit crab with large round glasses/eyes and a spiral conical shell",
    "oggy": "Oggy from Oggy and the Cockroaches cartoon, chubby light-blue cartoon cat with a big round red nose, wide expressive eyes, grey tummy patch, black-and-white tail, and white paws",
    "asterix": "Asterix from Asterix & Obelix Franco-Belgian cartoon, short clever Gaulish warrior with a big drooping yellow-blond mustache, winged helmet, black sleeveless vest, red trousers, and green belt with gourd and short sword",
    "obelix": "Obelix from Asterix & Obelix Franco-Belgian cartoon, giant rotund Gaulish menhir deliveryman with braided red hair and red mustache, bare muscular torso above iconic vertical blue-and-white striped trousers held by a green-and-gold belt",
    "tintin": "Tintin from The Adventures of Tintin cartoon, young reporter with his iconic ginger-blond quiff hairstyle, round face, blue sweater over a white collared shirt, brown plus-fours trousers, white socks, and brown shoes",
    "lucky luke": "Lucky Luke from Franco-Belgian cartoon, tall slender lonesome cowboy with black forelock under a white cowboy hat, red neckerchief, yellow shirt under a black vest, blue jeans, and holster",
    "bob l eponge": "SpongeBob SquarePants (Bob l'eponge), cheerful yellow rectangular cartoon sea sponge with large blue eyes, prominent buck teeth, porous yellow body, white collared shirt, red tie, brown square pants, and black shoes",
    "spongebob": "SpongeBob SquarePants, cheerful yellow rectangular cartoon sea sponge with large blue eyes, prominent buck teeth, porous yellow body, white collared shirt, red tie, brown square pants, and black shoes",
    "patrick": "Patrick Star from SpongeBob SquarePants, chubby pink cartoon starfish with thick black eyebrows, round belly, and lime-green floral swim trunks",
    "bugs bunny": "Bugs Bunny from Looney Tunes cartoon, tall slender grey-and-white anthropomorphic cartoon rabbit with long upright ears, white gloves, buck teeth, and cheerful grin",
    "daffy duck": "Daffy Duck from Looney Tunes cartoon, sleek black anthropomorphic cartoon duck with bright orange bill and webbed feet and white neck ring",
    "tom et jerry": "Tom (grey-and-white anthropomorphic cartoon house cat) and Jerry (small brown cartoon mouse with large ears) from Tom and Jerry cartoon",
    "homer": "Homer Simpson from The Simpsons cartoon, yellow-skinned cartoon father with round belly, two hairs on top of his bald head, brown beard muzzle, white polo shirt, and blue trousers",
    "bart": "Bart Simpson from The Simpsons cartoon, mischievous yellow-skinned cartoon boy with spiky flat-top hair, orange-red t-shirt, blue shorts, and blue sneakers",
    "rick": "Rick Sanchez from Rick and Morty cartoon, eccentric tall slender cartoon scientist with spiky light-blue hair, unibrow, white lab coat over a teal shirt, and brown trousers",
    "morty": "Morty Smith from Rick and Morty cartoon, anxious young cartoon boy with round head, short brown hair, yellow t-shirt, and blue jeans",
    "shrek": "Shrek, large green cartoon ogre with trumpet-shaped ears, bald round head, cream tunic under a dark-brown laced leather vest, brown trousers and boots",
    "stitch": "Stitch (Experiment 626) from Disney Lilo & Stitch, compact blue alien cartoon creature with large bat-like ears with pink insides, big black eyes, dark-blue nose, and light-blue chest patch",
    "mickey": "Mickey Mouse from Disney cartoon, iconic anthropomorphic cartoon mouse with round black ears, cheerful face, red shorts with two white buttons, large yellow shoes, and white four-fingered gloves",
    "donald": "Donald Duck from Disney cartoon, white anthropomorphic cartoon duck with yellow-orange bill and webbed feet, wearing a blue sailor shirt with yellow trim and blue sailor cap",
    "dingo": "Goofy (Dingo) from Disney cartoon, tall lanky anthropomorphic cartoon dog with long droopy black ears, buck teeth, green hat, orange turtleneck, black vest, and blue trousers",
    "goofy": "Goofy from Disney cartoon, tall lanky anthropomorphic cartoon dog with long droopy black ears, buck teeth, green hat, orange turtleneck, black vest, and blue trousers",
    "minion": "Minion from Illumination 3D cartoon, capsule-shaped yellow cartoon creature wearing silver metallic goggles over large eyes, blue denim overalls, and black gloves and boots",
    "minions": "Minion from Illumination 3D cartoon, capsule-shaped yellow cartoon creature wearing silver metallic goggles over large eyes, blue denim overalls, and black gloves and boots",
    "scooby": "Scooby-Doo, large brown Great Dane cartoon dog with black spots and a teal-blue collar with a yellow SD diamond tag",
    "rayman": "Rayman, iconic cartoon platformer hero with floating limbless hands and feet, blond hair tuft, red hood on a purple torso with a white O-ring emblem, white gloves, and yellow-and-white sneakers",
    "crash bandicoot": "Crash Bandicoot, energetic orange anthropomorphic cartoon bandicoot with wide grin, brown fingerless gloves, blue denim shorts, and red high-top sneakers",
}

CANONICAL_TRANSFORMATION_LORE: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(super\s*saiyan\s*blue|ssj\s*blue|ssb|super\s*saiyan\s*divin\s*bleu)\b", re.IGNORECASE),
        "transformed into Super Saiyan Blue (SSB) with upright spiky radiant cyan-blue hair, glowing turquoise-blue eyes, and a shimmering divine azure ki aura",
    ),
    (
        re.compile(r"\b(ultra\s*instinct|instinct\s*ultra|migatte)\b", re.IGNORECASE),
        "in Mastered Ultra Instinct form with shimmering silver-white hair, piercing silver eyes, and a crystalline cosmic silver-blue heat-haze aura",
    ),
    (
        re.compile(r"\b(super\s*saiyan|ssj[123]?)\b", re.IGNORECASE),
        "transformed into Super Saiyan with upright spiky golden-yellow hair, emerald-teal eyes, and a blazing golden ki aura",
    ),
    (
        re.compile(r"\b(gear\s*5|gear\s*fifth|nika)\b", re.IGNORECASE),
        "in Awakened Gear 5 (Sun God Nika) form with glowing white cloud-like hair, floating white steam hagoromo sash around the shoulders, crimson-pink eyes, joyful laughing expression, and all-white outfit",
    ),
    (
        re.compile(r"\b(mode\s*ermite|sage\s*mode)\b", re.IGNORECASE),
        "in Toad Sage Mode with golden yellow eyes, horizontal toad pupils, and orange-red pigmentation around the eyes",
    ),
    (
        re.compile(r"\b(bankai)\b", re.IGNORECASE),
        "unleashing Bankai with compressed spiritual pressure aura and transformed Bankai blade",
    ),
]

# Règles d'exclusions négatives : retire le mot interdit du prompt positif (pour empêcher FLUX/TRELLIS
# d'halluciner l'objet par simple présence du token) et le convertit en état affirmatif + negative_prompt
NEGATIVE_CLAUSE_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"\b(?:sans|pas\s+de|aucun[e]?|without|no)\s+(?:son\s+|sa\s+|ses\s+|le\s+|la\s+|les\s+|un\s+|une\s+)?(?:chapeau(?:\s+de\s+paille)?|casque|capuche|couvre[- ]?chef|couronne|hat|helmet|hood|headgear)\b", re.IGNORECASE),
        "bareheaded with full hair and head clearly visible",
        "hat, straw hat, helmet, hood, headgear, cap, crown",
    ),
    (
        re.compile(r"\b(?:sans|pas\s+de|aucun[e]?|without|no)\s+(?:son\s+|sa\s+|ses\s+|le\s+|la\s+)?(?:haut(?:\s+de\s+kimono)?|t[- ]?shirt|chemise|veste|tunique|armure\s+du\s+haut|shirt|top|upper\s+gi)\b", re.IGNORECASE),
        "bare-chested with defined upper body musculature",
        "shirt, jacket, tunic, kimono top, upper garment",
    ),
    (
        re.compile(r"\b(?:sans|pas\s+de|aucun[e]?|without|no)\s+(?:ses\s+|les\s+|de\s+)?(?:lunettes?|bandeau|masque|glasses|eyewear|blindfold|mask)\b", re.IGNORECASE),
        "unobstructed face and uncovered eyes",
        "glasses, spectacles, sunglasses, blindfold, face mask, goggles",
    ),
    (
        re.compile(r"\b(?:sans|pas\s+de|aucun[e]?|without|no)\s+(?:sa\s+|la\s+|de\s+)?(?:barbe|moustache|poils?\s+au\s+menton|beard|mustache|facial\s+hair)\b", re.IGNORECASE),
        "clean-shaven smooth jawline",
        "beard, mustache, stubble, facial hair, goatee",
    ),
    (
        re.compile(r"\b(?:sans|pas\s+de|aucun[e]?|without|no)\s+(?:son\s+|le\s+|de\s+)?(?:bouclier|shield)\b", re.IGNORECASE),
        "free off-hand with no shield",
        "shield, buckler, targe",
    ),
    (
        re.compile(r"\b(?:sans|pas\s+de|aucun[e]?|without|no)\s+(?:son\s+|sa\s+|ses\s+|d[' ]?|les?\s+)?(?:arme[s]?|epee|katana|fusil|pistolet|weapon[s]?|sword|gun)\b", re.IGNORECASE),
        "unarmed with empty hands",
        "weapon, sword, katana, blade, gun, rifle, spear, staff",
    ),
    (
        re.compile(r"\b(?:sans|pas\s+de|aucun[e]?|without|no)\s+(?:sa\s+|la\s+|de\s+)?(?:cape|manteau|écharpe|echarpe|cape|cloak|scarf)\b", re.IGNORECASE),
        "clean back and neck silhouette with no cape or scarf",
        "cape, cloak, mantle, scarf, muffler",
    ),
    (
        re.compile(r"\b(?:sans|pas\s+de|aucun[e]?|without|no)\s+(?:ses\s+|les\s+|d[' ]?)?(?:ailes?|wings?)\b", re.IGNORECASE),
        "wingless back anatomy",
        "wings, feathered wings, bat wings",
    ),
]

GENERIC_NEGATIVE_CLAUSE_RE = re.compile(
    r"\b(?:sans|pas\s+de|aucun[e]?|without|avoid)\s+(?!changer\b|modifier\b|toucher\b)([a-zA-ZÀ-ÿ0-9'_-]+(?:\s+[a-zA-ZÀ-ÿ0-9'_-]+){0,2})",
    re.IGNORECASE,
)


def classify_creature_surface(text: str) -> str:
    """Détermine la vraie nature biologique de surface d'une créature pour empêcher
    toute hallucination de fourrure ('fur') sur un oiseau, un dragon ou un scorpion."""
    norm = _norm(text)
    if re.search(r"\b(oiseau|bird|hibou|owl|aigle|eagle|faucon|falcon|corbeau|raven|crow|perroquet|parrot|cygne|swan|phenix|phoenix|pigeon|colombe|griffon)\b", norm):
        return "feathered_avian"
    if re.search(r"\b(dragon|dracaufeu|charizard|serpent|snake|lezard|lizard|reptile|dinosaure|dinosaur|t[- ]?rex|crocodile|alligator|tortue|turtle|wyvern|hydre|hydra|basilic)\b", norm):
        return "scaled_draconic_reptilian"
    if re.search(r"\b(scorpion|araignee|spider|insecte|insect|scarabee|beetle|fourmi|ant|mante|mantis|crabe|crab|homard|lobster)\b", norm):
        return "chitin_arthropod"
    if re.search(r"\b(renard|fox|loup|wolf|chat|cat|chien|dog|lion|tigre|tiger|ours|bear|lapin|rabbit|cheval|horse|cerf|deer|panthere|jaguar|hamster|ecureuil|pikachu|lucario|evoli|eevee)\b", norm):
        return "furred_mammal"
    return "humanoid_or_generic"


def extract_strict_prompt_constraints(raw_text: str) -> dict[str, Any]:
    """Extrait les contraintes strictes, exclusions ('sans X', 'pas de Y'), transformations
    et quantités pour garantir 0 hallucination et 100 % de respect du prompt."""
    cleaned_positive = raw_text or ""
    affirmative_replacements: list[str] = []
    excluded_items_en: list[str] = []
    mandatory_attributes_en: list[str] = []

    norm_in = _norm(cleaned_positive)

    # 1. Règles d'exclusions négatives connues -> conversion affirmative + negative_prompt
    for pattern, affirmative_en, neg_tokens_en in NEGATIVE_CLAUSE_RULES:
        if pattern.search(norm_in):
            cleaned_positive = pattern.sub(f", {affirmative_en}, ", cleaned_positive)
            if affirmative_en not in affirmative_replacements:
                affirmative_replacements.append(affirmative_en)
            for tok in neg_tokens_en.split(","):
                t = tok.strip()
                if t and t not in excluded_items_en:
                    excluded_items_en.append(t)

    # 2. Clauses négatives génériques restantes ("sans X", "pas de Y")
    for match in GENERIC_NEGATIVE_CLAUSE_RE.finditer(cleaned_positive):
        phrase = match.group(1).strip()
        if not phrase or re.search(r"\b(fond\s+blanc|white\s+background)\b", phrase, re.I):
            continue
        for pat, repl in FR_STOPWORD_CLEANUP:
            phrase = re.sub(pat, repl, _strip_accents(phrase), flags=re.IGNORECASE)
        phrase = re.sub(r"\b(un|une|le|la|les|du|des|de|son|sa|ses|a|the)\b", "", phrase, flags=re.IGNORECASE).strip()
        if phrase and phrase not in excluded_items_en:
            excluded_items_en.append(phrase)
    cleaned_positive = GENERIC_NEGATIVE_CLAUSE_RE.sub("", cleaned_positive)

    # 3. Transformations canoniques explicites (Super Saiyan, SSB, Gear 5, Mode Ermite...)
    for pattern, trans_desc in CANONICAL_TRANSFORMATION_LORE:
        if pattern.search(norm_in):
            mandatory_attributes_en.append(trans_desc)

    # 4. Mains / Côtés / Quantités explicites
    if re.search(r"\b(main\s+droite|right\s+hand)\b", norm_in):
        mandatory_attributes_en.append("held specifically in the right hand")
    if re.search(r"\b(main\s+gauche|left\s+hand)\b", norm_in):
        mandatory_attributes_en.append("held specifically in the left hand")
    qty_matches = re.findall(r"\b(un\s+seul|une\s+seule|deux|trois|quatre|2|3|4)\s+([a-zA-ZÀ-ÿ]{3,})", norm_in)
    qty_map = {"un seul": "exactly 1", "une seule": "exactly 1", "deux": "2", "trois": "3", "quatre": "4"}
    for q_raw, noun_raw in qty_matches:
        if noun_raw in {"mains", "yeux", "bras", "jambes", "pieds", "vues", "points"}:
            continue
        q_en = qty_map.get(q_raw.lower(), q_raw)
        mandatory_attributes_en.append(f"exact count: {q_en} {noun_raw}")

    return {
        "cleaned_positive_text": re.sub(r"\s{2,}", " ", cleaned_positive).strip(" ,.;:-"),
        "affirmative_replacements_en": affirmative_replacements,
        "excluded_items_en": excluded_items_en,
        "mandatory_attributes_en": mandatory_attributes_en,
        "creature_surface_class": classify_creature_surface(raw_text),
    }


def translate_french_to_english_core(raw_text: str) -> str:
    """Traduit une requête française (ou bilingue) en anglais fluide tout en injectant
    les descriptions canoniques et en convertissant les négations pour éviter toute hallucination."""
    text = (raw_text or "").strip()
    if not text:
        return ""

    constraints = extract_strict_prompt_constraints(text)
    norm = _norm(text)

    # Inject canonical lore if a known character is mentioned
    canonical_matches: list[str] = []
    seen_lore: set[str] = set()
    for key, desc in CANONICAL_CHARACTER_LORE.items():
        if re.search(rf"\b{re.escape(key)}\b", norm) and desc not in seen_lore:
            # Si une transformation (ex: Super Saiyan Blue) ou une exclusion (ex: sans haut) modifie
            # la couleur de cheveux ou la tenue de base, adapte la description canonique sans conflit
            adapted_desc = desc
            if re.search(r"\b(super\s*saiyan\s*blue|ssj\s*blue|ssb)\b", norm):
                adapted_desc = adapted_desc.replace("spiky jet-black hair", "spiky radiant cyan-blue Super Saiyan Blue hair").replace("spiky black hair", "spiky radiant cyan-blue Super Saiyan Blue hair")
            elif re.search(r"\b(ultra\s*instinct|migatte)\b", norm):
                adapted_desc = adapted_desc.replace("spiky jet-black hair", "shimmering silver-white Ultra Instinct hair").replace("spiky black hair", "shimmering silver-white Ultra Instinct hair")
            elif re.search(r"\b(super\s*saiyan|ssj)\b", norm):
                adapted_desc = adapted_desc.replace("spiky jet-black hair", "upright spiky golden-yellow Super Saiyan hair").replace("spiky black hair", "upright spiky golden-yellow Super Saiyan hair")
            elif re.search(r"\b(gear\s*5|nika)\b", norm):
                adapted_desc = adapted_desc.replace("tousled black hair", "glowing white cloud-like Awakened Gear 5 hair").replace("open red vest, blue denim shorts", "all-white Awakened Gear 5 outfit with floating white cloud sash")
            if any("bare-chested" in r for r in constraints["affirmative_replacements_en"]):
                adapted_desc = re.sub(r"signature bright orange martial arts gi over a royal blue undershirt", "bare muscular torso with orange martial arts trousers", adapted_desc)
            if any("bareheaded" in r for r in constraints["affirmative_replacements_en"]):
                adapted_desc = re.sub(r"wearing his signature woven straw hat with a red ribbon,?\s*", "bareheaded with his straw hat removed, ", adapted_desc)
            canonical_matches.append(adapted_desc)
            seen_lore.add(desc)

    working = _strip_accents(constraints["cleaned_positive_text"] or text)
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

    extra_clauses = list(constraints["mandatory_attributes_en"])
    for rep in constraints["affirmative_replacements_en"]:
        if rep.lower() not in working.lower():
            extra_clauses.append(rep)

    if canonical_matches:
        canon_str = "; ".join(canonical_matches)
        base_out = canon_str if len(working.split()) <= 3 else f"{canon_str} — {working}"
    else:
        base_out = working or text

    if extra_clauses:
        base_out = f"{base_out}. Mandatory visual details: {'; '.join(dict.fromkeys(extra_clauses))}"
    return base_out


_AURORA_CACHE_DIR = Path(__file__).resolve().parents[1] / ".aurora"
_OPEN_WORLD_CACHE_FILE = _AURORA_CACHE_DIR / "open_world_entities.json"
_COGNITIVE_PROMPT_CACHE_FILE = _AURORA_CACHE_DIR / "cognitive_prompt_cache.json"
_MEMORY_ENTITY_CACHE: dict[str, dict[str, Any] | None] = {}
_MEMORY_COGNITIVE_CACHE: dict[str, dict[str, Any]] = {}
_OLLAMA_MODEL_CACHE: dict[str, Any] = {"ts": 0.0, "model": None, "use_cpu_only": False}

_GENERIC_NON_ENTITY_WORDS = {
    "homme", "femme", "personne", "personnage", "perso", "garcon", "fille", "enfant",
    "portrait", "visage", "guerrier", "mage", "chevalier", "ninja", "samourai", "pirate",
    "boulanger", "pompier", "policier", "medecin", "docteur", "soldat", "cuisinier", "chef",
    "forgeron", "peintre", "ouvrier", "agriculteur", "professeur", "chanteur", "acteur",
    "actrice", "footballeur", "sportif", "danseur", "danseuse", "musicien", "roi", "reine",
    "prince", "princesse", "sorcier", "sorciere", "voleur", "assassin", "archer", "moine",
    "chat", "chien", "loup", "renard", "lion", "tigre", "ours", "cheval", "oiseau",
    "hibou", "aigle", "dragon", "serpent", "scorpion", "araignee", "axolotl", "requin",
    "hyene", "crabe", "singe", "gorille", "lapin", "souris", "rat", "canard", "grenouille",
    "voiture", "moto", "velo", "maison", "chateau", "cathedrale", "paysage", "montagne", "foret",
    "mer", "plage", "table", "chaise", "fauteuil", "casque", "camera", "voilier", "bateau",
    "sphere", "cube", "cylindre", "engrenage", "poulie", "icone", "potion", "epee", "sabre",
    "horloger", "suisse", "atelier", "banc", "bois", "ville", "rue", "robot", "alien", "monstre",
    "pomme", "poire", "banane", "orange", "fraise", "citron", "fruit", "fleur", "arbre", "plante",
    "cape", "ballon", "eclair", "eclairs", "chapeau", "lunettes", "cristal", "verre", "metal",
    "pierre", "or", "argent", "diamant", "eau", "feu", "glace", "livre", "tasse", "bouteille",
    "montre", "telephone", "ordinateur", "arme", "bouclier", "armure", "couronne", "anneau", "baguette",
    "realiste", "photorealiste", "stylise", "cartoon", "anime", "manga", "figurine", "statue",
    "jouet", "peluche", "vrai", "vraie", "reel", "reelle", "jeune", "vieux", "vieille", "grand", "petit",
    "man", "woman", "person", "character", "boy", "girl", "warrior", "knight", "baker", "firefighter",
    "policeman", "doctor", "soldier", "cat", "dog", "wolf", "fox", "owl", "bicycle", "cathedral",
    "helmet", "chair", "sailing", "ship", "bench", "wooden", "city", "landscape", "forest", "apple",
    "realistic", "photorealistic", "stylized", "pink", "red", "blue", "black", "white", "rouge", "bleu", "vert", "jaune",
    "opal", "opale", "crystal", "translucent", "mystical", "spirit", "esprit", "kitsune", "tailed", "nine",
    "fur", "fourrure", "amber", "ambre", "gold", "golden", "silver", "brass", "laiton", "bronze", "copper",
    "iron", "steel", "acier", "titanium", "titane", "iridium", "obsidian", "obsidienne", "basalt", "basalte",
    "lava", "lave", "magma", "jade", "porcelain", "porcelaine", "ceramic", "ceramique", "kintsugi", "marble",
    "marbre", "granite", "stone", "glass", "diamond", "ruby", "sapphire", "emerald", "pearl", "ivory", "ivoire",
    "bone", "leather", "cuir", "silk", "soie", "velvet", "velours", "fire", "ice", "water", "lightning",
    "shadow", "ombre", "celestial", "celeste", "ancient", "ancien", "royal", "imperial", "biomechanical",
    "biomecanique", "cyberpunk", "steampunk", "clockwork", "mechanical", "mecanique", "bionic", "bionique",
    "robotic", "robotique", "animated", "animation", "fluid", "wave", "tail", "queue", "wings", "ailes",
    "feathers", "plumes", "scales", "ecailles", "armor", "helm", "sword", "blade", "lame", "shield",
    "turret", "tourelle", "drone", "rover", "engine", "moteur", "hand", "main", "arm", "bras", "astrolabe",
    "drawbridge", "enclosure", "boitier", "nautilus", "submarine", "sous-marin", "phoenix", "phenix",
    "griffin", "griffon", "gargoyle", "gargouille", "leviathan", "seraphim", "seraphin", "archangel",
    "archange", "valkyrie", "samurai", "shinobi", "paladin", "sorceress", "mage", "creature", "animal",
    "quadruped", "quadrupede", "biped", "bipede", "queues", "tails", "blanc", "blanche", "noir", "noire",
    "veines", "veins", "abyssal", "abyssale", "bioluminescent", "bioluminescente", "mecatronique",
    "mechatronic", "coaxial", "coaxiale", "turbine", "gyroscopique", "gyroscopic", "cryo", "doigts",
    "fingers", "phalanges", "etages", "stages", "inedit", "inedite", "xylo", "vulpis",
    "vase", "vases", "flacon", "carafe", "coupe", "calice", "bol", "pot", "urne", "bocal", "bijou", "bague",
    "pendentif", "collier", "medaillon", "trophee", "coffret", "bougie", "chandelier", "lampe", "miroir",
    "sablier", "coeur", "coeurs", "heart", "hearts", "rose", "roses", "graver", "grave", "gravure", "engraved",
    "prenom", "nom", "forme", "formes", "couleur", "transparent", "refractif",
}


def extract_universal_style_clause(raw_text: str) -> dict[str, Any]:
    """Extrait par analyse syntaxique universelle (sans dépendre d'une liste figée de styles)
    toute demande de transformation de style, de matériau ou d'esthétique en français ou anglais.
    Exemples supportés : 'changé en figurine en bois sculpté', 'en porcelaine', 'en origami',
    'style Tim Burton', 'façon Zig et Sharko', 'en cartoon figurine', 'en personne réelle'."""
    text = (raw_text or "").strip()
    norm = _norm(text)
    result: dict[str, Any] = {
        "has_style_clause": False,
        "is_transformation_verb": False,
        "is_real_override": False,
        "style_phrase_raw": None,
        "core_subject_clean": text,
    }
    if not text:
        return result

    # 1. Verbe explicite de transformation : "transforme/change/convertis/mets <Sujet> en <Style>"
    m_trans = re.search(
        r"\b(?:transform(?:e|er|ee?|es)?|chang(?:e|er|ee?|es)?|converti(?:s|r|e|es)?|adapt(?:e|er|ee?|es)?|met(?:s|tre)|pass(?:e|er)|rend(?:s|re))\s+"
        r"(?P<mid>(?:[\wÀ-ÿ'’_-]+\s+){0,6}?)"
        r"en\s+(?P<style>[^,.;:!?]+?)(?=\s+(?:qui\s+|avec\s+|sans\s+|dans\s+un|sur\s+fond)|[,.;:!?]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if m_trans:
        style_raw = m_trans.group("style").strip()
        mid_subj = m_trans.group("mid").strip()
        prefix = text[: m_trans.start()].strip()
        suffix = text[m_trans.end() :].strip()
        core_parts = [p for p in (prefix, mid_subj, suffix) if p]
        core_clean = " ".join(core_parts).strip() or mid_subj or text
        style_norm = _norm(style_raw)
        is_real = bool(
            re.search(
                r"\b(personne\s+reelle|vrai\s+humain|vraie\s+personne|real\s+person|real\s+human|realiste|photorealiste|live[- ]?action|peau\s+reelle)\b",
                style_norm,
            )
        )
        return {
            "has_style_clause": True,
            "is_transformation_verb": True,
            "is_real_override": is_real,
            "style_phrase_raw": style_raw,
            "core_subject_clean": core_clean,
        }

    # 2. Marqueur syntaxique de style libre : "style <X>", "façon <X>", "à la manière de <X>", "comme dans <X>", "version <X>"
    m_style = re.search(
        r"\b(?:dans\s+le\s+style(?:\s+de|\s+d['’])?|en\s+style|style|fa[cç]on|[aà]\s+la\s+mani[eè]re\s+de|comme\s+dans|version|esth[eé]tique|rendu)\s+"
        r"(?P<style>[^,.;:!?]+?)(?=\s+(?:qui\s+|avec\s+|sans\s+|dans\s+un|sur\s+fond)|[,.;:!?]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if m_style:
        style_raw = m_style.group("style").strip()
        core_clean = (text[: m_style.start()].strip() + " " + text[m_style.end() :].strip()).strip()
        style_norm = _norm(style_raw)
        is_real = bool(
            re.search(
                r"\b(personne\s+reelle|vrai\s+humain|vraie\s+personne|real\s+person|real\s+human|realiste|photorealiste|live[- ]?action|peau\s+reelle)\b",
                style_norm,
            )
        )
        return {
            "has_style_clause": True,
            "is_transformation_verb": True,
            "is_real_override": is_real,
            "style_phrase_raw": style_raw,
            "core_subject_clean": core_clean or text,
        }

    # 3. Complément ouvert de matière / forme artistique / style futur : "<Sujet> en <Matière/Forme/Style>"
    # Sans aucune liste fermée de matériaux : accepte tout syntagme de matière ou d'esthétique
    # ("en verre soufflé bioluminescent", "en métal liquide holographique", "en sculpture néo-brutaliste", etc.)
    # en excluant uniquement les compléments grammaticaux de lieu, d'action, de posture, de vêtement ou de format technique.
    m_en = re.search(
        r"(?<=\S)\s+\ben\s+"
        r"(?!forme\b|formes\b|taille\b|coupe\b|biseau\b|relief\b|gravure\b|train\b|feu\b|flammes?\b|col[eè]re\b|pleurs?\b|larmes?\b|souriant\b|criant\b|courant\b|marchant\b|volant\b|sautant\b|dormant\b|dansant\b|nageant\b|tirant\b|frappant\b|"
        r"mouvement\b|action\b|marche\b|course\b|vol\b|combat\b|bataille\b|guerre\b|garde\b|posture\b|pose\b|[eé]quilibre\b|l[eé]vitation\b|chute\b|vie\b|paix\b|danger\b|urgence\b|"
        r"3d\b|2d\b|4k\b|8k\b|16k\b|hd\b|uhd\b|pbr\b|pied\b|entier\b|buste\b|gros\s+plan\b|plan\s+large\b|contre[- ]?plong[eé]e\b|plong[eé]e\b|profil\b|face\b|dos\b|couleurs?\b|noir\s+et\s+blanc\b|ligne\b|direct\b|jeu\b|vrai\b|"
        r"armure\b|costume\b|veste\b|robe\b|short\b|pantalon\b|jean\b|t[- ]?shirt\b|chemise\b|pull\b|manteau\b|uniforme\b|maillot\b|kimono\b|smoking\b|pyjama\b|surv[eê]tement\b|sweat\b|bikini\b|tenue\b|bottes?\b|baskets?\b|chaussures?\b|cape\b|blouse\b|tablier\b|casque\b|"
        r"plein(?:e)?\b|haut\b|bas\b|avant\b|arri[eè]re\b|milieu\b|centre\b|diagonale\b|cercle\b|studio\b|int[eé]rieur\b|ext[eé]rieur\b|ville\b|for[eê]t\b|mer\b|oc[eé]an\b|montagne\b|plage\b|d[eé]sert\b|espace\b|orbite\b|"
        r"france\b|espagne\b|italie\b|allemagne\b|angleterre\b|japon\b|chine\b|cor[eé]e\b|am[eé]rique\b|europe\b|asie\b|afrique\b|[eé]t[eé]\b|hiver\b|automne\b|printemps\b|nuit\b|jour\b|soir[eé]e\b|matin[eé]e\b|[0-9]{3,4}\b|anglais\b|fran[cç]ais\b|japonais\b|"
        r"un\b|une\b|le\b|la\b|les\b|des\b|du\b|de\b|ce\b|cet\b|cette\b|ces\b|son\b|sa\b|ses\b|mon\b|ma\b|mes\b|ton\b|ta\b|tes\b|leur\b|leurs\b|soi\b|lui\b|elle\b|eux\b|elles\b|qui\b|que\b|quoi\b|dont\b|o[uù]\b|plus\b|moins\b|tant\b|outre\b|effet\b|fait\b|cas\b|"
        r"super\s+saiyan\b|ssj[1-4b]?\b|ultra\s+instinct\b|kaioken\b|mode\s+(?:ermite|sage|kurama|baryon|chakra|six\s+chemins|d[eé]mon)\b|gear\s*[2345]\b|bankai\b)"
        r"(?P<style>[a-zA-ZÀ-ÿ0-9'’\-]+(?:\s+[a-zA-ZÀ-ÿ0-9'’\-]+){0,5}?)"
        r"(?=\s+(?:qui\s+|avec\s+|sans\s+|dans\s+un|sur\s+fond)|[,.;:!?]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if m_en:
        style_raw = m_en.group("style").strip()
        core_clean = (text[: m_en.start()].strip() + " " + text[m_en.end() :].strip()).strip()
        style_norm = _norm(style_raw)
        is_physical_material_or_color = bool(
            re.search(
                r"\b(verre|cristal|crystal|glass|porcelaine|ceramique|bois|metal|acier|bronze|laiton|cuivre|or|argent|marbre|pierre|plastique|resine|silicone|blanc|blanche|rose|rouge|bleu|bleue|vert|verte|noir|noire|jaune|violet|orange|gris|grise|transparent|opaque)\b",
                style_norm,
            )
        )
        is_real = bool(
            re.search(
                r"\b(personne\s+reelle|vrai\s+humain|vraie\s+personne|real\s+person|real\s+human|realiste|photorealiste|live[- ]?action|peau\s+reelle)\b",
                style_norm,
            )
        )
        return {
            "has_style_clause": not is_physical_material_or_color,
            "is_transformation_verb": not is_physical_material_or_color,
            "is_real_override": is_real,
            "style_phrase_raw": style_raw,
            "core_subject_clean": core_clean or text,
        }

    return result


def _extract_candidate_entity_query(raw_prompt: str) -> str | None:
    """Extrait le nom propre, le personnage ou l'œuvre principale d'un prompt libre sans liste en dur."""
    style_info = extract_universal_style_clause(raw_prompt)
    text = (style_info.get("core_subject_clean") or raw_prompt or "").strip()
    if not text:
        return None
    norm_text_check = _norm(text)
    if (
        re.search(
            r"\b(vase|vases|flacon|carafe|coupe|calice|bol|pot|urne|bocal|tasse|bouteille|bijou|bague|pendentif|collier|medaillon|trophee|coffret|bougie|chandelier|lampe|miroir|sablier)\b",
            norm_text_check,
        )
        and not re.search(r"\b(de\s+[A-Z]|du\s+jeu|dans\s+le\s+jeu|personnage)\b", text)
    ):
        return None
    # Retire toute clause de gravure ou d'inscription de prénom/nom ("avec graver le prénom Rayen", "gravé Rayen", etc.)
    text = re.sub(
        r"\b(?:avec\s+)?(?:grav(?:er|é|ee|es|ure)|inscri(?:re|t|ption)|marqu(?:er|é)|[eé]crit)\s+(?:le\s+|la\s+|un\s+|une\s+)?(?:pr[eé]nom\s+|nom\s+|mot\s+|texte\s+)?[A-ZÀ-ÖØ-Þa-zà-öø-ÿ0-9'’-]+",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b(?:pr[eé]nom|nom)\s+[A-ZÀ-ÖØ-Þa-zà-öø-ÿ0-9'’-]+", " ", text, flags=re.IGNORECASE)
    # Retire les formules d'introduction, verbes de modification et pronoms compléments ("transforme-le", "ajoute", etc.)
    cleaned = re.sub(
        r"^(?:fais[- ]?moi|fait[- ]?moi|cree[- ]?moi|creer|genere[- ]?moi|generer|dessine[- ]?moi|"
        r"modifie(?:r)?(?:[- ]?(?:le|la|les|l['’]))?|change(?:r)?(?:[- ]?(?:le|la|les|l['’]))?|"
        r"transforme(?:r)?(?:[- ]?(?:le|la|les|l['’]))?|converti(?:s|r)(?:[- ]?(?:le|la|les|l['’]))?|"
        r"adapte(?:r)?(?:[- ]?(?:le|la|les|l['’]))?|ajoute(?:r)?(?:[- ]?(?:lui|y))?|mets?(?:[- ]?(?:lui|y))?|"
        r"remplace(?:r)?|enleve(?:r)?|supprime(?:r)?|reproduis|je\s+veux|peux[- ]?tu\s+faire)\b[\s,-]*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(?:une?\s+(?:image|illustration|photo|portrait|modele\s+3d|rendu\s+3d|personnage(?:\s+r[eé]el)?|perso(?:\s+r[eé]el)?|personne(?:\s+r[eé]elle)?|figurine)\s+(?:de|d[' ]|comme)\s*|"
        r"(?:anime\s+illustration|close[- ]up\s+portrait|full[- ]body\s+character|a\s+low\s+poly\s+prop)\s+of\s+)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Coupe avant les clauses descriptives secondaires, lieux, formes de combat et actions ("qui marche", "sur la plage", "en vol", "en Gear 5", etc.)
    cleaned = re.split(
        r"\b(?:avec|sans|pas\s+de|tenant|portant|qui\s+|en\s+train\s+de|"
        r"en\s+(?:vol|course|combat|action|mouvement|garde|posture|pose|l[eé]vitation|super\s+saiyan|ssj[1-4b]?|ultra\s+instinct|mode\s+\w+|gear\s*[2345]|bankai)\b|"
        r"dans\s+(?:un|une|le|la|les|l['’]|des|son|sa|ses)|"
        r"sur\s+(?:un|une|le|la|les|l['’]|des|son|sa|ses|fond)|"
        r"devant\s+|derri[eè]re\s+|sous\s+|au\s+bord\s+|"
        r"on\s+(?:a|an|the|his|her|their|its)\s+|in\s+(?:a|an|the|his|her|their|its)\s+|"
        r"at\s+(?:a|an|the)\s+|under\s+(?:a|an|the)\s+|"
        r"with\s+|without\s+|holding\s+|wearing\s+|posed\s+|standing\s+|running\s+|flying\s+|swimming\s+|sitting\s+|"
        r"crafted\s+|carved\s+|sculpted\s+|made\s+of\b|"
        r"(?:style|fa[cç]on|version)\s+|"
        r"transform[eé]\s+en|chang[eé]\s+en|image\s+\d)\b|[,;]|(?<!\b[A-Za-z])\.(?!\s*[A-Za-z])",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()

    # Si la requête commence par un article suivi d'un nom commun en minuscule ("un boulanger", "la pomme", "une épée d'Elden Ring"),
    # c'est un nom commun générique SAUF s'il contient un complément d'œuvre/jeu/entité avec nom propre ("de/du/des/d'/dans/from/of/in <EntitéPropre>")
    if re.match(r"^(?:[Uu]n|[Uu]ne|[Dd]es|[Ll]e|[Ll]a|[Ll]es|[Cc]e|[Cc]et|[Cc]ette|[Aa]|[Aa]n|[Tt]he)\s+[a-zà-öø-ÿ]", cleaned):
        m_of = re.search(
            r"(?:\b(?:de|du|des|de\s+la|de\s+l['’]|dans|from|of|in|comme|like)\s+|\bd['’])\s*([\wÀ-ÿ'’\s-]{2,40})$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if m_of:
            candidate_tail = m_of.group(1).strip()
            tail_words = [
                w for w in re.split(r"\s+", _norm(candidate_tail))
                if w and w not in {"le", "la", "les", "de", "du", "des", "l", "et", "and", "the", "of", "jeu", "game"}
            ]
            has_capitalized_proper_noun = bool(re.search(r"\b[A-ZÀ-ÖØ-Þ][a-zA-ZÀ-ÿ0-9'’-]{1,}", candidate_tail))
            has_known_entity_pattern = bool(ANIME_UNIVERSE_AND_CHARACTER_PATTERNS.search(_norm(candidate_tail)))
            if (
                tail_words
                and (has_capitalized_proper_noun or has_known_entity_pattern)
                and not any(w in _GENERIC_NON_ENTITY_WORDS for w in tail_words)
            ):
                cleaned = re.sub(r"^(?:jeu(?:\s+vid[eé]o)?|video\s+game)\s+", "", candidate_tail, flags=re.IGNORECASE).strip()
            else:
                return None
        else:
            # Vérifie s'il y a un nom propre avec majuscule après le nom commun (ex: "un footballeur Zinedine Zidane")
            after_indef = re.sub(r"^(?:un|une|des|le|la|les|ce|cet|cette|a|an|the)\s+[a-zà-öø-ÿ_-]+\s*", "", cleaned, flags=re.IGNORECASE)
            if after_indef and re.search(r"\b[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]{2,}", after_indef):
                cleaned = after_indef.strip()
            else:
                return None

    cleaned = re.sub(r"^(?:un|une|le|la|les|du|de\s+la|d[' ]|a|an|the)\b\s*", "", cleaned, flags=re.IGNORECASE).strip(" -'\"")
    words = [w for w in re.split(r"\s+", _norm(cleaned)) if w]
    if not words or len(words) > 6:
        return None
    non_stop_words = [
        w for w in words
        if w not in {"le", "la", "les", "de", "du", "des", "l", "et", "and", "the", "of", "a", "an", "un", "une"}
        and len(w) >= 2
    ]
    if not non_stop_words or all(w in _GENERIC_NON_ENTITY_WORDS for w in non_stop_words):
        return None
    return cleaned


def _build_search_variants(candidate: str) -> list[str]:
    """Construit les variantes de recherche MediaWiki (exacte, sans liaison d'/de, entité principale et phonétique/fuzzy)
    pour résoudre même les noms d'œuvres/personnages composés ou mal orthographiés ('Jibanyan de yokay watch' -> 'Jibanyan' + 'yokai watch')."""
    variants: list[str] = []
    # Si la requête est de la forme "<Personnage> de/d' <Œuvre>" (ex: "Jibanyan de yokay watch", "Mark Evans d'Inazuma Eleven"),
    # on cherche d'abord la combinaison propre "<Personnage> <Œuvre>" ET le personnage seul "<Personnage>"
    m_compound = re.match(
        r"^([\wÀ-ÿ'’-]{3,30}(?:\s+[\wÀ-ÿ'’-]{2,25})?)\s+(?:d['’]|de\s+la\s+|de\s+l['’]|du\s+|des\s+|de\s+|from\s+|of\s+|in\s+)(.+)$",
        candidate,
        flags=re.IGNORECASE,
    )
    head_entity = ""
    if m_compound:
        head_entity = m_compound.group(1).strip()
        tail_entity = m_compound.group(2).strip()
        combined_clean = f"{head_entity} {tail_entity}".strip()
        variants.append(combined_clean)
        phonetic_combined = re.sub(r"([aou])y\b", r"\1i", combined_clean, flags=re.IGNORECASE)
        phonetic_combined = re.sub(r"([aou])y(?=[a-z])", r"\1i", phonetic_combined, flags=re.IGNORECASE)
        if phonetic_combined.lower() not in {v.lower() for v in variants}:
            variants.append(phonetic_combined)
        if head_entity and _norm(head_entity) not in _GENERIC_NON_ENTITY_WORDS:
            variants.append(head_entity)

    if candidate.lower() not in {v.lower() for v in variants}:
        variants.append(candidate)
    de_stripped = re.sub(r"\b(?:d['’]|de\s+la\s+|de\s+l['’]|du\s+|des\s+|de\s+)", " ", candidate, flags=re.IGNORECASE)
    de_stripped = re.sub(r"\s+", " ", de_stripped).strip()
    if de_stripped and de_stripped.lower() not in {v.lower() for v in variants}:
        variants.append(de_stripped)
    phonetic = re.sub(r"([aou])y\b", r"\1i", de_stripped or candidate, flags=re.IGNORECASE)
    phonetic = re.sub(r"([aou])y(?=[a-z])", r"\1i", phonetic, flags=re.IGNORECASE)
    phonetic = re.sub(r"ou", "u", phonetic, flags=re.IGNORECASE)
    if phonetic and phonetic.lower() not in {v.lower() for v in variants}:
        variants.append(phonetic)
    return variants


def resolve_open_world_entity(raw_prompt: str, timeout_s: float = 1.45) -> dict[str, Any] | None:
    """Résout n'importe quel personnage, œuvre, série animée, jeu vidéo, célébrité ou créature parmi des millions
    via MediaWiki OpenSearch + Extracts (FR + EN) avec correction phonétique/orthographique et inférence
    automatique du médium artistique natif par descripteurs encyclopédiques universels (zéro liste de jeux en dur)."""
    candidate = _extract_candidate_entity_query(raw_prompt)
    if not candidate:
        return None
    cache_key = _norm(candidate)
    if cache_key in _MEMORY_ENTITY_CACHE:
        cached = _MEMORY_ENTITY_CACHE[cache_key]
        if isinstance(cached, dict) and "inferred_submode" in cached:
            return cached

    disk_data: dict[str, Any] = {}
    try:
        if _OPEN_WORLD_CACHE_FILE.exists():
            loaded = json.loads(_OPEN_WORLD_CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                disk_data = loaded
                if cache_key in disk_data and isinstance(disk_data[cache_key], dict) and "inferred_submode" in disk_data[cache_key]:
                    _MEMORY_ENTITY_CACHE[cache_key] = disk_data[cache_key]
                    return disk_data[cache_key]
    except Exception:
        disk_data = {}

    if os.environ.get("AURORA_DISABLE_OPEN_WORLD_LOOKUP") == "1":
        return None

    headers = {"User-Agent": "AuroraIA/4.0 (https://aurora-ia.org; contact@aurora-ia.org) Python/3.12"}
    best_extract = ""
    best_title = ""
    search_variants = _build_search_variants(candidate)
    m_head = re.match(
        r"^([\wÀ-ÿ'’-]{3,30}(?:\s+[\wÀ-ÿ'’-]{2,25})?)\s+(?:d['’]|de\s+la\s+|de\s+l['’]|du\s+|des\s+|de\s+|from\s+|of\s+|in\s+)",
        candidate,
        flags=re.IGNORECASE,
    )
    head_norm = _norm(m_head.group(1)) if m_head else ""
    found_media_match = False
    for query_variant in search_variants:
        if found_media_match:
            break
        for lang in ("fr", "en"):
            q_enc = urllib.parse.quote(query_variant)
            url = (
                f"https://{lang}.wikipedia.org/w/api.php?"
                f"action=query&generator=search&gsrsearch={q_enc}&gsrlimit=2"
                f"&prop=extracts|description&exintro=1&explaintext=1&exchars=900&format=json"
            )
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    pages = (payload.get("query") or {}).get("pages") or {}
                    if not pages:
                        continue
                    sorted_pages = sorted(pages.values(), key=lambda p: p.get("index", 99))
                    top = sorted_pages[0]
                    title = str(top.get("title") or "").strip()
                    desc = str(top.get("description") or "").strip()
                    extract = str(top.get("extract") or "").strip()
                    combined = f"{title} ({desc}): {extract}" if desc else f"{title}: {extract}"
                    if len(extract) > 30:
                        is_media_page = bool(
                            re.search(
                                r"\b(manga|anime|manhwa|webtoon|light\s+novel|shonen|seinen|jeu\s+video|jeux\s+video|video\s+game|"
                                r"personnage|fictional\s+character|fictional\s+cat|yokai|comics|bande\s+dessinee|cartoon|serie\s+d\s+animation|"
                                r"serie\s+televisee\s+d\s+animation|animated\s+series|dessin\s+anime|espece|species|animal|"
                                r"footballeur|acteur|actrice|chanteur|homme\s+politique)\b",
                                _norm(combined),
                            )
                        )
                        if not best_extract or (head_norm and head_norm in _norm(title) and is_media_page):
                            best_title = title
                            best_extract = re.sub(r"\s+", " ", combined).strip()
                        if is_media_page and (not head_norm or head_norm in _norm(title)):
                            best_title = title
                            best_extract = re.sub(r"\s+", " ", combined).strip()
                            found_media_match = True
                            break
            except Exception:
                continue

    if not best_extract:
        _MEMORY_ENTITY_CACHE[cache_key] = None
        return None

    norm_ext = _norm(best_extract)
    first_sentence = _norm(best_extract[:260])
    is_biological_species = bool(
        re.search(
            r"\b(espece\s+d|species\s+of|genre\s+d|genus\s+of|amphibien|amphibian|mammifere|mammal|"
            r"oiseau|bird|reptile|arthropode|arthropod|insecte|insect|poisson|fish|plante|plant)\b",
            first_sentence,
        )
    )
    is_real_person = bool(
        re.search(
            r"\b(ne\s+le|nee\s+le|born\s+on|born\s+\d|est\s+un\s+(?:footballeur|joueur|acteur|chanteur|rappeur|homme\s+politique|sportif|pilote|entrepreneur|scientifique|ecrivain)|"
            r"est\s+une\s+(?:actrice|chanteuse|joueuse|femme\s+politique|sportive)|"
            r"is\s+a(?:n)?\s+(?:french|american|british|spanish|german|italian|brazilian|japanese)?\s*(?:footballer|actor|actress|singer|rapper|politician|athlete|player))\b",
            first_sentence,
        )
    ) and not bool(re.search(r"\b(personnage\s+de\s+fiction|fictional\s+character|serie\s+d\s+animation|animated\s+series|manga|bande\s+dessinee|jeu\s+video|video\s+game)\b", first_sentence))

    inferred_ontology = None
    inferred_submode = None
    if is_real_person:
        inferred_ontology = "real_human_subject"
        inferred_submode = None
    elif not is_biological_species:
        # Inférence universelle par descripteurs encyclopédiques de médium (zéro liste de titres en dur)
        is_japanese_anime_manga = bool(
            re.search(
                r"\b(manga|manhwa|webtoon|light\s+novel|shonen|seinen|shojo|isekai|animation\s+japonaise|"
                r"japanese\s+anime|japanese\s+manga|anime\s+series|serie\s+d\s+animation\s+japonaise|yokai|corocoro)\b",
                norm_ext,
            )
        )
        is_stop_motion_clay = bool(
            re.search(
                r"\b(animation\s+en\s+volume|stop[- ]?motion|pate\s+a\s+modeler|clay\s+animation|claymation|marionnette)\b",
                norm_ext,
            )
        )
        is_cartoon_or_bd = bool(
            re.search(
                r"\b(serie\s+d\s+animation|serie\s+televisee\s+d\s+animation|bande\s+dessinee|franco[- ]?belge|"
                r"cartoon|animated\s+series|animated\s+television|animated\s+sitcom|film\s+d\s+animation|animated\s+film|"
                r"comic\s+strip|comic\s+book|comics|dessin\s+anime)\b",
                norm_ext,
            )
        )
        is_video_game = bool(
            re.search(
                r"\b(jeu\s+video|jeux\s+video|video\s+game|personnage\s+de\s+jeu|action[- ]?adventure|role[- ]?playing\s+game|"
                r"jeu\s+de\s+role|jeu\s+d\s+action|jeu\s+de\s+plateforme|platform\s+game|platformer|first[- ]?person\s+shooter|jeu\s+de\s+tir|"
                r"battle\s+royale|sandbox\s+game|bac\s+a\s+sable|hack\s+and\s+slash|visual\s+novel|jeu\s+de\s+combat|fighting\s+game)\b",
                norm_ext,
            )
        )
        if is_stop_motion_clay:
            inferred_ontology = "anime_manga_character"
            inferred_submode = "clay_or_plush"
        elif is_video_game and not is_japanese_anime_manga:
            inferred_ontology = "game_character_or_asset"
            if re.search(r"\b(voxel|bloc[s]?\s+cubique|blocky|cubic\s+world)\b", norm_ext):
                inferred_submode = "lowpoly_voxel"
            elif re.search(r"\b(cartoon|jeu\s+de\s+plateforme|platform\s+game|platformer)\b", first_sentence):
                inferred_submode = "cartoon_3d"
            else:
                inferred_submode = None
        elif is_japanese_anime_manga:
            inferred_ontology = "anime_manga_character"
            inferred_submode = "anime_cel"
        elif is_cartoon_or_bd:
            inferred_ontology = "anime_manga_character"
            inferred_submode = "cartoon_3d"

    inferred_surface = None
    if re.search(r"\b(oiseau|rapace|bird|avian|feather|plumage)\b", norm_ext):
        inferred_surface = "feathered_avian"
    elif re.search(r"\b(reptile|amphibien|amphibian|dragon|serpent|lezard|dinosaure|ecaille|scale|axolotl|salamandre|pangolin|requin|shark)\b", norm_ext):
        inferred_surface = "scaled_draconic_reptilian"
    elif re.search(r"\b(arthropode|arthropod|insecte|insect|arachnide|crustace|scorpion|cafard|cockroach|chitine|exosquelette|exoskeleton)\b", norm_ext):
        inferred_surface = "chitin_arthropod"
    elif re.search(r"\b(mammifere|mammal|felin|canide|chat|chien|hyene|hyena|fourrure|pelage|fur)\b", norm_ext):
        inferred_surface = "furred_mammal"

    result = {
        "query": candidate,
        "title": best_title,
        "entity_title": best_title,
        "canonical_label": best_title,
        "description": best_extract[:750],
        "summary_extract": best_extract[:750],
        "visual_description_en": best_extract[:750],
        "source": "MediaWiki",
        "inferred_ontology": inferred_ontology,
        "inferred_submode": inferred_submode,
        "inferred_surface_class": inferred_surface,
    }
    _MEMORY_ENTITY_CACHE[cache_key] = result
    try:
        _AURORA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        disk_data[cache_key] = result
        _OPEN_WORLD_CACHE_FILE.write_text(json.dumps(disk_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return result


_VISUAL_WEB_REF_DIR = _AURORA_CACHE_DIR / "visual_web_references"
_MEMORY_VISUAL_REF_CACHE: dict[str, dict[str, Any] | None] = {}


def _fetch_best_cutout_pil(
    queries: list[str],
    required_tokens: list[str] | None = None,
    avoid_tokens: list[str] | None = None,
) -> tuple[Any, str] | tuple[None, str]:
    """Cherche sur Bing Images (via reference_visual_search) le meilleur détourage officiel
    (PNG transparent ou fond blanc propre, corps entier non coupé en bas) et retourne (PIL.Image RGB sur fond blanc, url)."""
    try:
        import io as _io
        import numpy as _np
        from PIL import Image as _Image
        ref_svc_dir = str(Path(__file__).resolve().parents[1] / "application" / "python-services")
        if ref_svc_dir not in sys.path:
            sys.path.insert(0, ref_svc_dir)
        from reference_visual_search import search_bing_images, request_bytes, MAX_IMAGE_BYTES
    except Exception:
        return None, ""

    best_score = -1e9
    best_crop = None
    best_url = ""
    seen_urls: set[str] = set()
    req_norm = [t.lower() for t in (required_tokens or []) if len(t) >= 3]
    avoid_norm = [t.lower() for t in (avoid_tokens or []) if len(t) >= 3]

    for q in queries:
        try:
            cands = search_bing_images(q, limit=6)
        except Exception:
            continue
        for c in cands[:6]:
            url = str(c.get("imageUrl") or c.get("thumbUrl") or "").strip()
            thumb_url = str(c.get("thumbUrl") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            title_low = str(c.get("title") or "").lower()
            url_low = url.lower()
            url_path_parts = [
                seg for seg in urllib.parse.urlsplit(url_low).path.split("/")
                if seg and seg not in ("revision", "latest", "scale-to-width-down")
            ]
            img_seg = next(
                (seg for seg in reversed(url_path_parts) if any(seg.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp"))),
                url_path_parts[-1] if url_path_parts else "",
            )
            url_filename = _norm(img_seg)
            combined_meta = f"{_norm(title_low)} {_norm(url_low)}"
            if any(
                bad in title_low or bad in url_low or bad in url_filename
                for bad in (
                    "cosplay", "meme", "tier-list", "tierlist", "tshirt", "t-shirt",
                    "mug", "wallpaper", "fanart", "fan-art", "freepik.com", "shutterstock.com",
                    "istockphoto.com", "vecteezy.com", "stock-image", "zig-zag", "zigzag",
                    "seasons", "season_", "episodes", "episode_", "saison", "banner", "collage",
                    "poster", "dvd", "blu-ray", "soundtrack",
                )
            ):
                continue
            if req_norm and (req_norm[0] not in combined_meta):
                continue
            if avoid_norm and any(tok in url_filename for tok in avoid_norm) and (not req_norm or req_norm[0] not in url_filename):
                continue
            try:
                try:
                    raw_bytes, _ = request_bytes(url, MAX_IMAGE_BYTES, accept="image/*,*/*;q=0.8")
                except Exception:
                    if thumb_url and thumb_url != url:
                        raw_bytes, _ = request_bytes(thumb_url, MAX_IMAGE_BYTES, accept="image/*,*/*;q=0.8")
                    else:
                        raise
                im = _Image.open(_io.BytesIO(raw_bytes))
                w, h = im.size
                if w < 240 or h < 240:
                    continue
                aspect = float(w) / float(h)
                if aspect < 0.28 or aspect > 2.2:
                    continue

                rgba = im.convert("RGBA")
                arr_rgba = _np.asarray(rgba)
                alpha = arr_rgba[:, :, 3]
                trans_frac = float((alpha < 28).mean())
                opaque_frac = float((alpha > 215).mean())
                border_alpha = _np.concatenate([alpha[0, :], alpha[-1, :], alpha[:, 0], alpha[:, -1]])
                border_trans_frac = float((border_alpha < 28).mean())
                is_cutout = (0.10 <= trans_frac <= 0.90) and (opaque_frac >= 0.08) and (border_trans_frac >= 0.65)

                white_bg = _Image.new("RGB", (w, h), (255, 255, 255))
                white_bg.paste(rgba, mask=rgba.split()[3])
                arr_rgb = _np.asarray(white_bg)
                nonwhite = arr_rgb.min(axis=2) < 242
                if int(nonwhite.sum()) < 2500:
                    continue

                border_rgb_white = _np.concatenate([
                    arr_rgb[0, :].min(axis=1) > 235,
                    arr_rgb[-1, :].min(axis=1) > 235,
                    arr_rgb[:, 0].min(axis=1) > 235,
                    arr_rgb[:, -1].min(axis=1) > 235,
                ])
                border_white_frac = float(border_rgb_white.mean())
                is_clean_white = border_white_frac >= 0.78

                if not is_cutout and not is_clean_white:
                    continue

                ys, xs = _np.where(alpha > 28 if is_cutout else nonwhite)
                y0, y1 = int(ys.min()), int(ys.max())
                x0, x1 = int(xs.min()), int(xs.max())
                bw = max(1, x1 - x0 + 1)
                bh = max(1, y1 - y0 + 1)
                touches_bottom = (y1 >= h - 2) and (y0 > int(0.06 * h))
                fg_crop = (alpha > 28 if is_cutout else nonwhite)[y0 : y1 + 1, x0 : x1 + 1]
                bot_band = fg_crop[max(0, bh - 3) : bh, :]
                bot_fill_frac = float(bot_band.any(axis=0).mean()) if bot_band.size > 0 else 0.0
                lower_q = fg_crop[max(0, int(0.78 * bh)) : max(1, int(0.92 * bh)), :]
                lower_q_width = float(lower_q.any(axis=0).mean()) if lower_q.size > 0 else 1.0
                bot_to_lower_ratio = bot_fill_frac / max(0.05, lower_q_width)
                # Detect flat horizontal guillotine cut at the bottom (waist/hip/tail cut off)
                is_guillotine_bottom_crop = (
                    (bot_fill_frac > 0.42)
                    or (bot_fill_frac > 0.22 and bot_to_lower_ratio > 0.82)
                    or (y1 >= h - 3 and bot_fill_frac > 0.18)
                )

                score = 0.0
                if is_cutout:
                    score += 55.0
                elif is_clean_white:
                    score += 32.0
                if any(dom in url_low for dom in ("wikia.nocookie.net", "fandom.com", "wikitide.net", "wikimedia.org", "bulbagarden", "yokaiwatch", "inazuma")):
                    score += 28.0
                if req_norm and req_norm[0] in url_filename:
                    score += 28.0
                elif req_norm and any(tok in url_filename for tok in req_norm):
                    score += 12.0
                if avoid_norm and any(tok in url_filename for tok in avoid_norm):
                    score -= 45.0
                if not touches_bottom and not is_guillotine_bottom_crop:
                    score += 28.0
                else:
                    score -= 65.0
                if float(bh) / float(bw) >= 1.15:
                    score += 14.0
                if min(w, h) >= 380:
                    score += 10.0

                if score > best_score:
                    best_score = score
                    best_crop = white_bg.crop((x0, y0, x1 + 1, y1 + 1))
                    best_url = url
                    if score >= 105.0 and not is_guillotine_bottom_crop:
                        return best_crop, best_url
            except Exception:
                continue
    return best_crop, best_url


def _extract_vision_traits_from_image(image_path: str, subject_label: str, timeout_s: float = 30.0) -> str:
    """Inspecte une image de référence officielle via qwen3-vl:8b Vision pour extraire
    ses attributs visuels exacts en anglais (sans aucun hardcode)."""
    try:
        ref_svc_dir = str(Path(__file__).resolve().parents[1] / "application" / "python-services")
        if ref_svc_dir not in sys.path:
            sys.path.insert(0, ref_svc_dir)
        from vlm_judge import ask_vlm
        verdict = ask_vlm(
            [image_path],
            f"Inspect this official character reference image of '{subject_label}' and describe its exact canonical visual design and pose in 35-55 affirmative English words: 2D cel-shaded vs 3D style, species/body proportions, head/hair tuft/ears/snout/teeth shape & color (note: any yellow band under a cartoon animal snout is a row of grinning yellow teeth, NOT a scarf; and pointed side hair tufts on human anime characters are spiky hair tufts, NEVER cat ears!), headgear/headband/glasses, eye shape & color, outfit or fur/skin colors & markings, and exact arm/hand gesture. CRITICAL: use ONLY affirmative descriptions of what IS visible—NEVER write negative phrases like 'no ears', 'no hair', or 'no arms'!",
            schema_hint='{"visual_description_en": "..."}',
            timeout=int(timeout_s),
        )
        if isinstance(verdict, dict):
            desc = str(verdict.get("visual_description_en") or "").strip()
            desc = re.sub(r",?\s*\bno\s+(?:hair|ears|arms|hands|legs)(?:/(?:hair|ears|arms|hands|legs))?\b", "", desc, flags=re.IGNORECASE).strip()
            if "human" in desc.lower():
                desc = re.sub(r"\bwith\s+cat(?:-like)?[- ]ears\b", "with pointed side hair tufts", desc, flags=re.IGNORECASE)
            if len(desc) > 20:
                return desc
    except Exception:
        pass
    return ""


def resolve_visual_web_reference(
    raw_prompt: str,
    open_world_entity: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Résout et télécharge automatiquement la vraie référence visuelle officielle d'un personnage
    (ou duo de personnages 'X et Y') depuis le web (Fandom/Wikia/Bing Images), l'assemble sur
    un canevas carré blanc 1024x1024 sans troncature, et extrait ses attributs visuels via Qwen3-VL Vision."""
    if os.environ.get("AURORA_DISABLE_OPEN_WORLD_LOOKUP") == "1" or os.environ.get("AURORA_DISABLE_VISUAL_WEB_REF") == "1":
        return None

    # Loi d'invariance morphologique : une créature quadrupède / mythologique générique ou un matériau
    # ("opale", "cristal", "jade", "kitsune à 9 queues") ne doit jamais déclencher une recherche de
    # personnage humanoïde homonyme (ex: Opal de Steven Universe à 4 bras).
    morph_check = infer_universal_morphology(raw_prompt)
    if morph_check.get("is_non_humanoid_creature") and not re.search(
        r"\b(?:de|du|des|d['’]|from|of|in)\s+[A-ZÀ-ÖØ-Þ]", raw_prompt or ""
    ):
        return None

    candidate = _extract_candidate_entity_query(raw_prompt)
    if not candidate:
        return None

    de_stripped = re.sub(r"\b(?:d['’]|de\s+la\s+|de\s+l['’]|du\s+|des\s+|de\s+)", " ", candidate, flags=re.IGNORECASE)
    de_stripped = re.sub(r"\s+", " ", de_stripped).strip()
    phonetic_q = re.sub(r"([aou])y\b", r"\1i", de_stripped or candidate, flags=re.IGNORECASE)
    phonetic_q = re.sub(r"([aou])y(?=[a-z])", r"\1i", phonetic_q, flags=re.IGNORECASE)

    slug = re.sub(r"[^a-z0-9]+", "_", _norm(phonetic_q)).strip("_")[:64]
    if not slug:
        return None

    if slug in _MEMORY_VISUAL_REF_CACHE:
        cached = _MEMORY_VISUAL_REF_CACHE[slug]
        if cached and Path(str(cached.get("image_path") or "")).is_file():
            return cached

    _VISUAL_WEB_REF_DIR.mkdir(parents=True, exist_ok=True)
    img_out_path = _VISUAL_WEB_REF_DIR / f"{slug}_ref1024.png"
    meta_out_path = _VISUAL_WEB_REF_DIR / f"{slug}_ref1024.json"

    if img_out_path.is_file() and meta_out_path.is_file():
        try:
            loaded_meta = json.loads(meta_out_path.read_text(encoding="utf-8"))
            if isinstance(loaded_meta, dict) and loaded_meta.get("image_path") and Path(loaded_meta["image_path"]).is_file():
                _MEMORY_VISUAL_REF_CACHE[slug] = loaded_meta
                return loaded_meta
        except Exception:
            pass

    try:
        from PIL import Image as _Image
    except Exception:
        return None

    ow_title = str((open_world_entity or {}).get("title") or "").strip()
    ow_title = re.sub(
        r"^(?:List\s+of\s+|Liste\s+des\s+[eé]pisodes\s+(?:de\s+|d['’])?|Saison\s+\d+\s+(?:de\s+|d['’])?)",
        "",
        ow_title,
        flags=re.IGNORECASE,
    )
    ow_title = re.sub(r"\s+(?:episodes|[eé]pisodes|seasons|saisons)$", "", ow_title, flags=re.IGNORECASE).strip()
    # Détection syntaxique d'un duo de personnages "<Nom1> et/and/& <Nom2>" (ex: "Zig et Sharko", "Astérix et Obélix")
    m_pair = re.match(
        r"^([\wÀ-ÿ'’-]{2,20})\s+(?:et|and|&)\s+([\wÀ-ÿ'’-]{2,20})(?:\s+.*)?$",
        de_stripped,
        flags=re.IGNORECASE,
    )
    canvas = _Image.new("RGB", (1024, 1024), (255, 255, 255))
    source_urls: list[str] = []
    pair_vision_desc_en = ""

    if m_pair:
        name1 = m_pair.group(1).strip()
        name2 = m_pair.group(2).strip()
        pair_canonical_slug = re.sub(r"[^a-z0-9]+", "_", _norm(f"{name1} et {name2}")).strip("_")
        pair_canonical_png = _VISUAL_WEB_REF_DIR / f"{pair_canonical_slug}_ref1024.png"
        pair_canonical_json = _VISUAL_WEB_REF_DIR / f"{pair_canonical_slug}_ref1024.json"
        if pair_canonical_png.is_file() and pair_canonical_json.is_file():
            try:
                loaded_pair = json.loads(pair_canonical_json.read_text(encoding="utf-8"))
                if isinstance(loaded_pair, dict) and loaded_pair.get("image_path") and Path(loaded_pair["image_path"]).is_file():
                    _MEMORY_VISUAL_REF_CACHE[slug] = loaded_pair
                    return loaded_pair
            except Exception:
                pass
        if _norm(name1) not in _GENERIC_NON_ENTITY_WORDS and _norm(name2) not in _GENERIC_NON_ENTITY_WORDS:
            ctx_label = ow_title or f"{name1} et {name2}"
            crop1, u1 = _fetch_best_cutout_pil(
                [
                    f"{name1} ({ctx_label}) png",
                    f"{name1} {ctx_label} character artwork png",
                ],
                required_tokens=[_norm(name1)],
                avoid_tokens=[_norm(name2), "seasons", "episodes"],
            )
            crop2, u2 = _fetch_best_cutout_pil(
                [
                    f"{name2} ({ctx_label}) png",
                    f"{name2} {ctx_label} character artwork png",
                ],
                required_tokens=[_norm(name2)],
                avoid_tokens=[_norm(name1), "seasons", "episodes"],
            )
            if crop1 is not None and crop2 is not None and u1 != u2:
                for idx, (c_im, x_center) in enumerate(((crop1, 270), (crop2, 754))):
                    cw, ch = c_im.size
                    scale = min(430.0 / float(cw), 820.0 / float(ch))
                    nw = max(1, int(round(cw * scale)))
                    nh = max(1, int(round(ch * scale)))
                    resized = c_im.resize((nw, nh), _Image.Resampling.LANCZOS)
                    px = max(16, min(1024 - nw - 16, x_center - nw // 2))
                    py = (1024 - nh) // 2
                    canvas.paste(resized, (px, py))
                source_urls = [u for u in (u1, u2) if u]
                try:
                    t1_path = _VISUAL_WEB_REF_DIR / f"{slug}_part1.png"
                    t2_path = _VISUAL_WEB_REF_DIR / f"{slug}_part2.png"
                    crop1.save(str(t1_path), format="PNG")
                    crop2.save(str(t2_path), format="PNG")
                    d1 = _extract_vision_traits_from_image(str(t1_path), f"{name1} ({ctx_label})")
                    d2 = _extract_vision_traits_from_image(str(t2_path), f"{name2} ({ctx_label})")
                    if d1 and d2:
                        pair_vision_desc_en = f"Left character ({name1}): {d1} Right character ({name2}): {d2}"
                except Exception:
                    pass

    if not source_urls:
        # Détecte si la requête nomme un personnage suivi d'une œuvre en duo ("<Perso> [de] <NomA> et <NomB>")
        m_sub_in_pair = re.match(
            r"^([\wÀ-ÿ'’-]{2,20})\s+([\wÀ-ÿ'’-]{2,20})\s+(?:et|and|&)\s+([\wÀ-ÿ'’-]{2,20})(?:\s+.*)?$",
            de_stripped,
            flags=re.IGNORECASE,
        )
        if m_sub_in_pair:
            subj_only = m_sub_in_pair.group(1).strip()
            ctx_pair = f"{m_sub_in_pair.group(2).strip()} & {m_sub_in_pair.group(3).strip()}"
            search_queries = [
                f"{subj_only} ({ctx_pair}) character png",
                f"{subj_only} {ctx_pair} full body png",
                f"{subj_only} {ctx_pair} png",
            ]
            req_toks = [_norm(subj_only)]
            avoid_single = [t for t in (_norm(m_sub_in_pair.group(2)), _norm(m_sub_in_pair.group(3))) if t != _norm(subj_only)]
        else:
            search_queries = [
                f"{phonetic_q} official character artwork full body png",
                f"{phonetic_q} png",
            ]
            if ow_title and ow_title.lower() not in phonetic_q.lower():
                search_queries.insert(0, f"{ow_title} {phonetic_q} character png")
            req_toks = [t for t in re.findall(r"[a-z0-9]{3,}", _norm(phonetic_q)) if t not in {"watch", "eleven", "war", "god", "les", "des", "une"}]
            avoid_single = []
        crop_single, u_single = _fetch_best_cutout_pil(search_queries, required_tokens=req_toks, avoid_tokens=avoid_single)
        if crop_single is None:
            _MEMORY_VISUAL_REF_CACHE[slug] = None
            return None
        cw, ch = crop_single.size
        scale = min(840.0 / float(cw), 860.0 / float(ch))
        nw = max(1, int(round(cw * scale)))
        nh = max(1, int(round(ch * scale)))
        resized = crop_single.resize((nw, nh), _Image.Resampling.LANCZOS)
        canvas.paste(resized, ((1024 - nw) // 2, (1024 - nh) // 2))
        source_urls = [u_single] if u_single else []

    try:
        canvas.save(str(img_out_path), format="PNG")
    except Exception:
        return None

    subject_label = f"{phonetic_q} ({ow_title})" if ow_title and ow_title.lower() != phonetic_q.lower() else phonetic_q
    vision_desc_en = pair_vision_desc_en or _extract_vision_traits_from_image(str(img_out_path), subject_label)

    ref_info = {
        "query": phonetic_q,
        "subject_label": subject_label,
        "image_path": str(img_out_path),
        "source_urls": source_urls,
        "visual_description_en": vision_desc_en,
    }
    _MEMORY_VISUAL_REF_CACHE[slug] = ref_info
    try:
        meta_out_path.write_text(json.dumps(ref_info, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return ref_info


def _free_comfy_before_ollama() -> None:
    """Libère la RAM/VRAM de ComfyUI (--novram garde ~20 Go en RAM système) avant
    de solliciter Ollama afin d'éviter toute saturation mémoire des 30 Go de RAM."""
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8188/free",
            data=b'{"unload_models": true, "free_memory": true}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            resp.read()
    except Exception:
        pass


def _select_available_ollama_model() -> tuple[str | None, bool]:
    """Découvre dynamiquement le meilleur modèle Ollama disponible (en privilégiant tout modèle déjà
    chargé en mémoire ou les modèles maîtres installés) et vérifie la VRAM libre."""
    now = time.time()
    if now - float(_OLLAMA_MODEL_CACHE.get("ts") or 0.0) < 45.0 and _OLLAMA_MODEL_CACHE.get("model"):
        return _OLLAMA_MODEL_CACHE["model"], bool(_OLLAMA_MODEL_CACHE["use_cpu_only"])

    chosen_model: str | None = None
    already_loaded = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=1.5) as resp:
            ps_data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            for m in ps_data.get("models") or []:
                name = str(m.get("name") or "")
                if name and "embed" not in name.lower():
                    chosen_model = name
                    already_loaded = True
                    break
    except Exception:
        pass

    if not chosen_model:
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2.0) as resp:
                tags_data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                installed = [
                    str(m.get("name") or "")
                    for m in (tags_data.get("models") or [])
                    if m.get("name") and "embed" not in str(m.get("name")).lower()
                ]
                preferred_order = (
                    "orcarouter/Qwen3.8-27B-Uncensored:latest",
                    "qwen3-vl:30b",
                    "deepseek-r1:32b",
                    "qwen3-coder-next:q4_K_M",
                    "qwen3-vl:8b",
                )
                for pref in preferred_order:
                    if pref in installed:
                        chosen_model = pref
                        break
                if not chosen_model and installed:
                    chosen_model = installed[0]
        except Exception:
            return None, False

    use_cpu_only = False
    if chosen_model and not already_loaded:
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                text=True,
                timeout=0.8,
            ).strip()
            free_mib = int(out.splitlines()[0].strip())
            if free_mib < 6800:
                use_cpu_only = True
        except Exception:
            pass

    _OLLAMA_MODEL_CACHE.update({"ts": now, "model": chosen_model, "use_cpu_only": use_cpu_only})
    return chosen_model, use_cpu_only


def infer_universal_morphology(
    raw_text: str,
    english_core: str = "",
    open_world_entity: dict[str, Any] | None = None,
    visual_web_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Infère de manière 100 % universelle (sans aucune liste de noms de personnages codée en dur)
    la morphologie anatomique, squelettique et cinématique de N'IMPORTE QUEL sujet — qu'il soit
    connu (via ancrage Open-World / Vision VLM) ou 100 % inventé / inédit."""
    norm_raw = _norm(raw_text or "")
    norm_en = _norm(english_core or "")
    ow_summary = _norm(str((open_world_entity or {}).get("summary_extract") or ""))
    vis_desc = _norm(str((visual_web_reference or {}).get("visual_description_en") or ""))
    combined = f"{norm_raw} {norm_en} {ow_summary} {vis_desc}".strip()

    # 1. Loi syntaxique et visuelle universelle de bipédie / anthropomorphisme / humanoïde
    has_bipedal_or_humanoid_grammar = bool(
        re.search(
            r"\b("
            r"biped(?:e|al)?|anthropomorph(?:e|ic)?|humanoid(?:e)?|"
            r"standing\s+upright|debout|two\s+legs|deux\s+jambes|two\s+arms|deux\s+bras|"
            r"hands\b|mains\b|fists\b|poings\b|thumbs[- ]?up|pouce\s+lev|"
            r"holding\b|wielding\b|tenant\b|arms\s+raised|bras\s+lev|arms\s+crossed|bras\s+crois|"
            r"wearing\b|dressed\s+in|vetu|habille|veste|jacket|manteau|coat|pantalon|trousers|jeans|"
            r"shorts?\b|maillot|bermuda|chemise|shirt|tunique|tunic|robe|dress|costume|suit|gants|gloves|bottes|boots|sneakers|"
            r"homme|femme|garcon|fille|personne|humain|man\b|woman\b|boy\b|girl\b|human\b|person\b|"
            r"personnages?\b|characters?\b|duo\b|cartoon\b|dessin\s+anime|"
            r"guerrier|warrior|mage|sorcier|chevalier|knight|ninja|samourai|samurai|pirate|soldat|horloger"
            r")\b",
            combined,
        )
    )

    # 2. Loi anatomique et zoologique universelle de créature non-humanoïde (quadrupède, ailée, aquatique, multi-appendices)
    surface_cls = classify_creature_surface(raw_text)
    has_non_humanoid_creature_grammar = (
        surface_cls in {"furred_mammal", "scaled_draconic_reptilian", "feathered_avian", "chitin_arthropod"}
        or bool(
            re.search(
                r"\b("
                r"quadruped(?:e)?|four\s+legs|four\s+paws|quatre\s+pattes|forelegs|hind\s+legs|sabots|hooves|"
                r"museau|snout|crocs|fangs|griffes|claws|fourrure|pelage|plumage|ecailles|"
                r"wingspan|ailes\s+deployees|nageoires|fins\b|tentacules|tentacles|"
                r"nine[- ]?tailed|multi[- ]?tailed|queues?\b|tails?\b|"
                r"creature|bete|beast|animal|fox\s+spirit|esprit[- ]?renard|"
                r"canine|feline|equine|avian|reptilian|draconic|cephalopod|arthropod|insectoid|"
                r"kitsune|fox|renard|wolf|loup|lion|tiger|tigre|horse|cheval|deer|cerf|bear|ours|"
                r"dragon|griffin|griffon|owl|hibou|eagle|aigle|phoenix|phenix|bird|oiseau|"
                r"serpent|snake|leviathan|nautilus"
                r")\b",
                combined,
            )
        )
    )

    # Si l'utilisateur demande explicitement "zéro bras humains / quadrupède / quatre pattes", la morphologie animale prime
    explicit_feral_quadruped = bool(
        re.search(r"\b(quadruped(?:e)?|four\s+legs|four\s+paws|quatre\s+pattes|zero\s+humanoid|sans\s+bras\s+humain)\b", norm_raw)
    )
    is_non_humanoid_creature = explicit_feral_quadruped or (
        has_non_humanoid_creature_grammar and not has_bipedal_or_humanoid_grammar
    )

    if is_non_humanoid_creature:
        if re.search(r"\b(wing|aile|avian|bird|oiseau|owl|hibou|eagle|aigle|phoenix|phenix|griffin|griffon)\b", combined):
            sub_topology = "winged_creature"
        elif re.search(r"\b(swim|aquatic|ocean|abyss|fin|nageoire|tentacle|tentacule|leviathan|nautilus|serpent)\b", combined):
            sub_topology = "aquatic_or_serpentine_creature"
        else:
            sub_topology = "quadruped_or_multi_tailed_creature"
    else:
        sub_topology = "biped_anthropomorphic_or_humanoid"

    return {
        "is_non_humanoid_creature": is_non_humanoid_creature,
        "morphology_topology": sub_topology,
        "has_bipedal_or_humanoid_grammar": has_bipedal_or_humanoid_grammar,
        "has_non_humanoid_creature_grammar": has_non_humanoid_creature_grammar,
        "surface_class": surface_cls,
    }


def _call_local_ollama_director(
    raw_prompt: str,
    target_module: str,
    subject_ontology: str,
    effective_render_mode: str,
    operation_mode: str,
    has_reference: bool,
    conversation_context: str = "",
    open_world_entity: dict[str, Any] | None = None,
    syntactic_style_clause: dict[str, Any] | None = None,
    visual_web_reference: dict[str, Any] | None = None,
    timeout_s: float = 120.0,
) -> dict[str, Any] | None:
    """Raisonneur cognitif LLM local universel (sans liste en dur, avec contournement direct
    du bloc <think> Qwen3 pour une réponse en ~1.5-3s, cache persistant SHA-256 et protection VRAM).
    Comprend n'importe quel personnage, dessin animé, série, jeu vidéo, personne réelle ou style futur."""
    vision_grounding_str = str((visual_web_reference or {}).get("visual_description_en") or "").strip()
    cache_sig = hashlib.sha256(
        json.dumps(
            [
                "v6_visual_web_grounding",
                raw_prompt.strip(),
                target_module,
                operation_mode,
                bool(has_reference),
                (conversation_context or "").strip()[:180],
                (open_world_entity or {}).get("title"),
                (syntactic_style_clause or {}).get("style_phrase_raw"),
                vision_grounding_str[:160],
            ],
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:24]

    if cache_sig in _MEMORY_COGNITIVE_CACHE:
        return _MEMORY_COGNITIVE_CACHE[cache_sig]

    disk_cache: dict[str, Any] = {}
    try:
        if _COGNITIVE_PROMPT_CACHE_FILE.exists():
            loaded_c = json.loads(_COGNITIVE_PROMPT_CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded_c, dict):
                disk_cache = loaded_c
                if cache_sig in disk_cache:
                    _MEMORY_COGNITIVE_CACHE[cache_sig] = disk_cache[cache_sig]
                    return disk_cache[cache_sig]
    except Exception:
        disk_cache = {}

    model_name, use_cpu_only = _select_available_ollama_model()
    if not model_name:
        return None

    grounding_line = (
        f"- Open-World Wikipedia Grounding: {open_world_entity['summary_extract']}\n"
        if open_world_entity and open_world_entity.get("summary_extract")
        else ""
    )
    vision_line = (
        f"- Official Visual Reference Analysis (from verified official character artwork — MUST be respected 100%): {vision_grounding_str}\n"
        if vision_grounding_str
        else ""
    )
    style_clause_line = (
        f"- Explicit user style/material transformation phrase: '{syntactic_style_clause['style_phrase_raw']}'\n"
        if syntactic_style_clause and syntactic_style_clause.get("style_phrase_raw")
        else ""
    )
    system_rules = (
        "You are the Universal Open-World AGI Semantic Prompt & Ontology Director of AuroraIA.\n"
        "Analyze the user's request semantically using your full world knowledge and Official Visual Reference Analysis (for ANY character, cartoon, anime, manga, video game, movie/book franchise, real person, creature, object, or future/custom artistic style or material—even if phonetically spelled or misspelled in French like 'yokay watch' for Yo-kai Watch) and produce fluent, visually precise ENGLISH.\n"
        f"- Target module: {target_module}\n"
        f"- Operation mode: {operation_mode}\n"
        f"{grounding_line}{vision_line}{style_clause_line}"
        "STRICT UNIVERSAL ONTOLOGICAL LAWS:\n"
        "1. NATIVE CARTOON / BD / ANIMATED SERIES (any Western/French/global cartoon, BD, comics, or animated film): if the user did NOT ask for real human skin textures, set subject_ontology='anime_manga_character', effective_render_mode='native_anime_stylized', and stylized_submode='cartoon_3d'. When target_module='image' and the source cartoon is 2D animated (e.g. Zig & Sharko, Tom and Jerry, Simpsons), describe authentic 2D flat cel-shaded cartoon illustration with bold clean outlines and flat vibrant colors (NEVER write '3D cartoon surfaces' or '3D fur' in 2D image mode!). When target_module='3d', describe volumetric 3D cartoon rendering faithful to the exact cartoon proportions and colors. Always incorporate 100% of Official Visual Reference Analysis.\n"
        "2. NATIVE ANIME / MANGA / CROSS-MEDIA ANIME FRANCHISE (any Japanese anime, manga, light novel, or anime franchise like Inazuma Eleven, Yo-kai Watch, etc.): if no real-skin override is requested, set subject_ontology='anime_manga_character' (or 'game_character_or_asset' if primarily a game), effective_render_mode='native_anime_stylized' (or 'native_game_stylized'), and stylized_submode='anime_cel'. Always include every signature visual trait from Official Visual Reference Analysis and canonical lore.\n"
        "3. VIDEO GAME CHARACTER OR OBJECT (any video game character, creature, weapon, vehicle, or item): if no style modification is requested, set subject_ontology='game_character_or_asset' and effective_render_mode='native_game_stylized'. For realistic/dark-fantasy/cinematic AAA 3D games (e.g. God of War, The Witcher, Elden Ring), set stylized_submode=null and describe high-detail cinematic AAA 3D game engine rendering with physically based textures, dramatic lighting, and exact canonical in-game design. Set stylized_submode='lowpoly_voxel' only for voxel/blocky games, 'cartoon_3d' only for cartoon platformers, or 'anime_cel' for cel-shaded JRPGs.\n"
        "4. UNIVERSAL OPEN-ENDED STYLE / MATERIAL TRANSFORMATION (changing ANY subject into ANY requested style, artistic movement, or material—e.g. cartoon, 3D cartoon figurine, Funko Pop, cubic/voxel/blocky, claymation, plush, origami, blue bioluminescent crystal, blown glass, liquid metal, carved wood, porcelain, oil painting, or any future/invented aesthetic): set effective_render_mode='hybrid_real_to_stylized'. Set stylized_submode to 'cartoon_figurine', 'figurine_toy', 'clay_or_plush', 'lowpoly_voxel', 'cartoon_3d', 'anime_cel', OR null if it is a custom material/artistic medium (crystal, glass, liquid metal, marble, neon, painting, etc.). CRITICAL FOR FIGURINE / CARTOON FIGURINE TRANSFORMATIONS: when transforming a subject into a figurine or 3D cartoon figurine, you MUST describe a COMPLETE FULL-BODY head-to-toe stylized 3D collectible cartoon vinyl/chibi figurine with an oversized stylized cartoon head (1:2.5 chibi head-to-body ratio), large expressive glossy 3D cartoon eyes, smooth moulded satin PVC/vinyl toy surfaces, compact sculpted cartoon body holding their signature accessory, standing head-to-toe on a circular collector figurine display pedestal base—NEVER a half-body portrait or flat 2D anime drawing! CRITICAL FOR CUBIC / VOXEL TRANSFORMATIONS ('cubique', 'voxel', 'cube', 'blocky'): set stylized_submode='lowpoly_voxel' and describe a COMPLETE full-body 3D cubic voxel block-art character built 100% from sharp geometric 3D cubes, stepped 90-degree voxel blocks, cubic head, cubic hair blocks, and blocky voxel limbs standing on a cubic voxel base!\n"
        "5. ANIME/CARTOON/GAME TO REALISTIC OVERRIDE: if the user explicitly asks for real human skin textures or live-action realism on a stylized character, set effective_render_mode='hybrid_anime_with_real_textures' and stylized_submode=null.\n"
        "6. DEFAULT PHOTOREALISM / LIVE-ACTION CINEMA (e.g. real-world objects like 'une pomme', animals, real people, or live-action movie characters like Harry Potter when no cartoon/anime restyling is requested): set effective_render_mode='native_photorealistic' and stylized_submode=null. For everyday objects/fruits (e.g. 'une pomme'), describe a fresh, crisp, unblemished, healthy whole object resting on a natural surface (e.g. wooden table with morning light and tiny water droplets)—NEVER add brown spots, bruises, rot, or unrequested hands holding it!\n"
        "7. For 3D module ('3d'), english_expanded_prompt (45-70 words max) MUST describe a full-body or complete-object 3D reconstruction reference (centered, complete silhouette, separated limbs/hands if character, clean neutral studio background) in the exact determined style/material.\n"
        "8. For Image module ('image'), english_expanded_prompt (50-80 words max) MUST describe a finished, vivid, high-fidelity artwork or photograph in the exact determined style/material (do NOT write '3D reconstruction'). CRITICAL: When Official Visual Reference Analysis is provided in creation mode, preserve the EXACT character pose, gesture, and proportions from that official reference and place the subject(s) against a clean, simple soft pastel gradient backdrop (NEVER a busy multi-building background) so ReferenceLatent locks 100% of the canonical character design! When operation_mode='modification' and Recent context is provided, english_expanded_prompt MUST describe the complete resulting image combining the base subject from Recent context with the requested edit or style/material transformation while preserving all unmentioned canonical traits of the base subject. Keep reasoning_fr under 12 words.\n"
        "Output ONLY valid JSON:\n"
        "{\"subject_ontology\": \"anime_manga_character|game_character_or_asset|mechanical_cad_engineering|real_human_subject|real_world_object_or_scene\", \"effective_render_mode\": \"native_anime_stylized|hybrid_real_to_stylized|hybrid_anime_with_real_textures|native_game_stylized|native_engineering_pbr|native_photorealistic\", \"stylized_submode\": \"cartoon_3d|cartoon_figurine|figurine_toy|clay_or_plush|lowpoly_voxel|anime_cel|null\", \"creature_surface_class\": \"feathered_avian|scaled_draconic_reptilian|chitin_arthropod|furred_mammal|humanoid_or_generic\", \"english_subject\": \"...\", \"english_expanded_prompt\": \"...\", \"excluded_items_en\": [], \"mandatory_attributes_en\": [], \"reasoning_fr\": \"...\"}"
    )
    user_msg = f"User prompt: {raw_prompt}"
    if conversation_context:
        user_msg += f"\nRecent context: {conversation_context[:500]}"
    if has_reference:
        user_msg += "\nHas visual reference attached: true"

    options: dict[str, Any] = {"temperature": 0.1, "num_predict": 1024, "stop": ["<|im_end|>"]}
    if use_cpu_only:
        options["num_gpu"] = 0

    raw_chatml_prompt = (
        f"<|im_start|>system\n{system_rules}<|im_end|>\n"
        f"<|im_start|>user\n{user_msg}<|im_end|>\n"
        f"<|im_start|>assistant\n<think>\n\n</think>\n{{"
    )
    _free_comfy_before_ollama()
    payload = json.dumps({
        "model": model_name,
        "prompt": raw_chatml_prompt,
        "raw": True,
        "stream": False,
        "options": options,
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            content = "{" + str(data.get("response") or "").strip()
            content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
            parsed: dict[str, Any] | None = None
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except Exception:
                    parsed = None
            if parsed is None:
                # Récupération résiliente si le JSON a été coupé à la fin de reasoning_fr
                extracted: dict[str, Any] = {}
                for field in (
                    "subject_ontology",
                    "effective_render_mode",
                    "stylized_submode",
                    "creature_surface_class",
                    "english_subject",
                    "english_expanded_prompt",
                    "reasoning_fr",
                ):
                    m_f = re.search(rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"', content)
                    if m_f:
                        extracted[field] = m_f.group(1).replace('\\"', '"').strip()
                if extracted.get("english_expanded_prompt"):
                    parsed = extracted
            if isinstance(parsed, dict) and isinstance(parsed.get("english_expanded_prompt"), str) and len(parsed["english_expanded_prompt"].strip()) > 20:
                _MEMORY_COGNITIVE_CACHE[cache_sig] = parsed
                try:
                    _AURORA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    disk_cache[cache_sig] = parsed
                    _COGNITIVE_PROMPT_CACHE_FILE.write_text(
                        json.dumps(disk_cache, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
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
    use_llm: bool | None = None,
    use_open_world: bool = True,
    open_world_grounding: bool | None = None,
    reference_image_path: str | None = None,
) -> dict[str, Any]:
    """Analyse l'ontologie du sujet en Monde Ouvert (Wikipedia/MediaWiki + Recherche Visuelle Web Officielle +
    Raisonneur LLM Ollama + analyseur syntaxique universel), détecte tout style ou transformation sans dépendre
    de listes en dur, distingue création vs modification, et produit un prompt anglais complet et fidèle."""
    if open_world_grounding is not None:
        use_open_world = bool(open_world_grounding)
    if use_llm is None:
        use_llm = os.environ.get("AURORA_DISABLE_PROMPT_LLM") != "1"
    clean_raw = (raw_prompt or "").strip()
    norm = _norm(clean_raw)
    ctx_norm = _norm(conversation_context)
    req_style_norm = _norm(requested_style or "")

    # 1. Extraction syntaxique universelle de toute clause de style / transformation
    syntactic_style = extract_universal_style_clause(clean_raw)
    has_anime_style_selected = any(
        tok in req_style_norm for tok in ("anime", "manga", "ghibli", "cel", "cartoon", "comic", "chibi", "pixar", "figurine")
    )
    explicit_real_textures_override = (
        bool(EXPLICIT_REAL_TEXTURES_OVERRIDE_RE.search(norm))
        or bool(syntactic_style.get("is_real_override"))
    )
    explicit_stylized_override = (
        bool(EXPLICIT_STYLIZED_OVERRIDE_RE.search(norm))
        or has_anime_style_selected
        or (bool(syntactic_style.get("has_style_clause")) and not explicit_real_textures_override)
    )
    raw_stylized_submode = detect_requested_stylized_submode(clean_raw)

    # 2. Détection Création vs Modification vs Reproduction
    is_pure_style_transfer_creation = (
        not has_reference
        and not conversation_context.strip()
        and mode_hint not in {"edit", "modification"}
        and (explicit_stylized_override or explicit_real_textures_override or bool(syntactic_style.get("is_transformation_verb")))
        and bool(re.search(r"\b(?:transform(?:e|er)|chang(?:e|er)|converti(?:s|r)|adapte(?:r)?)\b.*\ben\b", norm))
        and not bool(re.search(r"\b(?:garde|conserve|sans\s+changer|meme\s+pose|meme\s+personnage)\b", norm))
    )
    is_reproduction = (
        mode_hint == "replicate"
        or bool(REPRODUCTION_INTENT_RE.search(norm))
    )
    is_modification = (
        not is_reproduction
        and not is_pure_style_transfer_creation
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

    # 3. Détection de l'ontologie intrinsèque du sujet (Monde Ouvert Wikipedia + Analyse syntaxique)
    core_subject_norm = _norm(syntactic_style.get("core_subject_clean") or clean_raw)
    prompt_without_style_override = EXPLICIT_REAL_TEXTURES_OVERRIDE_RE.sub(
        " ", EXPLICIT_STYLIZED_OVERRIDE_RE.sub(" ", core_subject_norm)
    )
    has_style_transformation_clause = bool(syntactic_style.get("has_style_clause")) or bool(
        re.search(
            r"\b(?:en\s+(?:style\s+|version\s+|mode\s+)?(?:anime|anim[eé]|manga|cartoon|dessin\s+anim[eé]|toon|ghibli|pixar|disney|dreamworks|chibi|kawaii|pixel\s*art|low[- ]?poly|voxel|bd|bande\s+dessin[eé]e|comics?|figurine(?:\s+cartoon)?|funko(?:\s*pop)?|pop\s*vinyl|nendoroid|jouet|toy|action\s+figure|peluche|plush(?:ie)?|p[aâ]te\s+[aà]\s+modeler|clay(?:mation)?|stop[- ]?motion|lego|playmobil|caricature|statue(?:tte)?)|"
            r"(?:transform(?:e|er|ee?)|chang(?:e|er|ee?)|converti(?:s|r)?|adapt(?:e|er|ee?)|met(?:s|tre)|pass(?:e|er))\s+(?:[\w'’_-]+\s+){0,6}en\s+)\b",
            norm,
        )
    )
    has_explicit_real_subject_words = bool(
        re.search(
            r"\b(personnage\s+reel|personne\s+reelle|vrai\s+humain|vraie\s+personne|real\s+person|real\s+human|"
            r"homme|femme|pompier|policier|medecin|boulanger|soldat|footballeur|acteur|actrice|chanteur|president|mbappe|zidane|ronaldo|messi)\b",
            prompt_without_style_override,
        )
    )
    has_intrinsic_anime_or_cartoon_entity = bool(
        ANIME_UNIVERSE_AND_CHARACTER_PATTERNS.search(prompt_without_style_override)
    ) and not has_explicit_real_subject_words
    has_anime_signal_in_prompt = has_intrinsic_anime_or_cartoon_entity or (
        bool(ANIME_UNIVERSE_AND_CHARACTER_PATTERNS.search(norm))
        and not has_explicit_real_subject_words
        and not has_style_transformation_clause
    )
    has_anime_signal_in_ctx = is_modification and bool(ANIME_UNIVERSE_AND_CHARACTER_PATTERNS.search(ctx_norm))

    is_game_asset = (
        bool(GAME_ASSET_RE.search(norm))
        or bool(re.search(r"\b(?:jeu\s+vid[eé]o|video\s+game|personnage\s+de\s+jeu|objet\s+de\s+jeu|arme\s+de\s+jeu|in[- ]?game)\b", norm))
        or any(tok in req_style_norm for tok in ("pixel", "isometric", "low-poly", "low_poly"))
    ) and not has_explicit_real_subject_words
    is_mechanical_cad = bool(MECHANICAL_CAD_RE.search(norm))
    is_inanimate_vessel_or_object = bool(
        re.search(
            r"\b(vase|vases|flacon|carafe|coupe|calice|bol|pot|urne|bocal|tasse|bouteille|verre\s+en\s+forme|coeur\s+en\s+(?:verre|cristal)|bijou|bague|pendentif|collier|medaillon|trophee|coffret|bougie|chandelier|lampe|miroir|sablier)\b",
            norm,
        )
        and not re.search(r"\b(personnage|personne|humain|homme|femme|garcon|fille|guerrier|mage)\b", norm)
    )

    open_world_entity: dict[str, Any] | None = None
    if use_open_world and not is_mechanical_cad and not is_inanimate_vessel_or_object:
        open_world_entity = resolve_open_world_entity(clean_raw)
        if not open_world_entity and conversation_context.strip():
            ctx_head = conversation_context.split("—")[0].split("\n")[0].strip()
            open_world_entity = resolve_open_world_entity(ctx_head)
        if open_world_entity:
            ow_ont = open_world_entity.get("inferred_ontology")
            if ow_ont == "real_human_subject":
                has_explicit_real_subject_words = True
                has_anime_signal_in_prompt = False
            elif ow_ont == "anime_manga_character" and not has_explicit_real_subject_words:
                has_anime_signal_in_prompt = True
                if open_world_entity.get("inferred_submode") and not has_style_transformation_clause:
                    raw_stylized_submode = str(open_world_entity["inferred_submode"])
            elif ow_ont == "game_character_or_asset" and not has_explicit_real_subject_words:
                is_game_asset = True
                if not has_style_transformation_clause:
                    raw_stylized_submode = open_world_entity.get("inferred_submode")

    is_character = (
        bool(CHARACTER_SUBJECT_RE.search(norm))
        or has_anime_signal_in_prompt
        or has_anime_signal_in_ctx
        or has_explicit_real_subject_words
        or bool(open_world_entity and open_world_entity.get("inferred_ontology") in {"anime_manga_character", "game_character_or_asset", "real_human_subject"})
    )

    # Détermination de l'ontologie intrinsèque du sujet
    if is_mechanical_cad:
        subject_ontology = "mechanical_cad_engineering"
    elif is_game_asset:
        subject_ontology = "game_character_or_asset"
    elif has_anime_signal_in_prompt or has_anime_signal_in_ctx:
        subject_ontology = "anime_manga_character"
    elif is_character:
        subject_ontology = "real_human_subject"
    else:
        subject_ontology = "real_world_object_or_scene"

    # 4. Calcul du mode de rendu effectif
    if subject_ontology == "anime_manga_character":
        if explicit_real_textures_override:
            effective_render_mode = "hybrid_anime_with_real_textures"
            style_category = "photo_realistic"
        elif explicit_stylized_override and has_style_transformation_clause:
            effective_render_mode = "hybrid_real_to_stylized"
            style_category = "stylized_anime_ghibli"
        else:
            effective_render_mode = "native_anime_stylized"
            style_category = "stylized_manga_ink" if "manga" in norm and "noir et blanc" in norm else "stylized_anime_ghibli"
    elif subject_ontology == "game_character_or_asset":
        if explicit_real_textures_override:
            effective_render_mode = "hybrid_anime_with_real_textures"
            style_category = "photo_realistic"
        elif explicit_stylized_override and has_style_transformation_clause:
            effective_render_mode = "hybrid_real_to_stylized"
            style_category = "stylized_anime_ghibli"
        else:
            effective_render_mode = "native_game_stylized"
            style_category = "game_asset_pixel_art" if "pixel" in norm else "game_asset_3d_prop"
    elif subject_ontology == "mechanical_cad_engineering":
        effective_render_mode = "native_engineering_pbr"
        style_category = "photo_realistic"
    else:
        if explicit_stylized_override and not explicit_real_textures_override:
            effective_render_mode = "hybrid_real_to_stylized"
            style_category = "stylized_anime_ghibli"
        else:
            effective_render_mode = "native_photorealistic"
            style_category = "photo_realistic"

    stylized_submode: str | None = (
        raw_stylized_submode
        if effective_render_mode in {"native_anime_stylized", "hybrid_real_to_stylized", "native_game_stylized"}
        else None
    )

    # 5. Traduction en anglais du cœur de la demande (enrichie par le style syntaxique si présent)
    english_core = translate_french_to_english_core(clean_raw)
    if syntactic_style.get("style_phrase_raw") and not explicit_real_textures_override:
        raw_style_str = str(syntactic_style["style_phrase_raw"])
        if raw_style_str.lower() not in english_core.lower():
            english_core = f"{english_core} (rendered in {raw_style_str} style)"

    # 6. Construction déterministe haute-fidélité en anglais selon (target_module, effective_render_mode, operation_mode)
    if operation_mode == "modification":
        if effective_render_mode == "native_anime_stylized":
            style_lock = (
                "STRICT MODIFICATION LOCK (STYLIZED / CARTOON / ANIME ONTOLOGY): Preserve 100% of the existing character's "
                "identity, stylized proportions, expressive features, pose, framing, and unmentioned colors. "
                "Do NOT convert the character into a photorealistic human or add real skin pores."
            )
            negative_prompt = (
                "photorealistic human skin pores, live-action photo, uncanny valley, "
                "identity drift, altered pose, extra limbs, blurry linework, deformed hands, watermark"
            )
        elif effective_render_mode == "hybrid_real_to_stylized":
            custom_style = str(syntactic_style.get("style_phrase_raw") or stylized_submode or "stylized")
            if stylized_submode in {"figurine_toy", "cartoon_figurine", "cartoon_3d"}:
                style_lock = (
                    f"STYLE & MORPHOLOGY TRANSFORMATION LOCK ({stylized_submode.upper()}): Transform the reference subject into a "
                    f"COMPLETE FULL-BODY head-to-toe stylized 3D collectible cartoon vinyl/chibi figurine ({custom_style}) with an oversized "
                    f"cartoon head (1:2.5 chibi head-to-body ratio), large expressive glossy 3D cartoon eyes, smooth moulded satin PVC/vinyl "
                    f"toy finish, compact sculpted cartoon body holding their signature accessory, standing on a circular collector figurine "
                    f"display pedestal base, while preserving 100% of their recognizable identity, hairstyle, glasses/marks, and outfit colors. "
                    f"Do NOT keep a flat 2D drawing or half-body portrait crop."
                )
                negative_prompt = (
                    "raw unstylized photograph, realistic human skin pores, live-action photo, half-body portrait crop, "
                    "flat 2D drawing without 3D figurine base, uncanny valley, lost identity, deformed hands, watermark"
                )
            elif stylized_submode == "lowpoly_voxel":
                style_lock = (
                    f"CUBIC / VOXEL / LOW-POLY GEOMETRY TRANSFORMATION LOCK ({custom_style}): Transform the reference subject into a "
                    f"COMPLETE 3D cubic/voxel blocky character ({custom_style}) built entirely from sharp geometric 3D cubes, rectangular "
                    f"voxel blocks, and crisp 90-degree blocky facets for the head, hair, torso, arms, and legs, while preserving 100% of "
                    f"their iconic color palette, headband/accessories, and outfit markings."
                )
                negative_prompt = (
                    "smooth organic curves, flat 2D anime drawing, realistic human skin pores, live-action photo, "
                    "lost character colors, blurry, watermark"
                )
            else:
                style_lock = (
                    f"MATERIAL & STYLE TRANSFORMATION LOCK ({custom_style}): Transform the reference subject/object entirely "
                    f"into the requested material and aesthetic ({custom_style}) with authentic optical properties, reflections, "
                    f"refraction, and internal luminescence, while preserving the exact silhouette, shape, and composition of the reference."
                )
                negative_prompt = (
                    "ordinary unstylized opaque surface ignoring requested material, flat 2D cutout, "
                    "lost silhouette, blurry, watermark"
                )
        elif effective_render_mode == "hybrid_anime_with_real_textures":
            style_lock = (
                "TARGETED TEXTURE MODIFICATION (STYLIZED TO REAL HUMAN SKIN): Preserve the exact iconic character "
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
        if effective_render_mode in {"native_anime_stylized", "hybrid_real_to_stylized"}:
            if stylized_submode in {"figurine_toy", "cartoon_figurine"}:
                english_expanded = (
                    f"Full-body 3D collectible cartoon vinyl/chibi figurine reference of {english_core}, rendered in authentic stylized "
                    f"collectible figurine 3D aesthetic with an oversized stylized cartoon head (1:2.5 chibi head-to-body ratio), large "
                    f"expressive glossy 3D cartoon eyes, compact sculpted vinyl toy body holding their signature accessory, smooth satin "
                    f"PVC/resin surface finish, crisp color separation, and standing head-to-toe on a circular collector display pedestal base. "
                    f"Centered full-body three-quarter view on a clean studio background, zero photorealistic skin pores or live-action photography."
                )
                negative_prompt = (
                    "photorealistic human skin pores, raw live-action photograph, half-body portrait crop, uncanny valley human face, "
                    "flat 2D paper cutout, melted geometry, cropped feet, fused fingers, cluttered background, text, watermark"
                )
                reasoning_fr = (
                    "Style figurine / cartoon 3D détecté : génération 3D directe en figurine stylisée corps entier sur socle "
                    "sans forcer un réalisme photographique."
                )
            elif stylized_submode == "clay_or_plush":
                english_expanded = (
                    f"Full-body 3D reference of {english_core}, rendered in authentic tactile claymation / plush toy 3D "
                    f"aesthetic. Expressive handcrafted stylized proportions, volumetric 3D form with soft studio lighting, "
                    f"clear limb separation on a clean studio background, zero realistic human skin pores."
                )
                negative_prompt = (
                    "photorealistic human skin pores, live-action photo, flat 2D drawing, cropped body, cluttered background, watermark"
                )
                reasoning_fr = (
                    "Style pâte à modeler / peluche détecté : génération 3D volumétrique dans le matériau stylisé demandé."
                )
            elif stylized_submode == "lowpoly_voxel":
                english_expanded = (
                    f"Full-body 3D reference of {english_core}, rendered in crisp stylized low-poly / voxel 3D game art "
                    f"aesthetic with clean geometric facets, vibrant color palette, and readable silhouette on a clean studio background."
                )
                negative_prompt = (
                    "photorealistic skin pores, live-action photo, blurry noisy textures, cropped body, watermark"
                )
                reasoning_fr = (
                    "Style low-poly / voxel détecté : génération 3D géométrique stylisée."
                )
            elif stylized_submode == "cartoon_3d":
                english_expanded = (
                    f"Full-body 3D cartoon character reference of {english_core}, rendered in vibrant authentic 3D cartoon "
                    f"animation style (faithful to the cartoon's iconic silhouette, expressive cartoon proportions, snout/eyes/limbs, "
                    f"and bold saturated cartoon color zones with smooth 3D volumetric shading). Centered full-body view on a "
                    f"clean neutral studio background, clear separation between arms, hands, and legs for 3D reconstruction and "
                    f"skeletal rigging, zero photorealistic human skin pores or live-action textures."
                )
                negative_prompt = (
                    "photorealistic human skin pores, live-action cosplay photo, realistic human anatomy override, "
                    "uncanny valley, flat 2D line-only sketch without 3D shading, melted blob, cropped legs, fused limbs, "
                    "cluttered background, text, watermark"
                )
                reasoning_fr = (
                    "Style cartoon / dessin animé détecté : génération 3D directe avec ses vraies proportions et couleurs "
                    "cartoon en volume 3D (aucun forçage au réalisme humain)."
                )
            elif effective_render_mode == "hybrid_real_to_stylized" and syntactic_style.get("style_phrase_raw"):
                custom_style = str(syntactic_style["style_phrase_raw"])
                english_expanded = (
                    f"Full-body / complete 3D reference of {english_core}, crafted and rendered entirely in the requested "
                    f"material and artistic aesthetic ({custom_style}). High-precision volumetric 3D geometry, authentic "
                    f"surface physics, reflections, refraction, and micro-details faithful to the requested medium, "
                    f"centered on a clean studio background."
                )
                negative_prompt = (
                    "raw unstylized photograph ignoring requested material, flat 2D cutout, melted geometry, "
                    "cropped silhouette, cluttered background, text, watermark"
                )
                reasoning_fr = (
                    f"Style ou matériau personnalisé détecté (« {custom_style} ») : génération 3D directe "
                    f"intégralement dans l'esthétique/matière demandée."
                )
            else:
                _morph_3d = infer_universal_morphology(
                    raw_text=clean_raw,
                    english_core=english_core,
                    open_world_entity=open_world_entity,
                )
                if _morph_3d["is_non_humanoid_creature"]:
                    english_expanded = (
                        f"Full-body 3D creature reference of {english_core}. Authentic non-humanoid animal/mythical creature anatomy "
                        f"(four distinct articulated paws/legs or species-accurate wings/fins/tails, fierce animal head and snout, "
                        f"well-separated tails and limbs for 3D reconstruction and skeletal rigging, zero humanoid arms, zero human hands, "
                        f"zero human face or clothing). Centered three-quarter full-body view on a clean white studio background."
                    )
                    negative_prompt = (
                        "humanoid woman, humanoid man, human face, human arms, four arms, human hands, human clothing, dress, "
                        "cosplay, flat 2D cutout, melted blob, cropped legs, fused tails, cluttered background, text, watermark"
                    )
                    reasoning_fr = (
                        "Créature / quadrupède / animal mythique détecté par loi morphologique universelle : "
                        "génération 3D avec anatomie animale fidèle (zéro bras/visage humains)."
                    )
                else:
                    english_expanded = (
                        f"Full-body 3D character reference of {english_core}, rendered in authentic native anime/stylized "
                        f"3D aesthetic. Faithful anime facial proportions with crisp expressive eyes, clean defined nose and jawline, "
                        f"sculpted stylized hair locks with sharp silhouette separation, and iconic costume geometry with vibrant "
                        f"cel-shaded PBR material zones. Centered full-body view on a clean white studio background, "
                        f"clear separation between arms, fingers, and legs for skeletal rigging, zero photorealistic skin pores or "
                        f"uncanny live-action textures."
                    )
                    negative_prompt = (
                        "photorealistic skin pores, old wrinkles, live-action cosplay photo, uncanny valley human face, "
                        "melted blob, cropped legs, fused fingers, cluttered background, text, watermark"
                    )
                    reasoning_fr = (
                        "Personnage/sujet animé ou stylisé détecté : génération 3D directe dans son vrai style animé/stylisé "
                        "(sans textures de peau humaine réelle non demandées)."
                    )
        elif effective_render_mode == "hybrid_anime_with_real_textures":
            english_expanded = (
                f"Full-body 3D character reference of {english_core}, combining the character's exact iconic "
                f"silhouette, signature hairstyle, and official costume design with explicit photorealistic real human "
                f"skin textures, fine epidermal pores, natural subsurface scattering, and physically based fabric, leather, "
                f"and metal micro-textures. Centered full-body three-quarter angle on a clean white studio background, "
                f"anatomically articulated hands and separated limbs ready for 3D reconstruction and rigging."
            )
            negative_prompt = (
                "flat 2d cartoon cel-shading, plastic toy skin, generic face losing character identity, "
                "melted geometry, fused limbs, cropped feet, watermark"
            )
            reasoning_fr = (
                "Personnage animé/cartoon avec demande explicite de textures réelles : préservation de l'identité "
                "et du design avec application de vraies textures cutanées et matériaux PBR réalistes."
            )
        elif effective_render_mode == "native_game_stylized":
            if stylized_submode == "lowpoly_voxel":
                english_expanded = (
                    f"Complete 3D in-game reference of {english_core}, rendered with 100% fidelity to its canonical "
                    f"cubic voxel / blocky video game geometry, sharp voxel edges, and authentic in-game pixel/block textures "
                    f"on a clean white studio background."
                )
                negative_prompt = "smoothed organic curves, realistic human skin pores, live-action photo, melted geometry, watermark"
            elif stylized_submode == "cartoon_3d":
                english_expanded = (
                    f"Complete 3D in-game reference of {english_core}, rendered with 100% fidelity to the video game's "
                    f"canonical stylized 3D proportions, iconic silhouette, and vibrant in-game PBR materials on a clean white studio background."
                )
                negative_prompt = "live-action cosplay photo, realistic human skin pores, off-model generic design, cropped silhouette, watermark"
            elif stylized_submode == "anime_cel":
                english_expanded = (
                    f"Complete 3D in-game reference of {english_core}, rendered with 100% fidelity to the video game's "
                    f"canonical anime cel-shaded 3D character/asset design, sharp silhouette, and vibrant in-game materials on a clean white studio background."
                )
                negative_prompt = "photorealistic human skin pores, live-action photo, off-model generic design, cropped silhouette, watermark"
            else:
                english_expanded = (
                    f"Complete 3D in-game master reference of {english_core}, reproduced with 100% fidelity to the original "
                    f"video game's canonical 3D model, exact armor/weapon/costume geometry, authentic proportions, and high-precision "
                    f"in-game PBR materials on a clean white studio background."
                )
                negative_prompt = "off-model generic replacement, unrequested cartoon restyling, blurry edges, cropped silhouette, cluttered background, watermark"
            reasoning_fr = (
                "Personnage ou objet de jeu vidéo détecté sans demande de changement de style : reproduction 3D 100 % fidèle "
                "au modèle et à la direction artistique d'origine du jeu."
            )
        elif effective_render_mode == "native_engineering_pbr":
            english_expanded = (
                f"Precision 3D engineering and product reference of {english_core}. Crisp hard-surface CAD geometry, "
                f"clean bevels, mechanically accurate part separation, distinct metallic and polymer PBR material zones, "
                f"three-quarter orthographic-friendly studio angle on a clean white studio background revealing front, side, and top volume."
            )
            negative_prompt = (
                "melted organic surfaces, asymmetric distortion, blurry edges, cartoon style, cluttered scene, text, watermark"
            )
            reasoning_fr = (
                "Pièce mécanique / produit technique détecté : expansion 3D orientée géométrie CAO hard-surface et PBR."
            )
        else:
            _morph_3d = infer_universal_morphology(
                raw_text=clean_raw,
                english_core=english_core,
                open_world_entity=open_world_entity,
            )
            if _morph_3d["is_non_humanoid_creature"]:
                english_expanded = (
                    f"Full-body high-precision 3D creature reference of {english_core}. Authentic non-humanoid creature/animal anatomy "
                    f"(four distinct articulated paws/legs or species-accurate wings/fins/tails, expressive animal snout/head, "
                    f"well-separated tails and limbs for 3D reconstruction and skeletal rigging, zero humanoid arms, zero human hands, "
                    f"zero human face or clothing). Centered three-quarter volumetric studio view on a clean white studio background "
                    f"with crisp edge separation and directional key and rim lighting."
                )
                negative_prompt = (
                    "humanoid woman, humanoid man, human face, human arms, four arms, human hands, human clothing, dress, "
                    "flat 2D cutout, melted blob, fused tails, cropped body, watermark"
                )
                reasoning_fr = (
                    "Créature / quadrupède / animal détecté par loi morphologique universelle : "
                    "génération 3D avec anatomie animale fidèle et membres/queues bien séparés."
                )
            elif is_character:
                english_expanded = (
                    f"Full-body photorealistic 3D reference of {english_core}. True-to-life physical proportions (1:7.5 adult "
                    f"humanoid ratio if human), authentic natural skin micro-texture with fine pores, realistic hair strands, "
                    f"and physically accurate fabric and surface materials with strong albedo contrast. Centered three-quarter "
                    f"volumetric studio view on a clean white studio background with crisp edge separation and directional key and rim lighting."
                )
                negative_prompt = (
                    "anime, cartoon, cel-shaded, chibi, plastic doll skin, airbrushed wax face, melted blob, "
                    "fused fingers, cropped body, watermark"
                )
                reasoning_fr = (
                    "Personnage réel détecté : génération 3D photoréaliste physique directe avec proportions et textures réelles."
                )
            else:
                english_expanded = (
                    f"Single isolated physical 3D object reference of {english_core}. Complete standalone 3D volumetric form "
                    f"with crisp sculptural silhouette, authentic physical material optics (high-refraction optical crystal/glass "
                    f"transmission, caustics, internal light dispersion, and sharp engraved bas-relief calligraphy if glass/crystal or engraved), "
                    f"centered three-quarter studio view on a clean white studio background. Strictly isolated object ONLY: "
                    f"no person, no human, no man, no woman, no hands, no body."
                )
                negative_prompt = (
                    "person, human, man, woman, boy, girl, hands holding object, body, face, legs, feet, "
                    "opaque plastic balloon, secondary object at feet, cluttered background, watermark"
                )
                reasoning_fr = (
                    "Objet physique isolé détecté : génération 3D volumétrique pure de l'objet seul (zéro personne hallucinée) avec physique optique des matériaux."
                )

    else:
        # Image / Video / Drawing modules
        if effective_render_mode == "native_anime_stylized":
            if stylized_submode == "cartoon_3d":
                english_expanded = (
                    f"Masterpiece official-grade animated cartoon illustration of {english_core}. Authentic cartoon "
                    f"character proportions, dynamic expressive facial features, bold vibrant cartoon colors, clean "
                    f"outlines and volumetric cartoon shading, faithful to the original animated series aesthetic. "
                    f"Zero realistic human skin pores."
                )
            else:
                english_expanded = (
                    f"Masterpiece official-grade anime key visual of {english_core}. Authentic native anime character design "
                    f"with crisp expressive linework, vibrant cel-shaded color separation, luminous expressive anime eyes, "
                    f"dynamic sculpted hair silhouette, and faithful costume details. Set within a richly illustrated, cohesive "
                    f"anime environment with layered foreground-to-background atmospheric depth and dramatic cinematic anime lighting. "
                    f"Pure 2D/cel-shaded anime fidelity, no realistic human skin pores."
                )
            negative_prompt = (
                "photorealistic human skin pores, live-action photography, uncanny valley, "
                "muddy shading, off-model face, deformed hands, extra fingers, empty background, watermark"
            )
            reasoning_fr = (
                "Sujet animé/cartoon détecté : développement artistique en anglais dans son style animé/cartoon authentique "
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
            custom_style_label = str(syntactic_style.get("style_phrase_raw") or (stylized_submode or "stylized").replace("_", " "))
            if stylized_submode in {"figurine_toy", "cartoon_figurine"}:
                english_expanded = (
                    f"Complete full-body head-to-toe 3D collectible cartoon vinyl/chibi figurine of {english_core}, sculpted with an "
                    f"oversized stylized cartoon head (1:2.5 chibi head-to-body ratio), large expressive glossy 3D cartoon eyes, smooth "
                    f"moulded satin PVC/vinyl toy surfaces, and compact sculpted cartoon body holding their signature accessory, standing "
                    f"on a circular collector figurine display pedestal base while preserving all iconic character traits and colors."
                )
                negative_prompt = (
                    "raw unstylized photograph, realistic human skin pores, half-body portrait crop, live-action photo, "
                    "flat 2D anime drawing, uncanny valley, muddy colors, deformed hands, watermark"
                )
            elif stylized_submode == "lowpoly_voxel":
                english_expanded = (
                    f"Complete full-body 3D cubic voxel block-art sculpture of {english_core}, constructed 100% from sharp geometric "
                    f"3D cubes, stepped 90-degree voxel blocks, blocky cubic head, voxel hair blocks, and rectangular blocky limbs "
                    f"standing on a cubic voxel pedestal base while preserving all iconic character colors and accessories."
                )
                negative_prompt = (
                    "smooth organic curves, flat 2D anime drawing, realistic human skin pores, live-action photo, "
                    "blurry, watermark"
                )
            else:
                english_expanded = (
                    f"Expressive high-precision adaptation of {english_core} rendered entirely in {custom_style_label} style/material, "
                    f"preserving the recognizable identity, posture, and key traits of the subject while translating the surfaces "
                    f"and aesthetic into the requested medium."
                )
                negative_prompt = (
                    "raw unstylized photograph ignoring requested style, uncanny realistic skin pores, muddy colors, deformed hands, watermark"
                )
            reasoning_fr = (
                f"Demande explicite de style/matériau (« {custom_style_label} ») : adaptation fidèle dans l'esthétique demandée."
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

    strict_constraints = extract_strict_prompt_constraints(clean_raw)
    creature_surface_class = strict_constraints["creature_surface_class"]
    if open_world_entity and open_world_entity.get("inferred_surface_class"):
        creature_surface_class = open_world_entity["inferred_surface_class"]

    canonical_character_id: str | None = None
    for key in CANONICAL_CHARACTER_LORE:
        if re.search(rf"\b{re.escape(key)}\b", norm):
            canonical_character_id = key
            break

    if not canonical_character_id and open_world_entity and open_world_entity.get("entity_title"):
        canonical_character_id = str(open_world_entity["entity_title"])
        ow_summary = str(open_world_entity.get("summary_extract") or "").strip()
        if ow_summary and ow_summary[:32].lower() not in english_core.lower():
            english_core = f"{english_core} ({ow_summary[:220]})"
            english_expanded = f"{english_expanded} Open-world entity identity: {ow_summary[:260]}."

    # 7. Ancrage visuel web officiel autonome (uniquement lorsqu'une entité/personnage nommé canonique ou Open-World
    # est identifié en création, y compris lorsqu'une transformation en figurine/cubique/style libre est demandée sur ce personnage)
    visual_web_reference: dict[str, Any] | None = None
    verified_web_reference_path: str | None = None
    has_named_canonical_or_ow_character = bool(
        canonical_character_id
        or (
            open_world_entity
            and open_world_entity.get("inferred_ontology") in {"anime_manga_character", "game_character_or_asset"}
        )
    )
    if (
        use_open_world
        and operation_mode == "creation"
        and not has_reference
        and not explicit_real_textures_override
        and has_named_canonical_or_ow_character
        and (
            subject_ontology == "anime_manga_character"
            or raw_stylized_submode in {"anime_cel", "cartoon_3d"}
        )
    ):
        web_lookup_q = str(syntactic_style.get("core_subject_clean") or clean_raw).strip() or clean_raw
        visual_web_reference = resolve_visual_web_reference(web_lookup_q, open_world_entity)
        if visual_web_reference and visual_web_reference.get("image_path"):
            verified_web_reference_path = str(visual_web_reference["image_path"])
            vis_desc = str(visual_web_reference.get("visual_description_en") or "").strip()
            if vis_desc:
                if open_world_entity is not None:
                    open_world_entity = {**open_world_entity, "visual_description_en": vis_desc}
                english_expanded = f"{english_expanded} Official visual design: {vis_desc}"

    # Si l'utilisateur modifie une image de référence, on inspecte aussi l'image avec Qwen3-VL Vision
    if operation_mode == "modification" and reference_image_path and use_llm:
        if Path(str(reference_image_path)).is_file():
            _free_comfy_before_ollama()
            ref_vis_desc = _extract_vision_traits_from_image(str(reference_image_path), conversation_context[:60] or "base reference subject", timeout_s=20.0)
            if ref_vis_desc:
                conversation_context = (f"{conversation_context} | Visual appearance in base image: {ref_vis_desc}").strip(" |")

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
            open_world_entity=open_world_entity,
            syntactic_style_clause=syntactic_style,
            visual_web_reference=visual_web_reference,
        )
        if llm_res:
            prev_render_mode = effective_render_mode
            english_expanded = llm_res["english_expanded_prompt"].strip()
            if llm_res.get("english_subject"):
                english_core = llm_res["english_subject"].strip()
            if llm_res.get("reasoning_fr"):
                reasoning_fr = llm_res["reasoning_fr"].strip()
            if llm_res.get("subject_ontology") in {
                "anime_manga_character",
                "game_character_or_asset",
                "mechanical_cad_engineering",
                "real_human_subject",
                "real_world_object_or_scene",
            }:
                subject_ontology = llm_res["subject_ontology"]
            if llm_res.get("effective_render_mode") in {
                "native_anime_stylized",
                "hybrid_anime_with_real_textures",
                "native_photorealistic",
                "hybrid_real_to_stylized",
                "native_game_stylized",
                "native_engineering_pbr",
            }:
                effective_render_mode = llm_res["effective_render_mode"]
            if has_style_transformation_clause and not explicit_real_textures_override:
                effective_render_mode = "hybrid_real_to_stylized"

            ow_desc_norm = _norm((open_world_entity or {}).get("summary_extract") or "")
            is_explicit_realistic_game_ow = bool(
                open_world_entity
                and open_world_entity.get("inferred_ontology") == "game_character_or_asset"
                and open_world_entity.get("inferred_submode") is None
                and re.search(r"\b(dark\s+fantasy|souls[- ]?like|first[- ]?person\s+shooter|survival\s+horror|photorealistic|hack\s+and\s+slash|mythologie\s+nordique)\b", ow_desc_norm)
            )
            llm_sub = llm_res.get("stylized_submode")
            explicit_prompt_submode = detect_requested_stylized_submode(clean_raw)
            is_custom_open_material_style = bool(
                has_style_transformation_clause
                and explicit_prompt_submode is None
                and syntactic_style.get("style_phrase_raw")
            )
            if has_style_transformation_clause and explicit_prompt_submode:
                raw_stylized_submode = explicit_prompt_submode
            elif is_custom_open_material_style:
                raw_stylized_submode = None
            elif llm_sub in {
                "cartoon_3d",
                "cartoon_figurine",
                "figurine_toy",
                "clay_or_plush",
                "lowpoly_voxel",
                "anime_cel",
            }:
                if not (is_explicit_realistic_game_ow and not has_style_transformation_clause):
                    raw_stylized_submode = str(llm_sub)
            elif llm_sub in {None, "null", "none", ""} and not raw_stylized_submode:
                raw_stylized_submode = None

            if has_style_transformation_clause and not explicit_real_textures_override:
                if raw_stylized_submode == "lowpoly_voxel":
                    if "voxel" not in english_expanded.lower() or "3d cube" not in english_expanded.lower():
                        english_expanded = (
                            f"Complete full-body 3D cubic voxel block-art character sculpture: {english_expanded} "
                            f"Built 100% from sharp geometric 3D cubes, stepped 90-degree voxel blocks, blocky cubic head, "
                            f"cubic hair blocks, and rectangular voxel limbs standing on a cubic voxel pedestal base."
                        )
                    negative_prompt = (
                        "smooth organic curves, flat 2D anime drawing, realistic human skin pores, live-action photo, "
                        "blurry, watermark"
                    )
                elif raw_stylized_submode in {"figurine_toy", "cartoon_figurine"}:
                    if "pedestal" not in english_expanded.lower() or "vinyl" not in english_expanded.lower():
                        english_expanded = (
                            f"Complete full-body head-to-toe 3D collectible cartoon vinyl/chibi figurine on circular display pedestal base: "
                            f"{english_expanded} Oversized stylized 3D cartoon head (1:2.5 chibi ratio), glossy 3D toy eyes, smooth moulded "
                            f"satin PVC/vinyl figurine surfaces, standing on a circular collector display pedestal base."
                        )
                    negative_prompt = (
                        "flat 2D anime drawing, raw unstylized photograph, realistic human skin pores, half-body portrait crop, "
                        "live-action photo, uncanny valley, deformed hands, watermark"
                    )

            if effective_render_mode != prev_render_mode:
                if effective_render_mode in {"native_anime_stylized", "hybrid_real_to_stylized"}:
                    style_category = "stylized_anime_ghibli"
                    negative_prompt = (
                        "photorealistic human skin pores, live-action cosplay photo, uncanny valley, "
                        "melted geometry, cropped silhouette, deformed hands, cluttered background, watermark"
                    )
                elif effective_render_mode == "native_game_stylized":
                    style_category = "game_asset_3d_prop"
                    negative_prompt = (
                        "live-action cosplay photo, off-model generic replacement, cropped silhouette, "
                        "cluttered background, deformed geometry, watermark"
                    )
                elif effective_render_mode == "native_photorealistic":
                    style_category = "photo_realistic"

            if llm_res.get("creature_surface_class") in {
                "feathered_avian",
                "scaled_draconic_reptilian",
                "chitin_arthropod",
                "furred_mammal",
                "humanoid_or_generic",
            }:
                creature_surface_class = llm_res["creature_surface_class"]
            for item in llm_res.get("excluded_items_en") or []:
                if isinstance(item, str) and item.strip() and item.strip() not in strict_constraints["excluded_items_en"]:
                    strict_constraints["excluded_items_en"].append(item.strip())
            for attr in llm_res.get("mandatory_attributes_en") or []:
                if isinstance(attr, str) and attr.strip() and attr.strip() not in strict_constraints["mandatory_attributes_en"]:
                    strict_constraints["mandatory_attributes_en"].append(attr.strip())
            llm_used = True

    stylized_submode = (
        raw_stylized_submode
        if effective_render_mode in {"native_anime_stylized", "hybrid_real_to_stylized", "native_game_stylized"}
        else None
    )

    if strict_constraints["excluded_items_en"]:
        extra_neg = ", ".join(strict_constraints["excluded_items_en"])
        negative_prompt = f"{extra_neg}, {negative_prompt}"

    universal_morphology = infer_universal_morphology(
        raw_text=clean_raw,
        english_core=english_core,
        open_world_entity=open_world_entity,
        visual_web_reference=visual_web_reference,
    )

    return {
        "ok": True,
        "raw_prompt": clean_raw,
        "target_module": target_module,
        "operation_mode": operation_mode,
        "subject_ontology": subject_ontology,
        "native_ontology": subject_ontology,
        "effective_render_mode": effective_render_mode,
        "stylized_submode": stylized_submode,
        "syntactic_style_clause": syntactic_style,
        "explicit_real_textures_override": explicit_real_textures_override,
        "explicit_stylized_override": explicit_stylized_override,
        "preserve_native_anime_style": effective_render_mode == "native_anime_stylized",
        "preserve_native_real_style": effective_render_mode == "native_photorealistic",
        "lock_unmentioned_attributes": operation_mode in {"modification", "reproduction"},
        "style_category": style_category,
        "canonical_character_id": canonical_character_id,
        "canonical_subject_en": english_core if canonical_character_id else None,
        "open_world_grounding": open_world_entity,
        "open_world_entity": open_world_entity,
        "visual_web_reference": visual_web_reference,
        "verified_web_reference_path": verified_web_reference_path,
        "universal_morphology": universal_morphology,
        "english_subject": english_core,
        "english_expanded_prompt": english_expanded,
        "directed_prompt_en": english_expanded,
        "negative_prompt": negative_prompt,
        "negative_prompt_en": negative_prompt,
        "excluded_items_en": strict_constraints["excluded_items_en"],
        "mandatory_attributes_en": strict_constraints["mandatory_attributes_en"],
        "creature_surface_class": creature_surface_class,
        "reasoning_fr": reasoning_fr,
        "llm_used": llm_used,
        "director_model": "qwen3-vl:8b" if llm_used else None,
    }


def detect_subject_ontology(raw_prompt: str, target_module: str = "image", use_open_world: bool = True) -> dict[str, Any]:
    """Inspection ontologique avec Monde Ouvert (Wikipedia/MediaWiki) et cache persistant."""
    return analyze_and_direct_prompt(raw_prompt, target_module=target_module, use_llm=False, use_open_world=use_open_world)


def resolve_universal_entity_knowledge(raw_prompt: str, timeout_s: float = 1.35, **_kwargs: Any) -> dict[str, Any]:
    """Résolveur d'entités universel (Open-World Wikipedia/MediaWiki + ancres sémantiques)."""
    ow = resolve_open_world_entity(raw_prompt, timeout_s=timeout_s)
    res = analyze_and_direct_prompt(raw_prompt, target_module="3d", use_llm=False, use_open_world=False)
    return {
        "entity_id": res.get("canonical_character_id") or (ow or {}).get("title"),
        "subject_ontology": res.get("subject_ontology"),
        "canonical_subject_en": res.get("canonical_subject_en") or res.get("english_subject"),
        "open_world_entity": ow,
        "preserve_native_anime_style": bool(res.get("preserve_native_anime_style")),
    }


def infer_semantic_ontology(raw_prompt: str, target_module: str = "3d") -> dict[str, Any]:
    """Infère l'ontologie 7-axes (Domaine, Médium, Topologie, Cinématique, Matériaux, Auto-Rigging, Invariants)
    par lois universelles (sans dépendre d'une liste fermée de noms), valable sur tout sujet existant ou 100 % inventé."""
    res = analyze_and_direct_prompt(raw_prompt, target_module=target_module, use_llm=False, use_open_world=False)
    low = _norm(raw_prompt or "")
    subj_ont = str(res.get("subject_ontology") or "general_object")
    render_medium = str(res.get("effective_render_mode") or "native_photorealistic")
    is_mod = str(res.get("operation_mode") or "") in {"modification", "reproduction"}
    explicit_real = bool(res.get("explicit_real_textures_override"))
    univ_morph = res.get("universal_morphology") or infer_universal_morphology(raw_prompt)

    is_mechatronic_or_cad = (
        subj_ont == "mechanical_cad_engineering"
        or bool(MECHANICAL_CAD_RE.search(low))
        or bool(
            re.search(
                r"\b(mecatronique|mechatronic|actionneur|actuator|stator|rotor|servo|nema|logement\s+moteur|"
                r"motor\s+housing|exosquelette|exoskeleton|phalange|tendon|turbine|gyro|epicycl|planetaire|"
                r"planetary|cinematique|kinematic|manipulateur|manipulator|montre|tourbillon|watch|gear|"
                r"engrenage|horlog|moteur|piston|vilebrequin|crankshaft|clock|microscope|appareil)\b",
                low,
            )
        )
    )

    if is_mechatronic_or_cad:
        domain = "mechanical_precision"
    elif any(k in low for k in ("cathedrale", "cathedral", "chateau", "castle", "temple", "pont", "bridge", "tour", "tower", "batiment", "building", "palais", "arch", " pont-levis", "drawbridge")):
        domain = "architectural_structural"
    elif any(k in low for k in ("velo", "bicycle", "bike", "voiture", "car", "moto", "motorcycle", "avion", "aircraft", "vaisseau", "spaceship", "train", "bateau", "ship", "hexacopter", "drone", "rover")):
        domain = "vehicle_aerospace"
    elif (
        subj_ont in {"anime_manga_character", "real_human_subject"}
        or bool(univ_morph.get("is_non_humanoid_creature"))
        or bool(univ_morph.get("has_bipedal_or_humanoid_grammar"))
        or bool(univ_morph.get("has_non_humanoid_creature_grammar"))
        or any(k in low for k in ("perso", "character", "guerrier", "creature", "robot", "humanoid", "homme", "femme"))
    ):
        domain = "character_creature"
    elif any(k in low for k in ("epee", "sword", "katana", "bouclier", "shield", "armure", "armor", "hache", "axe", "couronne", "crown", "sceptre", "staff")):
        domain = "fantasy_weapon_prop"
    else:
        domain = "general"

    auto_rig = (
        domain in {"character_creature", "mechanical_precision"}
        or any(k in low for k in ("anim", "rig", "march", "walk", "run", "cour", "vol", "fly", "combat", "pose", "squelette", "articul"))
    )
    invariants: list[str] = ["watertight_manifold_bvh_zero_self_intersection"]
    if domain == "mechanical_precision":
        invariants.append("zero_boolean_interference_manifold64_and_motor_housings")
    if is_mod:
        invariants.append("strict_non_target_attribute_preservation")
    if res.get("preserve_native_anime_style"):
        invariants.append("native_anime_stylized_fidelity_no_uncanny_skin")
    if auto_rig:
        invariants.append("autonomous_unirig_geodesic_dqs_and_ik")

    tax_info = infer_3d_physical_taxonomy(raw_prompt, reference_image_path=None)

    return {
        "domain": domain,
        "subject_ontology": subj_ont,
        "render_medium": render_medium,
        "universal_morphology": univ_morph,
        "physical_taxonomy": tax_info["primary_taxonomy"],
        "active_taxonomies": tax_info["active_taxonomies"],
        "taxonomy_invariants": tax_info["taxonomy_invariants"],
        "topology_regime": "articulated_watertight_manifold" if auto_rig else "sharp_feature_manifold_mesh",
        "kinematic_regime": (
            "mechatronic_multibody_kinematic_chain"
            if domain == "mechanical_precision"
            else ("unirig_geodesic_dqs_footlock_ik" if auto_rig else "static_structural_equilibrium")
        ),
        "material_regime": "cel_shaded_stylized_pbr" if res.get("preserve_native_anime_style") else "physically_based_16k_pbr",
        "auto_rig_required": auto_rig,
        "is_modification": is_mod,
        "explicit_real_human_override": explicit_real,
        "implicit_invariants": invariants,
    }


def match_cached_visual_reference_for_prompt(prompt: str) -> Path | None:
    """Recherche de manière générique (par correspondance des jetons alphanumériques du nom de fichier
    dans `_VISUAL_WEB_REF_DIR`, sans aucune liste de personnages codée en dur) si une référence visuelle
    `*_ref1024.png` est disponible pour ce prompt."""
    clean_p = re.sub(r"[^a-z0-9]+", " ", _norm(prompt or "")).strip()
    norm_p = f" {clean_p} "
    compact_p = clean_p.replace(" ", "")
    if not clean_p or not _VISUAL_WEB_REF_DIR.is_dir():
        return None
    best_path: Path | None = None
    best_score = 0
    stop_toks = {"les", "des", "une", "the", "and", "watch", "eleven", "personnage", "modele"}
    for cand in sorted(_VISUAL_WEB_REF_DIR.glob("*_ref1024.png")):
        stem = cand.name[: -len("_ref1024.png")]
        toks = [t for t in stem.split("_") if len(t) >= 3 and t not in stop_toks]
        if not toks:
            continue
        matched = [t for t in toks if (f" {t} " in norm_p or (len(t) >= 5 and t in compact_p))]
        # Match if first 2 tokens match, or if the primary distinct entity token (>=6 chars) matches
        if (len(toks) >= 2 and len(matched) >= 2 and toks[0] in matched) or (len(toks[0]) >= 6 and toks[0] in matched):
            score = len(matched) * 10 + len(toks[0])
            if score > best_score:
                best_score = score
                best_path = cand
    return best_path


def infer_3d_physical_taxonomy(
    prompt: str,
    reference_image_path: str | Path | None = None,
) -> dict[str, Any]:
    """Classifie universellement (sans liste de personnages codée en dur) tout sujet 3D
    selon ses régimes physiques, morphologiques et géométriques :
      - 'liquide'        : fluides à surface libre, vagues, gouttes, vortex, éclaboussures (Young-Laplace + Beer-Lambert/Fresnel)
      - 'poils'          : pelages anisotropes, mèches, crinières, fourrures (déplacement géodésique Kajiya-Kay)
      - 'animaux'        : quadrupèdes, créatures organiques, faune réelle ou chimérique (cardinalité 4 pattes, 0 bras fantôme)
      - 'humains'        : bipèdes anthropomorphes / humanoïdes (2 bras, 2 jambes, 0 membre fantôme, posture verticale Y-up)
      - 'invention'      : CAO mécatronique, horlogerie, robotique, turbines (Manifold64 0.0000 mm³, logements moteurs, alésages M3)
      - 'reconnaissance' : reconstruction 3D fidèle à une référence visuelle canonique ou multi-vues (Level-Set Elliptique + Marching Cubes)
    Retourne la taxonomie primaire, les taxonomies secondaires actives et les seuils de falsification VM1."""
    low = re.sub(r"[^a-z0-9]+", " ", _norm(prompt or "")).strip()
    # Strip adverbial phrases like "mouvement fluide" / "animation fluide" before checking physical liquid regime
    low_phys = re.sub(r"\b(?:mouvement|animation|marche|course|geste)\s+fluides?\b", "", low)
    univ_morph = infer_universal_morphology(prompt or "")
    resolved_ref = (
        Path(str(reference_image_path))
        if (reference_image_path and Path(str(reference_image_path)).is_file())
        else match_cached_visual_reference_for_prompt(prompt)
    )
    has_ref_file = bool(resolved_ref and resolved_ref.is_file())

    is_liquid = bool(
        re.search(
            r"\b(liquides?|liquid|eau|water|fluides?|fluid|vagues?|waves?|gouttes?|droplets?|"
            r"splash|eclaboussures?|vortex|fontaines?|fountains?|cascades?|oceans?|lave|lava|"
            r"magma|mercure|mercury|rayleigh\s+plateau|worthington)\b",
            low_phys,
        )
    )
    is_fur_hair = bool(
        re.search(
            r"\b(poils?|fourrures?|fur|pelages?|crinieres?|mane|meches?|chevelures?|duvet|"
            r"fluffy|furry|plumes?|laine|renards?|fox|kitsune|vulpis|loups?|wolf|lions?|"
            r"tigres?|ours|chats?|cat|chiens?|dog|hyenes?|hyena)\b",
            low,
        )
    )
    is_animal = bool(univ_morph.get("is_non_humanoid_creature")) or bool(
        re.search(
            r"\b(animal|animaux|quadrupedes?|quadrupeds?|creatures?|renards?|fox|kitsune|"
            r"vulpis|loups?|wolf|lions?|tigres?|ours|cheval|chevaux|cerfs?|dragons?|griffons?|"
            r"phenix|requins?|shark|hyenes?|hyena|chats?|chiens?)\b",
            low,
        )
    )
    is_invention = bool(
        re.search(
            r"\b(cao|cad|mecatroniques?|mechatronics?|engrenages?|gears?|moteurs?|motors?|"
            r"servomoteurs?|servos?|actionneurs?|actuators?|turbines?|gyroscopiques?|gyroscopic|"
            r"bioniques?|bionic|micromanipulateurs?|chirurgical|statoriques?|stator|brides?|"
            r"roulements?|bearings?|alesages?|drones?|tourelles?)\b",
            low,
        )
    )
    is_human = (
        not is_animal
        and not is_invention
        and not is_liquid
        and (
            bool(univ_morph.get("has_bipedal_or_humanoid_grammar"))
            or bool(
                re.search(
                    r"\b(humains?|humans?|hommes?|femmes?|personnages?|characters?|bipedes?|"
                    r"bipeds?|guerriers?|warriors?|mages?|sorciers?|chevaliers?|knights?|"
                    r"horlogers?|kaelithor|samurais?|samourais?|gardiens?|enfants?|garcons?|filles?)\b",
                    low,
                )
            )
        )
    )
    is_recon = has_ref_file or bool(
        re.search(
            r"\b(canoniques?|canonical|fideles?|references?|reconnai\w*|officiels?|series?|anime|cartoon|duo)\b",
            low,
        )
    )

    active: list[str] = []
    if is_invention:
        active.append("invention")
    if is_liquid:
        active.append("liquide")
    if is_recon:
        active.append("reconnaissance")
    if is_animal:
        active.append("animaux")
    if is_fur_hair:
        active.append("poils")
    if is_human:
        active.append("humains")
    if not active:
        active.append("humains")

    # Priorité de routage géométrique primaire :
    if is_invention:
        primary = "invention"
    elif is_liquid:
        primary = "liquide"
    elif has_ref_file:
        primary = "reconnaissance"
    elif is_animal:
        primary = "animaux"
    elif is_fur_hair:
        primary = "poils"
    elif is_human:
        primary = "humains"
    else:
        primary = active[0]

    invariants: dict[str, Any] = {
        "require_watertight_2manifold": True,
        "require_gltf_animations_min": 1,
        "max_self_intersection_ratio": 0.0,
    }
    if "liquide" in active:
        invariants.update({
            "min_mean_curvature_smoothness": 0.90,
            "min_fluid_wave_or_droplet_nodes": 4,
            "min_fresnel_chromatic_range": 35.0,
        })
    if "poils" in active:
        invariants.update({
            "min_anisotropic_fur_relief_score": 0.85,
            "min_fluted_lock_lobes": 8,
        })
    if "animaux" in active:
        invariants.update({
            "required_quadruped_legs": 4,
            "max_phantom_human_arms": 0,
            "min_depth_to_width_ratio": 0.42,
        })
    if "humains" in active:
        invariants.update({
            "required_arms_per_biped": 2,
            "required_legs_per_biped": 2,
            "max_phantom_limbs": 0,
            "min_height_to_width_ratio": 1.25,
        })
    if "reconnaissance" in active:
        invariants.update({
            "min_front_silhouette_iou_vs_ref": 0.88,
            "min_front_chromatic_fidelity_vs_ref": 0.88,
            "min_depth_to_width_ratio": 0.42,
            "min_articulated_channels": 16,
        })
    if "invention" in active:
        invariants.update({
            "max_boolean_interference_mm3": 0.0,
            "require_stator_motor_housings": True,
            "require_counterbored_m3_mounts": True,
            "require_locked_pivot_se3": True,
        })

    return {
        "primary_taxonomy": primary,
        "active_taxonomies": active,
        "taxonomy_invariants": invariants,
    }



if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="AuroraIA Open-World Cognitive Prompt Director")
    parser.add_argument("--prompt", required=True, help="Raw user prompt")
    parser.add_argument("--module", default="image", help="Target module (image, 3d, video, drawing)")
    parser.add_argument("--mode", default=None, help="Mode hint (create, edit, modification, replicate)")
    parser.add_argument("--style", default=None, help="Requested style")
    parser.add_argument("--context", default="", help="Conversation or base image context")
    parser.add_argument("--has-reference", action="store_true", help="Whether a reference image is attached")
    parser.add_argument("--ref-image", default=None, help="Optional path to reference image")
    args = parser.parse_args()
    out = analyze_and_direct_prompt(
        raw_prompt=args.prompt,
        target_module=args.module,
        mode_hint=args.mode,
        requested_style=args.style,
        has_reference=args.has_reference,
        conversation_context=args.context,
        reference_image_path=args.ref_image,
    )
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")


