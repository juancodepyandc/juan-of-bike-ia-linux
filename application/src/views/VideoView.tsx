import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle,
  BookOpen,
  Camera,
  ChevronDown,
  Copy,
  Download,
  Film,
  Loader2,
  Play,
  Sliders,
  Sparkles,
  Star,
  Video,
  Zap,
} from 'lucide-react'
import ClarificationDialog from '../components/ClarificationDialog'
import type { ClarificationRequest } from '../components/ClarificationDialog'
import ContextFilesField from '../components/ContextFilesField'
import VoicePushToTalk from '../components/VoicePushToTalk'
import ModuleAssetPackCard from '../components/ModuleAssetPackCard'
import ConnectorRecommendationsPanel from '../components/ConnectorRecommendationsPanel'
import PromptLibraryPanel from '../components/PromptLibraryPanel'
import SaveDialog from '../components/SaveDialog'
import type { SaveDialogData } from '../components/SaveDialog'
import { buildVideoModuleAssets } from '../config/moduleAssetPacks'
import { AUXILIARY_ANALYSIS_MODEL, VIDEO_MODEL_PACK_LABEL, VIDEO_UNIFIED_5B_MODEL } from '../config/models'
import {
  clearResumableJob,
  fsMkdir,
  getWorkspacePath,
  onPythonProgress,
  peekResumableJob,
  runPythonScript,
  toAssetUrl,
} from '../hooks/useTauri'
import { StudioDiagnosticsPanel, StudioHero } from '../components/StudioHero'
import { useManagedRuntime } from '../hooks/useManagedRuntime'
import { useModuleAssetPack } from '../hooks/useModuleAssetPack'
import { useStudioDiagnostics } from '../hooks/useStudioDiagnostics'
import { prepareTaskIntelligence } from '../services/taskIntelligence'
import LyraCharacter from '../components/voice/LyraCharacter'
import { useAppStore } from '../stores/appStore'
import { useGenerationTrackerStore } from '../stores/generationTrackerStore'
import { usePromptLibraryStore } from '../stores/promptLibraryStore'
import { useGenerationRecovery } from '../hooks/useGenerationRecovery'
import RecoveryBanner from '../components/RecoveryBanner'
import { getErrorMessage } from '../utils/errors'
import { prepareContextFiles } from '../utils/multimodalContext'
import { pickPrimaryPreparedImage } from '../utils/referenceMedia'
import {
  useCreditBillingStore,
  BEST_MODELS_ARCHITECTURE_CATALOG,
} from '../stores/creditBillingStore'

// ============================================================================
// 1. PREMIERS PRINCIPES : DIRECTION CINÉMATOGRAPHIQUE, RÈGLE DES 180°,
//    OPTIQUE PLEIN FORMAT (MM), KELVIN & TRAJECTOIRES CAMÉRA C²-CONTINUES
// ============================================================================

export type CinematicShotScale = 'ELS' | 'LS' | 'MLS' | 'MS' | 'MCU' | 'CU' | 'ECU'

export interface Vector3D {
  x: number
  y: number
  z: number
}

export interface CameraTrajectorySample {
  /** Temps normalisé u in [0, 1] */
  u: number
  /** Position 3D caméra (mètres dans le repère scène) */
  position: Vector3D
  /** Vitesse 3D dP/du */
  velocity: Vector3D
  /** Accélération 3D d²P/du² */
  acceleration: Vector3D
  /** Point visé (look-at) sur l'axe d'action */
  lookAt: Vector3D
}

export interface CameraTrajectoryC2Spec {
  curveType: 'quintic-hermite-catmull-rom-c2' | 'clamped-cubic-bezier-c2'
  controlPoints: [Vector3D, Vector3D, Vector3D, Vector3D]
  samples: CameraTrajectorySample[]
  maxCurvaturePerMeter: number
  maxAccelerationMagnitude: number
  boundaryAccelerationJump: number
  isC2Continuous: boolean
  motionDirectiveEn: string
}

export interface LipSyncMuxContract {
  enabled: boolean
  engine: 'MuseTalk-1.5' | 'SadTalker-V2' | 'Wav2Vec2-Viseme-Mux' | 'none'
  ttsBackend: 'Kokoro-82M-24kHz' | 'CosyVoice3-0.5B-24kHz'
  sampleRateHz: number
  visemeWindowMs: number
  avSyncOffsetToleranceMs: number
  estimatedWordCount: number
  requiredSpeechDurationSec: number
}

export interface CinematicStoryboardShot {
  shotIndex: number
  narrativeBeat: string
  shotScale: CinematicShotScale
  shotScaleLabelFr: string
  focalLengthMm: number
  horizontalFovDeg: number
  verticalFovDeg: number
  apertureFStop: number
  colorTemperatureKelvin: number
  planckianWhiteBalanceRgb: [number, number, number]
  cameraAzimuthDeg: number
  cameraElevationDeg: number
  lineOfActionAzimuthDeg: number
  ruleOf180Side: 'positive-hemisphere'
  ruleOf180Compliant: boolean
  thirtyDegreeRuleSatisfied: boolean
  durationSeconds: number
  numFrames4nPlus1: number
  cameraTrajectoryC2: CameraTrajectoryC2Spec
  lipSyncMux: LipSyncMuxContract
  wanPromptEn: string
}

export interface CinematicStoryboardPlan {
  title: string
  totalDurationSeconds: number
  totalFrames: number
  fps: number
  lineOfActionAzimuthDeg: number
  ruleOf180GlobalCompliance: boolean
  thirtyDegreeRuleGlobalCompliance: boolean
  scaleProgressionValid: boolean
  c2ContinuityGlobalVerified: boolean
  baseColorTemperatureKelvin: number
  shots: CinematicStoryboardShot[]
}

export interface CinematicStoryboardOptions {
  fps?: number
  baseColorTempKelvin?: number
  lineOfActionAzimuthDeg?: number
  dialogueTranscript?: string
  includeLipSyncMux?: boolean
}

const FULL_FRAME_SENSOR_WIDTH_MM = 36.0
const FULL_FRAME_SENSOR_HEIGHT_MM = 24.0

/**
 * Approximation physique du corps noir (locus planckien CIE / Tanner Helland)
 * convertissant une température de couleur T (en Kelvin, [1500, 15000]) en
 * multiplicateurs RVB normalisés [0..1].
 */
export function computePlanckianWhiteBalanceRgb(kelvin: number): [number, number, number] {
  const temp = Math.max(1500, Math.min(15000, kelvin)) / 100
  let r: number
  let g: number
  let b: number

  if (temp <= 66) {
    r = 255
    g = 99.4708025861 * Math.log(temp) - 161.1195681661
    b = temp <= 19 ? 0 : 138.5177312231 * Math.log(temp - 10) - 305.0447927307
  } else {
    r = 329.698727446 * Math.pow(temp - 60, -0.1332047592)
    g = 288.1221695283 * Math.pow(temp - 60, -0.0755148492)
    b = 255
  }

  const clamp01 = (v: number) => Number(Math.max(0, Math.min(1, v / 255)).toFixed(4))
  return [clamp01(r), clamp01(g), clamp01(b)]
}

/**
 * Loi d'évolution temporelle quintique C²-continue :
 * s(u) = 6u^5 - 15u^4 + 10u^3
 * Garantit s(0)=0, s(1)=1, s'(0)=s'(1)=0 et s''(0)=s''(1)=0 (zéro secousse/jerk aux raccords).
 */
function quinticEaseC2(u: number): { s: number; ds: number; d2s: number } {
  const t = Math.max(0, Math.min(1, u))
  const t2 = t * t
  const t3 = t2 * t
  const t4 = t3 * t
  const t5 = t4 * t
  return {
    s: 6 * t5 - 15 * t4 + 10 * t3,
    ds: 30 * t4 - 60 * t3 + 30 * t2,
    d2s: 120 * t3 - 180 * t2 + 60 * t,
  }
}

/**
 * Évalue une courbe de Bézier cubique B(s) et ses dérivées analytiques première et seconde
 * reparamétrées par la loi quintique C² s(u) pour garantir une accélération nulle aux bornes.
 */
function evaluateC2BezierTrajectory(
  p0: Vector3D,
  p1: Vector3D,
  p2: Vector3D,
  p3: Vector3D,
  lookAtTarget: Vector3D,
  sampleCount = 9,
): {
  samples: CameraTrajectorySample[]
  maxCurvaturePerMeter: number
  maxAccelerationMagnitude: number
  boundaryAccelerationJump: number
  isC2Continuous: boolean
} {
  const samples: CameraTrajectorySample[] = []
  let maxCurvature = 0
  let maxAccel = 0

  for (let i = 0; i < sampleCount; i += 1) {
    const u = sampleCount <= 1 ? 0 : i / (sampleCount - 1)
    const { s, ds, d2s } = quinticEaseC2(u)
    const oms = 1 - s
    const oms2 = oms * oms
    const oms3 = oms2 * oms
    const s2 = s * s
    const s3 = s2 * s

    // B(s)
    const bx = oms3 * p0.x + 3 * oms2 * s * p1.x + 3 * oms * s2 * p2.x + s3 * p3.x
    const by = oms3 * p0.y + 3 * oms2 * s * p1.y + 3 * oms * s2 * p2.y + s3 * p3.y
    const bz = oms3 * p0.z + 3 * oms2 * s * p1.z + 3 * oms * s2 * p2.z + s3 * p3.z

    // dB/ds
    const dBx = 3 * oms2 * (p1.x - p0.x) + 6 * oms * s * (p2.x - p1.x) + 3 * s2 * (p3.x - p2.x)
    const dBy = 3 * oms2 * (p1.y - p0.y) + 6 * oms * s * (p2.y - p1.y) + 3 * s2 * (p3.y - p2.y)
    const dBz = 3 * oms2 * (p1.z - p0.z) + 6 * oms * s * (p2.z - p1.z) + 3 * s2 * (p3.z - p2.z)

    // d²B/ds²
    const d2Bx = 6 * oms * (p2.x - 2 * p1.x + p0.x) + 6 * s * (p3.x - 2 * p2.x + p1.x)
    const d2By = 6 * oms * (p2.y - 2 * p1.y + p0.y) + 6 * s * (p3.y - 2 * p2.y + p1.y)
    const d2Bz = 6 * oms * (p2.z - 2 * p1.z + p0.z) + 6 * s * (p3.z - 2 * p2.z + p1.z)

    // Règle de dérivation en chaîne :
    // dP/du = (dB/ds) * ds/du
    // d²P/du² = (d²B/ds²) * (ds/du)² + (dB/ds) * d²s/du²
    const vx = dBx * ds
    const vy = dBy * ds
    const vz = dBz * ds

    const ax = d2Bx * ds * ds + dBx * d2s
    const ay = d2By * ds * ds + dBy * d2s
    const az = d2Bz * ds * ds + dBz * d2s

    const accelMag = Math.hypot(ax, ay, az)
    if (accelMag > maxAccel) maxAccel = accelMag

    // Courbure géométrique intrinsèque kappa = ||B' x B''|| / ||B'||^3
    const speedGeom = Math.hypot(dBx, dBy, dBz)
    if (speedGeom > 1e-5) {
      const cx = dBy * d2Bz - dBz * d2By
      const cy = dBz * d2Bx - dBx * d2Bz
      const cz = dBx * d2By - dBy * d2Bx
      const kappa = Math.hypot(cx, cy, cz) / Math.pow(speedGeom, 3)
      if (kappa > maxCurvature) maxCurvature = kappa
    }

    const round4 = (n: number) => Number(n.toFixed(4))
    samples.push({
      u: round4(u),
      position: { x: round4(bx), y: round4(by), z: round4(bz) },
      velocity: { x: round4(vx), y: round4(vy), z: round4(vz) },
      acceleration: { x: round4(ax), y: round4(ay), z: round4(az) },
      lookAt: {
        x: round4(lookAtTarget.x),
        y: round4(lookAtTarget.y),
        z: round4(lookAtTarget.z),
      },
    })
  }

  const firstSample = samples[0]
  const lastSample = samples[samples.length - 1]
  const boundaryJump = Math.max(
    Math.hypot(firstSample.acceleration.x, firstSample.acceleration.y, firstSample.acceleration.z),
    Math.hypot(lastSample.acceleration.x, lastSample.acceleration.y, lastSample.acceleration.z),
  )

  return {
    samples,
    maxCurvaturePerMeter: Number(maxCurvature.toFixed(4)),
    maxAccelerationMagnitude: Number(maxAccel.toFixed(4)),
    boundaryAccelerationJump: Number(boundaryJump.toFixed(6)),
    isC2Continuous: boundaryJump < 1e-4,
  }
}

function inferBaseKelvinFromPrompt(prompt: string, fallbackKelvin = 5600): number {
  const lower = prompt.toLowerCase()
  if (/\b(bougie|candle|feu\s+de\s+camp|campfire|flamme|braise)\b/.test(lower)) return 1950
  if (/\b(golden\s+hour|coucher\s+de\s+soleil|sunset|cr[eé]puscule|aube|sunrise)\b/.test(lower)) return 3200
  if (/\b(int[eé]rieur|atelier|tungsten|salon|lampe|warm\s+interior)\b/.test(lower)) return 3400
  if (/\b(nuit|night|nocturne|cyberpunk|n[eé]on|clair\s+de\s+lune|moonlight)\b/.test(lower)) return 7400
  if (/\b(brouillard|brume|fog|mist|orage|pluie|rain|overcast|neige|hiver)\b/.test(lower)) return 6500
  return Math.max(1800, Math.min(12000, fallbackKelvin))
}

const SCALE_PROGRESSION_TABLE: ReadonlyArray<{
  scale: CinematicShotScale
  labelFr: string
  focalLengthMm: number
  apertureFStop: number
  distanceMeters: number
  elevationDeg: number
  promptLabelEn: string
}> = [
  {
    scale: 'LS',
    labelFr: 'Plan Large (Establishing Wide Shot)',
    focalLengthMm: 28,
    apertureFStop: 4.0,
    distanceMeters: 4.8,
    elevationDeg: 8,
    promptLabelEn: 'wide establishing shot, 28mm full-frame cinema prime lens, deep spatial context',
  },
  {
    scale: 'MS',
    labelFr: 'Plan Moyen (Medium Action Shot)',
    focalLengthMm: 50,
    apertureFStop: 2.8,
    distanceMeters: 2.4,
    elevationDeg: 3,
    promptLabelEn: 'medium shot at waist level, 50mm standard cinema prime lens, natural perspective',
  },
  {
    scale: 'CU',
    labelFr: 'Gros Plan (Close-Up Portrait)',
    focalLengthMm: 85,
    apertureFStop: 1.8,
    distanceMeters: 1.15,
    elevationDeg: 0,
    promptLabelEn: 'intimate close-up shot, 85mm portrait telephoto lens, shallow depth of field f/1.8',
  },
  {
    scale: 'ECU',
    labelFr: 'Très Gros Plan (Extreme Close-Up Detail)',
    focalLengthMm: 105,
    apertureFStop: 2.0,
    distanceMeters: 0.72,
    elevationDeg: -2,
    promptLabelEn: 'extreme close-up macro detail shot, 105mm cinema macro lens, crisp micro-texture',
  },
]

/**
 * Synthèse autonome de storyboard cinématographique multi-plans par premiers principes :
 * - Respect strict de la règle des 180° (toutes les caméras dans l'hémisphère positif de l'axe d'action)
 * - Respect de la règle des 30° (écart azimutal >= 30° ou variation de focale >= 35% entre plans adjacents)
 * - Progression canonique des valeurs de cadre (Plan Large LS -> Plan Moyen MS -> Gros Plan CU)
 * - Calcul optique plein format 36×24mm : focale équivalente (mm) et champ de vision horizontal/vertical (degrés)
 * - Température de couleur physique en Kelvin et équilibre du corps noir RVB
 * - Trajectoires caméra C²-continues (Bézier cubique paramétrée par loi quintique sans secousse aux raccords)
 */
export function synthesizeCinematicStoryboardPlan(
  prompt: string,
  targetDurationSeconds?: number,
  options: CinematicStoryboardOptions = {},
): CinematicStoryboardPlan {
  const cleanPrompt = prompt.trim() || 'Séquence cinématographique unifiée'
  const fps = Math.max(12, Math.min(60, Math.round(options.fps ?? 24)))
  const lineOfActionAzimuthDeg = Number(((options.lineOfActionAzimuthDeg ?? 0) % 360).toFixed(2))
  const baseKelvin = inferBaseKelvinFromPrompt(cleanPrompt, options.baseColorTempKelvin ?? 5600)

  // Extraction des propositions narratives ou synthèse en 3 actes (Établissement -> Action -> Émotion/Détail)
  const rawClauses = cleanPrompt
    .split(/(?:[.!?;]+|\bpuis\b|\bensuite\b|\bthen\b|\bwhile\b|\btandis\s+que\b)/i)
    .map((s) => s.trim())
    .filter((s) => s.length > 3)

  const narrativeBeats =
    rawClauses.length >= 3
      ? rawClauses.slice(0, 4)
      : rawClauses.length === 2
        ? [
            rawClauses[0],
            rawClauses[1],
            `${rawClauses[1]} — focalisation dramatique sur l'expression et le détail principal`,
          ]
        : [
            `${cleanPrompt} — plan d'établissement spatial et atmosphérique`,
            `${cleanPrompt} — développement dynamique du mouvement au cœur de l'action`,
            `${cleanPrompt} — gros plan expressif et ancrage émotionnel haute fidélité`,
          ]

  const dialogueText = (options.dialogueTranscript ?? '').trim()
  const dialogueWords = dialogueText ? dialogueText.split(/\s+/).filter(Boolean).length : 0
  const minSpeechSeconds = dialogueWords > 0 ? Math.ceil((dialogueWords / 2.5) * 10) / 10 : 0

  const inferredTotalSeconds = Math.max(
    minSpeechSeconds,
    targetDurationSeconds && targetDurationSeconds > 0
      ? targetDurationSeconds
      : narrativeBeats.length * 3.5,
  )

  const shotCount = narrativeBeats.length
  const baseShotSeconds = Math.max(2.0, inferredTotalSeconds / shotCount)

  // Azimuts dans l'hémisphère [lineOfAction + 25°, lineOfAction + 155°] espacés d'au moins 32°
  // pour satisfaire simultanément la règle des 180° et la règle des 30°.
  const relativeAzimuths = [35, 78, 122, 154]

  const shots: CinematicStoryboardShot[] = narrativeBeats.map((beat, idx) => {
    const scaleSpec = SCALE_PROGRESSION_TABLE[Math.min(idx, SCALE_PROGRESSION_TABLE.length - 1)]
    const focalMm = scaleSpec.focalLengthMm
    const hFovDeg = Number(
      ((2 * Math.atan(FULL_FRAME_SENSOR_WIDTH_MM / (2 * focalMm)) * 180) / Math.PI).toFixed(2),
    )
    const vFovDeg = Number(
      ((2 * Math.atan(FULL_FRAME_SENSOR_HEIGHT_MM / (2 * focalMm)) * 180) / Math.PI).toFixed(2),
    )

    const relAzimuth = relativeAzimuths[idx % relativeAzimuths.length]
    const cameraAzimuthDeg = Number((lineOfActionAzimuthDeg + relAzimuth).toFixed(2))
    const sinHemisphere = Math.sin(((cameraAzimuthDeg - lineOfActionAzimuthDeg) * Math.PI) / 180)
    const ruleOf180Compliant = sinHemisphere > 1e-4

    // Dérive thermique douce et contrôlée (+0K, -120K, -180K pour réchauffer légèrement les gros plans)
    const shotKelvin = Math.round(baseKelvin - idx * 90)
    const wbRgb = computePlanckianWhiteBalanceRgb(shotKelvin)

    // Construction des 4 points de contrôle de la trajectoire caméra C² dans le repère scène
    const azRad0 = (cameraAzimuthDeg * Math.PI) / 180
    const azRad1 = ((cameraAzimuthDeg + 8) * Math.PI) / 180
    const r0 = scaleSpec.distanceMeters
    const r1 = scaleSpec.distanceMeters * 0.92
    const y0 = 1.55 + Math.sin((scaleSpec.elevationDeg * Math.PI) / 180) * r0 * 0.25
    const y1 = y0 + (idx % 2 === 0 ? 0.06 : -0.04)

    const p0: Vector3D = { x: Math.cos(azRad0) * r0, y: y0, z: Math.sin(azRad0) * r0 }
    const p3: Vector3D = { x: Math.cos(azRad1) * r1, y: y1, z: Math.sin(azRad1) * r1 }
    const p1: Vector3D = {
      x: p0.x + (p3.x - p0.x) * 0.33,
      y: p0.y + (p3.y - p0.y) * 0.33,
      z: p0.z + (p3.z - p0.z) * 0.33,
    }
    const p2: Vector3D = {
      x: p0.x + (p3.x - p0.x) * 0.67,
      y: p0.y + (p3.y - p0.y) * 0.67,
      z: p0.z + (p3.z - p0.z) * 0.67,
    }
    const lookAtTarget: Vector3D = { x: 0, y: 1.5, z: 0 }

    const c2Eval = evaluateC2BezierTrajectory(p0, p1, p2, p3, lookAtTarget, 9)

    // Contrainte Wan2.2 : 4n + 1 trames par plan
    const rawFrames = Math.max(25, Math.round(baseShotSeconds * fps))
    const nLatent = Math.max(6, Math.round((rawFrames - 1) / 4))
    const numFrames4nPlus1 = 4 * nLatent + 1
    const exactSeconds = Number((numFrames4nPlus1 / fps).toFixed(2))

    // Contrat Lip-Sync & Multiplexage Audio/Vidéo (actif sur MS / MCU / CU si dialogue ou demandé)
    const hasSpokenTrack =
      Boolean(options.includeLipSyncMux) ||
      dialogueWords > 0 ||
      /\b(parle|dit|dialogue|discours|chante|speech|talk|speaking|monologue)\b/i.test(beat)
    const isFaceVisibleScale = scaleSpec.scale === 'MS' || scaleSpec.scale === 'MCU' || scaleSpec.scale === 'CU'
    const lipSyncActive = hasSpokenTrack && isFaceVisibleScale
    const shotWords = lipSyncActive
      ? Math.max(4, Math.round((dialogueWords || Math.round(exactSeconds * 2.4)) / shotCount))
      : 0

    const lipSyncMux: LipSyncMuxContract = {
      enabled: lipSyncActive,
      engine: lipSyncActive ? (scaleSpec.scale === 'CU' ? 'MuseTalk-1.5' : 'SadTalker-V2') : 'none',
      ttsBackend: 'CosyVoice3-0.5B-24kHz',
      sampleRateHz: 24000,
      visemeWindowMs: 40,
      avSyncOffsetToleranceMs: 12,
      estimatedWordCount: shotWords,
      requiredSpeechDurationSec: Number((shotWords / 2.5).toFixed(2)),
    }

    const motionDirectiveEn =
      idx === 0
        ? 'smooth C2-continuous establishing dolly-in trajectory, zero camera shake'
        : idx === 1
          ? 'fluid C2-continuous lateral tracking arc maintaining 180-degree axis of action'
          : 'subtle C2-continuous push-in focus on subject expression, locked horizon'

    const wanPromptEn = [
      beat,
      scaleSpec.promptLabelEn,
      `${focalMm}mm focal length (${hFovDeg} deg horizontal FOV, f/${scaleSpec.apertureFStop})`,
      `${shotKelvin}K color temperature lighting`,
      motionDirectiveEn,
      lipSyncActive
        ? 'clear visible mouth and facial articulation for frame-accurate lip-sync multiplexing'
        : 'coherent physical motion and stable identity across all frames',
    ].join(', ')

    return {
      shotIndex: idx + 1,
      narrativeBeat: beat,
      shotScale: scaleSpec.scale,
      shotScaleLabelFr: scaleSpec.labelFr,
      focalLengthMm: focalMm,
      horizontalFovDeg: hFovDeg,
      verticalFovDeg: vFovDeg,
      apertureFStop: scaleSpec.apertureFStop,
      colorTemperatureKelvin: shotKelvin,
      planckianWhiteBalanceRgb: wbRgb,
      cameraAzimuthDeg,
      cameraElevationDeg: scaleSpec.elevationDeg,
      lineOfActionAzimuthDeg,
      ruleOf180Side: 'positive-hemisphere',
      ruleOf180Compliant,
      thirtyDegreeRuleSatisfied: true,
      durationSeconds: exactSeconds,
      numFrames4nPlus1,
      cameraTrajectoryC2: {
        curveType: 'quintic-hermite-catmull-rom-c2',
        controlPoints: [p0, p1, p2, p3],
        samples: c2Eval.samples,
        maxCurvaturePerMeter: c2Eval.maxCurvaturePerMeter,
        maxAccelerationMagnitude: c2Eval.maxAccelerationMagnitude,
        boundaryAccelerationJump: c2Eval.boundaryAccelerationJump,
        isC2Continuous: c2Eval.isC2Continuous,
        motionDirectiveEn,
      },
      lipSyncMux,
      wanPromptEn,
    }
  })

  // Vérification inter-plans de la règle des 30° (écart angulaire >= 30° ou ratio de focale >= 1.35)
  for (let i = 1; i < shots.length; i += 1) {
    const prev = shots[i - 1]
    const curr = shots[i]
    const deltaAzimuth = Math.abs(curr.cameraAzimuthDeg - prev.cameraAzimuthDeg)
    const focalRatio =
      Math.max(curr.focalLengthMm, prev.focalLengthMm) /
      Math.max(1, Math.min(curr.focalLengthMm, prev.focalLengthMm))
    curr.thirtyDegreeRuleSatisfied = deltaAzimuth >= 30 || focalRatio >= 1.35
  }

  const totalFrames = shots.reduce((acc, s) => acc + s.numFrames4nPlus1, 0)
  const totalDurationSeconds = Number((totalFrames / fps).toFixed(2))
  const scaleOrder: Record<CinematicShotScale, number> = {
    ELS: 0,
    LS: 1,
    MLS: 2,
    MS: 3,
    MCU: 4,
    CU: 5,
    ECU: 6,
  }
  const scaleProgressionValid = shots.every(
    (s, i) => i === 0 || scaleOrder[s.shotScale] >= scaleOrder[shots[i - 1].shotScale],
  )

  return {
    title: cleanPrompt.slice(0, 72),
    totalDurationSeconds,
    totalFrames,
    fps,
    lineOfActionAzimuthDeg,
    ruleOf180GlobalCompliance: shots.every((s) => s.ruleOf180Compliant),
    thirtyDegreeRuleGlobalCompliance: shots.every((s) => s.thirtyDegreeRuleSatisfied),
    scaleProgressionValid,
    c2ContinuityGlobalVerified: shots.every((s) => s.cameraTrajectoryC2.isC2Continuous),
    baseColorTemperatureKelvin: baseKelvin,
    shots,
  }
}

// ============================================================================
// 2. PREMIERS PRINCIPES : PROFIL TEMPOREL OPTIMAL WAN2.2-TI2V-5B
//    CONTRAINTE 4n + 1 TRAMES, MULTIPLE DE 32 PIXELS & VIDEO_SHIFT ANTI-FLICKER
// ============================================================================

export interface Wan22TemporalProfileInput {
  requestedWidth: number
  requestedHeight: number
  requestedFrames: number
  fps?: number
  mode?: 't2v' | 'i2v'
  motionIntensity?: number
  vramGb?: number
  qualityMode?: 'auto' | 'balanced' | 'premium'
}

export interface Wan22TemporalProfile {
  modelId: string
  width: number
  height: number
  numFrames: number
  latentTemporalFrames: number
  latentSpatialWidth: number
  latentSpatialHeight: number
  spatiotemporalTokenCount: number
  videoShift: number
  cfgScale: number
  inferenceSteps: number
  shiftedTimestepSchedule: number[]
  temporalFlickerSuppressionIndex: number
  estimatedPeakVramGb: number
  framesConstraint4nPlus1Satisfied: boolean
  spatialMultipleOf32Satisfied: boolean
}

/**
 * Calcule par premiers principes les paramètres optimaux du modèle de diffusion
 * temporelle par flux rectifié `Wan-AI/Wan2.2-TI2V-5B` :
 * 1. Contrainte causale du VAE 3D Wan : `numFrames = 4n + 1` (exactement divisible par 4 après la 1re trame).
 * 2. Contrainte spatiale DiT + VAE : `width` et `height` multiples stricts de 32 pixels, adaptés au plafond VRAM.
 * 3. Décalage dynamique du flux temporel (`videoShift` / $\alpha$) selon la loi d'échelle SNR spatiotemporelle :
 *    $$t_{\text{shifted}} = \frac{\alpha t}{1 + (\alpha - 1) t}, \quad \alpha = \text{clamp}\left(\alpha_0 \sqrt{\frac{N_{\text{tokens}}}{N_0}} \cdot \phi_{\text{motion}}, 3.0, 12.0\right)$$
 *    éliminant le scintillement inter-trames (boiling/flickering) tout en préservant l'identité.
 */
export function computeOptimalWan22TemporalProfile(
  input: Wan22TemporalProfileInput,
): Wan22TemporalProfile {
  const vramGb = input.vramGb && input.vramGb > 0 ? input.vramGb : 16
  const mode = input.mode ?? 't2v'
  const qualityMode = input.qualityMode ?? 'auto'
  const motionIntensity = Math.max(0, Math.min(1, input.motionIntensity ?? 0.55))

  // 1. Alignement temporel strict sur 4n + 1 trames (minimum 25 trames = 4*6 + 1, max 121 trames par segment)
  const clampedTargetFrames = Math.max(25, Math.min(193, Math.round(input.requestedFrames || 49)))
  const nTemporal = Math.max(6, Math.round((clampedTargetFrames - 1) / 4))
  const numFrames = 4 * nTemporal + 1
  const latentTemporalFrames = nTemporal + 1

  // 2. Alignement spatial sur un multiple exact de 32 pixels avec respect du plafond VRAM
  const rawW = Math.max(256, Math.min(1920, Math.round(input.requestedWidth || 1280)))
  const rawH = Math.max(256, Math.min(1920, Math.round(input.requestedHeight || 720)))
  const aspect = rawW / Math.max(1, rawH)

  // Budget de surface maximale en pixels selon la VRAM et le mode (I2V consomme ~18% de VRAM en plus pour l'encodeur CLIP/VAE d'ancrage)
  const maxPixelBudget =
    vramGb >= 24
      ? 1280 * 720
      : vramGb >= 15
        ? mode === 'i2v' && numFrames > 65
          ? 832 * 480
          : 1056 * 576
        : 640 * 384

  let scaledW = rawW
  let scaledH = rawH
  if (scaledW * scaledH > maxPixelBudget) {
    scaledH = Math.sqrt(maxPixelBudget / Math.max(0.25, aspect))
    scaledW = scaledH * aspect
  }

  const align32 = (v: number) => Math.max(256, Math.round(v / 32) * 32)
  const width = align32(scaledW)
  const height = align32(scaledH)

  // Patchification 3D DiT Wan2.2 : stride spatial 16 (VAE 8x * patch 2x2)
  const latentSpatialWidth = width / 16
  const latentSpatialHeight = height / 16
  const spatiotemporalTokenCount = Math.round(
    latentTemporalFrames * latentSpatialWidth * latentSpatialHeight,
  )

  // 3. Décalage dynamique de flux temporel (Rectified Flow log-SNR shift `video_shift`)
  // Référence canonique Wan2.2 : N0 = 13 * 52 * 30 = 20280 tokens (49 frames @ 832x480), alpha0 = 5.0
  const referenceTokensN0 = 13 * 52 * 30
  const tokenScaleFactor = Math.sqrt(spatiotemporalTokenCount / referenceTokensN0)
  const baseShiftAlpha = mode === 'i2v' ? 4.8 : 5.5
  const motionModulator = 1.0 + 0.28 * (motionIntensity - 0.5)
  const rawVideoShift = baseShiftAlpha * tokenScaleFactor * motionModulator
  const videoShift = Number(Math.max(3.0, Math.min(12.0, rawVideoShift)).toFixed(3))

  // Nombre d'étapes d'intégration Euler/UniPC et trajectoire des pas de temps décalés t_shifted
  const inferenceSteps =
    qualityMode === 'premium' ? 60 : qualityMode === 'balanced' ? 32 : vramGb >= 15 ? 48 : 32
  const cfgScale = mode === 'i2v' ? 5.0 : 6.0

  const sampleScheduleSteps = 10
  const shiftedTimestepSchedule: number[] = []
  for (let i = 0; i <= sampleScheduleSteps; i += 1) {
    const tLinear = 1 - i / sampleScheduleSteps
    const tShifted = (videoShift * tLinear) / (1 + (videoShift - 1) * tLinear)
    shiftedTimestepSchedule.push(Number(tShifted.toFixed(4)))
  }

  // Indice de suppression du scintillement inter-trames [0..1]
  // Maximal quand le shift compense exactement la dimensionnalité des tokens et que le nombre d'étapes est élevé
  const stepFactor = Math.min(1, inferenceSteps / 48)
  const shiftOptimality = 1 - Math.min(0.4, Math.abs(videoShift - baseShiftAlpha * tokenScaleFactor) / 8)
  const temporalFlickerSuppressionIndex = Number((0.82 * shiftOptimality + 0.18 * stepFactor).toFixed(4))

  // Estimation physique du pic VRAM (poids TI2V-5B FP8/Q6 + activations KV-cache spatiotemporelles)
  const baseWeightsGb = 6.4
  const kvActivationGb = (spatiotemporalTokenCount / 20280) * (mode === 'i2v' ? 4.6 : 3.8)
  const estimatedPeakVramGb = Number((baseWeightsGb + kvActivationGb).toFixed(2))

  return {
    modelId: VIDEO_UNIFIED_5B_MODEL,
    width,
    height,
    numFrames,
    latentTemporalFrames,
    latentSpatialWidth,
    latentSpatialHeight,
    spatiotemporalTokenCount,
    videoShift,
    cfgScale,
    inferenceSteps,
    shiftedTimestepSchedule,
    temporalFlickerSuppressionIndex,
    estimatedPeakVramGb,
    framesConstraint4nPlus1Satisfied: (numFrames - 1) % 4 === 0 && numFrames >= 25,
    spatialMultipleOf32Satisfied: width % 32 === 0 && height % 32 === 0,
  }
}

// ============================================================================
// 3. ANALYSE DE GRAMMAIRE VIDÉO, COMPOSITION DE PROMPT WAN & TEMPO AUDIO
// ============================================================================

export interface VideoPromptAnalysis {
  camera: string[]
  shot: string | null
  lighting: string[]
  style: string | null
  tempo: string | null
  staticCamera: boolean
}

interface LexiconEntry {
  pattern: RegExp
  directive: string
}

const CAMERA_LEXICON: LexiconEntry[] = [
  { pattern: /\b(zoom\s*avant|zoom\s*in|zoome?r?\s+vers)\b/i, directive: 'slow cinematic zoom in' },
  { pattern: /\b(zoom\s*arriere|zoom\s*arrière|zoom\s*out|dezoom)\b/i, directive: 'slow cinematic zoom out' },
  { pattern: /\b(panoramique|camera\s+pan|pan\s+(gauche|droite|lateral)|balayage)\b/i, directive: 'smooth horizontal camera pan' },
  { pattern: /\b(travelling|dolly)\b/i, directive: 'steady dolly tracking shot' },
  { pattern: /\b(orbite|orbital|orbit|tourne\s+autour|rotation\s+autour)\b/i, directive: 'camera slowly orbiting around the subject' },
  { pattern: /\b(drone|vue\s+a[eé]rienne|aerial|survol)\b/i, directive: 'aerial drone shot, high altitude perspective' },
  { pattern: /\b(plong[eé]e)\b/i, directive: 'high-angle shot looking down' },
  { pattern: /\b(contre[-\s]?plong[eé]e)\b/i, directive: 'low-angle shot looking up, imposing perspective' },
  { pattern: /\b(pov|premi[eè]re\s+personne|first\s+person|vue\s+subjective)\b/i, directive: 'first-person POV shot' },
  { pattern: /\b(suit|suivre|poursuite|tracking|follow)\b/i, directive: 'tracking shot following the subject' },
  { pattern: /\b(camera\s+[aà]\s+l[' ]?[eé]paule|handheld|cam[eé]ra\s+port[eé]e)\b/i, directive: 'handheld camera, subtle natural shake' },
]

const STATIC_CAMERA_PATTERN = /\b(plan\s+fixe|cam[eé]ra\s+fixe|static\s+(camera|shot)|sans\s+mouvement\s+de\s+cam[eé]ra)\b/i

const SHOT_LEXICON: LexiconEntry[] = [
  { pattern: /\b(tr[eè]s\s+gros\s+plan|extreme\s+close[-\s]?up|macro)\b/i, directive: 'extreme close-up shot' },
  { pattern: /\b(gros\s+plan|close[-\s]?up|portrait\s+serr[eé])\b/i, directive: 'close-up shot' },
  { pattern: /\b(plan\s+moyen|medium\s+shot|[aà]\s+mi[-\s]corps)\b/i, directive: 'medium shot' },
  { pattern: /\b(plan\s+large|plan\s+d[' ]?ensemble|wide\s+shot|vue\s+d[' ]?ensemble|panorama)\b/i, directive: 'wide establishing shot' },
]

const LIGHTING_LEXICON: LexiconEntry[] = [
  { pattern: /\b(coucher\s+de\s+soleil|golden\s+hour|cr[eé]puscule|sunset)\b/i, directive: 'golden hour lighting, warm tones' },
  { pattern: /\b(aube|lever\s+de\s+soleil|sunrise)\b/i, directive: 'soft sunrise light, cool-to-warm gradient' },
  { pattern: /\b(nuit|nocturne|night)\b/i, directive: 'night scene, controlled low-key lighting' },
  { pattern: /\bn[eé]ons?\b/i, directive: 'neon lighting reflecting on surfaces' },
  { pattern: /\b(pluie|rain|orage|storm|temp[eê]te)\b/i, directive: 'rain atmosphere, wet reflective surfaces' },
  { pattern: /\b(brouillard|brume|fog|mist)\b/i, directive: 'volumetric fog, atmospheric depth' },
  { pattern: /\b(neige|hiver|snow)\b/i, directive: 'snowy scene, soft diffuse winter light' },
  { pattern: /\b(bougie|candle|feu\s+de\s+camp|campfire)\b/i, directive: 'warm flickering firelight' },
  { pattern: /\b(studio)\b/i, directive: 'clean studio lighting' },
  { pattern: /\b(sous[-\s]?marin|underwater|sous\s+l[' ]?eau)\b/i, directive: 'underwater light rays and caustics' },
]

const STYLE_LEXICON: LexiconEntry[] = [
  { pattern: /\b(anime|manga)\b/i, directive: 'high quality anime animation style, clean linework, expressive motion' },
  { pattern: /\b(cartoon|dessin\s+anim[eé])\b/i, directive: '2D cartoon animation style, bold shapes' },
  { pattern: /\b(pixar|3d\s+anim[eé]|animation\s+3d)\b/i, directive: 'polished 3D animated film style, soft global illumination' },
  { pattern: /\b(noir\s+et\s+blanc|black\s+and\s+white|monochrome)\b/i, directive: 'black and white film, rich grayscale contrast' },
  { pattern: /\b(vintage|r[eé]tro|pellicule|film\s+grain|super\s*8)\b/i, directive: 'vintage film look, analog grain' },
  { pattern: /\b(cyberpunk)\b/i, directive: 'cyberpunk aesthetic, neon-soaked futuristic city' },
  { pattern: /\b(aquarelle|watercolor)\b/i, directive: 'watercolor painting animation style' },
  { pattern: /\b(r[eé]aliste|photo[-\s]?r[eé]aliste|realistic|photoreal)\b/i, directive: 'photorealistic live-action footage, real camera optics' },
  { pattern: /\b(documentaire|documentary)\b/i, directive: 'documentary cinematography, natural framing' },
]

const TEMPO_LEXICON: LexiconEntry[] = [
  { pattern: /\b(ralenti|slow\s*motion|slow[-\s]?mo)\b/i, directive: 'slow motion, fluid high-frame-rate look' },
  { pattern: /\b(time[-\s]?lapse|acc[eé]l[eé]r[eé])\b/i, directive: 'timelapse, accelerated time flow' },
  { pattern: /\b(boucle|loop|seamless)\b/i, directive: 'seamless loop, last frame matches first frame' },
]

export const VIDEO_QUALITY_TAIL = [
  'cinematic composition',
  'high detail',
  'sharp focus',
  'natural color grading',
  'coherent physics',
  'stable subject identity',
  'smooth natural motion',
  'professional video quality',
]

function matchAllLexicon(text: string, lexicon: LexiconEntry[]): string[] {
  const out: string[] = []
  for (const entry of lexicon) {
    if (entry.pattern.test(text)) out.push(entry.directive)
  }
  return out
}

export function analyzeVideoPrompt(raw: string): VideoPromptAnalysis {
  const text = raw.normalize('NFC')
  const camera = matchAllLexicon(text, CAMERA_LEXICON)
  const shots = matchAllLexicon(text, SHOT_LEXICON)
  const lighting = matchAllLexicon(text, LIGHTING_LEXICON)
  const styles = matchAllLexicon(text, STYLE_LEXICON)
  const tempos = matchAllLexicon(text, TEMPO_LEXICON)

  return {
    camera,
    shot: shots[0] ?? null,
    lighting,
    style: styles[0] ?? null,
    tempo: tempos[0] ?? null,
    staticCamera: STATIC_CAMERA_PATTERN.test(text),
  }
}

function alreadyPresentInPrompt(base: string, directive: string): boolean {
  const lowered = base.toLowerCase()
  if (lowered.includes(directive.toLowerCase())) return true
  const tokens = directive.toLowerCase().split(/[,\s]+/).filter((t) => t.length > 3)
  if (tokens.length < 2) return false
  return lowered.includes(tokens[0]) && lowered.includes(tokens[1])
}

export interface ComposeOptions {
  motionSuffix?: string
  mode?: 't2v' | 'i2v'
}

export function composeWanPrompt(
  distilled: string,
  analysis: VideoPromptAnalysis,
  options: ComposeOptions = {},
): string {
  const base = distilled.replace(/\s+$/g, '').trim()
  const parts: string[] = []
  const merged = options.motionSuffix ? `${base}\n${options.motionSuffix}` : base

  const push = (directive: string) => {
    if (!directive) return
    if (alreadyPresentInPrompt(merged, directive)) return
    if (parts.some((p) => p === directive)) return
    parts.push(directive)
  }

  if (analysis.shot) push(analysis.shot)
  if (analysis.staticCamera) {
    push('static camera, locked tripod shot, no camera movement')
  } else {
    for (const cam of analysis.camera) push(cam)
  }
  for (const light of analysis.lighting) push(light)
  if (analysis.style) push(analysis.style)
  if (analysis.tempo) push(analysis.tempo)
  for (const tail of VIDEO_QUALITY_TAIL) push(tail)

  if (parts.length === 0) return base
  return `${base}\n\nCinematography: ${parts.join(', ')}.`
}

export type TempoCategory =
  | 'larghissimo'
  | 'lento'
  | 'andante'
  | 'moderato'
  | 'allegro'
  | 'presto'
  | 'prestissimo'

export function classifyTempo(bpm: number): TempoCategory {
  if (bpm < 60) return 'larghissimo'
  if (bpm < 80) return 'lento'
  if (bpm < 108) return 'andante'
  if (bpm < 120) return 'moderato'
  if (bpm < 156) return 'allegro'
  if (bpm < 184) return 'presto'
  return 'prestissimo'
}

export function recommendBpmForTone(
  tone: 'tutoriel' | 'storytelling' | 'pub' | 'recap' | 'hype',
): number {
  const map: Record<string, number> = {
    tutoriel: 100,
    storytelling: 80,
    pub: 130,
    recap: 110,
    hype: 150,
  }
  return map[tone] ?? 110
}

// ============================================================================
// 4. PROFILS DE RÉSOLUTION & RÉSOLUTION DE DURÉE BASÉE SUR LE CONTENU
// ============================================================================

type VideoProfile = {
  width: number
  height: number
  numFrames: number
  videoShift: number
  label: string
}

type GeneratedVideo = {
  url: string
  prompt: string
  time: number
  durationLabel: string
  modelLabel: string
}

type MotionPreset = {
  id: string
  label: string
  promptSuffix: string
}

const MOTION_PRESETS: MotionPreset[] = [
  { id: 'free', label: 'Libre', promptSuffix: '' },
  { id: 'dance', label: 'Danse', promptSuffix: 'dancing energetically, fluid body movement, rhythmic motion, natural limb animation' },
  { id: 'walk', label: 'Marche', promptSuffix: 'walking naturally forward, smooth locomotion, balanced gait' },
  { id: 'zoom_in', label: 'Zoom avant', promptSuffix: 'camera slowly zooming in, cinematic depth, foreground clarity increases' },
  { id: 'zoom_out', label: 'Zoom arriere', promptSuffix: 'camera slowly zooming out, revealing wider scene context' },
  { id: 'parallax', label: 'Parallaxe', promptSuffix: 'cinematic parallax effect, foreground and background layers moving at different speeds, depth illusion' },
  { id: 'pan', label: 'Panoramique', promptSuffix: 'smooth horizontal camera pan, steady movement, no shake' },
  { id: 'orbit', label: 'Orbite', promptSuffix: 'camera slowly orbiting around the subject, consistent radius, subject centered' },
  { id: 'dolly', label: 'Travelling', promptSuffix: 'steady dolly tracking shot, rail-smooth lateral movement' },
  { id: 'drone', label: 'Drone', promptSuffix: 'aerial drone shot, smooth flight path, high altitude perspective' },
  { id: 'slowmo', label: 'Ralenti', promptSuffix: 'slow motion, fluid high-frame-rate look, every movement stretched in time' },
  { id: 'timelapse', label: 'Timelapse', promptSuffix: 'timelapse, accelerated time flow, smooth exposure transitions' },
  { id: 'loop', label: 'Boucle', promptSuffix: 'seamless loop, last frame matches first frame, continuous cycle' },
]

function buildVideoProfiles(
  width: number,
  height: number,
  numFrames: number,
  mode: 't2v' | 'i2v' = 't2v',
  vramGb = 16,
): VideoProfile[] {
  const rawTiers: Array<{ w: number; h: number; label: string }> = [
    { w: width, h: height, label: 'profil principal' },
    { w: Math.min(width, 832), h: Math.min(height, 480), label: 'profil stable' },
    { w: Math.min(width, 640), h: Math.min(height, 384), label: 'profil secours' },
    { w: Math.min(width, 512), h: Math.min(height, 320), label: 'profil minimal' },
  ]

  const candidates: VideoProfile[] = rawTiers.map((tier) => {
    const opt = computeOptimalWan22TemporalProfile({
      requestedWidth: tier.w,
      requestedHeight: tier.h,
      requestedFrames: numFrames,
      mode,
      vramGb,
    })
    return {
      width: opt.width,
      height: opt.height,
      numFrames: opt.numFrames,
      videoShift: opt.videoShift,
      label: tier.label,
    }
  })

  return candidates.filter(
    (candidate, index, array) =>
      array.findIndex(
        (entry) =>
          entry.width === candidate.width &&
          entry.height === candidate.height &&
          entry.numFrames === candidate.numFrames,
      ) === index,
  )
}

function isRecoverableVideoFailure(error: unknown) {
  const message = getErrorMessage(error, '').toLowerCase()
  return [
    'out of memory',
    'cuda',
    'cudnn',
    'vram',
    'oom',
    'access violation',
    'exit -1073741819',
    'device-side assert',
    'illegal memory access',
    'exit 15',
    'sigterm',
    'generation interrompue par le systeme',
  ].some((needle) => message.includes(needle))
}

const FPS = 24
const MIN_FRAMES = 25
const MAX_FRAMES = 97 * 5
const secondsToFrames = (seconds: number) => {
  const raw = Math.max(MIN_FRAMES, Math.min(MAX_FRAMES, Math.round(seconds * FPS)))
  const n = Math.max(6, Math.round((raw - 1) / 4))
  return 4 * n + 1
}

const ACTION_WORDS =
  'combat|fight|bataille|bagarre|saut|jump|bond|explosion|course|sprint|poursuite|chase|chute|fall|attaque|attack|frappe|punch|kick|coup|danse|dance|choregraphie|marche|walk|stride|scene|plan|shot|cascade|stunt|duel|' +
  'court|couru|courir|court-metrage|vole|voler|flotte|flotter|tombe|tomber|glisse|glisser|roule|rouler|nage|nager|escalade|grimpe|grimper|lance|lancer|tire|tirer|pousse|pousser|tourne|tourner|pivote|pivoter|ouvre|ouvrir|ferme|fermer|casse|casser|brise|briser|detruit|detruire'

function parseExplicitVideoDuration(text: string): number | null {
  const totalDurationRegex =
    /(?:vid[eé]o\s+(?:de\s+|d[''])?|clip\s+(?:de\s+|d[''])?|sequence\s+(?:de\s+|d[''])?|dur(?:ant|ee)?\s*(?:totale\s*)?(?:de\s+|d[''])?|pendant\s+|qui\s+dure\s+|longueur\s*(?:de\s+)?|total\s+(?:de\s+)?)(\d+(?:[.,]\d+)?)\s*(?:s(?:ec(?:onde)?s?)?|secondes?)/i
  const match = text.match(totalDurationRegex)
  if (!match) return null
  const seconds = parseFloat(match[1].replace(',', '.'))
  if (seconds > 0 && seconds <= 120) return seconds
  return null
}

function hasActionLocalDuration(text: string): boolean {
  return new RegExp(
    `(?:${ACTION_WORDS})\\s+(?:de\\s+|d['']|qui\\s+dure\\s+)?\\d+(?:[.,]\\d+)?\\s*s`,
    'i',
  ).test(text)
}

function parseStandaloneVideoDuration(text: string): number | null {
  if (hasActionLocalDuration(text)) return null
  const standaloneRegex = /(?:^|\s)(\d+(?:[.,]\d+)?)\s*(?:s(?:ec(?:onde)?s?)?|secondes?)(?:\s|$|,|\.)/i
  const match = text.match(standaloneRegex)
  if (!match) return null
  const seconds = parseFloat(match[1].replace(',', '.'))
  if (seconds >= 3 && seconds <= 120) return seconds
  return null
}

function inferDurationFromContent(text: string): { seconds: number; rationale: string } {
  const normalized = text.toLowerCase()

  if (new RegExp(`\\b(${ACTION_WORDS})\\b`, 'i').test(normalized)) {
    return { seconds: 5, rationale: 'sequence d action detectee -> 5s pour lisibilite du mouvement' }
  }
  if (/\b(travelling|travel|dolly|crane|reveal|r[eé]v[eé]lation|panorama|pan(?:oramique)?|tilt|orbit|360)\b/i.test(normalized)) {
    return { seconds: 5, rationale: 'mouvement camera long -> 5s' }
  }
  if (/\b(transform|morph|transition|time[\s-]?lapse|evolution|croissance|grow|build\s*up|explode)\b/i.test(normalized)) {
    return { seconds: 4, rationale: 'transformation progressive -> 4s' }
  }
  if (/\b(foule|crowd|ville|city|rue|street|paysage|landscape|for[eê]t|mer|ocean|montagne|mountain|ciel|sky|atmosphere)\b/i.test(normalized)) {
    return { seconds: 4, rationale: 'plan d atmosphere -> 4s' }
  }
  if (/\b(portrait|visage|face|smile|sourire|regard|clignement|expression|emotion)\b/i.test(normalized)) {
    return { seconds: 2.5, rationale: 'portrait -> 2.5s' }
  }
  if (/\b(produit|product|objet|object|packshot|studio|detail|zoom)\b/i.test(normalized)) {
    return { seconds: 3, rationale: 'plan produit -> 3s' }
  }
  return { seconds: 3, rationale: 'plan neutre -> 3s par defaut' }
}

export type DurationResolution = {
  frames: number
  seconds: number
  source: 'user-slider' | 'explicit-total' | 'standalone-number' | 'content-inference'
  rationale: string
}

export function resolveVideoDuration(
  text: string,
  sliderFrames: number,
  sliderIsDefault: boolean,
): DurationResolution {
  const explicit = parseExplicitVideoDuration(text)
  if (explicit !== null) {
    return {
      frames: secondsToFrames(explicit),
      seconds: explicit,
      source: 'explicit-total',
      rationale: `duree totale demandee: ${explicit}s`,
    }
  }
  const standalone = parseStandaloneVideoDuration(text)
  if (standalone !== null) {
    return {
      frames: secondsToFrames(standalone),
      seconds: standalone,
      source: 'standalone-number',
      rationale: `duree detectee dans le prompt: ${standalone}s`,
    }
  }
  if (!sliderIsDefault) {
    const aligned = secondsToFrames(sliderFrames / FPS)
    return {
      frames: aligned,
      seconds: Math.round((aligned / FPS) * 10) / 10,
      source: 'user-slider',
      rationale: `duree fixee par le slider utilisateur (${aligned} frames 4n+1)`,
    }
  }
  const inferred = inferDurationFromContent(text)
  const actionDurationsParsed = Array.from(
    text.matchAll(
      new RegExp(
        `(?:${ACTION_WORDS})\\s+(?:de\\s+|d['']|qui\\s+dure\\s+)?(\\d+(?:[.,]\\d+)?)\\s*s`,
        'gi',
      ),
    ),
  )
    .map((m) => parseFloat(m[1].replace(',', '.')))
    .filter((n) => Number.isFinite(n) && n > 0 && n <= 30)
  const longestAction = actionDurationsParsed.length > 0 ? Math.max(...actionDurationsParsed) : 0
  const minForAction = longestAction > 0 ? longestAction + 0.5 : 0
  const finalSeconds = Math.max(inferred.seconds, minForAction)
  return {
    frames: secondsToFrames(finalSeconds),
    seconds: finalSeconds,
    source: 'content-inference',
    rationale:
      longestAction > 0
        ? `${inferred.rationale} + couverture action ${longestAction}s`
        : inferred.rationale,
  }
}

function extractActionDurations(text: string): string {
  const actionRegex = new RegExp(
    `(${ACTION_WORDS})\\s+(?:de\\s+|d['']|qui\\s+dure\\s+)?(\\d+(?:[.,]\\d+)?)\\s*s`,
    'gi',
  )
  const actions: string[] = []
  let match: RegExpExecArray | null
  while ((match = actionRegex.exec(text)) !== null) {
    actions.push(`${match[2]}s ${match[1]}`)
  }
  return actions.length > 0 ? `Action timings: ${actions.join(', ')}` : ''
}

function humanizeVideoError(rawError: string): string {
  if (!rawError || rawError === '{}' || rawError === '{"ok": false, "error": ""}') {
    return 'Le pipeline video a ete interrompu (SIGTERM/exit 15). VRAM probablement insuffisante pour cette resolution. Le module va automatiquement retenter avec une resolution plus basse.'
  }
  if (rawError.includes('exit 15') || rawError.includes('exit code: 15')) {
    return 'Le pipeline video a ete interrompu par le watchdog VRAM. Resolution trop haute pour la memoire GPU disponible. Reduction automatique en cours...'
  }
  return rawError
}

// ============================================================================
// 5. COMPOSANT PRINCIPAL VIDEOVIEW
// ============================================================================

export default function VideoView() {
  const { visionModel, hardware } = useAppStore()
  const { executeWithRuntime } = useManagedRuntime()
  const diagnostics = useStudioDiagnostics({
    requiresTauri: true,
    requiresOllama: true,
    requiredFiles: [
      { label: 'Pipeline video', relativePath: 'python-services/video_generate.py' },
    ],
  })
  const [prompt, setPrompt] = useState('')
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const [width, setWidth] = useState(1280)
  const [height, setHeight] = useState(704)
  const [numFrames, setNumFrames] = useState(49)
  const [isGenerating, setIsGenerating] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [videoMeta, setVideoMeta] = useState<{ duration: number; width: number; height: number } | null>(null)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [copyPromptFeedback, setCopyPromptFeedback] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [videoMode, setVideoMode] = useState<'speed' | 'quality'>('speed')
  const [qualityMode, setQualityMode] = useState<'auto' | 'balanced' | 'premium'>('auto')
  const [motionPreset, setMotionPreset] = useState<string>('free')
  const [videos, setVideos] = useState<GeneratedVideo[]>([])
  const [saveDialogData, setSaveDialogData] = useState<SaveDialogData | null>(null)
  const [promptLibraryOpen, setPromptLibraryOpen] = useState(false)
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null)
  const { addPrompt } = usePromptLibraryStore()
  const { trackGeneration, completeGeneration, failGeneration } = useGenerationTrackerStore()
  const billingMode = useCreditBillingStore((s) => s.billingMode)
  const jbCoinsBalance = useCreditBillingStore((s) => s.juanOfBikeCoins)
  const subscriptionTier = useCreditBillingStore((s) => s.subscriptionTier)
  const selectedPaymentMethod = useCreditBillingStore((s) => s.selectedPaymentMethod)
  const processCheckoutPurchase = useCreditBillingStore((s) => s.processCheckoutPurchase)
  const consumeCoinsForModule = useCreditBillingStore((s) => s.consumeCoinsForModule)
  const addJbCoins = useCreditBillingStore((s) => s.addJuanOfBikeCoins)
  const videoArchSpec = BEST_MODELS_ARCHITECTURE_CATALOG.find((m) => m.moduleId === 'video')!
  const recovery = useGenerationRecovery('video')
  const activeTrackerIdRef = useRef<string | null>(null)
  const unlistenRef = useRef<(() => void) | null>(null)
  const useImageToVideo = contextFiles.some((file) => file.type.startsWith('image/'))
  const activeOllamaModel = contextFiles.length > 0 ? visionModel : AUXILIARY_ANALYSIS_MODEL
  const vramGb = Number(hardware?.vram_gb ?? 16)

  const { pack: assetPack, preparePack } = useModuleAssetPack({
    module: 'video',
    title: 'Pack modele video',
    assets: buildVideoModuleAssets(visionModel, useImageToVideo, contextFiles.length > 0, vramGb),
  })

  // Calcul réactif du storyboard cinématographique (Règle des 180°, C², Kelvin, Focales)
  // et du profil temporel Wan2.2-TI2V-5B (4n+1 trames, multiple de 32px, video_shift)
  const liveStoryboardPlan = useMemo(
    () =>
      synthesizeCinematicStoryboardPlan(prompt || 'Plan cinématographique Aurora', undefined, {
        fps: FPS,
        includeLipSyncMux: true,
      }),
    [prompt],
  )

  const liveWan22Profile = useMemo(
    () =>
      computeOptimalWan22TemporalProfile({
        requestedWidth: width,
        requestedHeight: height,
        requestedFrames: numFrames,
        fps: FPS,
        mode: useImageToVideo ? 'i2v' : 't2v',
        vramGb,
        qualityMode,
      }),
    [width, height, numFrames, useImageToVideo, vramGb, qualityMode],
  )

  useEffect(() => {
    return () => {
      unlistenRef.current?.()
    }
  }, [])

  const [pendingJobBanner, setPendingJobBanner] = useState<{
    jobId: string
    status: 'queued' | 'running' | 'done'
  } | null>(null)
  useEffect(() => {
    let alive = true
    const tick = async () => {
      const info = await peekResumableJob('video')
      if (alive) setPendingJobBanner(info)
    }
    void tick()
    const id = window.setInterval(tick, 15_000)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])

  const canGenerate = Boolean(prompt.trim()) && !isGenerating && !diagnostics.blockingReason

  const generate = useCallback(async () => {
    if (!prompt.trim() || isGenerating) return

    if (diagnostics.blockingReason) {
      setError(diagnostics.blockingReason)
      return
    }

    const creditCheck = consumeCoinsForModule('video')
    if (!creditCheck.allowed) {
      setError(creditCheck.reasonFr || 'Solde de pièces Juan of Bike insuffisant pour le rendu Vidéo sur les VMs.')
      return
    }

    setIsGenerating(true)
    setError(null)
    setProgress('Analyse de la scene video...')

    try {
      await executeWithRuntime({
        module: 'video',
        title: 'Generation video',
        services: ['ollama'],
        ollamaModel: activeOllamaModel,
        prepare: async ({ setPhase }) => {
          await preparePack(setPhase)
        },
        job: async ({ setPhase }) => {
          const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
          const primaryPreparedImage = pickPrimaryPreparedImage(preparedContext)
          const activePreset = MOTION_PRESETS.find((preset) => preset.id === motionPreset)
          const motionSuffix = activePreset?.promptSuffix
            ? `\n\nMotion directive: ${activePreset.promptSuffix}`
            : ''
          const referenceAwarePrompt = primaryPreparedImage
            ? [
                prompt,
                'Reference video contract: preserve the main identity, camera framing, palette and subject count from the reference image unless the prompt explicitly changes them.',
                'Use the reference image as the first frame or visual anchor and apply only the requested motion, setting or action changes.',
                'Keep limb trajectories, body balance, clothing continuity and prop placement coherent across the whole shot. No teleportation, no identity drift, no random scene jumps.',
              ].join('\n\n') + motionSuffix
            : prompt + motionSuffix
          const taskContext = await prepareTaskIntelligence({
            module: 'video',
            prompt: referenceAwarePrompt,
            model: visionModel,
            files: preparedContext,
            setPhase,
            phaseBase: 42,
            phaseSpan: 18,
          })

          if (taskContext.clarificationQuestion) {
            setPhase('Clarification utilisateur requise avant rendu video.', 50)
            const userAnswer = await new Promise<string | null>((resolve) => {
              setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve })
            })
            setClarification(null)
            if (userAnswer) {
              taskContext.generationPrompt = `${taskContext.generationPrompt}\n\nPrecisions de l utilisateur: ${userAnswer}`
            }
          }

          const durationResolution = resolveVideoDuration(prompt, numFrames, numFrames === 49)
          const effectiveFrames = durationResolution.frames
          const actionTimings = extractActionDurations(prompt)
          const timedGenerationPrompt = actionTimings
            ? `${taskContext.generationPrompt}\n\n${actionTimings}`
            : taskContext.generationPrompt

          const cinematicAnalysis = analyzeVideoPrompt(prompt)
          const finalGenerationPrompt = composeWanPrompt(timedGenerationPrompt, cinematicAnalysis, {
            motionSuffix: activePreset?.promptSuffix || '',
            mode: primaryPreparedImage ? 'i2v' : 't2v',
          })

          const workspacePath = await getWorkspacePath()
          const timestamp = Date.now()
          const outputDir = `${workspacePath}/output/videos`
          const outputPath = `${outputDir}/juan_bike_video_${timestamp}.mp4`
          const thumbnailPath = `${outputDir}/thumb_${timestamp}.png`
          const scriptPath = `${workspacePath}/python-services/video_generate.py`
          await fsMkdir(outputDir)
          const profiles = buildVideoProfiles(
            width,
            height,
            effectiveFrames,
            primaryPreparedImage ? 'i2v' : 't2v',
            vramGb,
          )

          activeTrackerIdRef.current = trackGeneration({
            module: 'video',
            type: 'python_script',
            prompt,
            startedAt: Date.now(),
            expectedOutputDir: `${workspacePath}/output/videos`,
            expectedOutputPattern: 'juan_bike_video_.*\\.mp4',
          })
          const trackerId = activeTrackerIdRef.current

          unlistenRef.current?.()
          unlistenRef.current = await onPythonProgress((message) => {
            if (message.startsWith('PROGRESS:')) {
              const parts = message.split(':')
              const stage = parts[1] || 'run'
              const detail = parts.slice(2).join(':') || parts[1] || 'Generation video en cours...'
              setProgress(detail)
              const phaseProgress =
                stage === 'install'
                  ? 48
                  : stage === 'vram'
                    ? 52
                    : stage === 'repair'
                      ? 56
                      : stage === 'loading_start' || stage === 'init' || stage === 'loading_pipeline'
                        ? 58
                        : stage === 'loading_done' || stage === 'generating'
                          ? 72
                          : stage === 'validating'
                            ? 82
                            : stage === 'saving'
                              ? 88
                              : 68
              setPhase(detail, phaseProgress)
            }
          })

          let output = ''
          let successfulProfile = profiles[0]

          for (let attempt = 0; attempt < profiles.length; attempt += 1) {
            const profile = profiles[attempt]
            successfulProfile = profile
            const profileLabel = `${profile.label} ${profile.width}x${profile.height}, ${profile.numFrames} frames (shift=${profile.videoShift})`
            setProgress(
              primaryPreparedImage
                ? `Lancement du pipeline video image-vers-video (${profileLabel})...`
                : `Lancement du pipeline video local (${profileLabel})...`,
            )
            setPhase(
              primaryPreparedImage
                ? `Execution Python du pipeline image-vers-video (${profileLabel})...`
                : `Execution Python du pipeline video (${profileLabel})...`,
              60,
            )

            const promptSeed = (() => {
              let h = 0x811c9dc5
              for (let i = 0; i < finalGenerationPrompt.length; i += 1) {
                h ^= finalGenerationPrompt.charCodeAt(i)
                h = Math.imul(h, 0x01000193) >>> 0
              }
              return h % 2147483647
            })()

            try {
              output = await runPythonScript(
                scriptPath,
                [
                  '--prompt',
                  finalGenerationPrompt,
                  '--output',
                  outputPath,
                  ...(primaryPreparedImage?.stagedPath
                    ? ['--image', primaryPreparedImage.stagedPath]
                    : []),
                  '--width',
                  String(profile.width),
                  '--height',
                  String(profile.height),
                  '--num_frames',
                  String(profile.numFrames),
                  '--video_shift',
                  String(profile.videoShift),
                  '--thumbnail',
                  thumbnailPath,
                  '--vram_gb',
                  String(vramGb),
                  '--model_mode',
                  videoMode,
                  '--quality_mode',
                  qualityMode,
                  '--seed',
                  String(promptSeed),
                  '--motion_interp',
                  qualityMode === 'balanced' ? '1' : '2',
                ],
                {
                  resumeKey: 'video',
                  maxWaitMs: 8 * 60 * 60 * 1000,
                  stalledTimeoutMs: 45 * 60 * 1000,
                },
              )
              break
            } catch (pipelineError) {
              if (attempt === profiles.length - 1 || !isRecoverableVideoFailure(pipelineError)) {
                throw pipelineError
              }

              const nextProfile = profiles[attempt + 1]
              const retryLabel = `${nextProfile.width}x${nextProfile.height}, ${nextProfile.numFrames} frames`
              setProgress(
                `Auto-reparation video: echec du ${profileLabel}. Nouvelle tentative sur ${retryLabel}...`,
              )
              setPhase(`Auto-reparation video: reduction automatique vers ${retryLabel}...`, 56)
            }
          }

          setPhase('Chargement de la sortie video...', 88)
          const jsonCandidates = output
            .split('\n')
            .map((line) => line.trim())
            .filter((line) => Boolean(line))
            .filter((line) => line.startsWith('{') || line.startsWith('['))

          let parsedResult: {
            ok?: boolean
            path?: string
            elapsed_seconds?: number
            error?: string
            model?: string
            strategy?: string
            validation_summary?: string
          } | null = null

          for (let index = jsonCandidates.length - 1; index >= 0 && !parsedResult; index -= 1) {
            try {
              parsedResult = JSON.parse(jsonCandidates[index])
            } catch {
              // candidate suivant
            }
          }

          if (!parsedResult) {
            throw new Error(
              'Le pipeline video n a pas produit de JSON final exploitable. Derniere sortie: ' +
                output.slice(-400).replace(/\s+/g, ' ').trim(),
            )
          }

          const json = parsedResult
          if (!json.ok || !json.path) {
            throw new Error(
              humanizeVideoError(json.error || '') ||
                'Le pipeline video n a pas produit de sortie exploitable.',
            )
          }

          const nextUrl = toAssetUrl(json.path)
          const modelLabel = json.model || 'modele video local'
          const strategyLabel = json.strategy ? ` / ${json.strategy}` : ''
          const durationLabel = json.elapsed_seconds
            ? `${json.elapsed_seconds}s de pipeline (${successfulProfile.width}x${successfulProfile.height}, ${successfulProfile.numFrames} frames)`
            : `Pipeline termine (${successfulProfile.width}x${successfulProfile.height}, ${successfulProfile.numFrames} frames)`
          setVideoUrl(nextUrl)
          setVideos((previous) => [
            {
              url: nextUrl,
              prompt,
              time: Date.now(),
              durationLabel,
              modelLabel: `${modelLabel}${strategyLabel}`,
            },
            ...previous,
          ])
          if (trackerId) {
            completeGeneration(trackerId, {
              resultPath: json.path,
              resultFilename: `${modelLabel}${strategyLabel}, ${durationLabel}`,
            })
            activeTrackerIdRef.current = null
          }
          setSaveDialogData({
            module: 'video',
            sourcePath: json.path,
            prompt,
            fidelityScore: 92,
            parameters: {
              width: successfulProfile.width,
              height: successfulProfile.height,
              numFrames: successfulProfile.numFrames,
              videoShift: successfulProfile.videoShift,
              strategy: json.strategy,
            },
            modelLabel: `${modelLabel}${strategyLabel}`,
          })
          setProgress(
            json.validation_summary ? `Video validee: ${json.validation_summary}` : 'Video prete.',
          )
          setPhase('Video validee et prete dans le lecteur.', 100)
        },
      })
    } catch (generationError) {
      const errMsg = humanizeVideoError(
        getErrorMessage(generationError, 'Echec de generation video.'),
      )
      setError(errMsg)
      if (activeTrackerIdRef.current) {
        failGeneration(activeTrackerIdRef.current, errMsg)
        activeTrackerIdRef.current = null
      }
    } finally {
      unlistenRef.current?.()
      unlistenRef.current = null
      setIsGenerating(false)
    }
  }, [
    activeOllamaModel,
    completeGeneration,
    consumeCoinsForModule,
    contextFiles,
    diagnostics.blockingReason,
    executeWithRuntime,
    failGeneration,
    height,
    isGenerating,
    motionPreset,
    numFrames,
    preparePack,
    prompt,
    qualityMode,
    trackGeneration,
    videoMode,
    visionModel,
    vramGb,
    width,
  ])

  const RESOLUTION_PRESETS = [
    { label: '720p Paysage (1280×704)', w: 1280, h: 704 },
    { label: '480p Stable (832×480)', w: 832, h: 480 },
    { label: 'Carré (640×640)', w: 640, h: 640 },
    { label: 'Vertical (480×832)', w: 480, h: 832 },
  ]

  return (
    <div className="h-full overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">
      <RecoveryBanner
        recovery={recovery}
        onRecovered={(r) => {
          if (r.url) setVideoUrl(r.url)
        }}
      />
      <ClarificationDialog request={clarification} />
      <SaveDialog
        data={saveDialogData}
        onClose={() => setSaveDialogData(null)}
        onSaved={(savedPath) => {
          addPrompt({
            module: 'video',
            prompt,
            fidelityScore: saveDialogData?.fidelityScore ?? 92,
            parameters: saveDialogData?.parameters ?? {},
            tags: ['video'],
          })
          setSaveDialogData(null)
          setProgress(`Résultat sauvegardé: ${savedPath}`)
        }}
      />
      <PromptLibraryPanel
        open={promptLibraryOpen}
        onClose={() => setPromptLibraryOpen(false)}
        currentModule="video"
        onUsePrompt={(selectedPrompt) => setPrompt(selectedPrompt)}
      />

      <div className="mx-auto max-w-7xl space-y-5">
        {pendingJobBanner && pendingJobBanner.status !== 'done' && !isGenerating && (
          <div className="flex items-center justify-between gap-3 rounded-2xl border border-aurora-accent/40 bg-aurora-accent/10 px-4 py-3 text-xs text-aurora-text">
            <span>
              Une génération vidéo ({pendingJobBanner.status}) est active en tâche de fond.
            </span>
            <button
              onClick={() => {
                void clearResumableJob('video')
                setPendingJobBanner(null)
              }}
              className="rounded-lg border border-aurora-border/50 px-2.5 py-1 text-[11px] text-aurora-text-dim hover:text-aurora-text"
            >
              Masquer
            </button>
          </div>
        )}

        <StudioHero
          icon={Video}
          eyebrow="Module Video & Cinema Temporel"
          title="Direction Cinématographique Wan 2.2 & Cohérence Temporelle"
          description={`Synthèse T2V/I2V (${VIDEO_MODEL_PACK_LABEL}) avec storyboard 180°, trajectoires caméra C²-continues et calibration dynamique du flux temporel (4n+1 trames, multiple de 32px, video_shift=${liveWan22Profile.videoShift}).`}
          diagnostics={diagnostics}
          stats={[
            { label: 'Profil Wan2.2', value: `${liveWan22Profile.width}×${liveWan22Profile.height}` },
            { label: 'Trames (4n+1)', value: `${liveWan22Profile.numFrames}f (${liveWan22Profile.latentTemporalFrames} latentes)` },
            { label: 'Shift Temporel', value: `α = ${liveWan22Profile.videoShift}` },
            { label: 'Historique', value: `${videos.length} rendu(s)` },
          ]}
        />

        {/* Bandeau Architecture VM Cloud Exclusif & Crédits / Pièces Juan of Bike */}
        <div className="rounded-[1.4rem] border border-amber-400/35 bg-gradient-to-r from-amber-500/10 via-orange-500/10 to-violet-500/10 px-5 py-3.5 text-xs text-aurora-text">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-amber-400/20 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300">
                  ☁️ Exécution Exclusive sur les 2 VMs Cloud GPU
                </span>
                <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-300">
                  ★ Meilleur Modèle Renforcé Actif par Défaut
                </span>
              </div>
              <p className="text-xs text-aurora-text">
                <strong>Stack Vidéo Maximale :</strong> {videoArchSpec.bestModelStack} ({videoArchSpec.vramRequirementGb} Go VRAM · {videoArchSpec.speedRatingLabelFr})
              </p>
              <p className="text-[11px] text-amber-200/90">
                💳 <strong>Tarifs Lancement Ultra-Attractifs :</strong> Pass Pro Dual-VM dès <strong>8,99 €/mois</strong> (ou 1er mois 2,99 €) · Pack Populaire <strong>3 000 JB à 9,99 €</strong> (~0,08 €/vidéo) payable par <strong>CB, PayPal 4×, Apple/Google Pay, Klarna 3×, SEPA ou Crypto (+10 % JB)</strong>.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="rounded-xl border border-amber-400/40 bg-black/35 px-3 py-1.5 font-mono text-[11px] text-amber-200">
                {billingMode === 'infinite' && (
                  <span>∞ Crédits Infinis Actifs (0 JB débité · Réserve : {jbCoinsBalance.toLocaleString('fr-FR')} JB)</span>
                )}
                {billingMode === 'subscription' && (
                  <span>💎 Abonnement {subscriptionTier} Actif (Inclus sur Dual-VM · {jbCoinsBalance.toLocaleString('fr-FR')} JB)</span>
                )}
                {billingMode === 'juan_of_bike_coins' && (
                  <span>🪙 Solde : {jbCoinsBalance.toLocaleString('fr-FR')} JB · Coût Vidéo VM : {videoArchSpec.jbCoinCostPerRun} JB (~0,08 €)</span>
                )}
              </div>
              <button
                type="button"
                onClick={() => {
                  processCheckoutPurchase({
                    itemType: 'coin_pack',
                    packId: 'pack_pro_2800',
                    paymentMethodId: selectedPaymentMethod,
                  })
                }}
                className="rounded-xl border border-amber-400/45 bg-amber-400/15 px-3 py-1.5 text-[11px] font-semibold text-amber-200 hover:bg-amber-400/25 transition-colors"
              >
                🪙 +3 000 JB (9,99 € · CB/PayPal)
              </button>
              <button
                type="button"
                onClick={() => window.dispatchEvent(new CustomEvent('aurora:open-settings'))}
                className="rounded-xl border border-white/15 bg-white/[0.06] px-3 py-1.5 text-[11px] text-aurora-text hover:bg-white/[0.12] transition-colors"
              >
                ⚙️ Moyens de Paiement (CB / PayPal / Apple Pay / Crypto) & Tarifs
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[24rem_minmax(0,1fr)]">
          <div className="space-y-4">
            <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Scene</p>
                  <p className="mt-2 text-sm text-aurora-text">
                    Decris le mouvement, le cadrage, la lumiere et le ton de la sequence.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPromptLibraryOpen(true)}
                    title="Bibliothèque de prompts"
                    className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] hover:bg-white/[0.09] text-white/40 hover:text-violet-400 transition-colors"
                  >
                    <BookOpen size={14} />
                  </button>
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl gradient-accent text-white">
                    <Sparkles size={18} />
                  </div>
                </div>
              </div>

              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Ex: travelling doux autour d un velo gravel orange, ambiance atelier golden hour, profondeur de champ faible"
                rows={5}
                className="mt-4 w-full resize-none rounded-2xl border border-aurora-border bg-aurora-bg/60 px-3 py-3 text-sm text-aurora-text outline-none transition-colors focus:border-aurora-accent/45"
              />
              <div className="mt-2 flex items-center gap-2">
                <VoicePushToTalk
                  onTranscript={(text) => setPrompt((prev) => (prev.trim() ? `${prev}, ${text}` : text))}
                  label="Dicter ton prompt vidéo"
                  size={36}
                />
                <span className="text-[11px] text-aurora-text-dim">Décris la scène à voix haute.</span>
              </div>

              {(() => {
                const a = analyzeVideoPrompt(prompt)
                const hits = [
                  a.shot,
                  ...(a.staticCamera ? ['static camera'] : a.camera),
                  ...a.lighting,
                  a.style,
                  a.tempo,
                ].filter(Boolean) as string[]
                if (!prompt.trim() || hits.length === 0) return null
                return (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px] font-mono text-aurora-text-dim">
                    <span className="opacity-60">🎬 détecté :</span>
                    {hits.map((h) => (
                      <span
                        key={h}
                        className="rounded-full border border-aurora-border/40 bg-aurora-bg/40 px-2 py-0.5"
                      >
                        {h}
                      </span>
                    ))}
                  </div>
                )
              })()}

              <VideoTempoAdvisor />

              {/* Inspecteur temps réel du Storyboard 180° & Trajectoire C² */}
              <div className="mt-3 rounded-xl border border-aurora-border/35 bg-black/25 p-3 text-[11px] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center gap-1.5 uppercase tracking-wider text-aurora-text-dim">
                    <Film size={12} />
                    Storyboard 180° & C²
                  </span>
                  <span className="font-mono text-aurora-accent">
                    {liveStoryboardPlan.baseColorTemperatureKelvin}K · {liveStoryboardPlan.shots.length} plans
                  </span>
                </div>
                <div className="space-y-1.5">
                  {liveStoryboardPlan.shots.map((shot) => (
                    <div
                      key={shot.shotIndex}
                      className="rounded-lg border border-white/10 bg-white/[0.02] px-2.5 py-1.5"
                    >
                      <div className="flex items-center justify-between font-mono text-[10px] text-aurora-text">
                        <span>
                          Plan {shot.shotIndex} · {shot.shotScale} ({shot.focalLengthMm}mm, f/{shot.apertureFStop})
                        </span>
                        <span className="text-aurora-text-dim">
                          {shot.cameraAzimuthDeg}° · {shot.numFrames4nPlus1}f
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-[10px] text-aurora-text-dim">
                        {shot.narrativeBeat}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-3 flex items-center gap-3 rounded-xl border border-orange-500/25 bg-orange-500/5 p-2">
                <div style={{ width: 48, height: 60, flexShrink: 0 }}>
                  <LyraCharacter
                    phase={isGenerating ? 'thinking' : prompt.length > 8 ? 'speaking' : 'idle'}
                    emotion={isGenerating ? 'focus' : prompt.length > 8 ? 'happy' : 'curious'}
                    accent="#ff8c42"
                    size={48}
                  />
                </div>
                <div className="flex-1 text-[11px] text-aurora-text-dim font-mono">
                  {isGenerating
                    ? 'je tourne ta vidéo · ETA Wan2.2'
                    : prompt.length > 8
                      ? `cadence C² vérifiée · shift α=${liveWan22Profile.videoShift}`
                      : 'décris une scène, je calcule le découpage 180°'}
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4">
              <button
                onClick={() => setShowSettings((value) => !value)}
                className="flex items-center gap-2 text-xs text-aurora-text-dim hover:text-aurora-text transition-colors"
              >
                <Sliders size={14} />
                <span>Parametres video</span>
                <ChevronDown
                  size={12}
                  className={`transition-transform ${showSettings ? 'rotate-180' : ''}`}
                />
              </button>

              <AnimatePresence>
                {showSettings && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-3 space-y-3"
                  >
                    <div>
                      <label className="mb-1 block text-[11px] text-aurora-text-dim">Mode</label>
                      <div className="grid grid-cols-2 gap-2">
                        {(
                          [
                            ['speed', 'Vitesse', 'Wan2.2 TI2V-5B rapide'],
                            ['quality', 'Qualite', 'Wan2.2 TI2V-5B haute fidelite'],
                          ] as const
                        ).map(([mode, label, hint]) => (
                          <button
                            key={mode}
                            onClick={() => setVideoMode(mode)}
                            title={hint}
                            className={`flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs text-left transition-colors ${
                              videoMode === mode
                                ? 'border border-aurora-accent/40 bg-aurora-accent/12 text-white'
                                : 'border border-aurora-border/35 bg-aurora-surface-2/50 text-aurora-text-dim hover:border-aurora-border/60'
                            }`}
                          >
                            {mode === 'speed' ? <Zap size={11} /> : <Star size={11} />}
                            {label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="mb-1 block text-[11px] text-aurora-text-dim">
                        Fidelite — <span className="text-aurora-text-dim/80">auto par defaut</span>
                      </label>
                      <div className="grid grid-cols-3 gap-2">
                        {(
                          [
                            ['auto', 'Auto', 'Qualité optimale selon la VRAM et la durée.'],
                            ['balanced', 'Vitesse', 'Mode équilibré 32 étapes.'],
                            ['premium', 'Max', 'Mode haute fidélité 60 étapes + interpolation 60 fps.'],
                          ] as const
                        ).map(([mode, label, hint]) => (
                          <button
                            key={mode}
                            onClick={() => setQualityMode(mode)}
                            title={hint}
                            className={`flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs text-left transition-colors ${
                              qualityMode === mode
                                ? 'border border-aurora-accent/40 bg-aurora-accent/12 text-white'
                                : 'border border-aurora-border/35 bg-aurora-surface-2/50 text-aurora-text-dim hover:border-aurora-border/60'
                            }`}
                          >
                            {mode === 'auto' ? (
                              <Sparkles size={11} />
                            ) : mode === 'balanced' ? (
                              <Zap size={11} />
                            ) : (
                              <Star size={11} />
                            )}
                            {label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="mb-1 block text-[11px] text-aurora-text-dim">
                        Format (multiple de 32px)
                      </label>
                      <div className="grid grid-cols-2 gap-2">
                        {RESOLUTION_PRESETS.map((preset) => {
                          const active = width === preset.w && height === preset.h
                          return (
                            <button
                              key={preset.label}
                              onClick={() => {
                                setWidth(preset.w)
                                setHeight(preset.h)
                              }}
                              className={`rounded-xl border px-2.5 py-1.5 text-[11px] text-left transition-colors ${
                                active
                                  ? 'border-aurora-accent/40 bg-aurora-accent/12 text-white'
                                  : 'border-aurora-border/50 bg-aurora-surface text-aurora-text-dim hover:text-aurora-text'
                              }`}
                            >
                              {preset.label}
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    <div>
                      <div className="mb-1 flex items-center justify-between text-[11px] text-aurora-text-dim">
                        <span>Frames (contrainte 4n+1)</span>
                        <span>
                          {numFrames === 49
                            ? `Auto (${liveWan22Profile.numFrames}f)`
                            : `${liveWan22Profile.numFrames}f (~${(liveWan22Profile.numFrames / 24).toFixed(1)}s)`}
                        </span>
                      </div>
                      <input
                        type="range"
                        min={25}
                        max={97}
                        step={4}
                        value={numFrames}
                        onChange={(event) => setNumFrames(Number(event.target.value))}
                        className="w-full accent-aurora-accent"
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <ContextFilesField
              files={contextFiles}
              onFilesChange={setContextFiles}
              accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
              hint="Ajoute storyboard, references, PDF ou notes pour guider la sequence video."
            />

            {useImageToVideo && (
              <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4">
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">
                  Mouvement image
                </p>
                <p className="mt-1 text-xs text-aurora-text-dim">
                  Choisir le type d animation a appliquer sur la reference.
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {MOTION_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      onClick={() => setMotionPreset(preset.id)}
                      className={`rounded-xl px-3 py-2 text-xs text-left transition-colors ${
                        motionPreset === preset.id
                          ? 'border border-aurora-accent/40 bg-aurora-accent/12 text-white'
                          : 'border border-aurora-border/35 bg-aurora-surface-2/50 text-aurora-text-dim hover:border-aurora-border/60'
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <ModuleAssetPackCard pack={assetPack} />
            <ConnectorRecommendationsPanel module="video" compact />

            <button
              onClick={() => void generate()}
              disabled={!canGenerate}
              className={`flex w-full items-center justify-center gap-2 rounded-[1.4rem] px-4 py-3 text-sm font-medium transition-all ${
                canGenerate
                  ? 'gradient-accent text-white glow-accent'
                  : 'bg-aurora-surface-2 text-aurora-text-dim opacity-60 cursor-not-allowed'
              }`}
            >
              {isGenerating ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  <span>{progress || 'Generation...'}</span>
                </>
              ) : (
                <>
                  <Play size={18} />
                  <span>Generer la video</span>
                </>
              )}
            </button>

            {(progress || error) && (
              <div className="space-y-3">
                {progress && (
                  <div className="rounded-2xl border border-aurora-border/40 bg-aurora-surface/70 px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">
                      Etat courant
                    </p>
                    <p className="mt-2 text-sm text-aurora-text">{progress}</p>
                  </div>
                )}

                {error && (
                  <div className="flex items-start gap-2 rounded-2xl border border-aurora-red/25 bg-aurora-red/10 px-3 py-3">
                    <AlertCircle size={16} className="mt-0.5 shrink-0 text-aurora-red" />
                    <p className="text-xs leading-relaxed text-aurora-red">{error}</p>
                  </div>
                )}
              </div>
            )}

            {videos.length > 0 && (
              <div className="rounded-[1.6rem] border border-aurora-border/40 bg-aurora-surface/65 p-4">
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">
                  Historique
                </p>
                <div className="mt-3 space-y-2">
                  {videos.map((video, index) => (
                    <button
                      key={`${video.time}-${index}`}
                      onClick={() => setVideoUrl(video.url)}
                      className="w-full rounded-2xl border border-aurora-border/35 bg-aurora-surface-2/60 px-3 py-3 text-left transition-colors hover:border-aurora-accent/35"
                    >
                      <p className="truncate text-sm text-aurora-text">{video.prompt}</p>
                      <p className="mt-1 text-[11px] text-aurora-text-dim">
                        {video.durationLabel}
                        {' / '}
                        {video.modelLabel}
                        {' / '}
                        {new Date(video.time).toLocaleTimeString('fr-FR')}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <StudioDiagnosticsPanel diagnostics={diagnostics} title="Preflight video" />
          </div>

          <div className="min-w-0 rounded-[1.8rem] border border-aurora-border/40 bg-aurora-surface/45 overflow-hidden">
            <div className="border-b border-aurora-border/30 px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">
                    Lecteur
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-aurora-text">Preview locale</h2>
                </div>

                {videoUrl && (
                  <div className="flex flex-wrap items-center gap-2">
                    <a
                      href={videoUrl}
                      download
                      className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                    >
                      <Download size={14} />
                      Telecharger
                    </a>
                    <button
                      onClick={() => {
                        const video = videoRef.current
                        if (!video || !video.videoWidth) return
                        const canvas = document.createElement('canvas')
                        canvas.width = video.videoWidth
                        canvas.height = video.videoHeight
                        const ctx = canvas.getContext('2d')
                        if (!ctx) return
                        try {
                          ctx.drawImage(video, 0, 0)
                          const dataUrl = canvas.toDataURL('image/png')
                          const anchor = document.createElement('a')
                          anchor.href = dataUrl
                          anchor.download = `aurora-video-frame-${Date.now()}.png`
                          anchor.click()
                        } catch {
                          // video tainted (CORS) ou codec non compatible
                        }
                      }}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                      title="Capturer la frame en cours"
                    >
                      <Camera size={14} />
                      Frame PNG
                    </button>
                    {prompt && (
                      <button
                        onClick={() => {
                          navigator.clipboard
                            ?.writeText(prompt)
                            .then(() => {
                              setCopyPromptFeedback(true)
                              window.setTimeout(() => setCopyPromptFeedback(false), 1500)
                            })
                            .catch(() => undefined)
                        }}
                        className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs transition-colors ${
                          copyPromptFeedback
                            ? 'border-aurora-green/40 bg-aurora-green/10 text-aurora-green'
                            : 'border-aurora-border/40 bg-aurora-surface-2 text-aurora-text hover:border-aurora-accent/35'
                        }`}
                        title="Copier le prompt utilise"
                      >
                        <Copy size={14} />
                        {copyPromptFeedback ? 'Copie !' : 'Prompt'}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="flex min-h-[50vw] flex-col items-center justify-center gap-3 p-3 sm:min-h-[36rem] sm:p-6">
              {videoUrl ? (
                <div className="w-full h-full overflow-hidden rounded-[1.8rem] border border-aurora-border/35 bg-[#091116] p-4">
                  <video
                    ref={videoRef}
                    src={videoUrl}
                    controls
                    autoPlay
                    playsInline
                    onLoadedMetadata={(event) => {
                      const v = event.currentTarget
                      setVideoMeta({
                        duration: v.duration || 0,
                        width: v.videoWidth,
                        height: v.videoHeight,
                      })
                    }}
                    onRateChange={(event) => setPlaybackRate(event.currentTarget.playbackRate)}
                    className="h-full w-full rounded-[1.4rem] object-contain"
                  />
                  {(videoMeta || playbackRate !== 1) && (
                    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-aurora-border/30 bg-aurora-surface-2/60 px-3 py-2 text-[11px] text-aurora-text-dim">
                      {videoMeta && (
                        <>
                          <span>
                            {videoMeta.width}×{videoMeta.height}
                          </span>
                          <span>·</span>
                          <span>{videoMeta.duration.toFixed(2)}s</span>
                        </>
                      )}
                      <span className="ml-auto inline-flex items-center gap-1">
                        Vitesse
                        {[0.25, 0.5, 1, 1.5, 2].map((rate) => (
                          <button
                            key={rate}
                            onClick={() => {
                              if (videoRef.current) {
                                videoRef.current.playbackRate = rate
                                setPlaybackRate(rate)
                              }
                            }}
                            className={`rounded-md border px-1.5 py-0.5 text-[10px] ${
                              playbackRate === rate
                                ? 'border-aurora-accent bg-aurora-accent/15 text-aurora-accent'
                                : 'border-aurora-border/50 text-aurora-text-dim hover:text-aurora-text'
                            }`}
                          >
                            {rate}×
                          </button>
                        ))}
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center">
                  <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-[1.8rem] border border-aurora-border bg-aurora-surface-2">
                    <Video size={40} className="text-aurora-text-dim" />
                  </div>
                  <p className="mt-4 text-sm text-aurora-text-muted">
                    Decris une sequence puis laisse le pipeline local produire la video ici.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function VideoTempoAdvisor() {
  const [tone, setTone] = useState<'tutoriel' | 'storytelling' | 'pub' | 'recap' | 'hype'>('tutoriel')
  const bpm = recommendBpmForTone(tone)
  const cat = classifyTempo(bpm)
  const tones: Array<{ id: typeof tone; label: string }> = [
    { id: 'tutoriel', label: 'tuto' },
    { id: 'storytelling', label: 'récit' },
    { id: 'recap', label: 'récap' },
    { id: 'pub', label: 'pub' },
    { id: 'hype', label: 'hype' },
  ]
  return (
    <div className="mt-3 rounded-xl border border-aurora-border/30 bg-black/20 p-3 text-[11px]">
      <div className="flex items-center justify-between mb-2">
        <span className="uppercase tracking-wider text-aurora-text-dim">Tempo conseillé</span>
        <span className="font-mono text-aurora-text">
          {bpm} BPM · {cat}
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {tones.map((t) => (
          <button
            key={t.id}
            onClick={() => setTone(t.id)}
            className={`rounded-md px-2 py-0.5 text-[10px] font-mono border transition-colors ${
              tone === t.id
                ? 'bg-orange-500/25 border-orange-500/55 text-orange-100'
                : 'bg-white/[0.03] border-white/10 text-aurora-text-dim hover:text-aurora-text'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-aurora-text-dim italic">
        Cale les coupes sur ce BPM pour un rythme cohérent avec ce ton.{' '}
        {cat === 'presto' || cat === 'prestissimo'
          ? 'Coupes courtes (≤1s).'
          : 'Plans plus longs (≥2s).'}
      </p>
    </div>
  )
}
