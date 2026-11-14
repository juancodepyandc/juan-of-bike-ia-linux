#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrôle du bureau pour l'IA d'Aurora : voir l'écran, localiser, cliquer, taper, faire défiler.

Avant : le Cowork demandait `scrot`, `gnome-screenshot` ou `import` pour une capture (aucun
n'est installé ici, la capture échouait toujours) et rien ne pilotait la souris ni le clavier.

Ici, sans dépendance à installer :
- capture d'écran par PIL (`ImageGrab`, X11) ;
- souris et clavier par l'extension XTest de X11, appelée avec `ctypes` (ce que fait `xdotool`),
  y compris les caractères absents du clavier (correspondance temporaire d'un code de touche libre) ;
- localisation d'un élément décrit en langage naturel par le modèle de vision local
  (Qwen3-VL rend des coordonnées normalisées 0..1000, converties en pixels) ;
- garde-fous : activation explicite (`AURORA_DESKTOP_CONTROL=1`), combinaisons système
  refusées, journal d'audit de chaque action avec l'empreinte de l'écran avant et après.

Toutes les actions décrivent ce qu'elles ont réellement fait ; une action qui n'a pas pu se
faire le dit, elle ne rend jamais un succès supposé.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.util
import hashlib
import io
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

SCHEMA = "aurora.bureau.v1"
OLLAMA_URL = "http://127.0.0.1:11434"
MODELE_VISION = "qwen3-vl:8b-instruct"
APP_DIR = Path(__file__).resolve().parents[1]
DOSSIER_SORTIE = APP_DIR / "output" / "cowork" / "bureau"
ENV_ACTIVATION = "AURORA_DESKTOP_CONTROL"

ACTIONS = ("deplacer", "cliquer", "double_cliquer", "clic_droit", "glisser", "taper", "touche", "defiler")
BOUTONS = {"gauche": 1, "milieu": 2, "droit": 3}
DEFILEMENT = {"haut": 4, "bas": 5, "gauche": 6, "droite": 7}
# Combinaisons qui agissent sur la session ou le système plutôt que sur une application.
COMBINAISONS_REFUSEES = {
    frozenset({"ctrl", "alt", "delete"}), frozenset({"ctrl", "alt", "backspace"}),
    frozenset({"super", "l"}), frozenset({"ctrl", "alt", "l"}),
}
ALIAS_TOUCHES = {
    "ctrl": "Control_L", "control": "Control_L", "alt": "Alt_L", "shift": "Shift_L", "maj": "Shift_L",
    "super": "Super_L", "win": "Super_L", "meta": "Super_L", "altgr": "ISO_Level3_Shift",
    "entree": "Return", "enter": "Return", "return": "Return", "echap": "Escape", "esc": "Escape",
    "tab": "Tab", "espace": "space", "space": "space", "retour": "BackSpace", "backspace": "BackSpace",
    "suppr": "Delete", "delete": "Delete", "haut": "Up", "bas": "Down", "gauche": "Left", "droite": "Right",
    "debut": "Home", "fin": "End", "pageup": "Prior", "pagedown": "Next",
}


class BureauIndisponible(RuntimeError):
    pass


# --------------------------------------------------------------------------- X11 / XTest

class X11:
    """Appels X11/XTest minimaux. Une instance = une connexion au serveur X."""

    def __init__(self, display: str | None = None):
        nom_x11, nom_xtst = ctypes.util.find_library("X11"), ctypes.util.find_library("Xtst")
        if not nom_x11 or not nom_xtst:
            raise BureauIndisponible("bibliothèques X11/XTest introuvables (session X11 requise)")
        self.x = ctypes.cdll.LoadLibrary(nom_x11)
        self.t = ctypes.cdll.LoadLibrary(nom_xtst)
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.x.XStringToKeysym.restype = ctypes.c_ulong
        self.x.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x.XKeysymToKeycode.restype = ctypes.c_ubyte
        self.x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x.XGetKeyboardMapping.restype = ctypes.POINTER(ctypes.c_ulong)
        self.x.XGetKeyboardMapping.argtypes = [ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.x.XChangeKeyboardMapping.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                                  ctypes.POINTER(ctypes.c_ulong), ctypes.c_int]
        self.x.XDisplayKeycodes.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        self.x.XFree.argtypes = [ctypes.c_void_p]
        self.x.XFlush.argtypes = [ctypes.c_void_p]
        self.x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.x.XQueryPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong] + [ctypes.POINTER(ctypes.c_ulong)] * 2 + \
            [ctypes.POINTER(ctypes.c_int)] * 4 + [ctypes.POINTER(ctypes.c_uint)]
        self.t.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        self.t.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.t.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.t.XTestQueryExtension.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_int)] * 4
        nom = (display or os.environ.get("DISPLAY") or "").encode() or None
        self.d = self.x.XOpenDisplay(nom)
        if not self.d:
            raise BureauIndisponible("impossible d'ouvrir l'affichage X11 (DISPLAY)")
        a, b, c, e = (ctypes.c_int() for _ in range(4))
        if not self.t.XTestQueryExtension(self.d, ctypes.byref(a), ctypes.byref(b), ctypes.byref(c), ctypes.byref(e)):
            self.fermer()
            raise BureauIndisponible("extension XTest absente du serveur X")
        self.racine = self.x.XDefaultRootWindow(self.d)

    def fermer(self) -> None:
        if getattr(self, "d", None):
            self.x.XCloseDisplay(self.d)
            self.d = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.fermer()

    def position(self) -> tuple[int, int]:
        r, e = ctypes.c_ulong(), ctypes.c_ulong()
        rx, ry, wx, wy = (ctypes.c_int() for _ in range(4))
        m = ctypes.c_uint()
        self.x.XQueryPointer(self.d, self.racine, ctypes.byref(r), ctypes.byref(e), ctypes.byref(rx), ctypes.byref(ry),
                             ctypes.byref(wx), ctypes.byref(wy), ctypes.byref(m))
        return rx.value, ry.value

    def deplacer(self, x: int, y: int) -> None:
        self.t.XTestFakeMotionEvent(self.d, -1, int(x), int(y), 0)
        self.x.XFlush(self.d)

    def bouton(self, numero: int, appuye: bool) -> None:
        self.t.XTestFakeButtonEvent(self.d, numero, 1 if appuye else 0, 0)
        self.x.XFlush(self.d)

    def keysym(self, nom: str) -> int:
        return int(self.x.XStringToKeysym(nom.encode()))

    def keycode(self, keysym: int) -> int:
        return int(self.x.XKeysymToKeycode(self.d, keysym))

    def touche(self, keycode: int, appuye: bool) -> None:
        self.t.XTestFakeKeyEvent(self.d, keycode, 1 if appuye else 0, 0)
        self.x.XFlush(self.d)

    def niveau(self, keycode: int, keysym: int) -> int | None:
        """Niveau (0 normal, 1 Maj, 2 AltGr, 3 AltGr+Maj) auquel le code de touche produit ce keysym."""
        n = ctypes.c_int()
        tableau = self.x.XGetKeyboardMapping(self.d, keycode, 1, ctypes.byref(n))
        try:
            for i in range(min(4, n.value)):
                if tableau[i] == keysym:
                    return i
        finally:
            self.x.XFree(tableau)
        return None

    def code_libre(self) -> int | None:
        bas, haut = ctypes.c_int(), ctypes.c_int()
        self.x.XDisplayKeycodes(self.d, ctypes.byref(bas), ctypes.byref(haut))
        for code in range(haut.value, bas.value - 1, -1):
            n = ctypes.c_int()
            tableau = self.x.XGetKeyboardMapping(self.d, code, 1, ctypes.byref(n))
            try:
                if all(tableau[i] == 0 for i in range(n.value)):
                    return code
            finally:
                self.x.XFree(tableau)
        return None

    def associer(self, code: int, keysym: int) -> None:
        valeurs = (ctypes.c_ulong * 2)(keysym, keysym)
        self.x.XChangeKeyboardMapping(self.d, code, 2, valeurs, 1)
        self.x.XSync(self.d, 0)


# --------------------------------------------------------------------------- clavier

def keysym_du_caractere(caractere: str) -> str:
    """Nom X11 d'un caractère : nom direct pour l'ASCII, keysym Unicode (U+XXXX) sinon."""
    noms = {" ": "space", "\n": "Return", "\t": "Tab"}
    if caractere in noms:
        return noms[caractere]
    if caractere.isascii() and caractere.isalnum():
        return caractere
    return f"U{ord(caractere):04X}"


def analyser_combinaison(texte: str) -> list[str]:
    """« ctrl+maj+s » → noms de keysyms X11 dans l'ordre d'appui. Refuse les combinaisons système."""
    morceaux = [m.strip() for m in re.split(r"\s*\+\s*", texte.strip()) if m.strip()]
    if not morceaux:
        raise ValueError("combinaison vide")
    normalises = {m.lower() for m in morceaux}
    if any(interdite <= normalises for interdite in COMBINAISONS_REFUSEES):
        raise PermissionError(f"combinaison système refusée : {texte}")
    return [ALIAS_TOUCHES.get(m.lower(), m if len(m) > 1 else keysym_du_caractere(m)) for m in morceaux]


# --------------------------------------------------------------------------- écran

def capturer(chemin: str | Path | None = None) -> dict[str, Any]:
    """Capture de l'écran entier ; rend le chemin, la taille et l'empreinte de l'image."""
    try:
        from PIL import ImageGrab
        image = ImageGrab.grab()
    except Exception as exc:  # noqa: BLE001
        raise BureauIndisponible(f"capture d'écran impossible : {type(exc).__name__}: {exc}") from exc
    tampon = io.BytesIO()
    image.save(tampon, format="PNG")
    octets = tampon.getvalue()
    if chemin is None:
        DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
        chemin = DOSSIER_SORTIE / f"ecran_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 1000:03d}.png"
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(octets)
    return {"chemin": str(chemin), "largeur": image.width, "hauteur": image.height,
            "sha256": hashlib.sha256(octets).hexdigest()}


def _demander_vision(image_png: bytes, consigne: str, modele: str, timeout_s: float = 120.0) -> str:
    corps = json.dumps({
        "model": modele, "stream": False, "format": "json", "think": False,
        "options": {"temperature": 0.0, "num_predict": 200},
        "messages": [{"role": "user", "content": consigne, "images": [base64.b64encode(image_png).decode()]}],
    }).encode()
    requete = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=corps, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=timeout_s) as reponse:
        return str(json.loads(reponse.read().decode()).get("message", {}).get("content", ""))


def convertir_point(brut: dict[str, Any], largeur: int, hauteur: int) -> tuple[int, int] | None:
    """Coordonnées normalisées 0..1000 (convention Qwen-VL) → pixels de l'écran."""
    try:
        x, y = float(brut["x"]), float(brut["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0.0 <= x <= 1000.0 and 0.0 <= y <= 1000.0):
        return None
    return int(round(x / 1000.0 * (largeur - 1))), int(round(y / 1000.0 * (hauteur - 1)))


def localiser(description: str, *, capture: dict[str, Any] | None = None, modele: str = MODELE_VISION,
              demander: Callable[[bytes, str, str], str] = _demander_vision) -> dict[str, Any]:
    """Point de l'écran correspondant à `description`, lu par le modèle de vision sur une capture."""
    capture = capture or capturer()
    octets = Path(capture["chemin"]).read_bytes()
    consigne = (
        "Tu regardes une capture d'écran. Trouve l'élément décrit et rends UNIQUEMENT un JSON "
        '{"trouve": true, "x": 0, "y": 0, "confiance": 0.0, "element": "..."} où x et y sont les '
        "coordonnées du CENTRE de l'élément, normalisées entre 0 et 1000 (0,0 en haut à gauche). "
        'Si l\'élément n\'est pas visible : {"trouve": false}.\n'
        f"Élément : {description}"
    )
    try:
        texte = demander(octets, consigne, modele)
        debut, fin = texte.find("{"), texte.rfind("}")
        brut = json.loads(texte[debut:fin + 1]) if debut >= 0 and fin > debut else {}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "raison": f"modèle de vision injoignable : {type(exc).__name__}", "capture": capture}
    if not isinstance(brut, dict) or brut.get("trouve") is not True:
        return {"ok": False, "raison": "élément non trouvé sur l'écran", "capture": capture}
    point = convertir_point(brut, capture["largeur"], capture["hauteur"])
    if point is None:
        return {"ok": False, "raison": "coordonnées hors contrat", "capture": capture, "brut": brut}
    confiance = brut.get("confiance")
    return {"ok": True, "x": point[0], "y": point[1], "element": str(brut.get("element") or description)[:120],
            "confiance": float(confiance) if isinstance(confiance, (int, float)) else None, "capture": capture}


# --------------------------------------------------------------------------- actions

def valider_action(action: Any) -> dict[str, Any]:
    """Action normalisée ; ValueError/PermissionError si elle sort du contrat."""
    if not isinstance(action, dict) or action.get("type") not in ACTIONS:
        raise ValueError(f"type d'action attendu parmi {', '.join(ACTIONS)}")
    t = action["type"]
    propre: dict[str, Any] = {"type": t}

    def point(cle_x: str = "x", cle_y: str = "y") -> tuple[int, int]:
        x, y = action.get(cle_x), action.get(cle_y)
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError(f"{cle_x}/{cle_y} numériques requis")
        if x < 0 or y < 0:
            raise ValueError("coordonnées négatives")
        return int(x), int(y)

    if t in ("deplacer", "cliquer", "double_cliquer", "clic_droit"):
        propre["x"], propre["y"] = point()
        if t == "cliquer":
            bouton = action.get("bouton", "gauche")
            if bouton not in BOUTONS:
                raise ValueError("bouton : gauche, milieu ou droit")
            propre["bouton"] = bouton
    elif t == "glisser":
        propre["x"], propre["y"] = point()
        propre["x2"], propre["y2"] = point("x2", "y2")
    elif t == "taper":
        texte = action.get("texte")
        if not isinstance(texte, str) or not texte or len(texte) > 2000:
            raise ValueError("texte de 1 à 2000 caractères requis")
        propre["texte"] = texte
    elif t == "touche":
        combinaison = action.get("touches")
        if not isinstance(combinaison, str):
            raise ValueError("touches requises, par exemple « ctrl+s »")
        propre["touches"] = combinaison
        propre["keysyms"] = analyser_combinaison(combinaison)
    elif t == "defiler":
        sens = action.get("sens", "bas")
        if sens not in DEFILEMENT:
            raise ValueError("sens : haut, bas, gauche ou droite")
        quantite = action.get("quantite", 3)
        if isinstance(quantite, bool) or not isinstance(quantite, int) or not 1 <= quantite <= 30:
            raise ValueError("quantite entière de 1 à 30")
        propre["sens"], propre["quantite"] = sens, quantite
        if "x" in action or "y" in action:
            propre["x"], propre["y"] = point()
    return propre


class Bureau:
    """Exécute des actions validées sur une connexion X11 (injectable pour les tests)."""

    def __init__(self, x11: Any):
        self.x11 = x11

    def _cliquer(self, numero: int, fois: int = 1) -> None:
        for _ in range(fois):
            self.x11.bouton(numero, True)
            time.sleep(0.02)
            self.x11.bouton(numero, False)
            time.sleep(0.06)

    def _appuyer_keysym(self, nom: str, appuye: bool) -> None:
        keysym = self.x11.keysym(nom)
        if not keysym:
            raise ValueError(f"touche inconnue : {nom}")
        code = self.x11.keycode(keysym)
        if not code:
            raise ValueError(f"touche sans code sur ce clavier : {nom}")
        self.x11.touche(code, appuye)

    def _taper_caractere(self, caractere: str) -> None:
        nom = keysym_du_caractere(caractere)
        keysym = self.x11.keysym(nom)
        code = self.x11.keycode(keysym) if keysym else 0
        temporaire = False
        niveau = self.x11.niveau(code, keysym) if code else None
        if not code or niveau is None or niveau > 1:
            # caractère absent ou seulement en AltGr : un code de touche libre reçoit ce caractère
            code = self.x11.code_libre()
            if not code or not keysym:
                raise ValueError(f"caractère impossible à taper : {caractere!r}")
            self.x11.associer(code, keysym)
            niveau, temporaire = 0, True
        maj = self.x11.keycode(self.x11.keysym("Shift_L")) if niveau == 1 else 0
        try:
            if maj:
                self.x11.touche(maj, True)
            self.x11.touche(code, True)
            self.x11.touche(code, False)
            if maj:
                self.x11.touche(maj, False)
        finally:
            if temporaire:
                time.sleep(0.02)
                self.x11.associer(code, 0)
        time.sleep(0.008)

    def executer(self, action: dict[str, Any]) -> dict[str, Any]:
        t = action["type"]
        if t in ("deplacer", "cliquer", "double_cliquer", "clic_droit", "glisser") or ("x" in action and t == "defiler"):
            self.x11.deplacer(action["x"], action["y"])
            time.sleep(0.05)
        if t == "cliquer":
            self._cliquer(BOUTONS[action["bouton"]])
        elif t == "double_cliquer":
            self._cliquer(1, 2)
        elif t == "clic_droit":
            self._cliquer(3)
        elif t == "glisser":
            self.x11.bouton(1, True)
            etapes = 12
            for i in range(1, etapes + 1):
                self.x11.deplacer(action["x"] + (action["x2"] - action["x"]) * i // etapes,
                                  action["y"] + (action["y2"] - action["y"]) * i // etapes)
                time.sleep(0.015)
            self.x11.bouton(1, False)
        elif t == "taper":
            for caractere in action["texte"]:
                self._taper_caractere(caractere)
        elif t == "touche":
            appuyees = []
            try:
                for nom in action["keysyms"]:
                    self._appuyer_keysym(nom, True)
                    appuyees.append(nom)
            finally:
                for nom in reversed(appuyees):
                    self._appuyer_keysym(nom, False)
        elif t == "defiler":
            self._cliquer(DEFILEMENT[action["sens"]], action["quantite"])
        return {"pointeur": list(self.x11.position())}


def journaliser(entree: dict[str, Any]) -> None:
    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
    with open(DOSSIER_SORTIE / "journal_actions.jsonl", "a", encoding="utf-8") as fichier:
        fichier.write(json.dumps({"date": time.strftime("%Y-%m-%dT%H:%M:%S"), **entree}, ensure_ascii=False) + "\n")


def agir(action: Any, *, x11_factory: Callable[[], Any] = X11, avec_captures: bool = True,
         environ: dict[str, str] | None = None) -> dict[str, Any]:
    """Valide puis exécute une action ; journalise avec l'empreinte de l'écran avant et après."""
    environ = os.environ if environ is None else environ
    if environ.get(ENV_ACTIVATION) != "1":
        return {"schema": SCHEMA, "ok": False,
                "raison": f"contrôle du bureau désactivé : définir {ENV_ACTIVATION}=1 pour l'autoriser sur ce PC"}
    try:
        propre = valider_action(action)
    except (ValueError, PermissionError) as exc:
        journaliser({"action": action if isinstance(action, dict) else str(action), "ok": False, "raison": str(exc)})
        return {"schema": SCHEMA, "ok": False, "raison": str(exc)}
    avant = capturer() if avec_captures else None
    try:
        with x11_factory() as x11:
            resultat = Bureau(x11).executer(propre)
    except (BureauIndisponible, ValueError) as exc:
        journaliser({"action": propre, "ok": False, "raison": str(exc)})
        return {"schema": SCHEMA, "ok": False, "raison": str(exc)}
    time.sleep(0.25)
    apres = capturer() if avec_captures else None
    sortie = {"schema": SCHEMA, "ok": True, "action": {k: v for k, v in propre.items() if k != "keysyms"}, **resultat,
              "ecran_avant": avant, "ecran_apres": apres,
              "ecran_change": bool(avant and apres and avant["sha256"] != apres["sha256"])}
    journaliser({k: v for k, v in sortie.items() if k not in ("ecran_avant", "ecran_apres")}
                | {"avant": avant and avant["sha256"], "apres": apres and apres["sha256"]})
    return sortie


def main() -> int:
    import argparse
    analyseur = argparse.ArgumentParser(description="Contrôle du bureau d'Aurora (X11)")
    sous = analyseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("capturer")
    loc = sous.add_parser("localiser")
    loc.add_argument("description")
    act = sous.add_parser("agir")
    act.add_argument("action_json")
    arguments = analyseur.parse_args()
    if arguments.commande == "capturer":
        print(json.dumps(capturer(), ensure_ascii=False))
    elif arguments.commande == "localiser":
        resultat = localiser(arguments.description)
        resultat.pop("capture", None)
        print(json.dumps(resultat, ensure_ascii=False))
    else:
        print(json.dumps(agir(json.loads(arguments.action_json)), ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
