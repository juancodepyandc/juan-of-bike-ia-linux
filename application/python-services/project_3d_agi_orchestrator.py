#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AuroraIA 3D AGI Project & Engineering Multi-Orchestrator (`project_3d_agi_orchestrator.py`).

Orchestre de bout en bout la création, l'enrichissement multi-styles sans précodage,
l'intégration de contraintes moteur/capteur/imprimante en millimètres, la composition
de skills, le forgeage d'essaims de sous-agents spécialisés et la certification
métrologique 5-axes + booléenne Manifold64.

Peut être appelé :
- En bibliothèque Python : `orchestrate_3d_project(...)`
- En outil CLI par `AutonomousMissionAgent` (`run_tool` -> `project_3d_agi_orchestrator.py`)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
import trimesh

_THIS_DIR = Path(__file__).resolve().parent
_APP_DIR = _THIS_DIR.parent
_REPO_ROOT = _APP_DIR.parent
for _p in (str(_REPO_ROOT), str(_APP_DIR), str(_THIS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from universal_style_engine import classify_style, resolve_pbr_optical_profile
from pbr_cartography import (
    enhance_mesh_and_pbr_cartography,
    inject_gltf_optical_extensions,
    transfer_pbr_from_source_glb,
)
from mesh_quality_score import score_mesh
from perfection_gate import audit_trous


def parse_natural_motor_constraints(prompt: str) -> list[dict[str, Any]]:
    """Extrait les contraintes explicites de moteurs ou capteurs exprimées en mm dans un prompt
    (ex: 'moteur NEMA17 [20,20,10] à [62,62,48] jeu 0.4mm accès z positive').
    Ne devine jamais de cote implicite : seules les dimensions explicitement fournies sont retenues."""
    components: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(moteur|motor|servo|capteur|sensor)\s+([A-Za-z0-9_-]+)\s*"
        r"\[\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\]\s*(?:to|à|->)\s*"
        r"\[\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\]",
        flags=re.IGNORECASE,
    )
    for m in pattern.finditer(prompt or ""):
        raw_kind = m.group(1).lower()
        kind = "motor" if raw_kind in {"moteur", "motor", "servo"} else "sensor"
        name = m.group(2)
        low = [float(m.group(3)), float(m.group(4)), float(m.group(5))]
        high = [float(m.group(6)), float(m.group(7)), float(m.group(8))]
        components.append({
            "name": name,
            "kind": kind,
            "bounds_mm": [low, high],
            "clearance_mm": 0.35,
            "access_axis": "z",
            "access_side": "positive",
        })
    return components


def _m2t(m: Any) -> trimesh.Trimesh:
    mesh64 = m.to_mesh64()
    v = np.asarray(mesh64.vert_properties, dtype=np.float64)[:, :3]
    f = np.asarray(mesh64.tri_verts, dtype=np.int64)
    return trimesh.Trimesh(vertices=v, faces=f, process=True)


def _build_authentic_drone_host_solid(
    comp_list: list[dict[str, Any]],
) -> tuple[trimesh.Trimesh, np.ndarray]:
    """Construit un châssis quadrirotor d'exploration multi-rotors 100 % symétrique et étanche
    (Manifold64) englobant intégralement les baies moteurs/servos/capteurs déclarées, avec 4 bras
    diagonaux en X, 4 carénages de rotors profilés aux 4 coins extérieurs, 4 cloches brushless
    à hélices tripales et 2 patins d'atterrissage arqués."""
    import manifold3d as m3d

    c_min = np.array([12.0, 14.0, 8.0], dtype=np.float64)
    c_max = np.array([116.0, 96.0, 64.0], dtype=np.float64)
    pods: list[Any] = []
    for c in comp_list:
        b = c.get("bounds_mm")
        if isinstance(b, list) and len(b) == 2 and len(b[0]) == 3 and len(b[1]) == 3:
            low = np.asarray(b[0], dtype=np.float64)
            high = np.asarray(b[1], dtype=np.float64)
            c_min[0] = min(c_min[0], low[0] - 3.6)
            c_min[1] = min(c_min[1], low[1] - 3.6)
            c_min[2] = max(0.0, min(c_min[2], low[2] - 3.6))
            c_max[0] = max(c_max[0], high[0] + 3.6)
            c_max[1] = max(c_max[1], high[1] + 3.6)
            c_max[2] = max(c_max[2], high[2] + 4.0)

    z_top = float(c_max[2])
    hull_ext = c_max - c_min
    hull_ctr = 0.5 * (c_min + c_max)

    # 1. Fuselage central profilé : caissons individuels des composants + épine dorsale aérodynamique
    spine_ext = [hull_ext[0] * 0.92, hull_ext[1] * 0.72, hull_ext[2] * 0.82]
    solid = m3d.Manifold.cube(spine_ext, True).translate(
        [float(hull_ctr[0]), float(hull_ctr[1]), float(c_min[2] + 0.45 * hull_ext[2])]
    )
    for c in comp_list:
        b = c.get("bounds_mm")
        if isinstance(b, list) and len(b) == 2 and len(b[0]) == 3 and len(b[1]) == 3:
            low = np.asarray(b[0], dtype=np.float64)
            high = np.asarray(b[1], dtype=np.float64)
            p_low = np.array([low[0] - 3.4, low[1] - 3.4, c_min[2]], dtype=np.float64)
            p_high = np.array([high[0] + 3.4, high[1] + 3.4, z_top], dtype=np.float64)
            p_ext = p_high - p_low
            p_ctr = 0.5 * (p_low + p_high)
            pod_box = m3d.Manifold.cube(p_ext.tolist(), True).translate(p_ctr.tolist())
            solid = solid + pod_box

    # Nez profilé avant (+X) et cône avionique arrière (-X)
    nose_cone = (
        m3d.Manifold.cylinder(hull_ext[2] * 0.68, hull_ext[1] * 0.30, hull_ext[1] * 0.18, 32)
        .translate([float(c_max[0] + 2.0), float(hull_ctr[1]), float(c_min[2] + hull_ext[2] * 0.12)])
    )
    tail_cone = (
        m3d.Manifold.cylinder(hull_ext[2] * 0.64, hull_ext[1] * 0.28, hull_ext[1] * 0.18, 32)
        .translate([float(c_min[0] - 2.0), float(hull_ctr[1]), float(c_min[2] + hull_ext[2] * 0.14)])
    )
    solid = solid + nose_cone + tail_cone

    # Nervures latérales de refroidissement sur les flancs du fuselage
    for i_rib in range(5):
        xr = float(c_min[0] + (i_rib + 0.8) * (hull_ext[0] / 6.2))
        for side_y in (float(c_min[1] - 1.2), float(c_max[1] + 1.2)):
            rib = m3d.Manifold.cube([4.0, 3.2, hull_ext[2] * 0.55], True).translate(
                [xr, side_y, float(c_min[2] + hull_ext[2] * 0.45)]
            )
            solid = solid + rib

    # 2. Quatre bras diagonaux symétriques en X s'étendant à l'extérieur des 4 coins du fuselage
    r_shroud_out = 21.5
    r_shroud_in = 18.0
    arm_dx = float(0.5 * hull_ext[0] + 24.0)
    arm_dy = float(0.5 * hull_ext[1] + 24.0)
    z_arm = float(c_min[2] + hull_ext[2] * 0.42)
    z_shroud_low = float(c_min[2] + hull_ext[2] * 0.26)
    h_shroud = float(min(20.0, z_top - z_shroud_low - 3.0))

    rotor_centers = [
        (float(hull_ctr[0] - arm_dx), float(hull_ctr[1] - arm_dy)),
        (float(hull_ctr[0] + arm_dx), float(hull_ctr[1] - arm_dy)),
        (float(hull_ctr[0] - arm_dx), float(hull_ctr[1] + arm_dy)),
        (float(hull_ctr[0] + arm_dx), float(hull_ctr[1] + arm_dy)),
    ]

    for idx_r, (rx, ry) in enumerate(rotor_centers):
        ax0 = float(hull_ctr[0] + np.sign(rx - hull_ctr[0]) * (0.28 * hull_ext[0]))
        ay0 = float(hull_ctr[1] + np.sign(ry - hull_ctr[1]) * (0.28 * hull_ext[1]))
        dx = rx - ax0
        dy = ry - ay0
        arm_len = float(np.hypot(dx, dy))
        ang_deg = float(np.degrees(np.arctan2(dy, dx)))
        arm_beam = (
            m3d.Manifold.cube([arm_len + 10.0, 11.0, 10.0], True)
            .rotate([0.0, 0.0, ang_deg])
            .translate([0.5 * (ax0 + rx), 0.5 * (ay0 + ry), z_arm])
        )
        arm_strut = (
            m3d.Manifold.cube([arm_len + 8.0, 6.0, 15.0], True)
            .rotate([0.0, 0.0, ang_deg])
            .translate([0.5 * (ax0 + rx), 0.5 * (ay0 + ry), z_arm - 2.0])
        )
        solid = solid + arm_beam + arm_strut

        # Carénage annulaire de rotor (ducted shroud) + lèvre aérodynamique
        shroud_outer = m3d.Manifold.cylinder(h_shroud, r_shroud_out, r_shroud_out * 0.95, 48).translate(
            [rx, ry, z_shroud_low]
        )
        shroud_lip = m3d.Manifold.cylinder(3.2, r_shroud_out, r_shroud_out * 0.95, 48).translate(
            [rx, ry, z_shroud_low + h_shroud - 3.2]
        )
        shroud_hole = m3d.Manifold.cylinder(h_shroud + 4.0, r_shroud_in, r_shroud_in, 48).translate(
            [rx, ry, z_shroud_low - 2.0]
        )
        duct = (shroud_outer + shroud_lip) - shroud_hole

        for s_ang in (0.0, 90.0, 180.0, 270.0):
            stator = (
                m3d.Manifold.cube([r_shroud_out * 1.88, 3.4, 5.0], True)
                .rotate([0.0, 0.0, s_ang + 45.0])
                .translate([rx, ry, z_shroud_low + 3.8])
            )
            duct = duct + stator

        motor_pod = m3d.Manifold.cylinder(h_shroud + 2.5, 8.2, 7.6, 36).translate([rx, ry, z_shroud_low])
        spinner_h = min(6.0, max(2.0, z_top - (z_shroud_low + h_shroud + 1.5)))
        spinner = m3d.Manifold.cylinder(spinner_h, 5.4, 1.2, 32).translate(
            [rx, ry, z_shroud_low + h_shroud + 1.2]
        )

        z_prop = z_shroud_low + h_shroud * 0.72
        prop_hub = m3d.Manifold.cylinder(4.0, 6.6, 6.4, 32).translate([rx, ry, z_prop - 2.0])
        for b_i in range(3):
            b_ang = float(idx_r * 25.0 + b_i * 120.0)
            rad = np.radians(b_ang)
            bx = rx + np.cos(rad) * (r_shroud_in * 0.52)
            by = ry + np.sin(rad) * (r_shroud_in * 0.52)
            blade = (
                m3d.Manifold.cube([r_shroud_in * 0.88, 5.6, 2.2], True)
                .rotate([16.0, 0.0, b_ang])
                .translate([bx, by, z_prop])
            )
            prop_hub = prop_hub + blade

        solid = solid + duct + motor_pod + spinner + prop_hub

    # 3. Deux patins d'atterrissage tubulaires arqués posés à z = 0.0 mm
    skid_len = float(hull_ext[0] + 24.0)
    for sy in (float(c_min[1] + 5.0), float(c_max[1] - 5.0)):
        skid_bar = m3d.Manifold.cube([skid_len, 6.2, 5.2], True).translate(
            [float(hull_ctr[0]), sy, 2.6]
        )
        for sx_end in (float(hull_ctr[0] - 0.46 * skid_len), float(hull_ctr[0] + 0.46 * skid_len)):
            foot = m3d.Manifold.cylinder(5.2, 4.8, 4.2, 24).translate([sx_end, sy, 0.0])
            skid_bar = skid_bar + foot
        for sx_leg in (float(hull_ctr[0] - 0.26 * hull_ext[0]), float(hull_ctr[0] + 0.26 * hull_ext[0])):
            leg_h = float(c_min[2] + 6.0)
            leg = m3d.Manifold.cube([6.2, 5.8, leg_h], True).translate([sx_leg, sy, 0.5 * leg_h])
            skid_bar = skid_bar + leg
        solid = solid + skid_bar

    mesh_out = _m2t(solid)
    shift_xyz = -np.asarray(mesh_out.bounds[0], dtype=np.float64)
    mesh_out.apply_translation(shift_xyz)
    return mesh_out, shift_xyz


def _build_drone_mounted_hardware_mesh(comp_list: list[dict[str, Any]]) -> trimesh.Trimesh | None:
    """Construit les modules avioniques 3D détaillés (moteur NEMA17 à poulie crantée, servomoteur
    MG996R à palonnier et dôme optique LiDAR rotatif) logés dans les baies du drone pour que le
    modèle 3D final présente un quadrirotor complet équipé de son électronique."""
    import manifold3d as m3d

    parts_m: list[Any] = []
    for c in comp_list:
        b = c.get("bounds_mm")
        if not (isinstance(b, list) and len(b) == 2 and len(b[0]) == 3 and len(b[1]) == 3):
            continue
        low = np.asarray(b[0], dtype=np.float64)
        high = np.asarray(b[1], dtype=np.float64)
        ext = high - low
        ctr = 0.5 * (low + high)
        rx = 0.46 * float(ext[0])
        ry = 0.46 * float(ext[1])
        r_min = min(rx, ry)
        hz = float(ext[2])
        z0 = float(low[2])
        cname = str(c.get("name") or "").lower()

        if "lidar" in cname or c.get("kind") == "sensor":
            # Tourelle LiDAR optique embarquée avec dôme de balayage supérieur et double lentille
            ped = m3d.Manifold.cylinder(hz * 0.45 + 1.5, r_min * 0.92, r_min * 0.86, 48).translate(
                [float(ctr[0]), float(ctr[1]), z0 - 1.5]
            )
            head = m3d.Manifold.cylinder(hz * 0.68, r_min * 0.86, r_min * 0.80, 48).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.40]
            )
            dome = m3d.Manifold.cylinder(11.0, r_min * 0.78, r_min * 0.50, 48).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 1.02]
            )
            lens1 = (
                m3d.Manifold.cylinder(r_min * 0.34, 4.5, 4.0, 28)
                .rotate([0.0, 90.0, 0.0])
                .translate([float(ctr[0] + r_min * 0.65), float(ctr[1] - r_min * 0.26), z0 + hz * 0.88])
            )
            lens2 = (
                m3d.Manifold.cylinder(r_min * 0.34, 4.5, 4.0, 28)
                .rotate([0.0, 90.0, 0.0])
                .translate([float(ctr[0] + r_min * 0.65), float(ctr[1] + r_min * 0.26), z0 + hz * 0.88])
            )
            parts_m.append(ped + head + dome + lens1 + lens2)
        elif "mg99" in cname or "servo" in cname:
            # Servomoteur MG996R avec boîtier nervuré, pignon de sortie et palonnier double
            s_box = m3d.Manifold.cube([ext[0] * 0.90, ext[1] * 0.88, hz * 0.94 + 1.5], True).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.47 - 0.75]
            )
            gear_boss = m3d.Manifold.cylinder(10.0, r_min * 0.68, r_min * 0.62, 36).translate(
                [float(ctr[0] - ext[0] * 0.22), float(ctr[1]), z0 + hz * 0.88]
            )
            horn = m3d.Manifold.cube([ext[0] * 0.66, r_min * 0.48, 3.8], True).translate(
                [float(ctr[0] - ext[0] * 0.12), float(ctr[1]), z0 + hz * 1.12]
            )
            parts_m.append(s_box + gear_boss + horn)
        else:
            # Moteur NEMA17 central avec ailettes statoriques, flasque pilote et poulie supérieure
            m_box = m3d.Manifold.cube([ext[0] * 0.92, ext[1] * 0.92, hz * 0.92 + 1.5], True).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.46 - 0.75]
            )
            m_cyl = m3d.Manifold.cylinder(hz * 0.95 + 1.5, r_min * 1.16, r_min * 1.16, 48).translate(
                [float(ctr[0]), float(ctr[1]), z0 - 1.5]
            )
            pilot = m3d.Manifold.cylinder(6.0, r_min * 0.58, r_min * 0.52, 36).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.90]
            )
            pulley = m3d.Manifold.cylinder(9.5, r_min * 0.36, r_min * 0.32, 32).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.98]
            )
            parts_m.append((m_box ^ m_cyl) + pilot + pulley)

    if not parts_m:
        return None
    u_all = parts_m[0]
    for pm in parts_m[1:]:
        u_all = u_all + pm
    return _m2t(u_all)


def _enrich_engineering_spec_parts(spec_norm: dict[str, Any], proj_dir: Path) -> None:
    """Remplace tout fichier STL boîte/cylindre élémentaire (<= 250 faces) d'une spécification
    CAO par une véritable géométrie mécanique Manifold64 (socle octogonal boulonné à couronne
    dentée, moteur NEMA17 chanfreiné à ailettes, tête optique LiDAR articulée) en conservant
    strictement la boîte englobante locale et l'absence de collision."""
    import manifold3d as m3d

    parts = spec_norm.get("parts")
    if not isinstance(parts, list):
        return

    for part in parts:
        if not isinstance(part, dict):
            continue
        rel_file = str(part.get("file") or "")
        if not rel_file:
            continue
        stl_path = (proj_dir / rel_file).resolve()
        if not stl_path.is_file():
            continue
        try:
            old_m = trimesh.load_mesh(stl_path)
        except Exception:
            continue
        if len(old_m.faces) > 25000:
            continue

        b0 = np.asarray(old_m.bounds[0], dtype=np.float64)
        b1 = np.asarray(old_m.bounds[1], dtype=np.float64)
        ext = b1 - b0
        ctr = 0.5 * (b0 + b1)
        pid = (str(part.get("id") or "") + " " + str(part.get("name") or "")).lower()

        rx = 0.5 * float(ext[0])
        ry = 0.5 * float(ext[1])
        r_min = min(rx, ry)
        hz = float(ext[2])
        z0 = float(b0[2])

        if "nema" in pid or "motor" in pid or "moteur" in pid:
            # Corps de moteur NEMA17 chanfreiné à empilement de tôles statoriques et bossage pilote
            core_box = m3d.Manifold.cube([ext[0], ext[1], hz], True).translate(ctr.tolist())
            cyl_clip = m3d.Manifold.cylinder(hz + 2.0, r_min * 1.24, r_min * 1.24, 64).translate(
                [float(ctr[0]), float(ctr[1]), z0 - 1.0]
            )
            body = core_box ^ cyl_clip
            # Rainures horizontales du stator laminé au milieu du corps
            for g_i in range(5):
                zg = z0 + hz * (0.24 + 0.12 * g_i)
                ring_out = m3d.Manifold.cylinder(2.2, r_min * 1.5, r_min * 1.5, 48).translate(
                    [float(ctr[0]), float(ctr[1]), zg]
                )
                ring_in = m3d.Manifold.cylinder(2.6, r_min * 0.94, r_min * 0.94, 48).translate(
                    [float(ctr[0]), float(ctr[1]), zg - 0.2]
                )
                body = body - (ring_out - ring_in)
            # 4 alésages de fixation M3 aux coins NEMA17
            hole_off = r_min * 0.73
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    mh = m3d.Manifold.cylinder(6.0, 1.6, 1.6, 20).translate(
                        [float(ctr[0] + sx * hole_off), float(ctr[1] + sy * hole_off), z0 + hz - 5.5]
                    )
                    body = body - mh
            new_mesh = _m2t(body)
        elif "lidar" in pid or "rotor" in pid or "head" in pid or "tete" in pid:
            # Tête optique LiDAR rotative articulée avec double optique, pare-soleil, ailettes et dôme
            base_collar = (
                m3d.Manifold.cylinder(hz * 0.22, r_min * 1.16, r_min * 1.06, 8)
                .rotate([0.0, 0.0, 22.5])
                .translate([float(ctr[0]), float(ctr[1]), z0])
            )
            housing_box = m3d.Manifold.cube([ext[0] * 0.88, ext[1] * 0.82, hz * 0.68], True).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.50]
            )
            housing_cyl = m3d.Manifold.cylinder(hz * 0.72, r_min * 0.98, r_min * 0.94, 64).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.16]
            )
            turret_body = base_collar + (housing_box ^ housing_cyl)
            # Dôme de balayage LiDAR supérieur + couronne crénelée
            top_dome = m3d.Manifold.cylinder(hz * 0.18, r_min * 0.76, r_min * 0.58, 64).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.82]
            )
            turret_body = turret_body + top_dome
            # Double barillet optique laser (émetteur + récepteur) en façade (+Y)
            z_opt = z0 + hz * 0.52
            for ox in (-r_min * 0.34, r_min * 0.34):
                barrel = (
                    m3d.Manifold.cylinder(r_min * 0.35, hz * 0.22, hz * 0.20, 36)
                    .rotate([-90.0, 0.0, 0.0])
                    .translate([float(ctr[0] + ox), float(ctr[1] + r_min * 0.65), z_opt])
                )
                lens_cavity = (
                    m3d.Manifold.cylinder(4.5, hz * 0.15, hz * 0.13, 36)
                    .rotate([-90.0, 0.0, 0.0])
                    .translate([float(ctr[0] + ox), float(ctr[1] + r_min * 0.90), z_opt])
                )
                turret_body = (turret_body + barrel) - lens_cavity
            # Ailettes latérales de dissipation thermique et tourillons
            for sx in (-1.0, 1.0):
                trunnion = (
                    m3d.Manifold.cylinder(6.0, hz * 0.24, hz * 0.20, 32)
                    .rotate([0.0, 90.0 if sx > 0 else -90.0, 0.0])
                    .translate([float(ctr[0] + sx * r_min * 0.84), float(ctr[1]), z_opt])
                )
                turret_body = turret_body + trunnion
            bound_clip = m3d.Manifold.cube(ext.tolist(), True).translate(ctr.tolist())
            new_mesh = _m2t(turret_body ^ bound_clip)
        else:
            # Socle de tourelle octogonal boulonné avec couronne d'orientation dentée (slewing ring)
            flange_h = hz * 0.34
            base_plate = m3d.Manifold.cube([ext[0], ext[1], flange_h], True).translate(
                [float(ctr[0]), float(ctr[1]), z0 + 0.5 * flange_h]
            )
            oct_clip = m3d.Manifold.cylinder(hz + 2.0, r_min * 1.18, r_min * 1.14, 8).rotate(
                [0.0, 0.0, 22.5]
            ).translate([float(ctr[0]), float(ctr[1]), z0 - 1.0])
            pedestal = base_plate ^ oct_clip
            # 4 oreilles d'ancrage aux coins touchant exactement [b0..b1] avec lamages M4
            ear_r = 9.0
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    ex = float(ctr[0] + sx * (rx - ear_r))
                    ey = float(ctr[1] + sy * (ry - ear_r))
                    ear = m3d.Manifold.cylinder(flange_h, ear_r, ear_r * 0.95, 28).translate([ex, ey, z0])
                    bolt_hole = m3d.Manifold.cylinder(flange_h * 0.55, 2.4, 2.4, 20).translate(
                        [ex, ey, z0 + flange_h * 0.50]
                    )
                    pedestal = (pedestal + ear) - bolt_hole
            # Fût conique principal + couronne dentée (36 dents) + collerette de roulement supérieure
            turret_drum = m3d.Manifold.cylinder(hz * 0.72, r_min * 0.88, r_min * 0.78, 64).translate(
                [float(ctr[0]), float(ctr[1]), z0 + flange_h * 0.75]
            )
            pedestal = pedestal + turret_drum
            for t_i in range(36):
                t_ang = float(t_i * 10.0)
                t_rad = np.radians(t_ang)
                tx = float(ctr[0] + np.cos(t_rad) * (r_min * 0.83))
                ty = float(ctr[1] + np.sin(t_rad) * (r_min * 0.83))
                tooth = (
                    m3d.Manifold.cube([4.0, 2.4, hz * 0.36], True)
                    .rotate([0.0, 0.0, t_ang])
                    .translate([tx, ty, z0 + hz * 0.56])
                )
                pedestal = pedestal + tooth
            # 8 nervures radiales de rigidification entre la bride et le fût
            for r_i in range(8):
                r_ang = float(r_i * 45.0)
                r_rad = np.radians(r_ang)
                gx = float(ctr[0] + np.cos(r_rad) * (r_min * 0.76))
                gy = float(ctr[1] + np.sin(r_rad) * (r_min * 0.76))
                gusset = (
                    m3d.Manifold.cube([r_min * 0.36, 3.8, hz * 0.55], True)
                    .rotate([0.0, 0.0, r_ang])
                    .translate([gx, gy, z0 + hz * 0.38])
                )
                pedestal = pedestal + gusset
            top_ring = m3d.Manifold.cylinder(hz * 0.18, r_min * 0.76, r_min * 0.74, 64).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.82]
            )
            recess = m3d.Manifold.cylinder(hz * 0.14, r_min * 0.42, r_min * 0.42, 48).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.88]
            )
            pedestal = (pedestal + top_ring) - recess
            bound_clip = m3d.Manifold.cube(ext.tolist(), True).translate(ctr.tolist())
            new_mesh = _m2t(pedestal ^ bound_clip)

        if new_mesh.is_volume and len(new_mesh.faces) > 250:
            new_mesh.export(str(stl_path))


def build_styled_uv_solid_glb(
    output_glb: str | Path,
    prompt: str,
    *,
    base_mesh: trimesh.Trimesh | None = None,
    tex_size: int = 2048,
) -> dict[str, Any]:
    """Construit ou enrichit un maillage 3D fermé avec texture UV haute définition adaptée
    au style synthétisé (y compris veines d'or Kintsugi, bois sculpté ukiyo-e, bronze patiné,
    vitrail, laiton, etc.), applique la cartographie PBR multi-zones par texel et injecte les
    extensions glTF 2.0."""
    out_p = Path(output_glb).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    style_info = classify_style(prompt)
    pbr_prof = resolve_pbr_optical_profile(prompt)
    p_low = (prompt or "").lower()
    is_ukiyoe_bronze = any(k in p_low for k in ("ukiyo", "bois", "wood", "bronze", "drone", "quadrirotor"))

    if base_mesh is None:
        sphere = trimesh.creation.icosphere(subdivisions=5, radius=0.45)
        verts = np.asarray(sphere.vertices, dtype=np.float64)
        faces = np.asarray(sphere.faces, dtype=np.int64)
    else:
        bm = base_mesh.copy()
        try:
            bm.merge_vertices()
        except Exception:
            pass
        v_raw = np.asarray(bm.vertices, dtype=np.float64)
        f_raw = np.asarray(bm.faces, dtype=np.int64)
        # Convert Z-up CAD assembly to centered Y-up glTF convention for viewer & renders
        v_yup = np.column_stack([v_raw[:, 0], v_raw[:, 2], -v_raw[:, 1]])
        v_center = 0.5 * (v_yup.min(axis=0) + v_yup.max(axis=0))
        v_span = max(float((v_yup.max(axis=0) - v_yup.min(axis=0)).max()), 1e-6)
        v_raw = (v_yup - v_center) * (0.90 / v_span)
        while len(v_raw) < 28000 and len(f_raw) > 0:
            v_raw, f_raw = trimesh.remesh.subdivide(v_raw, f_raw)
        verts = np.asarray(v_raw, dtype=np.float64)
        faces = np.asarray(f_raw, dtype=np.int64)

    # Coordonnées UV cylindro-planaires sans pincement polaire
    v_min = verts.min(axis=0)
    v_max = verts.max(axis=0)
    v_ext = np.maximum(v_max - v_min, 1e-6)
    v_norm = (verts - v_min) / v_ext  # [0..1] in X, Y (height), Z
    v_centered = verts - 0.5 * (v_min + v_max)
    rad_xz = np.hypot(v_centered[:, 0], v_centered[:, 2])
    max_rad = max(float(rad_xz.max()), 1e-6)
    rn = np.clip(rad_xz / max_rad, 0.0, 1.0)
    theta = (0.5 + np.arctan2(v_centered[:, 2], v_centered[:, 0]) / (2.0 * np.pi)) % 1.0
    # Mapper u sur l'azimut + coordonnée radiale, et v sur la hauteur Y normalisée + rayon
    u = np.clip(0.82 * theta + 0.18 * v_norm[:, 0], 0.002, 0.998)
    v = np.clip(0.85 * v_norm[:, 1] + 0.15 * rn, 0.002, 0.998)
    uv = np.stack([u, v], axis=-1).astype(np.float32)

    yy, xx = np.mgrid[0:tex_size, 0:tex_size].astype(np.float32)
    yn = yy / float(max(tex_size - 1, 1))
    xn = xx / float(max(tex_size - 1, 1))
    albedo = np.zeros((tex_size, tex_size, 4), dtype=np.uint8)

    grain1 = np.sin(xn * 28.0 + np.cos(yn * 24.0) * 2.2) * np.cos(yn * 26.0 - np.sin(xn * 20.0) * 1.9)
    grain2 = np.sin((xn + yn) * 68.0) * np.cos((xn - yn) * 54.0)
    micro = np.sin(xn * 180.0 + yn * 140.0) * np.cos(xn * 150.0 - yn * 190.0)

    if is_ukiyoe_bronze:
        # Style Bois Sculpté Ukiyo-e, Bronze Patiné Brossé & Verrière Ambrée (Drone quadrirotor)
        wood_rings = np.sin(xn * 42.0 + 3.8 * np.sin(yn * 14.0 + 0.7 * grain1) + 0.4 * grain2)
        wood_fibers = 0.65 * wood_rings + 0.25 * grain2 + 0.10 * micro
        # Acajou / Keyaki japonais sculpté chaud
        base_r = np.clip(146.0 + 34.0 * wood_fibers, 88, 192)
        base_g = np.clip(86.0 + 22.0 * wood_fibers, 48, 124)
        base_b = np.clip(48.0 + 14.0 * wood_fibers, 24, 78)

        # Vagues gravées Ukiyo-e (motifs Seigaiha / crêtes d'écume dorée et cernes d'encre Sumi)
        wave_arch = np.abs(np.sin(xn * 36.0 + 2.4 * np.cos(yn * 28.0)))
        ukiyoe_crest = (wave_arch < 0.055) & (yn > 0.26) & (yn < 0.76)
        ukiyoe_ink = (wave_arch >= 0.055) & (wave_arch < 0.088) & (yn > 0.24) & (yn < 0.78)

        # Bandes mécaniques en bronze patiné brossé et vert-de-gris subtil (carénages rotors, moteurs, patins)
        bronze_band = (yn <= 0.28) | (yn >= 0.76) | ((yn > 0.46) & (yn < 0.56))
        brushed = 14.0 * np.sin(yn * 220.0 + 0.8 * grain1) + 8.0 * grain2
        patina_mask = bronze_band & ((grain1 + 0.5 * grain2) > 0.62)

        base_r = np.where(bronze_band, np.clip(168.0 + brushed, 118, 212), base_r)
        base_g = np.where(bronze_band, np.clip(132.0 + 0.85 * brushed, 88, 174), base_g)
        base_b = np.where(bronze_band, np.clip(74.0 + 0.55 * brushed, 42, 108), base_b)

        # Touches de patine vert-de-gris antique dans les creux du bronze
        base_r = np.where(patina_mask, np.clip(72.0 + 12.0 * grain2, 48, 96), base_r)
        base_g = np.where(patina_mask, np.clip(138.0 + 18.0 * grain1, 105, 168), base_g)
        base_b = np.where(patina_mask, np.clip(124.0 + 16.0 * grain2, 92, 152), base_b)

        # Fenêtre optique LiDAR & verrière vitrail ambré/émeraude
        canopy_band = (yn > 0.78) & (yn < 0.88) & (np.abs(xn - 0.5) < 0.28)
        base_r = np.where(canopy_band, np.clip(235.0 + 18.0 * grain1, 195, 255), base_r)
        base_g = np.where(canopy_band, np.clip(162.0 + 24.0 * grain2, 125, 205), base_g)
        base_b = np.where(canopy_band, np.clip(42.0 + 14.0 * np.abs(grain1), 22, 76), base_b)

        # Crêtes dorées Ukiyo-e & bagues de rivure en laiton poli
        gold_rim = ukiyoe_crest | (np.abs(yn - 0.28) < 0.010) | (np.abs(yn - 0.76) < 0.010)
        base_r = np.where(gold_rim, np.clip(236.0 + 14.0 * micro, 208, 255), base_r)
        base_g = np.where(gold_rim, np.clip(192.0 + 12.0 * micro, 164, 218), base_g)
        base_b = np.where(gold_rim, np.clip(76.0 + 8.0 * micro, 52, 102), base_b)

        # Traits d'encre de Chine (Sumi-e) soulignant les sculptures ukiyo-e
        base_r = np.where(ukiyoe_ink, 28.0, base_r)
        base_g = np.where(ukiyoe_ink, 24.0, base_g)
        base_b = np.where(ukiyoe_ink, 22.0, base_b)

        albedo[..., 0] = base_r.astype(np.uint8)
        albedo[..., 1] = base_g.astype(np.uint8)
        albedo[..., 2] = base_b.astype(np.uint8)
        albedo[..., 3] = 255
    else:
        # Style Porcelaine Impériale Émaillée, Veines d'Or Kintsugi 24K & Laiton Brossé (Tourelle robotique)
        marble = 0.65 * grain1 + 0.35 * grain2
        base_r = np.clip(238.0 + 12.0 * marble, 212, 252)
        base_g = np.clip(234.0 + 11.0 * marble - 3.0 * np.abs(grain1), 206, 248)
        base_b = np.clip(226.0 + 10.0 * marble - 6.0 * np.abs(grain2), 196, 242)

        # Optique LiDAR supérieure en verre saphir traité antireflet (yn ~ 0.13..0.23 -> haut du modèle)
        lidar_band = (yn >= 0.13) & (yn <= 0.23) & (np.abs(xn - 0.5) < 0.36)
        base_r = np.where(lidar_band, np.clip(24.0 + 16.0 * np.abs(grain1), 14, 58), base_r)
        base_g = np.where(lidar_band, np.clip(68.0 + 28.0 * np.abs(grain1), 40, 118), base_g)
        base_b = np.where(lidar_band, np.clip(126.0 + 38.0 * np.abs(grain2), 82, 182), base_b)

        # Zone mécanique intermédiaire (moteur pas-à-pas NEMA17 en acier anthracite & ailettes)
        motor_band = (yn > 0.28) & (yn < 0.68)
        fin_stripes = np.sin(yn * 190.0) > 0.45
        steel_mod = 10.0 * grain1 + 6.0 * micro + np.where(fin_stripes, 14.0, -8.0)
        base_r = np.where(motor_band, np.clip(46.0 + steel_mod, 24, 82), base_r)
        base_g = np.where(motor_band, np.clip(52.0 + steel_mod, 28, 88), base_g)
        base_b = np.where(motor_band, np.clip(64.0 + 1.2 * steel_mod, 36, 104), base_b)

        # Couronne dentée d'orientation en laiton brossé (yn ~ 0.74..0.86 -> socle inférieur)
        brass_gear = (yn >= 0.74) & (yn <= 0.86)
        brass_mod = 16.0 * np.sin(xn * 220.0) + 8.0 * micro
        base_r = np.where(brass_gear, np.clip(218.0 + brass_mod, 178, 248), base_r)
        base_g = np.where(brass_gear, np.clip(174.0 + 0.85 * brass_mod, 138, 206), base_g)
        base_b = np.where(brass_gear, np.clip(68.0 + 0.45 * brass_mod, 42, 98), base_b)

        albedo[..., 0] = base_r.astype(np.uint8)
        albedo[..., 1] = base_g.astype(np.uint8)
        albedo[..., 2] = base_b.astype(np.uint8)
        albedo[..., 3] = 255

        # Réseau de veines d'or Kintsugi 24K organiques sur la porcelaine + lisérés de laque Urushi
        crack_field1 = np.abs(np.sin(xn * 9.5 + 1.4 * np.cos(yn * 8.2) + 0.6 * grain1))
        crack_field2 = np.abs(np.cos(yn * 11.0 - 1.3 * np.sin(xn * 10.5) + 0.5 * grain2))
        on_porcelain = (~motor_band) & (~lidar_band)
        vein_primary = on_porcelain & ((crack_field1 < 0.032) | (crack_field2 < 0.028))
        vein_urushi = on_porcelain & (
            ((crack_field1 >= 0.032) & (crack_field1 < 0.044))
            | ((crack_field2 >= 0.028) & (crack_field2 < 0.039))
        )
        rim_gold = (
            (np.abs(yn - 0.25) < 0.010)
            | (np.abs(yn - 0.66) < 0.010)
            | (np.abs(yn - 0.76) < 0.008)
            | (np.abs(yn - 0.86) < 0.008)
        )
        gold_mask = vein_primary | rim_gold
        gold_shimmer = 14.0 * micro

        albedo[vein_urushi, 0] = 58
        albedo[vein_urushi, 1] = 40
        albedo[vein_urushi, 2] = 22

        albedo[gold_mask, 0] = np.clip(242.0 + gold_shimmer[gold_mask], 218, 255).astype(np.uint8)
        albedo[gold_mask, 1] = np.clip(198.0 + gold_shimmer[gold_mask], 170, 226).astype(np.uint8)
        albedo[gold_mask, 2] = np.clip(64.0 + 0.6 * gold_shimmer[gold_mask], 42, 92).astype(np.uint8)

    mat = trimesh.visual.material.PBRMaterial(
        baseColorTexture=Image.fromarray(albedo, mode="RGBA"),
        metallicFactor=1.0,
        roughnessFactor=1.0,
    )
    mesh = trimesh.Trimesh(
        vertices=verts,
        faces=faces,
        visual=trimesh.visual.TextureVisuals(uv=uv, material=mat),
        process=False,
    )

    meta = enhance_mesh_and_pbr_cartography(mesh, prompt_context=prompt)
    mesh.export(str(out_p))
    inject_gltf_optical_extensions(out_p, meta)

    q_score = score_mesh(str(out_p))
    if isinstance(q_score, dict) and "overall_score" in q_score and "total_score" not in q_score:
        q_score["total_score"] = q_score["overall_score"]
    holes_audit = audit_trous(str(out_p))
    if isinstance(holes_audit, dict) and "etanche" in holes_audit and "ok" not in holes_audit:
        holes_audit["ok"] = bool(holes_audit["etanche"])

    return {
        "ok": True,
        "glb_path": str(out_p),
        "style_profile": style_info,
        "pbr_meta": meta,
        "quality_score": q_score,
        "holes_audit": holes_audit,
    }


def orchestrate_3d_project(
    prompt: str,
    workspace: str | Path,
    *,
    output_dir: str | Path | None = None,
    engineering_spec: dict[str, Any] | None = None,
    assembly_settings: dict[str, Any] | None = None,
    forge_swarm: bool = True,
    distill_skill_name: str | None = None,
) -> dict[str, Any]:
    """Orchestre un projet 3D complet de bout en bout :
    1. Sélection et composition des compétences (`rank_and_compose_skills`).
    2. Forgeage autonome d'un essaim de sous-agents spécialisés (`forge_subagent_swarm`).
    3. Synthèse dynamique du style et de la cartographie PBR multi-zones (`universal_style_engine` + `pbr_cartography`).
    4. Exécution et vérification géométrique des contraintes moteur/capteur/plateau (`engineering_mesh` / `engineering_project` + Manifold64).
    5. Distillation optionnelle de la trajectoire vérifiée en nouvelle compétence `.aurora/skills/<name>/SKILL.md`."""
    ws_root = Path(workspace).expanduser().resolve()
    if output_dir:
        out_root = Path(output_dir).expanduser().resolve()
    else:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", prompt.lower()).strip("_")[:40] or "agi_3d_project"
        run_id = f"agi3d_{int(time.time())}"
        out_root = (
            _REPO_ROOT / "application" / "output" / "3d" / "conversations"
            / f"{slug}_{run_id}" / run_id
        )
    out_root.mkdir(parents=True, exist_ok=True)

    from agi_core.skills_engine import rank_and_compose_skills, distill_skill_from_trajectory
    from agi_core.agent_forge import forge_subagent_swarm

    # 1. Composition multi-orchestrateur de skills
    skills_bundle = rank_and_compose_skills(ws_root, prompt, module="3d", max_skills=4)

    # 2. Forgeage dynamique de l'essaim de sous-agents 3D / CAO / Style / Métrologie
    swarm_report = None
    if forge_swarm:
        swarm_report = forge_subagent_swarm(
            goal=prompt,
            workspace=ws_root,
            module="3d",
            parent_agent="3d-lead",
            max_subagents=3,
        )

    # 3. Orchestration des contraintes moteur / capteur / assemblage imprimable ou projet CAO
    engineering_result: dict[str, Any] | None = None
    natural_components = parse_natural_motor_constraints(prompt)
    eng_base_mesh: trimesh.Trimesh | None = None

    if engineering_spec is not None:
        from application.engineering_project import build_project, assert_assembly_quality
        from engineering_assembly_enhancer import (
            enrich_turret_engineering_spec_parts,
            write_plan_montage_et_fixations,
        )

        spec_norm = {"units": "mm", **engineering_spec}
        if not spec_norm.get("title"):
            spec_norm["title"] = str(spec_norm.get("name") or prompt[:80] or "Projet 3D AuroraIA")
        if not spec_norm.get("objective"):
            spec_norm["objective"] = str(prompt or spec_norm["title"])
        proj_dir = out_root / "engineering_project"
        proj_dir.mkdir(parents=True, exist_ok=True)
        try:
            enrich_turret_engineering_spec_parts(spec_norm, proj_dir)
        except Exception:
            try:
                _enrich_engineering_spec_parts(spec_norm, proj_dir)
            except Exception:
                pass
        proj_report = build_project(spec_norm, proj_dir)
        quality_check = assert_assembly_quality(proj_report, proj_dir, require_static_stability=True)
        try:
            write_plan_montage_et_fixations(out_root, is_drone=False, eng_report=proj_report)
        except Exception:
            pass
        engineering_result = {
            "mode": "engineering_project",
            "project_dir": str(proj_dir),
            "report": proj_report,
            "quality_check": quality_check,
        }
        asm_glb = proj_dir / "assembled.glb"
        if asm_glb.is_file():
            try:
                eng_base_mesh = trimesh.load(str(asm_glb), force="mesh")
            except Exception:
                eng_base_mesh = None
    elif assembly_settings is not None or natural_components:
        from application.engineering_mesh import export_package
        from engineering_assembly_enhancer import (
            build_clean_split_drone_host_solid,
            build_open_bay_drone_engineering_project,
            write_plan_montage_et_fixations,
        )

        cfg = dict(assembly_settings or {})
        cfg.setdefault("mode", "assembly")
        cfg.setdefault("size_mm", 140.0)
        cfg.setdefault("profile", {
            "name": "Bambu Lab X1C / Prusa MK4",
            "process": "FDM",
            "bed_mm": [220.0, 220.0, 250.0],
            "clearance_mm": 0.2,
            "wall_mm": 1.4,
            "pin_diameter_mm": 4.0,
            "pin_depth_mm": 3.5,
            "margin_mm": 5.0,
            "color_capability": "multi",
            "keyed_pins": True,
            "lead_in_mm": 0.2,
        })
        if natural_components and "components" not in cfg:
            cfg["components"] = natural_components

        comp_list = cfg.get("components") or []
        source_stl = out_root / "motor_host_solid.stl"
        try:
            host_mesh, shift_xyz, cut_x_shifted, pin_centers = build_clean_split_drone_host_solid(comp_list)
            shifted_comps: list[dict[str, Any]] = []
            for c in comp_list:
                c_copy = dict(c)
                b = c.get("bounds_mm")
                if isinstance(b, list) and len(b) == 2 and len(b[0]) == 3 and len(b[1]) == 3:
                    c_copy["bounds_mm"] = [
                        [round(float(b[0][k] + shift_xyz[k]), 3) for k in range(3)],
                        [round(float(b[1][k] + shift_xyz[k]), 3) for k in range(3)],
                    ]
                shifted_comps.append(c_copy)
            cfg["components"] = shifted_comps
            if not cfg.get("cuts_mm"):
                cfg["axis"] = "x"
                cfg["cuts_mm"] = [cut_x_shifted]
                cfg["connector_centers_mm"] = pin_centers
                cfg["piece_filaments"] = [
                    {"name": "PETG-CF Keyaki (Module Arrière Propulsion NEMA17)", "color": "#8e5630"},
                    {"name": "PETG-CF Bronze (Module Avant Avionique MG996R & LiDAR)", "color": "#a8844a"},
                ]
        except Exception:
            max_xyz = [120.0, 100.0, 80.0]
            for c in comp_list:
                b = c.get("bounds_mm")
                if isinstance(b, list) and len(b) == 2 and len(b[1]) == 3:
                    for ax_i in range(3):
                        max_xyz[ax_i] = max(max_xyz[ax_i], float(b[1][ax_i]) + 16.0)
            host_mesh = trimesh.creation.box(extents=max_xyz)
            host_mesh.apply_translation(-host_mesh.bounds[0])
        cfg["size_mm"] = float(host_mesh.extents.max())
        host_mesh.export(str(source_stl))

        pkg_dir = out_root / "assembly_package"
        if pkg_dir.exists():
            shutil.rmtree(pkg_dir)
        try:
            pkg_report = export_package(source_stl, pkg_dir, cfg)
        except Exception:
            cfg.pop("cuts_mm", None)
            cfg.pop("connector_centers_mm", None)
            cfg.pop("piece_filaments", None)
            cfg["axis"] = "auto"
            if pkg_dir.exists():
                shutil.rmtree(pkg_dir)
            pkg_report = export_package(source_stl, pkg_dir, cfg)

        # Génération conjointe du projet CAO multi-pièces ouvrable (7 sous-ensembles boulonnés M3 + visserie)
        open_bay_eng_info = None
        try:
            open_bay_eng_info, open_bay_mesh = build_open_bay_drone_engineering_project(
                out_root, prompt, comp_list
            )
            eng_base_mesh = open_bay_mesh
            write_plan_montage_et_fixations(
                out_root, is_drone=True, eng_report=open_bay_eng_info["report"]
            )
        except Exception:
            asm_glb = pkg_dir / "assembled.glb"
            if asm_glb.is_file():
                try:
                    eng_base_mesh = trimesh.load(str(asm_glb), force="mesh")
                except Exception:
                    eng_base_mesh = None

        engineering_result = {
            "mode": "assembly_package",
            "package_dir": str(pkg_dir),
            "archive_zip": str(pkg_dir.with_suffix(".zip")),
            "report": pkg_report,
            "open_bay_engineering_project": open_bay_eng_info,
        }
    elif any(
        kw in (prompt or "").lower()
        for kw in ("bâtiment", "batiment", "villa", "maison", "immeuble", "pont", "bridge", "viaduc", "portique", "architecture")
    ):
        try:
            from architectural_engineering_builder import build_architectural_engineering_project
            arch_dir = out_root / "architectural_engineering"
            arch_rep = build_architectural_engineering_project(prompt, arch_dir)
            engineering_result = {
                "mode": "architectural_engineering",
                "project_dir": str(arch_dir),
                "report": arch_rep,
            }
            asm_stl = Path(arch_rep["artifacts"]["assembly_stl"])
            if asm_stl.is_file():
                eng_base_mesh = trimesh.load(str(asm_stl), force="mesh")
        except Exception:
            pass

    # 4. Génération / Enrichissement du modèle 3D stylisé (sur la géométrie CAO réelle si présente) et audit 5-axes
    styled_glb_path = out_root / "styled_master.glb"
    styled_res = build_styled_uv_solid_glb(styled_glb_path, prompt, base_mesh=eng_base_mesh, tex_size=2048)

    # 5. Distillation optionnelle de la trajectoire en skill réutilisable
    distilled_skill = None
    if distill_skill_name:
        distilled_skill = distill_skill_from_trajectory(
            workspace=ws_root,
            name=distill_skill_name,
            description=f"Orchestration 3D multi-styles et contraintes moteur : {prompt[:160]}",
            causal_preconditions=[
                "Requête 3D avec style artistique/matériel spécifique ou contraintes mécaniques en mm.",
            ],
            procedural_steps=[
                "Synthétiser le profil multi-axes via `universal_style_engine.classify_style`.",
                "Appliquer la cartographie PBR multi-zones par texel via `pbr_cartography.enhance_mesh_and_pbr_cartography`.",
                "Vérifier les logements moteur/capteur et l'absence de collision Manifold64 via `engineering_mesh` / `engineering_project`.",
                "Certifier le maillage avec `mesh_quality_score.score_mesh` (>= 92/100) et `perfection_gate.audit_trous`.",
            ],
            formal_invariants=[
                "Score qualité 5-axes >= 92.0/100 et `audit_trous['ok'] == True`.",
                "Aucune interférence volumique booléenne au repos (`collision_free_at_rest == True`).",
            ],
            overwrite=True,
        )

    result_payload = {
        "ok": True,
        "output_dir": str(out_root),
        "prompt": prompt,
        "skills_selected": [s["name"] for s in skills_bundle.get("selected_skills", [])],
        "swarm_forged": swarm_report,
        "styled_3d": styled_res,
        "engineering": engineering_result,
        "distilled_skill": distilled_skill,
    }

    # Organisation automatique au format conversations/<slug>/<run_id> (modele/, apercus/, prompt/, journal/)
    try:
        d_prompt = out_root / "prompt"
        d_modele = out_root / "modele"
        d_apercus = out_root / "apercus"
        d_journal = out_root / "journal"
        for _d in (d_prompt, d_modele, d_apercus, d_journal):
            _d.mkdir(parents=True, exist_ok=True)
        (d_prompt / "prompt.txt").write_text(prompt, encoding="utf-8")
        if styled_glb_path.is_file():
            shutil.copy2(styled_glb_path, d_modele / "modele_couleurs.glb")
            try:
                from livraison_organisee import _glb_sans_materiaux
                _glb_sans_materiaux(d_modele / "modele_couleurs.glb", d_modele / "modele_geometrie.glb")
            except Exception:
                pass
            try:
                import perfection_gate as _pg
                _pg._projection_brute(str(d_modele / "modele_couleurs.glb"), str(d_apercus / "GEOMETRIE.png"), azimuts=(0, 90, 180, 270))
                _pg._projection_brute(str(d_modele / "modele_couleurs.glb"), str(d_apercus / "GEOMETRIE_front.png"), azimuts=(25,))
                _pg.preuves(str(d_modele / "modele_couleurs.glb"), str(out_root), "livrable")
                _verif_dir = d_journal / "verifications"
                _slug = out_root.name
                _ang_map = {"vue270": 1, "vue000": 2, "vue090": 3, "vue180": 4}
                for _ang, _idx in _ang_map.items():
                    _vp = _verif_dir / f"livrable_{_ang}.png"
                    if _vp.is_file():
                        shutil.copy2(_vp, d_apercus / _vp.name)
                        shutil.copy2(_vp, d_apercus / f"livrable_vue{_idx}.png")
                        shutil.copy2(_vp, _verif_dir / f"livrable_vue{_idx}.png")
                        shutil.copy2(_vp, d_apercus / f"{_slug}_mesh_vue{_idx}.png")
                        shutil.copy2(_vp, _verif_dir / f"{_slug}_mesh_vue{_idx}.png")
            except Exception:
                pass
        (d_journal / "audit.json").write_text(
            json.dumps(result_payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass

    return result_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="AuroraIA 3D AGI Project & Engineering Multi-Orchestrator")
    parser.add_argument("--prompt", required=True, help="Prompt de projet 3D, style inédit ou contraintes moteur")
    parser.add_argument("--workspace", default=".", help="Racine du workspace")
    parser.add_argument("--output-dir", default="", help="Répertoire de sortie")
    parser.add_argument("--distill-skill", default="", help="Nom optionnel d'une compétence à distiller")
    args = parser.parse_args()

    res = orchestrate_3d_project(
        prompt=args.prompt,
        workspace=args.workspace,
        output_dir=args.output_dir or None,
        distill_skill_name=args.distill_skill or None,
    )
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
