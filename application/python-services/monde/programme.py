"""Lecture d'une phrase en PROGRAMME DE SCÈNE typé et validé (aurora.programme-scene.v1).

Le modèle de langage local lit UNE phrase française (« un intérieur de maison complet », « un village
médiéval au bord d'une rivière ») et écrit un programme dans les vocabulaires fermés de
`monde.vocabulaire` ; Python le valide de façon déterministe, puis applique la LOI DE COMPLÉTUDE.

Ce que fait le modèle, ce que fait Python :
  - le modèle choisit le type de scène, les pièces, leurs surfaces et adjacences, les zones d'une ville, le
    biome d'un paysage, et SEULEMENT les meubles que la phrase nomme ;
  - Python vérifie chaque clé contre son vocabulaire, chaque nombre contre ses bornes, la copie exacte du
    style, la cohérence type ↔ section, l'existence des cibles de relation et des pièces adjacentes, la
    connexité du logement et la présence du jour ; il normalise les parts des zones et ramène une surface
    aberrante dans la fourchette de sa fonction (avec une note) ;
  - la loi de complétude (générale, jamais par sujet) : une pièce complète — marquée complète, ou toute pièce
    quand la phrase dit le logement complet, ou toute pièce pour laquelle la phrase ne nomme aucun meuble —
    reçoit `FONCTIONS_PIECES[f]["meubles_typiques"]` fusionnés avec les meubles demandés (la demande l'emporte
    sur les nombres, les relations et les matériaux ; les catégories exclues par la phrase sont retirées) ;
  - tout terme du vocabulaire (fonction de pièce, catégorie de meuble) que la phrase nomme doit figurer dans
    le programme d'un intérieur.

Une réponse hors contrat reçoit UNE correction avec la liste nominative des erreurs ; encore invalide, le
résultat est `source: "indisponible"` avec les raisons. Jamais de programme par défaut silencieux.

Appel au modèle : même serveur, même piège et même choix de modèle que `lecture_demande` (Ollama
`/api/chat`, `format: "json"` avec `think: false` — un SCHÉMA JSON passé en `format` est ignoré avec
`think: false` sur Ollama 0.31.1, mesuré le 14/11/2026 ; la consigne liste donc les clés permises et Python
valide).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from typing import Any, Callable

from lecture_demande import MODELE_SOUHAITE, OLLAMA_URL, _dans, _extraire_json, _plat

from . import vocabulaire as voc

SCHEMA = "aurora.programme-scene.v1"

# Bornes du contrat (mètres, m², étages).
HAUTEUR_PLAFOND = (2.3, 3.6)
TAILLE_VILLE = (100.0, 1500.0)
LARGEUR_RUES = (6.0, 40.0)
TAILLE_NATURE = (50.0, 1000.0)
ETAGES = (1, 60)
NOMBRE_MEUBLES = (1, 12)
MAX_PIECES = 16
TOLERANCE_SURFACE = (0.5, 1.5)   # surface admise = [0,5 × min ; 1,5 × max] de la fonction
EAUX_NATURE = ("aucune", "lac", "riviere", "mer")

# Un programme de maison complète fait 1 500 à 2 500 jetons ; un 27B partagé GPU/CPU écrit 5 à 15 jetons/s.
DELAI_S = float(os.environ.get("AURORA_MONDE_PROGRAMME_DELAI_S", "900"))
GARDER_CHARGE = os.environ.get("AURORA_MONDE_KEEP_ALIVE", "15m")


# ── Consigne au modèle, construite depuis les vocabulaires (aucune liste recopiée à la main) ──────────

def _liste_fonctions() -> str:
    lignes = []
    for cle, f in voc.FONCTIONS_PIECES.items():
        typiques = ",".join(c for c, _n, _r in f["meubles_typiques"])
        jour = "fenêtre" if f["fenetre"] else "aveugle"
        lignes.append(f"{cle} ({f['surface'][0]:g}-{f['surface'][1]:g} m², {jour}; typique: {typiques})")
    return "; ".join(lignes)


def _liste_categories(exterieur: bool) -> str:
    return ", ".join(f"{cle}[{','.join(c['materiaux'])}]" for cle, c in voc.CATEGORIES.items()
                     if bool(c["exterieur"]) == exterieur)


def _liste_relations() -> str:
    avec = [k for k, r in voc.RELATIONS.items() if r["cible"]]
    sans = [k for k, r in voc.RELATIONS.items() if not r["cible"]]
    return f"sans cible (cible null) : {', '.join(sans)} ; avec cible (une catégorie de la même pièce) : {', '.join(avec)}"


def _liste_materiaux() -> str:
    return ", ".join(cle + ("*" if m["coloriable"] else "") for cle, m in voc.MATERIAUX.items())


def _liste_zones() -> str:
    return "; ".join(f"{cle} ({z['description']}, {z['etages'][0]}-{z['etages'][1]} étages)"
                     for cle, z in voc.ZONES_VILLE.items())


def _liste_styles() -> str:
    return "; ".join(f"{cle} ({s['description']}, étage {s['hauteur_etage']:g} m)" for cle, s in voc.STYLES_ARCHI.items())


def _liste_biomes() -> str:
    return "; ".join(f"{cle} (sol {b['sol']}: " + ",".join(f"{c}{'/' + s if s else ''}" for c, s, _d in b["vegetation"]) + ")"
                     for cle, b in voc.BIOMES.items())


def consigne() -> str:
    """Consigne système complète. Les listes sont lues dans `monde.vocabulaire` à chaque appel."""
    return (
        "Tu traduis UNE phrase française en programme de scène 3D. Réponds UNIQUEMENT par un objet JSON, sans "
        "texte autour. Chaque clé de vocabulaire est copiée EXACTEMENT d'une liste ci-dessous (minuscules, "
        "tirets bas, sans accents) ; n'invente jamais une clé.\n"
        "FORME :\n"
        '{"type_scene": "interieur|ville|nature", "titre": "<titre court en français>", '
        '"style": {"texte": <mots EXACTS de la phrase qui donnent le style, l\'époque ou le rendu, ou null>, '
        '"architecture": <STYLE ou null>}, '
        '"interieur": {"complet": <bool>, "hauteur_plafond": <m>, "pieces": [{"nom": "<nom unique>", '
        '"fonction": <FONCTION>, "surface_m2": <nombre>, "adjacente_a": [<noms d\'autres pièces>], '
        '"sol": <MATERIAU ou null>, "murs": <MATERIAU ou "MATERIAU:COULEUR" ou null>, "complete": <bool>, '
        '"meubles": [{"categorie": <CATEGORIE>, "nombre": <1-12>, "relations": [[<RELATION>, <CATEGORIE ou null>]], '
        '"materiaux": {"<emplacement>": <MATERIAU>}}], "sans": [<CATEGORIE exclue par la phrase>]}]} ou null, '
        '"ville": {"taille_m": [<largeur>, <profondeur>], "trame": <TRAME>, "zones": [{"type": <ZONE>, "part": <0-1>}], '
        '"etages": [<min>, <max>] ou null, "largeur_rues_m": <6-40>, "riviere": <bool>, "arbres_alignement": <bool>, '
        '"voitures": <bool>, "style": <STYLE>} ou null, '
        '"nature": {"biome": <BIOME>, "relief": <RELIEF>, "taille_m": <50-1000>, "eau": "aucune|lac|riviere|mer"} ou null, '
        '"notes": ["<ce qui ne peut pas être représenté>"], "raison": "<une phrase : pourquoi ces choix>"}\n'
        "RÈGLES :\n"
        "- Une seule section remplie, celle de type_scene ; les deux autres valent null. interieur = un logement ou "
        "des pièces vues de l'intérieur ; ville = une ville, un village, un quartier, des rues ; nature = un paysage "
        "sans ville (forêt, plage, montagne, désert, prairie).\n"
        "- style.texte : le plus court morceau copié mot pour mot de la phrase qui donne le style ou le rendu "
        "(« réaliste », « haussmannien », « médiéval », « de verre »), jamais toute la phrase ; null si la phrase "
        "n'en donne pas. style.architecture : le STYLE que la phrase implique, sinon null.\n"
        "- INTÉRIEUR. pieces : une entrée par pièce réelle (« deux chambres » = deux pièces aux noms distincts) ; "
        "nom : nom français lisible et court (« salon », « chambre 2 »), repris tel quel dans adjacente_a. "
        "Garde toutes les pièces que la phrase nomme. Si la phrase nomme une maison ou un appartement sans lister "
        "ses pièces, propose l'ensemble typique et cohérent d'un logement réel. Un LOGEMENT (maison, appartement, "
        "loft, studio) est toujours habitable : même quand la phrase liste d'autres pièces, ajoute celles qui "
        "manquent parmi entrée, séjour (salon), salle de bain ou salle d'eau, wc, et un couloir si besoin ; seule "
        "une phrase qui parle d'UNE pièce (« une chambre », « une cuisine ») reste à cette pièce. Un « coin » "
        "(coin bureau, coin repas) ou un espace ouvert est une pièce adjacente à la pièce principale. surface_m2 "
        "dans la fourchette de la fonction (« grande » vers le haut, « petite » vers le bas). adjacente_a : les "
        "pièces reliées par une porte ou une ouverture ; une pièce dite « ouverte » (cuisine ouverte) est adjacente "
        "au séjour ; l'entrée est adjacente au séjour ou au couloir ; toutes les pièces doivent être reliées entre "
        "elles ; au moins une pièce à fenêtre. hauteur_plafond entre 2.3 et 3.6 m, selon "
        "l'époque (ancien et haussmannien hauts, moderne vers 2.5, loft vers 3.5).\n"
        "- meubles : SEULEMENT les meubles que la phrase nomme pour cette pièce ; le mobilier typique de la "
        "fonction est ajouté ensuite automatiquement, ne le recopie pas. [] si la phrase n'en nomme aucun. Une "
        "catégorie au plus une fois par pièce (le nombre va dans « nombre »). relations : [RELATION, null] pour "
        "une relation sans cible, [RELATION, CATEGORIE] sinon, la cible étant un meuble de la même pièce (nommé "
        "ou typique de la fonction) ; « sur » seulement sur un meuble à dessus. materiaux : seulement ceux que la "
        "phrase donne, emplacement pris dans la liste entre crochets de la catégorie. sans : catégories que la "
        "phrase exclut explicitement (« sans télévision »), sinon [].\n"
        "- complete : true si la phrase veut cette pièce complète, meublée ou équipée. complet : true si la "
        "phrase le dit pour tout le logement. sol, murs : null sauf si la phrase ou le style les donne.\n"
        "- VILLE. taille_m de 100 à 1500 m par côté (village 200-400, quartier 300-600, ville 600-1500). zones : "
        "les usages présents et leur part de la surface (parts positives, somme 1), au moins une zone bâtie. "
        "etages : [min, max] si la phrase ou le type de lieu l'impose, sinon null. riviere : true pour un cours "
        "d'eau qui traverse ou longe le lieu (il n'a PAS besoin de zone eau) ; la zone eau est réservée à un plan "
        "d'eau (lac, bassin, port). Un village ou un bourg a un centre ou une place. style : obligatoire.\n"
        "- NATURE. biome, relief, taille_m de 50 à 1000 m, eau.\n"
        "- notes : courtes phrases pour ce que la phrase demande et que ce programme ne sait pas représenter "
        "(mezzanine, étage, escalier, cuisine ouverte sans cloison, objet absent du vocabulaire). [] sinon.\n"
        "VOCABULAIRES :\n"
        f"FONCTION : {_liste_fonctions()}\n"
        f"CATEGORIE (intérieur, [emplacements de matériau]) : {_liste_categories(False)}\n"
        f"RELATION : {_liste_relations()}\n"
        f"MATERIAU (* = coloriable en \"MATERIAU:COULEUR\") : {_liste_materiaux()}\n"
        f"COULEUR : {', '.join(voc.PALETTE)}\n"
        f"STYLE : {_liste_styles()}\n"
        f"ZONE : {_liste_zones()}\n"
        f"TRAME : {', '.join(voc.TRAMES)}\n"
        f"BIOME : {_liste_biomes()}\n"
        f"RELIEF : {', '.join(voc.RELIEFS)}\n"
        "Pas de texte hors du JSON."
    )


# ── Appel au modèle ─────────────────────────────────────────────────────────────────────────────────

def _interroger_ollama(message: str, modele: str, timeout_s: float = DELAI_S) -> str:
    corps = json.dumps({
        "model": modele,
        "stream": False,
        "format": "json",
        "think": False,          # avec la réflexion : 6 à 30+ min par tour sur ce poste (mesuré le 14/11)
        "keep_alive": GARDER_CHARGE,
        "options": {"temperature": 0.0, "num_predict": 3500, "num_ctx": 12288},
        "messages": [{"role": "system", "content": consigne()}, {"role": "user", "content": message}],
    }).encode("utf-8")
    requete = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=corps, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=timeout_s) as reponse:
        return str(json.loads(reponse.read().decode("utf-8")).get("message", {}).get("content", ""))


def _correction(demande: str, reponse: str, erreurs: list[str]) -> str:
    liste = "\n".join(f"{i + 1}. {e}" for i, e in enumerate(erreurs[:40]))
    return (f"{demande}\n\n---\nTa réponse précédente :\n{reponse.strip()[:6000]}\n\n"
            f"Elle enfreint le contrat sur ces points :\n{liste}\n"
            "Rends le programme JSON complet corrigé (toutes les sections), en ne changeant que ce qui est fautif.")


# ── Outils de validation ────────────────────────────────────────────────────────────────────────────

def _texte(v: Any) -> str:
    return " ".join(str(v).split()) if isinstance(v, str) else ""


def _nombre(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.replace(",", "."))
        except ValueError:
            return None
    return None


def _materiau_valide(cle: Any) -> str | None:
    """Message d'erreur, ou None si la clé est un matériau (éventuellement « famille:couleur ») du vocabulaire."""
    if not isinstance(cle, str) or not cle:
        return "doit être une clé de MATERIAU"
    try:
        voc.materiau(cle)
    except KeyError as exc:
        return str(exc.args[0] if exc.args else exc)
    return None


def _mots(texte: str) -> str:
    """Forme de recherche : sans accents ni casse, toute ponctuation (apostrophes comprises) en espace."""
    return " " + " ".join(re.sub(r"[^0-9a-z]+", " ", _plat(texte)).split()) + " "


def _nomme(cle: str, demande_mots: str) -> bool:
    """La clé d'un vocabulaire (« table_basse ») est-elle dite dans la phrase, au singulier ou au pluriel ?"""
    motif = r"\s+".join(re.escape(m) + r"(?:s|x)?" for m in cle.split("_") if m)
    return re.search(r" " + motif + r" ", demande_mots) is not None


def _couvre(cle_dite: str, cle_programme: str) -> bool:
    """Un terme dit est couvert par une clé du programme qui contient tous ses mots (chambre ⊂ chambre_enfant)."""
    return set(cle_dite.split("_")) <= set(cle_programme.split("_"))


# ── Validation par section ──────────────────────────────────────────────────────────────────────────

def _valider_meuble(brut: Any, chemin: str, erreurs: list[str]) -> dict[str, Any] | None:
    if not isinstance(brut, dict):
        erreurs.append(f"{chemin} doit être un objet {{categorie, nombre, relations, materiaux}}")
        return None
    cat = brut.get("categorie")
    if cat not in voc.CATEGORIES:
        erreurs.append(f"{chemin}.categorie {cat!r} n'est pas une CATEGORIE")
        return None
    if voc.CATEGORIES[cat]["exterieur"]:
        erreurs.append(f"{chemin}.categorie {cat!r} est une catégorie d'extérieur, interdite dans une pièce")
        return None
    nombre = _nombre(brut.get("nombre", 1))
    if nombre is None or nombre != int(nombre) or not NOMBRE_MEUBLES[0] <= nombre <= NOMBRE_MEUBLES[1]:
        erreurs.append(f"{chemin}.nombre doit être un entier de {NOMBRE_MEUBLES[0]} à {NOMBRE_MEUBLES[1]}")
        nombre = None
    relations = []
    for j, r in enumerate(brut.get("relations") or []):
        # formes admises : [rel, cible], {"relation": rel, "cible": cible}, "rel"
        if isinstance(r, str):
            r = [r, None]
        elif isinstance(r, dict):
            r = [r.get("relation"), r.get("cible")]
        if not isinstance(r, (list, tuple)) or len(r) not in (1, 2):
            erreurs.append(f"{chemin}.relations[{j}] doit être [RELATION, CATEGORIE ou null]")
            continue
        rel, cible = r[0], (r[1] if len(r) == 2 else None)
        if rel not in voc.RELATIONS:
            erreurs.append(f"{chemin}.relations[{j}] : {rel!r} n'est pas une RELATION")
            continue
        relations.append([rel, cible])
    materiaux = {}
    mats = brut.get("materiaux") or {}
    if not isinstance(mats, dict):
        erreurs.append(f"{chemin}.materiaux doit être un objet {{emplacement: MATERIAU}}")
        mats = {}
    for slot, cle in mats.items():
        if slot not in voc.CATEGORIES[cat]["materiaux"]:
            erreurs.append(f"{chemin}.materiaux : emplacement {slot!r} inconnu pour {cat} "
                           f"(permis : {', '.join(voc.CATEGORIES[cat]['materiaux'])})")
            continue
        message = _materiau_valide(cle)
        if message:
            erreurs.append(f"{chemin}.materiaux.{slot} : {message}")
            continue
        materiaux[slot] = cle
    if nombre is None:
        return None
    return {"categorie": cat, "nombre": int(nombre), "relations": relations, "materiaux": materiaux,
            "origine": "demande"}


def _completer(fonction: str, demandes: list[dict[str, Any]], sans: set[str]) -> list[dict[str, Any]]:
    """Loi de complétude : mobilier typique de la fonction ∪ meubles demandés (la demande l'emporte)."""
    par_cat = {m["categorie"]: m for m in demandes}
    resultat, vus = [], set()
    for cat, nombre, relations in voc.FONCTIONS_PIECES[fonction]["meubles_typiques"]:
        if cat in sans or cat in vus:
            continue
        vus.add(cat)
        if cat in par_cat:
            m = dict(par_cat[cat])
            if not m["relations"]:
                m["relations"] = [[r, c] for r, c in relations]
            resultat.append(m)
        else:
            resultat.append({"categorie": cat, "nombre": int(nombre), "relations": [[r, c] for r, c in relations],
                             "materiaux": {}, "origine": "typique"})
    resultat += [m for m in demandes if m["categorie"] not in vus]
    # une relation typique dont la cible a été exclue par la phrase n'a plus d'objet : on la retire
    presentes = {m["categorie"] for m in resultat}
    for m in resultat:
        if m["origine"] == "typique":
            m["relations"] = [[r, c] for r, c in m["relations"] if c is None or c in presentes]
    return resultat


def _verifier_relations(meubles: list[dict[str, Any]], chemin: str, erreurs: list[str]) -> None:
    presentes = {m["categorie"] for m in meubles}
    for i, m in enumerate(meubles):
        for rel, cible in m["relations"]:
            ou = f"{chemin}.meubles[{m['categorie']}] relation {rel}"
            if not voc.RELATIONS[rel]["cible"]:
                if cible is not None:
                    erreurs.append(f"{ou} ne prend pas de cible : mettre null")
                continue
            if cible is None:
                erreurs.append(f"{ou} exige une cible (une catégorie de la même pièce)")
            elif cible not in voc.CATEGORIES:
                erreurs.append(f"{ou} : cible {cible!r} n'est pas une CATEGORIE")
            elif cible == m["categorie"]:
                erreurs.append(f"{ou} : un meuble ne peut pas se cibler lui-même")
            elif cible not in presentes:
                erreurs.append(f"{ou} : cible {cible!r} absente de la pièce (ajoute-la aux meubles ou change de cible)")
            elif rel == "sur":
                porteur = voc.CATEGORIES[cible]
                pose_sur = voc.CATEGORIES[m["categorie"]]["pose_sur"]
                if not porteur["support"] or (pose_sur and cible not in pose_sur):
                    erreurs.append(f"{ou} : {m['categorie']} ne se pose pas sur {cible}")


def _valider_interieur(brut: Any, demande: str, erreurs: list[str], notes: list[str]) -> dict[str, Any] | None:
    if not isinstance(brut, dict):
        erreurs.append("interieur doit être un objet {complet, hauteur_plafond, pieces}")
        return None
    hauteur = _nombre(brut.get("hauteur_plafond"))
    if hauteur is None or not HAUTEUR_PLAFOND[0] <= hauteur <= HAUTEUR_PLAFOND[1]:
        erreurs.append(f"interieur.hauteur_plafond doit être un nombre de {HAUTEUR_PLAFOND[0]} à {HAUTEUR_PLAFOND[1]} m")
    complet_logement = brut.get("complet") is True
    pieces_brutes = brut.get("pieces")
    if not isinstance(pieces_brutes, list) or not pieces_brutes or len(pieces_brutes) > MAX_PIECES:
        erreurs.append(f"interieur.pieces doit être une liste de 1 à {MAX_PIECES} pièces")
        return None
    pieces: list[dict[str, Any]] = []
    noms: list[str] = []
    for i, p in enumerate(pieces_brutes):
        ch = f"pieces[{i}]"
        if not isinstance(p, dict):
            erreurs.append(f"{ch} doit être un objet")
            continue
        nom = _texte(p.get("nom"))
        if not nom:
            erreurs.append(f"{ch}.nom est vide")
            continue
        if _plat(nom) in {_plat(n) for n in noms}:
            erreurs.append(f"{ch}.nom {nom!r} est déjà pris : chaque pièce a un nom unique")
            continue
        noms.append(nom)
        ch = f"pieces[{nom}]"
        fonction = p.get("fonction")
        if fonction not in voc.FONCTIONS_PIECES:
            erreurs.append(f"{ch}.fonction {fonction!r} n'est pas une FONCTION")
            continue
        lo, hi = voc.FONCTIONS_PIECES[fonction]["surface"]
        surface = _nombre(p.get("surface_m2"))
        if surface is None or surface <= 0:
            erreurs.append(f"{ch}.surface_m2 doit être un nombre positif (fourchette {lo:g}-{hi:g} m²)")
            continue
        if not TOLERANCE_SURFACE[0] * lo <= surface <= TOLERANCE_SURFACE[1] * hi:
            corrigee = min(max(surface, lo), hi)
            notes.append(f"surface de « {nom} » ramenée de {surface:g} à {corrigee:g} m² (fourchette {fonction} "
                         f"{lo:g}-{hi:g} m²)")
            surface = corrigee
        adjacentes = p.get("adjacente_a") or []
        if not isinstance(adjacentes, list):
            erreurs.append(f"{ch}.adjacente_a doit être une liste de noms de pièces")
            adjacentes = []
        piece: dict[str, Any] = {"nom": nom, "fonction": fonction, "surface_m2": round(float(surface), 2),
                                 "adjacente_a": [_texte(a) for a in adjacentes if _texte(a)]}
        for champ in ("sol", "murs"):
            v = p.get(champ)
            if v is not None:
                message = _materiau_valide(v)
                if message:
                    erreurs.append(f"{ch}.{champ} : {message}")
                    v = None
            piece[champ] = v
        sans = []
        for s in p.get("sans") or []:
            if s not in voc.CATEGORIES:
                erreurs.append(f"{ch}.sans : {s!r} n'est pas une CATEGORIE")
            else:
                sans.append(s)
        demandes, vues = [], set()
        for j, m in enumerate(p.get("meubles") or []):
            meuble = _valider_meuble(m, f"{ch}.meubles[{j}]", erreurs)
            if meuble is None:
                continue
            if meuble["categorie"] in vues:
                erreurs.append(f"{ch}.meubles : {meuble['categorie']} figure deux fois (une entrée, avec « nombre »)")
                continue
            if meuble["categorie"] in sans:
                erreurs.append(f"{ch} : {meuble['categorie']} est à la fois demandé et exclu (« sans »)")
                continue
            vues.add(meuble["categorie"])
            demandes.append(meuble)
        complete = p.get("complete") is True or complet_logement or not demandes
        meubles = _completer(fonction, demandes, set(sans)) if complete else demandes
        _verifier_relations(meubles, ch, erreurs)
        piece.update({"complete": complete, "meubles": meubles, "sans": sans})
        pieces.append(piece)
    if not pieces:
        return None
    # adjacences : noms existants, symétrie, connexité, jour
    par_nom = {_plat(p["nom"]): p for p in pieces}
    voisins: dict[str, set[str]] = {p["nom"]: set() for p in pieces}
    for p in pieces:
        propres = []
        for a in p["adjacente_a"]:
            cible = par_nom.get(_plat(a))
            if cible is None:
                erreurs.append(f"pieces[{p['nom']}].adjacente_a : aucune pièce ne s'appelle {a!r}")
            elif cible is p:
                erreurs.append(f"pieces[{p['nom']}].adjacente_a : une pièce n'est pas adjacente à elle-même")
            elif cible["nom"] not in propres:
                propres.append(cible["nom"])
                voisins[p["nom"]].add(cible["nom"])
                voisins[cible["nom"]].add(p["nom"])
        p["adjacente_a"] = propres
    for p in pieces:   # adjacence rendue symétrique : une porte relie deux pièces
        p["adjacente_a"] = sorted(voisins[p["nom"]], key=[q["nom"] for q in pieces].index)
    if len(pieces) == len(noms):
        atteintes, pile = set(), [pieces[0]["nom"]]
        while pile:
            n = pile.pop()
            if n not in atteintes:
                atteintes.add(n)
                pile.extend(voisins[n] - atteintes)
        isolees = [p["nom"] for p in pieces if p["nom"] not in atteintes]
        if isolees:
            erreurs.append(f"pièces non reliées au reste du logement par adjacente_a : {', '.join(isolees)} "
                           "(relie-les directement ou par une entrée ou un couloir)")
    if not any(voc.FONCTIONS_PIECES[p["fonction"]]["fenetre"] for p in pieces):
        erreurs.append("aucune pièce à fenêtre : un logement a au moins une pièce de jour")
    # Loi d'habitabilité : des pièces où l'on dort ET où l'on cuisine forment un logement, qui doit permettre de
    # se laver (essai du 15/11 : un loft « cuisine, coin bureau, chambre » rendu sans aucune salle d'eau).
    groupes = {voc.CATEGORIES[m["categorie"]]["groupe"] for p in pieces for m in p["meubles"]}
    if {"couchage", "cuisine"} <= groupes and "sanitaire" not in groupes:
        erreurs.append("ce logement a de quoi dormir et cuisiner mais aucune pièce d'eau : ajoute une salle_de_bain "
                       "ou une salle_d_eau reliée aux autres pièces")
    # tout terme du vocabulaire dit dans la phrase doit être représenté
    dits = _mots(demande)
    fonctions = {p["fonction"] for p in pieces}
    categories = {m["categorie"] for p in pieces for m in p["meubles"]} | {s for p in pieces for s in p["sans"]}
    for cle in voc.FONCTIONS_PIECES:
        if _nomme(cle, dits) and not any(_couvre(cle, f) for f in fonctions | categories):
            erreurs.append(f"la phrase nomme « {cle.replace('_', ' ')} » mais aucune pièce n'a cette fonction")
    for cle, cat in voc.CATEGORIES.items():
        if cat["exterieur"] or cle in voc.FONCTIONS_PIECES:
            continue
        if _nomme(cle, dits) and not any(_couvre(cle, c) for c in categories):
            erreurs.append(f"la phrase nomme le meuble « {cle} » mais il n'est dans aucune pièce")
    return {"hauteur_plafond": round(hauteur, 2) if hauteur is not None else None, "complet": complet_logement,
            "pieces": pieces}


def _valider_ville(brut: Any, style_archi: str | None, erreurs: list[str], notes: list[str]) -> dict[str, Any] | None:
    if not isinstance(brut, dict):
        erreurs.append("ville doit être un objet")
        return None
    taille = brut.get("taille_m")
    if _nombre(taille) is not None:
        taille = [taille, taille]
    if not isinstance(taille, (list, tuple)) or len(taille) != 2 or any(_nombre(t) is None for t in taille):
        erreurs.append(f"ville.taille_m doit être [largeur, profondeur] de {TAILLE_VILLE[0]:g} à {TAILLE_VILLE[1]:g} m")
        taille = None
    else:
        taille = [float(_nombre(t)) for t in taille]
        if any(not TAILLE_VILLE[0] <= t <= TAILLE_VILLE[1] for t in taille):
            erreurs.append(f"ville.taille_m : chaque côté de {TAILLE_VILLE[0]:g} à {TAILLE_VILLE[1]:g} m")
    trame = brut.get("trame")
    if trame not in voc.TRAMES:
        erreurs.append(f"ville.trame {trame!r} n'est pas une TRAME ({', '.join(voc.TRAMES)})")
    parts: dict[str, float] = {}
    zones_brutes = brut.get("zones")
    if not isinstance(zones_brutes, list) or not zones_brutes:
        erreurs.append("ville.zones doit être une liste non vide de {type, part}")
        zones_brutes = []
    for i, z in enumerate(zones_brutes):
        if isinstance(z, str):
            z = {"type": z, "part": 1.0}
        if not isinstance(z, dict) or z.get("type") not in voc.ZONES_VILLE:
            erreurs.append(f"ville.zones[{i}].type {z.get('type') if isinstance(z, dict) else z!r} n'est pas une ZONE")
            continue
        part = _nombre(z.get("part"))
        if part is None or part < 0:
            erreurs.append(f"ville.zones[{i}].part doit être un nombre positif")
            continue
        parts[z["type"]] = parts.get(z["type"], 0.0) + part
    total = sum(parts.values())
    if zones_brutes and parts and total <= 0:
        erreurs.append("ville.zones : la somme des parts est nulle")
    zones = []
    if total > 0:
        if abs(total - 1.0) > 0.01:
            notes.append(f"parts des zones normalisées (somme {total:g} → 1)")
        zones = [{"type": t, "part": round(p / total, 4)} for t, p in parts.items() if p > 0]
        if not any(voc.ZONES_VILLE[z["type"]]["batie"] for z in zones):
            erreurs.append("ville.zones : au moins une zone bâtie (une ville a des bâtiments)")
    etages = brut.get("etages")
    if etages is not None:
        if (not isinstance(etages, (list, tuple)) or len(etages) != 2 or any(_nombre(e) is None for e in etages)
                or any(_nombre(e) != int(_nombre(e)) for e in etages)):
            erreurs.append("ville.etages doit être [min, max] (entiers) ou null")
            etages = None
        else:
            etages = [int(_nombre(e)) for e in etages]
            if not ETAGES[0] <= etages[0] <= etages[1] <= ETAGES[1]:
                erreurs.append(f"ville.etages : {ETAGES[0]} ≤ min ≤ max ≤ {ETAGES[1]}")
    largeur = _nombre(brut.get("largeur_rues_m"))
    if largeur is None or not LARGEUR_RUES[0] <= largeur <= LARGEUR_RUES[1]:
        erreurs.append(f"ville.largeur_rues_m doit être un nombre de {LARGEUR_RUES[0]:g} à {LARGEUR_RUES[1]:g} m")
    style = brut.get("style") or style_archi
    if style not in voc.STYLES_ARCHI:
        erreurs.append(f"ville.style {style!r} n'est pas un STYLE")
    booleens = {}
    for champ in ("riviere", "arbres_alignement", "voitures"):
        v = brut.get(champ, False)
        if not isinstance(v, bool):
            erreurs.append(f"ville.{champ} doit être true ou false")
        booleens[champ] = v is True
    return {"taille_m": taille, "trame": trame, "zones": zones, "etages": etages,
            "largeur_rues_m": largeur, **booleens, "style": style}


def _valider_nature(brut: Any, erreurs: list[str]) -> dict[str, Any] | None:
    if not isinstance(brut, dict):
        erreurs.append("nature doit être un objet {biome, relief, taille_m, eau}")
        return None
    if brut.get("biome") not in voc.BIOMES:
        erreurs.append(f"nature.biome {brut.get('biome')!r} n'est pas un BIOME")
    if brut.get("relief") not in voc.RELIEFS:
        erreurs.append(f"nature.relief {brut.get('relief')!r} n'est pas un RELIEF")
    taille = _nombre(brut.get("taille_m"))
    if taille is None or not TAILLE_NATURE[0] <= taille <= TAILLE_NATURE[1]:
        erreurs.append(f"nature.taille_m doit être un nombre de {TAILLE_NATURE[0]:g} à {TAILLE_NATURE[1]:g} m")
    eau = brut.get("eau") or "aucune"
    if eau not in EAUX_NATURE:
        erreurs.append(f"nature.eau doit être {', '.join(EAUX_NATURE)}")
    return {"biome": brut.get("biome"), "relief": brut.get("relief"), "taille_m": taille, "eau": eau}


def valider_programme(brut: Any, demande: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Valide une réponse brute du modèle. Rend (programme, []) ou (None, erreurs nominatives)."""
    demande = " ".join(str(demande or "").split())
    if not isinstance(brut, dict):
        return None, ["la réponse n'est pas un objet JSON"]
    erreurs: list[str] = []
    notes = [n for n in (_texte(x) for x in (brut.get("notes") or []) if isinstance(brut.get("notes"), list)) if n]
    type_scene = brut.get("type_scene")
    if type_scene not in voc.TYPES_SCENE:
        erreurs.append(f"type_scene {type_scene!r} doit être {', '.join(voc.TYPES_SCENE)}")
    titre = _texte(brut.get("titre"))
    if not titre or len(titre) > 120:
        erreurs.append("titre doit être un texte court non vide")
    style_brut = brut.get("style") if isinstance(brut.get("style"), dict) else {}
    texte_style = _texte(style_brut.get("texte")) or None
    if texte_style and not _dans(texte_style, demande):
        erreurs.append(f"style.texte {texte_style!r} doit être copié mot pour mot de la phrase (ou null)")
    archi = style_brut.get("architecture") or None
    if archi is not None and archi not in voc.STYLES_ARCHI:
        erreurs.append(f"style.architecture {archi!r} n'est pas un STYLE (ou null)")
    remplies = [s for s in voc.TYPES_SCENE if brut.get(s)]
    if len(remplies) != 1:
        erreurs.append(f"exactement une section parmi {', '.join(voc.TYPES_SCENE)} doit être remplie "
                       f"(remplies : {', '.join(remplies) or 'aucune'})")
    elif type_scene in voc.TYPES_SCENE and remplies[0] != type_scene:
        erreurs.append(f"type_scene vaut {type_scene} mais la section remplie est {remplies[0]}")
    sections: dict[str, Any] = {s: None for s in voc.TYPES_SCENE}
    if type_scene == "interieur" and brut.get("interieur"):
        sections["interieur"] = _valider_interieur(brut["interieur"], demande, erreurs, notes)
    elif type_scene == "ville" and brut.get("ville"):
        sections["ville"] = _valider_ville(brut["ville"], archi, erreurs, notes)
    elif type_scene == "nature" and brut.get("nature"):
        sections["nature"] = _valider_nature(brut["nature"], erreurs)
    if erreurs:
        return None, erreurs
    return {"schema": SCHEMA, "source": "llm", "demande": demande, "type_scene": type_scene, "titre": titre,
            "style": {"texte": texte_style, "architecture": archi}, **sections, "notes": notes,
            "raison": _texte(brut.get("raison"))}, []


# ── Point d'entrée ─────────────────────────────────────────────────────────────────────────────────

def programme_indisponible(demande: str, raison: str, erreurs: list[str] | None = None, **trace: Any) -> dict[str, Any]:
    """Aucun programme : l'appelant ne construit rien et dit pourquoi."""
    return {"schema": SCHEMA, "source": "indisponible", "demande": demande, "type_scene": None, "titre": None,
            "style": {"texte": None, "architecture": None}, "interieur": None, "ville": None, "nature": None,
            "notes": [], "raison": raison[:400], "erreurs": list(erreurs or []), **trace}


def lire_programme(demande: str, *, interroger: Callable[[str], str] | None = None,
                   modele: str | None = None) -> dict[str, Any]:
    """Phrase → programme de scène validé, ou `source: "indisponible"` avec les raisons.

    `interroger` reçoit le message utilisateur (la phrase, puis au besoin la demande de correction) et rend le
    texte du modèle ; il est injectable pour les tests. Sans lui, le modèle local passe par Ollama.
    """
    demande = " ".join(str(demande or "").split())
    if not demande:
        return programme_indisponible("", "demande vide")
    if interroger is None:
        if modele is None:
            modele = os.environ.get("AURORA_MONDE_MODELE") or None
        if modele is None:
            try:
                from llm_disponible import resoudre_modele
                modele = resoudre_modele(MODELE_SOUHAITE, "texte", bavard=False)
            except Exception:  # noqa: BLE001 — sans résolveur, on tente le modèle souhaité
                modele = MODELE_SOUHAITE
        modele_choisi = modele

        def interroger(texte: str) -> str:
            return _interroger_ollama(texte, modele_choisi)
    tours: list[dict[str, Any]] = []
    message, erreurs = demande, []
    for tour in (1, 2):
        debut = time.monotonic()
        try:
            reponse = str(interroger(message))
        except Exception as exc:  # noqa: BLE001 — modèle injoignable ou trop lent : pas de programme inventé
            tours.append({"tour": tour, "duree_s": round(time.monotonic() - debut, 2), "erreur": f"{type(exc).__name__}"})
            return programme_indisponible(demande, f"modèle indisponible : {type(exc).__name__}: {exc}", erreurs,
                                          tours=tours, modele=modele)
        programme, erreurs = valider_programme(_extraire_json(reponse), demande)
        tours.append({"tour": tour, "duree_s": round(time.monotonic() - debut, 2), "erreurs": list(erreurs)})
        if programme is not None:
            programme.update(tours=tours, modele=modele)
            return programme
        message = _correction(demande, reponse, erreurs)
    return programme_indisponible(demande, f"programme hors contrat après correction ({len(erreurs)} erreurs)",
                                  erreurs, tours=tours, modele=modele)


def _nom_fichier(demande: str) -> str:
    return ("_".join(_mots(demande).split())[:70] or "demande") + ".json"


def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path
    analyseur = argparse.ArgumentParser(description="Phrase → programme de scène validé (aurora.programme-scene.v1)")
    analyseur.add_argument("--demande", action="append", required=True, help="répétable : lues une à la fois")
    analyseur.add_argument("--modele", default=None)
    analyseur.add_argument("--dossier", default=None, help="écrit chaque programme dans ce dossier (JSON)")
    arguments = analyseur.parse_args(argv)
    for demande in arguments.demande:
        debut = time.monotonic()
        programme = lire_programme(demande, modele=arguments.modele)
        programme["duree_totale_s"] = round(time.monotonic() - debut, 2)
        if arguments.dossier:
            cible = Path(arguments.dossier) / _nom_fichier(demande)
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(json.dumps(programme, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"demande": demande, "source": programme["source"], "type_scene": programme["type_scene"],
                          "tours": programme.get("tours"), "duree_totale_s": programme["duree_totale_s"],
                          "raison": programme.get("raison") if programme["source"] != "llm" else None},
                         ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
