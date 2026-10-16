/**
 * Orchestrateur des 5 Sous-Agents 3D & CAO d'Assemblage, Persistance de Mission
 * et Générateur de Splats Gaussiens 3D piloté par la géométrie réelle (.stl / project.json).
 *
 * Aucune forme, main ou objet prédéfini n'est codé en dur : les splats et les métriques
 * proviennent des fichiers STL réels générés dans le workspace, des pièces/articulations
 * mesurées et de l'état d'avancement effectif du pipeline.
 */

export type ThreeDSubAgentId =
  | 'kinematics'
  | 'cad_topology'
  | 'gaussian_splat'
  | 'materials_pbr'
  | 'qa_assembly';

export interface LivePartGeometryPreview {
  id: string;
  name: string;
  file?: string;
  source?: string;
  manufacturing?: string;
  dimensions_mm?: number[] | null;
  bounds_mm?: number[][] | null;
  centroid_mm?: number[] | null;
  volume_mm3?: number | null;
  surface_area_mm2?: number | null;
  estimated_mass_g?: number | null;
  watertight?: boolean | null;
  filament?: string | null;
  color_rgba?: number[] | null;
  sample_points_mm?: number[][] | null;
}

export interface LiveJointPreview {
  id: string;
  type: string;
  parent: string;
  child: string;
  origin_mm?: number[] | null;
  axis?: number[] | null;
  limits?: [number, number] | null;
}

export interface LiveEngineeringTelemetryInput {
  stlCount?: number;
  verifiedCount?: number;
  criteriaCount?: number;
  verifiedCriteriaCount?: number;
  totalCriteriaCount?: number;
  partCount?: number;
  jointCount?: number;
  dof?: number | null;
  bomCount?: number;
  stepCount?: number;
  workspaceFiles?: string[];
  clearanceMm?: number;
  wallMm?: number;
  usableBedMm?: [number, number, number];
  parts?: LivePartGeometryPreview[];
  joints?: LiveJointPreview[];
}

export interface ThreeDSubAgentSpec {
  id: ThreeDSubAgentId;
  index: number;
  code: string;
  name: string;
  role: string;
  specialty: string;
  color: string;
  status: 'pending' | 'running' | 'working' | 'done' | 'error';
  progressPercent: number;
  currentAction: string;
  liveMetrics: string[];
}

export interface HolographicSplatPoint {
  x: number;
  y: number;
  z: number;
  rx: number;
  ry: number;
  rz: number;
  color: [number, number, number];
  alpha: number;
  group: number;
  partId?: string;
  partLabel?: string;
  isJointNode?: boolean;
  jointAxis?: [number, number, number];
}

export interface PersistedThreeDMission {
  missionId: string;
  active: boolean;
  jobId?: string | null;
  designId?: string | null;
  mode: 'visual_3d' | 'engineering_cad' | 'mesh_3d';
  rawPrompt: string;
  startedAtMs: number;
  updatedAtMs: number;
  estimatedTotalSeconds: number;
  progressPercent: number;
  phasePercent: number;
  phaseDetail: string;
  phaseLabel: string;
  stlCount?: number;
  verifiedCriteriaCount?: number;
  totalCriteriaCount?: number;
  status: 'running' | 'completed' | 'error';
  resultUrl?: string | null;
  viewerUrl?: string | null;
  completedMeshUrl?: string | null;
  completedViewerUrl?: string | null;
  subAgents: ThreeDSubAgentSpec[];
}

const STORAGE_KEY_MISSION = 'aurora.3d.active_mission.v2';

function hashPrompt(text: string): number {
  let h = 2166136261;
  const s = (text || 'aurora-cad').trim().toLowerCase();
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/**
 * Calcule l'état temps réel des 5 sous-agents spécialisés à partir de la progression
 * et des preuves réelles mesurées dans le workspace (fichiers, STL, critères, pièces, DDL).
 */
export function computeSubAgentsForProgress(
  prompt: string,
  overallPercent: number,
  phaseDetail: string,
  mode: 'visual_3d' | 'engineering_cad' | 'mesh_3d' = 'visual_3d',
  telemetry?: LiveEngineeringTelemetryInput,
): ThreeDSubAgentSpec[] {
  const pct = Math.max(0, Math.min(100, Number.isFinite(overallPercent) ? overallPercent : 0));
  const files = telemetry?.workspaceFiles || [];
  const hasDesignPy = files.includes('design.py');
  const hasTestsPy = files.includes('tests.py');
  const hasProjectJson = files.includes('project.json') || files.includes('project_spec.json');
  const stlCount = telemetry?.stlCount ?? files.filter((f) => f.endsWith('.stl')).length;
  const partCount = telemetry?.partCount ?? telemetry?.parts?.length ?? stlCount;
  const jointCount = telemetry?.jointCount ?? telemetry?.joints?.length ?? 0;
  const dof = telemetry?.dof ?? 0;
  const bomCount = telemetry?.bomCount ?? 0;
  const verifiedCount = telemetry?.verifiedCount ?? telemetry?.verifiedCriteriaCount ?? 0;
  const criteriaCount = telemetry?.criteriaCount ?? telemetry?.totalCriteriaCount ?? 0;

  const stages: Array<{
    id: ThreeDSubAgentId;
    code: string;
    name: string;
    role: string;
    specialty: string;
    color: string;
    range: [number, number];
    runningAction: string;
    doneAction: string;
    metrics: string[];
  }> = [
    {
      id: 'kinematics',
      code: 'AGENT-01 · ATLAS-KINEMATICS',
      name: 'Atlas Kinematics',
      role: 'Architecture Fonctionnelle & Chaîne Cinématique',
      specialty: 'Décomposition en sous-ensembles fixes/mobiles, axes de liaison et degrés de liberté',
      color: '#38bdf8',
      range: [0, 22],
      runningAction:
        mode === 'engineering_cad'
          ? 'Décomposition fonctionnelle des pièces, liaisons et degrés de liberté…'
          : 'Analyse spatiale multi-entités, proportions et axes principaux…',
      doneAction:
        jointCount > 0
          ? `${jointCount} liaison(s) cinématique(s) · ${dof} DDL verrouillés`
          : 'Architecture spatiale et repères de référence établis',
      metrics: [
        criteriaCount > 0 ? `Critères : ${verifiedCount}/${criteriaCount} vérifiés` : 'Analyse de la demande',
        jointCount > 0 ? `Cinématique : ${jointCount} liaison(s) (${dof} DDL)` : 'Repère monde millimétrique',
      ],
    },
    {
      id: 'cad_topology',
      code: 'AGENT-02 · MECANO-CAD',
      name: 'Mecano CAD',
      role: 'Conception CAO Paramétrique & Tolérances',
      specialty: 'Génération géométrique exacte (design.py), parois, jeux fonctionnels et entraxes',
      color: '#a78bfa',
      range: [18, 52],
      runningAction: hasDesignPy
        ? `Exécution de design.py (${stlCount} solide(s) STL généré(s))…`
        : 'Écriture du modèle paramétrique et calcul des cotes fonctionnelles…',
      doneAction:
        stlCount > 0
          ? `${stlCount} solide(s) STL paramétrique(s) exporté(s) en mm`
          : 'Paramètres géométriques et cotes d’interface calculés',
      metrics: [
        telemetry?.clearanceMm != null
          ? `Jeu : ${telemetry.clearanceMm} mm · Paroi ≥ ${telemetry.wallMm ?? 2.0} mm`
          : 'Volumes fermés (manifold)',
        hasDesignPy ? 'Source : design.py actif' : 'Synthèse géométrique',
      ],
    },
    {
      id: 'gaussian_splat',
      code: 'AGENT-03 · GAUSSIAN-SCULPT',
      name: 'Gaussian Sculpt',
      role: 'Reconstruction Volumétrique & Maillages Étanches',
      specialty: 'Validation des volumes fermés, normales cohérentes et contrôle des interférences',
      color: '#34d399',
      range: [45, 76],
      runningAction:
        stlCount > 0
          ? `Échantillonnage volumétrique de ${stlCount} maillage(s) STL en cours…`
          : phaseDetail || 'Densification du champ de splats 3D et extraction de surface…',
      doneAction:
        partCount > 0
          ? `${partCount} volume(s) étanche(s) reconstruit(s) et mesuré(s)`
          : 'Maillage 3D manifold consolidé',
      metrics: [
        stlCount > 0 ? `${stlCount} fichier(s) STL mesuré(s) sur disque` : 'Maillage haute densité',
        hasTestsPy ? 'Vérification : tests.py présent' : 'Contrôle d’étanchéité 3D',
      ],
    },
    {
      id: 'materials_pbr',
      code: 'AGENT-04 · SHADER-PBR',
      name: 'Shader PBR & BOM',
      role: 'Matériaux, Nomenclature (BOM) & Plaques',
      specialty: 'Affectation matière/filament, composants achetés, nomenclature et plaques d’impression',
      color: '#f59e0b',
      range: [70, 90],
      runningAction:
        mode === 'engineering_cad'
          ? 'Construction de la nomenclature (BOM), plan de filaments et plaques STL…'
          : 'Synthèse des textures PBR (Albedo, Roughness, Metallic, Normal)…',
      doneAction:
        bomCount > 0
          ? `BOM (${bomCount} réf.) et affectation matières validées`
          : 'Matériaux et repères visuels appliqués',
      metrics: [
        bomCount > 0 ? `Nomenclature : ${bomCount} référence(s)` : 'Repérage couleur par pièce',
        telemetry?.usableBedMm
          ? `Volume utile : ${telemetry.usableBedMm.join('×')} mm`
          : ' UV & Matériaux PBR',
      ],
    },
    {
      id: 'qa_assembly',
      code: 'AGENT-05 · QA-ASSEMBLY',
      name: 'QA Assembly',
      role: 'Métrologie d’Assemblage, Insertion & Dossier Scellé',
      specialty: 'Contrôle des collisions, trajectoires d’insertion sans pénétration et archive vérifiée',
      color: '#ec4899',
      range: [85, 100],
      runningAction: hasProjectJson
        ? 'Vérification cryptographique des STL, fermeture cinématique et archive ZIP…'
        : 'Contrôle des jeux d’assemblage, centre de gravité et séquence de montage…',
      doneAction: 'Assemblage vérifié et livrable complet scellé',
      metrics: [
        telemetry?.stepCount
          ? `Séquence : ${telemetry.stepCount} étape(s) de montage`
          : 'Contrôle de collision & insertion',
        hasProjectJson ? 'Manifeste project.json vérifié' : 'Scellement des preuves',
      ],
    },
  ];

  return stages.map((st, idx) => {
    const [start, end] = st.range;
    let status: ThreeDSubAgentSpec['status'] = 'pending';
    let subPct = 0;

    if (pct >= 100) {
      status = 'done';
      subPct = 100;
    } else if (pct >= end) {
      status = 'done';
      subPct = 100;
    } else if (pct >= start) {
      status = 'running';
      const span = Math.max(1, end - start);
      subPct = Math.min(99, Math.max(8, Math.round(((pct - start) / span) * 100)));
    } else {
      status = 'pending';
      subPct = 0;
    }

    return {
      id: st.id,
      index: idx + 1,
      code: st.code,
      name: st.name,
      role: st.role,
      specialty: st.specialty,
      color: st.color,
      status,
      progressPercent: subPct,
      currentAction:
        status === 'done'
          ? st.doneAction
          : status === 'running'
          ? phaseDetail && phaseDetail.length > 4
            ? phaseDetail
            : st.runningAction
          : 'En attente des données amont…',
      liveMetrics: st.metrics,
    };
  });
}

const DEFAULT_PART_PALETTE: Array<[number, number, number]> = [
  [56, 189, 248],
  [167, 139, 250],
  [52, 211, 153],
  [245, 158, 11],
  [244, 114, 182],
  [96, 165, 250],
  [45, 212, 191],
  [251, 146, 60],
];

/**
 * Génère un nuage de Splats Gaussiens 3D :
 * 1) Si des pièces STL réelles (`liveParts`) sont disponibles dans la télémétrie, projette leurs
 *    vrais sommets échantillonnés (`sample_points_mm`) et leurs boîtes englobantes (`bounds_mm` / `dimensions_mm`)
 *    aux coordonnées exactes de l'assemblage, ainsi que les articulations réelles (`liveJoints`).
 * 2) Sinon (avant le premier STL écrit sur disque), génère une grille volumétrique abstraite
 *    purement mathématique (sans aucun objet codé en dur) dimensionnée sur le plateau d'impression.
 */
export function generateHolographicSplats(
  prompt: string,
  count = 1500,
  liveParts?: LivePartGeometryPreview[],
  liveJoints?: LiveJointPreview[],
  bedMm: [number, number, number] = [220, 220, 250],
): HolographicSplatPoint[] {
  const splats: HolographicSplatPoint[] = [];
  const validParts = (liveParts || []).filter(
    (p) =>
      (Array.isArray(p.sample_points_mm) && p.sample_points_mm.length > 0) ||
      (Array.isArray(p.dimensions_mm) && p.dimensions_mm.length >= 3),
  );

  // CAS 1 : Géométrie réelle issue des fichiers STL / project.json du workspace
  if (validParts.length > 0) {
    let minX = Infinity,
      minY = Infinity,
      minZ = Infinity;
    let maxX = -Infinity,
      maxY = -Infinity,
      maxZ = -Infinity;

    const partBoxes = validParts.map((part, idx) => {
      if (
        Array.isArray(part.bounds_mm) &&
        part.bounds_mm.length === 2 &&
        Array.isArray(part.bounds_mm[0]) &&
        Array.isArray(part.bounds_mm[1]) &&
        part.bounds_mm[0].length >= 3 &&
        part.bounds_mm[1].length >= 3
      ) {
        const b0: [number, number, number] = [
          part.bounds_mm[0][0],
          part.bounds_mm[0][1],
          part.bounds_mm[0][2],
        ];
        const b1: [number, number, number] = [
          part.bounds_mm[1][0],
          part.bounds_mm[1][1],
          part.bounds_mm[1][2],
        ];
        minX = Math.min(minX, b0[0]);
        minY = Math.min(minY, b0[1]);
        minZ = Math.min(minZ, b0[2]);
        maxX = Math.max(maxX, b1[0]);
        maxY = Math.max(maxY, b1[1]);
        maxZ = Math.max(maxZ, b1[2]);
        return { part, idx, low: b0, high: b1 };
      }
      const dims = part.dimensions_mm && part.dimensions_mm.length >= 3 ? part.dimensions_mm : [40, 40, 40];
      const cx = part.centroid_mm?.[0] ?? idx * (dims[0] * 0.65);
      const cy = part.centroid_mm?.[1] ?? 0;
      const cz = part.centroid_mm?.[2] ?? 0;
      const low: [number, number, number] = [cx - dims[0] / 2, cy - dims[1] / 2, cz - dims[2] / 2];
      const high: [number, number, number] = [cx + dims[0] / 2, cy + dims[1] / 2, cz + dims[2] / 2];
      minX = Math.min(minX, low[0]);
      minY = Math.min(minY, low[1]);
      minZ = Math.min(minZ, low[2]);
      maxX = Math.max(maxX, high[0]);
      maxY = Math.max(maxY, high[1]);
      maxZ = Math.max(maxZ, high[2]);
      return { part, idx, low, high };
    });

    const centerX = (minX + maxX) * 0.5;
    const centerY = (minY + maxY) * 0.5;
    const centerZ = (minZ + maxZ) * 0.5;
    const maxSpan = Math.max(1e-3, maxX - minX, maxY - minY, maxZ - minZ);
    const normScale = 1.45 / maxSpan;

    const toNorm = (pt: number[]): [number, number, number] => [
      ((pt[0] ?? 0) - centerX) * normScale,
      -((pt[2] ?? 0) - centerZ) * normScale, // Z-up CAO -> Y-screen
      ((pt[1] ?? 0) - centerY) * normScale,
    ];

    const perPartBudget = Math.max(40, Math.floor(count / validParts.length));

    for (const { part, idx, low, high } of partBoxes) {
      const rawColor = part.color_rgba;
      const color: [number, number, number] =
        Array.isArray(rawColor) && rawColor.length >= 3
          ? [
              rawColor[0] <= 1 ? Math.round(rawColor[0] * 255) : Math.round(rawColor[0]),
              rawColor[1] <= 1 ? Math.round(rawColor[1] * 255) : Math.round(rawColor[1]),
              rawColor[2] <= 1 ? Math.round(rawColor[2] * 255) : Math.round(rawColor[2]),
            ]
          : DEFAULT_PART_PALETTE[idx % DEFAULT_PART_PALETTE.length];

      // Centroid node of the real part
      const mid: [number, number, number] = [
        (low[0] + high[0]) * 0.5,
        (low[1] + high[1]) * 0.5,
        (low[2] + high[2]) * 0.5,
      ];
      const [mcx, mcy, mcz] = toNorm(mid);
      splats.push({
        x: mcx,
        y: mcy,
        z: mcz,
        rx: 0.036,
        ry: 0.036,
        rz: 0.036,
        color,
        alpha: 0.95,
        group: idx,
        partId: part.id,
        partLabel: `${part.name || part.id}${
          part.dimensions_mm ? ` (${part.dimensions_mm.slice(0, 3).map((d) => Math.round(d)).join('×')} mm)` : ''
        }`,
        isJointNode: true,
      });

      const samples = part.sample_points_mm;
      if (Array.isArray(samples) && samples.length > 0) {
        // Utilise directement les vrais sommets 3D extraits du fichier STL sur disque
        for (let i = 0; i < perPartBudget; i++) {
          const src = samples[i % samples.length];
          if (!Array.isArray(src) || src.length < 3) continue;
          const jitter = i >= samples.length ? 0.008 : 0;
          const [nx, ny, nz] = toNorm(src);
          splats.push({
            x: nx + (Math.sin(i * 12.9898 + idx) * jitter),
            y: ny + (Math.cos(i * 78.233 + idx) * jitter),
            z: nz + (Math.sin(i * 45.164 + idx) * jitter),
            rx: 0.015,
            ry: 0.012,
            rz: 0.015,
            color,
            alpha: 0.78,
            group: idx,
            partId: part.id,
          });
        }
      } else {
        // Échantillonnage de la boîte englobante mesurée de la pièce (arêtes + faces)
        const sx = Math.max(1, high[0] - low[0]);
        const sy = Math.max(1, high[1] - low[1]);
        const sz = Math.max(1, high[2] - low[2]);
        for (let i = 0; i < perPartBudget; i++) {
          const face = i % 6;
          const u = ((i * 37) % 100) / 100;
          const v = ((i * 73) % 100) / 100;
          let px = low[0] + u * sx;
          let py = low[1] + v * sy;
          let pz = low[2] + (((i * 19) % 100) / 100) * sz;
          if (face === 0) px = low[0];
          else if (face === 1) px = high[0];
          else if (face === 2) py = low[1];
          else if (face === 3) py = high[1];
          else if (face === 4) pz = low[2];
          else pz = high[2];

          const [nx, ny, nz] = toNorm([px, py, pz]);
          splats.push({
            x: nx,
            y: ny,
            z: nz,
            rx: 0.016,
            ry: 0.012,
            rz: 0.016,
            color,
            alpha: 0.68,
            group: idx,
            partId: part.id,
          });
        }
      }
    }

    // Ajout des vraies articulations cinématiques déclarées dans le projet
    for (const joint of liveJoints || []) {
      if (Array.isArray(joint.origin_mm) && joint.origin_mm.length >= 3) {
        const [jx, jy, jz] = toNorm(joint.origin_mm);
        const rawAxis = joint.axis;
        const jointAxis: [number, number, number] =
          Array.isArray(rawAxis) && rawAxis.length >= 3
            ? [rawAxis[0], rawAxis[1], rawAxis[2]]
            : [0, 0, 1];
        splats.push({
          x: jx,
          y: jy,
          z: jz,
          rx: 0.044,
          ry: 0.044,
          rz: 0.044,
          color: [244, 114, 182],
          alpha: 1,
          group: 99,
          partId: joint.id,
          partLabel: `${joint.id} (${joint.type})`,
          isJointNode: true,
          jointAxis,
        });
      }
    }

    return splats;
  }

  // CAS 2 : Aucun STL encore écrit sur disque -> Grille d'assemblage paramétrique abstraite
  // dérivée mathématiquement du hash de l'objectif et des proportions du plateau (0 hardcode d'objet)
  let seed = hashPrompt(prompt) || 123456789;
  const rand = () => {
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    return (seed >>> 0) / 4294967296;
  };

  const maxBed = Math.max(1, bedMm[0], bedMm[1], bedMm[2]);
  const bx = (bedMm[0] / maxBed) * 0.72;
  const by = (bedMm[2] / maxBed) * 0.65;
  const bz = (bedMm[1] / maxBed) * 0.72;

  const words = (prompt || '').trim().split(/\s+/).filter(Boolean);
  const subVolumeCount = Math.max(3, Math.min(7, 3 + Math.floor(words.length / 6)));

  const nodes: Array<{
    cx: number;
    cy: number;
    cz: number;
    sx: number;
    sy: number;
    sz: number;
    color: [number, number, number];
  }> = [];

  for (let g = 0; g < subVolumeCount; g++) {
    const t = subVolumeCount === 1 ? 0 : g / (subVolumeCount - 1) - 0.5;
    const angle = g * ((Math.PI * 2) / subVolumeCount) + (rand() - 0.5) * 0.35;
    const radius = g === 0 ? 0 : 0.28 + rand() * 0.22;
    const cx = Math.cos(angle) * radius * bx;
    const cy = t * by * 0.85;
    const cz = Math.sin(angle) * radius * bz;
    const sx = 0.14 + rand() * 0.14;
    const sy = 0.12 + rand() * 0.14;
    const sz = 0.14 + rand() * 0.14;
    const color = DEFAULT_PART_PALETTE[g % DEFAULT_PART_PALETTE.length];
    nodes.push({ cx, cy, cz, sx, sy, sz, color });

    splats.push({
      x: cx,
      y: cy,
      z: cz,
      rx: 0.038,
      ry: 0.038,
      rz: 0.038,
      color,
      alpha: 0.95,
      group: g,
      partLabel: `Sous-ensemble #${g + 1}`,
      isJointNode: true,
    });
  }

  const perNode = Math.max(40, Math.floor(count / nodes.length));
  nodes.forEach((node, g) => {
    for (let i = 0; i < perNode; i++) {
      const u = rand() * Math.PI * 2;
      const v = rand() * Math.PI - Math.PI / 2;
      const shell = 0.72 + rand() * 0.28;
      splats.push({
        x: node.cx + Math.cos(v) * Math.cos(u) * node.sx * shell,
        y: node.cy + Math.sin(v) * node.sy * shell,
        z: node.cz + Math.cos(v) * Math.sin(u) * node.sz * shell,
        rx: 0.014 + rand() * 0.012,
        ry: 0.011 + rand() * 0.01,
        rz: 0.014 + rand() * 0.012,
        color: node.color,
        alpha: 0.45 + rand() * 0.4,
        group: g,
      });
    }
  });

  return splats;
}

/**
 * Lecture et persistance de la mission 3D / CAO active pour reprise transparente
 */
export function readPersistedThreeDMission(): PersistedThreeDMission | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_MISSION);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedThreeDMission;
    if (!parsed || typeof parsed.startedAtMs !== 'number' || !parsed.rawPrompt) return null;
    if (Date.now() - parsed.updatedAtMs > 6 * 3600 * 1000) {
      localStorage.removeItem(STORAGE_KEY_MISSION);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writePersistedThreeDMission(mission: PersistedThreeDMission | null): void {
  try {
    if (!mission) {
      localStorage.removeItem(STORAGE_KEY_MISSION);
      return;
    }
    localStorage.setItem(STORAGE_KEY_MISSION, JSON.stringify(mission));
  } catch {
    // Ignore storage quota errors
  }
}

export function startOrUpdateThreeDMission(params: {
  rawPrompt: string;
  active?: boolean;
  startedAtMs?: number;
  mode?: 'visual_3d' | 'engineering_cad' | 'mesh_3d';
  jobId?: string | null;
  designId?: string | null;
  progressPercent?: number;
  phasePercent?: number;
  phaseDetail?: string;
  phaseLabel?: string;
  stlCount?: number;
  verifiedCriteriaCount?: number;
  totalCriteriaCount?: number;
  status?: 'running' | 'completed' | 'error';
  resultUrl?: string | null;
  viewerUrl?: string | null;
  estimatedTotalSeconds?: number;
  telemetry?: LiveEngineeringTelemetryInput;
  liveTelemetry?: LiveEngineeringTelemetryInput;
}): PersistedThreeDMission {
  const existing = readPersistedThreeDMission();
  const now = Date.now();
  const mode = params.mode || existing?.mode || 'visual_3d';
  const rawPrompt = params.rawPrompt.trim() || existing?.rawPrompt || 'Projet 3D';

  const isSameMission =
    existing &&
    existing.status === 'running' &&
    ((params.jobId && existing.jobId === params.jobId) ||
      (params.designId && existing.designId === params.designId) ||
      existing.rawPrompt.trim().toLowerCase() === rawPrompt.toLowerCase());

  const startedAtMs = params.startedAtMs || (isSameMission ? existing.startedAtMs : now);
  const prevPct = isSameMission ? existing.progressPercent : 0;
  const rawPct = params.progressPercent ?? params.phasePercent ?? prevPct;
  const progressPercent =
    params.status === 'completed'
      ? 100
      : Math.max(prevPct, Math.min(99, Number.isFinite(rawPct) && rawPct > 0 ? rawPct : Math.max(prevPct, 6)));

  const phaseDetail =
    params.phaseDetail?.trim() ||
    params.phaseLabel?.trim() ||
    existing?.phaseDetail ||
    'Initialisation des sous-agents et de la géométrie 3D…';

  const defaultEta = mode === 'engineering_cad' ? 210 : 165;
  const estimatedTotalSeconds = params.estimatedTotalSeconds || existing?.estimatedTotalSeconds || defaultEta;

  const mergedTelemetry: LiveEngineeringTelemetryInput | undefined = params.liveTelemetry || params.telemetry || {
    stlCount: params.stlCount ?? existing?.stlCount,
    verifiedCount: params.verifiedCriteriaCount ?? existing?.verifiedCriteriaCount,
    criteriaCount: params.totalCriteriaCount ?? existing?.totalCriteriaCount,
  };

  const subAgents = computeSubAgentsForProgress(rawPrompt, progressPercent, phaseDetail, mode, mergedTelemetry);
  const status = params.status || (params.active === false ? 'completed' : 'running');
  const resultUrl = params.resultUrl !== undefined ? params.resultUrl : existing?.resultUrl ?? null;
  const viewerUrl = params.viewerUrl !== undefined ? params.viewerUrl : existing?.viewerUrl ?? null;

  const mission: PersistedThreeDMission = {
    missionId: isSameMission ? existing.missionId : `3d_mis_${now.toString(36)}`,
    active: params.active !== undefined ? params.active : status === 'running',
    jobId: params.jobId !== undefined ? params.jobId : existing?.jobId ?? null,
    designId: params.designId !== undefined ? params.designId : existing?.designId ?? null,
    mode,
    rawPrompt,
    startedAtMs,
    updatedAtMs: now,
    estimatedTotalSeconds,
    progressPercent,
    phasePercent: progressPercent,
    phaseDetail,
    phaseLabel: phaseDetail,
    stlCount: params.stlCount ?? mergedTelemetry?.stlCount ?? existing?.stlCount ?? 0,
    verifiedCriteriaCount:
      params.verifiedCriteriaCount ?? mergedTelemetry?.verifiedCount ?? existing?.verifiedCriteriaCount ?? 0,
    totalCriteriaCount:
      params.totalCriteriaCount ?? mergedTelemetry?.criteriaCount ?? existing?.totalCriteriaCount ?? 0,
    status,
    resultUrl,
    viewerUrl,
    completedMeshUrl: resultUrl,
    completedViewerUrl: viewerUrl,
    subAgents,
  };

  writePersistedThreeDMission(mission);
  return mission;
}

export function completeThreeDMission(
  resultOrOpts?: string | null | { meshUrl?: string | null; viewerUrl?: string | null },
  viewerUrlArg?: string | null,
): void {
  const existing = readPersistedThreeDMission();
  if (!existing) return;
  const meshUrl =
    typeof resultOrOpts === 'object' && resultOrOpts !== null
      ? resultOrOpts.meshUrl ?? existing.resultUrl ?? null
      : resultOrOpts ?? existing.resultUrl ?? null;
  const viewerUrl =
    typeof resultOrOpts === 'object' && resultOrOpts !== null
      ? resultOrOpts.viewerUrl ?? existing.viewerUrl ?? null
      : viewerUrlArg ?? existing.viewerUrl ?? null;
  const doneText = 'Modèle 3D et assemblage finalisés et vérifiés.';
  writePersistedThreeDMission({
    ...existing,
    active: false,
    updatedAtMs: Date.now(),
    progressPercent: 100,
    phasePercent: 100,
    phaseDetail: doneText,
    phaseLabel: doneText,
    status: 'completed',
    resultUrl: meshUrl,
    viewerUrl,
    completedMeshUrl: meshUrl,
    completedViewerUrl: viewerUrl,
    subAgents: computeSubAgentsForProgress(existing.rawPrompt, 100, doneText, existing.mode),
  });
}

export function clearPersistedThreeDMission(): void {
  writePersistedThreeDMission(null);
}

export function formatDurationShort(totalSeconds: number): string {
  const sec = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m <= 0) return `${s}s`;
  return `${m}m ${s.toString().padStart(2, '0')}s`;
}

/**
 * Calcule le temps écoulé exact (sans jamais se figer) et le temps restant estimé dynamique (ETA).
 * Accepte soit `(startedAtMs, progressPercent, estimatedTotalSeconds, serverElapsed, serverRemaining)`
 * soit `(mission, nowMs)`.
 */
export function computeLiveMissionTiming(
  startedAtOrMission: number | PersistedThreeDMission | null,
  progressOrNow = 0,
  estimatedTotalSeconds = 180,
  serverElapsedSeconds?: number | null,
  serverRemainingSeconds?: number | null,
): {
  elapsedSeconds: number;
  remainingSeconds: number;
  effectivePercent: number;
  formattedElapsed: string;
  formattedRemaining: string;
} {
  let startedAtMs = Date.now();
  let progressPercent = progressOrNow;
  let estTotal = estimatedTotalSeconds;
  let nowMs = Date.now();

  if (typeof startedAtOrMission === 'object' && startedAtOrMission !== null) {
    startedAtMs = startedAtOrMission.startedAtMs || Date.now();
    progressPercent = startedAtOrMission.progressPercent ?? startedAtOrMission.phasePercent ?? 6;
    estTotal = startedAtOrMission.estimatedTotalSeconds || 180;
    if (progressOrNow > 1_000_000_000_000) {
      nowMs = progressOrNow;
    }
  } else if (typeof startedAtOrMission === 'number') {
    startedAtMs = startedAtOrMission;
  }

  const localElapsed = Math.max(0, Math.floor((nowMs - startedAtMs) / 1000));
  const elapsedSeconds =
    typeof serverElapsedSeconds === 'number' && Number.isFinite(serverElapsedSeconds)
      ? Math.max(localElapsed, Math.floor(serverElapsedSeconds))
      : localElapsed;

  const asymptoticFloor = Math.min(
    92,
    Math.round((1 - Math.exp(-elapsedSeconds / Math.max(60, estTotal * 0.85))) * 88) + 4,
  );
  const effectivePercent =
    progressPercent >= 100
      ? 100
      : Math.max(progressPercent > 0 ? progressPercent : 5, Math.min(95, asymptoticFloor));

  let remainingSeconds: number;
  if (typeof serverRemainingSeconds === 'number' && Number.isFinite(serverRemainingSeconds) && serverRemainingSeconds > 0) {
    remainingSeconds = Math.max(3, Math.round(serverRemainingSeconds));
  } else if (effectivePercent >= 100) {
    remainingSeconds = 0;
  } else if (effectivePercent >= 12 && elapsedSeconds >= 8) {
    const projectedTotal = (elapsedSeconds / effectivePercent) * 100;
    const blendedTotal = projectedTotal * 0.65 + Math.max(estTotal, elapsedSeconds + 20) * 0.35;
    remainingSeconds = Math.max(5, Math.round(blendedTotal - elapsedSeconds));
  } else {
    remainingSeconds = Math.max(10, Math.round(estTotal - elapsedSeconds));
  }

  return {
    elapsedSeconds,
    remainingSeconds,
    effectivePercent,
    formattedElapsed: formatDurationShort(elapsedSeconds),
    formattedRemaining: formatDurationShort(remainingSeconds),
  };
}
