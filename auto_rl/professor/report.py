"""Read a diagnosis or a verdict and print what was measured, in French.

    python -m auto_rl.professor.report CHEMIN/diagnosis.json
    python -m auto_rl.professor.report CHEMIN/verdict_0.json

Nothing is recomputed or rounded in the model's favour: the lines are the
examiner's numbers. Output goes to the terminal; no report file is written.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _percent(value):
    return "  n/a " if value is None else f"{100 * value:5.1f} %"


def diagnosis_lines(report):
    overall = report["summary"]["overall"]
    lines = [f"Diagnostic de {report['student']['tag']} ({report['student']['hf']}) — modules : {', '.join(report['modules'])}",
             f"Examen {'complet' if report['complete'] else 'INCOMPLET'} : {overall['items']} items notés, "
             f"{overall['skipped']} ignorés (prompt trop long), précision macro {_percent(overall['macro_accuracy']).strip()}",
             "", "Points faibles, du plus faible au plus fort (intervalle de Wilson à 95 %) :"]
    for row in report["weak_points"]:
        low, high = row["ci95"]
        note = "" if row["trainable"] else "   [mesuré, sans données d'entraînement directes]"
        lines.append(f"  {_percent(row['accuracy'])}  [{100 * low:4.0f} ; {100 * high:4.0f}]  n={row['items']:4d}  {row['skill']}{note}")
        worst = [f"{sub['subskill']} {100 * sub['accuracy']:.0f} %" for sub in row["subskills"][:4] if sub["items"] >= 3]
        if worst:
            lines.append("            sous-compétences les plus faibles : " + ", ".join(worst))
    return lines


def verdict_lines(verdict):
    overall = verdict["overall"]
    low, high = overall["macro_gain_ci"]
    label = {"promote": "PROMU", "reject": "REJETÉ", "inconclusive": "NON CONCLUANT"}[verdict["verdict"]]
    lines = [f"Verdict du cycle {verdict['cycle']} pour {verdict['student']['tag']} : {label}"
             + ("" if verdict["verdict"] != "promote" else (" — installable" if verdict["promotable"] else " — non installable (élève de répétition ou examen incomplet)")),
             *[f"  motif : {reason}" for reason in verdict["reasons"]],
             f"Examen apparié : {overall['items']} items notés pour les deux modèles ({'complet' if verdict['exam_complete'] else 'INCOMPLET'})",
             f"Précision macro : {_percent(overall['macro_base']).strip()} → {_percent(overall['macro_candidate']).strip()} "
             f"(gain {100 * overall['macro_gain']:+.1f} points, intervalle à 95 % [{100 * low:+.1f} ; {100 * high:+.1f}])",
             f"Items corrigés par le candidat : {overall['fixed']} ; items cassés : {overall['broken']} ; McNemar exact p = {overall['mcnemar_p']:.4f}",
             "", "Par compétence (base → candidat, gain, p de McNemar, n) :"]
    for skill, table in sorted(verdict["skills"].items(), key=lambda kv: -kv[1]["gain"]):
        flag = "  RÉGRESSION" if skill in verdict["regressions"] else ""
        lines.append(f"  {_percent(table['base_accuracy'])} → {_percent(table['candidate_accuracy'])}  {100 * table['gain']:+6.1f}  "
                     f"p={table['mcnemar_p']:.3f}  n={table['items']:4d}  {skill}{flag}")
    training = verdict.get("training") or {}
    if training.get("steps") is not None:
        lines += ["", f"Entraînement : {training['steps']} pas, arrêt « {training['stopped']} », perte de développement "
                      f"{training['initial_dev_loss']:.4f} → {training['selected_dev_loss']:.4f} "
                      "(une perte plus basse n'est pas une preuve de meilleures réponses)."]
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path)
    report = json.loads(parser.parse_args(argv).path.read_text(encoding="utf-8"))
    kind = report.get("kind")
    if kind == "aurora_professor_diagnosis":
        print("\n".join(diagnosis_lines(report)))
    elif kind == "aurora_professor_verdict":
        print("\n".join(verdict_lines(report)))
    else:
        raise SystemExit(f"Fichier non reconnu : kind={kind!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
