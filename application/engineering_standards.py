"""Normes, matières et procédés : la connaissance d'ingénieur dont dépendent les liaisons.

Rien ici ne dépend d'un sujet. Ce sont des tables de données publiques (normes ISO/DIN de la
visserie métrique, matières, jeux de fabrication par procédé) et des règles de calcul
classiques (capacité d'une vis, arrachement dans le bois ou le plastique, flèche admissible
d'un clip, attraction de deux aimants). Chaque valeur dérivée dit d'où elle vient et ce qu'elle
ne garantit pas : une estimation n'est jamais présentée comme une mesure.

Unités : millimètres, newtons, mégapascals, grammes par centimètre cube.
"""
from __future__ import annotations

import math
from typing import Any

# --------------------------------------------------------------------------- matières
# densité g/cm³ ; module d'Young MPa ; résistance (limite élastique ou rupture en traction) MPa ;
# cisaillement MPa ; déformation admissible d'un clip (fraction, montage répété), None = matière
# inadaptée à un clip ; famille de soudage ; couleur d'aspect sRGB, rugosité, métallicité.
MATIERES: dict[str, dict[str, Any]] = {
    "pin": {"nom": "pin (résineux)", "famille": "bois", "densite": 0.50, "module": 11000, "resistance": 40,
            "cisaillement": 4.0, "clip": None, "soudage": None, "couleur": (214, 178, 124), "rugosite": 0.72, "metal": 0.0},
    "chene": {"nom": "chêne", "famille": "bois", "densite": 0.70, "module": 12000, "resistance": 60,
              "cisaillement": 6.0, "clip": None, "soudage": None, "couleur": (171, 128, 80), "rugosite": 0.68, "metal": 0.0},
    "hetre": {"nom": "hêtre", "famille": "bois", "densite": 0.72, "module": 14000, "resistance": 65,
              "cisaillement": 6.5, "clip": None, "soudage": None, "couleur": (205, 160, 112), "rugosite": 0.66, "metal": 0.0},
    "contreplaque": {"nom": "contreplaqué", "famille": "bois", "densite": 0.60, "module": 8000, "resistance": 30,
                     "cisaillement": 3.0, "clip": None, "soudage": None, "couleur": (212, 184, 140), "rugosite": 0.70, "metal": 0.0},
    "mdf": {"nom": "MDF", "famille": "bois", "densite": 0.75, "module": 3000, "resistance": 15,
            "cisaillement": 1.5, "clip": None, "soudage": None, "couleur": (168, 142, 112), "rugosite": 0.78, "metal": 0.0},
    "pla": {"nom": "PLA", "famille": "polymere", "densite": 1.24, "module": 3500, "resistance": 50,
            "cisaillement": 30.0, "clip": 0.015, "soudage": None, "couleur": (232, 232, 226), "rugosite": 0.48, "metal": 0.0},
    "petg": {"nom": "PETG", "famille": "polymere", "densite": 1.27, "module": 2100, "resistance": 45,
             "cisaillement": 27.0, "clip": 0.025, "soudage": None, "couleur": (88, 132, 188), "rugosite": 0.38, "metal": 0.0},
    "abs": {"nom": "ABS", "famille": "polymere", "densite": 1.04, "module": 2300, "resistance": 35,
            "cisaillement": 24.0, "clip": 0.020, "soudage": None, "couleur": (60, 62, 66), "rugosite": 0.5, "metal": 0.0},
    "nylon_pa12": {"nom": "polyamide PA12", "famille": "polymere", "densite": 1.01, "module": 1700, "resistance": 45,
                   "cisaillement": 30.0, "clip": 0.040, "soudage": None, "couleur": (226, 222, 210), "rugosite": 0.8, "metal": 0.0},
    "pp": {"nom": "polypropylène", "famille": "polymere", "densite": 0.90, "module": 1500, "resistance": 30,
           "cisaillement": 20.0, "clip": 0.050, "soudage": None, "couleur": (236, 236, 236), "rugosite": 0.55, "metal": 0.0},
    "resine": {"nom": "résine photopolymère", "famille": "polymere", "densite": 1.15, "module": 2500, "resistance": 50,
               "cisaillement": 30.0, "clip": 0.010, "soudage": None, "couleur": (196, 200, 206), "rugosite": 0.35, "metal": 0.0},
    "polycarbonate": {"nom": "polycarbonate PC", "famille": "polymere", "densite": 1.20, "module": 2300, "resistance": 60,
                      "cisaillement": 40.0, "clip": 0.040, "soudage": None, "couleur": (214, 224, 232), "rugosite": 0.2, "metal": 0.0},
    "acrylique": {"nom": "acrylique PMMA", "famille": "polymere", "densite": 1.18, "module": 3200, "resistance": 70,
                  "cisaillement": 40.0, "clip": None, "soudage": None, "couleur": (222, 236, 242), "rugosite": 0.12, "metal": 0.0},
    "carbone": {"nom": "composite carbone", "famille": "composite", "densite": 1.55, "module": 60000, "resistance": 500,
                "cisaillement": 60.0, "clip": None, "soudage": None, "couleur": (38, 38, 42), "rugosite": 0.32, "metal": 0.0},
    "aluminium": {"nom": "aluminium 6061-T6", "famille": "metal", "densite": 2.70, "module": 69000, "resistance": 275,
                  "cisaillement": 190.0, "clip": None, "soudage": "aluminium", "couleur": (208, 211, 216), "rugosite": 0.36, "metal": 1.0},
    "acier": {"nom": "acier S235", "famille": "metal", "densite": 7.85, "module": 210000, "resistance": 235,
              "cisaillement": 170.0, "clip": None, "soudage": "acier", "couleur": (150, 154, 160), "rugosite": 0.42, "metal": 1.0},
    "inox": {"nom": "inox A2 (304)", "famille": "metal", "densite": 8.00, "module": 193000, "resistance": 210,
             "cisaillement": 150.0, "clip": None, "soudage": "inox", "couleur": (196, 199, 204), "rugosite": 0.3, "metal": 1.0},
    "acier_zingue": {"nom": "acier zingué (visserie)", "famille": "metal", "densite": 7.85, "module": 210000, "resistance": 640,
                     "cisaillement": 380.0, "clip": None, "soudage": None, "couleur": (176, 180, 186), "rugosite": 0.34, "metal": 1.0},
    "laiton": {"nom": "laiton", "famille": "metal", "densite": 8.50, "module": 100000, "resistance": 200,
               "cisaillement": 130.0, "clip": None, "soudage": None, "couleur": (204, 164, 72), "rugosite": 0.3, "metal": 1.0},
    "neodyme": {"nom": "aimant NdFeB nickelé", "famille": "metal", "densite": 7.50, "module": 160000, "resistance": 80,
                "cisaillement": 50.0, "clip": None, "soudage": None, "couleur": (200, 202, 208), "rugosite": 0.25, "metal": 1.0},
    "electronique": {"nom": "carte électronique (FR4 et composants)", "famille": "composite", "densite": 1.85, "module": 20000,
                     "resistance": 300, "cisaillement": 50.0, "clip": None, "soudage": None, "couleur": (34, 96, 58),
                     "rugosite": 0.5, "metal": 0.0},
    "composant": {"nom": "composant acheté (enveloppe)", "famille": "composite", "densite": 3.5, "module": 50000,
                  "resistance": 100, "cisaillement": 50.0, "clip": None, "soudage": None, "couleur": (70, 72, 80),
                  "rugosite": 0.45, "metal": 0.3},
}

# Facteur de résistance d'une pièce selon son procédé (une impression FDM n'a pas la
# résistance de la matière massive, surtout entre couches) : estimation prudente.
FACTEUR_PROCEDE_RESISTANCE = {"impression_fdm": 0.6, "impression_resine": 0.8, "impression_sls": 0.85}

# --------------------------------------------------------------------------- procédés
# Jeux en millimètres, valeurs au diamètre sauf mention « par flanc ». Ce sont les cotes à
# MODÉLISER (compensation usuelle du procédé incluse), à calibrer par un essai réel.
PROCEDES: dict[str, dict[str, Any]] = {
    "impression_fdm": {"nom": "impression 3D FDM", "glissant": 0.40, "rotation": 0.45, "serrage": 0.10, "colle": 0.20,
                       "paroi_min": 1.2, "detail_min": 0.8, "axial": 0.40, "queue_aronde": 0.20, "clip": 0.30,
                       "aimant": 0.20, "compensation_trou": 0.20, "imprime": True, "decoupe_2d": False},
    "impression_resine": {"nom": "impression 3D résine", "glissant": 0.20, "rotation": 0.25, "serrage": 0.05, "colle": 0.10,
                          "paroi_min": 0.8, "detail_min": 0.4, "axial": 0.25, "queue_aronde": 0.10, "clip": 0.15,
                          "aimant": 0.10, "compensation_trou": 0.05, "imprime": True, "decoupe_2d": False},
    "impression_sls": {"nom": "impression 3D SLS", "glissant": 0.30, "rotation": 0.30, "serrage": 0.10, "colle": 0.15,
                       "paroi_min": 1.0, "detail_min": 0.6, "axial": 0.40, "queue_aronde": 0.15, "clip": 0.25,
                       "aimant": 0.15, "compensation_trou": 0.10, "imprime": True, "decoupe_2d": False},
    "usinage": {"nom": "usinage CNC", "glissant": 0.02, "rotation": 0.05, "serrage": 0.02, "colle": 0.05,
                "paroi_min": 0.8, "detail_min": 0.5, "axial": 0.10, "queue_aronde": 0.03, "clip": 0.05,
                "aimant": 0.05, "compensation_trou": 0.0, "imprime": False, "decoupe_2d": False},
    "decoupe_plaque": {"nom": "découpe de plaque (laser, jet d'eau, fraisage 2D)", "glissant": 0.15, "rotation": 0.20,
                       "serrage": 0.05, "colle": 0.10, "paroi_min": 2.0, "detail_min": 1.0, "axial": 0.30,
                       "queue_aronde": 0.10, "clip": 0.20, "aimant": 0.10, "compensation_trou": 0.0,
                       "imprime": False, "decoupe_2d": True},
    # paroi : règle d'ébénisterie (un tourillon Ø6 dans un panneau de 12 mm laisse 3 mm de chaque côté)
    "bois": {"nom": "menuiserie (bois)", "glissant": 0.30, "rotation": 0.40, "serrage": 0.0, "colle": 0.10,
             "paroi_min": 3.0, "detail_min": 2.0, "axial": 0.50, "queue_aronde": 0.15, "clip": None,
             "aimant": 0.20, "compensation_trou": 0.0, "imprime": False, "decoupe_2d": False},
    "tolerie": {"nom": "tôlerie (découpe, pliage, soudage)", "glissant": 0.20, "rotation": 0.30, "serrage": 0.02,
                "colle": 0.10, "paroi_min": 1.0, "detail_min": 1.0, "axial": 0.30, "queue_aronde": None, "clip": 0.10,
                "aimant": 0.10, "compensation_trou": 0.0, "imprime": False, "decoupe_2d": True},
    "moulage": {"nom": "moulage par injection", "glissant": 0.10, "rotation": 0.15, "serrage": 0.05, "colle": 0.10,
                "paroi_min": 1.0, "detail_min": 0.5, "axial": 0.20, "queue_aronde": 0.08, "clip": 0.10,
                "aimant": 0.10, "compensation_trou": 0.0, "imprime": False, "decoupe_2d": False},
    "achat": {"nom": "composant acheté", "glissant": 0.20, "rotation": 0.25, "serrage": 0.02, "colle": 0.10,
              "paroi_min": 1.0, "detail_min": 0.5, "axial": 0.20, "queue_aronde": None, "clip": None,
              "aimant": 0.10, "compensation_trou": 0.0, "imprime": False, "decoupe_2d": False},
}

# Procédé naturel d'une matière quand la demande ne le dit pas (règle de fabrication courante).
PROCEDE_PAR_FAMILLE = {"bois": "bois", "polymere": "impression_fdm", "metal": "usinage", "composite": "decoupe_plaque"}

# --------------------------------------------------------------------------- filetage ISO 261/262
# d : (pas P, diamètre de perçage avant taraudage). Le diamètre du noyau d3 = d - 1,22687 P.
FILETAGE = {2.0: (0.40, 1.60), 2.5: (0.45, 2.05), 3.0: (0.50, 2.50), 4.0: (0.70, 3.30), 5.0: (0.80, 4.20),
            6.0: (1.00, 5.00), 8.0: (1.25, 6.80), 10.0: (1.50, 8.50), 12.0: (1.75, 10.20)}
DIAMETRES = sorted(FILETAGE)
# Section résistante As (mm²), ISO 898-1.
SECTION_RESISTANTE = {2.0: 2.07, 2.5: 3.39, 3.0: 5.03, 4.0: 8.78, 5.0: 14.2, 6.0: 20.1, 8.0: 36.6, 10.0: 58.0, 12.0: 84.3}
# Contrainte d'épreuve (MPa) des classes de qualité, ISO 898-1 / ISO 3506.
CLASSES = {"8.8": 580.0, "4.8": 310.0, "10.9": 830.0, "12.9": 970.0, "A2-70": 450.0}

# ISO 273 : trous de passage fin / moyen / large.
PASSAGE_ISO273 = {2.0: (2.2, 2.4, 2.6), 2.5: (2.7, 2.9, 3.1), 3.0: (3.2, 3.4, 3.6), 4.0: (4.3, 4.5, 4.8),
                  5.0: (5.3, 5.5, 5.8), 6.0: (6.4, 6.6, 7.0), 8.0: (8.4, 9.0, 10.0), 10.0: (10.5, 11.0, 12.0),
                  12.0: (13.0, 13.5, 14.5)}

# ISO 4762 vis à tête cylindrique à six pans creux : dk, k, s (clé), t (profondeur d'empreinte),
# diamètre de lamage (DIN 974-1).
ISO4762 = {2.0: (3.8, 2.0, 1.5, 1.0, 4.3), 2.5: (4.5, 2.5, 2.0, 1.1, 5.0), 3.0: (5.5, 3.0, 2.5, 1.3, 6.0),
           4.0: (7.0, 4.0, 3.0, 2.0, 8.0), 5.0: (8.5, 5.0, 4.0, 2.5, 10.0), 6.0: (10.0, 6.0, 5.0, 3.0, 11.0),
           8.0: (13.0, 8.0, 6.0, 4.0, 15.0), 10.0: (16.0, 10.0, 8.0, 5.0, 18.0), 12.0: (18.0, 12.0, 10.0, 6.0, 20.0)}
# ISO 10642 vis à tête fraisée à six pans creux (90°) : dk théorique, k, s.
ISO10642 = {3.0: (6.72, 1.86, 2.0), 4.0: (8.96, 2.48, 2.5), 5.0: (11.20, 3.10, 3.0), 6.0: (13.44, 3.72, 4.0),
            8.0: (17.92, 4.96, 5.0), 10.0: (22.40, 6.20, 6.0), 12.0: (26.88, 7.44, 8.0)}
# ISO 7380-1 vis à tête bombée à six pans creux : dk, k, s.
ISO7380 = {3.0: (5.7, 1.65, 2.0), 4.0: (7.6, 2.20, 2.5), 5.0: (9.5, 2.75, 3.0), 6.0: (10.5, 3.30, 4.0),
           8.0: (14.0, 4.40, 5.0), 10.0: (17.5, 5.50, 6.0), 12.0: (21.0, 6.60, 8.0)}
# ISO 4017 vis à tête hexagonale : s (sur plats), k.
ISO4017 = {3.0: (5.5, 2.0), 4.0: (7.0, 2.8), 5.0: (8.0, 3.5), 6.0: (10.0, 4.0), 8.0: (13.0, 5.3),
           10.0: (16.0, 6.4), 12.0: (18.0, 7.5)}
# ISO 4032 écrou hexagonal : s, m.
ISO4032 = {2.0: (4.0, 1.6), 2.5: (5.0, 2.0), 3.0: (5.5, 2.4), 4.0: (7.0, 3.2), 5.0: (8.0, 4.7), 6.0: (10.0, 5.2),
           8.0: (13.0, 6.8), 10.0: (16.0, 8.4), 12.0: (18.0, 10.8)}
# ISO 7089 rondelle plate : d1, d2, h.
ISO7089 = {2.0: (2.2, 5.0, 0.3), 2.5: (2.7, 6.0, 0.5), 3.0: (3.2, 7.0, 0.5), 4.0: (4.3, 9.0, 0.8), 5.0: (5.3, 10.0, 1.0),
           6.0: (6.4, 12.0, 1.6), 8.0: (8.4, 16.0, 1.6), 10.0: (10.5, 20.0, 2.0), 12.0: (13.0, 24.0, 2.5)}

SERIE_LONGUEURS = [3, 4, 5, 6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100, 110, 120]
# Plages de longueur commercialisées (mm) par norme et diamètre.
PLAGE_LONGUEURS = {
    "ISO 4762": {2.0: (3, 20), 2.5: (4, 25), 3.0: (5, 30), 4.0: (6, 40), 5.0: (8, 50), 6.0: (10, 60), 8.0: (12, 80),
                 10.0: (16, 100), 12.0: (20, 120)},
    "ISO 10642": {3.0: (8, 30), 4.0: (8, 40), 5.0: (8, 50), 6.0: (8, 60), 8.0: (10, 80), 10.0: (12, 100), 12.0: (20, 100)},
    "ISO 7380": {3.0: (5, 30), 4.0: (6, 40), 5.0: (8, 40), 6.0: (10, 40), 8.0: (12, 50), 10.0: (16, 50), 12.0: (20, 50)},
    "ISO 4017": {3.0: (6, 30), 4.0: (8, 40), 5.0: (10, 50), 6.0: (12, 60), 8.0: (16, 80), 10.0: (20, 100), 12.0: (25, 120)},
}

# DIN 7997 vis à bois à tête fraisée : diamètre nominal -> dk ; longueurs usuelles.
DIN7997 = {2.5: 4.7, 3.0: 5.6, 3.5: 6.5, 4.0: 7.5, 4.5: 8.3, 5.0: 9.2, 6.0: 10.9}
SERIE_VIS_BOIS = [10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80]
NOYAU_VIS_BOIS = 0.70   # diamètre du noyau ≈ 0,7 d (profil DIN 7998)

# ISO 2338 goupilles cylindriques (m6) : diamètre -> (longueur min, longueur max).
ISO2338 = {1.0: (4, 10), 1.5: (4, 16), 2.0: (4, 20), 2.5: (6, 24), 3.0: (6, 30), 4.0: (8, 40), 5.0: (10, 50),
           6.0: (12, 60), 8.0: (14, 80), 10.0: (18, 95), 12.0: (22, 100)}
SERIE_GOUPILLES = [4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85,
                   90, 95, 100]
# DIN 68150 tourillons en hêtre (diamètre, longueur).
DIN68150 = [(5, 25), (5, 30), (6, 25), (6, 30), (6, 35), (6, 40), (8, 30), (8, 35), (8, 40), (8, 45), (8, 50),
            (10, 40), (10, 45), (10, 50), (10, 60), (12, 50), (12, 60)]

# Aimants néodyme N42 en disque, tailles de catalogue courantes (diamètre, hauteur).
AIMANTS = [(3, 1), (3, 2), (4, 1), (4, 2), (5, 1), (5, 2), (5, 3), (6, 1), (6, 2), (6, 3), (8, 1), (8, 2), (8, 3), (8, 4),
           (10, 1), (10, 2), (10, 3), (10, 5), (12, 2), (12, 3), (15, 2), (15, 3), (15, 5), (20, 2), (20, 3), (20, 5)]
BR_N42 = 1.29       # induction rémanente (T), plage N42 1,28–1,32
MU0 = 4e-7 * math.pi

# Inserts filetés à chaud pour pièces imprimées : valeurs TYPIQUES de fournisseurs, à vérifier
# sur la fiche du produit acheté : d -> (longueur, diamètre extérieur, diamètre du logement).
INSERTS_CHAUD = {2.0: (3.0, 3.6, 3.2), 2.5: (4.0, 4.0, 3.6), 3.0: (5.7, 4.6, 4.0), 4.0: (8.1, 6.3, 5.6),
                 5.0: (9.5, 7.1, 6.4)}
# Variantes de longueur proposées au catalogue (la plus longue d'abord) : un insert court quand la matière manque.
INSERTS_VARIANTES = {2.0: [(3.0, 3.6, 3.2)], 2.5: [(4.0, 4.0, 3.6), (3.0, 4.0, 3.6)],
                     3.0: [(5.7, 4.6, 4.0), (4.0, 4.6, 4.0), (3.0, 4.6, 4.0)], 4.0: [(8.1, 6.3, 5.6), (4.0, 6.3, 5.6)],
                     5.0: [(9.5, 7.1, 6.4), (5.8, 7.1, 6.4)]}


# Épaisseurs commerciales : panneaux de bois, tôles, plaques usinables.
EPAISSEURS_PANNEAU_BOIS = [3, 5, 6, 8, 10, 12, 15, 18, 22, 25, 30]
EPAISSEURS_TOLE = [0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
EPAISSEURS_PLAQUE = [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0]


def paroi_par_defaut(dims: list[float], cle_procede: str, cle_matiere: str) -> tuple[float, str]:
    """Épaisseur de paroi d'un contenant quand la demande ne la donne pas, et la règle employée.

    Bois : panneau standard le plus proche d'1/15 de la plus petite dimension (au moins 6 mm) ;
    tôle ou plaque : épaisseur standard la plus proche d'1/60 ; impression ou moulage : deux fois la
    paroi minimale du procédé, et au moins 1/40 de la plus petite dimension.
    """
    petit = float(min(dims))
    famille = MATIERES[cle_matiere]["famille"]
    if famille == "bois":
        cible = max(6.0, petit / 15.0)
        valeur = min(EPAISSEURS_PANNEAU_BOIS, key=lambda e: (abs(e - cible), e))
        return float(valeur), f"panneau standard le plus proche de {cible:.1f} mm (1/15 de {petit:g} mm)"
    if cle_procede in ("tolerie", "decoupe_plaque") or famille == "metal":
        table = EPAISSEURS_TOLE if cle_procede == "tolerie" else EPAISSEURS_PLAQUE
        cible = max(PROCEDES[cle_procede]["paroi_min"], petit / 60.0)
        valeur = min(table, key=lambda e: (abs(e - cible), e))
        return float(valeur), f"épaisseur standard la plus proche de {cible:.1f} mm"
    cible = max(2 * PROCEDES[cle_procede]["paroi_min"], petit / 40.0)
    valeur = round(cible / 0.4) * 0.4 if PROCEDES[cle_procede]["imprime"] else round(cible, 1)
    return float(round(valeur, 2)), f"deux fois la paroi minimale du procédé ({PROCEDES[cle_procede]['paroi_min']:g} mm), au moins 1/40 de {petit:g} mm"


# Vocabulaire libre → clés connues (une lecture sans schéma imposé écrit « Aluminium 7075-T6 », « Usinage CNC »).
MOTS_MATIERE = {"pin": "pin", "sapin": "pin", "epicea": "pin", "resineux": "pin", "chene": "chene", "hetre": "hetre",
                "contreplaque": "contreplaque", "multiplis": "contreplaque", "mdf": "mdf", "medium": "mdf",
                "pla": "pla", "petg": "petg", "abs": "abs", "nylon": "nylon_pa12", "polyamide": "nylon_pa12", "pa12": "nylon_pa12",
                "polypropylene": "pp", "pp": "pp", "resine": "resine", "photopolymere": "resine", "acrylique": "acrylique",
                "pmma": "acrylique", "plexiglas": "acrylique", "polycarbonate": "polycarbonate", "pc": "polycarbonate",
                "lexan": "polycarbonate", "carbone": "carbone", "aluminium": "aluminium", "alu": "aluminium",
                "inox": "inox", "inoxydable": "inox", "acier": "acier", "laiton": "laiton", "pcb": "electronique",
                "fr4": "electronique", "electronique": "electronique"}
MOTS_PROCEDE = {"fdm": "impression_fdm", "fff": "impression_fdm", "impression": "impression_fdm", "imprime": "impression_fdm",
                "sla": "impression_resine", "dlp": "impression_resine", "sls": "impression_sls", "mjf": "impression_sls",
                "cnc": "usinage", "usinage": "usinage", "fraisage": "usinage", "tournage": "usinage",
                "laser": "decoupe_plaque", "decoupe": "decoupe_plaque", "jet": "decoupe_plaque",
                "menuiserie": "bois", "ebenisterie": "bois", "bois": "bois", "tolerie": "tolerie", "pliage": "tolerie",
                "soudage": "tolerie", "moulage": "moulage", "injection": "moulage", "achat": "achat", "achete": "achat",
                "commerce": "achat"}


def _mots(texte) -> list[str]:
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode().lower()
    return [m for m in re.split(r"[^a-z0-9]+", t) if m]


def resoudre_matiere(texte) -> str | None:
    """Clé de matière pour un texte libre ; None si aucun mot n'est reconnu (pas de devinette)."""
    if texte in MATIERES:
        return texte
    mots = _mots(texte)
    if "resine" in mots and ("impression" in mots or "sla" in mots):
        return "resine"
    for m in mots:
        if m in ("inoxydable", "inox"):
            return "inox"
    for m in mots:
        if m in MOTS_MATIERE:
            return MOTS_MATIERE[m]
    return None


def resoudre_procede(texte) -> str | None:
    if texte in PROCEDES:
        return texte
    mots = _mots(texte)
    if "resine" in mots and "impression" in mots:
        return "impression_resine"
    for m in mots:
        if m in MOTS_PROCEDE:
            return MOTS_PROCEDE[m]
    return None


# --------------------------------------------------------------------------- utilitaires

def lineaire(srgb: tuple[int, int, int]) -> list[float]:
    """Couleur sRGB 0–255 vers composantes linéaires (glTF baseColorFactor)."""
    out = []
    for c in srgb:
        x = c / 255.0
        out.append(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4)
    return out


def matiere(cle: str) -> dict[str, Any]:
    if cle not in MATIERES:
        raise ValueError(f"matière inconnue : {cle}")
    return MATIERES[cle]


def procede(cle: str) -> dict[str, Any]:
    if cle not in PROCEDES:
        raise ValueError(f"procédé inconnu : {cle}")
    return PROCEDES[cle]


def resistance_effective(cle_matiere: str, cle_procede: str, grandeur: str = "resistance") -> float:
    return float(matiere(cle_matiere)[grandeur]) * FACTEUR_PROCEDE_RESISTANCE.get(cle_procede, 1.0)


def diametre_noyau(d: float) -> float:
    return d - 1.22687 * FILETAGE[d][0]


def trou_passage(d: float, classe: str = "moyen") -> float:
    return PASSAGE_ISO273[d][{"fin": 0, "moyen": 1, "large": 2}[classe]]


def longueur_normalisee(serie: list[int], minimum: float, maximum: float | None = None,
                        plage: tuple[float, float] | None = None) -> int | None:
    """Plus petite longueur de la série ≥ minimum (et ≤ maximum), dans la plage commercialisée."""
    for longueur in serie:
        if longueur + 1e-9 < minimum:
            continue
        if maximum is not None and longueur > maximum + 1e-9:
            return None
        if plage and not plage[0] <= longueur <= plage[1]:
            continue
        return longueur
    return None


def plus_grande_longueur(serie: list[int], maximum: float, plage: tuple[float, float] | None = None) -> int | None:
    meilleure = None
    for longueur in serie:
        if longueur <= maximum + 1e-9 and (not plage or plage[0] <= longueur <= plage[1]):
            meilleure = longueur
    return meilleure


def format_mm(x: float) -> str:
    return f"{x:g}".replace(".", ",")


# --------------------------------------------------------------------------- capacités (estimations)

def capacite_traction_vis(d: float, classe: str = "8.8") -> float:
    """Charge d'épreuve As × Sp (N), ISO 898-1 : limite de la vis seule, pas de l'assemblage."""
    return SECTION_RESISTANTE[d] * CLASSES[classe]


def arrachement_bois(d: float, penetration: float, densite: float) -> float:
    """Résistance caractéristique à l'arrachement d'une vis à bois (N), EN 1995-1-1 éq. 8.40a.

    f_ax,k = 0,52 d^-0,5 l_ef^-0,1 ρ_k^0,8 ; F = f_ax,k d l_ef. La norme la valide pour 6 ≤ d ≤ 12 mm :
    pour une petite vis d'ébénisterie c'est un ordre de grandeur, pas une valeur de calcul.
    """
    rho = densite * 1000.0
    l_ef = max(1.0, penetration - d)
    f_ax = 0.52 * d ** -0.5 * l_ef ** -0.1 * rho ** 0.8
    return f_ax * d * l_ef


def arrachement_plastique(d: float, engagement: float, cisaillement: float) -> float:
    """Arrachement d'une vis autotaraudeuse ou d'un filet dans un polymère (N), modèle de cisaillement
    du cylindre de filet (π d L τ × 0,5 pour la forme du filet) : ordre de grandeur."""
    return math.pi * d * engagement * cisaillement * 0.5


def force_aimants(d: float, h: float, ecart: float, br: float = BR_N42) -> float:
    """Attraction de deux aimants disques identiques coaxiaux (N) séparés d'un écart (mm).

    Champ axial d'un cylindre aimanté (modèle des charges) au plan médian, somme des deux aimants,
    puis pression de Maxwell B²A/(2μ0). Estimation à ±50 % : la force réelle se mesure.
    """
    r = d / 2.0
    z = ecart / 2.0
    b = br * ((h + z) / math.sqrt(r * r + (h + z) ** 2) - z / math.sqrt(r * r + z * z))
    aire = math.pi * (r * 1e-3) ** 2
    return b * b * aire / (2 * MU0)


def clip_cantilever(longueur: float, epaisseur: float, largeur: float, fleche: float, module: float,
                    angle_entree_deg: float = 30.0, frottement: float = 0.4) -> dict[str, float]:
    """Crochet en porte-à-faux de section rectangulaire constante (méthode de calcul usuelle des
    clips) : déformation ε = 1,5 y h / l², effort de flexion P = b h² E ε / (6 l),
    effort d'emboîtement W = P (μ + tan α) / (1 − μ tan α)."""
    eps = 1.5 * fleche * epaisseur / (longueur * longueur)
    p = largeur * epaisseur ** 2 * module * eps / (6.0 * longueur)
    t = math.tan(math.radians(angle_entree_deg))
    w = p * (frottement + t) / max(1e-6, 1.0 - frottement * t)
    return {"deformation": eps, "effort_flexion_N": p, "effort_emboitement_N": w}


# --------------------------------------------------------------------------- désignations et contrôle

def designation_vis(norme: str, d: float, longueur: float, classe: str) -> str:
    return f"{norme} M{format_mm(d)}×{format_mm(longueur)} – {classe}"


def verifier_quincaillerie(article: dict[str, Any]) -> list[str]:
    """Écarts d'un article de quincaillerie à sa norme : la liste vide signifie conforme."""
    ecarts: list[str] = []
    norme, d = article.get("norme"), article.get("d")
    longueur = article.get("longueur")
    if norme in ("ISO 4762", "ISO 10642", "ISO 7380", "ISO 4017"):
        table = {"ISO 4762": ISO4762, "ISO 10642": ISO10642, "ISO 7380": ISO7380, "ISO 4017": ISO4017}[norme]
        if d not in table:
            return [f"{norme} n'existe pas en M{d:g}"]
        if longueur not in SERIE_LONGUEURS:
            ecarts.append(f"longueur {longueur} hors série normalisée")
        plage = PLAGE_LONGUEURS[norme].get(d)
        if plage and not plage[0] <= longueur <= plage[1]:
            ecarts.append(f"longueur {longueur} hors plage commercialisée {plage}")
        if article.get("classe") not in CLASSES:
            ecarts.append("classe de qualité inconnue")
    elif norme == "ISO 4032":
        if d not in ISO4032:
            ecarts.append(f"écrou ISO 4032 inexistant en M{d:g}")
    elif norme == "ISO 7089":
        if d not in ISO7089:
            ecarts.append(f"rondelle ISO 7089 inexistante en M{d:g}")
    elif norme == "DIN 7997":
        if d not in DIN7997:
            ecarts.append(f"vis à bois DIN 7997 inexistante en {d:g} mm")
        if longueur not in SERIE_VIS_BOIS:
            ecarts.append(f"longueur {longueur} hors série usuelle")
    elif norme == "ISO 2338":
        plage = ISO2338.get(d)
        if not plage:
            ecarts.append(f"goupille ISO 2338 inexistante en {d:g} mm")
        elif longueur not in SERIE_GOUPILLES or not plage[0] <= longueur <= plage[1]:
            ecarts.append(f"longueur {longueur} hors série pour Ø{d:g}")
    elif norme == "DIN 68150":
        if (int(d), int(longueur)) not in DIN68150:
            ecarts.append(f"tourillon {d:g}×{longueur:g} hors série DIN 68150")
    elif norme == "aimant N42":
        if (int(d), int(article.get("h", 0))) not in AIMANTS:
            ecarts.append(f"aimant {d:g}×{article.get('h')} hors catalogue courant")
    elif norme == "insert à chaud":
        if d not in INSERTS_CHAUD:
            ecarts.append(f"insert M{d:g} inconnu")
    elif norme == "entretoise F/F":
        if d not in ISO4032 or longueur not in (5, 6, 8, 10, 12, 15, 20, 25, 30, 35, 40):
            ecarts.append("entretoise hors série")
    else:
        ecarts.append(f"norme inconnue : {norme}")
    return ecarts
