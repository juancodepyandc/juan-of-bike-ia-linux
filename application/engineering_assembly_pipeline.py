"""Conception d'un assemblage de bout en bout, de la demande en français aux fichiers vérifiés.

    python -m application.engineering_assembly_pipeline --demande "une boîte en bois avec un couvercle à charnière"

Étapes : lecture des exigences (modèle local) → graphe d'assemblage (motifs, décomposition par
procédé) → placement par contacts → liaisons dimensionnées par règles avec leurs usinages sur les
deux pièces → solides finaux → contrôles mesurés → exports (STL, glTF articulé et animé, vue
éclatée, coupe, dossier) → rendus f3d. Le verdict ne passe que si tous les contrôles passent ;
sinon le dossier dit précisément ce qui manque. Sorties sous `application/output/3d/assemblages/`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np

RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from application import engineering_standards as normes  # noqa: E402
from application.engineering_assembly import (ErreurConception, Piece, boite_englobante, decomposer_contenants,  # noqa: E402
                                              developper_motifs, interface_principale, normaliser, placer, volume,
                                              _slug)
from application.engineering_assembly_checks import (balayage_charnieres, construire, controle_interferences,  # noqa: E402
                                                      controle_ligaments, controle_quincaillerie, controle_solides,
                                                      corps_rigides, gamme_de_montage, masse_et_stabilite,
                                                      pieces_flottantes, registre, vecteurs_eclates)
from application.engineering_mates import generer  # noqa: E402

SORTIES = RACINE / "application" / "output" / "3d" / "assemblages"
SCHEMA_RAPPORT = "aurora.assemblage.v1"


def _aabb(s) -> np.ndarray:
    return boite_englobante(s)


def _chevauche(a, b, marge=0.0) -> bool:
    return bool(np.all(a[0] - marge <= b[1]) and np.all(b[0] - marge <= a[1]))


OUTILLEES = ("vis", "boulon_ecrou", "colle", "soudure", "emmanchement", "queue_aronde")


def fermetures_sans_outil(graphe: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Une liaison entre deux pièces déjà reliées par une articulation est une FERMETURE : elle doit
    s'ouvrir sans outil, sinon elle bloque l'articulation. Vis, colle ou soudure y deviennent un aimant
    (un clip si la matière le permet, choisi ensuite par les replis)."""
    articulees = {frozenset(l["entre"]) for l in graphe["liaisons"] if l["type"] == "charniere"}
    for l in graphe["liaisons"]:
        if l["type"] in OUTILLEES and frozenset(l["entre"]) in articulees:
            ancien = l["type"]
            l["type"] = "aimant"
            l["demontable"] = True
            decisions.append({"sujet": l["id"], "decision": f"{ancien} remplacé par une fermeture sans outil (aimant)",
                              "raison": "ces deux pièces sont déjà reliées par une charnière : une liaison outillée les rendrait "
                                        "solidaires et bloquerait l'ouverture"})
        elif l["type"] in ("aimant", "clip") and frozenset(l["entre"]) in articulees:
            l["demontable"] = True
    return graphe


def generer_liaisons(graphe: dict[str, Any], pieces: dict[str, Piece], decisions: list[dict[str, Any]]):
    """Chaque liaison, en évitant les zones déjà occupées par les fixations et perçages précédents."""
    resultats, erreurs = [], []
    occupes: list[tuple[Any, np.ndarray]] = []
    for liaison in graphe["liaisons"]:
        exclusions: list[Any] = []
        accepte = None
        for essai in range(4):
            try:
                rs = generer({**liaison, "_exclusions": exclusions}, pieces)
            except ErreurConception as exc:
                if essai == 0:
                    erreurs.append({"liaison": liaison["id"], "type": liaison["type"], "entre": liaison["entre"],
                                    "raison": str(exc)})
                else:
                    accepte = accepte_precedent
                break
            conflits = []
            for r in rs:
                nouveaux = [q.solide for q in r.quincaillerie] + [c for cs in r.retraits.values() for c in cs]
                for s in nouveaux:
                    bs = _aabb(s)
                    for (o, bo) in occupes:
                        if _chevauche(bs, bo) and volume(s ^ o) > 0.01:
                            conflits.append(o)
            accepte_precedent = rs
            if not conflits:
                accepte = rs
                break
            exclusions = exclusions + conflits
            if essai == 3:
                accepte = rs
                decisions.append({"sujet": liaison["id"], "decision": "fixations conservées malgré un chevauchement",
                                  "raison": "aucune autre place dans l'interface ; voir le contrôle d'interférence"})
        if not accepte:
            continue
        if exclusions:
            decisions.append({"sujet": liaison["id"], "decision": "fixations déplacées",
                              "raison": f"{len(exclusions)} zone(s) déjà occupée(s) par d'autres liaisons évitée(s)"})
        for r in accepte:
            resultats.append(r)
            decisions.extend(r.decisions)
            for q in r.quincaillerie:
                pieces[q.id] = q
                occupes.append((q.solide, _aabb(q.solide)))
            for cs in r.retraits.values():
                for c in cs:
                    occupes.append((c, _aabb(c)))
    return resultats, erreurs


def nomenclature(pieces: dict[str, Piece], masses: dict[str, float]) -> dict[str, Any]:
    fabriquees, achetees, quinc, rapportees = [], [], {}, {}
    for p in pieces.values():
        if p.origine == "procede" and (p.article or {}).get("norme") == "pièce rapportée":
            cle = p.nom.rstrip("0123456789 ").strip() + f" ({normes.MATIERES[p.matiere]['nom']}), collé sur " + \
                (pieces[p.hote].nom if p.hote in pieces else "?")
            dims = [round(float(x), 1) for x in (boite_englobante(p.final)[1] - boite_englobante(p.final)[0])]
            item = rapportees.setdefault(cle, {"designation": cle, "quantite": 0, "dimensions_hors_tout_mm": dims, "pieces": []})
            item["quantite"] += 1
            item["pieces"].append(p.id)
            continue
        if p.est_quincaillerie:
            cle = p.article["designation"] if p.article else p.nom
            item = quinc.setdefault(cle, {"designation": cle, "quantite": 0, "norme": (p.article or {}).get("norme"),
                                          "matiere": normes.MATIERES[p.matiere]["nom"], "pieces": []})
            item["quantite"] += 1
            item["pieces"].append(p.id)
            continue
        dims = [round(float(x), 1) for x in (boite_englobante(p.final)[1] - boite_englobante(p.final)[0])]
        ligne = {"id": p.id, "nom": p.nom, "matiere": normes.MATIERES[p.matiere]["nom"],
                 "procede": normes.PROCEDES[p.procede]["nom"], "dimensions_hors_tout_mm": dims,
                 "masse_g": masses.get(p.id), "reference": p.reference or None}
        (achetees if p.origine == "achete" else fabriquees).append(ligne)
    return {"fabriquees": fabriquees, "achetees": achetees, "rapportees": sorted(rapportees.values(), key=lambda x: x["designation"]),
            "quincaillerie": sorted(quinc.values(), key=lambda x: x["designation"])}


def _racine_reelle(graphe: dict[str, Any], pieces: dict[str, Piece]) -> str:
    r = graphe["racine"]
    if r in pieces:
        return r
    membres = [p for p in pieces.values() if p.base_id == r and not p.est_quincaillerie]
    fond = [p for p in membres if p.id.endswith("_fond")]
    return (fond or sorted(membres, key=lambda p: -volume(p.solide)))[0].id


def concevoir(exigences: dict[str, Any], dossier: Path, *, demande: str = "", rendre_f3d: bool = True) -> dict[str, Any]:
    """Conçoit, contrôle et exporte. Rend le rapport (aussi écrit dans `rapport.json`)."""
    from application import engineering_assembly_export as export
    t0 = time.time()
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    decisions: list[dict[str, Any]] = []
    graphe = fermetures_sans_outil(normaliser(exigences), decisions)
    graphe = developper_motifs(graphe, decisions)
    graphe = decomposer_contenants(graphe, decisions)
    pieces = placer(graphe, decisions)
    resultats, erreurs = generer_liaisons(graphe, pieces, decisions)
    racine = _racine_reelle(graphe, pieces)
    construire(pieces, resultats)
    solides = controle_solides(pieces)
    reg = registre(resultats)
    interferences = controle_interferences(pieces, reg)
    quinc = controle_quincaillerie(pieces)
    ligaments = controle_ligaments(pieces, resultats)
    flottantes = pieces_flottantes(pieces, resultats, racine)
    try:
        cinematique = corps_rigides(pieces, resultats)
        cine_erreur = None
    except ErreurConception as exc:
        cinematique = {"corps": {p: [p] for p in pieces}, "racine_de": {p: p for p in pieces}, "articulations": []}
        cine_erreur = str(exc)
    charnieres = balayage_charnieres(pieces, cinematique, reg)
    gamme = gamme_de_montage(pieces, resultats, racine, reg)
    ecarts = vecteurs_eclates(pieces, gamme)
    masse = masse_et_stabilite(pieces)
    nomen = nomenclature(pieces, masse["masses_g"])
    controles = {
        "solides_fermes": {"ok": all(s["ferme"] for s in solides), "pieces": solides},
        "interferences": interferences,
        "quincaillerie_normalisee": quinc,
        "ligaments": ligaments,
        "liaisons_realisees": {"ok": not erreurs, "erreurs": erreurs, "realisees": len(resultats)},
        "pieces_fixees": {"ok": not flottantes, "non_fixees": flottantes},
        "cinematique": {"ok": cine_erreur is None and all(c["amplitude_retenue_deg"] >= 15.0 for c in charnieres),
                        "erreur": cine_erreur, "charnieres": charnieres},
        "montage": {"ok": gamme["ok"], "blocages": gamme["blocages"], "etapes": len(gamme["etapes"])},
        "stabilite": {"ok": True, **{k: v for k, v in masse.items() if k != "masses_g"}},
    }
    verdict = all(c["ok"] for c in controles.values())
    # exports
    chemins_stl = export.exporter_stl(pieces, dossier)
    extras = {"aurora_assemblage": {"schema": SCHEMA_RAPPORT, "titre": graphe["titre"], "demande": demande,
                                    "verdict": "conforme" if verdict else "non_conforme", "unites": "glTF en mètres ; cotes en mm",
                                    "etapes": [{"numero": e["numero"], "texte": e["texte"], "pieces": e["pieces"]}
                                               for e in gamme["etapes"]],
                                    "liaisons": [{"id": r.id, "type": r.type, "entre": r.entre} for r in resultats]}}
    modele = dossier / "modele"
    chrono = export.ecrire_gltf(modele / "assemblage.glb", pieces, cinematique, gamme, ecarts, extras)
    export.ecrire_gltf(modele / "eclate.glb", pieces, cinematique, gamme, ecarts, extras, eclate=True, animer=False)
    coupe = None
    plan = export.plan_de_coupe(pieces)
    if plan is not None:
        coupe = dossier / "travail" / "coupe.glb"
        en_coupe = export.solides_en_coupe(pieces, plan[0], plan[1])
        gardees = {k: v for k, v in en_coupe.items() if not v.is_empty()}
        sous = {k: pieces[k] for k in gardees}
        cine_coupe = {"corps": {k: [k] for k in sous}, "racine_de": {k: k for k in sous}, "articulations": []}
        gamme_coupe = {"ordre": list(sous), "etapes": [], "support": {}, "approches": {}}
        export.ecrire_gltf(coupe, sous, cine_coupe, gamme_coupe, {}, {"aurora_coupe": {"origine_mm": plan[0].tolist(),
                                                                                       "normale": plan[1].tolist()}},
                           animer=False, solides=gardees)
    relecture = export.relire(modele / "assemblage.glb")
    apercus = export.rendre(dossier / "apercus", modele / "assemblage.glb", modele / "eclate.glb", coupe, chrono,
                            normale_coupe=None if plan is None else plan[1]) if rendre_f3d else {}
    rapport = {
        "schema": SCHEMA_RAPPORT, "demande": demande, "titre": graphe["titre"], "verdict": "conforme" if verdict else "non_conforme",
        "duree_s": round(time.time() - t0, 2), "fonctions": graphe["fonctions"], "hypotheses": graphe["hypotheses"],
        "decisions": decisions,
        "pieces": [{"id": p.id, "nom": p.nom, "matiere": p.matiere, "procede": p.procede, "origine": p.origine,
                    "forme": p.forme, "dimensions": p.dims, "masse_g": masse["masses_g"].get(p.id),
                    "stl": chemins_stl.get(p.id), "designation": (p.article or {}).get("designation")}
                   for p in pieces.values()],
        "liaisons": [{"id": r.id, "type": r.type, "type_demande": r.calculs.get("type_demande"), "entre": r.entre,
                      "interface": r.interface, "calculs": r.calculs, "etapes": r.etapes,
                      "cinematique": r.cinematique} for r in resultats],
        "nomenclature": nomen, "gamme": gamme["etapes"], "controles": controles, "relecture_glb": relecture,
        "chronologie_animation": chrono,
        "fichiers": {"assemblage": str(modele / "assemblage.glb"), "eclate": str(modele / "eclate.glb"),
                     "coupe": str(coupe) if coupe else None, "apercus": apercus, "dossier": str(dossier)},
        "limites": ["Efforts et capacités : estimations de conception (méthodes et coefficients indiqués), aucune résistance certifiée.",
                    "Filets modélisés au diamètre du noyau (filetage cosmétique) ; jeux à calibrer par un essai réel du procédé.",
                    "Gamme de montage : translations rectilignes balayées ; aucun trajet avec rotation, aucune déformation sauf les becs de clip déclarés.",
                    "Composants achetés : enveloppes et motifs de fixation supposés, à vérifier sur la fiche du fabricant."],
    }
    (dossier / "rapport.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=2, default=_json), encoding="utf-8")
    ecrire_dossier(dossier, rapport)
    return rapport


def _json(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, set):
        return sorted(o)
    return str(o)


def ecrire_dossier(dossier: Path, rapport: dict[str, Any]) -> None:
    L = [f"# {rapport['titre']}", "", f"Demande : « {rapport['demande']} »" if rapport["demande"] else "",
         f"Verdict des contrôles : **{rapport['verdict'].replace('_', ' ')}**", ""]
    if rapport["fonctions"]:
        L += ["## Fonctions", *[f"- {f}" for f in rapport["fonctions"]], ""]
    L += ["## Pièces fabriquées", "| Pièce | Matière | Procédé | Hors-tout (mm) | Masse (g) |", "|---|---|---|---|---:|"]
    for p in rapport["nomenclature"]["fabriquees"]:
        L.append(f"| {p['nom']} | {p['matiere']} | {p['procede']} | {' × '.join(f'{x:g}' for x in p['dimensions_hors_tout_mm'])} | {p['masse_g']} |")
    if rapport["nomenclature"]["achetees"]:
        L += ["", "## Composants achetés"] + [f"- {p['nom']} ({p['reference'] or 'référence à choisir'}) : "
                                              f"{' × '.join(f'{x:g}' for x in p['dimensions_hors_tout_mm'])} mm"
                                              for p in rapport["nomenclature"]["achetees"]]
    if rapport["nomenclature"].get("rapportees"):
        L += ["", "## Pièces rapportées (taillées à part et collées)", "| Qté | Pièce | Hors-tout (mm) |", "|---:|---|---|"]
        L += [f"| {q['quantite']} | {q['designation']} | {' × '.join(f'{x:g}' for x in q['dimensions_hors_tout_mm'])} |"
              for q in rapport["nomenclature"]["rapportees"]]
    L += ["", "## Quincaillerie (normalisée)", "| Qté | Désignation |", "|---:|---|"]
    L += [f"| {q['quantite']} | {q['designation']} |" for q in rapport["nomenclature"]["quincaillerie"]]
    L += ["", "## Liaisons et dimensionnement"]
    for l in rapport["liaisons"]:
        c = l["calculs"]
        resume = ", ".join(f"{k} = {v}" for k, v in c.items() if k not in ("replis", "crochets", "type_demande")
                           and not isinstance(v, (dict, list)))
        titre = l["type"] + (f" (demandé : {l['type_demande']})" if l.get("type_demande") and l["type_demande"] != l["type"] else "")
        L.append(f"- **{l['id']}** — {titre} entre {', '.join(l['entre'])} : {resume}")
    L += ["", "## Décisions d'ingénierie"] + [f"- {d['sujet']} : {d['decision']} — {d['raison']}" for d in rapport["decisions"]]
    L += ["", "## Gamme de montage"] + [f"{e['numero']}. {e['texte']}" for e in rapport["gamme"]]
    L += ["", "## Contrôles mesurés"]
    for nom, c in rapport["controles"].items():
        L.append(f"- {nom.replace('_', ' ')} : {'conforme' if c['ok'] else 'NON CONFORME'}")
    if rapport["hypotheses"]:
        L += ["", "## Hypothèses"] + [f"- {h}" for h in rapport["hypotheses"]]
    L += ["", "## Limites"] + [f"- {x}" for x in rapport["limites"]]
    (dossier / "DOSSIER.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def verifier_constructible(exigences: dict[str, Any]) -> str | None:
    """Refus d'une lecture valide au contrat mais impossible à assembler : message pour le modèle."""
    try:
        decisions: list[dict[str, Any]] = []
        g = decomposer_contenants(developper_motifs(normaliser(exigences), decisions), decisions)
        pieces = placer(g, decisions)
    except ErreurConception as exc:
        return str(exc)
    lies = {e for l in g["liaisons"] for e in l["entre"]}
    bases = {p.base_id for p in pieces.values() if p.base_id}
    sans = [p.id for p in pieces.values() if p.id not in lies and (p.base_id not in lies) and p.id != g["racine"]
            and p.base_id != g["racine"]]
    ecarts = []
    if sans:
        ecarts.append(f"ces pièces n'ont aucune liaison : {', '.join(sorted(sans))}")
    for l in g["liaisons"]:
        membres = [[e] if e in pieces else [p.id for p in pieces.values() if p.base_id == e] for e in l["entre"]]
        if len(membres) >= 2 and all(membres[:2]):
            touche = any(interface_principale(pieces[x], pieces[y]) is not None for x in membres[0] for y in membres[1])
            if not touche:
                ecarts.append(f"la liaison {l['type']} entre {l['entre'][0]} et {l['entre'][1]} relie deux pièces qui ne se "
                              "touchent pas : corrige leurs positions (cote, centre_sur, décalage)")
    del bases
    if not ecarts:
        # essai à blanc des liaisons : une liaison impossible est expliquée au modèle pour qu'il la change
        g2 = fermetures_sans_outil(g, [])
        _, erreurs = generer_liaisons(g2, dict(pieces), [])
        for e in erreurs[:4]:
            ecarts.append(f"liaison {e['type']} entre {', '.join(e['entre'])} impossible : {e['raison'][:300]}")
    return " ; ".join(ecarts) or None


def dossier_de_sortie(titre: str) -> Path:
    stamp = time.strftime("%m%d%H%M")
    return SORTIES / f"{_slug(titre)[:40]}_{stamp}_{uuid.uuid4().hex[:6]}"


def depuis_demande(demande: str, *, dossier: Path | None = None, modele: str | None = None,
                   rendre_f3d: bool = True) -> dict[str, Any]:
    from application.engineering_requirements import lire_exigences
    journal: list[dict[str, Any]] = []
    lecture = lire_exigences(demande, modele=modele, verifier=verifier_constructible, journal=journal)
    if not lecture.get("ok"):
        # l'échec est un résultat : son journal (réponses du modèle et écarts) reste consultable
        dossier = Path(dossier) if dossier else dossier_de_sortie("lecture_refusee_" + demande[:30])
        (dossier / "journal").mkdir(parents=True, exist_ok=True)
        (dossier / "journal" / "lecture_exigences.json").write_text(
            json.dumps({"modele": lecture.get("modele"), "raison": lecture.get("raison"), "journal": journal},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": False, "raison": lecture.get("raison"), "dossier": str(dossier), "journal_lecture": journal}
    if not lecture.get("assemblage"):
        return {"ok": False, "hors_portee": True, "raison": "la demande ne décrit pas un objet à concevoir en pièces assemblées",
                "lecture": lecture}
    exigences = lecture["exigences"]
    dossier = Path(dossier) if dossier else dossier_de_sortie(exigences.get("titre") or demande)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "prompt").mkdir(exist_ok=True)
    if not (dossier / "prompt" / "prompt.txt").is_file():      # l'interface a pu l'écrire avec sa session
        (dossier / "prompt" / "prompt.txt").write_text(f"run_id={dossier.name}\n{demande}\n", encoding="utf-8")
    (dossier / "journal").mkdir(exist_ok=True)
    (dossier / "journal" / "lecture_exigences.json").write_text(
        json.dumps({"modele": lecture.get("modele"), "tours": lecture.get("tours"), "journal": journal},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (dossier / "exigences.json").write_text(json.dumps(exigences, ensure_ascii=False, indent=2), encoding="utf-8")
    rapport = concevoir(exigences, dossier, demande=demande, rendre_f3d=rendre_f3d)
    rapport["modele_lecture"] = lecture.get("modele")
    return {"ok": rapport["verdict"] == "conforme", "rapport": rapport, "dossier": str(dossier)}


def main() -> int:
    a = argparse.ArgumentParser(description="Concevoir un assemblage (pièces, liaisons, fixations) depuis une demande")
    a.add_argument("--demande", help="demande en français")
    a.add_argument("--exigences", help="exigences JSON déjà lues (sinon lecture par le modèle local)")
    a.add_argument("--sortie", help="dossier de sortie (défaut : application/output/3d/assemblages/…)")
    a.add_argument("--modele", help="modèle Ollama préféré")
    a.add_argument("--sans-rendu", action="store_true")
    args = a.parse_args()
    if args.exigences:
        exigences = json.loads(Path(args.exigences).read_text(encoding="utf-8"))
        dossier = Path(args.sortie) if args.sortie else dossier_de_sortie(exigences.get("titre") or "assemblage")
        rapport = concevoir(exigences, dossier, demande=args.demande or "", rendre_f3d=not args.sans_rendu)
        res = {"ok": rapport["verdict"] == "conforme", "dossier": str(dossier), "rapport": rapport}
    elif args.demande:
        res = depuis_demande(args.demande, dossier=Path(args.sortie) if args.sortie else None, modele=args.modele,
                             rendre_f3d=not args.sans_rendu)
    else:
        a.error("--demande ou --exigences requis")
        return 2
    rapport = res.get("rapport") or {}
    print(json.dumps({"ok": res.get("ok"), "raison": res.get("raison"), "dossier": res.get("dossier"),
                      "verdict": rapport.get("verdict"),
                      "controles": {k: v.get("ok") for k, v in (rapport.get("controles") or {}).items()},
                      "fichiers": rapport.get("fichiers")}, ensure_ascii=False, indent=2, default=_json))
    return 0 if res.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
