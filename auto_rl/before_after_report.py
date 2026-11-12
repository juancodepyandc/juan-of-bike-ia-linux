"""Générateur automatique du comparatif visuel Avant/Après (`AVANT_APRES_3D_COMPARAISON.png`)
et du bilan détaillé mais simple à comprendre (`BILAN_AVANT_APRES_ET_GAINS.md`).

Exécuté automatiquement à la fin de chaque cycle d'entraînement 3D (et sur demande via CLI `/avant-apres`).
N'écrit que des valeurs mesurées en audit : aucune note n'est remplacée ni relevée par un plancher,
un écart nul ou négatif est affiché tel quel, et une valeur absente est écrite « non mesuré ».
"""
from __future__ import annotations

import json
import math
import os
import shutil
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .config import ROOT, STATE
from .reinforced_registry import NON_MESURE, PROMOTED_STATUS, honest_status, sign_test_sentence
from .storage import read_json


BUREAU_STUDIO_DIR = Path("/home/juan/Bureau/AuroraIA_Studio_&_Renforcement")


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    )
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, size: int, bold: bool = False):
    """Largest font up to `size` that keeps `text` inside `max_width` (measured sentences are longer)."""
    font = _load_font(size, bold)
    while size > 9 and draw.textlength(text, font=font) > max_width:
        size -= 1
        font = _load_font(size, bold)
    return font


def _measured(value: Any) -> float | None:
    """A finite measured number, or None. A missing value is never replaced by a literal."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _txt(value: float | None, spec: str = ".2f", unit: str = "") -> str:
    return NON_MESURE if value is None else f"{value:{spec}}{unit}"


def _count_txt(value: int | None) -> str:
    return NON_MESURE if value is None else f"{value:,}".replace(",", " ")


def _range_txt(values: list[Any], render) -> str:
    """`min à max` over the measured values of the loaded pairs, or « non mesuré »."""
    known = [v for v in values if v is not None]
    if not known:
        return NON_MESURE
    low, high = min(known), max(known)
    return render(low) if low == high else f"{render(low)} à {render(high)}"


def _si_change_pct(pair: dict[str, Any]) -> float | None:
    """Relative change of self-intersections for one pair; undefined without a positive baseline."""
    base, cand = pair["base_si"], pair["cand_si"]
    if base is None or cand is None or base <= 0:
        return None
    return (cand - base) / base * 100.0


def _find_best_audit_pairs(state: Path) -> list[dict[str, Any]]:
    """Trouve, pour chaque famille, la paire auditée AVANT (base) vs APRÈS (candidat) au meilleur écart.

    Ce sont des meilleurs cas, pas des cas typiques : chaque paire porte `family_pairs_examined`,
    le nombre de paires comparables examinées pour sa famille, tous cycles confondus.
    """
    runs_dir = state / "runs"
    candidate_runs = []
    if runs_dir.is_dir():
        for d in sorted(runs_dir.iterdir(), reverse=True):
            if d.is_dir() and d.name.startswith("3d-") and (d / "AVANT_BASE").is_dir() and (d / "APRES_CANDIDAT").is_dir():
                candidate_runs.append(d)

    def metric(metrics: dict[str, Any], key: str, scale: float = 1.0) -> float | None:
        value = _measured(metrics.get(key))
        return None if value is None else value * scale

    def count(metrics: dict[str, Any], key: str) -> int | None:
        value = _measured(metrics.get(key))
        return None if value is None else int(value)

    best_by_family: dict[str, dict[str, Any]] = {}
    examined: dict[str, int] = {}
    for run_dir in candidate_runs:
        base_dir = run_dir / "AVANT_BASE"
        cand_dir = run_dir / "APRES_CANDIDAT"
        for eval_file in sorted(base_dir.glob("*.evaluation.json")):
            cand_file = cand_dir / eval_file.name
            if not cand_file.is_file():
                continue
            b_data = read_json(eval_file, {})
            c_data = read_json(cand_file, {})
            b_judge = b_data.get("judge", {})
            c_judge = c_data.get("judge", {})
            b_metrics = b_judge.get("metrics", {})
            c_metrics = c_judge.get("metrics", {})
            b_views = [p for p in b_metrics.get("views", []) if os.path.isfile(p)]
            c_views = [p for p in c_metrics.get("views", []) if os.path.isfile(p)]
            if len(b_views) < 2 or len(c_views) < 2:
                continue
            b_score = _measured(b_judge.get("score"))
            c_score = _measured(c_judge.get("score"))
            if b_score is None or c_score is None:
                # Without a judged score on both sides there is no measured difference to show.
                continue
            gain_pts = (c_score - b_score) * 100.0
            family = str(b_data.get("family") or eval_file.stem.split("_")[1])
            examined[family] = examined.get(family, 0) + 1
            item = {
                "run_id": run_dir.name,
                "eval_name": eval_file.stem.replace(".evaluation", ""),
                "family": family,
                "prompt": str(b_data.get("prompt", "")),
                "style": str(b_data.get("style", "")),
                "gain_pts": gain_pts,
                "base_score_100": b_score * 100.0,
                "cand_score_100": c_score * 100.0,
                "base_si": count(b_metrics, "self_intersections"),
                "cand_si": count(c_metrics, "self_intersections"),
                "base_frag": metric(b_metrics, "fragment_area_fraction", 100.0),
                "cand_frag": metric(c_metrics, "fragment_area_fraction", 100.0),
                "base_clip": metric(b_metrics, "clip_mean", 100.0),
                "cand_clip": metric(c_metrics, "clip_mean", 100.0),
                "base_worst": metric(b_metrics, "clip_worst_view", 100.0),
                "cand_worst": metric(c_metrics, "clip_worst_view", 100.0),
                "base_views": b_views,
                "cand_views": c_views,
            }
            if family not in best_by_family or item["gain_pts"] > best_by_family[family]["gain_pts"]:
                best_by_family[family] = item
    for family, item in best_by_family.items():
        item["family_pairs_examined"] = examined[family]

    preferred_order = ["owl", "bicycle", "cathedral", "helmet", "camera"]
    ordered: list[dict[str, Any]] = []
    for fam in preferred_order:
        if fam in best_by_family:
            ordered.append(best_by_family[fam])
    for fam, item in sorted(best_by_family.items(), key=lambda kv: kv[1]["gain_pts"], reverse=True):
        if item not in ordered:
            ordered.append(item)
    return ordered[:3]


def _compose_two_views(views: list[str], target_w: int, target_h: int) -> Image.Image:
    """Two untouched audit renders side by side. Nothing is drawn over them: no rig is measured here."""
    panel = Image.new("RGB", (target_w, target_h), (14, 19, 30))
    half_w = (target_w - 12) // 2
    selected = [views[0], views[min(2, len(views) - 1)]]
    labels = ["Vue Avant (0°)", "Vue Latérale / Arrière (360°)"]
    font_small = _load_font(13, bold=True)
    for idx, vpath in enumerate(selected):
        try:
            img = Image.open(vpath).convert("RGB")
            img.thumbnail((half_w, target_h - 28), Image.Resampling.LANCZOS)
            px = idx * (half_w + 12) + (half_w - img.width) // 2
            py = 24 + (target_h - 28 - img.height) // 2
            panel.paste(img, (px, py))
        except Exception:
            pass
        draw = ImageDraw.Draw(panel)
        lx = idx * (half_w + 12) + 8
        draw.text((lx, 4), labels[idx], fill=(148, 163, 184), font=font_small)
    return panel


def _statut(manifest_3d: dict[str, Any], promoted: bool) -> str:
    """What the manifest allows us to say about the candidate; "non promu" unless proven otherwise."""
    if promoted:
        return "candidat promu (registre officiel)"
    return "candidat non promu" if manifest_3d.get("run_id") else "aucun candidat mesuré"


def _audit_sentence(score_base: float | None, score_renforce: float | None, gain: float | None,
                    manifest_3d: dict[str, Any]) -> str:
    """French sentence stating the audited composite, its paired outcome and the sign test."""
    if score_base is None or score_renforce is None:
        return f"Note composite d'audit : {NON_MESURE} (aucun score dans le manifeste)."
    sentence = (f"Note composite mesurée en audit : {score_base:.2f} → {score_renforce:.2f} sur 100 "
                f"(écart moyen {_txt(gain, '+.3f', ' pt')})")
    wins, losses, samples = manifest_3d.get("wins"), manifest_3d.get("losses"), manifest_3d.get("samples_audited")
    if all(isinstance(v, int) and not isinstance(v, bool) for v in (wins, losses, samples)):
        sentence += f" ; {wins} victoires / {losses} défaites sur {samples} paires auditées"
        sign_test = sign_test_sentence(wins, losses)
        if sign_test:
            sentence += f" ; {sign_test}"
    return sentence + "."


def generate_before_after_visual_and_report(state: Path = STATE) -> dict[str, Any]:
    """Génère la photo comparative `AVANT_APRES_3D_COMPARAISON.png` et le rapport `BILAN_AVANT_APRES_ET_GAINS.md`."""
    state = Path(state).resolve()
    manifest_3d = read_json(ROOT / "modele" / "renforce" / "3d" / "manifest.json", {}) or {}
    status_data = read_json(state / "status.json", {})

    # Exactly what the audit measured: no substitution, no floor, no fallback literal.
    score_base = _measured(manifest_3d.get("score_base_100"))
    score_renforce = _measured(manifest_3d.get("score_renforce_100"))
    gain_global = _measured(manifest_3d.get("gain_points_100"))
    if gain_global is None and score_base is not None and score_renforce is not None:
        gain_global = score_renforce - score_base
    # "Promu" only when the official registry still lists this very run; default "non promu".
    promoted = honest_status(manifest_3d, state, "3d") == PROMOTED_STATUS
    statut = _statut(manifest_3d, promoted)

    pairs = _find_best_audit_pairs(state)
    si_changes = [pct for pct in (_si_change_pct(p) for p in pairs) if pct is not None]

    width, height = 1680, 1260
    img = Image.new("RGB", (width, height), (9, 13, 22))
    draw = ImageDraw.Draw(img)

    font_h2 = _load_font(18, bold=True)
    font_metric = _load_font(14, bold=True)
    font_body = _load_font(13, bold=False)

    # En-tête supérieur
    box_x = width - 600
    header_room = box_x - 44 - 20
    draw.rounded_rectangle((24, 20, width - 24, 142), radius=14, fill=(15, 23, 42), outline=(56, 189, 248), width=2)
    header_title = "AURORA IA — COMPARATIF VISUEL AVANT / APRÈS 3D (MESURES D'AUDIT)"
    draw.text((44, 34), header_title, fill=(248, 250, 252), font=_fit_font(draw, header_title, header_room, 22, bold=True))
    if manifest_3d.get("run_id"):
        header_sub = f"Modèle de base (poids d'origine)  vs  candidat entraîné {manifest_3d['run_id']} — {statut}"
    else:
        header_sub = "Modèle de base (poids d'origine) — aucun candidat mesuré dans le manifeste"
    draw.text((44, 68), header_sub, fill=(148, 163, 184), font=_fit_font(draw, header_sub, header_room, 14))
    header_note = "Chaque cas affiché est le meilleur écart de sa famille, tous cycles confondus : il ne représente pas le gain moyen."
    draw.text((44, 98), header_note, fill=(56, 189, 248), font=_fit_font(draw, header_note, header_room, 14, bold=True))

    # Encadré de la note composite mesurée, en haut à droite
    box_room = (width - 38) - (box_x + 18) - 14
    draw.rounded_rectangle((box_x, 30, width - 38, 132), radius=12, fill=(6, 78, 59), outline=(16, 185, 129), width=2)
    box_title = f"NOTE COMPOSITE 3D — MESURE D'AUDIT · {statut.upper()}"
    draw.text((box_x + 18, 40), box_title, fill=(167, 243, 208), font=_fit_font(draw, box_title, box_room, 13, bold=True))
    if score_base is None or score_renforce is None:
        box_scores = f"AVANT : {NON_MESURE}  ->  APRÈS : {NON_MESURE}"
    else:
        box_scores = f"AVANT : {score_base:.2f}/100  ->  APRÈS : {score_renforce:.2f}/100"
    draw.text((box_x + 18, 60), box_scores, fill=(255, 255, 255), font=_fit_font(draw, box_scores, box_room, 19, bold=True))
    box_gain = f"ÉCART MOYEN : {_txt(gain_global, '+.3f', ' pt')}"
    wins, losses, samples = manifest_3d.get("wins"), manifest_3d.get("losses"), manifest_3d.get("samples_audited")
    if gain_global is not None and all(isinstance(v, int) and not isinstance(v, bool) for v in (wins, losses, samples)):
        box_gain += f"  ·  {wins} V / {losses} D sur {samples} paires"
    draw.text((box_x + 18, 90), box_gain, fill=(110, 231, 183), font=_fit_font(draw, box_gain, box_room, 12, bold=True))
    if pairs:
        # Peaks come from the pairs loaded above and are named for what they are: best cases.
        box_peak = f"Meilleurs cas affichés : note {max(p['gain_pts'] for p in pairs):+.2f} pts"
        if si_changes:
            box_peak += f"  ·  auto-intersections {min(si_changes):+.1f} %"
        draw.text((box_x + 18, 109), box_peak, fill=(110, 231, 183), font=_fit_font(draw, box_peak, box_room, 12, bold=True))

    # En-têtes de colonnes AVANT / APRÈS
    col_w = (width - 72) // 2
    left_x = 24
    right_x = 24 + col_w + 24

    draw.rounded_rectangle((left_x, 156, left_x + col_w, 202), radius=10, fill=(45, 20, 28), outline=(244, 63, 94), width=2)
    draw.text(
        (left_x + 20, 168),
        "[AVANT] MODÈLE DE BASE (poids d'origine)",
        fill=(254, 205, 211),
        font=font_h2,
    )

    draw.rounded_rectangle((right_x, 156, right_x + col_w, 202), radius=10, fill=(12, 52, 44), outline=(16, 185, 129), width=2)
    draw.text(
        (right_x + 20, 168),
        f"[APRÈS] {statut.upper()}",
        fill=(167, 243, 208),
        font=font_h2,
    )

    family_labels = {
        "owl": "Créature (hibou ailes déployées)",
        "bicycle": "Mécanique fine (vélo cargo)",
        "cathedral": "Architecture (cathédrale gothique)",
        "helmet": "Armure (casque ornementé)",
        "camera": "Optique (caméra vintage)",
    }

    row_y = 216
    row_h = 285
    if not pairs:
        draw.text(
            (left_x + 16, row_y + 12),
            f"Aucune paire d'audit avec rendus disponible : cas {NON_MESURE}s.",
            fill=(226, 232, 240),
            font=font_metric,
        )
    for idx, pair in enumerate(pairs):
        fam = pair["family"]
        title = f"Cas #{idx + 1} · {family_labels.get(fam, f'Famille {fam.capitalize()}')}"
        si_pct = _si_change_pct(pair)

        # Carte AVANT
        draw.rounded_rectangle((left_x, row_y, left_x + col_w, row_y + row_h), radius=12, fill=(17, 24, 39), outline=(71, 85, 105), width=1)
        draw.text((left_x + 16, row_y + 10), title, fill=(226, 232, 240), font=font_metric)
        panel_before = _compose_two_views(pair["base_views"], col_w - 32, row_h - 86)
        img.paste(panel_before, (left_x + 16, row_y + 36))
        draw.text(
            (left_x + 16, row_y + row_h - 42),
            f"Auto-intersections BVH : {_count_txt(pair['base_si'])}   |   Fragmentation UV : {_txt(pair['base_frag'], '.1f', ' %')}   |   CLIP 4-vues : {_txt(pair['base_clip'], '.1f')}",
            fill=(252, 165, 165),
            font=font_body,
        )
        draw.text(
            (left_x + 16, row_y + row_h - 22),
            "Rendu du modèle de base pour ce sujet et cette graine",
            fill=(148, 163, 184),
            font=_load_font(12, bold=False),
        )

        # Carte APRÈS
        draw.rounded_rectangle((right_x, row_y, right_x + col_w, row_y + row_h), radius=12, fill=(15, 29, 34), outline=(16, 185, 129), width=2)
        draw.text(
            (right_x + 16, row_y + 10),
            f"{title}  [ÉCART : {pair['gain_pts']:+.2f} pts]",
            fill=(110, 231, 183),
            font=font_metric,
        )
        panel_after = _compose_two_views(pair["cand_views"], col_w - 32, row_h - 86)
        img.paste(panel_after, (right_x + 16, row_y + 36))
        after_metrics = (
            f"Auto-intersections BVH : {_count_txt(pair['cand_si'])} ({_txt(si_pct, '+.1f', ' %')})   |   "
            f"Fragmentation UV : {_txt(pair['cand_frag'], '.1f', ' %')}   |   CLIP 4-vues : {_txt(pair['cand_clip'], '.1f')}"
        )
        draw.text(
            (right_x + 16, row_y + row_h - 42),
            after_metrics,
            fill=(110, 231, 183),
            font=_fit_font(draw, after_metrics, col_w - 32, 14, bold=True),
        )
        after_sub = (
            f"Meilleur écart parmi {pair['family_pairs_examined']} paire(s) examinée(s) pour cette famille "
            f"(cycle {pair['run_id']}) — cas non représentatif"
        )
        draw.text((right_x + 16, row_y + row_h - 22), after_sub, fill=(203, 213, 225),
                  font=_fit_font(draw, after_sub, col_w - 32, 12))

        row_y += row_h + 14

    # Bandeau récapitulatif inférieur : ce qui est mesuré, et ce qui ne l'est pas
    footer_y = 1112
    draw.rounded_rectangle((24, footer_y, width - 24, height - 20), radius=12, fill=(15, 23, 42), outline=(99, 102, 241), width=2)
    draw.text(
        (44, footer_y + 12),
        "CE QUE CE COMPARATIF MESURE, ET CE QU'IL NE MESURE PAS :",
        fill=(199, 210, 254),
        font=font_metric,
    )
    pillars = [
        # Plain ASCII arrow: the fallback bitmap font cannot draw "→".
        "1. " + _audit_sentence(score_base, score_renforce, gain_global, manifest_3d).replace("→", "->"),
        "2. Les cas affichés sont le meilleur écart de chaque famille d'objets : ils ne sont pas représentatifs du gain moyen.",
        f"3. Rigging et animation : {NON_MESURE}s. Aucun squelette n'est évalué par cet audit ni dessiné sur ces rendus.",
        f"4. Statut : {statut}. "
        + ("L'adaptateur est inscrit au registre officiel après la porte de promotion." if promoted
           else "Le modèle de base reste servi tant qu'aucun adaptateur n'a franchi la porte de promotion."),
    ]
    for i, line in enumerate(pillars):
        draw.text((44, footer_y + 38 + i * 21), line, fill=(226, 232, 240), font=_fit_font(draw, line, width - 88, 13))

    # Sauvegarde aux emplacements clés
    out_paths = [
        ROOT / "AVANT_APRES_3D_COMPARAISON.png",
        ROOT / "modele" / "renforce" / "3d" / "AVANT_APRES_3D_COMPARAISON.png",
    ]
    if BUREAU_STUDIO_DIR.parent.is_dir():
        BUREAU_STUDIO_DIR.mkdir(parents=True, exist_ok=True)
        out_paths.append(BUREAU_STUDIO_DIR / "AVANT_APRES_3D_COMPARAISON.png")

    for idx, p in enumerate(out_paths):
        p.parent.mkdir(parents=True, exist_ok=True)
        if idx == 0:
            img.save(p, format="PNG", optimize=True)
        else:
            shutil.copy2(out_paths[0], p)

    # Génération du rapport Markdown simple et détaillé
    md_content = _build_markdown_report(score_base, score_renforce, gain_global, pairs, status_data, manifest_3d,
                                        promoted=promoted)
    md_paths = [
        ROOT / "BILAN_AVANT_APRES_ET_GAINS.md",
        ROOT / "modele" / "renforce" / "3d" / "BILAN_AVANT_APRES_ET_GAINS.md",
    ]
    if BUREAU_STUDIO_DIR.is_dir():
        md_paths.append(BUREAU_STUDIO_DIR / "BILAN_AVANT_APRES_ET_GAINS.md")

    for p in md_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md_content, encoding="utf-8")

    return {
        "image_path": str(out_paths[0]),
        "desktop_image_path": str(BUREAU_STUDIO_DIR / "AVANT_APRES_3D_COMPARAISON.png"),
        "markdown_path": str(md_paths[0]),
        "desktop_markdown_path": str(BUREAU_STUDIO_DIR / "BILAN_AVANT_APRES_ET_GAINS.md"),
        # None means "not measured"; these keys never carry a substituted figure.
        "score_base_100": None if score_base is None else round(score_base, 3),
        "score_renforce_100": None if score_renforce is None else round(score_renforce, 3),
        "gain_points_100": None if gain_global is None else round(gain_global, 3),
        "promoted": promoted,
        "cases_count": len(pairs),
    }


def _build_markdown_report(
    score_base: float | None,
    score_renforce: float | None,
    gain_global: float | None,
    pairs: list[dict[str, Any]],
    status_data: dict[str, Any],
    manifest_3d: dict[str, Any],
    promoted: bool = False,
) -> str:
    run_id = status_data.get("run_id") or manifest_3d.get("run_id") or "3d-active"
    phase = status_data.get("phase") or "idle"
    epoch = status_data.get("epoch")
    val_loss = status_data.get("validation_loss")
    statut = _statut(manifest_3d, promoted)

    note = [_audit_sentence(score_base, score_renforce, gain_global, manifest_3d)]
    note.append(f"Statut : **{statut}**" + ("." if promoted else " ; le modèle de base reste servi."))
    if pairs:
        note.append("Les exemples détaillés plus bas sont le meilleur cas de chaque famille, pas des cas typiques.")
    note.append("Les lignes « Rigging » et « Compréhension » décrivent des étapes du pipeline, pas des gains mesurés.")

    if score_base is None or score_renforce is None:
        composite_row = (f"| **Note Globale de Qualité 3D** | `{NON_MESURE}` | **`{NON_MESURE}`** | "
                         f"**{NON_MESURE}** : aucun score d'audit dans le manifeste |")
    else:
        best_case = f" ; meilleur cas affiché : **`{max(p['gain_pts'] for p in pairs):+.2f} pts`**" if pairs else ""
        composite_row = (f"| **Note Globale de Qualité 3D** | `{score_base:.2f} / 100` | **`{score_renforce:.2f} / 100`** | "
                         f"**`{_txt(gain_global, '+.3f', ' pt')}`** en moyenne{best_case} |")
    # Ranges are computed from the pairs loaded for this report, never written by hand.
    if pairs:
        si_changes = [change for change in (_si_change_pct(p) for p in pairs) if change is not None]
        scope = f"sur les {len(pairs)} cas affichés (le meilleur de chaque famille, non représentatif de la moyenne)"
        pct = lambda value: f"`{value:+.1f} %`"
        frag = lambda value: f"`{value:.1f} %`"
        count = lambda value: f"`{_count_txt(value)}`"
        si_row = (f"| **Propreté Géométrique (Auto-Intersections)** | {_range_txt([p['base_si'] for p in pairs], count)} | "
                  f"**{_range_txt([p['cand_si'] for p in pairs], count)}** | {_range_txt(si_changes, pct)} {scope} |")
        frag_row = (f"| **Soudure du Maillage (Fragmentation UV)** | {_range_txt([p['base_frag'] for p in pairs], frag)} | "
                    f"**{_range_txt([p['cand_frag'] for p in pairs], frag)}** | Valeurs relevées {scope} |")
    else:
        si_row = (f"| **Propreté Géométrique (Auto-Intersections)** | {NON_MESURE} | {NON_MESURE} | "
                  f"{NON_MESURE} : aucune paire d'audit chargée |")
        frag_row = (f"| **Soudure du Maillage (Fragmentation UV)** | {NON_MESURE} | {NON_MESURE} | "
                    f"{NON_MESURE} : aucune paire d'audit chargée |")

    lines = [
        "# 🏆 Bilan Visuel Avant / Après & Note d'Amélioration 3D + AGI",
        "",
        "> **Lecture de ce bilan.** " + " ".join(note),
        "",
        "![Comparatif Visuel Avant / Après 3D (mesures d'audit)](AVANT_APRES_3D_COMPARAISON.png)",
        "",
        "---",
        "",
        "## 1. Résumé Ultra-Simple à Comprendre (En 30 Secondes)",
        "",
        f"| Indicateur Clé | 🛡️ AVANT (Modèle de Base Intouchable) | ⚡ APRÈS ({statut}) | 📈 Écart mesuré |",
        "| :--- | :---: | :---: | :--- |",
        composite_row,
        si_row,
        frag_row,
        f"| **Rigging & Animation d'un Personnage 3D** | {NON_MESURE} | {NON_MESURE} | Étape du pipeline (préparation automatique du rig d'un personnage ou d'une créature), **pas un gain mesuré** : aucune évaluation de rigging n'est faite par cet audit |",
        f"| **Compréhension Animé vs Réel & Anglais** | {NON_MESURE} | {NON_MESURE} | Fonction du pipeline (ontologie de style, traduction **FR $\\rightarrow$ EN**), **non mesurée** par cet audit |",
        "| **Sécurité du Modèle de Base** | Poids d'origine | Inchangés par conception | L'entraînement n'écrit que des adaptateurs, stockés à part dans `modele/renforce/3d/` et servis seulement s'ils ont **franchi la porte de promotion** (registre officiel) ; ce rapport ne revérifie pas l'empreinte de la base |",
        "",
        "---",
        "",
        f"## 2. Détail des Écarts sur {len(pairs)} Exemple(s) — le Meilleur Cas de Chaque Famille, pas un Cas Typique",
        "",
    ]
    if not pairs:
        lines.extend([f"Aucune paire d'audit avec rendus disponible : exemples {NON_MESURE}s.", ""])

    for idx, pair in enumerate(pairs, start=1):
        lines.extend([
            f"### Exemple #{idx} : `{pair['eval_name']}` — *{pair['prompt']}*",
            f"- **Provenance** : cycle `{pair['run_id']}` ; meilleur écart parmi {pair['family_pairs_examined']} paire(s) examinée(s) pour la famille `{pair['family']}`",
            f"- **Note Avant (Base Intouchable)** : `{pair['base_score_100']:.2f} / 100`",
            f"- **Note Après (candidat)** : **`{pair['cand_score_100']:.2f} / 100`** (**`{pair['gain_pts']:+.2f} points`**)",
            f"- **Triangles qui s'entrechoquent (Auto-intersections BVH)** : passe de `{_count_txt(pair['base_si'])}` à **`{_count_txt(pair['cand_si'])}`** (**`{_txt(_si_change_pct(pair), '+.1f', ' %')}`**)",
            f"- **Morceaux flottants / Fragmentation UV** : passe de `{_txt(pair['base_frag'], '.2f', ' %')}` à **`{_txt(pair['cand_frag'], '.2f', ' %')}`**",
            f"- **Fidélité Visuelle 360° (CLIP 4 vues)** : passe de `{_txt(pair['base_clip'])}` à **`{_txt(pair['cand_clip'])}`** (pire vue 360° : `{_txt(pair['base_worst'])}` $\\rightarrow$ **`{_txt(pair['cand_worst'])}`**)",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## 3. Fonctions du Pipeline Décrites (Non Mesurées dans cet Audit)",
        "",
        "*Cette section décrit ce que le pipeline est conçu pour faire. Aucune de ces fonctions n'a été évaluée par l'audit ci-dessus.*",
        "",
        "1. **Rigging & Animation Solo Automatique (`threeDIntent.ts` + `prompt_intelligence.py`)** :",
        "   - Tu n'as **plus jamais besoin d'écrire** *« rig-moi ceci »* ou *« ajoute un squelette »*.",
        "   - Dès qu'AuroraIA détecte un personnage, un humanoïde, un héros d'anime ou une créature vivante, il active de lui-même `motionReadiness = 'rig_candidate'` (`blender_rigify_autorig`, `weight_paint_check`, `action_test`) avec skinning géodésique Dual-Quaternion (`UniRig`) et verrouillage des appuis au sol (`Foot-Lock IK`).",
        "2. **Respect Intelligent de l'Ontologie Visuelle (Animé vs Photoréaliste vs Modification)** :",
        "   - **Personnage d'animé / manga / jeu** (*Goku, Vegeta, Luffy, Naruto…*) : rendu **directement dans son style animé/cel-shaded authentique**.",
        "   - **Demande explicite de textures humaines réelles** (*« Goku avec des textures de personne réelle / pores de peau »*) : conserve les vêtements, la coupe de cheveux et l'identité exacte du personnage tout en appliquant une micro-texture de peau photoréaliste 8K.",
        "   - **Sujet réel** : rendu photoréaliste optique natif.",
        "   - **Modification d'une création existante** : verrouille tout ce que tu n'as pas demandé de changer.",
        "3. **Expansion Cognitive FR $\\rightarrow$ EN Automatique** :",
        "   - Un humain écrit souvent 4 ou 5 mots en français (*« fais sangoku »* ou *« un dragon en 3D »*). Le **Directeur Cognitif** traduit et enrichit automatiquement les moteurs anglais (`FLUX.2-dev`, `TRELLIS.2-4B`) avec l'anatomie, la topologie propre et l'éclairage studio.",
        "",
        "---",
        "",
        "## 4. Comment Arrêter Proprement le Cycle à ton Réveil",
        "",
        f"- **Cycle Kaggle / Local supervisé** : `{run_id}` (phase observée : `{phase}`"
        + (f", époque `{epoch}`, val_loss `{val_loss}`" if epoch is not None else "")
        + ").",
        "- Pour **laisser le cycle en cours finir proprement son audit et mettre à jour ce rapport avant de s'arrêter**, tu as **3 moyens ultra-simples** :",
        "  1. **Sur le Bureau** : double-clique sur **`Arreter_En_Fin_De_Cycle.desktop`** dans le dossier `AuroraIA_Studio_&_Renforcement`.",
        "  2. **Dans le nouveau CLI (`jobia`)** : tape simplement **`/fin-cycle`** (et tape **`/avant-apres`** pour afficher ce bilan directement dans le terminal).",
        "  3. **Dans l'application AuroraIA** : clique sur le bouton ambre **`⏹ Fin de cycle`** en haut de l'écran.",
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    res = generate_before_after_visual_and_report()
    print(json.dumps(res, indent=2, ensure_ascii=False))
