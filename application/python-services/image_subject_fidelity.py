#!/usr/bin/env python3
"""Verrou de fidélité du sujet pour FLUX.2 — moteur Python (CLI de missions, bancs).

Même règle que ``application/src/services/imageSubjectFidelity.ts`` et
``application/src/utils/inscriptionText.ts`` (module Image natif, web/tunnel, CLI
Node) : un test de parité (``tests_agi/test_image_subject_fidelity.py``) compare
les deux implémentations sur les mêmes demandes.

Sans modèle de langage, il dit :
- le texte exact à écrire dans l'image (« avec l'inscription Rayen » : du texte,
  pas une personne nommée Rayen) ;
- l'objet demandé et sa catégorie exacte (un vase reste un vase, jamais un flacon) ;
- sa forme, sa matière, sa couleur ;
- si une personne ou un animal est réellement demandé.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_QUOTED_RE = re.compile(r"[\"“«‹]\s*([^\"”»›\n]{1,60}?)\s*[\"”»›]")
_CUE = (r"(?:inscriptions?|inscrite?s?|[eé]crit(?:e|es|s|ure)?|grav(?:[eé]e?s?|ure)|marqu[eé]e?s?|texte|mots?|noms?|"
        r"pr[eé]noms?|lettres?|lettrage|message|slogan|devise|initiales?|signature|[eé]tiquette|label)")
_CUE_RE = re.compile(
    r"(?:^|[\s,;(['’])" + _CUE
    + r"(?=\s*(?::\s*|\s+)(?:au\s+(?:nom|pr[eé]nom)\s+(?:de\s+|d['’]\s*)|(?:de|du|d['’])\s+|(?:le|la|les|l['’])\s*"
      r"(?:(?:nom|pr[eé]nom|mot|texte)\s+)?)?(?:(?:nom|pr[eé]nom|mot|texte)\s+(?:de\s+|d['’]\s*)?)?"
      r"([^\s,;:!?()]+(?:\s+[^\s,;:!?()]+){0,3}))",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "sur", "dessus", "dessous", "dedans", "devant", "derriere", "derrière", "autour", "au", "aux", "a", "à",
    "en", "avec", "et", "ou", "dans", "sous", "pour", "qui", "que", "de", "des", "du", "d", "le", "la", "les",
    "un", "une", "grave", "gravé", "gravee", "gravée", "graves", "gravés", "ecrit", "écrit", "ecrite", "écrite",
    "peint", "peinte", "dore", "doré", "doree", "dorée", "dorees", "dorées", "blanc", "blanche", "noir", "noire",
    "rouge", "rose", "bleu", "bleue", "vert", "verte", "or", "argent", "argente", "argenté", "style",
    "lettres", "cursive", "calligraphie", "calligraphique", "majuscules", "minuscules", "police", "gros", "grosses",
    "petites", "petits", "elegantes", "élégantes", "elegant", "élégant", "manuscrite", "manuscrit", "relief",
    "on", "with", "and", "in", "the", "of", "engraved", "written", "painted", "golden", "gold",
    "inscription", "inscriptions", "texte", "nom", "prenom", "prénom", "mot",
}
_NOT_TEXT = re.compile(
    r"^(?:lisible|lisibles|clair|claire|net|nette|propre|aucun|aucune|pas|sans|personnalise|personnalisé|personnalisee|"
    r"personnalisée|dessus|dessous|elegant|élégant|elegante|élégante|dore|doré|doree|dorée|grave|gravé|gravee|gravée|"
    r"ecrit|écrit|ecrite|écrite|en|de|du|des|un|une|le|la|les|sur)$",
    re.IGNORECASE,
)
_NEGATED_TEXT_RE = re.compile(
    r"\b(?:sans|aucun(?:e)?|pas\s+de|no|without)\s+(?:texte|inscriptions?|[eé]criture|lettres?|text|lettering|writing)\b",
    re.IGNORECASE,
)


def _clean_candidate(raw: str) -> str:
    kept: List[str] = []
    for word in raw.strip().split():
        bare = word.strip("'’\"“«").rstrip("'’\"”».")
        if not bare or bare.lower() in _STOP_WORDS:
            break
        kept.append(bare)
    return " ".join(kept).strip()


def extract_inscription_texts(raw: str) -> List[str]:
    """Textes à écrire dans l'image, dans l'ordre de la demande, sans doublon."""
    text = (raw or "").strip()
    if not text or _NEGATED_TEXT_RE.search(text):
        return []
    out: List[str] = []
    seen = set()

    def push(value: str) -> None:
        v = re.sub(r"\s+", " ", value or "").strip()
        if not v or len(v) > 60 or _NOT_TEXT.match(v):
            return
        if v.lower() in seen:
            return
        seen.add(v.lower())
        out.append(v)

    quoted = list(_QUOTED_RE.finditer(text))
    for m in quoted:
        push(m.group(1))
    spans = [(m.start(), m.end()) for m in quoted]
    for m in _CUE_RE.finditer(text):
        at = m.end()
        if any(a <= at < b for a, b in spans):
            continue
        cand = m.group(1) or ""
        if re.match(r"^[\"“«‹]", cand):
            continue
        push(_clean_candidate(cand))
    return out


def strip_inscription_spans(raw: str) -> str:
    """Retire de la demande les textes à écrire (une recherche de sujet ne doit pas les lire)."""
    texts = extract_inscription_texts(raw)
    out = _QUOTED_RE.sub(" ", raw or "")
    for t in texts:
        out = re.sub(r"(^|[^\w])" + re.escape(t) + r"(?=$|[^\w])", r"\1 ", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip()


@dataclass
class _Noun:
    pattern: str
    en: str
    guard: Optional[str] = None
    confusions: Tuple[str, ...] = ()
    figurative: bool = False


_OBJECTS: List[_Noun] = [
    _Noun(r"\bvases?\b", "vase", "a decorative vase: an open-topped vessel with a wide opening at the top",
          ("bottle", "perfume bottle", "flask", "flacon", "decanter", "jar with lid", "stopper", "cork")),
    _Noun(r"\bflacons?\b", "flacon", "a small glass flacon (bottle) with a stopper", ("vase",)),
    _Noun(r"\bbouteilles?\b", "bottle", "a bottle with a narrow neck", ("vase",)),
    _Noun(r"\bcarafes?\b", "carafe", "a carafe for pouring water or wine"),
    _Noun(r"\bpots?\s+de\s+fleurs?\b|\bcache[- ]?pots?\b", "flower pot", "a flower pot for a plant", ("vase",)),
    _Noun(r"\bbocal|\bbocaux\b", "jar", "a glass jar"),
    _Noun(r"\btasses?\b", "cup", "a cup with a handle", ("mug",)),
    _Noun(r"\bmugs?\b", "mug", "a ceramic mug with a handle"),
    _Noun(r"\bbols?\b", "bowl", "an open bowl"),
    _Noun(r"\bassiettes?\b", "plate", "a flat plate"),
    _Noun(r"\btheieres?\b", "teapot", "a teapot with spout, handle and lid"),
    _Noun(r"\bverres?\s+a\s+vin\b|\bcoupes?\s+de\s+champagne\b", "wine glass", "a stemmed glass"),
    _Noun(r"\bbougies?\b", "candle", "a candle with a wick"),
    _Noun(r"\bbougeoirs?\b", "candle holder"),
    _Noun(r"\blampes?\b", "lamp"),
    _Noun(r"\bboites?\b|\bcoffrets?\b", "box", "a lidded box"),
    _Noun(r"\bbagues?\b|\banneaux?\b", "ring", "a finger ring (jewelry)"),
    _Noun(r"\bcolliers?\b", "necklace"),
    _Noun(r"\bpendentifs?\b|\bmedaillons?\b", "pendant"),
    _Noun(r"\bbracelets?\b", "bracelet"),
    _Noun(r"\bboucles?\s+d['’ ]?oreilles?\b", "earrings"),
    _Noun(r"\bmontres?\b", "wristwatch"),
    _Noun(r"\bhorloges?\b|\bpendules?\b", "clock"),
    _Noun(r"\bcadres?\s+photo\b|\bcadres?\b", "picture frame"),
    _Noun(r"\bcoussins?\b", "cushion"),
    _Noun(r"\bsacs?\s+a\s+main\b|\bsacs?\b", "bag"),
    _Noun(r"\bchaussures?\b|\bbaskets?\b|\bsneakers?\b", "shoe"),
    _Noun(r"\bgateaux?\b", "cake"),
    _Noun(r"\bplaques?\b", "plaque", "a flat engraved plaque"),
    _Noun(r"\btrophees?\b|\bcoupes?\b", "trophy"),
    _Noun(r"\bmedailles?\b", "medal"),
    _Noun(r"\bporte[- ]?cles?\b", "keychain"),
    _Noun(r"\bt[- ]?shirts?\b|\btee[- ]?shirts?\b", "t-shirt", "a t-shirt laid flat or on a hanger",
          ("person wearing the t-shirt",)),
    _Noun(r"\bcasquettes?\b", "cap"),
    _Noun(r"\bchaises?\b|\bfauteuils?\b", "chair"),
    _Noun(r"\btables?\b", "table"),
    _Noun(r"\bepees?\b|\bsabres?\b", "sword"),
    _Noun(r"\bcasques?\b", "helmet", "an empty helmet, nobody wearing it"),
    _Noun(r"\bcouteaux?\b", "knife"),
    _Noun(r"\bstylos?\b", "pen"),
    _Noun(r"\blivres?\b", "book"),
    _Noun(r"\bcarnets?\b", "notebook"),
    _Noun(r"\bpeluches?\b", "plush toy", figurative=True),
    _Noun(r"\bstatuettes?\b|\bstatues?\b|\bfigurines?\b|\bbustes?\b", "statue", figurative=True),
    _Noun(r"\bpoupees?\b", "doll", figurative=True),
    _Noun(r"\bsculptures?\b", "sculpture"),
    _Noun(r"\bvoitures?\b", "car"),
    _Noun(r"\bmotos?\b", "motorcycle"),
    _Noun(r"\bvelos?\b", "bicycle"),
    _Noun(r"\bmaisons?\b", "house"),
    _Noun(r"\bbouquets?\b", "bouquet of flowers"),
    _Noun(r"\blogos?\b", "logo"),
]

_SHAPES: List[Tuple[str, str]] = [
    (r"coeurs?|cœurs?", "heart"), (r"etoiles?", "star"), (r"lunes?|croissants?\s+de\s+lune", "crescent moon"),
    (r"cercles?|ronds?|boules?|spheres?", "round"), (r"carres?", "square"), (r"cubes?", "cube"),
    (r"gouttes?(?:\s+d['’ ]?eau)?", "teardrop"), (r"fleurs?", "flower"), (r"roses?", "rose"), (r"papillons?", "butterfly"),
    (r"diamants?", "diamond"), (r"spirales?", "spiral"), (r"triangles?", "triangle"), (r"ovales?|oeufs?", "oval"),
    (r"chats?", "cat"), (r"hiboux?|chouettes?", "owl"), (r"coquillages?", "seashell"), (r"feuilles?", "leaf"),
    (r"nuages?", "cloud"), (r"arbres?", "tree"), (r"pommes?", "apple"), (r"hexagones?", "hexagon"), (r"vagues?", "wave"),
    (r"cranes?", "skull"), (r"main", "hand"), (r"visage", "face"),
]
_MATERIALS: List[Tuple[str, str]] = [
    (r"\b(?:en\s+)?verre\s+souffle\b", "hand-blown glass"),
    (r"\b(?:en\s+)?verre\b|\bvitre\b", "glass"), (r"\bcristal\b", "crystal"),
    (r"\b(?:en\s+)?ceramique\b", "ceramic"), (r"\b(?:en\s+)?porcelaine\b", "porcelain"), (r"\b(?:en\s+)?gres\b", "stoneware"),
    (r"\bterre\s+cuite\b", "terracotta"), (r"\b(?:en\s+)?bois\b", "wooden"), (r"\b(?:en\s+)?marbre\b", "marble"),
    (r"\b(?:en\s+)?pierre\b", "stone"), (r"\b(?:en\s+)?metal\b", "metal"), (r"\ben\s+or\b|\bdore(?:e)?\b", "gold"),
    (r"\ben\s+argent\b|\bargente(?:e)?\b", "silver"), (r"\b(?:en\s+)?cuivre\b", "copper"), (r"\b(?:en\s+)?bronze\b", "bronze"),
    (r"\b(?:en\s+)?laiton\b", "brass"), (r"\b(?:en\s+)?acier\b", "steel"), (r"\b(?:en\s+)?plastique\b", "plastic"),
    (r"\b(?:en\s+)?cuir\b", "leather"), (r"\b(?:en\s+)?tissu\b", "fabric"), (r"\b(?:en\s+)?resine\b", "resin"),
]
_FINISHES: List[Tuple[str, str]] = [
    (r"\btransparent(?:e)?s?\b", "transparent"), (r"\bopaque\b", "opaque"), (r"\bmat(?:e)?\b", "matte"),
    (r"\bbrillant(?:e)?s?\b|\bvernis(?:se)?\b|\bemaille(?:e)?\b", "glossy glazed"),
]
_COLORS: List[Tuple[str, str]] = [
    (r"\brouge(?:s)?\b", "red"), (r"\brose(?:s)?\b(?!\s+(?:des|de))", "pink"), (r"\bbleu(?:e|s|es)?\b", "blue"),
    (r"\bvert(?:e|s|es)?\b", "green"), (r"\bjaune(?:s)?\b", "yellow"), (r"\borange(?:s)?\b", "orange"),
    (r"\bviolet(?:te|s|tes)?\b", "purple"), (r"\bnoir(?:e|s|es)?\b", "black"), (r"\bblanc(?:he|s|hes)?\b", "white"),
    (r"\bgris(?:e|es)?\b", "grey"), (r"\bmarron\b|\bbrun(?:e)?\b", "brown"), (r"\bturquoise\b", "turquoise"),
    (r"\bbeige\b", "beige"), (r"\bbordeaux\b", "burgundy"),
]
_HUMAN_REQUEST_RE = re.compile(
    r"\b(?:personnes?|gens|homme|hommes|femme|femmes|enfants?|bebes?|fille|filles|garcon|garcons|ado|adolescent(?:e)?|"
    r"vieil(?:le|lard)|dame|monsieur|portrait|selfie|visage|personnage|perso|heros|heroine|guerrier(?:e)?|chevalier|mage|"
    r"sorcier(?:e)?|ninja|samourai|pirate|princesse?|roi|reine|mannequin|modele\s+humain|tenu(?:e)?\s+(?:par|dans)|"
    r"dans\s+(?:la|les|sa|ses)\s+mains?|main(?:s)?\s+qui|people|person|man|woman|girl|boy|child|human|character|someone|"
    r"astronaute|cycliste|danseu(?:r|se)|famille|couple|bride|mariee?)\b"
)
_ANIMAL_REQUEST_RE = re.compile(
    r"\b(?:chats?|chatons?|chiens?|chiots?|oiseaux?|oiseau|chevaux|cheval|lapins?|renards?|loups?|lions?|tigres?|ours|"
    r"poissons?|dragons?|papillons?|hiboux?|chouettes?|souris|elephants?|dauphins?|animal|animaux|creatures?|pokemon|"
    r"cat|dog|bird|horse|animal|creature)\b"
)
_SHAPE_RE = re.compile(
    r"\ben\s+forme\s+(?:de\s+|d['’ ]\s*)(?:petit(?:e)?\s+|grand(?:e)?\s+)?([a-z'’ -]{2,30}?)"
    r"(?=$|[\s,.;!?](?:avec|et|en|sur|dans|qui|de\s+couleur|aux?|a)\b|[,.;!?])"
)


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t.replace("œ", "oe").lower()).strip()


def _first(table: List[Tuple[str, str]], text: str) -> Optional[str]:
    for pattern, value in table:
        if re.search(pattern, text):
            return value
    return None


@dataclass
class SubjectFidelity:
    request: str
    inscriptions: List[str] = field(default_factory=list)
    noun_en: Optional[str] = None
    guard: Optional[str] = None
    confusions: List[str] = field(default_factory=list)
    shape_en: Optional[str] = None
    shape_fr: Optional[str] = None
    material_en: Optional[str] = None
    finish_en: Optional[str] = None
    color_en: Optional[str] = None
    wants_human: bool = False
    wants_animal: bool = False
    object_only: bool = False
    figurative: bool = False

    def summary(self) -> Dict[str, object]:
        return {
            "noun": self.noun_en, "shape": self.shape_en, "shapeFr": self.shape_fr, "material": self.material_en,
            "color": self.color_en, "inscriptions": list(self.inscriptions), "wantsHuman": self.wants_human,
            "wantsAnimal": self.wants_animal, "objectOnly": self.object_only,
        }


def analyze_subject_fidelity(request: str) -> SubjectFidelity:
    inscriptions = extract_inscription_texts(request)
    body = _norm(strip_inscription_spans(request))
    noun: Optional[_Noun] = None
    noun_at = 10 ** 9
    for entry in _OBJECTS:
        m = re.search(entry.pattern, body)
        if m and m.start() < noun_at:
            noun, noun_at = entry, m.start()
    shape_match = _SHAPE_RE.search(body)
    shape_fr_raw = shape_match.group(1).strip() if shape_match else ""
    shape_en = None
    if shape_fr_raw:
        for pattern, value in _SHAPES:
            if re.fullmatch(pattern, shape_fr_raw):
                shape_en = value
                break
    body_no_shape = body.replace(shape_match.group(0), " ", 1) if shape_match else body
    wants_human = bool(_HUMAN_REQUEST_RE.search(body_no_shape))
    wants_animal = bool(_ANIMAL_REQUEST_RE.search(body_no_shape))
    figurative = bool(noun and noun.figurative)
    return SubjectFidelity(
        request=(request or "").strip(),
        inscriptions=inscriptions,
        noun_en=noun.en if noun else None,
        guard=noun.guard if noun else None,
        confusions=list(noun.confusions) if noun else [],
        shape_en=shape_en,
        shape_fr=None if shape_en else (shape_fr_raw or None),
        material_en=_first(_MATERIALS, body_no_shape),
        finish_en=_first(_FINISHES, body_no_shape),
        color_en=_first(_COLORS, body_no_shape),
        wants_human=wants_human,
        wants_animal=wants_animal,
        object_only=bool(noun) and not wants_human and not wants_animal and not figurative,
        figurative=figurative,
    )


def _article(word: str) -> str:
    return "an" if re.match(r"^[aeiou]", word, re.IGNORECASE) else "a"


def build_subject_lock_line(f: SubjectFidelity) -> str:
    """Phrase de tête du prompt positif (vide si aucun objet n'est reconnu)."""
    if not f.noun_en:
        return ""
    descriptors = [d for d in (f.color_en, f.finish_en, f"{f.shape_en}-shaped" if f.shape_en else None, f.material_en) if d]
    core = f"{' '.join(descriptors)} {f.noun_en}".strip()
    head = (f"Requested object: {_article(core)} {core}" if (f.wants_human or f.wants_animal)
            else f"Main subject: {_article(core)} single {core}")
    parts = [head]
    if f.guard:
        parts.append(f"it is {f.guard}")
    if f.shape_en:
        parts.append(f"its whole silhouette and body are clearly shaped like a {f.shape_en}")
    elif f.shape_fr:
        parts.append(f"its whole silhouette is shaped like « {f.shape_fr} » (French)")
    if f.inscriptions:
        quoted = " and ".join(f'"{t}"' for t in f.inscriptions)
        parts.append(f"with the inscription {quoted} clearly lettered on its surface, spelled exactly as written")
    line = ", ".join(parts) + "."
    if f.object_only:
        line += f" Still life: the {f.noun_en} is the only subject, standing on its own, unattended, nobody in the frame."
    return line


def build_inscription_line(f: SubjectFidelity) -> str:
    if not f.inscriptions:
        return ""
    quoted = ", ".join(f'"{t}"' for t in f.inscriptions)
    return f"Exact lettering required: {quoted} — written once, spelled exactly letter for letter, no other words or letters."


def fidelity_negative_terms(f: SubjectFidelity) -> List[str]:
    """Termes du vrai prompt négatif propres à la demande."""
    out: List[str] = []
    if f.object_only:
        out += ["person", "people", "woman", "man", "child", "human face", "portrait", "hands", "fingers",
                "human body", "mannequin", "animal", "blurry", "low detail", "watermark", "extra objects", "duplicate object"]
    out += list(f.confusions)
    if f.inscriptions:
        out += ["misspelled lettering", "extra words", "random letters"]
    return out
