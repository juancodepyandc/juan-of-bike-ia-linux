"""Préférer la dominance et distinguer les arbitrages de qualité.

Le cycle de préférences classait les échantillons par le seul score composite
(`sorted(..., score)` puis `ranked[-1]`). Un candidat pouvait donc gagner sur la
moyenne en dégradant une métrique prise isolément, par exemple la pire vue CLIP ou
le nombre d'auto-intersections. Le gradient obtenu était alors un arbitrage, pas
une amélioration: « gagne 0,01 de score en perdant 0,03 de pire vue ».

Ici on filtre d'abord par dominance de Pareto. Un échantillon A domine B si A est
au moins aussi bon sur TOUTES les métriques suivies, et strictement meilleur sur
au moins une. Le gagnant est choisi parmi le front de Pareto. Une paire
strictement dominante préserve les métriques communes mesurées ; les autres
paires restent des arbitrages explicitement marqués, sans garantie de
non-régression. Cela ne prouve pas la qualité d'un modèle après entraînement.

Ce module ne modifie AUCUNE formule de score. Il ne fait que choisir, parmi des
échantillons déjà jugés, lequel devient le gagnant d'une paire de préférences.
"""
from __future__ import annotations

# direction: +1 = plus haut est mieux, -1 = plus bas est mieux
# "neutre" = volontairement absent, ce n'est pas un critère de qualité
TRACKED_3D: dict[str, int] = {
    "clip_mean": +1,
    "clip_worst_view": +1,
    "self_intersections_exactes": -1,
    "taux_faces_auto_intersectees": -1,
    "nonmanifold_edge_fraction": -1,
    "boundary_edge_fraction": -1,
    "fragment_area_fraction": -1,
    "degenerate_face_fraction": -1,
    "self_intersections": -1,
}


def _value(metrics: dict, key: str):
    v = metrics.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    v = float(v)
    return v if v == v and abs(v) != float("inf") else None


def metrics_of(sample: dict) -> dict:
    """Les métriques d'un échantillon.

    Elles sont imbriquées sous `judge["metrics"]`, pas sous `judge` directement.
    Lire le mauvais niveau renvoyait silencieusement un dictionnaire vide, et
    toute comparaison se déclenchait alors sur ZERO métrique: le filtre de
    dominance devenait un no-op au lieu de lever une erreur.
    """
    judge = sample.get("judge") or {}
    metrics = judge.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def comparable(a: dict, b: dict, tracked: dict[str, int]) -> list[str]:
    """Métriques exploitables pour comparer a et b (présentes et finies des deux)."""
    return [k for k in tracked
            if _value(a, k) is not None and _value(b, k) is not None]


def dominates(a: dict, b: dict, tracked: dict[str, int]) -> bool | None:
    """a domine-t-il b ? None si les deux n'ont aucune métrique commune.

    `None` distingue "pas de domination" de "comparaison impossible", ce qui
    évite de traiter une absence de données comme une égalité.
    """
    keys = comparable(a, b, tracked)
    if not keys:
        return None
    au_bout = False
    for k in keys:
        va, vb = _value(a, k), _value(b, k)
        if tracked[k] * (va - vb) > 0:
            au_bout = True
        elif tracked[k] * (va - vb) < 0:
            return False
    return au_bout


def _spec(tracked: dict[str, int], keys) -> dict[str, int]:
    """Restreint la table de directions aux métriques effectivement comparables."""
    return {k: tracked[k] for k in keys}


def pareto_front(samples: list[dict], tracked: dict[str, int]) -> tuple[list[dict], list[str]]:
    """Retourne (front, métriques réellement utilisées).

    Un échantillon du front n'est dominé par aucun autre. Les métriques retenues
    sont celles que TOUS les échantillons portent, pour ne pas comparer sur une
    métrique que certains n'ont pas mesurée.
    """
    metrics = [metrics_of(s) for s in samples]
    used = [k for k in tracked
            if all(_value(m, k) is not None for m in metrics)]
    spec = _spec(tracked, used)
    front = [s for s in samples
             if not any(dominates(metrics_of(o), metrics_of(s), spec) is True
                        for o in samples if o is not s)]
    return front, used


def front_best(front: list[dict], tracked: dict[str, int], used) -> dict:
    """Le candidat du front qui est au meilleur sur le plus de métriques.

    Quand aucun candidat ne domine un autre, ils sont mutuellement
    incomparables: la non-régression stricte sur TOUTES les métriques est
    mathématiquement impossible. Plutôt que de ne rien apprendre, on retient
    celui qui atteint le meilleur niveau sur le plus grand nombre de métriques,
    donc celui qui régresse sur le moins de critères possibles. Le score ne sert
    qu'à départager les égalités.
    """
    best = {k: max(tracked[k] * _value(metrics_of(c), k) for c in front) for k in used}
    def key(c):
        m = metrics_of(c)
        au_best = sum(1 for k in used
                      if tracked[k] * _value(m, k) >= best[k] - 1e-12)
        return (au_best, float((c.get("judge") or {}).get("score", -1.0)))
    return max(front, key=key)


def gain(a: dict, b: dict, tracked: dict[str, int], used) -> float:
    """Plus grand gain orienté de a sur b parmi les métriques comparables."""
    ma, mb = metrics_of(a), metrics_of(b)
    g = [tracked[k] * (_value(ma, k) - _value(mb, k)) for k in used]
    return max(g) if g else 0.0


def select(samples: list[dict], tracked: dict[str, int], margin: float = 1e-5):
    """Choisit (winner, loser, diagnostic) parmi des échantillons déjà jugés.

    Deux cas, volontairement distingués:

    - dominance stricte: un candidat est au moins aussi bon partout et
      strictement meilleur quelque part. Il gagne, la paire n'entraîne
      AUCUNE régression, et c'est le cas recherché.
    - incomparabilité: personne ne domine. La non-régression stricte est
      impossible sans changer la génération. On garde une paire pour ne pas
      perdre la supervision, mais elle est marquée `strict: False` afin que
      l'audit puisse compter les arbitrages au lieu de les découvrir plus tard.

    Conséquence importante: une paire strictement dominante n'est PAS filtrée
    sur l'écart de score. Améliorer toutes les métriques suivies peut faire
    baisser le score composite, puisque celui-ci ne connaît pas la métrique
    exacte. Refuser ce cas reviendrait à réintroduire la régression qu'on veut
    supprimer. Le filtre de score ne s'applique donc qu'aux paires d'arbitrage,
    où il joue son rôle habituel de garde-fou anti-bruit.
    """
    valid = [s for s in samples if (s.get("judge") or {}).get("valid")]
    if len(valid) < 2:
        return None, None, {"raison": "moins de deux échantillons valides",
                            "valides": len(valid), "total": len(samples)}
    front, used = pareto_front(valid, tracked)
    if not front:
        return None, None, {"raison": "front de Pareto vide", "valides": len(valid)}
    spec = _spec(tracked, used)

    # On préfère une paire à dominance stricte: elle est non régressive.
    strict = [c for c in front
              if any(dominates(metrics_of(c), metrics_of(o), spec) is True
                     for o in valid if o is not c)]
    if strict:
        winner = max(strict, key=lambda c: float((c.get("judge") or {}).get("score", -1.0)))
    else:
        winner = front_best(front, tracked, used)

    beaten = [s for s in valid if s is not winner
              and dominates(metrics_of(winner), metrics_of(s), spec) is True]
    if beaten:
        loser = min(beaten, key=lambda s: float((s.get("judge") or {}).get("score", float("inf"))))
    else:
        # Aucun échantillon n'est dominé par le gagnant: on conserve le pire
        # échantillon comme négatif dur plutôt que de jeter la tâche.
        loser = min(valid, key=lambda s: (bool((s.get("judge") or {}).get("valid")),
                                           float((s.get("judge") or {}).get("score", float("inf")))))
    wj, lj = winner.get("judge") or {}, loser.get("judge") or {}
    ecart = float(wj.get("score", 0.0)) - float(lj.get("score", 0.0))
    if beaten:
        # Paire non régressive: le seuil pertinent est le gain de métrique, pas
        # le score, qui peut légitimement baisser.
        g = gain(winner, loser, tracked, used)
        if g <= 1e-12:
            return None, None, {"raison": "dominance indiscernable sur toutes les métriques",
                                "valides": len(valid), "front": len(front), "strict": True}
    elif ecart <= margin:
        return None, None, {"raison": f"écart de score inférieur au seuil {margin}",
                            "valides": len(valid), "front": len(front), "strict": False}
    return winner, loser, {
        "raison": "dominance" if beaten else "arbitrage_non_regressif_minimal",
        "strict": bool(beaten),
        "metriques_utilisees": used,
        "valides": len(valid),
        "front": len(front),
        "perdants_domines": len(beaten),
        "ecart_score": ecart,
    }
