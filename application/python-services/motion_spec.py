import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAUT = {
    "element_mobile": "eau",
    "type_mouvement": "ecoulement",
    "direction": "descendant",
    "vitesse": 1.0,
    "amplitude": 1.0,
    "viscosite": "fluide",
    "couleur_cible": "bleu",
    "elements_immobiles": ["pierre", "structure"],
    "description_attendue": (
        "L'element liquide s'ecoule de facon continue vers le bas, les surfaces "
        "horizontales ondulent en cercles qui se propagent, la structure reste "
        "parfaitement immobile, aucune matiere detachee ne flotte en l'air."),
}


def build_motion_spec(prompt, motion_prompt, timeout=120):
    try:
        from vlm_judge import ask_vlm
        q = ("Tu es le directeur d'animation d'un studio 3D. Objet genere: '%s'. "
             "Mouvement demande par l'utilisateur: '%s'. "
             "Decris la specification EXACTE du mouvement attendu pour CE concept "
             "(pas un modele generique): quel element bouge, quel type de mouvement "
             "(ecoulement, ondulation, fige, chute, tourbillon, montee), sa direction, "
             "sa vitesse relative (0.2 tres lent a 2.0 rapide), son amplitude relative "
             "(0.2 subtile a 2.0 forte), sa viscosite (fluide, epais, fige), la famille "
             "de couleur de l'element mobile dans la texture (bleu, chaud pour "
             "lave/feu orange-rouge, blanc, sombre, autre), ce qui doit rester "
             "immobile, et une description_attendue en 2-3 phrases qui servira de "
             "critere de verification visuelle. Si le concept implique une matiere "
             "figee/gelee, type_mouvement='fige' et amplitude=0."
             % (prompt, motion_prompt))
        spec = ask_vlm([], q,
                       schema_hint=json.dumps({
                           "element_mobile": "str", "type_mouvement": "str",
                           "direction": "str", "vitesse": 1.0, "amplitude": 1.0,
                           "viscosite": "str", "couleur_cible": "str",
                           "elements_immobiles": ["str"],
                           "description_attendue": "str"}, ensure_ascii=False),
                       timeout=timeout)
        if isinstance(spec, dict) and spec.get("description_attendue"):
            out = {**DEFAUT, **{k: v for k, v in spec.items() if v not in (None, "", [])}}
            try:
                out["vitesse"] = max(0.2, min(2.0, float(out["vitesse"])))
                out["amplitude"] = max(0.0, min(2.0, float(out["amplitude"])))
            except (TypeError, ValueError):
                out["vitesse"], out["amplitude"] = 1.0, 1.0
            if str(out.get("type_mouvement", "")).lower() in ("fige", "gele", "frozen", "statique"):
                out["amplitude"] = 0.0
                out["viscosite"] = "fige"
            _c = str(out.get("couleur_cible", "")).lower()
            if any(k in _c for k in ("chaud", "orange", "rouge", "lave", "feu", "incandes")):
                out["couleur_cible"] = "chaud"
            elif any(k in _c for k in ("blanc", "neige", "lait", "glac")):
                out["couleur_cible"] = "blanc"
            elif any(k in _c for k in ("sombre", "noir", "boue")):
                out["couleur_cible"] = "sombre"
            else:
                out["couleur_cible"] = "bleu"
            return out
    except Exception:  # noqa: BLE001
        pass
    return dict(DEFAUT)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--motion", required=True)
    a = ap.parse_args()
    print("AURORA_MOTION_SPEC:" + json.dumps(build_motion_spec(a.prompt, a.motion), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
