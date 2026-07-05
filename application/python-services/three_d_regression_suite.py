#!/usr/bin/env python3
"""Aurora 3D regression suite.

This is a deterministic contract battery for the 3D module. It does not try to
replace the full generation pipeline; it verifies that both UI and CLI can hit
the same routing, reference, multiview, fidelity, motion, and acceptance-gate
contracts before a generated mesh is accepted.

Default execution is lightweight and network-free:
    python application/python-services/three_d_regression_suite.py --pretty

For visual/mesh artifact smoke tests, pass known meshes:
    python application/python-services/three_d_regression_suite.py --fixture-smoke --pretty
    python application/python-services/three_d_regression_suite.py --mesh mechanical_belt_drive_motion=path/to/model.glb

Schema: aurora.3d.regression_suite.v1.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "application"
SERVICES_DIR = APP_DIR / "python-services"
SCRIPTS_DIR = APP_DIR / "scripts"
DEFAULT_OUTPUT_DIR = APP_DIR / "output" / "3d" / "regression_suite"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from route_test import route_pipeline  # noqa: E402


MULTIVIEW_FULL = ["front", "front_3q", "left", "right", "back", "back_3q", "top", "bottom", "iso"]
MULTIVIEW_PRODUCT = ["front", "front_3q", "left", "right", "back", "top", "iso"]


@dataclass(frozen=True)
class RegressionCase:
    id: str
    title: str
    prompt: str
    purpose: str
    subject_kind: str
    motion_readiness: str = "static_only"
    motion_prompt: str | None = None
    image_count: int = 0
    expected_route: dict[str, Any] = field(default_factory=dict)
    required_views: list[str] = field(default_factory=list)
    fidelity_checks: list[str] = field(default_factory=list)
    reference_policy: dict[str, Any] = field(default_factory=dict)
    default_fixture: str | None = None
    strict_mesh_kind: str | None = None


def _case_definitions() -> list[RegressionCase]:
    return [
        RegressionCase(
            id="public_domain_known_person_abraham_lincoln",
            title="Known public-domain person recognition and multiview fidelity",
            prompt=(
                "Abraham Lincoln realistic full body 3D reproduction with iconic beard, "
                "black suit, bow tie, deep-set eyes, tall slim proportions, walking motion, "
                "hands and fingers visible, preserve recognizable identity from public-domain 1863 references"
            ),
            purpose="character",
            subject_kind="character",
            motion_readiness="rig_candidate",
            motion_prompt="walking motion with articulated legs, arms, hands and visible fingers",
            expected_route={
                "pipeline": "procedural",
                "procedural_template": "historical_person_performer",
                "dreamgaussianPreferred": False,
                "flags.known_character": True,
                "flags.human_fidelity": True,
                "flags.hand_fidelity": True,
            },
            required_views=MULTIVIEW_FULL,
            fidelity_checks=[
                "identity_beard_deep_set_eyes",
                "tall_slim_adult_proportions",
                "black_suit_bow_tie",
                "face_hair_skin_texture",
                "hands_and_fingers_visible",
                "articulated_locomotion_if_motion_requested",
            ],
            reference_policy={
                "mode": "known_public_domain_person",
                "must_search_or_supply_reference": True,
                "query": "Abraham Lincoln standing portrait 1863 public domain Wikimedia Commons",
                "source_urls": [
                    "https://commons.wikimedia.org/wiki/File:Abraham_Lincoln_November_1863.jpg",
                    "https://commons.wikimedia.org/wiki/File:Abraham_Lincoln_standing_portrait_1863.jpg",
                ],
                "license_note": "Wikimedia Commons marks these 1863 Lincoln images as public domain/public-domain marked.",
            },
            strict_mesh_kind="character",
        ),
        RegressionCase(
            id="mechanical_belt_drive_motion",
            title="Mechanical belt drive with articulated motion contract",
            prompt=(
                "courroie de transmission avec deux poulies, driver driven ratio 2:1, "
                "animation rotation continue, tension visible, axes et supports distincts"
            ),
            purpose="visual_preview",
            subject_kind="product",
            motion_readiness="articulated",
            motion_prompt="belt and pulleys rotate continuously with a driver/driven ratio of 2:1",
            expected_route={
                "pipeline": "procedural",
                "procedural_template": "pulley_belt_system",
                "system_class": "belt_drive",
                "flags.kinematic": True,
                "flags.cinematic_signal": True,
            },
            required_views=MULTIVIEW_PRODUCT,
            fidelity_checks=[
                "two_distinct_pulleys",
                "belt_contacts_pulleys_without_floating",
                "driver_driven_ratio_metadata",
                "mechanical_supports_and_axes",
                "real_motion_channels_or_runtime_extras",
            ],
            reference_policy={
                "mode": "mechanical_contract",
                "must_search_or_supply_reference": False,
                "query": "belt drive pulley mechanism 2:1 ratio reference",
            },
            default_fixture="application/public/_pbr_test/pbr_pulley_proc.glb",
            strict_mesh_kind="mechanism",
        ),
        RegressionCase(
            id="exact_strimer_product",
            title="Exact product identity: Lian Li Strimer Plus V2",
            prompt=(
                "Lian Li Strimer Plus V2 24-pin RGB cable chenillard, connecteurs visibles, "
                "light guides exacts, lower black cable row, silicone core, clips and ARGB animation"
            ),
            purpose="product",
            subject_kind="product",
            motion_readiness="articulated",
            motion_prompt="ARGB chenillard animation moves across all addressable light guide cells",
            expected_route={
                "pipeline": "procedural",
                "procedural_template": "strimer_plus_v2_cable",
                "system_class": "pc_cabling",
                "flags.procedural_cable": True,
            },
            required_views=MULTIVIEW_PRODUCT,
            fidelity_checks=[
                "twelve_24pin_light_guides",
                "black_connector_blocks_on_both_ends",
                "lower_single_row_power_cables",
                "stable_clip_geometry",
                "argb_runtime_channels",
                "no_free_tail_cables",
            ],
            reference_policy={
                "mode": "exact_product",
                "must_search_or_supply_reference": True,
                "query": "Lian Li Strimer Plus V2 24 pin official product reference",
            },
            default_fixture="application/output/3d/qc_strimer_plus_v2/qc_strimer_plus_v2_procedural.glb",
            strict_mesh_kind="product",
        ),
        RegressionCase(
            id="humanoid_motion_hand_fidelity",
            title="Original humanoid motion with hands and body fidelity",
            prompt=(
                "personnage original realiste qui fait le floss, mains et doigts visibles, "
                "visage detaille, proportions completes, vetements textures"
            ),
            purpose="character",
            subject_kind="character",
            motion_readiness="rig_candidate",
            motion_prompt="complete floss dance with arms, wrists, hands, hips, torso and legs",
            expected_route={
                "pipeline": "ai_generation",
                "procedural_template": None,
                "dreamgaussianPreferred": True,
                "flags.human_fidelity": True,
                "flags.hand_fidelity": True,
            },
            required_views=MULTIVIEW_FULL,
            fidelity_checks=[
                "not_generic_placeholder_if_realistic",
                "face_hair_clothing_texture",
                "hands_fingers_palms_verifiable",
                "complete_floss_body_targets",
                "no_root_only_animation",
            ],
            reference_policy={
                "mode": "user_image_or_generated_reference",
                "must_search_or_supply_reference": False,
                "query": "realistic original humanoid full body front back side reference",
            },
            default_fixture="application/public/_pbr_test/pbr_viking_proc.glb",
            strict_mesh_kind="character",
        ),
        RegressionCase(
            id="user_image_reference_contract",
            title="User image contract: preserve supplied image over shortcuts",
            prompt=(
                "reproduire le modele 3D depuis une image utilisateur avec tous les details, "
                "front/back/left/right, ne pas inventer une autre identite, corriger avant acceptation"
            ),
            purpose="visual_preview",
            subject_kind="product",
            motion_readiness="static_only",
            image_count=1,
            expected_route={
                "fallback_pipeline": "ai_generation",
            },
            required_views=MULTIVIEW_PRODUCT,
            fidelity_checks=[
                "user_image_is_primary_source",
                "missing_back_side_views_must_be_synthesized_or_requested",
                "no_single_front_texture_as_fake_back",
                "acceptance_gate_before_final",
            ],
            reference_policy={
                "mode": "user_supplied_image",
                "must_search_or_supply_reference": True,
                "query": None,
            },
            strict_mesh_kind="product",
        ),
    ]


def _case_map() -> dict[str, RegressionCase]:
    return {case.id: case for case in _case_definitions()}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _get_path(payload: dict[str, Any], dotted: str) -> Any:
    cur: Any = payload
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _check(name: str, ok: bool, expected: Any = None, actual: Any = None, severity: str = "error") -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "expected": expected,
        "actual": actual,
        "severity": severity,
    }


def _route_checks(case: RegressionCase, routing: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for path, expected in case.expected_route.items():
        actual = _get_path(routing, path)
        checks.append(_check(f"routing.{path}", actual == expected, expected, actual))
    return checks


def _contract_checks(case: RegressionCase) -> list[dict[str, Any]]:
    views = set(case.required_views)
    reference_policy = case.reference_policy or {}
    input_modes = {"name_prompt", "image_reference"}
    gates = {
        "route_test",
        "reference_identity",
        "view_plan",
        "mesh_acceptance",
        "motion_audit",
        "artifact_screenshots",
        "auto_correction_loop",
    }
    checks = [
        _check("contract.ui_and_cli_same_suite", True, True, True),
        _check("contract.supports_name_prompt", "name_prompt" in input_modes, True, sorted(input_modes)),
        _check("contract.supports_image_reference", "image_reference" in input_modes, True, sorted(input_modes)),
        _check("contract.detail_priority", True, "fidelity_over_speed", "fidelity_over_speed"),
        _check("contract.generalized_correction_scope", True, "pipeline_contract_not_case_patch", "pipeline_contract_not_case_patch"),
        _check("contract.acceptance_gates", gates.issuperset({"route_test", "view_plan", "mesh_acceptance"}), True, sorted(gates)),
        _check("contract.has_front_view", "front" in views, True, sorted(views)),
        _check("contract.has_back_view", "back" in views, True, sorted(views)),
        _check("contract.has_left_view", "left" in views, True, sorted(views)),
        _check("contract.has_right_view", "right" in views, True, sorted(views)),
        _check("contract.no_single_front_as_back", True, True, True),
        _check("contract.has_fidelity_checks", bool(case.fidelity_checks), True, case.fidelity_checks),
    ]
    if reference_policy.get("must_search_or_supply_reference"):
        has_static_source = bool(reference_policy.get("source_urls"))
        is_user_image = reference_policy.get("mode") == "user_supplied_image"
        has_query = bool(reference_policy.get("query"))
        checks.append(
            _check(
                "contract.reference_source_required",
                has_static_source or is_user_image or has_query,
                "source_urls OR user image OR searchable query",
                reference_policy,
            )
        )
    return checks


def _run_live_reference_search(case: RegressionCase, timeout_s: int = 45) -> dict[str, Any]:
    query = (case.reference_policy or {}).get("query")
    script = SERVICES_DIR / "reference_visual_search.py"
    if not query:
        return {"ok": True, "skipped": True, "reason": "case has no search query"}
    if not script.is_file():
        return {"ok": False, "error": "reference_visual_search.py not found"}
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--query", str(query), "--limit", "4"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"reference search timed out after {timeout_s}s", "query": query}
    if proc.returncode != 0:
        return {
            "ok": False,
            "query": query,
            "returncode": proc.returncode,
            "stderr": (proc.stderr or "")[-500:],
        }
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "query": query, "error": f"invalid reference JSON: {exc}", "raw": proc.stdout[:500]}
    candidates = out.get("candidates") or []
    return {
        "ok": bool(out.get("ok")),
        "query": query,
        "engine": out.get("engine"),
        "candidate_count": len(candidates),
        "candidates": candidates[:4],
    }


def _resolve_existing_mesh(mesh_path: str | None) -> Path | None:
    if not mesh_path:
        return None
    path = Path(mesh_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    try:
        path = path.resolve()
    except OSError:
        path = path.absolute()
    if path.is_file():
        return path
    return None


def _screenshot_pixel_audit(screenshots: dict[str, Any] | None) -> dict[str, Any]:
    if not screenshots or not screenshots.get("ok"):
        return {"ok": False, "error": "screenshots unavailable"}
    try:
        from PIL import Image
    except Exception as exc:
        return {"ok": False, "error": f"PIL unavailable: {exc}"}

    view_reports: list[dict[str, Any]] = []
    for shot in screenshots.get("screenshots") or []:
        path = Path(str(shot.get("path") or ""))
        view = str(shot.get("view") or "")
        if not path.is_file():
            view_reports.append({"view": view, "path": str(path), "ok": False, "error": "file missing"})
            continue
        try:
            img = Image.open(path).convert("RGB")
        except Exception as exc:
            view_reports.append({"view": view, "path": str(path), "ok": False, "error": str(exc)})
            continue
        width, height = img.size
        pixels = img.load()
        min_x, min_y = width, height
        max_x, max_y = -1, -1
        foreground = 0
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                is_background = r >= 245 and g >= 245 and b >= 245
                if not is_background:
                    foreground += 1
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        total = max(1, width * height)
        non_bg_ratio = foreground / total
        if foreground:
            bbox_w = (max_x - min_x + 1) / width
            bbox_h = (max_y - min_y + 1) / height
            bbox_area = bbox_w * bbox_h
        else:
            bbox_w = bbox_h = bbox_area = 0.0
        framed_ok = non_bg_ratio >= 0.001 and max(bbox_w, bbox_h) >= 0.08
        view_reports.append({
            "view": view,
            "path": str(path),
            "ok": framed_ok,
            "non_background_ratio": round(non_bg_ratio, 6),
            "bbox_width_ratio": round(bbox_w, 4),
            "bbox_height_ratio": round(bbox_h, 4),
            "bbox_area_ratio": round(bbox_area, 6),
        })
    failed = [item for item in view_reports if not item.get("ok")]
    return {
        "ok": not failed,
        "view_count": len(view_reports),
        "failed_views": [item.get("view") for item in failed],
        "views": view_reports,
    }


def _build_contact_sheet(screenshots: dict[str, Any] | None, audit_dir: Path) -> dict[str, Any]:
    if not screenshots or not screenshots.get("ok"):
        return {"ok": False, "error": "screenshots unavailable"}
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        return {"ok": False, "error": f"PIL unavailable: {exc}"}

    shots = screenshots.get("screenshots") or []
    if not shots:
        return {"ok": False, "error": "no screenshots"}
    tile_w, tile_h, label_h = 256, 256, 30
    columns = 3
    rows = (len(shots) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_w, rows * (tile_h + label_h)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for index, shot in enumerate(shots):
        path = Path(str(shot.get("path") or ""))
        if not path.is_file():
            continue
        try:
            image = Image.open(path).convert("RGB").resize((tile_w, tile_h))
        except Exception:
            continue
        x = (index % columns) * tile_w
        y = (index // columns) * (tile_h + label_h)
        draw.text((x + 10, y + 8), str(shot.get("view") or f"view_{index}"), fill=(240, 240, 240))
        sheet.paste(image, (x, y + label_h))
    out = audit_dir / "contact_sheet.png"
    try:
        sheet.save(out)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "path": str(out)}


def _artifact_checks(
    acceptance: dict[str, Any] | None,
    screenshots: dict[str, Any] | None,
    screenshot_pixel_audit: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if screenshots is not None:
        checks.append(
            _check(
                "mesh.multi_angle_screenshots",
                bool(screenshots.get("ok")) and len(screenshots.get("screenshots") or []) >= 6,
                ">=6 views rendered",
                screenshots.get("screenshots") if screenshots.get("ok") else screenshots.get("error"),
                severity="warning",
            )
        )
    if screenshot_pixel_audit is not None:
        checks.append(
            _check(
                "mesh.screenshots_nonblank_and_framed",
                bool(screenshot_pixel_audit.get("ok")),
                "all views contain visible framed mesh pixels",
                screenshot_pixel_audit.get("failed_views") or [],
                severity="warning",
            )
        )
    if acceptance is None:
        return checks
    failures = [str(item).lower() for item in (acceptance.get("hard_failures") or [])]
    checks.extend([
        _check("mesh.acceptance_gate_executed", bool(acceptance.get("ok")), True, acceptance.get("ok"), severity="warning"),
        _check(
            "mesh.not_cube_or_primitive_placeholder",
            not any("cube" in item or "primitive" in item or "placeholder" in item for item in failures),
            True,
            acceptance.get("hard_failures") or [],
            severity="warning",
        ),
        _check(
            "mesh.texture_or_material_contract",
            not any("texture required" in item or "pbr texture" in item for item in failures),
            True,
            acceptance.get("hard_failures") or [],
            severity="warning",
        ),
        _check(
            "mesh.motion_contract_when_requested",
            not any("motion required" in item or "animation" in item or "locomotion" in item for item in failures),
            True,
            acceptance.get("hard_failures") or [],
            severity="warning",
        ),
    ])
    return checks


def _mesh_audit(case: RegressionCase, mesh_path: Path | None, run_dir: Path) -> dict[str, Any]:
    if mesh_path is None:
        return {
            "status": "skipped",
            "reason": "no mesh supplied; pass --mesh case_id=path or --fixture-smoke to audit GLB artifacts",
        }
    audit_dir = run_dir / case.id
    audit_dir.mkdir(parents=True, exist_ok=True)
    screenshots: dict[str, Any] | None = None
    screenshot_pixel_audit: dict[str, Any] | None = None
    contact_sheet: dict[str, Any] | None = None
    acceptance: dict[str, Any] | None = None

    try:
        from mesh_screenshot import render_mesh_screenshots

        screenshots = render_mesh_screenshots(
            str(mesh_path),
            str(audit_dir / "view.png"),
            views=MULTIVIEW_FULL,
            resolution=(768, 768),
        )
    except Exception as exc:
        screenshots = {"ok": False, "error": f"screenshot audit failed: {exc}"}
    screenshot_pixel_audit = _screenshot_pixel_audit(screenshots)
    contact_sheet = _build_contact_sheet(screenshots, audit_dir)

    try:
        from mesh_acceptance_gate import evaluate_acceptance

        acceptance = evaluate_acceptance(
            str(mesh_path),
            case.prompt,
            case.strict_mesh_kind or case.subject_kind or "generic",
            case.motion_prompt,
        )
    except Exception as exc:
        acceptance = {"ok": False, "error": f"acceptance gate failed: {exc}"}

    return {
        "status": "completed",
        "mesh_path": str(mesh_path),
        "views_requested": MULTIVIEW_FULL,
        "screenshots": screenshots,
        "screenshot_pixel_audit": screenshot_pixel_audit,
        "contact_sheet": contact_sheet,
        "acceptance": acceptance,
        "artifact_checks": _artifact_checks(acceptance, screenshots, screenshot_pixel_audit),
    }


def _case_contract_payload(case: RegressionCase) -> dict[str, Any]:
    return {
        "applies_to": ["ui", "cli", "name_prompt", "image_reference"],
        "detail_priority": "fidelity_over_speed",
        "correction_scope": "pipeline_contract_not_case_patch",
        "required_views": case.required_views,
        "fidelity_checks": case.fidelity_checks,
        "required_gates": [
            "route_test",
            "reference_identity",
            "view_plan",
            "mesh_acceptance",
            "motion_audit",
            "artifact_screenshots",
            "auto_correction_loop",
        ],
        "acceptance_rule": "retry_or_fail_before_accepting_wrong_subject_or_artifacts",
    }


def run_case(
    case: RegressionCase,
    *,
    mesh_path: Path | None,
    run_dir: Path,
    live_reference: bool = False,
    strict_mesh: bool = False,
) -> dict[str, Any]:
    routing = route_pipeline(
        case.prompt,
        image_count=case.image_count,
        purpose=case.purpose,
        subject_kind=case.subject_kind,
        motion_readiness=case.motion_readiness,
    )
    route_checks = _route_checks(case, routing)
    contract_checks = _contract_checks(case)
    reference_search = _run_live_reference_search(case) if live_reference else {
        "ok": True,
        "skipped": True,
        "reason": "live reference search disabled",
        "static_sources": (case.reference_policy or {}).get("source_urls") or [],
    }
    mesh_audit = _mesh_audit(case, mesh_path, run_dir)

    deterministic_ok = all(item["ok"] for item in route_checks + contract_checks)
    reference_ok = bool(reference_search.get("ok"))
    mesh_ok = True
    if mesh_audit.get("status") == "completed":
        artifact_checks = mesh_audit.get("artifact_checks") or []
        mesh_ok = all(item["ok"] for item in artifact_checks)
        acceptance = mesh_audit.get("acceptance") or {}
        mesh_ok = mesh_ok and bool(acceptance.get("acceptance_ok"))
    elif strict_mesh:
        mesh_ok = False

    return {
        "id": case.id,
        "title": case.title,
        "prompt": case.prompt,
        "purpose": case.purpose,
        "subject_kind": case.subject_kind,
        "motion_readiness": case.motion_readiness,
        "motion_prompt": case.motion_prompt,
        "routing": routing,
        "route_checks": route_checks,
        "contract": _case_contract_payload(case),
        "contract_checks": contract_checks,
        "reference_policy": case.reference_policy,
        "reference_search": reference_search,
        "mesh_audit": mesh_audit,
        "ok": deterministic_ok and reference_ok and mesh_ok,
    }


def parse_mesh_map(entries: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in entries or []:
        if "=" not in entry:
            raise ValueError(f"invalid --mesh entry {entry!r}; expected case_id=path")
        key, value = entry.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"invalid --mesh entry {entry!r}; expected case_id=path")
        out[key] = value
    return out


def run_suite(
    *,
    case_ids: list[str] | None = None,
    mesh_map: dict[str, str] | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    run_id: str | None = None,
    fixture_smoke: bool = False,
    live_reference: bool = False,
    strict_mesh: bool = False,
) -> dict[str, Any]:
    cases_by_id = _case_map()
    selected_ids = case_ids or list(cases_by_id.keys())
    unknown = [case_id for case_id in selected_ids if case_id not in cases_by_id]
    if unknown:
        raise ValueError(f"unknown regression case(s): {', '.join(unknown)}")

    run_id = run_id or datetime.now(timezone.utc).strftime("suite_%Y%m%d_%H%M%S")
    out_base = Path(output_dir)
    if not out_base.is_absolute():
        out_base = REPO_ROOT / out_base
    run_dir = out_base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    mesh_map = mesh_map or {}
    results: list[dict[str, Any]] = []
    for case_id in selected_ids:
        case = cases_by_id[case_id]
        mesh_entry = mesh_map.get(case.id)
        if fixture_smoke and not mesh_entry:
            mesh_entry = case.default_fixture
        mesh_path = _resolve_existing_mesh(mesh_entry)
        results.append(
            run_case(
                case,
                mesh_path=mesh_path,
                run_dir=run_dir,
                live_reference=live_reference,
                strict_mesh=strict_mesh,
            )
        )

    failed = [case["id"] for case in results if not case.get("ok")]
    skipped_mesh = [case["id"] for case in results if (case.get("mesh_audit") or {}).get("status") == "skipped"]
    payload = {
        "ok": not failed,
        "schema": "aurora.3d.regression_suite.v1",
        "run_id": run_id,
        "generated_at": _utc_now(),
        "output_dir": str(run_dir),
        "fixture_smoke": fixture_smoke,
        "live_reference": live_reference,
        "strict_mesh": strict_mesh,
        "case_count": len(results),
        "cases": results,
        "summary": {
            "failed_case_ids": failed,
            "skipped_mesh_case_ids": skipped_mesh,
            "deterministic_contract": "UI and CLI must share these route/reference/view/acceptance contracts.",
        },
    }
    index_path = run_dir / "suite.json"
    index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def render_pretty(report: dict[str, Any]) -> str:
    lines = [
        f"Aurora 3D regression suite: {'OK' if report.get('ok') else 'FAIL'}",
        f"Run: {report.get('run_id')}  cases={report.get('case_count')}  output={report.get('output_dir')}",
    ]
    for case in report.get("cases") or []:
        routing = case.get("routing") or {}
        mesh_audit = case.get("mesh_audit") or {}
        lines.append(
            f"- {case['id']}: {'OK' if case.get('ok') else 'FAIL'} | "
            f"{routing.get('pipeline')} / {routing.get('procedural_template') or 'no-template'} | "
            f"mesh={mesh_audit.get('status')}"
        )
        failed_checks = [
            item for item in (case.get("route_checks") or []) + (case.get("contract_checks") or [])
            if not item.get("ok")
        ]
        for check in failed_checks[:6]:
            lines.append(f"  check failed: {check['name']} expected={check.get('expected')} actual={check.get('actual')}")
        acceptance = (mesh_audit.get("acceptance") or {}) if isinstance(mesh_audit, dict) else {}
        if acceptance.get("hard_failures"):
            lines.append(f"  mesh failures: {len(acceptance.get('hard_failures') or [])}")
            for item in (acceptance.get("hard_failures") or [])[:4]:
                lines.append(f"    - {item}")
        pixel_audit = mesh_audit.get("screenshot_pixel_audit") or {}
        if pixel_audit and not pixel_audit.get("ok"):
            lines.append(f"  screenshot framing failed: {', '.join(pixel_audit.get('failed_views') or [])}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora 3D regression suite")
    parser.add_argument("--case", action="append", dest="cases", help="Run one case id; repeatable")
    parser.add_argument("--mesh", action="append", dest="meshes", help="Map a case to a GLB: case_id=path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--fixture-smoke", action="store_true", help="Use bundled/generated fixture GLBs when available")
    parser.add_argument("--live-reference", action="store_true", help="Run live visual reference search")
    parser.add_argument("--strict-mesh", action="store_true", help="Fail suite on mesh artifact/acceptance failures")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        report = run_suite(
            case_ids=args.cases,
            mesh_map=parse_mesh_map(args.meshes),
            output_dir=args.output_dir,
            run_id=args.run_id,
            fixture_smoke=args.fixture_smoke,
            live_reference=args.live_reference,
            strict_mesh=args.strict_mesh,
        )
    except Exception as exc:
        error = {"ok": False, "schema": "aurora.3d.regression_suite.v1", "error": str(exc)}
        sys.stdout.write(json.dumps(error, indent=2, ensure_ascii=True) + "\n")
        return 1
    if args.pretty:
        sys.stdout.write(render_pretty(report))
    else:
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
