"""Contrôles d'un assemblage, mesurés sur les solides construits — jamais recopiés du concepteur.

  - chaque pièce est un solide fermé d'un seul tenant ;
  - aucune interférence au repos, sauf celles qu'une liaison a voulues (ajustement serré), et
    leur volume mesuré doit correspondre à celui que la liaison annonçait ;
  - la quincaillerie appartient à sa norme (diamètre, longueur de série, plage commercialisée) ;
  - il reste de la matière autour de chaque trou (ligament) ;
  - une gamme de montage existe : chaque pièce rejoint sa place par une translation balayée
    sans traverser les pièces déjà posées, chaque vis reste accessible à l'outil à son étape ;
  - le débattement de chaque charnière est mesuré par collision en faisant tourner la pièce ;
  - masse, centre de gravité et stabilité au repos.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from application import engineering_standards as normes
from application.engineering_assembly import (ErreurConception, Piece, boite_englobante, rotation_axe, translation,
                                              matrice_vers_3x4, union, volume, vers_trimesh)

TOL_VOLUME = 0.02          # mm³ : en dessous, contact numérique
TYPES_VERROU = ("aimant",)


# --------------------------------------------------------------------------- construction

def construire(pieces: dict[str, Piece], resultats) -> None:
    ajouts: dict[str, list] = {}
    retraits: dict[str, list] = {}
    for r in resultats:
        for pid, solides in r.ajouts.items():
            ajouts.setdefault(pid, []).extend(solides)
        for pid, solides in r.retraits.items():
            retraits.setdefault(pid, []).extend(solides)
    for p in pieces.values():
        if p.est_quincaillerie:
            p.final = p.solide
            continue
        s = union([p.solide] + ajouts.get(p.id, []))
        if retraits.get(p.id):
            s = s - union(retraits[p.id])
        p.final = s


def deplacer(solide, M: np.ndarray):
    return solide.transform(matrice_vers_3x4(M))


# --------------------------------------------------------------------------- solides

def controle_solides(pieces: dict[str, Piece]) -> list[dict[str, Any]]:
    import manifold3d
    sortie = []
    for p in pieces.values():
        s = p.final
        statut = s.status()
        morceaux = len(s.decompose()) if not s.is_empty() else 0
        m = vers_trimesh(s) if not s.is_empty() else None
        ferme = bool(m is not None and m.is_volume)
        sortie.append({"piece": p.id, "ferme": ferme and statut == manifold3d.Error.NoError and morceaux == 1,
                       "morceaux": morceaux, "volume_mm3": round(volume(s), 3), "faces": int(s.num_tri()),
                       "genre": int(s.genus()) if not s.is_empty() else None})
    return sortie


# --------------------------------------------------------------------------- interférences

def registre(resultats) -> dict[tuple[str, str], dict[str, Any]]:
    reg: dict[tuple[str, str], dict[str, Any]] = {}
    for r in resultats:
        for e in r.interferences:
            cle = tuple(sorted(e["pieces"]))
            item = reg.setdefault(cle, {"volume_attendu_mm3": 0.0, "nature": e["nature"], "liaisons": set()})
            item["volume_attendu_mm3"] += float(e["volume_attendu_mm3"])
            item["liaisons"].add(e["liaison"])
    return reg


def _chevauchent(ba: np.ndarray, bb: np.ndarray, marge: float = 0.0) -> bool:
    return bool(np.all(ba[0] - marge <= bb[1]) and np.all(bb[0] - marge <= ba[1]))


def controle_interferences(pieces: dict[str, Piece], reg: dict) -> dict[str, Any]:
    ids = list(pieces)
    boites = {i: boite_englobante(pieces[i].final) for i in ids}
    voulues, collisions, ecarts = [], [], []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if not _chevauchent(boites[a], boites[b]):
                continue
            v = volume(pieces[a].final ^ pieces[b].final)
            cle = tuple(sorted((a, b)))
            attendu = reg.get(cle)
            if attendu:
                va = attendu["volume_attendu_mm3"]
                item = {"pieces": list(cle), "volume_mm3": round(v, 4), "attendu_mm3": round(va, 4),
                        "nature": attendu["nature"]}
                if abs(v - va) <= max(0.45 * va, 0.05):
                    voulues.append(item)
                else:
                    ecarts.append(item)
            elif v > TOL_VOLUME:
                collisions.append({"pieces": list(cle), "volume_mm3": round(v, 4)})
    return {"ok": not collisions and not ecarts, "collisions": collisions, "voulues": voulues,
            "ecarts_au_registre": ecarts, "tolerance_mm3": TOL_VOLUME}


# --------------------------------------------------------------------------- quincaillerie

def controle_quincaillerie(pieces: dict[str, Piece]) -> dict[str, Any]:
    articles, ecarts = [], []
    for p in pieces.values():
        if not p.article or p.origine == "procede":
            continue
        e = normes.verifier_quincaillerie(p.article)
        articles.append(p.article["designation"])
        if e:
            ecarts.append({"piece": p.id, "designation": p.article["designation"], "ecarts": e})
    return {"ok": not ecarts, "articles": len(articles), "ecarts": ecarts}


# --------------------------------------------------------------------------- ligaments

def controle_ligaments(pieces: dict[str, Piece], resultats) -> dict[str, Any]:
    from application.engineering_mates import cyl_entre, ligament_min
    defauts, essais = [], 0
    for r in resultats:
        for t in r.trous:
            p = pieces.get(t["piece"])
            if p is None or p.est_quincaillerie or t.get("noeud"):
                continue
            axe = np.asarray(t["axe"], dtype=float)
            c = np.asarray(t["centre"], dtype=float)
            de, a = float(t.get("de", 0.0)), float(t.get("a", 0.0))
            if not t.get("traversant") and not t.get("noeud") and not t.get("debouchant"):
                # fond d'un trou borgne : il doit rester de la matière au-delà (un logement ne perce pas la pièce)
                fond = c + axe * (a + 0.2)
                essais += 1
                if not bool(vers_trimesh(p.final).contains([fond])[0]):
                    defauts.append({"piece": p.id, "liaison": t["liaison"], "defaut": "trou borgne débouchant",
                                    "profondeur_mm": round(a, 2)})
            if t.get("traversant") or a - de < 0.6 or t.get("bossage"):
                continue
            rayon = float(t["rayon"])
            e = 0.5 * ligament_min(p, 2 * rayon)
            p0, p1 = c + axe * (de + 0.3), c + axe * (a - 0.3)
            anneau = cyl_entre(p0, p1, rayon + e) - cyl_entre(p0 - axe, p1 + axe, rayon + 0.02)
            plein = volume(anneau)
            if plein <= 0:
                continue
            essais += 1
            # matière de la pièce avant usinage de ce trou : solide final + son propre trou
            present = volume(anneau ^ (p.final + cyl_entre(p0, p1, rayon + 0.02)))
            if present < 0.9 * plein:
                defauts.append({"piece": p.id, "liaison": t["liaison"], "rayon_mm": round(rayon, 2),
                                "ligament_exige_mm": round(e, 2), "matiere_presente": round(present / plein, 3)})
    return {"ok": not defauts, "trous_controles": essais, "defauts": defauts}


# --------------------------------------------------------------------------- corps rigides et cinématique

def corps_rigides(pieces: dict[str, Piece], resultats) -> dict[str, Any]:
    parent = {p: p for p in pieces}

    def trouver(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def unir(a, b):
        ra, rb = trouver(a), trouver(b)
        if ra != rb:
            parent[rb] = ra

    charnieres = [r for r in resultats if r.cinematique]
    differes = []
    for r in resultats:
        if r.cinematique or r.type in TYPES_VERROU:
            continue
        if r.type == "clip":
            differes.append(r)
            continue
        for x, y in zip(r.entre, r.entre[1:]):
            unir(x, y)
    for r in differes:
        a, b = r.entre
        lie = any({trouver(c.cinematique["fixe"]), trouver(c.cinematique["mobile"])} == {trouver(a), trouver(b)} for c in charnieres)
        if not lie:
            unir(a, b)
    for p in pieces.values():
        if p.est_quincaillerie and p.hote in pieces:
            unir(p.hote, p.id)
    corps: dict[str, list[str]] = {}
    for p in pieces:
        corps.setdefault(trouver(p), []).append(p)
    articulations = []
    for c in charnieres:
        cf, cm = trouver(c.cinematique["fixe"]), trouver(c.cinematique["mobile"])
        if cf == cm:
            raise ErreurConception(f"{c.id} : la pièce articulée est aussi fixée rigidement à son support")
        articulations.append({**c.cinematique, "liaison": c.id, "corps_fixe": cf, "corps_mobile": cm})
    return {"corps": corps, "racine_de": {p: trouver(p) for p in pieces}, "articulations": articulations}


def pieces_flottantes(pieces: dict[str, Piece], resultats, racine: str) -> list[str]:
    voisins: dict[str, set[str]] = {p: set() for p in pieces}
    for r in resultats:
        for x in r.entre:
            for y in r.entre:
                if x != y:
                    voisins[x].add(y)
    for p in pieces.values():
        if p.est_quincaillerie and p.hote in pieces:
            voisins[p.id].add(p.hote)
            voisins[p.hote].add(p.id)
    vus, pile = {racine}, [racine]
    while pile:
        x = pile.pop()
        for y in voisins[x]:
            if y not in vus:
                vus.add(y)
                pile.append(y)
    return sorted(p for p in pieces if p not in vus)


def balayage_charnieres(pieces: dict[str, Piece], cinematique: dict[str, Any], reg: dict, pas_deg: float = 2.0) -> list[dict[str, Any]]:
    sortie = []
    for art in cinematique["articulations"]:
        mobiles = set(cinematique["corps"][art["corps_mobile"]])
        # tout le sous-arbre porté par le corps mobile bouge avec lui
        obstacles = [p for p in pieces.values() if p.id not in mobiles]
        mob = union([pieces[i].final for i in mobiles])
        fixe = union([p.final for p in obstacles])
        axe, pivot = np.asarray(art["axe"]), np.asarray(art["pivot"])
        demande = float(art["amplitude_demandee_deg"])
        limite = min(180.0, demande + 5.0)
        libre, collision = 0.0, None
        theta = pas_deg
        reference = volume(mob ^ fixe)              # interférences voulues déjà présentes au repos
        while theta <= limite + 1e-9:
            M = rotation_axe(axe, math.radians(theta), pivot)
            v = volume(deplacer(mob, M) ^ fixe)
            if v > reference + max(0.05, TOL_VOLUME):
                collision = {"angle_deg": round(theta, 2), "volume_mm3": round(v - reference, 3)}
                break
            libre = theta
            theta += pas_deg
        retenue = min(demande, libre if collision else demande)
        if collision:
            retenue = max(0.0, min(demande, libre - 1.0))
        sortie.append({"liaison": art["liaison"], "amplitude_demandee_deg": demande, "amplitude_libre_deg": round(libre, 2),
                       "amplitude_retenue_deg": round(retenue, 2), "bornee_par_collision": collision is not None and retenue < demande,
                       "premiere_collision": collision})
        art["amplitude_retenue_deg"] = round(retenue, 2)
        art["bornee_par_collision"] = collision is not None and retenue < demande
    return sortie


# --------------------------------------------------------------------------- gamme de montage

def _etendue(solide, u: np.ndarray) -> tuple[float, float]:
    m = solide.to_mesh64()
    v = np.asarray(m.vert_properties, dtype=float)[:, :3] @ u
    return float(v.min()), float(v.max())


def _trajet_libre(groupe, obstacles, autorise: dict[str, float], u: np.ndarray, elastiques_contre: set[str],
                  noms_obstacles: list[str], course: float | None = None) -> tuple[bool, dict[str, Any]]:
    """Le groupe part de +D·u et rejoint sa place ; échantillonnage plus fin que les épaisseurs.

    Une pièce de structure vient de l'extérieur de tout ce qui est déjà posé ; un petit article
    (vis, tourillon, aimant) est amené à la main dans l'espace libre : sa course est sa propre
    longueur selon l'axe, plus 2 mm.
    """
    if not obstacles:
        return True, {"distance_mm": 0.0, "echantillons": 0}
    tout = union(obstacles)
    gmin, gmax = _etendue(groupe["solide"], u)
    omin, omax = _etendue(tout, u)
    D = course if course is not None else max(2.0, omax - gmin + 2.0)
    epaisseur = max(0.6, min(gmax - gmin, 6.0))
    pas = max(0.3, min(2.0, 0.45 * epaisseur))
    n = int(math.ceil(D / pas))
    if n > 600:
        pas = D / 600.0
        n = 600
    for k in range(n, 0, -1):
        dist = k * pas
        M = translation(u * dist)
        v = volume(deplacer(groupe["solide"], M) ^ tout)
        if v <= TOL_VOLUME:
            continue
        # détail par obstacle : serrage voulu ou bec de clip toléré
        for nom, obs in zip(noms_obstacles, obstacles):
            solide = groupe["solide_sans_becs"] if nom in elastiques_contre else groupe["solide"]
            vv = volume(deplacer(solide, M) ^ obs)
            if vv <= TOL_VOLUME:
                continue
            if vv > autorise.get(nom, 0.0) * 1.35 + 0.05:
                return False, {"bloque_par": nom, "a_mm": round(dist, 2), "volume_mm3": round(vv, 3)}
    return True, {"distance_mm": round(D, 2), "pas_mm": round(pas, 3), "echantillons": n}


NORMES_PREMONTEES = ("aimant N42", "insert à chaud", "pièce rapportée")
NORMES_VIS = ("ISO 4762", "ISO 10642", "ISO 7380", "ISO 4017", "DIN 7997")


def gamme_de_montage(pieces: dict[str, Piece], resultats, racine: str, reg: dict, budget: int = 400) -> dict[str, Any]:
    """Ordre de montage réalisable, trouvé par recherche avec retour arrière.

    Après chaque pièce de structure, la quincaillerie dont toutes les pièces sont posées est mise en
    place (dans l'ordre de son groupe : rondelle, vis, rondelle, écrou). Les aimants et inserts se
    prémontent dans leur pièce avant elle ; un tourillon entre dans la première pièce posée de sa
    liaison, du côté de la seconde.
    """
    from application.engineering_assembly import interface_principale
    structure = [p for p in pieces.values() if not p.est_quincaillerie]
    quinc = [p for p in pieces.values() if p.est_quincaillerie]
    par_liaison = {r.id: r for r in resultats}
    voisins: dict[str, list] = {p.id: [] for p in structure}
    for r in resultats:
        for x in r.entre:
            for y in r.entre:
                if x != y and x in voisins and y in voisins:
                    voisins[x].append((y, r))
    contraintes: dict[str, list] = {}
    for r in resultats:
        for c in r.contraintes:
            contraintes.setdefault(c["piece"], []).append(c)
    elastiques: dict[str, list] = {}
    for r in resultats:
        for e in r.elastiques:
            elastiques.setdefault(e["piece"], []).append(e)
    centre_base = boite_englobante(pieces[racine].final).mean(axis=0)
    premonte = {q.id for q in quinc if (q.article or {}).get("norme") in NORMES_PREMONTEES}
    chevilles = {q.id for q in quinc if q.liaison in par_liaison and par_liaison[q.liaison].type == "emmanchement"}
    cache_trajets: dict[tuple, tuple] = {}
    cache_contacts: dict[tuple, Any] = {}
    compteur = {"essais": 0}

    def contact(y: str, pid: str):
        """Interface de contact entre deux pièces telles que construites (bossages et nœuds compris)."""
        cle = (y, pid)
        if cle not in cache_contacts:
            itf = interface_principale(pieces[y], pieces[pid], solide_a=pieces[y].final, solide_b=pieces[pid].final)
            cache_contacts[cle] = itf if itf is not None and itf.ecart <= 1e-3 else None
        return cache_contacts[cle]

    def solide_groupe(ids):
        s = union([pieces[i].final for i in ids])
        becs = [e["solide"] for i in ids for e in elastiques.get(i, [])]
        return {"solide": s, "solide_sans_becs": s - union(becs) if becs else s}

    def autorises(ids):
        a: dict[str, float] = {}
        for (x, y), e in reg.items():
            if x in ids:
                a[y] = a.get(y, 0.0) + e["volume_attendu_mm3"]
            if y in ids:
                a[x] = a.get(x, 0.0) + e["volume_attendu_mm3"]
        return a

    def essayer(poses, ids, directions, court=False):
        obstacles_ids = [i for i in poses if i not in ids]
        cle_base = (tuple(sorted(ids)), tuple(sorted(obstacles_ids)))
        g = None
        dernier = None
        for u in directions:
            cle = cle_base + (tuple(np.round(u, 6)),)
            if cle not in cache_trajets:
                compteur["essais"] += 1
                if g is None:
                    g = solide_groupe(ids)
                contre = {e["contre"] for i in ids for e in elastiques.get(i, [])}
                course = None
                if court:
                    lo, hi = _etendue(g["solide"], u)
                    course = hi - lo + 2.0
                cache_trajets[cle] = _trajet_libre(g, [pieces[i].final for i in obstacles_ids], autorises(ids), u,
                                                   contre, obstacles_ids, course)
            ok, info = cache_trajets[cle]
            if ok:
                return u, info
            dernier = info
        return None, dernier

    def poser_quincaillerie(etat):
        poses, etapes = etat["poses"], etat["etapes"]
        progres = True
        while progres:
            progres = False
            for q in quinc:
                if q.id in poses or q.id in premonte:
                    continue
                r = par_liaison.get(q.liaison)
                if r is None:
                    continue
                art = q.article or {}
                if any((o.article or {}).get("groupe") == art.get("groupe") and (o.article or {}).get("rang", 0) < art.get("rang", 0)
                       and o.id not in poses for o in quinc):
                    continue
                if q.id in chevilles:
                    deja = [x for x in r.entre if x in poses]
                    if len(deja) != 1:
                        continue
                    autre = [x for x in r.entre if x != deja[0]][0]
                    centre_q = np.mean(boite_englobante(q.final), axis=0)
                    sens = np.asarray(pieces[autre].centre) - centre_q
                    u = np.asarray(q.approche) * (1 if float(np.dot(q.approche, sens)) >= 0 else -1)
                    dirs = [u]
                elif not all(x in poses for x in r.entre):
                    continue
                elif r.type == "soudure":
                    poses.append(q.id)
                    etat["approches"][q.id] = [0.0, 0.0, 0.0]
                    etat["support"][q.id] = q.hote
                    etapes.append({"pieces": [q.id], "type": "soudure", "texte": f"Souder : {art.get('designation')}.",
                                   "approche": None, "liaison": r.id})
                    progres = True
                    continue
                else:
                    u = np.asarray(q.approche, dtype=float)
                    dirs = [u, -u] if r.type == "charniere" else [u]
                u_ok, info = essayer(poses, [q.id], dirs, court=True)
                if u_ok is None:
                    etat["blocages"].append({"piece": q.id, "raison": "trajet d'insertion bloqué", **(info or {})})
                    u_ok = dirs[0]
                acces = None
                if art.get("norme") in NORMES_VIS:
                    acces = acces_outil(q, [pieces[i].final for i in poses], u_ok)
                    if not acces["ok"]:
                        etat["blocages"].append({"piece": q.id, "raison": "outil sans accès", **acces})
                poses.append(q.id)
                etat["approches"][q.id] = u_ok.tolist()
                etat["support"][q.id] = q.hote if q.hote in poses else r.entre[0]
                etapes.append({"pieces": [q.id], "type": "fixation", "texte": f"Mettre en place : {art.get('designation') or q.nom}.",
                               "approche": u_ok.tolist(), "trajet": info, "acces_outil": acces, "liaison": r.id})
                progres = True

    def directions(pid, poses):
        exact, glisse, demi = [], [], []
        for c in contraintes.get(pid, []):
            if c["par_rapport_a"] not in poses:
                continue
            if c.get("approche") is not None:
                exact.append(np.asarray(c["approche"], dtype=float))
            if c.get("glissement") is not None:
                s_ = np.asarray(c["glissement"], dtype=float)
                glisse.append([s_, -s_])
        for y, r in voisins[pid]:
            if y in poses:
                itf = contact(y, pid)
                if itf is not None:
                    demi.append(itf.normale)
        if exact:
            u = exact[0]
            if any(float(e @ u) < 0.999 for e in exact[1:]):
                return []                        # deux emmanchements dans des sens contraires : impasse
            dirs = [u]
        elif glisse:
            dirs = glisse[0]
        else:
            # normales de contact, axes propres de la pièce (un bras à 45° glisse le long de sa longueur), axes du monde
            from application.engineering_assembly import rotation_z
            Rp = rotation_z(pieces[pid].orientation_deg)[:3, :3]
            dirs = list(demi) + [Rp[:, i] * sg for i in (0, 1) for sg in (1, -1)] + \
                [np.eye(3)[i] * sg for i in (2, 0, 1) for sg in (1, -1)]
        uniques = []
        for d in dirs:
            if not any(float(d @ e) > 0.999 for e in uniques):
                uniques.append(d)
        # d'abord la direction qui éloigne la pièce de la pièce de base : geste naturel (on apporte la pièce de
        # l'extérieur de ce qui est monté) et vue éclatée lisible ; un bras rayonnant glisse le long de lui-même
        dehors = np.asarray(pieces[pid].centre, dtype=float) - centre_base
        if np.linalg.norm(dehors) > 1e-6:
            dehors = dehors / np.linalg.norm(dehors)
            uniques.sort(key=lambda d: -float(d @ dehors))
        return [d for d in uniques if all(float(d @ h) >= -1e-6 for h in demi)]

    def copie(etat):
        return {"poses": list(etat["poses"]), "etapes": list(etat["etapes"]), "approches": dict(etat["approches"]),
                "support": dict(etat["support"]), "blocages": list(etat["blocages"]), "restant": set(etat["restant"])}

    meilleur = {"etat": None}

    def recherche(etat):
        if meilleur["etat"] is None or len(etat["poses"]) > len(meilleur["etat"]["poses"]):
            meilleur["etat"] = etat
        if not etat["restant"]:
            return etat
        if compteur["essais"] > budget:
            return None
        candidats = []
        for pid in etat["restant"]:
            liens = [(y, r) for (y, r) in voisins[pid] if y in etat["poses"]]
            # une pièce se monte en s'appuyant sur une pièce déjà posée : jamais « en l'air »
            if liens and any(contact(y, pid) is not None for y in {y for y, _ in liens}):
                candidats.append((len(liens), volume(pieces[pid].final), pid, liens))
        # de bas en haut (on pose sur ce qui est déjà en place), puis la plus liée, puis la plus grosse
        candidats.sort(key=lambda c: (round(float(boite_englobante(pieces[c[2]].final)[0][2]), 0), -c[0], -c[1], c[2]))
        echecs = []
        for _, _, pid, liens in candidats:
            dirs = directions(pid, etat["poses"])
            if not dirs:
                echecs.append({"piece": pid, "raison": "emmanchements dans des sens contraires"})
                continue
            ids = [pid] + [q.id for q in quinc if q.id in premonte and q.hote == pid]
            u, info = essayer(etat["poses"], ids, dirs)
            if u is None:
                echecs.append({"piece": pid, "raison": "aucune translation libre", "directions_essayees": len(dirs), **(info or {})})
                continue
            suite = copie(etat)
            for qid in ids[1:]:
                suite["etapes"].append({"pieces": [qid], "type": "premontage", "approche": np.asarray(pieces[qid].approche).tolist(),
                                        "texte": f"Prémonter dans {pieces[pid].nom} : {pieces[qid].article['designation']}.",
                                        "liaison": pieces[qid].liaison})
            suite["poses"].extend(ids)
            for i in ids:
                suite["approches"][i] = u.tolist()
            appuis = [y for y, _ in liens if contact(y, pid) is not None]
            principal = max(appuis, key=lambda y: volume(pieces[y].final))
            suite["support"][pid] = principal
            for qid in ids[1:]:
                suite["support"][qid] = pid
            types = sorted({r.type for _, r in liens})
            suite["etapes"].append({"pieces": [pid], "type": "piece", "approche": u.tolist(), "trajet": info,
                                    "texte": f"Monter {pieces[pid].nom} sur {pieces[principal].nom} ({', '.join(types)})."})
            suite["restant"].discard(pid)
            poser_quincaillerie(suite)
            fin = recherche(suite)
            if fin is not None:
                return fin
        etat["echecs"] = echecs
        return None

    depart = {"poses": [racine], "approches": {racine: [0.0, 0.0, 0.0]}, "support": {}, "blocages": [],
              "restant": {p.id for p in structure} - {racine},
              "etapes": [{"pieces": [racine], "type": "base", "texte": f"Poser {pieces[racine].nom} (pièce de base).", "approche": None}]}
    for q in quinc:
        if q.id in premonte and q.hote == racine:
            depart["poses"].append(q.id)
            depart["approches"][q.id] = np.asarray(q.approche).tolist()
            depart["support"][q.id] = racine
            depart["etapes"].append({"pieces": [q.id], "type": "premontage", "approche": depart["approches"][q.id],
                                     "texte": f"Prémonter dans {pieces[racine].nom} : {q.article['designation']}.", "liaison": q.liaison})
    poser_quincaillerie(depart)
    fin = recherche(depart)
    etat = fin if fin is not None else meilleur["etat"]
    blocages = list(etat["blocages"])
    if fin is None:
        blocages.append({"pieces": sorted(etat["restant"]), "raison": "montage bloqué : aucune pièce restante ne peut rejoindre sa place",
                         "essais": etat.get("echecs", []), "recherche": compteur["essais"]})
    for q in quinc:
        if q.id not in etat["poses"]:
            blocages.append({"piece": q.id, "raison": "fixation jamais posée (ses pièces ne sont pas toutes montées)"})
    for i, e in enumerate(etat["etapes"]):
        e["numero"] = i + 1
    # un article prémonté sort de son logement selon son propre axe dans la vue éclatée
    propres = {q.id: np.asarray(q.approche, dtype=float).tolist() for q in quinc if q.id in premonte}
    return {"ok": not blocages, "ordre": etat["poses"], "etapes": etat["etapes"], "blocages": blocages,
            "support": etat["support"], "approches": etat["approches"], "approches_propres": propres,
            "trajets_calcules": compteur["essais"]}


def acces_outil(q: Piece, obstacles, u: np.ndarray) -> dict[str, Any]:
    """Rayons depuis la tête vers l'extérieur : la clé ou le tournevis doit passer sur 40 mm."""
    b = boite_englobante(q.final)
    centre = b.mean(axis=0)
    gmin, gmax = _etendue(q.final, u)
    depart = centre + u * (gmax - float(centre @ u) + 0.05)
    longueur = 40.0
    if not obstacles:
        return {"ok": True, "longueur_mm": longueur}
    tout = union(obstacles)
    hits = tout.ray_cast(tuple(map(float, depart)), tuple(map(float, depart + u * longueur)))
    if hits:
        return {"ok": False, "obstacle_a_mm": round(float(hits[0].distance) * longueur, 2), "longueur_mm": longueur}
    return {"ok": True, "longueur_mm": longueur}


# --------------------------------------------------------------------------- vue éclatée

def vecteurs_eclates(pieces: dict[str, Piece], gamme: dict[str, Any]) -> dict[str, np.ndarray]:
    """Vue éclatée : chaque pièce s'écarte selon sa direction de montage, au-delà de la pièce qui la
    porte, et assez loin pour que sa boîte ne recouvre aucune pièce déjà écartée (lisibilité)."""
    tout = np.array([boite_englobante(p.final) for p in pieces.values()])
    diag = float(np.linalg.norm(tout[:, 1].max(axis=0) - tout[:, 0].min(axis=0)))
    marge = 0.02 * diag
    ecarts: dict[str, np.ndarray] = {}
    boites: dict[str, np.ndarray] = {}

    def recouvre(b: np.ndarray, autre: np.ndarray) -> bool:
        return bool(np.all(b[0] < autre[1] + marge) and np.all(autre[0] < b[1] + marge))

    # le support d'abord : un article prémonté apparaît avant son hôte dans la gamme mais s'écarte AVEC lui
    ordre, places = [], set()
    restants = list(gamme["ordre"])
    while restants:
        avance = False
        for pid in list(restants):
            sup = gamme["support"].get(pid)
            if sup is None or sup in places or sup not in restants:
                ordre.append(pid)
                places.add(pid)
                restants.remove(pid)
                avance = True
        if not avance:
            ordre.extend(restants)
            break
    for pid in ordre:
        p = pieces[pid]
        propre = (gamme.get("approches_propres") or {}).get(pid)
        u = np.asarray(propre if propre is not None else (gamme["approches"].get(pid) or [0, 0, 0]), dtype=float)
        support = gamme["support"].get(pid)
        base = ecarts.get(support, np.zeros(3))
        b0 = boite_englobante(p.final)
        if not np.any(u):
            ecarts[pid] = base.copy()
            boites[pid] = b0 + base
            continue
        lo, hi = _etendue(p.final, u)
        dist = (hi - lo) * (0.9 if p.est_quincaillerie else 0.5) + (0.06 if p.est_quincaillerie else 0.18) * diag
        voisins = [q for q in boites if q != support and q != p.hote and
                   (not p.est_quincaillerie or pieces[q].est_quincaillerie or q not in (p.hote, support))]
        for _ in range(80):
            e = base + u * dist
            b = b0 + e
            if not any(recouvre(b, boites[q]) for q in voisins if not (p.est_quincaillerie and q == p.hote)):
                break
            dist += 0.05 * diag
        ecarts[pid] = e
        boites[pid] = b
    for pid in pieces:
        ecarts.setdefault(pid, np.zeros(3))
    return ecarts


# --------------------------------------------------------------------------- masse et stabilité

def masse_et_stabilite(pieces: dict[str, Piece]) -> dict[str, Any]:
    from shapely.geometry import MultiPoint, Point
    masses, centres = [], []
    for p in pieces.values():
        m = volume(p.final) * normes.MATIERES[p.matiere]["densite"] * 1e-3
        mesh = vers_trimesh(p.final)
        masses.append(m)
        centres.append(np.asarray(mesh.center_mass if mesh.is_volume else mesh.bounds.mean(axis=0)))
    total = float(sum(masses))
    cg = np.sum([c * m for c, m in zip(centres, masses)], axis=0) / max(total, 1e-9)
    zmin = min(boite_englobante(p.final)[0][2] for p in pieces.values())
    appuis = []
    for p in pieces.values():
        mesh = vers_trimesh(p.final)
        bas = mesh.vertices[mesh.vertices[:, 2] <= zmin + 0.3]
        appuis.extend(bas[:, :2].tolist())
    polygone = MultiPoint(appuis).convex_hull if len(appuis) >= 3 else None
    marge = None
    if polygone is not None and polygone.area > 0:
        q = Point(float(cg[0]), float(cg[1]))
        marge = polygone.exterior.distance(q) * (1 if polygone.contains(q) else -1)
    return {"masse_totale_g": round(total, 1), "centre_gravite_mm": [round(float(x), 2) for x in cg],
            "stable_au_repos": marge is not None and marge > 0, "marge_stabilite_mm": None if marge is None else round(marge, 2),
            "masses_g": {p.id: round(m, 2) for p, m in zip(pieces.values(), masses)}}
