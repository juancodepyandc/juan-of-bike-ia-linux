from __future__ import annotations

import html
import math
import statistics
from pathlib import Path

import numpy as np


def promotion_gate(base, champion, candidate, config):
    reasons = []
    keys = lambda rows: [(r["task_id"], r["seed"]) for r in rows]
    if not candidate or keys(base) != keys(candidate) or keys(champion) != keys(candidate):
        return {"eligible": False, "reasons": ["Comparaison incomplète ou graines différentes"],
                "candidate_mean": None, "base_mean": None, "champion_mean": None}
    b = np.array([r["judge"]["score"] for r in base], dtype=float)
    p = np.array([r["judge"]["score"] for r in champion], dtype=float)
    c = np.array([r["judge"]["score"] for r in candidate], dtype=float)
    if not all(np.isfinite(a).all() for a in (b, p, c)):
        return {"eligible": False, "reasons": ["Score non fini"],
                "candidate_mean": None, "base_mean": None, "champion_mean": None}
    for branches in zip(base, champion, candidate):
        if len({r["generation_digest"] for r in branches}) != 1:
            reasons.append("Paramètres d'inférence différents")
        if any(not r["judge"]["valid"] for r in branches):
            reasons.append("Au moins une mesure obligatoire manque ou échoue")
        if any(r["peak_vram_gb"] > config["max_vram_gb"] for r in branches):
            reasons.append("Budget VRAM dépassé")
    delta = c - p
    groups = {}
    for row, value in zip(candidate, delta):
        groups.setdefault(row["task_id"], []).append(float(value))
    group_means = np.array([np.mean(v) for v in groups.values()])
    # Resample PROMPTS, not seeds: repeated seeds are correlated observations.
    boot = np.random.default_rng(7391).choice(group_means, (4000, len(groups)), replace=True).mean(axis=1)
    ci = [float(x) for x in np.quantile(boot, [0.025, 0.975])]
    if len(groups) < 3:
        reasons.append("Moins de 3 sujets d'audit indépendants")
    if float(delta.mean()) <= config["min_gain"]:
        reasons.append("Gain moyen insuffisant face au champion")
    if ci[0] <= 0:
        reasons.append("Gain non concluant dans l'intervalle bootstrap à 95 %")
    if np.min(c - p) < -config["regression_tolerance"]:
        reasons.append("Régression mesurée face au champion sur un sujet")
    if np.min(c - b) < -config["regression_tolerance"]:
        reasons.append("Régression mesurée face à la base sur un sujet")
    if config["mode"] == "auto" and len(groups) < config["auto_min_tasks"]:
        reasons.append("Audit trop petit pour une promotion automatique")
    return {"eligible": not reasons, "reasons": sorted(set(reasons)),
            "base_mean": float(b.mean()), "champion_mean": float(p.mean()), "candidate_mean": float(c.mean()),
            "gain_points": float(delta.mean() * 100), "base_gain_points": float((c - b).mean() * 100),
            "ci95_gain_points": [x * 100 for x in ci], "tasks": len(groups), "samples": len(candidate),
            "wins": int((delta > 1e-9).sum()), "ties": int((abs(delta) <= 1e-9).sum()),
            "losses": int((delta < -1e-9).sum())}


def write_html(run, report):
    run = Path(run)
    esc = lambda s: html.escape(str(s), quote=True)
    def link(path):
        import os
        from urllib.parse import quote
        return quote(os.path.relpath(path, run))
    def cell(row):
        path = Path(row["artifact"])
        judge = row["judge"]
        body = f'<strong>Score : {judge["score"]:.4f}</strong><small>{row["seconds"]:.1f} s · {row["peak_vram_gb"]:.2f} Go VRAM</small>'
        if path.suffix == ".png":
            body += f'<img src="{link(path)}" alt="Résultat généré">'
        elif path.suffix == ".wav":
            body += f'<audio controls preload="none" src="{link(path)}"></audio>'
        elif path.suffix == ".glb":
            body += '<div class="views">' + ''.join(f'<img src="{link(p)}" alt="Vue {i + 1}">' for i, p in enumerate(judge["metrics"].get("views", []))) + '</div>'
        else:
            body += f'<pre>{esc(path.read_text()[:20000])}</pre>'
        body += f'<p><a href="{link(path)}">Ouvrir le fichier {esc(path.suffix)}</a></p>'
        body += '<details><summary>Mesures du juge</summary><pre>'
        import json
        body += esc(json.dumps(judge, ensure_ascii=False, indent=2)) + '</pre></details>'
        return body
    gate = report["gate"]
    state = "Candidat admissible à la validation" if gate["eligible"] else "Candidat non promouvable"
    reasons = " · ".join(gate["reasons"])
    cards = ""
    for before, previous, after in zip(report["base"], report["champion"], report["candidate"]):
        cards += f'<section><h2>{esc(after["prompt"])}</h2><small>{esc(after["task_id"])} · graine {after["seed"]}</small><div class="grid">'
        for title, row in (("Base intacte", before), ("Champion au début du cycle", previous), ("Candidat", after)):
            cards += f'<article><h3>{title}</h3>{cell(row)}</article>'
        cards += '</div></section>'
    page = f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aurora · Comparaison {esc(report['run_id'])}</title><style>
body{{font:16px system-ui;background:#101723;color:#e5edf8;max-width:1500px;margin:auto;padding:30px}}
h1{{font-size:32px}}small{{display:block;color:#a4b5cd;margin:8px 0}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}}
article,header{{background:#1b2636;border:1px solid #33455d;padding:20px;border-radius:12px}}section{{margin:35px 0}}a{{color:#83caff}}
img{{width:100%;object-fit:contain;border-radius:7px}}.views{{display:grid;grid-template-columns:1fr 1fr;gap:5px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;max-height:450px;overflow:auto}}audio{{width:100%;margin:20px 0}}
.metric{{font-size:25px;color:#83dbcd}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style><header><small>AURORA · {esc(report['module'])} · {esc(report['run_id'])}</small><h1>{state}</h1>
<p class="metric">Gain face au champion : {gate.get('gain_points', 0):+.3f} points / 100</p>
<p>{esc(reasons)}</p><p>Même modèle de base, même matériel, mêmes paramètres et mêmes graines pour chaque comparaison.</p>
<p>{gate.get('tasks', 0)} sujets réservés, {gate.get('samples', 0)} générations par version. Intervalle à 95 % du gain : {esc(gate.get('ci95_gain_points'))} points.</p>
<p>Ces mesures ne garantissent ni une amélioration générale, ni l'absence de régression hors de cet audit. Le bouton Valider se trouve dans le centre Aurora.</p>
<a href="report.json">Rapport JSON complet</a> · <a href="config.json">Paramètres</a></header>{cards}</html>'''
    (run / "comparison.html").write_text(page)
    return str(run / "comparison.html")
