"""Vocabulaires FERMÉS du moteur de scènes : le LLM choisit dans ces listes, il n'invente jamais une clé.

Ce sont des connaissances générales (dimensions réelles d'un lit ou d'une voie, meubles qu'on trouve dans
une cuisine, hauteur d'étage d'un style d'architecture), valables pour toute demande : aucune entrée ne
nomme un sujet, un lieu ou un personnage. Les dimensions sont en mètres, des fourchettes (min, max) dans
lesquelles le générateur tire selon la graine ; les couleurs sont des valeurs sRGB de matériaux réels.

Chaque table a une fonction de lecture qui lève `KeyError` explicite sur une clé inconnue : une clé hors
vocabulaire est une erreur à corriger dans le programme, jamais un repli silencieux.
"""
from __future__ import annotations

from typing import Any

# ── Matériaux ──────────────────────────────────────────────────────────────────────────────────────
# taille_m : côté du motif dans le monde (1 répétition de texture = taille_m mètres). Pour les façades,
# c'est le module d'une travée × un étage, pour que les fenêtres tombent sur les étages.
# alpha < 1 : matériau translucide (verre, eau) écrit en BLEND ; emissif : source de lumière.


def _m(description: str, famille: str, taille_m: float, metal: float, rugosite: float, couleur: str,
       coloriable: bool, **autres: Any) -> dict[str, Any]:
    return {"description": description, "famille": famille, "taille_m": float(taille_m), "metal": float(metal),
            "rugosite": float(rugosite), "couleur": couleur, "coloriable": bool(coloriable), **autres}


MATERIAUX: dict[str, dict[str, Any]] = {
    # sols et murs intérieurs
    "parquet_chene": _m("parquet de chêne en lames", "bois", 1.2, 0.0, 0.55, "#b58b5a", False),
    "parquet_fonce": _m("parquet foncé (noyer, wengé)", "bois", 1.2, 0.0, 0.5, "#6b4a32", False),
    "carrelage": _m("carrelage céramique grand format", "ceramique", 0.6, 0.0, 0.25, "#e8e4dc", True),
    "carrelage_metro": _m("carrelage métro biseauté", "ceramique", 0.3, 0.0, 0.2, "#f4f4f2", True),
    "carreaux_ciment": _m("carreaux de ciment à motifs", "ceramique", 0.4, 0.0, 0.45, "#c9c2b5", True),
    "tomette": _m("tomettes hexagonales en terre cuite", "ceramique", 0.5, 0.0, 0.7, "#a9583a", False),
    "marbre": _m("marbre veiné", "pierre", 1.5, 0.0, 0.15, "#ece9e4", True),
    "beton_cire": _m("béton ciré", "pierre", 2.0, 0.0, 0.55, "#a9a6a0", True),
    "platre_peint": _m("mur en plâtre peint", "peinture", 2.0, 0.0, 0.85, "#efebe3", True),
    "papier_peint": _m("papier peint à motifs", "peinture", 0.6, 0.0, 0.8, "#d9cfbf", True),
    "lambris": _m("lambris de bois", "bois", 1.0, 0.0, 0.6, "#c9a77c", True),
    "brique": _m("brique apparente", "pierre", 1.0, 0.0, 0.85, "#9c5a44", True),
    "pierre": _m("pierre de taille", "pierre", 1.5, 0.0, 0.8, "#c8bca6", True),
    "moquette": _m("moquette", "tissu", 1.0, 0.0, 0.95, "#8f8678", True),
    # mobilier
    "bois_chene": _m("chêne massif", "bois", 0.8, 0.0, 0.5, "#a9804f", False),
    "bois_noyer": _m("noyer", "bois", 0.8, 0.0, 0.45, "#5e4030", False),
    "bois_clair": _m("bois clair (hêtre, bouleau)", "bois", 0.8, 0.0, 0.5, "#d2b48c", False),
    "bois_peint": _m("bois laqué mat", "peinture", 1.0, 0.0, 0.4, "#f2efe8", True),
    "laque": _m("laque brillante", "peinture", 1.0, 0.0, 0.15, "#ffffff", True),
    "tissu": _m("tissu d'ameublement (lin, coton)", "tissu", 0.5, 0.0, 0.9, "#b9b0a2", True),
    "velours": _m("velours", "tissu", 0.5, 0.0, 0.8, "#4b5d67", True),
    "cuir": _m("cuir", "tissu", 0.6, 0.0, 0.45, "#6e4a33", True),
    "laine": _m("laine tissée (tapis, plaid)", "tissu", 1.0, 0.0, 0.95, "#c7b9a3", True),
    "metal_chrome": _m("chrome poli", "metal", 1.0, 1.0, 0.08, "#d9dadc", False),
    "inox": _m("acier inoxydable brossé", "metal", 0.5, 1.0, 0.3, "#bfc1c2", False),
    "metal_noir": _m("métal noir mat", "metal", 1.0, 1.0, 0.55, "#2a2a2a", False),
    "laiton": _m("laiton", "metal", 1.0, 1.0, 0.3, "#c9a45c", False),
    "cuivre": _m("cuivre", "metal", 1.0, 1.0, 0.3, "#b87333", False),
    "fonte": _m("fonte", "metal", 1.0, 1.0, 0.6, "#3a3a3a", False),
    "verre": _m("verre clair", "verre", 1.0, 0.0, 0.05, "#dfe9ec", False, alpha=0.25),
    "verre_depoli": _m("verre dépoli", "verre", 1.0, 0.0, 0.5, "#e6eaec", False, alpha=0.6),
    "miroir": _m("miroir", "metal", 1.0, 1.0, 0.02, "#f0f0f0", False),
    "ceramique": _m("céramique émaillée (sanitaires, vaisselle)", "ceramique", 1.0, 0.0, 0.1, "#fbfbfa", True),
    "plastique": _m("plastique", "plastique", 1.0, 0.0, 0.4, "#e0e0e0", True),
    "ecran": _m("écran éteint (verre noir)", "verre", 1.0, 0.0, 0.05, "#0d0f12", False),
    "lumiere": _m("source lumineuse (abat-jour, ampoule)", "lumiere", 1.0, 0.0, 0.5, "#fff3d6", True,
                  emissif=1.0),
    "plante": _m("feuillage de plante d'intérieur", "vegetal", 0.5, 0.0, 0.6, "#4f7a3a", True),
    "terre_cuite": _m("terre cuite (pot)", "ceramique", 0.5, 0.0, 0.75, "#b5603e", False),
    "papier": _m("papier, reliures de livres", "plastique", 0.3, 0.0, 0.8, "#d8cfbd", True),
    # extérieur
    "asphalte": _m("asphalte de chaussée", "sol_ext", 4.0, 0.0, 0.9, "#3b3c3e", False),
    "marquage": _m("marquage routier", "peinture", 1.0, 0.0, 0.6, "#f4f4f0", True),
    "trottoir": _m("dalles de trottoir", "sol_ext", 1.0, 0.0, 0.8, "#b0aca4", False),
    "paves": _m("pavés", "sol_ext", 1.0, 0.0, 0.85, "#8d8679", False),
    "gravier": _m("gravier", "sol_ext", 1.0, 0.0, 0.95, "#b8ad99", False),
    "herbe": _m("herbe", "vegetal", 2.0, 0.0, 0.95, "#5d8a3c", False),
    "terre": _m("terre", "sol_ext", 2.0, 0.0, 0.95, "#6f5640", False),
    "sable": _m("sable", "sol_ext", 2.0, 0.0, 0.9, "#d9c49a", False),
    "roche": _m("roche", "pierre", 3.0, 0.0, 0.85, "#7d7a74", True),
    "neige": _m("neige", "sol_ext", 3.0, 0.0, 0.6, "#f2f5f8", False),
    "eau": _m("surface d'eau", "eau", 4.0, 0.0, 0.05, "#2e5f77", False, alpha=0.75),
    "ecorce": _m("écorce", "vegetal", 0.6, 0.0, 0.9, "#5a4634", False),
    "feuillage": _m("feuillage d'arbre", "vegetal", 1.0, 0.0, 0.7, "#3f6b2e", True),
    "facade_enduit": _m("façade en enduit avec fenêtres", "facade", 3.0, 0.0, 0.85, "#e3d9c6", True),
    "facade_brique": _m("façade en brique avec fenêtres", "facade", 3.0, 0.0, 0.85, "#9a5440", True),
    "facade_pierre": _m("façade en pierre de taille avec fenêtres et balcons", "facade", 3.0, 0.0, 0.8,
                        "#d8ccb4", True),
    "facade_beton": _m("façade en béton avec fenêtres", "facade", 3.0, 0.0, 0.8, "#9b9a96", True),
    "facade_bois": _m("façade en bardage bois avec fenêtres", "facade", 3.0, 0.0, 0.75, "#8a6a48", True),
    "mur_rideau": _m("mur-rideau vitré (tours de bureaux)", "facade", 3.0, 0.4, 0.15, "#5d7f99", True),
    "vitrine": _m("rez-de-chaussée commercial vitré", "facade", 4.0, 0.2, 0.2, "#6a7a84", True),
    "tuile": _m("tuiles en terre cuite", "ceramique", 1.0, 0.0, 0.8, "#a4553a", False),
    "ardoise": _m("ardoise", "pierre", 1.0, 0.0, 0.7, "#4a4e55", False),
    "zinc": _m("couverture en zinc", "metal", 1.0, 1.0, 0.45, "#8e959b", False),
    "toit_terrasse": _m("toit-terrasse gravillonné", "sol_ext", 2.0, 0.0, 0.9, "#7b7975", False),
    "carrosserie": _m("peinture de carrosserie", "metal", 1.0, 0.6, 0.25, "#9a1b1b", True),
    "caoutchouc": _m("caoutchouc (pneus, joints)", "plastique", 1.0, 0.0, 0.9, "#1b1b1b", False),
}

# Couleurs nommées pour les matériaux coloriables (« platre_peint:vert_sauge »). Valeurs sRGB.
PALETTE: dict[str, str] = {
    "blanc": "#f5f5f2", "blanc_casse": "#efebe3", "creme": "#efe4cf", "beige": "#d8c7a8", "sable": "#cdb88f",
    "taupe": "#8b7d6b", "gris_clair": "#c9c9c6", "gris": "#8f8f8c", "anthracite": "#3d3f42", "noir": "#1c1c1c",
    "bleu_nuit": "#1f2d4a", "bleu_marine": "#25365a", "bleu_ciel": "#a9c6de", "bleu_canard": "#1f5c66",
    "bleu_gris": "#6f8796", "vert_sauge": "#9cad8f", "vert_olive": "#6b6b3a", "vert_foret": "#2f4d36",
    "vert_menthe": "#b9dcc8", "terracotta": "#b9603f", "rouge_brique": "#8e3b2c", "rouge": "#b0262a",
    "bordeaux": "#6b2133", "rose_poudre": "#e3c2bf", "jaune_moutarde": "#c99a2e", "jaune": "#e8c547",
    "ocre": "#c18a3f", "orange": "#d9752b", "marron": "#6e4b32", "chocolat": "#4a3022", "violet": "#5e4a7a",
    "lavande": "#b8acd6",
}


def materiau(cle: str) -> dict[str, Any]:
    """Spécification d'un matériau : « famille » ou « famille:couleur » (couleur de PALETTE ou #rrggbb)."""
    base, _, teinte = str(cle).partition(":")
    if base not in MATERIAUX:
        raise KeyError(f"matériau hors vocabulaire : {base!r}")
    spec = dict(MATERIAUX[base], cle=base)
    if teinte:
        if not spec["coloriable"]:
            raise KeyError(f"le matériau {base!r} n'est pas coloriable (couleur demandée : {teinte!r})")
        if teinte in PALETTE:
            spec["couleur"] = PALETTE[teinte]
        elif len(teinte) == 7 and teinte.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in teinte[1:]):
            spec["couleur"] = teinte.lower()
        else:
            raise KeyError(f"couleur hors palette : {teinte!r}")
    return spec


# ── Meubles et objets ──────────────────────────────────────────────────────────────────────────────
# largeur = étendue locale en X, profondeur = en Z (la face regarde +Z), hauteur = en Y.
# degagement : espace libre devant la face ; degagement_cotes : de chaque côté (lit, îlot).
# contre_mur : "oui" (dos au mur), "non" (au milieu), "indifferent".
# mural : accroché au mur à hauteur_pose (bas de l'objet) ; plafond : suspendu au plafond.
# support : offre un dessus où poser de petits objets ; pose_sur : catégories qui peuvent le porter.
# sol_partage : couvre le sol sans gêner (tapis) — d'autres meubles peuvent le chevaucher.


def _c(description: str, groupe: str, largeur: tuple[float, float], profondeur: tuple[float, float],
       hauteur: tuple[float, float], *, degagement: float = 0.0, degagement_cotes: float = 0.0,
       contre_mur: str = "indifferent", mural: bool = False, hauteur_pose: tuple[float, float] = (0.0, 0.0),
       plafond: bool = False, support: bool = False, pose_sur: tuple[str, ...] = (), sol_partage: bool = False,
       exterieur: bool = False, materiaux: dict[str, str] | None = None, styles: tuple[str, ...] = ()) -> dict:
    return {"description": description, "groupe": groupe, "largeur": largeur, "profondeur": profondeur,
            "hauteur": hauteur, "degagement": degagement, "degagement_cotes": degagement_cotes,
            "contre_mur": contre_mur, "mural": mural, "hauteur_pose": hauteur_pose, "plafond": plafond,
            "support": support, "pose_sur": pose_sur, "sol_partage": sol_partage, "exterieur": exterieur,
            "materiaux": dict(materiaux or {}), "styles": styles}


_DESSUS = ("table_de_chevet", "commode", "bureau", "buffet", "console", "meuble_tv", "table_basse",
           "table_a_manger", "plan_de_travail", "ilot_cuisine", "etagere_murale", "bibliotheque")

# `materiaux` : emplacements de matériau de l'objet et leur valeur par défaut (le programme peut les changer).
CATEGORIES: dict[str, dict[str, Any]] = {
    # couchage et chambre
    "lit_simple": _c("lit une place avec tête de lit", "couchage", (0.9, 1.0), (1.95, 2.1), (0.8, 1.0),
                     degagement=0.6, degagement_cotes=0.5, contre_mur="oui",
                     materiaux={"structure": "bois_chene", "literie": "tissu:blanc_casse"}),
    "lit_double": _c("lit deux places avec tête de lit", "couchage", (1.4, 1.8), (1.95, 2.15), (0.9, 1.1),
                     degagement=0.6, degagement_cotes=0.55, contre_mur="oui",
                     materiaux={"structure": "bois_chene", "literie": "tissu:blanc_casse", "plaid": "laine:gris"}),
    "table_de_chevet": _c("table de chevet à tiroir", "rangement", (0.4, 0.5), (0.35, 0.42), (0.45, 0.58),
                          contre_mur="oui", support=True, materiaux={"structure": "bois_chene"}),
    "armoire": _c("armoire à portes battantes", "rangement", (0.9, 2.0), (0.55, 0.62), (1.95, 2.25),
                  degagement=0.8, contre_mur="oui", materiaux={"structure": "bois_peint:blanc", "poignees": "metal_noir"}),
    "commode": _c("commode à tiroirs", "rangement", (0.8, 1.2), (0.45, 0.52), (0.75, 0.92), degagement=0.7,
                  contre_mur="oui", support=True, materiaux={"structure": "bois_noyer", "poignees": "laiton"}),
    # séjour
    "canape": _c("canapé trois places", "assise", (1.8, 2.5), (0.85, 1.0), (0.75, 0.88), degagement=0.5,
                 materiaux={"structure": "tissu:gris", "pieds": "bois_noyer"}),
    "fauteuil": _c("fauteuil", "assise", (0.7, 0.9), (0.75, 0.9), (0.75, 0.95), degagement=0.45,
                   materiaux={"structure": "tissu:vert_sauge", "pieds": "bois_noyer"}),
    "table_basse": _c("table basse", "table", (0.8, 1.2), (0.5, 0.7), (0.35, 0.45), contre_mur="non", support=True,
                      materiaux={"plateau": "bois_chene", "pieds": "metal_noir"}),
    "meuble_tv": _c("meuble télévision bas", "rangement", (1.2, 1.8), (0.38, 0.48), (0.42, 0.55), degagement=0.4,
                    contre_mur="oui", support=True, materiaux={"structure": "bois_noyer"}),
    "television": _c("télévision à écran plat", "electronique", (0.95, 1.45), (0.06, 0.22), (0.58, 0.88),
                     pose_sur=("meuble_tv", "commode", "buffet"), materiaux={"cadre": "metal_noir", "ecran": "ecran"}),
    "bibliotheque": _c("bibliothèque garnie de livres", "rangement", (0.8, 1.2), (0.3, 0.38), (1.8, 2.1),
                       degagement=0.6, contre_mur="oui", support=True,
                       materiaux={"structure": "bois_clair", "livres": "papier"}),
    "etagere_murale": _c("étagère murale", "rangement", (0.6, 1.2), (0.2, 0.28), (0.25, 0.35), mural=True,
                         hauteur_pose=(1.25, 1.6), support=True, materiaux={"structure": "bois_chene", "livres": "papier"}),
    "tapis": _c("tapis", "decor", (1.6, 3.0), (1.2, 2.0), (0.01, 0.02), contre_mur="non", sol_partage=True,
                materiaux={"surface": "laine:beige"}),
    "lampadaire": _c("lampadaire", "luminaire", (0.3, 0.45), (0.3, 0.45), (1.5, 1.8),
                     materiaux={"structure": "metal_noir", "abat_jour": "lumiere:creme"}),
    "lampe_de_table": _c("lampe de table à abat-jour", "luminaire", (0.22, 0.35), (0.22, 0.35), (0.35, 0.6),
                         pose_sur=("table_de_chevet", "commode", "bureau", "buffet", "console", "meuble_tv"),
                         materiaux={"pied": "ceramique:blanc", "abat_jour": "lumiere:creme"}),
    "suspension": _c("suspension (luminaire de plafond)", "luminaire", (0.3, 0.6), (0.3, 0.6), (0.2, 0.5),
                     plafond=True, materiaux={"structure": "metal_noir", "abat_jour": "lumiere:creme"}),
    "plante_en_pot": _c("plante verte en pot", "vegetal", (0.3, 0.6), (0.3, 0.6), (0.5, 1.6),
                        materiaux={"pot": "terre_cuite", "feuillage": "plante"}),
    "tableau": _c("tableau encadré", "decor", (0.5, 1.2), (0.03, 0.05), (0.4, 0.9), mural=True,
                  hauteur_pose=(1.2, 1.45), materiaux={"cadre": "bois_noyer", "toile": "papier:beige"}),
    "miroir": _c("miroir mural", "decor", (0.5, 0.9), (0.03, 0.04), (0.7, 1.1), mural=True,
                 hauteur_pose=(1.0, 1.25), materiaux={"cadre": "laiton", "glace": "miroir"}),
    "console": _c("console d'entrée", "table", (0.8, 1.2), (0.3, 0.38), (0.75, 0.85), degagement=0.5,
                  contre_mur="oui", support=True, materiaux={"structure": "bois_chene"}),
    "cheminee": _c("cheminée avec manteau", "decor", (1.0, 1.6), (0.3, 0.5), (1.0, 1.2), degagement=0.8,
                   contre_mur="oui", support=True, materiaux={"structure": "pierre", "foyer": "fonte"}),
    "piano": _c("piano droit", "decor", (1.4, 1.55), (0.55, 0.65), (1.1, 1.3), degagement=0.8,
                contre_mur="oui", materiaux={"structure": "laque:noir", "touches": "ceramique:blanc"}),
    # repas et travail
    "table_a_manger": _c("table à manger", "table", (1.4, 2.2), (0.8, 1.0), (0.74, 0.77), contre_mur="non",
                         support=True, materiaux={"plateau": "bois_chene", "pieds": "bois_chene"}),
    "chaise": _c("chaise", "assise", (0.42, 0.5), (0.46, 0.55), (0.8, 0.95), degagement=0.35,
                 materiaux={"structure": "bois_chene", "assise": "tissu:beige"}),
    "bureau": _c("bureau", "table", (1.0, 1.6), (0.6, 0.8), (0.72, 0.76), degagement=0.8, contre_mur="oui",
                 support=True, materiaux={"plateau": "bois_clair", "pieds": "metal_noir"}),
    "buffet": _c("buffet bas", "rangement", (1.4, 2.0), (0.45, 0.5), (0.8, 0.9), degagement=0.7,
                 contre_mur="oui", support=True, materiaux={"structure": "bois_noyer", "poignees": "laiton"}),
    "banc": _c("banc", "assise", (1.0, 1.5), (0.35, 0.45), (0.44, 0.48), degagement=0.4,
               materiaux={"structure": "bois_chene"}),
    "porte_manteau": _c("porte-manteau sur pied", "rangement", (0.4, 0.5), (0.4, 0.5), (1.7, 1.85),
                        materiaux={"structure": "bois_noyer"}),
    # cuisine
    "plan_de_travail": _c("linéaire de cuisine (meubles bas, plan de travail, évier, plaque)", "cuisine",
                          (1.2, 3.6), (0.6, 0.65), (0.88, 0.92), degagement=1.0, contre_mur="oui", support=True,
                          materiaux={"facades": "bois_peint:blanc", "plan": "marbre", "evier": "inox",
                                     "poignees": "metal_noir"}),
    "placard_haut": _c("placards hauts de cuisine", "cuisine", (0.6, 2.4), (0.33, 0.37), (0.6, 0.75), mural=True,
                       hauteur_pose=(1.45, 1.55), materiaux={"facades": "bois_peint:blanc", "poignees": "metal_noir"}),
    "ilot_cuisine": _c("îlot central de cuisine", "cuisine", (1.2, 2.4), (0.8, 1.0), (0.88, 0.92), degagement=1.0,
                       degagement_cotes=0.9, contre_mur="non", support=True,
                       materiaux={"facades": "bois_peint:blanc", "plan": "marbre"}),
    "refrigerateur": _c("réfrigérateur", "electromenager", (0.6, 0.9), (0.62, 0.75), (1.75, 2.0), degagement=0.9,
                        contre_mur="oui", materiaux={"caisse": "inox", "poignees": "metal_noir"}),
    "cuisiniere": _c("cuisinière avec four", "electromenager", (0.6, 0.9), (0.6, 0.65), (0.88, 0.92),
                     degagement=1.0, contre_mur="oui", materiaux={"caisse": "inox", "plaque": "ecran"}),
    "hotte": _c("hotte aspirante", "electromenager", (0.6, 0.9), (0.45, 0.5), (0.35, 0.8), mural=True,
                hauteur_pose=(1.6, 1.75), materiaux={"caisse": "inox"}),
    "lave_vaisselle": _c("lave-vaisselle", "electromenager", (0.6, 0.6), (0.58, 0.62), (0.82, 0.86),
                         degagement=0.9, contre_mur="oui", materiaux={"caisse": "inox"}),
    "lave_linge": _c("lave-linge à hublot", "electromenager", (0.6, 0.6), (0.55, 0.62), (0.82, 0.86),
                     degagement=0.8, contre_mur="oui", materiaux={"caisse": "plastique:blanc", "hublot": "verre"}),
    # salle de bain
    "baignoire": _c("baignoire", "sanitaire", (1.5, 1.8), (0.7, 0.8), (0.55, 0.6), degagement=0.7,
                    contre_mur="oui", materiaux={"cuve": "ceramique:blanc", "robinet": "metal_chrome"}),
    "douche": _c("douche à paroi vitrée", "sanitaire", (0.8, 1.2), (0.8, 1.2), (2.0, 2.1), degagement=0.7,
                 contre_mur="oui", materiaux={"receveur": "ceramique:blanc", "paroi": "verre", "robinet": "metal_chrome"}),
    "lavabo": _c("meuble vasque", "sanitaire", (0.5, 1.2), (0.45, 0.52), (0.82, 0.88), degagement=0.7,
                 contre_mur="oui", materiaux={"meuble": "bois_chene", "vasque": "ceramique:blanc", "robinet": "metal_chrome"}),
    "wc": _c("cuvette de toilettes avec réservoir", "sanitaire", (0.36, 0.4), (0.62, 0.7), (0.75, 0.8),
             degagement=0.6, contre_mur="oui", materiaux={"cuvette": "ceramique:blanc"}),
    # extérieur et mobilier urbain
    "lampadaire_rue": _c("lampadaire de rue", "urbain", (0.4, 1.6), (0.4, 0.5), (4.5, 7.5), exterieur=True,
                         materiaux={"mat": "fonte", "lanterne": "lumiere:creme"}),
    "banc_public": _c("banc public", "urbain", (1.6, 2.0), (0.55, 0.7), (0.78, 0.85), degagement=0.5,
                      exterieur=True, materiaux={"lattes": "bois_chene", "structure": "fonte"}),
    "poubelle_rue": _c("corbeille de rue", "urbain", (0.4, 0.55), (0.4, 0.55), (0.85, 1.05), exterieur=True,
                       materiaux={"structure": "metal_noir"}),
    "abribus": _c("abribus vitré", "urbain", (3.0, 4.5), (1.4, 1.8), (2.4, 2.7), degagement=1.0, exterieur=True,
                  materiaux={"structure": "metal_noir", "parois": "verre", "toit": "metal_noir"}),
    "feu_tricolore": _c("feu de circulation", "urbain", (0.3, 0.35), (0.3, 0.35), (3.0, 3.6), exterieur=True,
                        materiaux={"mat": "metal_noir", "feux": "lumiere:orange"}),
    "panneau": _c("panneau de signalisation", "urbain", (0.6, 0.8), (0.08, 0.12), (2.3, 2.7), exterieur=True,
                  materiaux={"mat": "inox", "plaque": "plastique:bleu_marine"}),
    "fontaine": _c("fontaine à vasque", "urbain", (2.0, 6.0), (2.0, 6.0), (0.8, 2.8), degagement=1.0,
                   exterieur=True, materiaux={"structure": "pierre", "eau": "eau"}),
    "table_pique_nique": _c("table de pique-nique", "urbain", (1.7, 2.0), (1.4, 1.6), (0.72, 0.78),
                            exterieur=True, materiaux={"structure": "bois_chene"}),
    "voiture": _c("voiture citadine (face = avant)", "vehicule", (1.7, 1.9), (3.9, 4.7), (1.4, 1.6),
                  exterieur=True, materiaux={"carrosserie": "carrosserie:rouge", "vitres": "verre",
                                             "pneus": "caoutchouc", "jantes": "inox"}),
    "parasol": _c("parasol de plage", "urbain", (1.8, 2.6), (1.8, 2.6), (2.2, 2.5), exterieur=True,
                  materiaux={"mat": "bois_clair", "toile": "tissu:blanc"}),
    "transat": _c("chaise longue", "assise", (0.6, 0.7), (1.8, 2.0), (0.35, 0.9), exterieur=True,
                  materiaux={"structure": "bois_clair", "toile": "tissu:bleu_canard"}),
    # végétation et minéral
    "arbre": _c("arbre", "vegetal", (2.5, 9.0), (2.5, 9.0), (4.0, 16.0), exterieur=True,
                materiaux={"tronc": "ecorce", "feuillage": "feuillage"},
                styles=("feuillu", "conifere", "palmier", "fruitier", "bouleau")),
    "buisson": _c("buisson", "vegetal", (0.6, 2.0), (0.6, 2.0), (0.5, 1.6), exterieur=True,
                  materiaux={"feuillage": "feuillage"}),
    "rocher": _c("rocher", "mineral", (0.3, 3.0), (0.3, 3.0), (0.2, 2.0), exterieur=True,
                 materiaux={"surface": "roche"}),
}


def categorie(cle: str) -> dict[str, Any]:
    if cle not in CATEGORIES:
        raise KeyError(f"catégorie d'objet hors vocabulaire : {cle!r}")
    return dict(CATEGORIES[cle], cle=cle)


# ── Pièces ─────────────────────────────────────────────────────────────────────────────────────────
# meubles_typiques : ce qu'une pièce COMPLÈTE de cette fonction contient d'ordinaire (connaissance
# générale), sous forme (categorie, nombre, relations). Le programme peut en retirer ou en ajouter ; une
# demande « complète » sans détail reçoit cette liste. Relations : voir RELATIONS.
FONCTIONS_PIECES: dict[str, dict[str, Any]] = {
    "salon": {"description": "salon / séjour", "surface": (14.0, 40.0), "sol": "parquet_chene", "murs": "platre_peint",
              "fenetre": True, "meubles_typiques": [
                  ("canape", 1, [("contre_mur", None)]), ("table_basse", 1, [("devant", "canape")]),
                  ("tapis", 1, [("sous", "table_basse")]), ("fauteuil", 1, [("autour_de", "table_basse")]),
                  ("meuble_tv", 1, [("contre_mur", None), ("face_a", "canape")]), ("television", 1, [("sur", "meuble_tv")]),
                  ("lampadaire", 1, [("a_cote_de", "canape")]), ("bibliotheque", 1, [("contre_mur", None)]),
                  ("plante_en_pot", 1, [("dans_un_coin", None)]), ("tableau", 1, [("au_dessus_de", "canape")]),
                  ("suspension", 1, [("au_centre", None)])]},
    "salle_a_manger": {"description": "salle à manger", "surface": (10.0, 25.0), "sol": "parquet_chene",
                       "murs": "platre_peint", "fenetre": True, "meubles_typiques": [
                           ("table_a_manger", 1, [("au_centre", None)]), ("chaise", 6, [("autour_de", "table_a_manger")]),
                           ("buffet", 1, [("contre_mur", None)]), ("suspension", 1, [("au_dessus_de", "table_a_manger")]),
                           ("tableau", 1, [("au_dessus_de", "buffet")]), ("plante_en_pot", 1, [("dans_un_coin", None)])]},
    "cuisine": {"description": "cuisine", "surface": (7.0, 20.0), "sol": "carrelage", "murs": "platre_peint",
                "fenetre": True, "meubles_typiques": [
                    ("plan_de_travail", 1, [("contre_mur", None), ("sous_fenetre", None)]),
                    ("cuisiniere", 1, [("contre_mur", None), ("a_cote_de", "plan_de_travail")]),
                    ("refrigerateur", 1, [("contre_mur", None), ("a_cote_de", "plan_de_travail")]),
                    ("lave_vaisselle", 1, [("contre_mur", None), ("a_cote_de", "plan_de_travail")]),
                    ("placard_haut", 1, [("au_dessus_de", "plan_de_travail")]),
                    ("hotte", 1, [("au_dessus_de", "cuisiniere")]),
                    ("table_a_manger", 1, [("au_centre", None)]), ("chaise", 2, [("autour_de", "table_a_manger")]),
                    ("suspension", 1, [("au_dessus_de", "table_a_manger")])]},
    "chambre": {"description": "chambre", "surface": (9.0, 22.0), "sol": "parquet_chene", "murs": "platre_peint",
                "fenetre": True, "meubles_typiques": [
                    ("lit_double", 1, [("contre_mur", None)]), ("table_de_chevet", 2, [("a_cote_de", "lit_double")]),
                    ("lampe_de_table", 2, [("sur", "table_de_chevet")]), ("armoire", 1, [("contre_mur", None)]),
                    ("commode", 1, [("contre_mur", None)]), ("tapis", 1, [("au_pied_de", "lit_double")]),
                    ("tableau", 1, [("au_dessus_de", "lit_double")]), ("suspension", 1, [("au_centre", None)])]},
    "chambre_enfant": {"description": "chambre d'enfant", "surface": (8.0, 16.0), "sol": "parquet_chene",
                       "murs": "platre_peint", "fenetre": True, "meubles_typiques": [
                           ("lit_simple", 1, [("contre_mur", None)]), ("table_de_chevet", 1, [("a_cote_de", "lit_simple")]),
                           ("bureau", 1, [("contre_mur", None), ("sous_fenetre", None)]), ("chaise", 1, [("devant", "bureau")]),
                           ("armoire", 1, [("contre_mur", None)]), ("bibliotheque", 1, [("contre_mur", None)]),
                           ("tapis", 1, [("au_centre", None)]), ("lampe_de_table", 1, [("sur", "bureau")])]},
    "salle_de_bain": {"description": "salle de bain", "surface": (4.0, 12.0), "sol": "carrelage",
                      "murs": "carrelage_metro", "fenetre": False, "meubles_typiques": [
                          ("baignoire", 1, [("contre_mur", None), ("dans_un_coin", None)]),
                          ("lavabo", 1, [("contre_mur", None)]), ("miroir", 1, [("au_dessus_de", "lavabo")]),
                          ("wc", 1, [("contre_mur", None)]), ("lave_linge", 1, [("contre_mur", None)])]},
    "salle_d_eau": {"description": "salle d'eau (douche)", "surface": (3.0, 7.0), "sol": "carrelage",
                    "murs": "carrelage_metro", "fenetre": False, "meubles_typiques": [
                        ("douche", 1, [("contre_mur", None), ("dans_un_coin", None)]), ("lavabo", 1, [("contre_mur", None)]),
                        ("miroir", 1, [("au_dessus_de", "lavabo")])]},
    "wc": {"description": "toilettes", "surface": (1.2, 3.0), "sol": "carrelage", "murs": "platre_peint",
           "fenetre": False, "meubles_typiques": [("wc", 1, [("contre_mur", None)])]},
    "entree": {"description": "entrée", "surface": (3.0, 10.0), "sol": "carreaux_ciment", "murs": "platre_peint",
               "fenetre": False, "meubles_typiques": [
                   ("console", 1, [("contre_mur", None)]), ("miroir", 1, [("au_dessus_de", "console")]),
                   ("porte_manteau", 1, [("dans_un_coin", None)]), ("banc", 1, [("contre_mur", None)]),
                   ("plante_en_pot", 1, [("dans_un_coin", None)])]},
    "couloir": {"description": "couloir / dégagement", "surface": (2.0, 10.0), "sol": "parquet_chene",
                "murs": "platre_peint", "fenetre": False, "meubles_typiques": [
                    ("tableau", 2, [("contre_mur", None)]), ("suspension", 1, [("au_centre", None)])]},
    "bureau": {"description": "bureau / pièce de travail", "surface": (7.0, 16.0), "sol": "parquet_chene",
               "murs": "platre_peint", "fenetre": True, "meubles_typiques": [
                   ("bureau", 1, [("contre_mur", None), ("sous_fenetre", None)]), ("chaise", 1, [("devant", "bureau")]),
                   ("bibliotheque", 2, [("contre_mur", None)]), ("fauteuil", 1, [("dans_un_coin", None)]),
                   ("lampadaire", 1, [("a_cote_de", "fauteuil")]), ("plante_en_pot", 1, [("dans_un_coin", None)]),
                   ("lampe_de_table", 1, [("sur", "bureau")])]},
    "buanderie": {"description": "buanderie / cellier", "surface": (3.0, 8.0), "sol": "carrelage",
                  "murs": "platre_peint", "fenetre": False, "meubles_typiques": [
                      ("lave_linge", 1, [("contre_mur", None)]), ("etagere_murale", 2, [("au_dessus_de", "lave_linge")]),
                      ("armoire", 1, [("contre_mur", None)])]},
    "dressing": {"description": "dressing", "surface": (3.0, 9.0), "sol": "parquet_chene", "murs": "platre_peint",
                 "fenetre": False, "meubles_typiques": [("armoire", 2, [("contre_mur", None)]),
                                                        ("miroir", 1, [("contre_mur", None)])]},
}


def fonction_piece(cle: str) -> dict[str, Any]:
    if cle not in FONCTIONS_PIECES:
        raise KeyError(f"fonction de pièce hors vocabulaire : {cle!r}")
    return dict(FONCTIONS_PIECES[cle], cle=cle)


# Relations de disposition (cible = une catégorie présente dans la même pièce, ou None).
RELATIONS: dict[str, dict[str, Any]] = {
    "contre_mur": {"cible": False, "description": "dos contre un mur"},
    "au_centre": {"cible": False, "description": "au centre de la pièce"},
    "dans_un_coin": {"cible": False, "description": "dans un angle de la pièce"},
    "sous_fenetre": {"cible": False, "description": "contre le mur d'une fenêtre, sous l'allège"},
    "face_a": {"cible": True, "description": "tourné vers la cible, à distance d'usage"},
    "devant": {"cible": True, "description": "devant la face de la cible"},
    "autour_de": {"cible": True, "description": "réparti autour de la cible, tourné vers elle"},
    "a_cote_de": {"cible": True, "description": "contre un côté de la cible, aligné avec elle"},
    "sur": {"cible": True, "description": "posé sur le dessus de la cible"},
    "sous": {"cible": True, "description": "au sol sous la cible (tapis)"},
    "au_pied_de": {"cible": True, "description": "au sol devant le pied de la cible (lit)"},
    "au_dessus_de": {"cible": True, "description": "au mur ou au plafond au-dessus de la cible"},
}


# ── Architecture ───────────────────────────────────────────────────────────────────────────────────
# Paramètres généraux d'un style : hauteur d'étage, toits possibles, matériaux de façade, retraits.
STYLES_ARCHI: dict[str, dict[str, Any]] = {
    "moderne": {"description": "contemporain, lignes droites", "hauteur_etage": 3.0, "toits": ("terrasse", "plat"),
                "facades": ("facade_enduit", "facade_beton", "facade_bois"), "toiture": "toit_terrasse",
                "interieur": {"sol": "parquet_chene", "murs": "platre_peint:blanc"}},
    "haussmannien": {"description": "immeubles parisiens XIXe, pierre de taille, toits mansardés",
                     "hauteur_etage": 3.4, "toits": ("mansarde",), "facades": ("facade_pierre",), "toiture": "zinc",
                     "interieur": {"sol": "parquet_chene", "murs": "platre_peint:blanc_casse"}},
    "traditionnel": {"description": "maisons traditionnelles à toit en pente", "hauteur_etage": 2.8,
                     "toits": ("deux_pans", "quatre_pans"), "facades": ("facade_enduit", "facade_brique"),
                     "toiture": "tuile", "interieur": {"sol": "tomette", "murs": "platre_peint:creme"}},
    "medieval": {"description": "bourg médiéval, pierre et colombages", "hauteur_etage": 2.7,
                 "toits": ("deux_pans",), "facades": ("facade_pierre", "facade_bois"), "toiture": "ardoise",
                 "interieur": {"sol": "pierre", "murs": "pierre"}},
    "industriel": {"description": "brique, métal, grandes verrières", "hauteur_etage": 3.6,
                   "toits": ("plat", "deux_pans"), "facades": ("facade_brique", "facade_beton"), "toiture": "zinc",
                   "interieur": {"sol": "beton_cire", "murs": "brique"}},
    "mediterraneen": {"description": "enduits clairs, tuiles, patios", "hauteur_etage": 2.9,
                      "toits": ("quatre_pans", "terrasse"), "facades": ("facade_enduit",), "toiture": "tuile",
                      "interieur": {"sol": "tomette", "murs": "platre_peint:blanc"}},
    "scandinave": {"description": "bois clair, sobriété", "hauteur_etage": 2.8, "toits": ("deux_pans",),
                   "facades": ("facade_bois", "facade_enduit"), "toiture": "zinc",
                   "interieur": {"sol": "parquet_chene", "murs": "platre_peint:blanc"}},
    "futuriste": {"description": "tours vitrées, volumes audacieux", "hauteur_etage": 3.8, "toits": ("plat",),
                  "facades": ("mur_rideau", "facade_beton"), "toiture": "toit_terrasse",
                  "interieur": {"sol": "beton_cire", "murs": "laque:blanc"}},
}

TOITS = ("plat", "terrasse", "deux_pans", "quatre_pans", "mansarde")

# Zones d'une ville : usage, gabarit (étages min-max), parcelle (m² min-max), retrait sur rue, part de
# rez-de-chaussée commercial.
ZONES_VILLE: dict[str, dict[str, Any]] = {
    "pavillonnaire": {"description": "maisons individuelles avec jardin", "etages": (1, 2), "parcelle": (300.0, 800.0),
                      "retrait": 5.0, "commerce": 0.0, "batie": True},
    "residentiel": {"description": "immeubles d'habitation", "etages": (3, 7), "parcelle": (400.0, 1500.0),
                    "retrait": 0.0, "commerce": 0.2, "batie": True},
    "centre": {"description": "centre-ville commerçant, rez-de-chaussée en vitrines", "etages": (3, 6),
               "parcelle": (250.0, 900.0), "retrait": 0.0, "commerce": 0.9, "batie": True},
    "affaires": {"description": "quartier d'affaires, tours", "etages": (10, 40), "parcelle": (1200.0, 4000.0),
                 "retrait": 6.0, "commerce": 0.5, "batie": True},
    "industriel": {"description": "entrepôts et ateliers", "etages": (1, 2), "parcelle": (1500.0, 6000.0),
                   "retrait": 8.0, "commerce": 0.0, "batie": True},
    "parc": {"description": "parc public (pelouse, allées, arbres, bancs)", "etages": (0, 0), "parcelle": (0.0, 0.0),
             "retrait": 0.0, "commerce": 0.0, "batie": False},
    "place": {"description": "place minérale (pavés, fontaine, bancs)", "etages": (0, 0), "parcelle": (0.0, 0.0),
              "retrait": 0.0, "commerce": 0.0, "batie": False},
    "eau": {"description": "plan d'eau ou rivière", "etages": (0, 0), "parcelle": (0.0, 0.0), "retrait": 0.0,
            "commerce": 0.0, "batie": False},
}

TRAMES = ("grille", "grille_irreguliere", "radiale", "organique")

# Biomes : sol, végétation (catégorie, style, densité par hectare) et minéral.
BIOMES: dict[str, dict[str, Any]] = {
    "foret_temperee": {"sol": "herbe", "vegetation": [("arbre", "feuillu", 280), ("arbre", "bouleau", 60),
                                                      ("buisson", None, 400), ("rocher", None, 20)]},
    "foret_de_coniferes": {"sol": "terre", "vegetation": [("arbre", "conifere", 420), ("buisson", None, 150),
                                                          ("rocher", None, 40)]},
    "foret_tropicale": {"sol": "terre", "vegetation": [("arbre", "palmier", 150), ("arbre", "feuillu", 300),
                                                       ("buisson", None, 900)]},
    "prairie": {"sol": "herbe", "vegetation": [("arbre", "feuillu", 8), ("buisson", None, 60), ("rocher", None, 10)]},
    "desert": {"sol": "sable", "vegetation": [("rocher", None, 60), ("buisson", None, 15)]},
    "montagne": {"sol": "roche", "vegetation": [("arbre", "conifere", 60), ("rocher", None, 200), ("buisson", None, 50)]},
    "plage": {"sol": "sable", "vegetation": [("arbre", "palmier", 12), ("rocher", None, 8)]},
    "enneige": {"sol": "neige", "vegetation": [("arbre", "conifere", 120), ("rocher", None, 30)]},
}

# Reliefs : amplitude verticale (m) et longueur d'onde dominante (m) d'un bruit fractal.
RELIEFS: dict[str, dict[str, float]] = {
    "plat": {"amplitude": 0.4, "longueur_onde": 60.0},
    "vallonne": {"amplitude": 6.0, "longueur_onde": 120.0},
    "collines": {"amplitude": 18.0, "longueur_onde": 160.0},
    "montagneux": {"amplitude": 70.0, "longueur_onde": 260.0},
    "cotier": {"amplitude": 8.0, "longueur_onde": 140.0},
}

TYPES_SCENE = ("interieur", "ville", "nature")
