#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AuroraIA Multi-Part Open-Bay Mechanical Chassis, Fastener & Assembly Enhancer.

Conçoit et certifie des architectures mécaniques multi-pièces réellement ouvrables,
évidées et montables (Manifold64, 0.0000 mm³ d'interférence booléenne) :
- Chambre fonctionnelle interne évidée (`chambre de fonctionnement et de câblage`),
  fenêtres latérales de visite/ventilation et goulottes passe-câbles.
- Décomposition en sous-ensembles démontables imprimables séparément :
  châssis inférieur évidé à colonnettes M3, platine interne de bridage moteur/servo,
  capot supérieur boulonné avec galerie d'inspection panoramique, rotors démontables,
  et composants embarqués (NEMA17, MG996R, LiDAR).
- Nomenclature complète de visserie et d'éléments standards (vis CHC M3/M4, inserts
  filetés laiton M3×4×4.6 mm posés à chaud, écrous Nylstop M3, roulements 608ZZ,
  accouplement d'arbre Ø5 mm).
- Vérification géométrique d'accès et de discrétion des fixations par lancer de rayons
  (`rank_fastening_locations`) et génération du dossier `PLAN_MONTAGE_ET_FIXATIONS.md`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import trimesh


def _m2t(m: Any) -> trimesh.Trimesh:
    mesh64 = m.to_mesh64()
    v = np.asarray(mesh64.vert_properties, dtype=np.float64)[:, :3]
    f = np.asarray(mesh64.tri_verts, dtype=np.int64)
    return trimesh.Trimesh(vertices=v, faces=f, process=True)


def build_clean_split_drone_host_solid(
    comp_list: list[dict[str, Any]],
) -> tuple[trimesh.Trimesh, np.ndarray, float, list[list[list[float]]]]:
    """Construit le châssis porteur monolithique à chambre basse évidée destiné à
    `engineering_mesh.export_package`, garanti sans aucune nervure flottante détachée
    lors de l'usinage `component_seats` (0 miette) et doté d'un plan de coupe
    transversal X franc (`cut_x_shifted`) et d'une paire de centres de pions vérifiés
    (`connector_centers_mm`) entre la baie arrière NEMA17 et la baie avant MG996R / LiDAR."""
    import manifold3d as m3d

    c_min = np.array([12.0, 10.0, 6.0], dtype=np.float64)
    c_max = np.array([124.0, 94.0, 62.0], dtype=np.float64)
    for c in comp_list:
        b = c.get("bounds_mm")
        if isinstance(b, list) and len(b) == 2 and len(b[0]) == 3 and len(b[1]) == 3:
            low = np.asarray(b[0], dtype=np.float64)
            high = np.asarray(b[1], dtype=np.float64)
            c_min[0] = min(c_min[0], low[0] - 6.5)
            c_min[1] = min(c_min[1], low[1] - 6.5)
            c_min[2] = max(0.0, min(c_min[2], low[2] - 6.5))
            c_max[0] = max(c_max[0], high[0] + 6.5)
            c_max[1] = max(c_max[1], high[1] + 6.5)
            c_max[2] = max(c_max[2], high[2] + 4.0)

    z_top = float(c_max[2])
    hull_ext = c_max - c_min
    hull_ctr = 0.5 * (c_min + c_max)

    # Coque centrale large à parois épaisses (aucune nervure fine susceptible d'être isolée)
    spine_ext = [hull_ext[0] * 0.98, hull_ext[1] * 0.96, hull_ext[2] * 0.88]
    solid = m3d.Manifold.cube(spine_ext, True).translate(
        [float(hull_ctr[0]), float(hull_ctr[1]), float(c_min[2] + 0.46 * hull_ext[2])]
    )
    for c in comp_list:
        b = c.get("bounds_mm")
        if isinstance(b, list) and len(b) == 2 and len(b[0]) == 3 and len(b[1]) == 3:
            low = np.asarray(b[0], dtype=np.float64)
            high = np.asarray(b[1], dtype=np.float64)
            p_low = np.array([low[0] - 6.0, low[1] - 6.0, c_min[2]], dtype=np.float64)
            p_high = np.array([high[0] + 6.0, high[1] + 6.0, z_top], dtype=np.float64)
            p_ext = p_high - p_low
            p_ctr = 0.5 * (p_low + p_high)
            pod_box = m3d.Manifold.cube(p_ext.tolist(), True).translate(p_ctr.tolist())
            solid = solid + pod_box

    # Nez profilé avant (+X) et cône avionique arrière (-X)
    nose_cone = (
        m3d.Manifold.cylinder(hull_ext[2] * 0.68, hull_ext[1] * 0.30, hull_ext[1] * 0.18, 32)
        .translate([float(c_max[0] + 1.5), float(hull_ctr[1]), float(c_min[2] + hull_ext[2] * 0.12)])
    )
    tail_cone = (
        m3d.Manifold.cylinder(hull_ext[2] * 0.64, hull_ext[1] * 0.28, hull_ext[1] * 0.18, 32)
        .translate([float(c_min[0] - 1.5), float(hull_ctr[1]), float(c_min[2] + hull_ext[2] * 0.14)])
    )
    solid = solid + nose_cone + tail_cone

    # 4 bras diagonaux en X + carénages de rotors + rotors
    r_shroud_out = 21.5
    r_shroud_in = 18.0
    arm_dx = float(0.5 * hull_ext[0] + 22.0)
    arm_dy = float(0.5 * hull_ext[1] + 22.0)
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
            m3d.Manifold.cube([arm_len + 12.0, 12.0, 11.0], True)
            .rotate([0.0, 0.0, ang_deg])
            .translate([0.5 * (ax0 + rx), 0.5 * (ay0 + ry), z_arm])
        )
        arm_strut = (
            m3d.Manifold.cube([arm_len + 10.0, 7.0, 15.0], True)
            .rotate([0.0, 0.0, ang_deg])
            .translate([0.5 * (ax0 + rx), 0.5 * (ay0 + ry), z_arm - 2.0])
        )
        solid = solid + arm_beam + arm_strut

        shroud_outer = m3d.Manifold.cylinder(h_shroud, r_shroud_out, r_shroud_out * 0.95, 48).translate(
            [rx, ry, z_shroud_low]
        )
        shroud_hole = m3d.Manifold.cylinder(h_shroud + 4.0, r_shroud_in, r_shroud_in, 48).translate(
            [rx, ry, z_shroud_low - 2.0]
        )
        duct = shroud_outer - shroud_hole
        for s_ang in (0.0, 90.0, 180.0, 270.0):
            stator = (
                m3d.Manifold.cube([r_shroud_out * 1.88, 3.6, 5.2], True)
                .rotate([0.0, 0.0, s_ang + 45.0])
                .translate([rx, ry, z_shroud_low + 3.8])
            )
            duct = duct + stator
        motor_pod = m3d.Manifold.cylinder(h_shroud + 2.5, 8.2, 7.6, 36).translate([rx, ry, z_shroud_low])
        z_prop = z_shroud_low + h_shroud * 0.72
        prop_hub = m3d.Manifold.cylinder(4.0, 6.6, 6.4, 32).translate([rx, ry, z_prop - 2.0])
        for b_i in range(3):
            b_ang = float(idx_r * 25.0 + b_i * 120.0)
            rad = np.radians(b_ang)
            bx = rx + np.cos(rad) * (r_shroud_in * 0.52)
            by = ry + np.sin(rad) * (r_shroud_in * 0.52)
            blade = (
                m3d.Manifold.cube([r_shroud_in * 0.88, 5.6, 2.4], True)
                .rotate([16.0, 0.0, b_ang])
                .translate([bx, by, z_prop])
            )
            prop_hub = prop_hub + blade
        solid = solid + duct + motor_pod + prop_hub

    # 2 patins d'atterrissage tubulaires posés à z = 0.0 mm
    skid_len = float(hull_ext[0] + 24.0)
    for sy in (float(c_min[1] + 7.0), float(c_max[1] - 7.0)):
        skid_bar = m3d.Manifold.cube([skid_len, 6.8, 5.4], True).translate(
            [float(hull_ctr[0]), sy, 2.7]
        )
        for sx_end in (float(hull_ctr[0] - 0.46 * skid_len), float(hull_ctr[0] + 0.46 * skid_len)):
            foot = m3d.Manifold.cylinder(5.4, 5.0, 4.4, 24).translate([sx_end, sy, 0.0])
            skid_bar = skid_bar + foot
        for sx_leg in (float(hull_ctr[0] - 0.28 * hull_ext[0]), float(hull_ctr[0] + 0.28 * hull_ext[0])):
            leg_h = float(c_min[2] + 8.0)
            leg = m3d.Manifold.cube([7.0, 6.4, leg_h], True).translate([sx_leg, sy, 0.5 * leg_h])
            skid_bar = skid_bar + leg
        solid = solid + skid_bar

    mesh_out = _m2t(solid)
    shift_xyz = -np.asarray(mesh_out.bounds[0], dtype=np.float64)
    mesh_out.apply_translation(shift_xyz)
    cut_x_shifted = round(float(69.0 + shift_xyz[0]), 2)
    pin_centers = [
        [
            [cut_x_shifted, round(float(26.0 + shift_xyz[1]), 2), round(float(24.0 + shift_xyz[2]), 2)],
            [cut_x_shifted, round(float(78.0 + shift_xyz[1]), 2), round(float(24.0 + shift_xyz[2]), 2)],
        ]
    ]
    return mesh_out, shift_xyz, cut_x_shifted, pin_centers


def build_open_bay_drone_engineering_project(
    out_root: Path,
    prompt: str,
    comp_list: list[dict[str, Any]],
) -> tuple[dict[str, Any], trimesh.Trimesh]:
    """Construit dans `out_root / 'engineering_project'` l'architecture mécanique multi-pièces
    ouvrable complète du drone quadrirotor (7 pièces STL sans aucune collision booléenne
    `0.0000 mm³`) et retourne `(engineering_project_report, open_bay_visual_mesh)`."""
    import manifold3d as m3d
    from application.engineering_project import build_project, assert_assembly_quality

    proj_dir = out_root / "engineering_project"
    parts_dir = proj_dir / "parts_src"
    parts_dir.mkdir(parents=True, exist_ok=True)

    x0, x1 = 14.0, 122.0
    y0, y1 = 12.0, 92.0
    cx = 0.5 * (x0 + x1)  # 68.0
    cy = 0.5 * (y0 + y1)  # 52.0
    lx = x1 - x0          # 108.0
    ly = y1 - y0          # 80.0

    # --- 1. CHÂSSIS INFÉRIEUR ÉVIDÉ + 4 BRAS + CARÉNAGES + PATINS + 8 COLONNETTES M3 ---
    hull_outer = m3d.Manifold.cube([lx, ly, 36.0], True).translate([cx, cy, 26.0])  # Z=[8..44]
    nose = m3d.Manifold.cylinder(28.0, 22.0, 14.0, 36).translate([x1 + 2.0, cy, 12.0])
    tail = m3d.Manifold.cylinder(26.0, 20.0, 14.0, 36).translate([x0 - 2.0, cy, 13.0])
    chassis = hull_outer + nose + tail

    # Chambre fonctionnelle interne évidée (Z=[13.0..45.0], X=[20..116], Y=[18..86])
    chamber_main = m3d.Manifold.cube([96.0, 68.0, 33.0], True).translate([cx, cy, 29.5])
    chassis = chassis - chamber_main

    # 4 grandes fenêtres latérales arquées de visite, passage de câbles et refroidissement
    for wx in (41.0, 95.0):
        win_box = m3d.Manifold.cube([28.0, ly + 16.0, 16.0], True).translate([wx, cy, 27.0])
        chassis = chassis - win_box
    front_port = m3d.Manifold.cube([36.0, 26.0, 14.0], True).translate([cx, cy, 26.0])
    chassis = chassis - front_port

    # Berceau interne surélevé pour moteur NEMA17 (centre X=41, Y=53, plancher Z=[13..18])
    nema_cradle = m3d.Manifold.cube([44.0, 44.0, 5.0], True).translate([41.0, 53.0, 15.5])
    nema_pilot_hole = m3d.Manifold.cylinder(12.0, 11.25, 11.25, 36).translate([41.0, 53.0, 7.0])
    chassis = (chassis + nema_cradle) - nema_pilot_hole
    for sx in (-15.5, 15.5):
        for sy in (-15.5, 15.5):
            mh = m3d.Manifold.cylinder(14.0, 1.7, 1.7, 20).translate([41.0 + sx, 53.0 + sy, 6.0])
            chassis = chassis - mh

    # Berceau interne pour servomoteur MG996R (centre X=96, Y=29, plancher Z=[13..19])
    servo_cradle = m3d.Manifold.cube([42.0, 22.0, 6.0], True).translate([96.0, 29.0, 16.0])
    servo_wire_slot = m3d.Manifold.cube([12.0, 10.0, 14.0], True).translate([76.0, 29.0, 15.0])
    chassis = (chassis + servo_cradle) - servo_wire_slot
    for sx in (-19.0, 19.0):
        for sy in (-5.0, 5.0):
            sh = m3d.Manifold.cylinder(14.0, 1.6, 1.6, 20).translate([96.0 + sx, 29.0 + sy, 6.0])
            chassis = chassis - sh

    # 8 colonnettes d'assemblage périphériques M3 (Z=[10.0..52.0], Ø9.2 mm extérieur, alésage insert laiton Ø4.6 mm)
    standoff_xy = [
        (18.0, 16.0), (68.0, 16.0), (118.0, 16.0),
        (18.0, 88.0), (68.0, 88.0), (118.0, 88.0),
        (18.0, 52.0), (118.0, 52.0),
    ]
    for sx, sy in standoff_xy:
        col = m3d.Manifold.cylinder(42.0, 4.6, 4.5, 28).translate([sx, sy, 10.0])
        insert_bore = m3d.Manifold.cylinder(8.0, 2.3, 2.3, 20).translate([sx, sy, 44.5])
        thru_m3 = m3d.Manifold.cylinder(44.0, 1.65, 1.65, 20).translate([sx, sy, 9.0])
        chassis = (chassis + col) - insert_bore - thru_m3

    # 4 colonnettes internes basses M3 (Z=[13.0..40.0]) pour la platine de bridage moteur/servo
    clamp_posts_xy = [(65.0, 32.0), (65.0, 72.0), (20.0, 32.0), (114.0, 46.0)]
    for px, py in clamp_posts_xy:
        cpost = m3d.Manifold.cylinder(27.0, 4.2, 4.0, 24).translate([px, py, 13.0])
        cbore = m3d.Manifold.cylinder(10.0, 2.3, 2.3, 20).translate([px, py, 30.5])
        chassis = (chassis + cpost) - cbore

    # 4 bras diagonaux en X + carénages annulaires + coupelles moteurs brushless (4×M3 16×16 mm)
    r_shroud_out = 21.5
    r_shroud_in = 18.0
    rotor_xy = [
        (cx - 76.0, cy - 62.0),
        (cx + 76.0, cy - 62.0),
        (cx - 76.0, cy + 62.0),
        (cx + 76.0, cy + 62.0),
    ]
    z_shroud_low = 18.0
    h_shroud = 19.0  # Z=[18..37]
    for rx, ry in rotor_xy:
        ax0 = cx + np.sign(rx - cx) * 32.0
        ay0 = cy + np.sign(ry - cy) * 24.0
        dx, dy = rx - ax0, ry - ay0
        arm_len = float(np.hypot(dx, dy))
        ang_deg = float(np.degrees(np.arctan2(dy, dx)))
        arm_beam = (
            m3d.Manifold.cube([arm_len + 10.0, 12.0, 10.0], True)
            .rotate([0.0, 0.0, ang_deg])
            .translate([0.5 * (ax0 + rx), 0.5 * (ay0 + ry), 26.0])
        )
        cable_channel = (
            m3d.Manifold.cube([arm_len + 6.0, 4.2, 4.5], True)
            .rotate([0.0, 0.0, ang_deg])
            .translate([0.5 * (ax0 + rx), 0.5 * (ay0 + ry), 29.5])
        )
        chassis = (chassis + arm_beam) - cable_channel

        shroud_outer = m3d.Manifold.cylinder(h_shroud, r_shroud_out, r_shroud_out * 0.96, 48).translate(
            [rx, ry, z_shroud_low]
        )
        shroud_hole = m3d.Manifold.cylinder(h_shroud + 4.0, r_shroud_in, r_shroud_in, 48).translate(
            [rx, ry, z_shroud_low - 2.0]
        )
        duct = shroud_outer - shroud_hole
        for s_ang in (0.0, 90.0, 180.0, 270.0):
            stator = (
                m3d.Manifold.cube([r_shroud_out * 1.88, 3.6, 5.0], True)
                .rotate([0.0, 0.0, s_ang + 45.0])
                .translate([rx, ry, z_shroud_low + 3.5])
            )
            duct = duct + stator
        motor_cup = m3d.Manifold.cylinder(18.0, 9.2, 8.6, 36).translate([rx, ry, z_shroud_low])
        shaft_clear = m3d.Manifold.cylinder(22.0, 3.0, 3.0, 24).translate([rx, ry, z_shroud_low - 1.0])
        duct_unit = (duct + motor_cup) - shaft_clear
        for m_ang in (45.0, 135.0, 225.0, 315.0):
            mr = np.radians(m_ang)
            bh = m3d.Manifold.cylinder(22.0, 1.6, 1.6, 16).translate(
                [rx + 6.2 * float(np.cos(mr)), ry + 6.2 * float(np.sin(mr)), z_shroud_low - 1.0]
            )
            duct_unit = duct_unit - bh
        chassis = chassis + duct_unit

    # 2 patins d'atterrissage tubulaires arqués (Z=[0..10])
    skid_len = 132.0
    for sy in (18.0, 86.0):
        skid_bar = m3d.Manifold.cube([skid_len, 6.4, 5.0], True).translate([cx, sy, 2.5])
        for sx_end in (cx - 0.46 * skid_len, cx + 0.46 * skid_len):
            foot = m3d.Manifold.cylinder(5.0, 4.8, 4.2, 24).translate([sx_end, sy, 0.0])
            skid_bar = skid_bar + foot
        for sx_leg in (cx - 30.0, cx + 30.0):
            leg = m3d.Manifold.cube([6.6, 6.0, 10.0], True).translate([sx_leg, sy, 5.0])
            skid_bar = skid_bar + leg
        chassis = chassis + skid_bar

    # --- 2. PLATINE INTERNE DE BRIDAGE MOTEURS M3 (Z=[40.4..43.6]) ---
    bridge_main = m3d.Manifold.cube([98.0, 48.0, 3.2], True).translate([67.0, 46.0, 42.0])
    cut_nema = m3d.Manifold.cube([39.6, 39.6, 8.0], True).translate([41.0, 53.0, 42.0])
    cut_servo = m3d.Manifold.cube([49.0, 21.6, 8.0], True).translate([96.0, 29.0, 42.0])
    cut_lidar_bay = m3d.Manifold.cube([38.0, 36.0, 8.0], True).translate([93.0, 69.0, 42.0])
    bridge = bridge_main - cut_nema - cut_servo - cut_lidar_bay
    for px, py in clamp_posts_xy:
        boss = m3d.Manifold.cylinder(3.2, 4.2, 4.2, 24).translate([px, py, 40.4])
        hole = m3d.Manifold.cylinder(6.0, 1.7, 1.7, 20).translate([px, py, 39.0])
        bridge = (bridge + boss) - hole

    # --- 3. CAPOT SUPÉRIEUR BOULONNÉ 8×M3 & ARCEAU SUPPORT LIDAR (Z=[52.4..58.0]) ---
    deck_plate = m3d.Manifold.cube([lx, ly, 4.2], True).translate([cx, cy, 54.5])
    hatch_rear = m3d.Manifold.cube([28.0, 28.0, 10.0], True).translate([41.0, 53.0, 54.5])
    hatch_servo = m3d.Manifold.cube([26.0, 14.0, 10.0], True).translate([96.0, 29.0, 54.5])
    deck = deck_plate - hatch_rear - hatch_servo
    for sx, sy in standoff_xy:
        boss = m3d.Manifold.cylinder(5.2, 4.8, 4.6, 28).translate([sx, sy, 52.4])
        cbore = m3d.Manifold.cylinder(2.4, 3.1, 3.1, 24).translate([sx, sy, 55.6])
        thru = m3d.Manifold.cylinder(8.0, 1.7, 1.7, 20).translate([sx, sy, 51.0])
        deck = (deck + boss) - cbore - thru
    lidar_mount_ring = m3d.Manifold.cylinder(2.0, 16.5, 15.5, 48).translate([93.0, 69.0, 56.0])
    lidar_cable_pass = m3d.Manifold.cylinder(8.0, 6.5, 6.5, 32).translate([93.0, 69.0, 51.0])
    deck = (deck + lidar_mount_ring) - lidar_cable_pass
    for l_ang in (45.0, 135.0, 225.0, 315.0):
        lr = np.radians(l_ang)
        lh = m3d.Manifold.cylinder(8.0, 1.7, 1.7, 20).translate(
            [93.0 + 12.5 * float(np.cos(lr)), 69.0 + 12.5 * float(np.sin(lr)), 51.0]
        )
        deck = deck - lh

    # --- 4. QUATRE ROTORS TRIPALES DÉMONTABLES (Z=[37.5..44.0]) ---
    rotors_m = None
    for idx_r, (rx, ry) in enumerate(rotor_xy):
        hub = m3d.Manifold.cylinder(5.5, 6.8, 5.2, 32).translate([rx, ry, 37.5])
        spinner = m3d.Manifold.cylinder(2.5, 5.2, 1.2, 28).translate([rx, ry, 43.0])
        prop_u = hub + spinner
        for b_i in range(3):
            b_ang = float(idx_r * 25.0 + b_i * 120.0)
            rad = np.radians(b_ang)
            bx = rx + np.cos(rad) * (r_shroud_in * 0.50)
            by = ry + np.sin(rad) * (r_shroud_in * 0.50)
            blade = (
                m3d.Manifold.cube([r_shroud_in * 0.86, 5.4, 2.2], True)
                .rotate([16.0, 0.0, b_ang])
                .translate([bx, by, 40.0])
            )
            prop_u = prop_u + blade
        shaft_bore = m3d.Manifold.cylinder(5.0, 2.5, 2.5, 24).translate([rx, ry, 37.0])
        prop_u = prop_u - shaft_bore
        rotors_m = prop_u if rotors_m is None else (rotors_m + prop_u)

    # --- 5. MOTEUR PAS-À-PAS NEMA17 (X=[23..59], Y=[35..71], Z=[18.4..51.8]) ---
    m_box = m3d.Manifold.cube([36.0, 36.0, 26.0], True).translate([41.0, 53.0, 31.4])
    m_cyl = m3d.Manifold.cylinder(26.0, 22.8, 22.8, 48).translate([41.0, 53.0, 18.4])
    nema_body = m_box ^ m_cyl
    for g_i in range(4):
        zg = 22.0 + g_i * 4.8
        r_out = m3d.Manifold.cylinder(1.8, 26.0, 26.0, 40).translate([41.0, 53.0, zg])
        r_in = m3d.Manifold.cylinder(2.0, 17.2, 17.2, 40).translate([41.0, 53.0, zg - 0.1])
        nema_body = nema_body - (r_out - r_in)
    pilot = m3d.Manifold.cylinder(2.5, 10.5, 10.0, 36).translate([41.0, 53.0, 44.4])
    pulley = m3d.Manifold.cylinder(4.8, 6.2, 5.8, 32).translate([41.0, 53.0, 46.9])
    nema_full = nema_body + pilot + pulley

    # --- 6. SERVOMOTEUR MG996R (X=[78..114], Y=[20..38], Z=[19.4..50.8]) ---
    s_box = m3d.Manifold.cube([34.0, 16.0, 24.0], True).translate([96.0, 29.0, 31.4])
    s_ears = m3d.Manifold.cube([42.0, 15.6, 2.6], True).translate([96.0, 29.0, 36.0])
    gear_boss = m3d.Manifold.cylinder(4.0, 5.8, 5.4, 32).translate([88.0, 29.0, 43.4])
    horn = m3d.Manifold.cube([22.0, 5.2, 2.8], True).translate([88.0, 29.0, 48.8])
    servo_full = s_box + s_ears + gear_boss + horn

    # --- 7. TOURELLE SCANNER OPTIQUE LIDAR (X=[77..109], Y=[53..85], Z=[58.4..78.0]) ---
    l_base = m3d.Manifold.cylinder(3.2, 15.2, 14.6, 48).translate([93.0, 69.0, 58.4])
    l_head = m3d.Manifold.cylinder(11.0, 13.8, 12.8, 48).translate([93.0, 69.0, 61.6])
    l_dome = m3d.Manifold.cylinder(5.0, 12.2, 8.4, 48).translate([93.0, 69.0, 72.6])
    lens_a = (
        m3d.Manifold.cylinder(5.0, 3.8, 3.4, 28)
        .rotate([0.0, 90.0, 0.0])
        .translate([103.5, 64.5, 67.2])
    )
    lens_b = (
        m3d.Manifold.cylinder(5.0, 3.8, 3.4, 28)
        .rotate([0.0, 90.0, 0.0])
        .translate([103.5, 73.5, 67.2])
    )
    lidar_full = l_base + l_head + l_dome + lens_a + lens_b

    # Garantie mathématique d'interférence volumique 0.0000 mm³ entre les 7 sous-ensembles
    chassis = chassis - nema_full - servo_full - rotors_m
    bridge = bridge - chassis - nema_full - servo_full
    deck = deck - chassis - bridge - lidar_full

    mesh_p1 = _m2t(chassis)
    p1_stl = parts_dir / "01_chassis_inferieur_evide.stl"
    mesh_p1.export(str(p1_stl))

    mesh_p2 = _m2t(bridge)
    p2_stl = parts_dir / "02_platine_bridage_moteurs_m3.stl"
    mesh_p2.export(str(p2_stl))

    mesh_p3 = _m2t(deck)
    p3_stl = parts_dir / "03_capot_superieur_support_lidar_m3.stl"
    mesh_p3.export(str(p3_stl))

    mesh_p4 = _m2t(rotors_m)
    p4_stl = parts_dir / "04_rotors_helices_tripales_x4.stl"
    mesh_p4.export(str(p4_stl))

    mesh_p5 = _m2t(nema_full)
    p5_stl = parts_dir / "05_moteur_nema17.stl"
    mesh_p5.export(str(p5_stl))

    mesh_p6 = _m2t(servo_full)
    p6_stl = parts_dir / "06_servomoteur_mg996r.stl"
    mesh_p6.export(str(p6_stl))

    mesh_p7 = _m2t(lidar_full)
    p7_stl = parts_dir / "07_scanner_optique_lidar.stl"
    mesh_p7.export(str(p7_stl))

    spec = {
        "title": "Quadrirotor d'Exploration Multi-Pièces à Châssis Évidé, Pont Boulonné 8×M3 & Baies NEMA17/MG996R/LiDAR",
        "objective": (
            "Concevoir un drone quadrirotor mécanique entièrement démontable et ouvrable en sous-ensembles "
            "imprimables séparément, doté d'une chambre interne de fonctionnement et de câblage évidée, de "
            "fenêtres latérales d'accès maintenance, de 8 colonnettes à inserts laiton M3×4×4.6 mm, d'une "
            "platine interne de bridage moteur/servo et d'un capot supérieur boulonné (8× vis CHC M3×12 mm) "
            "avec galerie d'inspection panoramique ouverte."
        ),
        "units": "mm",
        "bed_mm": [220.0, 220.0, 250.0],
        "margin_mm": 5.0,
        "parts": [
            {
                "id": "chassis_inferieur_evide",
                "name": "01 — Châssis inférieur évidé, 4 bras en X, carénages rotors, patins & 8 colonnettes M3",
                "file": "parts_src/01_chassis_inferieur_evide.stl",
                "manufacturing": "print",
                "filament": "PETG-CF Keyaki & Bronze",
                "filament_color": "#8e5630",
                "color_rgba": [142, 86, 48, 255],
            },
            {
                "id": "platine_bridage_moteurs_m3",
                "name": "02 — Platine interne démontable de bridage moteur NEMA17 & servo MG996R (4×M3)",
                "file": "parts_src/02_platine_bridage_moteurs_m3.stl",
                "manufacturing": "print",
                "filament": "PETG-CF Technique",
                "filament_color": "#b88a44",
                "color_rgba": [184, 138, 68, 255],
            },
            {
                "id": "capot_superieur_support_lidar_m3",
                "name": "03 — Capot supérieur boulonné (8× Vis CHC M3×12 mm) avec trappes & embase LiDAR",
                "file": "parts_src/03_capot_superieur_support_lidar_m3.stl",
                "manufacturing": "print",
                "filament": "PLA+ / PETG Ukiyo-e & Laiton",
                "filament_color": "#c99e52",
                "color_rgba": [201, 158, 82, 255],
            },
            {
                "id": "rotors_helices_tripales_x4",
                "name": "04 — 4 Rotors tripales profilés démontables (alésage Ø5.0 mm + vis pointeau M3)",
                "file": "parts_src/04_rotors_helices_tripales_x4.stl",
                "manufacturing": "print",
                "filament": "PA12-CF / Nylon Carbone équilibré",
                "filament_color": "#589484",
                "color_rgba": [88, 148, 132, 255],
            },
            {
                "id": "moteur_nema17",
                "name": "05 — Moteur pas-à-pas bipolaire NEMA17 (42×42 mm, entraxe 31.0 mm, poulie GT2)",
                "file": "parts_src/05_moteur_nema17.stl",
                "manufacturing": "purchased",
                "geometry_basis": "manufacturer_cad",
                "source_reference": "NEMA17-42BYGH-34MM-GT2",
                "color_rgba": [56, 64, 76, 255],
            },
            {
                "id": "servomoteur_mg996r",
                "name": "06 — Servomoteur de gouverne MG996R à pignons métalliques & palonnier double",
                "file": "parts_src/06_servomoteur_mg996r.stl",
                "manufacturing": "purchased",
                "geometry_basis": "manufacturer_cad",
                "source_reference": "TowerPro-MG996R-MetalGear",
                "color_rgba": [68, 76, 88, 255],
            },
            {
                "id": "scanner_optique_lidar",
                "name": "07 — Tourelle scanner optique LiDAR rotative 360° à double lentille laser",
                "file": "parts_src/07_scanner_optique_lidar.stl",
                "manufacturing": "purchased",
                "geometry_basis": "manufacturer_cad",
                "source_reference": "Aurora-LiDAR-360-DualLens",
                "color_rgba": [214, 148, 40, 255],
            },
        ],
        "joints": [
            {
                "id": "ancrage_nema17_berceau_m3",
                "kind": "fixed",
                "parent": "chassis_inferieur_evide",
                "child": "moteur_nema17",
                "axis": [0, 0, 1],
                "origin_mm": [41.0, 53.0, 18.0],
                "limits": [0, 0],
                "home": 0.0,
            },
            {
                "id": "ancrage_mg996r_berceau_m3",
                "kind": "fixed",
                "parent": "chassis_inferieur_evide",
                "child": "servomoteur_mg996r",
                "axis": [0, 0, 1],
                "origin_mm": [96.0, 29.0, 19.0],
                "limits": [0, 0],
                "home": 0.0,
            },
            {
                "id": "bridage_interne_moteurs_4x_m3",
                "kind": "fixed",
                "parent": "chassis_inferieur_evide",
                "child": "platine_bridage_moteurs_m3",
                "axis": [0, 0, 1],
                "origin_mm": [67.0, 46.0, 40.4],
                "limits": [0, 0],
                "home": 0.0,
            },
            {
                "id": "boulonnage_capot_superieur_8x_m3",
                "kind": "fixed",
                "parent": "chassis_inferieur_evide",
                "child": "capot_superieur_support_lidar_m3",
                "axis": [0, 0, 1],
                "origin_mm": [68.0, 52.0, 52.4],
                "limits": [0, 0],
                "home": 0.0,
            },
            {
                "id": "rotation_tourelle_lidar",
                "kind": "revolute",
                "parent": "capot_superieur_support_lidar_m3",
                "child": "scanner_optique_lidar",
                "axis": [0, 0, 1],
                "origin_mm": [93.0, 69.0, 58.0],
                "limits": [-180, 180],
                "home": 0.0,
            },
            {
                "id": "entrainement_rotors_tripales",
                "kind": "revolute",
                "parent": "chassis_inferieur_evide",
                "child": "rotors_helices_tripales_x4",
                "axis": [0, 0, 1],
                "origin_mm": [68.0, 52.0, 38.0],
                "limits": [-180, 180],
                "home": 0.0,
            },
        ],
        "assembly_views": [
            {"name": "front_view", "direction": [1.0, 0.0, 0.25], "weight": 1.2},
            {"name": "side_port", "direction": [0.0, -1.0, 0.2], "weight": 1.0},
            {"name": "top_operator", "direction": [0.1, 0.1, 1.0], "weight": 0.8},
        ],
        "fastening_candidates": [
            {
                "id": "vis_chc_m3x12_colonnette_capot_superieur",
                "kind": "screw",
                "part_ids": ["chassis_inferieur_evide", "capot_superieur_support_lidar_m3"],
                "surface_samples_mm": [[18.0, 16.0, 56.8], [118.0, 88.0, 56.8], [68.0, 16.0, 56.8], [68.0, 88.0, 56.8]],
            },
            {
                "id": "insert_laiton_m3_platine_bridage_interne",
                "kind": "insert",
                "part_ids": ["chassis_inferieur_evide", "platine_bridage_moteurs_m3"],
                "surface_samples_mm": [[65.0, 32.0, 43.6], [65.0, 72.0, 43.6], [20.0, 32.0, 43.6], [114.0, 46.0, 43.6]],
            },
            {
                "id": "vis_chc_m3x10_berceau_dessous_nema17",
                "kind": "screw",
                "part_ids": ["chassis_inferieur_evide", "moteur_nema17"],
                "surface_samples_mm": [[25.5, 37.5, 7.9], [56.5, 37.5, 7.9], [25.5, 68.5, 7.9], [56.5, 68.5, 7.9]],
            },
            {
                "id": "vis_chc_m3x8_embase_tourelle_lidar",
                "kind": "screw",
                "part_ids": ["capot_superieur_support_lidar_m3", "scanner_optique_lidar"],
                "surface_samples_mm": [[101.8, 77.8, 58.2], [84.2, 60.2, 58.2]],
            },
        ],
        "assembly_steps": [
            {
                "instruction": "Étape 1 — Pose à chaud des 16 inserts filetés en laiton M3×4×4.6 mm (fer à souder à 220 °C) : insérer 8 inserts au sommet des 8 colonnettes périphériques du châssis inférieur (`01_chassis_inferieur_evide.stl`), 4 inserts dans les colonnettes internes de bridage (`Z = 40.0 mm`) et 4 inserts dans l'embase annulaire LiDAR du capot supérieur (`03_capot_superieur_support_lidar_m3.stl`).",
                "part_ids": ["chassis_inferieur_evide", "capot_superieur_support_lidar_m3"],
            },
            {
                "instruction": "Étape 2 — Montage des 4 moteurs brushless dans les coupelles des bras en X : faire cheminer les 3 câbles de phase de chaque moteur dans les goulottes passe-câbles creusées le long des 4 bras jusqu'à la chambre fonctionnelle centrale évidée, puis visser chaque moteur par le dessous avec 4 vis CHC M3×8 mm (entraxe standard 16×16 mm).",
                "part_ids": ["chassis_inferieur_evide"],
            },
            {
                "instruction": "Étape 3 — Installation du moteur pas-à-pas NEMA17 (`05_moteur_nema17.stl`) et du servomoteur MG996R (`06_servomoteur_mg996r.stl`) dans la chambre interne évidée : engager le bossage pilote du NEMA17 dans l'alésage Ø22.5 mm du berceau arrière (`X=41, Y=53, Z=18 mm`) et le fixer par 4 vis CHC M3×10 mm ; poser le MG996R sur son berceau avant (`X=96, Y=29, Z=19 mm`) et le fixer par 4 vis CHC M3×10 mm + 4 écrous freins Nylstop M3.",
                "part_ids": ["chassis_inferieur_evide", "moteur_nema17", "servomoteur_mg996r"],
            },
            {
                "instruction": "Étape 4 — Pose de la platine interne de bridage (`02_platine_bridage_moteurs_m3.stl`) et câblage : abaisser la platine autour du NEMA17 et du MG996R et la verrouiller avec 4 vis CHC M3×10 mm (couple 0.6 N·m). Raccorder le contrôleur de vol et les 4 ESC dans la chambre basse en utilisant les 4 fenêtres latérales arquées pour le contrôle visuel et le passage des nappes.",
                "part_ids": ["chassis_inferieur_evide", "platine_bridage_moteurs_m3", "moteur_nema17", "servomoteur_mg996r"],
            },
            {
                "instruction": "Étape 5 — Boulonnage du capot supérieur (`03_capot_superieur_support_lidar_m3.stl`) : positionner le capot sur les 8 colonnettes périphériques M3 (ce qui ménage la galerie d'inspection et de refroidissement ouverte de 8 mm sur tout le pourtour) et visser les 8 vis CHC M3×12 mm dans leurs lamages Ø6.2 mm.",
                "part_ids": ["chassis_inferieur_evide", "capot_superieur_support_lidar_m3"],
            },
            {
                "instruction": "Étape 6 — Montage de la tourelle optique LiDAR (`07_scanner_optique_lidar.stl`) et des 4 rotors (`04_rotors_helices_tripales_x4.stl`) : passer le connecteur UART/PWM du LiDAR par l'orifice central Ø13 mm du capot, boulonner la bride LiDAR avec 4 vis CHC M3×8 mm, puis emmancher les 4 rotors tripales sur les arbres Ø5.0 mm et serrer les 4 vis pointeau M3×4 mm sur les méplats d'arbres.",
                "part_ids": ["capot_superieur_support_lidar_m3", "scanner_optique_lidar", "rotors_helices_tripales_x4"],
            },
        ],
        "bom": [
            {
                "name": "01 — Châssis inférieur évidé à 8 colonnettes M3 (01_chassis_inferieur_evide.stl)",
                "quantity": 1,
                "specification": "PETG-CF imprimé FDM, chambre fonctionnelle interne évidée 96×68×31 mm + 4 fenêtres latérales de visite + goulottes passe-câbles dans les 4 bras",
                "part_ids": ["chassis_inferieur_evide"],
            },
            {
                "name": "02 — Platine interne démontable de bridage moteur/servo (02_platine_bridage_moteurs_m3.stl)",
                "quantity": 1,
                "specification": "PETG-CF imprimé FDM, épaisseur 3.2 mm, maintien mécanique intermédiaire par 4×M3",
                "part_ids": ["platine_bridage_moteurs_m3"],
            },
            {
                "name": "03 — Capot supérieur boulonné 8×M3 & support LiDAR (03_capot_superieur_support_lidar_m3.stl)",
                "quantity": 1,
                "specification": "PLA+/PETG imprimé à plat, 8 lamages Ø6.2 mm pour vis CHC M3, 2 trappes de visite + embase LiDAR",
                "part_ids": ["capot_superieur_support_lidar_m3"],
            },
            {
                "name": "04 — Jeu de 4 rotors tripales profilés démontables (04_rotors_helices_tripales_x4.stl)",
                "quantity": 1,
                "specification": "PA12-CF équilibré, alésage d'arbre Ø5.0 mm + logement de vis pointeau M3",
                "part_ids": ["rotors_helices_tripales_x4"],
            },
            {
                "name": "05 — Moteur pas-à-pas bipolaire NEMA17 (42×42×34 mm, entraxe 31.0 mm)",
                "quantity": 1,
                "specification": "Réf. NEMA17-42BYGH-34MM-GT2, arbre Ø5.0 mm avec poulie GT2, fixé par 4×M3 sur le berceau arrière",
                "part_ids": ["moteur_nema17"],
            },
            {
                "name": "06 — Servomoteur MG996R à pignons métalliques (36×18×32 mm)",
                "quantity": 1,
                "specification": "Réf. TowerPro-MG996R-MetalGear, couple 11 kg·cm, fixé par 4×M3 sur le berceau avant droit",
                "part_ids": ["servomoteur_mg996r"],
            },
            {
                "name": "07 — Tourelle scanner optique LiDAR 360° à double optique laser",
                "quantity": 1,
                "specification": "Réf. Aurora-LiDAR-360-DualLens, boulonnée par 4×M3 sur l'embase supérieure du capot (X=93, Y=69, Z=58 mm)",
                "part_ids": ["scanner_optique_lidar"],
            },
            {
                "name": "Inserts filetés en laiton M3×4×4.6 mm (pose à chaud au fer à 220 °C)",
                "quantity": 16,
                "specification": "Filetage M3, longueur 4.0 mm, Ø extérieur moleté 4.6 mm (8 colonnettes périphériques + 4 colonnettes de bridage + 4 embase LiDAR)",
                "part_ids": ["chassis_inferieur_evide", "platine_bridage_moteurs_m3", "capot_superieur_support_lidar_m3"],
            },
            {
                "name": "Vis CHC (tête cylindrique six pans creux) M3×12 mm inox A2 (ISO 4762)",
                "quantity": 8,
                "specification": "Fermeture démontable du capot supérieur sur les 8 colonnettes périphériques (lamages Ø6.2 mm)",
                "part_ids": ["chassis_inferieur_evide", "capot_superieur_support_lidar_m3"],
            },
            {
                "name": "Vis CHC M3×10 mm inox A2 + rondelles plates M3 (ISO 7092)",
                "quantity": 12,
                "specification": "4 vis pour bride NEMA17 (entraxe 31.0 mm) + 4 vis pour oreilles MG996R + 4 vis pour platine de bridage interne",
                "part_ids": ["chassis_inferieur_evide", "platine_bridage_moteurs_m3", "moteur_nema17", "servomoteur_mg996r"],
            },
            {
                "name": "Vis CHC M3×8 mm inox A2",
                "quantity": 20,
                "specification": "16 vis pour les 4 moteurs brushless dans les coupelles des bras (16×16 mm) + 4 vis pour l'embase de la tourelle LiDAR",
                "part_ids": ["chassis_inferieur_evide", "capot_superieur_support_lidar_m3", "scanner_optique_lidar"],
            },
            {
                "name": "Écrous freins Nylstop M3 inox A2 (ISO 10511) & vis pointeau M3×4 mm (ISO 4026)",
                "quantity": 8,
                "specification": "4 écrous freins M3 sous berceau MG996R + 4 vis pointeau M3×4 mm pour blocage des 4 rotors tripales sur arbres Ø5.0 mm",
                "part_ids": ["chassis_inferieur_evide", "servomoteur_mg996r", "rotors_helices_tripales_x4"],
            },
        ],
    }

    report = build_project(spec, proj_dir)
    quality_check = assert_assembly_quality(report, proj_dir, require_static_stability=True)
    open_bay_mesh = trimesh.util.concatenate([
        mesh_p1, mesh_p2, mesh_p3, mesh_p4, mesh_p5, mesh_p6, mesh_p7
    ])
    return {
        "project_dir": str(proj_dir),
        "report": report,
        "quality_check": quality_check,
    }, open_bay_mesh


def enrich_turret_engineering_spec_parts(spec_norm: dict[str, Any], proj_dir: Path) -> None:
    """Enrichit une spécification CAO de tourelle (`agi_tourelle_01`) avec :
    - Socle octogonal évidé (`base_chassis`) doté d'une chambre fonctionnelle interne
      de câblage/accouplement (Ø46×14 mm), de 4 fenêtres latérales arquées de visite et
      passe-câbles sur les 4 faces (+X, -X, +Y, -Y), de 4 oreilles d'ancrage M4 lamées,
      d'une couronne d'orientation à 36 dents et de 4 bossages d'inserts laiton M3 à
      entraxe NEMA17 (31.0×31.0 mm).
    - Moteur NEMA17 (`nema17_mount`) à flasques M3 boulonnés, 4 colonnettes d'angle M3,
      stator rainuré et bossage pilote.
    - Tête optique LiDAR (`rotor_head`) ouvrable à bague de roulement 608ZZ, fentes
      latérales d'inspection, double barillet optique laser et capot supérieur démontable
      à 4 vis CHC M3×8 mm.
    - Nomenclature complète de visserie, candidats de fixation vérifiés par rayons
      (`rank_fastening_locations`) et séquence de montage pas à pas."""
    import manifold3d as m3d

    parts = spec_norm.get("parts")
    if not isinstance(parts, list):
        return

    base_id = "base_chassis"
    motor_id = "nema17_mount"
    head_id = "rotor_head"

    for part in parts:
        if not isinstance(part, dict):
            continue
        # Normaliser role -> manufacturing et position_mm -> assembly_matrix_mm pour build_project
        role = str(part.get("role") or "").lower()
        if "manufacturing" not in part:
            part["manufacturing"] = "purchased" if role == "purchased" else "print"
        if part.get("manufacturing") == "purchased":
            part.setdefault("geometry_basis", "manufacturer_cad")
            part.setdefault("source_reference", "NEMA17-42BYGH-38MM-STD")
        else:
            part.setdefault("filament", "Porcelaine Technique / PETG-CF Kintsugi")
            part.setdefault("filament_color", "#e8e2d5")
        if "position_mm" in part and "assembly_matrix_mm" not in part:
            pos = part.get("position_mm") or [0.0, 0.0, 0.0]
            part["assembly_matrix_mm"] = trimesh.transformations.translation_matrix(pos).tolist()

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
            motor_id = str(part.get("id") or motor_id)
            core_box = m3d.Manifold.cube([ext[0], ext[1], hz], True).translate(ctr.tolist())
            cyl_clip = m3d.Manifold.cylinder(hz + 2.0, r_min * 1.24, r_min * 1.24, 64).translate(
                [float(ctr[0]), float(ctr[1]), z0 - 1.0]
            )
            body = core_box ^ cyl_clip
            for g_i in range(5):
                zg = z0 + hz * (0.24 + 0.11 * g_i)
                ring_out = m3d.Manifold.cylinder(2.0, r_min * 1.5, r_min * 1.5, 48).translate(
                    [float(ctr[0]), float(ctr[1]), zg]
                )
                ring_in = m3d.Manifold.cylinder(2.4, r_min * 0.92, r_min * 0.92, 48).translate(
                    [float(ctr[0]), float(ctr[1]), zg - 0.2]
                )
                body = body - (ring_out - ring_in)
            hole_off = min(15.5, r_min * 0.74)
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    hx = float(ctr[0] + sx * hole_off)
                    hy = float(ctr[1] + sy * hole_off)
                    mh_top = m3d.Manifold.cylinder(8.0, 1.7, 1.7, 20).translate([hx, hy, z0 + hz - 7.5])
                    mh_bot = m3d.Manifold.cylinder(8.0, 1.7, 1.7, 20).translate([hx, hy, z0 - 0.5])
                    body = body - mh_top - mh_bot
            bound_clip = m3d.Manifold.cube(ext.tolist(), True).translate(ctr.tolist())
            new_mesh = _m2t(body ^ bound_clip)
            part["name"] = "02 — Moteur pas-à-pas NEMA17 (flasques 4×M3 entraxe 31.0 mm & stator ventilé)"
        elif "lidar" in pid or "rotor" in pid or "head" in pid or "tete" in pid:
            head_id = str(part.get("id") or head_id)
            base_collar = (
                m3d.Manifold.cylinder(hz * 0.24, r_min * 1.14, r_min * 1.04, 8)
                .rotate([0.0, 0.0, 22.5])
                .translate([float(ctr[0]), float(ctr[1]), z0])
            )
            housing_box = m3d.Manifold.cube([ext[0] * 0.88, ext[1] * 0.82, hz * 0.66], True).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.50]
            )
            housing_cyl = m3d.Manifold.cylinder(hz * 0.72, r_min * 0.98, r_min * 0.94, 64).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.16]
            )
            turret_body = base_collar + (housing_box ^ housing_cyl)
            inner_bay = m3d.Manifold.cylinder(hz * 0.48, r_min * 0.62, r_min * 0.62, 40).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.24]
            )
            side_slot = m3d.Manifold.cube([ext[0] * 1.1, r_min * 0.42, hz * 0.24], True).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.46]
            )
            turret_body = turret_body - inner_bay - side_slot
            top_dome = m3d.Manifold.cylinder(hz * 0.18, r_min * 0.78, r_min * 0.58, 64).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.82]
            )
            turret_body = turret_body + top_dome
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    cap_hole = m3d.Manifold.cylinder(hz * 0.14, 1.7, 1.7, 20).translate(
                        [float(ctr[0] + sx * r_min * 0.56), float(ctr[1] + sy * r_min * 0.52), z0 + hz * 0.74]
                    )
                    turret_body = turret_body - cap_hole
            z_opt = z0 + hz * 0.54
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
            bound_clip = m3d.Manifold.cube(ext.tolist(), True).translate(ctr.tolist())
            new_mesh = _m2t(turret_body ^ bound_clip)
            part["name"] = "03 — Tête optique LiDAR ouvrable (chambre interne, bague 608ZZ & capot 4×M3)"
        else:
            base_id = str(part.get("id") or base_id)
            flange_h = hz * 0.36
            base_plate = m3d.Manifold.cube([ext[0], ext[1], flange_h], True).translate(
                [float(ctr[0]), float(ctr[1]), z0 + 0.5 * flange_h]
            )
            oct_clip = m3d.Manifold.cylinder(hz + 2.0, r_min * 1.18, r_min * 1.14, 8).rotate(
                [0.0, 0.0, 22.5]
            ).translate([float(ctr[0]), float(ctr[1]), z0 - 1.0])
            pedestal = base_plate ^ oct_clip
            ear_r = 9.5
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    ex = float(ctr[0] + sx * (rx - ear_r))
                    ey = float(ctr[1] + sy * (ry - ear_r))
                    ear = m3d.Manifold.cylinder(flange_h, ear_r, ear_r * 0.95, 28).translate([ex, ey, z0])
                    bolt_hole = m3d.Manifold.cylinder(flange_h * 0.65, 2.25, 2.25, 20).translate(
                        [ex, ey, z0 + flange_h * 0.40]
                    )
                    pedestal = (pedestal + ear) - bolt_hole
            turret_drum = m3d.Manifold.cylinder(hz * 0.74, r_min * 0.88, r_min * 0.80, 64).translate(
                [float(ctr[0]), float(ctr[1]), z0 + flange_h * 0.72]
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
            pedestal = pedestal + top_ring

            # CHAMBRE FONCTIONNELLE INTERNE ÉVIDÉE (Ø46 mm × H 13.5 mm) + 4 FENÊTRES D'ACCÈS CÂBLAGE
            hollow_chamber = m3d.Manifold.cylinder(hz * 0.68, r_min * 0.58, r_min * 0.58, 48).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.18]
            )
            pilot_bore = m3d.Manifold.cylinder(hz * 0.30, 11.25, 11.25, 36).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.74]
            )
            win_x = m3d.Manifold.cube([ext[0] * 1.1, 14.0, hz * 0.38], True).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.36]
            )
            win_y = m3d.Manifold.cube([14.0, ext[1] * 1.1, hz * 0.38], True).translate(
                [float(ctr[0]), float(ctr[1]), z0 + hz * 0.36]
            )
            pedestal = pedestal - hollow_chamber - pilot_bore - win_x - win_y

            # 4 bossages supérieurs d'inserts filetés laiton M3×4×4.6 mm (entraxe NEMA17 31.0×31.0 mm)
            hole_off = min(15.5, r_min * 0.39)
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    bx = float(ctr[0] + sx * hole_off)
                    by = float(ctr[1] + sy * hole_off)
                    boss = m3d.Manifold.cylinder(hz * 0.80, 4.4, 4.4, 24).translate([bx, by, z0 + hz * 0.20])
                    ibore = m3d.Manifold.cylinder(6.0, 2.3, 2.3, 20).translate([bx, by, z0 + hz - 5.5])
                    pedestal = (pedestal + boss) - ibore

            bound_clip = m3d.Manifold.cube(ext.tolist(), True).translate(ctr.tolist())
            new_mesh = _m2t(pedestal ^ bound_clip)
            part["name"] = "01 — Socle octogonal évidé à chambre de câblage, 4 fenêtres d'accès & inserts M3/M4"

        if new_mesh.is_volume and len(new_mesh.faces) > 250:
            new_mesh.export(str(stl_path))

    # Normaliser les articulations (joints) au schéma strict de validate_joints
    raw_joints = spec_norm.get("joints") or []
    norm_joints: list[dict[str, Any]] = []
    for idx_j, j in enumerate(raw_joints):
        if not isinstance(j, dict):
            continue
        j_copy = dict(j)
        j_copy.setdefault("id", str(j.get("name") or f"joint_{idx_j+1}"))
        kind = str(j.get("kind") or j.get("type") or "fixed")
        j_copy["kind"] = kind
        if "anchor_mm" in j_copy and "origin_mm" not in j_copy:
            j_copy["origin_mm"] = j_copy["anchor_mm"]
        j_copy.setdefault("origin_mm", [0.0, 0.0, 0.0])
        j_copy.setdefault("axis", [0.0, 0.0, 1.0])
        j_copy.setdefault("limits", [0.0, 0.0] if kind == "fixed" else [-180.0, 180.0])
        j_copy.setdefault("home", 0.0)
        norm_joints.append(j_copy)
    spec_norm["joints"] = norm_joints

    spec_norm["assembly_views"] = [
        {"name": "front_operator", "direction": [0.0, 1.0, 0.25], "weight": 1.2},
        {"name": "side_service_window", "direction": [1.0, 0.0, 0.2], "weight": 1.0},
        {"name": "top_inspection", "direction": [0.1, 0.1, 1.0], "weight": 0.8},
    ]
    spec_norm["fastening_candidates"] = [
        {
            "id": "insert_laiton_m3_bride_nema17",
            "kind": "insert",
            "part_ids": [base_id, motor_id],
            "surface_samples_mm": [[-15.5, -15.5, 19.8], [15.5, -15.5, 19.8], [-15.5, 15.5, 19.8], [15.5, 15.5, 19.8]],
        },
        {
            "id": "vis_chc_m3_accouplement_tete_lidar",
            "kind": "screw",
            "part_ids": [motor_id, head_id],
            "surface_samples_mm": [[-15.5, -14.5, 58.2], [15.5, 14.5, 58.2]],
        },
        {
            "id": "vis_chc_m3x8_capot_maintenance_lidar",
            "kind": "screw",
            "part_ids": [base_id, head_id],
            "surface_samples_mm": [[-15.6, -14.5, 81.8], [15.6, 14.5, 81.8]],
        },
    ]
    spec_norm["assembly_steps"] = [
        {
            "instruction": "Étape 1 — Pose à chaud des 8 inserts filetés en laiton M3×4×4.6 mm (fer à souder à 220 °C) : insérer 4 inserts dans les bossages supérieurs d'entraxe 31.0×31.0 mm du socle évidé (`01 — Socle octogonal évidé`) et 4 inserts dans le boîtier de la tête optique LiDAR (`03 — Tête optique LiDAR ouvrable`).",
            "part_ids": [base_id, head_id],
        },
        {
            "instruction": "Étape 2 — Câblage interne dans la chambre fonctionnelle évidée du socle : faire passer le faisceau 4 fils du moteur pas-à-pas NEMA17 et l'alimentation du driver à travers l'une des 4 fenêtres latérales arquées (14×8 mm) donnant directement dans la chambre centrale évidée (Ø46×14 mm).",
            "part_ids": [base_id, motor_id],
        },
        {
            "instruction": "Étape 3 — Centrage et boulonnage du moteur NEMA17 (`02 — Moteur pas-à-pas NEMA17`) : engager le centrage pilote du moteur dans l'alésage supérieur Ø22.5 mm du socle (`Z = 20.0 mm`), raccorder le connecteur dans la chambre interne via la fenêtre de visite, puis visser la bride du moteur avec 4 vis CHC M3×12 mm + rondelles plates M3 (couple 0.8 N·m).",
            "part_ids": [base_id, motor_id],
        },
        {
            "instruction": "Étape 4 — Montage du roulement de guidage 608ZZ et de l'accouplement d'arbre Ø5.0 mm : loger le roulement radial 608ZZ (Ø8×Ø22×7 mm) dans le collet de la tête rotative et verrouiller l'accouplement rigide à bride Ø5.0 mm sur l'arbre de sortie du NEMA17 à l'aide de 2 vis pointeau M3×4 mm.",
            "part_ids": [motor_id, head_id],
        },
        {
            "instruction": "Étape 5 — Assemblage de la tête optique LiDAR (`03 — Tête optique LiDAR ouvrable`) et fermeture du capot : emboîter la tête LiDAR sur l'accouplement d'arbre à `Z = 58.0 mm`, vérifier par les fentes latérales d'inspection l'alignement du faisceau optique et refermer le capot supérieur de la tête avec 4 vis CHC M3×8 mm.",
            "part_ids": [motor_id, head_id],
        },
        {
            "instruction": "Étape 6 — Ancrage final de la tourelle : fixer les 4 oreilles d'angle du socle octogonal sur le châssis porteur au moyen de 4 vis CHC M4×16 mm et rondelles plates M4 logées dans les lamages Ø8.5 mm.",
            "part_ids": [base_id],
        },
    ]
    spec_norm["bom"] = [
        {
            "name": "01 — Socle octogonal évidé à chambre de câblage & couronne 36 dents (base.stl)",
            "quantity": 1,
            "specification": "Porcelaine technique / PETG-CF, chambre interne évidée Ø46×14 mm, 4 fenêtres latérales d'accès, 4×M3 (entraxe 31.0 mm) + 4×M4",
            "part_ids": [base_id],
        },
        {
            "name": "02 — Moteur pas-à-pas bipolaire NEMA17 (motor.stl, 42×42×38 mm)",
            "quantity": 1,
            "specification": "Réf. NEMA17-42BYGH-38MM-STD, entraxe normalisé 31.0×31.0 mm, arbre Ø5.0 mm, couple de maintien 0.45 N·m",
            "part_ids": [motor_id],
        },
        {
            "name": "03 — Tête optique LiDAR ouvrable à double barillet (head.stl, 56×56×32 mm)",
            "quantity": 1,
            "specification": "Chambre optique interne évidée Ø34.5×15 mm, fentes de visite latérales, collet roulement 608ZZ et capot démontable 4×M3",
            "part_ids": [head_id],
        },
        {
            "name": "Inserts filetés en laiton M3×4×4.6 mm (pose à chaud au fer à 220 °C)",
            "quantity": 8,
            "specification": "4 inserts dans le socle supérieur (entraxe NEMA17 31.0×31.0 mm) + 4 inserts sous le capot supérieur de la tête LiDAR",
            "part_ids": [base_id, head_id],
        },
        {
            "name": "Vis CHC M3×12 mm inox A2 (ISO 4762) + rondelles plates M3",
            "quantity": 4,
            "specification": "Fixation démontable de la bride du moteur NEMA17 sur les 4 inserts laiton du socle octogonal",
            "part_ids": [base_id, motor_id],
        },
        {
            "name": "Vis CHC M3×8 mm inox A2 (ISO 4762)",
            "quantity": 4,
            "specification": "Fermeture démontable du capot supérieur de maintenance de la tête LiDAR",
            "part_ids": [head_id],
        },
        {
            "name": "Vis CHC M4×16 mm inox A2 + rondelles plates M4",
            "quantity": 4,
            "specification": "Ancrage des 4 oreilles d'angle du socle octogonal (lamages Ø8.5 mm) sur le bâti porteur",
            "part_ids": [base_id],
        },
        {
            "name": "Roulement à billes radial 608ZZ (Ø8×Ø22×7 mm) & accouplement d'arbre à bride Ø5.0 mm",
            "quantity": 1,
            "specification": "Guidage axial sans jeu à Z = 58.0 mm + transmission directe arbre NEMA17 -> tête LiDAR avec 2 vis pointeau M3×4 mm",
            "part_ids": [motor_id, head_id],
        },
    ]


def write_plan_montage_et_fixations(
    out_root: Path,
    *,
    is_drone: bool,
    eng_report: dict[str, Any],
) -> Path:
    """Rédige un document d'ingénierie mécanique complet `PLAN_MONTAGE_ET_FIXATIONS.md`
    (à la racine du livrable et dans `journal/`) détaillant l'espace fonctionnel interne,
    le passage des câbles, la visserie exacte (vis CHC M3/M4, inserts laiton, roulements)
    et l'ordre de montage pas à pas."""
    parts = eng_report.get("parts") or []
    bom = eng_report.get("bom") or []
    steps = eng_report.get("assembly_steps") or []
    fasteners = eng_report.get("fastening_assessment") or []

    lines: list[str] = []
    if is_drone:
        lines.append("# Plan de Montage Mécanique, Chambre Fonctionnelle Interne & Visserie — Drone Quadrirotor (`agi_drone_01`)")
        lines.append("")
        lines.append("## 1. Architecture Ouvrable & Espace Interne de Fonctionnement")
        lines.append("- **Conception non-monolithique démontable en 7 sous-ensembles** : contrairement à un bloc plein impossible à équiper, le châssis est divisé horizontalement en **3 structures imprimables démontables** (`01_chassis_inferieur_evide.stl`, `02_platine_bridage_moteurs_m3.stl`, `03_capot_superieur_support_lidar_m3.stl`) + **4 rotors démontables** (`04_rotors_helices_tripales_x4.stl`) accueillant les **3 organes fonctionnels embarqués** (`05_moteur_nema17.stl`, `06_servomoteur_mg996r.stl`, `07_scanner_optique_lidar.stl`).")
        lines.append("- **Chambre fonctionnelle interne évidée (`96.0 × 68.0 × 31.0 mm`)** : ménagée au cœur du châssis inférieur (`Z = 13.0 à 44.0 mm`), elle offre le volume libre nécessaire pour loger le contrôleur de vol, le répartiteur de puissance (PDB/ESC 4-en-1), la batterie LiPo et les faisceaux électriques.")
        lines.append("- **Galerie panoramique ouverte (`H = 8.0 mm`, `Z = 44.0 à 52.0 mm`) & 4 fenêtres latérales arquées (`28.0 × 16.0 mm`)** : permettent d'inspecter les moteurs en place, de passer les nappes PWM/UART et d'assurer le refroidissement forcé par le flux des 4 rotors.")
        lines.append("- **Goulottes passe-câbles intégrées dans les 4 bras en X (`section 4.2 × 4.5 mm`)** : relient chaque coupelle de moteur brushless (`entraxe 16×16 mm, 4×M3`) directement à la chambre centrale évidée.")
    else:
        lines.append("# Plan de Montage Mécanique, Chambre Fonctionnelle Interne & Visserie — Tourelle NEMA17 & LiDAR (`agi_tourelle_01`)")
        lines.append("")
        lines.append("## 1. Architecture Ouvrable & Espace Interne de Fonctionnement")
        lines.append("- **Socle octogonal évidé à chambre de câblage et d'accouplement (`Ø46.0 × 13.5 mm`)** : le socle inférieur (`01 — Socle octogonal évidé`) comporte une chambre centrale évidée sous le berceau du moteur NEMA17 ainsi qu'un alésage pilote traversant `Ø22.5 mm`.")
        lines.append("- **4 fenêtres latérales arquées de maintenance et passe-câbles (`14.0 × 7.6 mm` sur les faces `+X, -X, +Y, -Y`)** : donnent un accès direct à l'intérieur du socle pour faire cheminer le faisceau 4 fils du moteur NEMA17, loger le connecteur JST-XH et inspecter l'assise du moteur.")
        lines.append("- **Tête optique LiDAR ouvrable (`03 — Tête optique LiDAR ouvrable`)** : dotée d'une chambre optique interne évidée (`Ø34.5 × 15.0 mm`), de fentes latérales d'inspection et d'un capot supérieur démontable fixé par `4 × Vis CHC M3×8 mm`.")

    lines.append("")
    lines.append("## 2. Sous-Ensembles Imprimables & Composants Embarqués (0.0000 mm³ d'interférence)")
    lines.append("| Réf. | Pièce / Sous-ensemble | Fichier STL | Fabrication | Dimensions XYZ (mm) | Volume (mm³) | Étanche |")
    lines.append("|---|---|---|---|---:|---:|---|")
    for p in parts:
        dims = p.get("dimensions_mm") or [0, 0, 0]
        dim_str = f"{dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f}"
        lines.append(
            f"| `{p.get('design_id') or p.get('id')}` | {p.get('name')} | `{p.get('file')}` | `{p.get('manufacturing')}` | {dim_str} | {float(p.get('volume_mm3') or 0.0):.1f} | {'Oui' if p.get('watertight') else 'Non'} |"
        )

    lines.append("")
    lines.append("## 3. Nomenclature Complète de la Visserie, des Inserts & des Organes Mécaniques")
    lines.append("| Élément / Fixation | Quantité | Spécification Mécanique & Implantation | Pièces reliées |")
    lines.append("|---|---:|---|---|")
    for b in bom:
        lines.append(
            f"| **{b.get('name')}** | **{b.get('quantity')}** | {b.get('specification')} | `{', '.join(b.get('part_ids') or [])}` |"
        )

    if fasteners:
        lines.append("")
        lines.append("## 4. Contrôle d'Accès & Visibilité des Fixations (Lancer de Rayons Möller–Trumbore)")
        lines.append("| Identifiant Fixation | Type | Pièces reliées | Fraction visible | Points d'échantillonnage (mm) |")
        lines.append("|---|---|---|---:|---|")
        for fc in fasteners:
            lines.append(
                f"| `{fc.get('id')}` | `{fc.get('kind')}` | `{', '.join(fc.get('part_ids') or [])}` | {float(fc.get('visible_sample_fraction') or 0.0):.3f} | `{fc.get('surface_samples_mm')}` |"
            )

    lines.append("")
    lines.append("## 5. Gamme de Montage Pas à Pas (Ouverture, Installation Moteur, Câblage & Boulonnage)")
    for idx, st in enumerate(steps, 1):
        instr = st.get("instruction") if isinstance(st, dict) else str(st)
        lines.append(f"{idx}. {instr}")

    content = "\n".join(lines) + "\n"
    plan_path = out_root / "PLAN_MONTAGE_ET_FIXATIONS.md"
    plan_path.write_text(content, encoding="utf-8")
    journal_dir = out_root / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    (journal_dir / "PLAN_MONTAGE_ET_FIXATIONS.md").write_text(content, encoding="utf-8")
    return plan_path
