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
    basis = report.get("basis") or {}
    subject = "du candidat entraîné" if basis.get("model") == "candidate" else "du modèle de base"
    lines = [f"Diagnostic {subject} de {report['student']['tag']} ({report['student']['hf']}) — modules : {', '.join(report['modules'])}",
             *([f"Tiré de l'examen {basis['exam']} ; adaptateur {str(basis.get('adapter_sha256'))[:16]}… : c'est le point de départ du cycle suivant."]
               if basis else []),
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


def _reuse_lines(verdict):
    """Exam items that an earlier cycle already used: said plainly, because they are not unseen any more."""
    notes = (verdict.get("exam") or {}).get("notes") or {}
    counted = notes.get("reused_items") or {}
    if counted:
        detail = ", ".join(f"{skill} {count}" for skill, count in sorted(counted.items()))
        return [f"  dont {sum(counted.values())} items déjà utilisés par l'examen d'un cycle précédent (réserve épuisée) : {detail}"]
    if notes.get("reused"):
        return ["  dont des items déjà utilisés par un cycle précédent pour : " + ", ".join(sorted(notes["reused"]))]
    return []


def verdict_lines(verdict):
    overall = verdict["overall"]
    low, high = overall["macro_gain_ci"]
    label = {"promote": "PROMU", "reject": "REJETÉ", "inconclusive": "NON CONCLUANT"}[verdict["verdict"]]
    lines = [f"Verdict du cycle {verdict['cycle']} pour {verdict['student']['tag']} : {label}"
             + ("" if verdict["verdict"] != "promote" else (" — installable" if verdict["promotable"] else " — NON installable")),
             *[f"  motif : {reason}" for reason in verdict["reasons"]],
             *[f"  non installable : {problem}" for problem in (verdict.get("not_installable") or [])
               if verdict["verdict"] == "promote"],
             *([f"  compétences non examinées faute d'exécution de code : {', '.join(skipped)}"]
               if (skipped := ((verdict.get("exam") or {}).get("notes") or {}).get("skipped_no_execution")) else []),
             f"Examen apparié : {overall['items']} items notés pour les deux modèles ({'complet' if verdict['exam_complete'] else 'INCOMPLET'})",
             *_reuse_lines(verdict),
             f"Précision macro : {_percent(overall['macro_base']).strip()} → {_percent(overall['macro_candidate']).strip()} "
             f"(gain {100 * overall['macro_gain']:+.1f} points, intervalle à 95 % [{100 * low:+.1f} ; {100 * high:+.1f}])",
             f"Items corrigés par le candidat : {overall['fixed']} ; items cassés : {overall['broken']} ; McNemar exact p = {overall['mcnemar_p']:.4f}",
             "", "Par compétence (base → candidat, gain, p de McNemar, n) :"]
    for skill, table in sorted(verdict["skills"].items(), key=lambda kv: -kv[1]["gain"]):
        flag = "  RÉGRESSION" if skill in verdict["regressions"] else ""
        lines.append(f"  {_percent(table['base_accuracy'])} → {_percent(table['candidate_accuracy'])}  {100 * table['gain']:+6.1f}  "
                     f"p={table['mcnemar_p']:.3f}  n={table['items']:4d}  {skill}{flag}")
    versus = verdict.get("versus_previous")
    if versus:
        against = versus["overall"]
        low, high = against["macro_gain_ci"]
        outcome = {"promote": "MEILLEUR que l'adaptateur précédent", "reject": "MOINS BON que l'adaptateur précédent",
                   "inconclusive": "différence NON ÉTABLIE avec l'adaptateur précédent"}[versus["verdict"]]
        lines += ["", f"Contre l'adaptateur que ce cycle prolonge, sur les mêmes items : {outcome}"
                      + ("" if versus.get("complete", True) else " (examen INCOMPLET)"),
                  f"  précision macro {_percent(against['macro_base']).strip()} → {_percent(against['macro_candidate']).strip()} "
                  f"(gain {100 * against['macro_gain']:+.1f} points, intervalle à 95 % [{100 * low:+.1f} ; {100 * high:+.1f}]) ; "
                  f"corrigés {against['fixed']}, cassés {against['broken']}, McNemar exact p = {against['mcnemar_p']:.4f}",
                  *[f"  motif : {reason}" for reason in versus["reasons"]]]
    training = verdict.get("training") or {}
    if training.get("steps") is not None:
        origin = " (suite d'un adaptateur existant)" if training.get("continued_from") else ""
        loss = lambda value: "n/a" if value is None else f"{value:.4f}"
        lines += ["", f"Entraînement{origin} : {training['steps']} pas, arrêt « {training['stopped']} », perte de développement "
                      f"{loss(training.get('initial_dev_loss'))} → {loss(training.get('selected_dev_loss'))} "
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
