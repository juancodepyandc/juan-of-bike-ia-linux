#!/usr/bin/env python
"""Prompt de référence d'une demande à sujets nommés : l'identité passe par les pixels du
dossier, le style et la pose par le texte du contrat (15/11/2026).

Ce qui a été mesuré. Run « Zig et Sharko en version réaliste : Zig la hyène qui court et Sharko le
requin qui nage » (`application/output/3d/conversations/zig_sharko_version_zig_168220a6-33de-4571/
juan_bike_1794717743024/`) : les six rendus FLUX venaient du texte seul (ni LoadImage ni
ReferenceLatent dans leurs métadonnées, graines toutes différentes) ; l'identité venait de deux
dictionnaires écrits en dur (`cognitivePromptDirector.ts` et `agi_core/prompt_intelligence.py`,
`CANONICAL_CHARACTER_LORE`) qui se contredisent et que les wikis de la série contredisent ;
« réaliste » a donné une hyène tachetée réelle et un requin générique portant le même short rayé.
§ 1.38 du document maître a observé que l'encodeur Mistral-3 de FLUX.2 dessine les mots du prompt
positif : un mot de vêtement écrit dans le positif, même pour l'interdire, devient un vêtement.

Lois appliquées, pour tout sujet (aucune entrée propre à un nom, aucune lecture de dictionnaire) :
1. Un sujet ancré est « le personnage de l'image de référence k ». Aucun nom ni aucune description
   d'identité n'est écrit : un nom réveille la mémoire de l'encodeur, pas les images du dossier.
2. Les seuls attributs écrits viennent du dossier `aurora.identite-visuelle.v1` (accord d'images
   réelles), formulés positivement. Une clause qui nomme une chose portée ou un nom propre n'est pas
   écrite : elle reste portée par les pixels de l'ancre, et l'écart est rapporté.
3. Le style vient du contrat `aurora.lecture-demande.v2` (`style.texte` + `style.cible`). Quand le
   médium visé diffère du médium d'origine des ancres, le négatif reçoit les marques du médium
   d'origine que la cible ne partage pas.
4. Le négatif est global à l'image : une absence (aucun vêtement) n'y entre que si elle est établie
   pour CHAQUE sujet ; sinon elle effacerait ce que porte un autre sujet.
5. Exactement N sujets entiers côte à côte, de gauche à droite dans l'ordre de la demande, séparés
   par un écart net, sans contact, sur la même ligne de sol, sur un fond neutre uni blanc : le fond
   que `trellis_multi_character.detect_and_crop_characters` sépare (min(RGB) ≥ 240) pour découper
   exactement les sujets que TRELLIS reconstruira.
6. Animation demandée : les repères de pose de repos du pipeline (`REST_POSE_CUES`, passés par
   l'appelant) sont ajoutés ; sans animation, chaque sujet garde l'action demandée.

Ce module n'appelle aucun modèle et n'écrit aucun fichier : il compose du texte. Le rendu se fait
par `flux_reference_synth.synth(positif, run_id, reference_images=references, negative_prompt=negatif)`
(une liste `references` vide = rendu sans `reference_images`).
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Iterable

from flux_reference_synth import NEGATIF_PAR_DEFAUT

SCHEMA = "aurora.reference-identite.v1"
SCHEMA_CONTRAT = "aurora.lecture-demande.v2"
SCHEMA_DOSSIER = "aurora.identite-visuelle.v1"

# Convention sur laquelle repose « sujet k = image k ». Lue le 15/11/2026, jamais mesurée ici.
CONVENTION_MULTI_REFERENCES = (
    "BFL, guide de prompt FLUX.2 (docs.bfl.ml/guides/prompting_guide_flux2, lu le 15/11/2026) : avec "
    "plusieurs images d'entrée, décrire le rôle de chacune (« subject from image 1, style from image 2 ») ; "
    "« image 1 » est la première image fournie ; [dev] : environ 6 références. Côté ComfyUI, chaque "
    "ReferenceLatent ajoute son latent en fin de liste (append=True) et FLUX.2 place la k-ième référence "
    "à l'indice 10·k de ses positions (model_detection : default_ref_method='index', ref_index_scale=10.0) : "
    "le premier maillon accroché au texte est l'image 1. NON MESURÉ sur FLUX.2 [dev] Q4_K_M local : la "
    "liaison image k → personnage k n'a été vérifiée par aucun rendu sur ce poste."
)

# Quatre images au plus, une par sujet : une référence d'environ 1 MP ajoute ≈ 4k jetons
# (estimation du vérificateur, plan du 15/11) ; BFL recommande environ 6 références pour [dev].
MAX_REFERENCES = 4
# Une ancre par sujet : « image k = sujet k » reste exact et chaque référence coûte des jetons au rendu.
MAX_ANCRES_PAR_SUJET = 1
# Un sujet dont l'identité vient d'être REFUSÉE par le juge reçoit une seconde ancre au rendu suivant
# (15/11/2026 : Zig sorti en hyène générique avec une seule ancre ; l'a priori de l'espèce l'emportait).
# Les rôles restent écrits image par image (« reference image 2 shows character 1 »), donc exacts.
MAX_ANCRES_RENFORCEES = 2

# Rendu demandé, par valeur de l'énumération fermée `style.cible` du contrat v2. « autre » et null
# n'ont pas de description : seul le texte de l'utilisateur est transmis.
# Chaque médium est visé À SON MEILLEUR (15/11/2026, « le plus réaliste à la demande ») : une demande
# « réaliste » veut la photographie haut de gamme ; une demande « animée » veut le haut de gamme de
# l'animation — jamais un réalisme de la vie réelle qui en retirerait le charme.
RENDU_PAR_CIBLE = {
    "photo": ("high-end photorealistic rendering with real-world physical materials, natural light and lifelike "
              "eyes, as if photographed"),
    "cel_2d": ("premium hand-drawn animation look: confident clean line art, crisp cel shading with soft "
               "gradients, vibrant harmonious colours, as in a high-end animated feature"),
    "cgi_3d": ("high-end 3D animated-feature look: appealing stylised forms, soft subsurface shading, rich "
               "saturated colours and cinematic soft lighting, as in a premium animation studio film"),
    "figurine": "premium collectible figurine, finely sculpted and hand-painted, photographed in a studio",
}

# Marques que chaque médium laisse sur une image ; elles vont au négatif quand le médium visé
# diffère du médium d'origine des ancres (`attributs.style_origine`, même énumération).
MARQUES_DU_MEDIUM = {
    "cel_2d": ("cartoon", "cel shading", "ink outlines", "flat 2D"),
    "cgi_3d": ("CGI look", "plastic CG shading"),
    "figurine": ("toy figurine", "moulded plastic", "display base"),
    "photo": ("photograph", "photographic realism"),
}

# Traits qu'une cible partage avec d'autres médiums : jamais niés vers elle (une figurine ou un
# rendu CGI d'un personnage dessiné reste « cartoon » de proportions).
TRAITS_PARTAGES_PAR_CIBLE = {
    "cgi_3d": frozenset({"cartoon"}),
    "figurine": frozenset({"cartoon"}),
}

# Absences écrites au négatif quand aucun sujet ne porte rien (plan, étape 3 : « clothing, shorts »).
ABSENCES_VETEMENT = ("clothing", "clothes", "outfit", "garments", "shorts", "trousers", "shirt", "swimwear")

# Choses portées : jamais écrites dans le positif (§ 1.38). Catégorie générale en anglais et en
# français (le modèle de vision peut répondre dans l'une ou l'autre), sans accents (texte
# normalisé), appliquée à tout sujet. « short » au singulier est exclu : en anglais c'est un
# adjectif (short tail). « coat » est gardé : une robe animale s'écrit aussi « coat », mais la
# clause écartée reste portée par les pixels de l'ancre.
_CHOSES_PORTEES = (
    "clothing", "clothes", "clothed", "unclothed", "outfit", "outfits", "garment", "garments",
    "apparel", "attire", "costume", "costumes", "wear", "wears", "wearing", "worn", "dressed",
    "dress", "dresses", "shorts", "trunks", "swimsuit", "swimsuits", "swimwear", "bikini", "pants",
    "trousers", "jeans", "skirt", "skirts", "shirt", "shirts", "t-shirt", "t-shirts", "tshirt",
    "jacket", "jackets", "coat", "coats", "vest", "vests", "waistcoat", "hoodie", "sweater",
    "uniform", "uniforms", "underwear", "suit", "suits", "tunic", "robe", "robes", "gown", "cape",
    "cloak", "scarf", "scarves", "glove", "gloves", "shoe", "shoes", "boot", "boots", "sandal",
    "sandals", "sneakers", "sock", "socks", "hat", "hats", "helmet", "helmets", "accessory",
    "accessories",
    "vetement", "vetements", "sous-vetement", "sous-vetements", "habit", "habits", "habille",
    "habillee", "habilles", "habillees", "tenue", "tenues", "maillot", "maillots", "calecon",
    "calecons", "pantalon", "pantalons", "jupe", "jupes", "chemise", "chemises", "tee-shirt",
    "tee-shirts", "veste", "vestes", "manteau", "manteaux", "gilet", "gilets", "uniforme",
    "uniformes", "echarpe", "echarpes", "gant", "gants", "chaussure", "chaussures", "botte", "bottes",
    "sandale", "sandales", "chaussette", "chaussettes", "chapeau", "chapeaux", "casque", "casques",
    "accessoire", "accessoires",
)
_RX_CHOSE_PORTEE = re.compile(
    r"(?<![\w-])(?:%s)(?![\w-])" % "|".join(sorted(map(re.escape, _CHOSES_PORTEES), key=len, reverse=True)))

# Lecture d'un `attributs.vetements` qui dit l'absence. Seule une réponse faite UNIQUEMENT de mots
# de négation, de mots génériques du vêtement et de mots vides vaut absence (« none », « aucun
# vêtement visible », « it wears nothing ») ; une réponse qui nomme une pièce (« no shorts »,
# « striped shorts ») ou qu'on ne sait pas lire n'affirme aucune absence : les pixels décident.
_NEGATIONS = frozenset({
    "none", "no", "nothing", "without", "naked", "nude", "bare", "unclothed", "undressed",
    "aucun", "aucune", "rien", "sans", "pas", "nu", "nue", "nus", "nues",
})
_VETEMENT_GENERIQUE = frozenset({
    "clothing", "clothes", "clothed", "outfit", "outfits", "garment", "garments", "apparel", "attire",
    "wear", "wears", "wearing", "worn", "vetement", "vetements", "habit", "habits", "tenue", "tenues",
    "porte", "portes", "portee", "portees", "habille", "habillee",
})
_MOTS_VIDES = frozenset({
    "a", "an", "the", "of", "at", "all", "any", "is", "it", "its", "body", "visible", "on",
    "de", "d", "du", "des", "le", "la", "les", "l", "un", "une", "il", "elle", "ne", "n", "est", "corps",
})

_NOMBRES = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
_ORDINAUX = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")


class IdentiteNonEtablie(ValueError):
    """Un sujet nommé n'a aucune ancre établie : l'appelant pose la question (joindre une image ou
    continuer en « identité non vérifiée »), jamais de repli sur un dictionnaire ni sur un nom.

    `sujets` : [{"index", "nom", "raison"}] pour chaque sujet concerné.
    """

    def __init__(self, sujets: list[dict]):
        self.sujets = sujets
        super().__init__("identite non etablie : " + "; ".join(
            "%s (%s)" % (s.get("nom") or "sujet %s" % s.get("index"), s.get("raison") or "raison inconnue")
            for s in sujets))


def _normaliser(texte) -> str:
    """Minuscules, sans accents, espaces réduits : la forme sur laquelle les lois lexicales portent."""
    decompose = unicodedata.normalize("NFD", str(texte or ""))
    sans_accent = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sans_accent.casefold()).strip()


def nomme_une_chose_portee(texte) -> bool:
    """Le texte nomme-t-il une chose portée (vêtement, chaussure, couvre-chef, accessoire) ?"""
    return bool(_RX_CHOSE_PORTEE.search(_normaliser(texte)))


def dit_l_absence_de_vetement(vetements) -> bool:
    """Vrai seulement si `attributs.vetements` affirme sans ambiguïté que rien n'est porté."""
    mots = re.findall(r"[a-z]+", _normaliser(vetements))
    if not mots or not any(mot in _NEGATIONS for mot in mots):
        return False
    return all(mot in _NEGATIONS or mot in _VETEMENT_GENERIQUE or mot in _MOTS_VIDES for mot in mots)


def _contient_un_nom(texte, noms: list[str]) -> bool:
    forme = _normaliser(texte)
    return any(re.search(r"(?<!\w)%s(?!\w)" % re.escape(nom), forme) for nom in noms if nom)


def _clauses(texte) -> list[str]:
    return [c.strip(" .") for c in re.split(r"[;,\n]+", str(texte or "")) if c.strip(" .")]


def _filtrer(morceaux: list[str], *, noms: list[str], sujet, champ: str, ecartes: list[dict]) -> list[str]:
    """Garde les clauses écrivables ; une clause qui nomme une chose portée ou un nom propre est
    écartée (et rapportée) : elle reste portée par les pixels de l'ancre."""
    gardes = []
    for clause in morceaux:
        if nomme_une_chose_portee(clause):
            ecartes.append({"sujet": sujet, "champ": champ, "texte": clause,
                            "raison": "nomme une chose portee : jamais ecrite dans le positif"})
        elif _contient_un_nom(clause, noms):
            ecartes.append({"sujet": sujet, "champ": champ, "texte": clause,
                            "raison": "contient un nom propre : l'identite passe par les pixels"})
        else:
            gardes.append(clause)
    return gardes


def _medium(valeur) -> str | None:
    forme = re.sub(r"[\s-]+", "_", _normaliser(valeur))
    return forme if forme in MARQUES_DU_MEDIUM or forme == "autre" else None


def _verifier_contrat(contrat) -> list[dict]:
    if not isinstance(contrat, dict) or contrat.get("schema") != SCHEMA_CONTRAT:
        raise ValueError("contrat de demande : schema %r attendu" % SCHEMA_CONTRAT)
    if contrat.get("source") != "llm":
        raise ValueError("contrat de demande non lu (source %r) : aucun sujet n'est etabli" % contrat.get("source"))
    sujets = contrat.get("sujets")
    if not isinstance(sujets, list) or not sujets or not all(isinstance(s, dict) for s in sujets):
        raise ValueError("contrat de demande : liste de sujets vide ou invalide")
    return sujets


def _verifier_dossier(dossier) -> list[dict]:
    if not isinstance(dossier, dict) or dossier.get("schema") != SCHEMA_DOSSIER:
        raise ValueError("dossier d'identite : schema %r attendu" % SCHEMA_DOSSIER)
    entrees = dossier.get("sujets")
    if not isinstance(entrees, list) or not all(isinstance(e, dict) for e in entrees):
        raise ValueError("dossier d'identite : liste de sujets invalide")
    indices = []
    for entree in entrees:
        try:
            indices.append(int(entree.get("index")))
        except (TypeError, ValueError):
            raise ValueError("dossier d'identite : sujet sans index entier (%r)" % entree.get("nom")) from None
    if len(set(indices)) != len(indices):
        raise ValueError("dossier d'identite : deux sujets portent le meme index")
    return entrees


def _ancres_lisibles(entree: dict, ecartes: list[dict]) -> list[str]:
    """Ancres d'un sujet établi, dans l'ordre du dossier (médoïde d'abord), sans doublon, présentes
    sur le disque ; un sujet non établi n'en a aucune (pas d'accord entre images)."""
    if not entree.get("etabli"):
        return []
    vues, chemins = set(), []
    for chemin in entree.get("ancres") or []:
        texte = str(chemin or "").strip()
        if not texte:
            continue
        cle = os.path.normcase(os.path.abspath(texte))
        if cle in vues:
            continue
        vues.add(cle)
        if not Path(texte).is_file():
            ecartes.append({"sujet": int(entree["index"]), "champ": "ancres", "texte": texte,
                            "raison": "fichier absent : ancre ignoree"})
            continue
        chemins.append(texte)
    return chemins


def _repartir(candidats: list[tuple[int, list[str]]],
              renforces: Iterable[int] = ()) -> list[tuple[int, list[str]]]:
    """Une ancre par sujet d'abord ; les places restantes (4 au total) vont, dans l'ordre des sujets,
    aux sujets `renforces` (identité refusée au rendu précédent), jusqu'à MAX_ANCRES_RENFORCEES chacun.
    Règle déterministe : aucun autre critère de priorité n'a été mesuré."""
    renforces = {int(i) for i in renforces}
    if len(candidats) > MAX_REFERENCES:
        raise ValueError("%d sujets a ancrer pour %d images de reference au plus : impossible de donner "
                         "une image a chacun" % (len(candidats), MAX_REFERENCES))
    vus: dict[str, int] = {}
    for index, chemins in candidats:
        for chemin in chemins:
            cle = os.path.normcase(os.path.abspath(chemin))
            if vus.setdefault(cle, index) != index:
                raise ValueError("la meme ancre %s est attribuee aux sujets %d et %d" % (chemin, vus[cle], index))
    reste = MAX_REFERENCES - len(candidats)
    plan = []
    for index, chemins in candidats:
        plafond = MAX_ANCRES_RENFORCEES if index in renforces else MAX_ANCRES_PAR_SUJET
        nombre = 1
        while nombre < min(plafond, len(chemins)) and reste > 0:
            nombre += 1
            reste -= 1
        plan.append((index, chemins[:nombre]))
    return plan


def choisir_ancres(dossier: dict) -> list[str]:
    """Une ou deux ancres par sujet établi, dans l'ordre des sujets (index), quatre au total au plus.

    Le dossier met le médoïde du groupe d'accord en premier et la meilleure découpe d'un autre
    domaine ensuite : c'est cet ordre qui est gardé. Plus de quatre sujets établis lèvent ValueError
    (un sujet sans image serait décrit par le texte seul).
    """
    candidats = []
    for entree in sorted(_verifier_dossier(dossier), key=lambda e: int(e["index"])):
        chemins = _ancres_lisibles(entree, [])
        if chemins:
            candidats.append((int(entree["index"]), chemins))
    return [chemin for _, chemins in _repartir(candidats) for chemin in chemins]


def _entree_du_dossier(rang: int, sujet: dict, entrees: list[dict]) -> dict | None:
    """L'entrée du dossier qui décrit le sujet de rang `rang` du contrat : même index et même nom ;
    à défaut, la seule entrée de même nom (dossier numéroté autrement)."""
    nom = _normaliser(sujet.get("nom"))
    for entree in entrees:
        if int(entree["index"]) == rang:
            nom_entree = _normaliser(entree.get("nom"))
            if not nom or not nom_entree or nom_entree == nom:
                return entree
            break
    if nom:
        meme_nom = [e for e in entrees if _normaliser(e.get("nom")) == nom]
        if len(meme_nom) == 1:
            return meme_nom[0]
    return None


def _nombre(n: int) -> str:
    return "%s (%d)" % (_NOMBRES[n], n) if n < len(_NOMBRES) else str(n)


def _ordinal(k: int) -> str:
    return _ORDINAUX[k - 1] if k <= len(_ORDINAUX) else "number %d" % k


def _images(numeros: list[int]) -> str:
    if len(numeros) == 1:
        return "reference image %d" % numeros[0]
    return "reference images %s and %d" % (", ".join(str(n) for n in numeros[:-1]), numeros[-1])


def prompt_reference_identite(contrat: dict, dossier: dict, *, animation: bool, rest_pose_cues: str,
                              accepter_non_etablis: bool = False, renforces: Iterable[int] = ()) -> dict:
    """Compose le prompt FLUX.2 d'une référence où chaque sujet ancré est « le personnage de l'image k ».

    Retourne {"positif", "negatif", "references", "roles", ...} : `references` = chemins des ancres
    dans l'ordre des sujets (image 1, image 2…), `roles[i]` = rôle de l'image i + 1 tel qu'écrit dans
    le positif. Clés de traçabilité : `sujets` (rang, images, état de l'identité), `ecartes` (clauses
    et ancres non écrites, avec la raison), `decisions` (absences et marques du négatif), `convention`.

    Un sujet nommé sans identité établie lève IdentiteNonEtablie, sauf `accepter_non_etablis=True`
    (choix explicite de l'utilisateur) : il est alors décrit par sa seule nature et marqué
    « non_verifiee ». Un sujet non nommé est décrit par sa nature. `animation=True` exige
    `rest_pose_cues` (l'appelant passe `aurora_3d_pipeline.REST_POSE_CUES`). `renforces` : rangs des
    sujets dont le juge vient de refuser l'identité ; ils reçoivent une seconde ancre si elle existe.
    """
    sujets = _verifier_contrat(contrat)
    entrees = _verifier_dossier(dossier)
    if animation and not str(rest_pose_cues or "").strip():
        raise ValueError("animation demandee sans reperes de pose de repos : la reference montrerait l'action")

    noms = sorted({nom for nom in ([_normaliser(s.get("nom")) for s in sujets]
                                   + [_normaliser(e.get("nom")) for e in entrees]) if nom})
    ecartes: list[dict] = []
    utilisees: set[int] = set()
    lus = []
    for rang, sujet in enumerate(sujets):
        entree = _entree_du_dossier(rang, sujet, entrees)
        if entree is not None:
            if int(entree["index"]) in utilisees:
                raise ValueError("dossier d'identite : l'entree %s decrit deux sujets du contrat" % entree["index"])
            utilisees.add(int(entree["index"]))
        lus.append({"rang": rang, "sujet": sujet, "entree": entree,
                    "ancres": _ancres_lisibles(entree, ecartes) if entree else []})
    for entree in entrees:
        if int(entree["index"]) not in utilisees:
            ecartes.append({"sujet": int(entree["index"]), "champ": "dossier", "texte": str(entree.get("nom") or ""),
                            "raison": "sujet du dossier absent du contrat : ignore"})

    manquants = [{"index": lu["rang"], "nom": lu["sujet"].get("nom"),
                  "raison": (lu["entree"] or {}).get("raison")
                  or ("aucune ancre lisible" if lu["entree"] else "absent du dossier d'identite")}
                 for lu in lus if lu["sujet"].get("nomme") and not lu["ancres"]]
    if manquants and not accepter_non_etablis:
        raise IdentiteNonEtablie(manquants)

    plan = dict(_repartir([(lu["rang"], lu["ancres"]) for lu in lus if lu["ancres"]], renforces))
    references: list[str] = []
    roles: list[str] = []
    total = len(lus)
    descriptions = []
    traces = []
    for position, lu in enumerate(lus, start=1):
        sujet, entree, rang = lu["sujet"], lu["entree"] or {}, lu["rang"]
        nature = (_filtrer(_clauses(sujet.get("nature_en")), noms=noms, sujet=rang, champ="nature_en", ecartes=ecartes)
                  or _filtrer(_clauses(sujet.get("nature")), noms=noms, sujet=rang, champ="nature", ecartes=ecartes))
        nature_txt = ", ".join(nature)
        chemins = plan.get(rang, [])
        numeros = list(range(len(references) + 1, len(references) + len(chemins) + 1))
        for numero, chemin in zip(numeros, chemins):
            references.append(chemin)
            roles.append("reference image %d shows character %d%s" % (
                numero, position, " (%s)" % nature_txt if nature_txt else ""))
        attributs = entree.get("attributs") if isinstance(entree.get("attributs"), dict) else {}
        evalues = bool(chemins) and attributs.get("source") == "vision"
        # L'identité passe par les PIXELS des ancres, jamais par du texte (relecture du 15/11/2026) : décrire
        # couleurs ou vêtements faisait fuir un attribut d'un sujet à l'autre (le short sur les deux), et lire
        # « aucun vêtement visible » comme une absence pouvait dévêtir une personne réelle cadrée en buste.
        absent = False
        tete = ("Character %d, the %s from the left" % (position, _ordinal(position)) if total > 1
                else "Character %d" % position)
        if chemins:
            images = _images(numeros)
            phrase = ("%s: the character of %s%s, with exactly the identity shown in %s: same body plan, head "
                      "and face, proportions, silhouette, colours and markings" % (
                          tete, images, " (%s)" % nature_txt if nature_txt else "", images))
        else:
            phrase = "%s: %s" % (tete, nature_txt or "the requested subject")
        if not animation:
            action = _filtrer(_clauses(sujet.get("mouvement")), noms=noms, sujet=rang, champ="mouvement",
                              ecartes=ecartes)
            if action:
                phrase += "; in the pose of its requested action « %s »" % ", ".join(action)
        descriptions.append(phrase + ".")
        identite = "etablie" if chemins else ("non_verifiee" if sujet.get("nomme") else "non_nomme")
        traces.append({"index": rang, "position": position, "nom": sujet.get("nom"),
                       "nature_en": sujet.get("nature_en"), "images": numeros, "identite": identite,
                       "absence_de_vetement": absent,
                       "style_origine": _medium(attributs.get("style_origine")) if evalues else None})

    if total > 1:
        composition = (
            "Exactly %s separate full-body characters side by side in one single image, ordered from left to "
            "right as described below, each one complete from head to feet, separated from each other by a "
            "clear empty gap of background, not touching and not overlapping, all standing on the same ground "
            "line, on a plain seamless neutral white background, with nothing else in the image." % _nombre(total))
    else:
        composition = (
            "Exactly %s full-body character alone in one single image, complete from head to feet, centred, "
            "standing on a ground line, on a plain seamless neutral white background, with nothing else in "
            "the image." % _nombre(1))
    morceaux = [composition]
    if roles:
        morceaux.append("Reference roles: " + "; ".join(roles) + ".")
    morceaux.extend(descriptions)

    style = contrat.get("style") if isinstance(contrat.get("style"), dict) else {}
    cible = _medium(style.get("cible"))
    texte_style = ", ".join(_filtrer(_clauses(style.get("texte")), noms=noms, sujet=None, champ="style.texte",
                                     ecartes=ecartes))
    rendu = RENDU_PAR_CIBLE.get(cible or "", "")
    demande = ("requested style « %s »" % texte_style) if texte_style else ""
    if rendu or demande:
        phrase_style = "Rendering: " + (("%s (%s)" % (rendu, demande)) if rendu and demande else (rendu or demande))
        if references:
            phrase_style += "; only the rendering medium changes, every character keeps the identity of its reference image"
        morceaux.append(phrase_style + ".")
    elif references:
        morceaux.append("Rendering: the same rendering style as the reference images.")
    # Loi fibre/masse (TURNAROUND_CONTRACT, 27/07) formulée sans nommer de matière : la masse reste
    # géométrique, le grain fin appartient à la texture ; les mèches détachées vont au négatif.
    morceaux.append("Readable 3D volume and depth with soft even studio lighting; every surface rendered as solid "
                    "sculpted volumes with a clean readable contour, fine surface grain carried by texture only.")
    if animation:
        morceaux.append(str(rest_pose_cues).strip().rstrip(".") + ".")
    positif = " ".join(morceaux)
    if nomme_une_chose_portee(positif):
        # Filet de sécurité : les gabarits ci-dessus et les repères de repos n'en contiennent aucun.
        raise ValueError("le positif nomme une chose portee : %r" % _RX_CHOSE_PORTEE.search(_normaliser(positif)).group(0))

    negatif = [NEGATIF_PAR_DEFAUT]
    if total > 1:
        negatif.append("characters touching each other, overlapping characters, merged characters, extra characters")
    negatif.append("flyaway strands, wispy detached tufts")
    absences = bool(traces) and all(t["absence_de_vetement"] for t in traces)
    if absences:
        negatif.append(", ".join(ABSENCES_VETEMENT))
    marques: list[str] = []
    if cible in MARQUES_DU_MEDIUM:
        exclues = TRAITS_PARTAGES_PAR_CIBLE.get(cible, frozenset()) | set(MARQUES_DU_MEDIUM[cible])
        for origine in [t["style_origine"] for t in traces]:
            if origine not in MARQUES_DU_MEDIUM or origine == cible:
                continue
            for marque in MARQUES_DU_MEDIUM[origine]:
                if marque not in exclues and marque not in marques:
                    marques.append(marque)
        raison_marques = ("medium d'origine des ancres different du medium vise : ses marques sont niees" if marques
                          else "medium d'origine identique, inconnu ou non evalue : rien a nier")
    else:
        raison_marques = "medium vise absent ou hors enumeration (%r) : rien a nier" % style.get("cible")
    if marques:
        negatif.append(", ".join(marques))
    decisions = {
        "absences": absences,
        "raison_absences": ("chaque sujet est sans vetement selon le dossier : absences ecrites au negatif" if absences
                            else "non ecrites : le negatif est global et au moins un sujet porte quelque chose ou "
                                 "n'a pas d'absence etablie par le dossier"),
        "marques_origine": marques,
        "raison_marques": raison_marques,
    }

    return {
        "schema": SCHEMA,
        "positif": positif,
        "negatif": ", ".join(negatif),
        "references": references,
        "roles": roles,
        "sujets": traces,
        "renforces": sorted({int(i) for i in renforces}),
        "ecartes": ecartes,
        "decisions": decisions,
        "convention": CONVENTION_MULTI_REFERENCES,
    }
