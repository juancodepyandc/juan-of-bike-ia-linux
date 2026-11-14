"""Assemblages d'ingénierie : graphe, liaisons usinées sur les deux pièces, contrôles mesurés.

Les exigences sont écrites à la main pour tester le moteur natif de façon déterministe (la lecture
d'une demande par le modèle local est testée à part, avec un modèle substitué). Chaque contrôle
porte sur les solides construits et les fichiers écrits, jamais sur des valeurs recopiées.
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("trimesh")
pytest.importorskip("manifold3d")
pytest.importorskip("shapely")

from application import engineering_standards as normes  # noqa: E402
from application.engineering_assembly import (ErreurConception, decomposer_contenants, developper_motifs,  # noqa: E402
                                              interface_principale, normaliser, placer, union, volume)
from application.engineering_assembly_checks import (construire, controle_interferences, registre)  # noqa: E402
from application.engineering_assembly_pipeline import concevoir, fermetures_sans_outil  # noqa: E402
from application.engineering_mates import generer  # noqa: E402
from application.engineering_requirements import lire_exigences  # noqa: E402

BOITE = {"titre": "Boîte", "procede": "bois", "matiere": "pin",
         "pieces": [{"id": "caisse", "nom": "Caisse", "forme": "bac", "dimensions_mm": [300, 200, 150], "paroi_mm": 12,
                     "ouverture": "dessus", "origine": "fabrique"},
                    {"id": "couvercle", "nom": "Couvercle", "forme": "plaque", "dimensions_mm": [300, 200, 12],
                     "origine": "fabrique", "position": {"par_rapport_a": "caisse", "cote": "dessus"}}],
         "liaisons": [{"entre": ["caisse", "couvercle"], "type": "charniere", "bord": "arriere", "demontable": False},
                      {"entre": ["caisse", "couvercle"], "type": "clip", "bord": "avant", "demontable": True}]}

DRONE = {"titre": "Châssis", "procede": "impression_fdm", "matiere": "petg",
         "pieces": [{"id": "plaque_basse", "nom": "Plaque basse", "forme": "plaque", "dimensions_mm": [90, 90, 3], "origine": "fabrique"},
                    {"id": "bras", "nom": "Bras", "forme": "barre", "dimensions_mm": [120, 18, 6], "origine": "fabrique",
                     "position": {"par_rapport_a": "plaque_basse", "cote": "dessus"},
                     "motif": {"type": "polaire", "nombre": 4, "angle_depart_deg": 45}},
                    {"id": "plaque_haute", "nom": "Plaque haute", "forme": "plaque", "dimensions_mm": [90, 90, 3], "origine": "fabrique",
                     "position": {"par_rapport_a": "bras", "cote": "dessus", "centre_sur": "plaque_basse"}},
                    {"id": "moteur", "nom": "Moteur", "forme": "cylindre", "dimensions_mm": [28, 20], "origine": "achete",
                     "position": {"par_rapport_a": "bras", "cote": "dessus", "alignement": {"x": "max"}},
                     "trous_existants": {"vis": "M3", "entraxe_mm": [16, 16], "profondeur_mm": 4}}],
         "liaisons": [{"entre": ["plaque_haute", "bras", "plaque_basse"], "type": "boulon_ecrou", "demontable": True},
                      {"entre": ["moteur", "bras"], "type": "vis", "demontable": True}]}

BOITIER = {"titre": "Boîtier", "procede": "impression_fdm", "matiere": "petg",
           "pieces": [{"id": "boitier", "nom": "Boîtier", "forme": "bac", "dimensions_mm": [90, 70, 35], "paroi_mm": 2.4,
                       "ouverture": "dessus", "origine": "fabrique"},
                      {"id": "couvercle", "nom": "Couvercle", "forme": "plaque", "dimensions_mm": [90, 70, 2.4],
                       "origine": "fabrique", "position": {"par_rapport_a": "boitier", "cote": "dessus"}},
                      {"id": "carte", "nom": "Carte", "forme": "plaque", "dimensions_mm": [60, 40, 1.6], "origine": "achete",
                       "matiere": "electronique", "position": {"par_rapport_a": "boitier", "cote": "dedans", "hauteur_mm": 6}}],
           "liaisons": [{"entre": ["couvercle", "boitier"], "type": "clip", "demontable": True},
                        {"entre": ["carte", "boitier"], "type": "vis", "demontable": True}]}


@pytest.fixture(scope="module")
def boite(tmp_path_factory):
    d = tmp_path_factory.mktemp("boite")
    return concevoir(json.loads(json.dumps(BOITE)), d, rendre_f3d=False), d


@pytest.fixture(scope="module")
def drone(tmp_path_factory):
    d = tmp_path_factory.mktemp("drone")
    return concevoir(json.loads(json.dumps(DRONE)), d, rendre_f3d=False), d


@pytest.fixture(scope="module")
def boitier(tmp_path_factory):
    d = tmp_path_factory.mktemp("boitier")
    return concevoir(json.loads(json.dumps(BOITIER)), d, rendre_f3d=False), d


def _liaisons(rapport, type_):
    return [l for l in rapport["liaisons"] if l["type"] == type_]


def _glb(chemin):
    raw = Path(chemin).read_bytes()
    n = struct.unpack_from("<I", raw, 12)[0]
    return json.loads(raw[20:20 + n])


# --------------------------------------------------------------------------- graphe

def test_normalisation_nomme_les_references_inconnues():
    ex = json.loads(json.dumps(BOITE))
    ex["liaisons"].append({"entre": ["caisse", "poignee"], "type": "vis"})
    with pytest.raises(ErreurConception) as e:
        normaliser(ex)
    assert "poignee" in str(e.value) and "caisse" in str(e.value)


def test_motif_polaire_repete_ce_qui_suit_et_garde_unique_la_piece_centree():
    dec = []
    g = developper_motifs(normaliser(json.loads(json.dumps(DRONE))), dec)
    ids = {p["id"] for p in g["pieces"]}
    assert {"bras_1", "bras_2", "bras_3", "bras_4", "moteur_1", "moteur_4"} <= ids
    assert "plaque_haute" in ids and not any(i.startswith("plaque_haute_") for i in ids)
    boulons = [l for l in g["liaisons"] if l["type"] == "boulon_ecrou"]
    assert len(boulons) == 4 and all(l["entre"][0] == "plaque_haute" for l in boulons)


def test_bac_en_bois_devient_cinq_panneaux_un_bac_imprime_reste_monobloc():
    dec = []
    g = decomposer_contenants(normaliser(json.loads(json.dumps(BOITE))), dec)
    panneaux = [p["id"] for p in g["pieces"] if p.get("_panneau_de") == "caisse"]
    assert len(panneaux) == 5
    types = {l["type"] for l in g["liaisons"] if all(e.startswith("caisse_") for e in l["entre"])}
    assert {"vis", "colle", "emmanchement"} <= types
    g2 = decomposer_contenants(normaliser(json.loads(json.dumps(BOITIER))), [])
    assert any(p["id"] == "boitier" and p["forme"] == "bac" for p in g2["pieces"])


def test_placement_par_contact_dans_le_repere_de_la_reference():
    dec = []
    g = decomposer_contenants(developper_motifs(normaliser(json.loads(json.dumps(DRONE))), dec), dec)
    pieces = placer(g, dec)
    for k in range(1, 5):
        bras, moteur = pieces[f"bras_{k}"], pieces[f"moteur_{k}"]
        # le moteur affleure le bout du bras le long de SA longueur (bras tourné de 45° + k·90°)
        axe = np.array([math.cos(math.radians(bras.orientation_deg)), math.sin(math.radians(bras.orientation_deg)), 0.0])
        bout = float(np.asarray(bras.centre) @ axe) + 60.0
        assert float(np.asarray(moteur.centre) @ axe) + 14.0 == pytest.approx(bout, abs=1e-6)
        assert moteur.solide.bounding_box()[2] == pytest.approx(bras.solide.bounding_box()[5], abs=1e-6)
    haute, basse = pieces["plaque_haute"], pieces["plaque_basse"]
    assert haute.orientation_deg == pytest.approx(basse.orientation_deg)
    assert haute.solide.bounding_box()[2] == pytest.approx(pieces["bras_1"].solide.bounding_box()[5], abs=1e-6)


# --------------------------------------------------------------------------- liaisons et usinages

def test_vis_a_bois_usine_les_deux_pieces_et_reste_normalisee(boite):
    rapport, _ = boite
    vis = [l for l in _liaisons(rapport, "vis") if l["calculs"].get("mode") == "bois"]
    assert vis, "le fond doit être vissé dans les panneaux"
    for l in vis:
        c = l["calculs"]
        assert c["diametre_mm"] in normes.DIN7997 and c["longueur_mm"] in normes.SERIE_VIS_BOIS
        assert c["trou_passage_mm"] > c["diametre_mm"] > c["trou_recepteur_mm"]
        assert c["engagement_mm"] >= 3 * c["diametre_mm"]
    pieces = {p["id"]: p for p in rapport["pieces"]}
    articles = [p for p in rapport["pieces"] if (p.get("designation") or "").startswith("vis à bois")]
    assert articles and all(Path(p["stl"]).is_file() for p in articles)
    assert rapport["controles"]["quincaillerie_normalisee"]["ok"]
    assert rapport["controles"]["ligaments"]["ok"] and rapport["controles"]["ligaments"]["trous_controles"] > 0
    assert pieces["caisse_fond"]["masse_g"] < 300 * 200 * 12 * normes.MATIERES["pin"]["densite"] * 1e-3


def test_usinages_presents_sur_les_deux_pieces_d_une_liaison():
    dec = []
    g = decomposer_contenants(normaliser(json.loads(json.dumps(BOITE))), dec)
    pieces = placer(g, dec)
    l = next(x for x in g["liaisons"] if x["type"] == "vis" and x["entre"] == ["caisse_fond", "caisse_avant"])
    [r] = generer(l, pieces)
    assert set(r.retraits) == {"caisse_fond", "caisse_avant"}
    for pid, coupes in r.retraits.items():
        avant = volume(pieces[pid].solide)
        apres = volume(pieces[pid].solide - union(coupes))
        assert apres < avant - 1.0, f"{pid} n'a pas été usinée"
    vis = [q for q in r.quincaillerie if "vis" in q.id]
    for q in vis:
        b = q.solide.bounding_box()
        assert b[2] < pieces["caisse_fond"].solide.bounding_box()[5] < b[5], "la vis traverse le fond et entre dans le panneau"


def test_boulons_de_la_pile_et_ecrous_normalises(drone):
    rapport, _ = drone
    boulons = _liaisons(rapport, "boulon_ecrou")
    assert len(boulons) == 4
    for l in boulons:
        c = l["calculs"]
        assert c["diametre_mm"] == 3.0
        assert c["longueur_mm"] in normes.SERIE_LONGUEURS and c["longueur_mm"] >= c["epaisseur_serree_mm"]
    designations = {q["designation"] for q in rapport["nomenclature"]["quincaillerie"]}
    assert any(d.startswith("ISO 4762 M3×") for d in designations)
    assert any("ISO 4032" in d for d in designations) and any("ISO 7089" in d for d in designations)


def test_motif_impose_par_un_composant_achete_ajoute_une_platine_de_renfort(drone):
    rapport, _ = drone
    vis = _liaisons(rapport, "vis")
    assert len(vis) == 4 and all(l["calculs"]["mode"] == "filetage_existant" for l in vis)
    assert all(l["calculs"]["renfort_diametre_mm"] > 18.0 for l in vis)          # le bras ne fait que 18 mm
    assert all(l["calculs"]["engagement_mm"] <= 4.0 + 1e-6 for l in vis)           # filet moteur déclaré : 4 mm
    assert rapport["controles"]["ligaments"]["ok"]


def test_emmanchement_imprime_serrage_mesure_conforme_au_registre(tmp_path):
    ex = {"titre": "Blocs goupillés", "procede": "impression_fdm", "matiere": "pla",
          "pieces": [{"id": "a", "nom": "A", "forme": "bloc", "dimensions_mm": [60, 40, 20], "origine": "fabrique"},
                     {"id": "b", "nom": "B", "forme": "bloc", "dimensions_mm": [60, 40, 20], "origine": "fabrique",
                      "position": {"par_rapport_a": "a", "cote": "dessus"}}],
          "liaisons": [{"entre": ["a", "b"], "type": "emmanchement", "demontable": False}]}
    rapport = concevoir(ex, tmp_path, rendre_f3d=False)
    voulues = rapport["controles"]["interferences"]["voulues"]
    assert voulues and not rapport["controles"]["interferences"]["collisions"]
    for v in voulues:
        assert v["nature"] == "serrage" and abs(v["volume_mm3"] - v["attendu_mm3"]) <= 0.45 * v["attendu_mm3"]
    assert rapport["verdict"] == "conforme"


def test_clip_refuse_dans_le_bois_puis_aimant(boite):
    rapport, _ = boite
    fermeture = [l for l in rapport["liaisons"] if l.get("type_demande") == "clip"]
    assert fermeture and fermeture[0]["type"] == "aimant"
    assert any("clip remplacé par aimant" in d["decision"] for d in rapport["decisions"])
    assert fermeture[0]["calculs"]["force_totale_N"] >= 2 * fermeture[0]["calculs"]["effort_N"] * 0.999


def test_clip_imprime_dans_la_deformation_admissible(boitier):
    rapport, d = boitier
    [clip] = _liaisons(rapport, "clip")
    for c in clip["calculs"]["crochets"]:
        assert c["deformation"] <= c["deformation_admissible"]
        assert c["contre_depouille_mm"] >= 0.5
    assert rapport["verdict"] == "conforme"
    vis = _liaisons(rapport, "vis")[0]["calculs"]
    assert vis["mode"] == "insert" and vis["bossage"] and vis["nombre"] == 4


def test_charniere_balayee_et_exportee_comme_le_moteur_articule(boite):
    rapport, _ = boite
    [ch] = rapport["controles"]["cinematique"]["charnieres"]
    assert ch["amplitude_retenue_deg"] >= 90.0
    doc = _glb(rapport["fichiers"]["assemblage"])
    assert doc["extras"]["aurora_articulation"]["schema"] == "aurora.articulation.v1"
    pivots = [n for n in doc["nodes"] if (n.get("extras") or {}).get("aurora_liaison")]
    assert len(pivots) == 1 and pivots[0]["extras"]["aurora_liaison"]["type"] == "charniere"
    noms = {n["name"] for n in doc["nodes"]}
    assert {"caisse_fond", "couvercle"} <= noms
    [anim] = doc["animations"]
    assert anim["name"] == "montage_puis_mouvement"
    assert rapport["relecture_glb"]["maillages"] == rapport["relecture_glb"]["maillages_fermes"]


def test_queue_aronde_tenon_sur_l_enfant_rainure_dans_le_parent(tmp_path):
    ex = {"titre": "Queue d'aronde", "procede": "impression_fdm", "matiere": "pla",
          "pieces": [{"id": "socle", "nom": "Socle", "forme": "bloc", "dimensions_mm": [80, 60, 20], "origine": "fabrique"},
                     {"id": "coulisseau", "nom": "Coulisseau", "forme": "bloc", "dimensions_mm": [80, 30, 15], "origine": "fabrique",
                      "position": {"par_rapport_a": "socle", "cote": "dessus"}}],
          "liaisons": [{"entre": ["socle", "coulisseau"], "type": "queue_aronde", "demontable": True}]}
    rapport = concevoir(ex, tmp_path, rendre_f3d=False)
    [qa] = _liaisons(rapport, "queue_aronde")
    assert qa["calculs"]["largeur_tete_mm"] > qa["calculs"]["largeur_racine_mm"]
    assert rapport["controles"]["interferences"]["ok"] and rapport["controles"]["montage"]["ok"]
    m = {p["id"]: p["masse_g"] for p in rapport["pieces"]}
    assert m["socle"] < 80 * 60 * 20 * 1.24e-3 and m["coulisseau"] > 80 * 30 * 15 * 1.24e-3


def test_soudure_entre_aciers_et_refus_entre_matieres_non_soudables(tmp_path):
    ex = {"titre": "Té soudé", "procede": "tolerie", "matiere": "acier",
          "pieces": [{"id": "semelle", "nom": "Semelle", "forme": "plaque", "dimensions_mm": [120, 80, 8], "origine": "fabrique"},
                     {"id": "ame", "nom": "Âme", "forme": "plaque", "dimensions_mm": [120, 8, 60], "origine": "fabrique",
                      "position": {"par_rapport_a": "semelle", "cote": "dessus"}}],
          "liaisons": [{"entre": ["semelle", "ame"], "type": "soudure", "demontable": False}]}
    rapport = concevoir(ex, tmp_path / "acier", rendre_f3d=False)
    [s] = _liaisons(rapport, "soudure")
    assert s["calculs"]["gorge_mm"] > 0 and s["calculs"]["longueur_cordons_mm"] >= 2 * 120 - 1
    assert rapport["controles"]["interferences"]["ok"]
    ex["pieces"][1]["matiere"] = "pla"
    ex["pieces"][1]["procede"] = "impression_fdm"
    rapport2 = concevoir(ex, tmp_path / "mixte", rendre_f3d=False)
    assert all(l["type"] != "soudure" for l in rapport2["liaisons"])
    assert any("ne se soudent pas" in r for l in rapport2["liaisons"] for r in l["calculs"].get("replis", []))


def test_collision_non_voulue_est_detectee():
    ex = {"titre": "Chevauchement", "procede": "impression_fdm", "matiere": "pla",
          "pieces": [{"id": "a", "nom": "A", "forme": "bloc", "dimensions_mm": [40, 40, 10], "origine": "fabrique"},
                     {"id": "b", "nom": "B", "forme": "bloc", "dimensions_mm": [40, 40, 10], "origine": "fabrique",
                      "position": {"par_rapport_a": "a", "cote": "dessus", "decalage_mm": [0, 0, -3]}}],
          "liaisons": [{"entre": ["a", "b"], "type": "colle", "demontable": False}]}
    dec = []
    g = decomposer_contenants(developper_motifs(normaliser(ex), dec), dec)
    pieces = placer(g, dec)
    construire(pieces, [])
    res = controle_interferences(pieces, registre([]))
    assert not res["ok"] and res["collisions"][0]["volume_mm3"] == pytest.approx(40 * 40 * 3, rel=1e-3)


def test_quincaillerie_hors_norme_refusee():
    assert normes.verifier_quincaillerie({"norme": "ISO 4762", "d": 3.0, "longueur": 13, "classe": "8.8"})
    assert not normes.verifier_quincaillerie({"norme": "ISO 4762", "d": 3.0, "longueur": 12, "classe": "8.8"})
    assert normes.verifier_quincaillerie({"norme": "ISO 10642", "d": 2.0, "longueur": 10, "classe": "8.8"})


def test_gamme_trouvee_par_retour_arriere_et_vue_eclatee_lisible(boite):
    rapport, _ = boite
    assert rapport["controles"]["montage"]["ok"]
    ordre = [e["pieces"][0] for e in rapport["gamme"] if e["type"] in ("base", "piece")]
    assert ordre[0] == "caisse_fond" and ordre[-1] == "couvercle"
    # le dernier panneau posé n'est jamais coincé entre deux tourillons de sens contraires
    murs = [p for p in ordre if p in ("caisse_avant", "caisse_arriere", "caisse_gauche", "caisse_droite")]
    assert len(murs) == 4
    doc = _glb(rapport["fichiers"]["eclate"])
    assert all("translation" in n for n in doc["nodes"][1:] if "mesh" in n)


def test_fermeture_d_une_piece_articulee_toujours_sans_outil():
    ex = json.loads(json.dumps(BOITE))
    ex["liaisons"][1]["type"] = "vis"
    dec = []
    g = fermetures_sans_outil(normaliser(ex), dec)
    assert [l["type"] for l in g["liaisons"]] == ["charniere", "aimant"]
    assert "sans outil" in dec[0]["decision"]


def test_verdict_et_controles_du_boitier_et_du_chassis(boitier, drone):
    for rapport, _ in (boitier, drone):
        assert rapport["verdict"] == "conforme", {k: v["ok"] for k, v in rapport["controles"].items()}
        assert all(s["ferme"] for s in rapport["controles"]["solides_fermes"]["pieces"])


# --------------------------------------------------------------------------- lecture des exigences

def test_lecture_renvoie_les_ecarts_au_modele_puis_accepte():
    reponses = [json.dumps({"assemblage": True, "titre": "x", "fonctions": [], "hypotheses": [],
                            "pieces": [{"id": "a", "nom": "A", "fonction": "", "forme": "plaque", "dimensions_mm": [10, 10, 2],
                                        "origine": "fabrique"}],
                            "liaisons": [{"entre": ["a", "z"], "type": "vis", "demontable": True, "justification": ""}]}),
                json.dumps({"assemblage": True, "titre": "x", "fonctions": [], "hypotheses": [],
                            "pieces": [{"id": "a", "nom": "A", "fonction": "", "forme": "plaque", "dimensions_mm": [40, 40, 4],
                                        "origine": "fabrique"},
                                       {"id": "b", "nom": "B", "fonction": "", "forme": "plaque", "dimensions_mm": [40, 40, 4],
                                        "origine": "fabrique", "position": {"par_rapport_a": "a", "cote": "dessus"}}],
                            "liaisons": [{"entre": ["a", "b"], "type": "vis", "demontable": True, "justification": ""}]})]
    vus = []

    def interroger(messages):
        vus.append(messages)
        return reponses[len(vus) - 1]
    r = lire_exigences("deux plaques vissées", interroger=interroger)
    assert r["ok"] and r["tours"] == 2
    assert "z" in vus[1][-1]["content"] and "pièces" in vus[1][-1]["content"]


def test_lecture_hors_portee_et_modele_injoignable():
    r = lire_exigences("un chat qui dort", interroger=lambda m: json.dumps({"assemblage": False, "titre": "chat",
                                                                           "pieces": [], "liaisons": [], "hypotheses": [],
                                                                           "fonctions": []}))
    assert r["ok"] and r["assemblage"] is False

    def panne(messages):
        raise OSError("connexion refusée")
    r2 = lire_exigences("une étagère", interroger=panne)
    assert not r2["ok"] and "indisponible" in r2["raison"]


# --------------------------------------------------------------------------- règles révélées par les lectures réelles

def test_panneaux_minces_colles_aimants_sur_taquets_et_charniere_d_un_couvercle_debordant(tmp_path):
    """Lecture réelle du 14/11 : chêne 6 mm, couvercle 4 mm plus large que la caisse."""
    ex = {"titre": "Boîte fine", "procede": "decoupe_plaque", "matiere": "chene",
          "pieces": [{"id": "corps", "nom": "Corps", "forme": "bac", "dimensions_mm": [200, 150, 80], "paroi_mm": 6,
                      "ouverture": "dessus", "origine": "fabrique"},
                     {"id": "couvercle", "nom": "Couvercle", "forme": "plaque", "dimensions_mm": [204, 154, 6],
                      "origine": "fabrique", "position": {"par_rapport_a": "corps", "cote": "dessus"}}],
          "liaisons": [{"entre": ["corps", "couvercle"], "type": "charniere", "bord": "arriere", "amplitude_deg": 110},
                       {"entre": ["corps", "couvercle"], "type": "aimant", "bord": "avant", "demontable": True, "effort_N": 8}]}
    rapport = concevoir(ex, tmp_path, rendre_f3d=False)
    assert rapport["verdict"] == "conforme", {k: v["ok"] for k, v in rapport["controles"].items()}
    types = {l["type"] for l in rapport["liaisons"] if all(e.startswith("corps_") for e in l["entre"])}
    assert types == {"colle"}, "une tranche de 6 mm ne reçoit ni vis ni tourillon"
    assert any("taquet" in d["decision"] for d in rapport["decisions"])
    aimants = [q for q in rapport["nomenclature"]["quincaillerie"] if q["norme"] == "aimant N42"]
    assert aimants and aimants[0]["quantite"] <= 4
    pieces = {s["piece"]: s for s in rapport["controles"]["solides_fermes"]["pieces"]}
    assert pieces["corps_arriere"]["morceaux"] == 1 and pieces["couvercle"]["morceaux"] == 1


def test_un_composant_achete_n_est_jamais_usine(tmp_path):
    ex = {"titre": "Batterie", "procede": "impression_fdm", "matiere": "petg",
          "pieces": [{"id": "plaque", "nom": "Plaque", "forme": "plaque", "dimensions_mm": [120, 80, 4], "origine": "fabrique"},
                     {"id": "batterie", "nom": "Batterie", "forme": "bloc", "dimensions_mm": [70, 35, 25], "origine": "achete",
                      "position": {"par_rapport_a": "plaque", "cote": "dessus"}}],
          "liaisons": [{"entre": ["batterie", "plaque"], "type": "vis", "demontable": True}]}
    rapport = concevoir(ex, tmp_path, rendre_f3d=False)
    [erreur] = rapport["controles"]["liaisons_realisees"]["erreurs"]
    assert "acheté" in erreur["raison"]
    batterie = next(p for p in rapport["pieces"] if p["id"] == "batterie")
    assert batterie["masse_g"] == pytest.approx(70 * 35 * 25 * normes.MATIERES["composant"]["densite"] * 1e-3, abs=0.01)


def test_un_bac_sans_epaisseur_de_paroi_recoit_un_panneau_standard_consigne():
    """Lecture réelle du 14/11 : trois tours sans paroi_mm, l'épaisseur n'était que dans les hypothèses."""
    ex = json.loads(json.dumps(BOITE))
    del ex["pieces"][0]["paroi_mm"]
    g = normaliser(ex)
    caisse = next(p for p in g["pieces"] if p["id"] == "caisse")
    assert caisse["paroi"] in normes.EPAISSEURS_PANNEAU_BOIS and caisse["paroi"] == 10.0   # 150 / 15
    assert any("paroi non précisée" in h for h in g["hypotheses"])
    ex2 = json.loads(json.dumps(BOITIER))
    del ex2["pieces"][0]["paroi_mm"]
    boitier = next(p for p in normaliser(ex2)["pieces"] if p["id"] == "boitier")
    assert boitier["paroi"] >= 2 * normes.PROCEDES["impression_fdm"]["paroi_min"]


def test_le_pipeline_3d_confie_une_demande_de_conception_au_moteur_d_assemblage(tmp_path, monkeypatch):
    import sys
    services = Path(__file__).resolve().parents[1] / "application" / "python-services"
    if str(services) not in sys.path:
        sys.path.insert(0, str(services))
    pipeline = pytest.importorskip("aurora_3d_pipeline")
    import application.engineering_assembly_pipeline as moteur
    vus = []

    def faux(demande, dossier=None, **_):
        vus.append((demande, Path(dossier)))
        glb = Path(dossier) / "modele" / "assemblage.glb"
        return {"ok": True, "dossier": str(dossier), "rapport": {
            "verdict": "conforme", "controles": {"interferences": {"ok": True}},
            "chronologie_animation": {"duree_s": 9.0}, "nomenclature": {"quincaillerie": []},
            "fichiers": {"assemblage": str(glb), "eclate": str(glb.with_name("eclate.glb")), "apercus": {}}}}
    monkeypatch.setattr(moteur, "depuis_demande", faux)
    audit = []
    res = pipeline._conception_assemblage("une boîte en bois à charnière", "run1", tmp_path / "run1" / "work", audit, 0.0)
    assert vus == [("une boîte en bois à charnière", tmp_path / "run1")]
    assert res["ok"] and res["pipeline"] == "assemblage_ingenierie" and res["final_mesh"].endswith("assemblage.glb")
    assert res["rigged_mesh"] == res["final_mesh"] and audit[-1]["stage"] == "assemblage"
    monkeypatch.setattr(moteur, "depuis_demande", lambda d, dossier=None, **_: {"ok": False, "hors_portee": True, "raison": "x"})
    assert pipeline._conception_assemblage("un dragon", "run2", tmp_path / "run2" / "work", [], 0.0) is None


def test_route_du_pont_concoit_dans_un_processus_et_rend_les_fichiers(tmp_path):
    import time
    from flask import Blueprint, Flask
    from application.engineering_assembly_api import register_assembly_routes
    app = Flask(__name__)
    bp = Blueprint("assemblage_test", __name__)
    register_assembly_routes(bp, tmp_path)
    app.register_blueprint(bp)
    client = app.test_client()
    entetes = {"Authorization": "Bearer proprietaire"}
    ex = {"titre": "Deux plaques vissées", "procede": "impression_fdm", "matiere": "petg",
          "pieces": [{"id": "a", "nom": "Plaque A", "forme": "plaque", "dimensions_mm": [60, 40, 6], "origine": "fabrique"},
                     {"id": "b", "nom": "Plaque B", "forme": "plaque", "dimensions_mm": [60, 40, 6], "origine": "fabrique",
                      "position": {"par_rapport_a": "a", "cote": "dessus"}}],
          "liaisons": [{"entre": ["a", "b"], "type": "vis", "demontable": True}]}
    assert client.post("/api/3d/assembly", json={}, headers=entetes).status_code == 400
    r = client.post("/api/3d/assembly", json={"exigences": ex, "demande": "deux plaques vissées"}, headers=entetes)
    assert r.status_code == 202
    job = r.get_json()["job_id"]
    assert client.get(f"/api/3d/assembly/{job}", headers={"Authorization": "Bearer autre"}).status_code == 404
    fin = time.monotonic() + 240
    while time.monotonic() < fin:
        etat = client.get(f"/api/3d/assembly/{job}", headers=entetes).get_json()
        if etat["etat"] != "en_cours":
            break
        time.sleep(0.5)
    assert etat["etat"] == "termine" and etat["ok"] and etat["verdict"] == "conforme", etat
    assert etat["fichiers_url"]["assemblage"].startswith("/api/3d/file/assemblages/")
    assert etat["fichiers_url"]["assemblage"].endswith("/modele/assemblage.glb")
    assert any("ISO" in q["designation"] or "insert" in q["designation"] for q in etat["nomenclature"]["quincaillerie"])
    assert (tmp_path / "output" / "3d" / etat["fichiers_url"]["assemblage"].split("/api/3d/file/")[1]).is_file()
