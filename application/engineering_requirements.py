"""Lecture d'une demande en français en exigences d'assemblage, par le modèle de langage local.

Le modèle fait le travail sémantique d'un ingénieur : quelles pièces (et pourquoi), en quelle
matière, par quel procédé, posées comment les unes par rapport aux autres, et comment chaque
paire est assemblée. Il ne donne aucune coordonnée : les positions sont des contacts
(« dessus de », « centré sur »), le moteur natif calcule la géométrie, choisit vis, jeux et
longueurs par règles, et mesure tout.

Contrat JSON validé (`engineering_assembly.normaliser`) ; une réponse hors contrat est renvoyée
au modèle avec la liste exacte des écarts, deux fois au plus. Un modèle injoignable ou qui ne
tient pas dans la mémoire libre est dit tel quel : jamais de lecture inventée.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from typing import Any, Callable

from application import engineering_standards as normes
from application.engineering_assembly import TYPES_LIAISON, ErreurConception, normaliser

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
SCHEMA = "aurora.exigences-assemblage.v1"
PREFERENCES = ("orcarouter/Qwen3.8-27B-Uncensored:latest", "qwen3-coder:30b", "qwen3-vl:30b",
               "qwen3-vl:8b-instruct", "qwen3-vl:8b")

MATIERES = sorted(normes.MATIERES)
PROCEDES = sorted(normes.PROCEDES)

SCHEMA_JSON: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assemblage": {"type": "boolean"},
        "titre": {"type": "string"},
        "fonctions": {"type": "array", "items": {"type": "string"}},
        "procede": {"type": "string", "enum": PROCEDES},
        "matiere": {"type": "string", "enum": MATIERES},
        "pieces": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"}, "nom": {"type": "string"}, "fonction": {"type": "string"},
                "forme": {"type": "string", "enum": ["plaque", "bloc", "barre", "cylindre", "tube", "bac", "equerre"]},
                "dimensions_mm": {"type": "array", "items": {"type": "number"}},
                "paroi_mm": {"type": "number"},
                "ouverture": {"type": "string", "enum": ["dessus", "dessous", "avant", "arriere", "gauche", "droite"]},
                "assemblage_angles": {"type": "string", "enum": ["queue_aronde", "emmanchement", "vis", "colle", "soudure"]},
                "matiere": {"type": "string", "enum": MATIERES},
                "procede": {"type": "string", "enum": PROCEDES},
                "origine": {"type": "string", "enum": ["fabrique", "achete"]},
                "reference": {"type": "string"},
                "axe": {"type": "string", "enum": ["x", "y", "z"]},
                "position": {"type": "object", "properties": {
                    "par_rapport_a": {"type": "string"},
                    "cote": {"type": "string", "enum": ["dessus", "dessous", "avant", "arriere", "gauche", "droite", "dedans"]},
                    "centre_sur": {"type": "string"},
                    "alignement": {"type": "object", "properties": {
                        "x": {"type": "string", "enum": ["min", "centre", "max"]},
                        "y": {"type": "string", "enum": ["min", "centre", "max"]},
                        "z": {"type": "string", "enum": ["min", "centre", "max"]}}},
                    "decalage_mm": {"type": "array", "items": {"type": "number"}},
                    "hauteur_mm": {"type": "number"},
                    "radial": {"type": "object", "properties": {"rayon_extremite_mm": {"type": "number"},
                                                                "recouvrement_mm": {"type": "number"}}},
                    "orientation_deg": {"type": "number"}},
                    "required": ["par_rapport_a", "cote"]},
                "motif": {"type": "object", "properties": {
                    "type": {"type": "string", "enum": ["polaire", "lineaire"]}, "nombre": {"type": "integer"},
                    "angle_depart_deg": {"type": "number"}, "pas_mm": {"type": "number"},
                    "direction": {"type": "string", "enum": ["x", "y"]}}},
                "trous_existants": {"type": "object", "properties": {
                    "vis": {"type": "string"}, "entraxe_mm": {"type": "array", "items": {"type": "number"}},
                    "diametre_cercle_mm": {"type": "number"}, "nombre": {"type": "integer"},
                    "profondeur_mm": {"type": "number"}, "degagement_central_mm": {"type": "number"}}},
            },
            "required": ["id", "nom", "fonction", "forme", "dimensions_mm", "origine"]}},
        "liaisons": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "entre": {"type": "array", "items": {"type": "string"}},
                "type": {"type": "string", "enum": list(TYPES_LIAISON)},
                "bord": {"type": "string", "enum": ["avant", "arriere", "gauche", "droite", "dessus", "dessous"]},
                "demontable": {"type": "boolean"}, "effort_N": {"type": "number"},
                "amplitude_deg": {"type": "number"}, "justification": {"type": "string"}},
            "required": ["entre", "type", "demontable", "justification"]}},
        "hypotheses": {"type": "array", "items": {"type": "string"}},
        "contraintes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["assemblage", "titre", "fonctions", "pieces", "liaisons", "hypotheses"],
}

CONSIGNE = (
    "Tu es ingénieur de conception mécanique. On te donne une demande d'objet. Pense comme un ingénieur : "
    "quelles pièces sont nécessaires et pour quelle fonction, en quelle matière et par quel procédé, où se trouve "
    "chacune par rapport aux autres, et surtout COMMENT chaque paire de pièces est assemblée, et pourquoi.\n"
    "Repère : X de gauche à droite vu de face, Y de l'avant vers l'arrière, Z de bas en haut.\n"
    "Dimensions_mm selon la forme : plaque, bloc, barre : [X, Y, Z] ; bac (pièce creuse ouverte : boîte, caisse, "
    "boîtier, tiroir) : [X, Y, Z] extérieurs avec paroi_mm et ouverture ; cylindre : [diamètre, hauteur] ; tube : "
    "[diamètre extérieur, diamètre intérieur, hauteur] ; equerre : [longueur, aile horizontale, aile verticale, épaisseur]. "
    "Une barre qui rayonne (bras) a sa longueur selon X.\n"
    "Règles :\n"
    "- La quincaillerie n'est JAMAIS une pièce : vis, boulons, écrous, rondelles, charnières, broches, goupilles, "
    "tourillons, aimants, clips, colle, cordons de soudure sont des LIAISONS entre deux pièces. Le moteur les "
    "dimensionne selon les normes et les fabrique lui-même (une charnière produit ses nœuds sur les deux pièces et sa "
    "broche). Ne décris donc que les pièces de l'objet et les composants achetés qu'il intègre.\n"
    "- Une pièce creuse est UNE pièce de forme bac, même en bois : le moteur la découpe lui-même en panneaux si le "
    "procédé l'exige et choisit l'assemblage des angles (tu peux l'imposer avec assemblage_angles si la demande le dit).\n"
    "- Un composant acheté (moteur, carte électronique, batterie, roulement, capteur) a origine achete, une forme "
    "enveloppe simple et ses dimensions usuelles ; si son motif de fixation est connu, renseigne trous_existants "
    "(vis « M3 », entraxe_mm ou diametre_cercle_mm et nombre, profondeur_mm du filet, degagement_central_mm si un axe dépasse).\n"
    "- La première pièce est la base : sans position. Chaque autre pièce a une position par rapport à une pièce déjà "
    "décrite : cote (dessus, dessous, avant, arriere, gauche, droite, dedans pour l'intérieur d'un bac avec "
    "hauteur_mm au-dessus du fond) ; centre_sur pour se centrer sur une autre pièce que celle du contact ; alignement "
    "pour affleurer un bord (min ou max selon x, y, z) ; decalage_mm ; radial (rayon_extremite_mm ou "
    "recouvrement_mm) pour une barre qui rayonne autour du centre.\n"
    "- Des pièces identiques répétées : décris-en UNE avec motif (polaire avec nombre et angle_depart_deg, ou "
    "lineaire avec nombre, pas_mm, direction). Une pièce posée sur une pièce à motif est répétée avec elle.\n"
    "- liaisons : une par paire de pièces assemblées. Types : vis ; boulon_ecrou (peut traverser plusieurs pièces "
    "empilées, liste-les de haut en bas) ; emmanchement (goupilles ou tourillons) ; clip (encliquetage élastique) ; "
    "charniere (pièce qui pivote) ; colle ; soudure ; queue_aronde ; aimant (fermeture magnétique). Choisis selon la "
    "fonction et justifie : démontable ou non, pièce mobile ou non, matières, effort, aspect. Une fermeture (loquet) est "
    "une liaison démontable entre la pièce mobile et son support qui s'ouvre SANS OUTIL : clip ou aimant, jamais vis ni "
    "boulon. bord : côté de l'objet où se trouve la liaison "
    "(une charnière de couvercle est en général à l'arrière, un loquet à l'avant). effort_N seulement si la demande "
    "permet de l'estimer.\n"
    "- Toute pièce doit être reliée aux autres par au moins une liaison.\n"
    "- Ce que la demande ne précise pas (dimensions, matière, procédé) est une hypothèse raisonnable : écris-la dans "
    "hypotheses.\n"
    "- assemblage vaut false si la demande ne décrit pas un objet à concevoir en pièces assemblées (personnage, "
    "animal, sculpture, paysage) ; dans ce cas pieces et liaisons peuvent être vides.\n"
    "Réponds uniquement par le JSON."
)


# --------------------------------------------------------------------------- choix du modèle selon la mémoire réelle

def _memoire_libre_go() -> float:
    libre = 0.0
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for ligne in f:
                if ligne.startswith("MemAvailable:"):
                    libre = int(ligne.split()[1]) / 1024 / 1024
    except OSError:
        pass
    try:
        sortie = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=10)
        libre += sum(float(x) for x in sortie.stdout.split()) / 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return libre


def _modeles() -> tuple[dict[str, float], set[str]]:
    tailles, charges = {}, set()
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=8) as r:
            for m in json.loads(r.read().decode()).get("models", []):
                tailles[m["name"]] = m.get("size", 0) / 1e9
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=8) as r:
            charges = {m["name"] for m in json.loads(r.read().decode()).get("models", [])}
    except Exception:  # noqa: BLE001 — Ollama injoignable : liste vide, l'appelant le dira
        pass
    return tailles, charges


def choisir_modele(prefere: str | None = None) -> dict[str, Any]:
    """Premier modèle de la liste qui tient dans RAM + VRAM libres (le swap ne compte pas)."""
    tailles, charges = _modeles()
    if not tailles:
        return {"ok": False, "raison": "Ollama injoignable ou aucun modèle installé"}
    ordre = [prefere] if prefere else []
    ordre += [m for m in PREFERENCES if m not in ordre]
    libre = _memoire_libre_go()
    for nom in ordre:
        if nom in charges:
            return {"ok": True, "modele": nom, "raison": "déjà chargé", "memoire_libre_go": round(libre, 1)}
    for nom in ordre:
        if nom in tailles and tailles[nom] + 2.5 <= libre:
            return {"ok": True, "modele": nom, "raison": f"{tailles[nom]:.1f} Go ≤ {libre:.1f} Go libres",
                    "memoire_libre_go": round(libre, 1)}
    return {"ok": False, "raison": f"aucun modèle de la liste ne tient dans {libre:.1f} Go libres (RAM + VRAM)",
            "memoire_libre_go": round(libre, 1)}


def _interroger(modele: str, messages: list[dict[str, str]], timeout_s: float = 1200.0) -> str:
    # Mesuré le 14/11/2026 (Ollama 0.31.1) : avec « think: false », le modèle 27B ignore entièrement le
    # schéma imposé et répond en prose ; sans ce paramètre il réfléchit puis respecte le schéma. On
    # laisse donc la réflexion (budget de jetons en conséquence).
    # AURORA_ASSEMBLAGE_REFLEXION=0 : lecture rapide (sans réflexion, JSON demandé par la consigne puis validé et
    # réparé), au prix d'un raisonnement d'ingénieur moins riche.
    if os.environ.get("AURORA_ASSEMBLAGE_REFLEXION", "1") == "0":
        corps = {"model": modele, "stream": False, "format": "json", "think": False,
                 "options": {"temperature": 0.1, "num_predict": 6000, "num_ctx": 16384}, "messages": messages}
    else:
        corps = {"model": modele, "stream": False, "format": SCHEMA_JSON,
                 "options": {"temperature": 0.1, "num_predict": 14000, "num_ctx": 20480}, "messages": messages}
    for essai in range(2):
        requete = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(corps).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(requete, timeout=timeout_s) as reponse:
                return str(json.loads(reponse.read().decode("utf-8")).get("message", {}).get("content", ""))
        except urllib.error.HTTPError as exc:
            texte = exc.read().decode("utf-8", "replace")[:300]
            if essai == 0 and "think" in texte.lower():
                corps.pop("think", None)        # modèle sans mode de réflexion
                continue
            raise RuntimeError(f"Ollama HTTP {exc.code} : {texte}") from exc
    raise RuntimeError("Ollama : réponse impossible")


def _extraire(texte: str) -> dict[str, Any] | None:
    texte = re.sub(r"<think>.*?</think>", "", texte, flags=re.S)
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        return None
    try:
        v = json.loads(texte[debut:fin + 1])
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def lire_exigences(demande: str, *, interroger: Callable[[list[dict[str, str]]], str] | None = None,
                   modele: str | None = None, verifier: Callable[[dict[str, Any]], str | None] | None = None,
                   reparations: int = 2, journal: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Exigences validées, ou {"ok": False, "raison": …}. `verifier` peut refuser une lecture valide
    au contrat mais inconstructible (pièces qui ne se touchent pas…) : son message est renvoyé au modèle."""
    demande = " ".join(str(demande or "").split())
    journal = journal if journal is not None else []
    if not demande:
        return {"ok": False, "raison": "demande vide"}
    choix = {"ok": True, "modele": modele or "fourni"}
    if interroger is None:
        choix = choisir_modele(modele)
        if not choix["ok"]:
            return {"ok": False, "raison": choix["raison"], "schema": SCHEMA}
        nom = choix["modele"]

        def interroger(messages):  # noqa: E306
            return _interroger(nom, messages)
    messages = [{"role": "system", "content": CONSIGNE}, {"role": "user", "content": demande}]
    derniere = None
    for tour in range(reparations + 1):
        try:
            texte = interroger(messages)
        except Exception as exc:  # noqa: BLE001 — panne du modèle : dite, pas maquillée
            return {"ok": False, "raison": f"modèle indisponible : {exc}", "schema": SCHEMA, "modele": choix.get("modele")}
        brut = _extraire(texte)
        journal.append({"tour": tour + 1, "reponse": brut if brut is not None else texte[:2000]})
        if brut is None:
            ecart = "la réponse n'est pas un objet JSON"
        elif brut.get("assemblage") is False:
            return {"ok": True, "assemblage": False, "schema": SCHEMA, "exigences": brut, "modele": choix.get("modele"),
                    "tours": tour + 1}
        else:
            try:
                normaliser(brut)
                ecart = verifier(brut) if verifier else None
            except ErreurConception as exc:
                ecart = str(exc)
            if not ecart:
                return {"ok": True, "assemblage": True, "schema": SCHEMA, "exigences": brut,
                        "modele": choix.get("modele"), "tours": tour + 1}
        derniere = ecart
        journal[-1]["ecart"] = ecart
        messages = messages + [{"role": "assistant", "content": texte[:12000]},
                               {"role": "user", "content": "Ta réponse a ces défauts, corrige-les et renvoie le JSON complet : "
                                                           + ecart}]
    return {"ok": False, "raison": f"lecture hors contrat après {reparations + 1} essais : {derniere}", "schema": SCHEMA,
            "modele": choix.get("modele")}
