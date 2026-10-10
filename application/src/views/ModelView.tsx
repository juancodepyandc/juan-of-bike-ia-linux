import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, BookOpen, Box, Check, Globe, Image as ImageIcon, Layers3, Loader2, Lock, Orbit, Palette, Sparkles, X } from 'lucide-react'
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { Center, OrbitControls } from '@react-three/drei'
import { ACESFilmicToneMapping, AnimationClip, AnimationMixer, AxesHelper, Box3, Color, Group, LoopRepeat, Mesh, MeshPhysicalMaterial, MeshStandardMaterial, NearestFilter, Object3D, RepeatWrapping, SkeletonHelper, SkinnedMesh, SRGBColorSpace, Vector3 } from 'three'
import type { Texture } from 'three'
import ClarificationDialog from '../components/ClarificationDialog.tsx'
import { ThreeDProgressOverlay } from '../components/ThreeDProgressOverlay.tsx'
import type { ClarificationRequest } from '../components/ClarificationDialog.tsx'
import ContextFilesField from '../components/ContextFilesField.tsx'
import SubjectSelectPanel from '../components/SubjectSelectPanel.tsx'
import VoicePushToTalk from '../components/VoicePushToTalk.tsx'
import ModuleAssetPackCard from '../components/ModuleAssetPackCard.tsx'
import ConnectorRecommendationsPanel from '../components/ConnectorRecommendationsPanel.tsx'
import PromptLibraryPanel from '../components/PromptLibraryPanel.tsx'
import SaveDialog from '../components/SaveDialog.tsx'
import type { SaveDialogData } from '../components/SaveDialog.tsx'
import SessionSwitcher from '../components/SessionSwitcher.tsx'
import { buildThreeDModuleAssets } from '../config/moduleAssetPacks.ts'
import { AUXILIARY_ANALYSIS_MODEL, THREE_D_MODEL_PACK_LABEL } from '../config/models.ts'
import { clearResumableJob, comfyuiGetHistory, comfyuiGetImage, comfyuiQueuePrompt, freeGpuBeforeFlux, fsExists, fsMkdir, fsReadBinary, fsWriteBinary, getWorkspacePath, onPythonProgress, peekResumableJob, runPythonScript, toAssetUrl } from '../hooks/useTauri.ts'
import { emitGenerationFx, fxAsk } from '../components/generationFx/fxBus.ts'
import { StudioDiagnosticsPanel, StudioHero } from '../components/StudioHero.tsx'
import { useManagedRuntime } from '../hooks/useManagedRuntime.ts'
import { useModuleAssetPack } from '../hooks/useModuleAssetPack.ts'
import { useStudioDiagnostics } from '../hooks/useStudioDiagnostics.ts'
import { prepareTaskIntelligence } from '../services/taskIntelligence.ts'
import { prepareThreeDReferenceSupport, type ThreeDReferenceSupport } from '../services/threeDReferenceSupport.ts'
import { detectUploadedImageView, prepareThreeDViewPlan, resolvePreparedReferenceViews, verifyViewImage, buildCorrectedViewDirective, getSyntheticViewDirective, type ThreeDViewPlan, type ThreeDViewTag, type ThreeDViewAssignment, type ThreeDViewOverlay } from '../services/threeDViewPlanner.ts'
import { analyzeReferenceImage, mergePaletteWithOverrides, parseColorOverridesFromPrompt, type VisualReferenceAnalysis, type ReferencePaletteEntry, type ColorOverride } from '../services/visualReferenceAnalyzer.ts'
import ReferenceInspectorPanel from '../components/ReferenceInspectorPanel.tsx'
import EngineeringExportPanel from '../components/EngineeringExportPanel.tsx'
import { analyzeThreeDIntent, buildFluxVisualDescription, buildMeshCorrectionStrategy, detectMotionVerbHint, inferPbrProfile, previewThreeDIntent, verify3DMeshFidelity, type PbrProfile, type ThreeDIntent, type ThreeDMotionPreset, type ThreeDPipeline, type ThreeDPipelineRouting, type MeshFidelityVerification, type MeshCorrectionStrategy } from '../services/threeDIntent.ts'
import { runProceduralModeling, runAutoRig, runMeshValidation, runMeshCleanup, renderMeshScreenshot, type BlenderScriptResult, type MeshValidationReport } from '../services/blenderBridge.ts'
import { runAutoRigFromPrompt } from '../services/motionPipeline.ts'
import { verifyGeneratedReferenceVisual } from '../services/referenceVisualResearch.ts'
import { useAppStore } from '../stores/appStore.ts'
import { useModuleHistoryStore, type ConversationSession } from '../stores/moduleHistoryStore.ts'
import { usePromptLibraryStore } from '../stores/promptLibraryStore.ts'
import { extractComfyHistoryFailure, extractComfyImageOutput, extractComfyPromptId } from '../utils/comfyui.ts'
import { getErrorMessage } from '../utils/errors.ts'
import { useGenerationTrackerStore } from '../stores/generationTrackerStore.ts'
import { useGenerationRecovery } from '../hooks/useGenerationRecovery.ts'
import RecoveryBanner from '../components/RecoveryBanner.tsx'
import { createFlux2Workflow, type FluxStyle } from '../utils/fluxWorkflow.ts'
import { prepareContextFiles, type PreparedContextFile } from '../utils/multimodalContext.ts'
import { pickPrimaryPreparedImage, stageBlobToComfyInput } from '../utils/referenceMedia.ts'
import type { HardwareProfile } from '../types/app.ts'
import { readUiSkin } from '../utils/uiSkin.ts'

const AURORA_V4_SKIN = readUiSkin() === 'aurora_v4'
const COLORS = ['#ff6a3d', '#37c7bf', '#ffd166', '#4dd5a4', '#7fb7ff']
const EDIT_INTENT = /(?:^|\b)(ajoute|ajouter|enleve|enlever|retire|retirer|supprime|supprimer|change|changer|modifie|modifier|remplace|remplacer|mets|met|mettre|rajoute|rajouter|deplace|deplacer|transforme|transformer|ameliore|ameliorer|corrige|corriger|plus fin|plus epais|plus large|plus haut|sans le|sans la|sans les|avec un|avec une|avec des|garde|conserve|preserve|same object|same part|meme objet|meme piece)/i
type GeoChild = Object3D & { geometry?: { dispose?: () => void } }
type Mat = { dispose?: () => void }
type MatChild = Object3D & { material?: Mat | Mat[] }
type ModelGenerationResult = { ok?: boolean; path?: string; outputPath?: string; engine?: string; error?: string; format?: 'glb' | 'obj'; shape_model?: string; shape_subfolder?: string; shape_weight_format?: string; shape_runtime?: string; shape_strategy?: string; shape_offload?: boolean; texture_model?: string; texture_strategy?: string; paint_offload?: boolean; textured?: boolean; fallback_used?: boolean; compatibility_reason?: string | null; shape_input_mode?: 'single_view' | 'multiview'; multiview_used?: boolean; view_count?: number; license?: string; eu_compliant?: boolean; pipeline?: ThreeDPipeline; animationFrames?: number; kinematicRatio?: number; rigBones?: number; validationReport?: MeshValidationReport; mesh_quality_ok?: boolean; mesh_quality_issues?: string[]; mesh_quality_warnings?: string[]; mesh_geometry_grade?: string; mesh_vertex_count?: number; mesh_face_count?: number; mesh_extents?: [number, number, number]; mesh_flatness_ratio?: number; mesh_aspect_ratio?: number; mesh_humanoid_aspect_ratio?: number | null; mesh_head_vertex_fraction?: number | null; mesh_head_body_width_ratio?: number | null; mesh_disconnected_bodies?: number; mesh_degenerate_face_count?: number; mesh_is_watertight?: boolean; mesh_surface_area?: number; mesh_volume?: number }
type ReferenceSeedOrigin = 'user' | 'session' | 'external' | null
type MaterializedViewPlan = {
  assignments: Array<{ view: ThreeDViewTag; path: string }>
  primaryPath: string | null
  summary: string | null
}
type ViewerConfig = {
  autoRotate: boolean
  lockView: boolean
  cameraPosition: [number, number, number]
  modeLabel: string
  modeDetail: string
}
type ViewerMaterialMode = 'authored' | 'diagnostic'

function disposeTree(object: Object3D | null) {
  if (!object) return
  object.traverse((child) => {
    const geoChild = child as GeoChild
    if (geoChild.geometry && typeof geoChild.geometry.dispose === 'function') geoChild.geometry.dispose()
    const matChild = child as MatChild
    if (matChild.material) (Array.isArray(matChild.material) ? matChild.material : [matChild.material]).forEach((material) => material?.dispose?.())
  })
}

function short(text: string, limit = 180) {
  const normalized = text.replace(/\s+/g, ' ').trim()
  return normalized.length <= limit ? normalized : `${normalized.slice(0, limit)}...`
}

function safeOutputSegment(value: string | null | undefined, fallback: string) {
  const cleaned = (value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9._-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 80)
  return cleaned || fallback
}

function buildPromptTopicSegment(prompt: string | null | undefined, fallback = 'conversation_3d') {
  const normalized = (prompt || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
  const topicRules: Array<[RegExp, string]> = [
    [/\b(macarena|danse|dance|dancing|personnage|character|humanoid|avatar)\b/, 'personnage_danse'],
    [/\b(strimer|lian\s+li|24\s*-?\s*pin|12vhpwr)\b/, 'strimer_plus_v2'],
    [/\b(courroie|belt|poulie|pulley|transmission)\b/, 'mecanisme_poulie_courroie'],
    [/\b(engrenage|gear|pignon|gearbox)\b/, 'mecanisme_engrenages'],
    [/\b(paysage|landscape|terrain|vallee|montagne|forest|foret)\b/, 'paysage_3d'],
    [/\b(motherboard|carte\s+mere|pcb|x870e|rog)\b/, 'carte_mere_3d'],
  ]
  for (const [pattern, label] of topicRules) {
    if (pattern.test(normalized)) return label
  }
  const stop = new Set([
    'un', 'une', 'le', 'la', 'les', 'des', 'de', 'du', 'avec', 'pour', 'qui', 'que',
    'je', 'veux', 'vrai', 'vraie', 'modele', 'model', '3d', 'realiste', 'texture',
    'a', 'the', 'and', 'with', 'for', 'of', 'in', 'on', 'real', 'make', 'create',
  ])
  const words = normalized
    .replace(/[^a-z0-9\s_-]+/g, ' ')
    .split(/\s+/)
    .filter((word) => word.length > 2 && !stop.has(word))
    .slice(0, 4)
  return safeOutputSegment(words.join('_'), fallback)
}

function utf8Bytes(text: string) {
  return Array.from(new TextEncoder().encode(text))
}

function buildThreeDRunOutputPaths(workspacePath: string, session: ConversationSession, runId: string, prompt?: string) {
  const genericTitle = /^(nouvelle_conversation|new_chat|conversation|conversation_3d|module_3d|3d|codex_current|session)$/i
  const sessionTitleRaw = safeOutputSegment(session.title, '')
  const sessionTitle = sessionTitleRaw && !genericTitle.test(sessionTitleRaw)
    ? sessionTitleRaw
    : buildPromptTopicSegment(prompt, 'conversation_3d')
  const sessionId = safeOutputSegment(session.id.replace(/^session-/, ''), 'session').slice(0, 18)
  const conversationDir = `${workspacePath}/output/3d/conversations/${sessionTitle}_${sessionId}`
  const root = `${conversationDir}/${runId}`
  return {
    conversationDir,
    root,
    references: `${root}/references`,
    prompts: `${root}/prompts`,
    models: `${root}/models`,
    motion: `${root}/motion`,
    audits: `${root}/audits`,
    work: `${root}/work`,
    rescue: `${root}/rescue`,
  }
}

function buildColorLoadOutputDir(workspacePath: string, meshPath: string) {
  const normalized = meshPath.replace(/\\/g, '/')
  const marker = '/models/'
  const markerIndex = normalized.lastIndexOf(marker)
  if (markerIndex >= 0) {
    return `${normalized.slice(0, markerIndex)}/rescue/color_load_${Date.now()}`
  }
  return `${workspacePath}/output/3d/color_load_${Date.now()}`
}

function parseLastJsonLine(output: string) {
  const lines = output.split('\n').map((line) => line.trim()).filter(Boolean)
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try {
      return JSON.parse(lines[index]) as ModelGenerationResult
    } catch {}
  }
  return null
}

function buildConversationContext(history: Array<{ role: 'user' | 'assistant'; content: string }>) {
  return history.slice(-4).map((message) => `${message.role.toUpperCase()}: ${short(message.content, 220)}`).join('\n')
}

function promptExplicitlyRequestsBackground(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(background|backdrop|fond|decor|d[ée]cor|scene|environment|environnement|landscape|paysage|cityscape|dans une scene|dans un decor|sur un fond)\b/i.test(normalized)
}

function promptExplicitlyRequestsHostDevice(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(pc complet|full pc|entire case|boitier complet|tour complete|whole computer|inside a case|dans un boitier|dans une tour)\b/i.test(normalized)
}

function isLedCablePrompt(prompt: string, intent: ThreeDIntent) {
  return intent.systemClass === 'pc_cabling'
    && /\b(strimer|argb|rgb|led|light guide|diffuser|12vhpwr|24 pin|24-pin|8 pin|8-pin|pcie extension|extension cable)\b/i.test(prompt.toLowerCase())
}

function shouldForceBlackBackdrop(prompt: string, intent: ThreeDIntent) {
  return isCharacterLike(intent) && !promptExplicitlyRequestsBackground(prompt)
}

async function materializeViewPlan(
  plan: ThreeDViewPlan,
  outputDir: string,
  runId: string,
) {
  const resolvedPaths = new Map<ThreeDViewTag, string>()

  for (const assignment of plan.assignments) {
    if (assignment.sourceKind === 'user' && assignment.file?.stagedPath) {
      resolvedPaths.set(assignment.view, assignment.file.stagedPath)
      continue
    }

    if (assignment.sourceKind === 'external' && assignment.externalReference) {
      const targetPath = `${outputDir}/${runId}_${assignment.view}_reference.png`
      await fsWriteBinary(targetPath, Array.from(new Uint8Array(await assignment.externalReference.blob.arrayBuffer())))
      resolvedPaths.set(assignment.view, targetPath)
      continue
    }

    if (assignment.sourceKind === 'reuse' && assignment.reuseFrom) {
      const reusedPath = resolvedPaths.get(assignment.reuseFrom)
      if (reusedPath) {
        resolvedPaths.set(assignment.view, reusedPath)
      }
      continue
    }

    // Synthetic views are resolved later via FLUX generation
    if (assignment.sourceKind === 'synthetic' && assignment.resolvedBlob) {
      const targetPath = `${outputDir}/${runId}_${assignment.view}_synthetic.png`
      await fsWriteBinary(targetPath, Array.from(new Uint8Array(await assignment.resolvedBlob.arrayBuffer())))
      resolvedPaths.set(assignment.view, targetPath)
    }
  }

  const assignments = plan.assignments.flatMap((assignment) => {
    const path = resolvedPaths.get(assignment.view)
    return path ? [{ view: assignment.view, path }] : []
  })

  return {
    assignments,
    primaryPath: resolvedPaths.get(plan.primaryView) || assignments[0]?.path || null,
    summary: assignments.length >= 2 ? assignments.map((assignment) => assignment.view).join(', ') : null,
  } satisfies MaterializedViewPlan
}

/**
 * Generate a single synthetic view via FLUX and return the blob.
 * Used for autonomous multi-view generation when external search fails.
 */
async function generateSyntheticView(
  fluxPrompt: string,
  style: FluxStyle,
  width: number,
  height: number,
  steps: number,
  filenamePrefix: string,
  referenceSeed: { filename: string; denoise?: number } | null,
  ensureComfy: () => Promise<void>,
  vramGuard?: { ollamaModelsToEvict: string[] },
): Promise<Blob> {
  // Start the image service only when this route actually renders an image.
  await ensureComfy()
  // Enforce single-entity, single-view constraint at FLUX prompt level
  const antiSplitSuffix = ', THIS IMAGE MUST SHOW EXACTLY ONE ENTITY FROM ONE SINGLE ANGLE, NEVER split into panels, NEVER show side-by-side views, NEVER generate a multi-view composite, the ENTIRE canvas is ONE continuous single-angle image of ONE subject, no mirror copies, no turnaround sheet'
  const safePrompt = fluxPrompt + antiSplitSuffix

  // FLUX.1 (unet 17.2G + t5xxl + clip_l + ae: les SEULS poids reellement presents).
  // Les fichiers FLUX.2 du disque sont des telechargements tronques de 133 octets:
  // ComfyUI y lit 33.8 Go de tenseurs declares, tente de les charger et SEGFAUTE
  // (c'etait aussi l'origine de "Could not find schema for aten::matmul").
  const workflow = createFlux2Workflow({
    prompt: safePrompt,
    width,
    height,
    steps,
    filenamePrefix,
  })
  // Free VRAM before each FLUX queue: on a 16 GB card, FLUX UNet + T5 XXL
  // alone eat ~22 GiB so anything else pinned (vision LLM, previous CLIP
  // residue) crashes the next CLIPTextEncodeFlux step with OOM.
  if (vramGuard) {
    await freeGpuBeforeFlux(vramGuard.ollamaModelsToEvict)
  }
  const queueResult = await comfyuiQueuePrompt(workflow)
  const promptId = extractComfyPromptId(queueResult)

  const imageResult = await new Promise<{ filename: string; subfolder: string }>((resolve, reject) => {
    let attempts = 0
    const poll = setInterval(async () => {
      attempts += 1
      // FLUX.2 Q4: ~9 min MESUREES par rendu (chargement 19 Go compris).
      // L'ancien seuil de 240 s datait de FLUX.1 et tuait la generation en
      // plein rendu legitime ("Timeout generation vue synthetique").
      if (attempts > 1200) { clearInterval(poll); reject(new Error('Timeout generation vue synthetique (20 min).')); return }
      try {
        const history = await comfyuiGetHistory(promptId)
        const entry = history?.[promptId]
        if (!entry) return
        if (entry.status?.status_str === 'error') { clearInterval(poll); reject(new Error(extractComfyHistoryFailure(entry) || 'Erreur generation vue synthetique.')); return }
        if (entry.status?.completed) { clearInterval(poll); resolve(extractComfyImageOutput(entry)); return }
      } catch (e) {
        const m = e instanceof Error ? e.message : ''
        if (m.includes('aucune image') || m.includes('refuse')) { clearInterval(poll); reject(e) }
      }
    }, 1000)
  })

  return comfyuiGetImage(imageResult.filename, imageResult.subfolder)
}

/**
 * Generate all synthetic views, verify them, and retry once if verification fails.
 */
async function generateAndVerifySyntheticViews({
  plan,
  intent,
  referenceSupport,
  prompt,
  model,
  style,
  width,
  height,
  steps,
  runId,
  outputDir,
  frontSeedFilename,
  setPhase,
  ensureComfy,
  vramGuard,
}: {
  plan: ThreeDViewPlan
  intent: ThreeDIntent
  referenceSupport: ThreeDReferenceSupport
  prompt: string
  model: string
  style: FluxStyle
  width: number
  height: number
  steps: number
  runId: string
  outputDir: string
  frontSeedFilename: string | null
  setPhase: (message: string, progress: number) => void
  ensureComfy: () => Promise<void>
  vramGuard?: { ollamaModelsToEvict: string[] }
}): Promise<ThreeDViewAssignment[]> {
  const syntheticAssignments = plan.assignments.filter((a) => a.sourceKind === 'synthetic')
  if (syntheticAssignments.length === 0) return plan.assignments

  const updatedAssignments = [...plan.assignments]

  for (let viewIndex = 0; viewIndex < syntheticAssignments.length; viewIndex++) {
    const assignment = syntheticAssignments[viewIndex]
    const directive = getSyntheticViewDirective(assignment)
    if (!directive) continue

    const viewLabel = assignment.view
    setPhase(`Référence photo — vue ${viewLabel} (${viewIndex + 1}/${syntheticAssignments.length})...`, 25 + viewIndex * 2)

    // Use the front view as an identity seed for the other angles. By the time
    // we hit the synthetic branch, symmetric views have already been resolved
    // via the reuseMap, so any view still reaching this code is known to
    // differ from the front (back of a character/GPU, asymmetric side of a
    // cable, etc.). Low denoise keeps FLUX too anchored to the front — the
    // back of a GPU ends up looking like the front with a swap of logo — so
    // we push denoise high enough to let the silhouette and features rotate
    // while the seed still provides palette, lighting and proportions.
    // Character creatures are the only subjects where we know left/right are
    // true mirrors of each other, so we keep those slightly tighter.
    const isCharacterLike = intent.subjectKind === 'character' || intent.subjectKind === 'creature' || intent.purpose === 'character'
    const seedDenoise = assignment.view === 'back'
      ? 0.72
      : isCharacterLike
        ? 0.58
        : 0.64
    const seed = frontSeedFilename && assignment.view !== 'front'
      ? { filename: frontSeedFilename, denoise: seedDenoise }
      : null

    let blob: Blob
    let verification
    let retryCount = 0
    let currentDirective = directive

    // Generate + verify loop (max 2 attempts)
    while (retryCount < 2) {
      try {
        blob = await generateSyntheticView(
          currentDirective,
          style,
          width,
          height,
          steps,
          `${runId}_${viewLabel}_synth`,
          seed,
          ensureComfy,
          vramGuard,
        )

        // Verify the generated view
        const base64 = btoa(String.fromCharCode(...new Uint8Array(await blob.arrayBuffer())))
        // Build a minimal strategy for verification
        const verificationStrategy = {
          needsMultiview: true,
          requiredViews: plan.assignments.map((a) => a.view),
          optionalViews: [] as ThreeDViewTag[],
          reuseMap: {},
          verificationChecks: plan.verificationNotes,
          lightingRequirements: plan.lightingNotes,
          viewRequirements: {} as Partial<Record<ThreeDViewTag, string[]>>,
          viewGenerationDirectives: {} as Partial<Record<ThreeDViewTag, string>>,
        }

        verification = await verifyViewImage({
          view: viewLabel,
          imageBase64: base64,
          prompt,
          model,
          strategy: verificationStrategy,
          referenceSupport,
        })

        if (verification.passed || retryCount >= 1) {
          // Accept this view (either passed or we've exhausted retries)
          const idx = updatedAssignments.findIndex((a) => a.view === viewLabel)
          if (idx >= 0) {
            updatedAssignments[idx] = {
              ...assignment,
              resolvedBlob: blob,
              verification,
              notes: [
                ...assignment.notes,
                verification.passed
                  ? `vue ${viewLabel} generee et verifiee avec succes`
                  : `vue ${viewLabel} generee (verification partielle: ${verification.notes})`,
                verification.functionalDetailsFound.length > 0
                  ? `details fonctionnels trouves: ${verification.functionalDetailsFound.join(', ')}`
                  : '',
                verification.functionalDetailsMissing.length > 0
                  ? `details manquants: ${verification.functionalDetailsMissing.join(', ')}`
                  : '',
              ].filter(Boolean),
            }
          }
          break
        }

        // Verification failed - build corrected directive and retry
        retryCount++
        setPhase(`Correction de la vue ${viewLabel} (tentative ${retryCount + 1})...`, 67 + viewIndex * 3)
        const corrected = buildCorrectedViewDirective(
          { ...assignment, syntheticPrompt: currentDirective },
          verification,
        )
        if (corrected) {
          currentDirective = corrected
        }
      } catch {
        // Generation failed entirely - mark as failed but don't block
        const idx = updatedAssignments.findIndex((a) => a.view === viewLabel)
        if (idx >= 0) {
          updatedAssignments[idx] = {
            ...assignment,
            notes: [...assignment.notes, `vue ${viewLabel}: echec de generation synthetique, vue omise`],
          }
        }
        break
      }
    }
  }

  return updatedAssignments
}

async function runReferenceWorkflow({
  workflow,
  setPhase,
  pollRef,
  phaseStart = 70,
  label = 'Rendu de la reference en cours...',
  ensureComfy,
  vramGuard,
}: {
  workflow: Record<string, unknown>
  setPhase: (message: string, progress: number) => void
  pollRef: { current: ReturnType<typeof setInterval> | null }
  phaseStart?: number
  label?: string
  ensureComfy: () => Promise<void>
  vramGuard?: { ollamaModelsToEvict: string[] }
}) {
  await ensureComfy()
  if (vramGuard) {
    await freeGpuBeforeFlux(vramGuard.ollamaModelsToEvict)
  }
  const queueResult = await comfyuiQueuePrompt(workflow)
  const promptId = extractComfyPromptId(queueResult)
  setPhase(label, phaseStart)

  const imageResult = await new Promise<{ filename: string; subfolder: string }>((resolve, reject) => {
    let attempts = 0
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      attempts += 1
      setPhase(`${label} (${attempts}s)`, Math.min(78, phaseStart + Math.round((attempts / 300) * 8)))
      if (attempts > 300) {
        clearInterval(pollRef.current!)
        pollRef.current = null
        reject(new Error('Timeout pendant la generation de reference 3D.'))
        return
      }

      try {
        const history = await comfyuiGetHistory(promptId)
        const entry = history?.[promptId]
        if (!entry) return
        if (entry.status?.status_str === 'error') {
          clearInterval(pollRef.current!)
          pollRef.current = null
          reject(new Error(extractComfyHistoryFailure(entry) || 'ComfyUI a signale une erreur pendant la reference 3D.'))
          return
        }
        if (entry.status?.completed) {
          clearInterval(pollRef.current!)
          pollRef.current = null
          resolve(extractComfyImageOutput(entry))
          return
        }
      } catch (e) {
        const m = e instanceof Error ? e.message : ''
        if (m.includes('aucune image') || m.includes('refuse')) {
          clearInterval(pollRef.current!)
          pollRef.current = null
          reject(e)
        }
      }
    }, 1000)
  })

  return comfyuiGetImage(imageResult.filename, imageResult.subfolder)
}

function buildReferencePrompt(
  prompt: string,
  intent: ThreeDIntent,
  motionPreset: ThreeDMotionPreset | null = null,
  referenceSupport: ThreeDReferenceSupport | null = null,
  viewPlan: ThreeDViewPlan | null = null,
  sourcePrompt = prompt,
) {
  const forceBlackBackdrop = shouldForceBlackBackdrop(sourcePrompt, intent)
  const ledCablePrompt = isLedCablePrompt(sourcePrompt, intent)
  const hideHostDevice = ledCablePrompt && !promptExplicitlyRequestsHostDevice(sourcePrompt)

  // Separate product/subject identity lines from general reference additions
  const identityLines = intent.referencePromptAdditions.filter((line) =>
    /^(THIS IS NOT|Visual description:|DO NOT generate|Generate ONLY|The .+ is a|.+ variant:)/i.test(line),
  )
  const otherAdditions = intent.referencePromptAdditions.filter((line) => !identityLines.includes(line))

  return [
    prompt,

    // PRODUCT/SUBJECT IDENTITY — FIRST, so FLUX's text encoder sees it early
    ...(identityLines.length > 0 ? [
      '',
      'MANDATORY SUBJECT IDENTITY:',
      ...identityLines.map((line) => `${line}`),
    ] : []),

    // MOTION PRESET — STRONG, right after identity
    ...(motionPreset ? [
      '',
      'MANDATORY POSE/MOTION:',
      `The subject MUST be shown in this exact state: ${motionPreset.promptDirective}`,
    ] : []),

    '',
    '3D reference image contract:',
    '- THIS IMAGE MUST SHOW EXACTLY ONE ENTITY FROM ONE SINGLE ANGLE',
    '- CRITICAL: Show the subject at a THREE-QUARTER ANGLE (slightly rotated) so that 3 faces are visible (front + one side + top)',
    '- NEVER generate a flat front-on view — depth cues are required for proper 3D reconstruction',
    '- The image must look like a professional 3D product photograph with visible DEPTH, VOLUME and SHADOWS',
    '- Strong directional lighting to reveal all surface details: edges, bevels, recesses, holes, buttons, ports',
    '- Do not use cube/block/sphere/cylinder placeholders or basic primitives unless the user explicitly asked for that primitive',
    '- Material fidelity is mandatory: show real texture cues and distinct material zones, not a flat 2D picture pasted onto a simple block',
    '- If motion is requested, make the moving parts visually separate and riggable; whole-object rotation is not a substitute for wheels, limbs, fans, gears, LEDs, screens or hinges moving',
    '- NEVER split the image into multiple panels or side-by-side views',
    '- NEVER render left and right views on the same image',
    '- NEVER generate a multi-view composite or turnaround sheet',
    '- the ENTIRE canvas is ONE continuous single-angle photograph of ONE subject',
    '- no mirror copies, no duplicated subjects, no tiled views',
    `- purpose: ${intent.purpose}`,
    `- subject kind: ${intent.subjectKind}`,
    `- system class: ${intent.systemClass}`,
    `- representation goal: ${intent.representationGoal}`,
    `- reference framing: ${intent.referenceFraming}`,
    referenceSupport ? `- reference mode: ${referenceSupport.referenceMode}` : '',
    referenceSupport ? `- dimension strategy: ${referenceSupport.dimensionStrategy}` : '',
    referenceSupport?.searchProfile.subjectLabel ? `- exact subject label: ${referenceSupport.searchProfile.subjectLabel}` : '',
    referenceSupport?.searchProfile.requiredElements.length ? `- required visible elements: ${referenceSupport.searchProfile.requiredElements.join(', ')}` : '',
    referenceSupport?.searchProfile.forbiddenElements.length ? `- forbidden parasite elements: ${referenceSupport.searchProfile.forbiddenElements.join(', ')}` : '',
    intent.movingPartsFocus.length > 0 ? `- moving parts focus: ${intent.movingPartsFocus.join(', ')}` : '',
    intent.anchoredPartsFocus.length > 0 ? `- anchored parts focus: ${intent.anchoredPartsFocus.join(', ')}` : '',
    ...otherAdditions.map((item) => `- ${item}`),
    ...intent.meshConstraints.slice(0, 4).map((item) => `- ${item}`),
    ...intent.motionGuidance.slice(0, 3).map((item) => `- ${item}`),
    ...(referenceSupport?.dimensionNotes || []).map((item) => `- researched dimensions: ${item}`),
    ...(referenceSupport?.sourceNotes || []).map((item) => `- ${item}`),
    forceBlackBackdrop
      ? '- background: solid black studio backdrop unless the user explicitly requested another background'
      : '',
    forceBlackBackdrop
      ? '- no scenery, no environmental props, no extra characters, no mascot companions'
      : '',
    ledCablePrompt
      ? '- keep the requested LED or RGB cable assembly isolated, crisp and readable'
      : '',
    hideHostDevice
      ? '- do not generate a full PC case or host device around the cable unless explicitly requested'
      : '',
    ledCablePrompt
      ? '- preserve light guides, sleeves, comb spacing and connector orientation without deformation'
      : '',
    referenceSupport?.referenceMode === 'exact_reference'
      ? '- preserve the recognizable identity of the known reference subject before stylizing or cleaning the view'
      : '',
    referenceSupport?.dimensionStrategy === 'auto_researched'
      ? '- keep researched dimensional relationships unless the user explicitly overrides the size'
      : '',
  ].filter(Boolean).join('\n')
}

function resolveReferenceMinimumScore(referenceSupport: ThreeDReferenceSupport | null) {
  if (!referenceSupport) return 72
  return referenceSupport.searchProfile.minimumScore
    ?? (referenceSupport.searchProfile.strictIdentity ? 84 : 72)
}

function buildReferenceCorrectionPrompt(
  basePrompt: string,
  intent: ThreeDIntent,
  referenceSupport: ThreeDReferenceSupport,
  failureNotes: string,
) {
  return [
    basePrompt,
    '',
    'Auto-correction after failed reference verification:',
    `- previous attempt issue: ${failureNotes}`,
    referenceSupport.searchProfile.subjectLabel
      ? `- regenerate EXACTLY this subject: ${referenceSupport.searchProfile.subjectLabel}`
      : '',
    `- keep framing: ${intent.referenceFraming}`,
    ...(referenceSupport.searchProfile.requiredElements || []).map((item) => `- must visibly include: ${item}`),
    ...(referenceSupport.searchProfile.forbiddenElements || []).slice(0, 6).map((item) => `- strictly forbid: ${item}`),
    referenceSupport.searchProfile.strictIdentity
      ? '- exact identity fidelity is mandatory, do not switch to another character, product, variant or host device'
      : '',
    intent.referenceFraming === 'isolated_subject'
      ? '- keep the subject fully isolated with no host machine, no installation context and no extra prop'
      : '',
  ].filter(Boolean).join('\n')
}

function isAnimeLikePrompt(prompt: string) {
  return /\b(anime|manga|personnage d anime|anime character|waifu|shonen|shojo|isekai|mecha anime)\b/i.test(prompt.toLowerCase())
}

function selectReferenceStyle(intent: ThreeDIntent, prompt: string, referenceSupport: ThreeDReferenceSupport | null = null): FluxStyle {
  // ONLY use anime style when EXPLICITLY requested (anime, manga, waifu, shonen keywords)
  // Default to REALISTIC for all characters to avoid blobby/cartoon output
  if ((intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') && isAnimeLikePrompt(prompt)) {
    return 'anime'
  }
  // Non-anime characters/creatures → realistic for photorealistic quality
  if (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') {
    return 'realistic'
  }

  if (intent.referenceFraming === 'isolated_subject' && intent.systemClass === 'pc_cabling') {
    return referenceSupport?.searchProfile.strictIdentity ? 'realistic' : 'technical_render'
  }

  if (intent.referenceFraming === 'isolated_subject' && (intent.purpose === 'product' || intent.subjectKind === 'product')) {
    return referenceSupport?.searchProfile.strictIdentity ? 'realistic' : 'technical_render'
  }

  if (
    intent.requiresDimensionalPrecision
    || intent.purpose === 'mechanical_part'
    || intent.systemClass !== 'generic'
    || intent.representationGoal === 'kinematic_readability'
    || intent.representationGoal === 'routing_readability'
    || intent.subjectKind === 'electrical_system'
  ) {
    return 'technical_render'
  }

  return 'realistic'
}

function resolveReferenceWorkflow(
  intent: ThreeDIntent,
  hardware: HardwareProfile | null,
  hasSeed: boolean,
  prompt: string,
  referenceSupport: ThreeDReferenceSupport | null = null,
) {
  const style = selectReferenceStyle(intent, prompt, referenceSupport)
  const availableVram = Math.max(hardware?.vram_free_gb ?? 0, hardware?.vram_gb ?? 0)
  const hasHighHeadroom = availableVram >= 14
  const hasMidHeadroom = availableVram >= 8
  const technicalMode = style === 'technical_render'
  const animeMode = style === 'anime'
  const isCharacter = intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature'

  // Higher resolution and more steps for maximum precision — quality over speed
  const width = technicalMode
    ? hasHighHeadroom ? (hasSeed ? 1024 : 1024) : hasMidHeadroom ? 896 : 768
    : animeMode
      ? hasHighHeadroom ? 1024 : hasMidHeadroom ? 1024 : 896
      : isCharacter
        ? hasHighHeadroom ? 1024 : hasMidHeadroom ? 896 : 768
        : hasHighHeadroom ? 1024 : hasMidHeadroom ? 896 : 768
  const height = width
  const steps = technicalMode
    ? intent.requiresDimensionalPrecision ? (hasHighHeadroom ? 42 : 38) : (hasHighHeadroom ? 40 : 36)
    : animeMode
      ? hasHighHeadroom ? 40 : 36
      : isCharacter
        ? hasHighHeadroom ? 40 : 34
        : hasMidHeadroom ? 36 : 30

  return { style, width, height, steps }
}

function shouldRefineReferenceSeed(
  intent: ThreeDIntent,
  motionPreset: ThreeDMotionPreset | null,
  referenceSupport: ThreeDReferenceSupport | null,
  hasSeed: boolean,
  seedOrigin: ReferenceSeedOrigin,
  sourcePrompt: string,
) {
  if (!hasSeed) return true
  if (seedOrigin === 'user') {
    // User-uploaded reference is ALWAYS respected — never regenerate it
    // unless there's a specific motion preset that requires a different pose
    // The user's image is the ground truth for what they want
    return Boolean(motionPreset)
  }
  if (
    seedOrigin === 'external'
    && shouldForceBlackBackdrop(sourcePrompt, intent)
    && !(referenceSupport?.searchProfile.strictIdentity && (referenceSupport.externalReference?.score ?? 0) >= resolveReferenceMinimumScore(referenceSupport))
  ) {
    return true
  }
  if (
    seedOrigin === 'external'
    && !motionPreset
    && referenceSupport?.externalReference
    && (referenceSupport.searchProfile.strictIdentity || referenceSupport.externalReference.score >= 82)
  ) {
    return false
  }
  if (motionPreset) return true
  if (intent.requiresDimensionalPrecision || intent.systemClass !== 'generic') return true
  if (referenceSupport?.dimensionStrategy === 'auto_researched') return true
  if (!referenceSupport?.externalReference) return false
  return referenceSupport.referenceMode !== 'exact_reference'
}

function findLatestUserPrompt(messages: Array<{ role: 'user' | 'assistant'; content: string }>) {
  const content = [...messages].reverse().find((message) => message.role === 'user')?.content || ''
  return content
    .replace(/\n\nPreset action\/mouvement:[\s\S]*$/i, '')
    .replace(/\n\nPrecision:[\s\S]*$/i, '')
    .trim()
}

function resolveSelectedMotionPreset(intent: ThreeDIntent | null, presetId: string | null) {
  if (!intent || !presetId) return null
  return intent.motionPresets.find((preset) => preset.id === presetId) || null
}

function isCharacterLike(intent: ThreeDIntent | null) {
  if (!intent) return false
  return intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature'
}

function acceptanceKindForIntent(intent: ThreeDIntent): string {
  if (intent.subjectKind === 'vehicle') return 'vehicle'
  if (intent.subjectKind === 'architecture') return 'architecture'
  if (intent.subjectKind === 'character') return 'character'
  if (intent.subjectKind === 'creature') return 'creature'
  if (intent.subjectKind === 'body_part') return 'humanoid'
  if (intent.subjectKind === 'product' || intent.purpose === 'product') return 'product'
  if (intent.systemClass === 'pc_cabling' || intent.systemClass === 'electrical_harness') return 'product'
  if (intent.subjectKind === 'mechanical_part' || intent.subjectKind === 'assembly') return 'product'
  return 'generic'
}

function resolveViewerConfig(intent: ThreeDIntent | null, motionPreset: ThreeDMotionPreset | null): ViewerConfig {
  const lockedByPreset = Boolean(motionPreset?.lockViewer)

  if (!intent) {
    return {
      autoRotate: true,
      lockView: false,
      cameraPosition: [0, 1.6, 4.6],
      modeLabel: 'Rotation douce',
      modeDetail: 'Orbite manuelle active',
    }
  }

  if (lockedByPreset) {
    if (intent.systemClass === 'belt_drive' || intent.systemClass === 'gear_train' || intent.systemClass === 'cylinder_actuator' || intent.systemClass === 'hinge_joint' || intent.systemClass === 'linkage') {
      return {
        autoRotate: false,
        lockView: true,
        cameraPosition: [0, 0.85, 4.75],
        modeLabel: 'Etude mouvement',
        modeDetail: `Vue verrouillee pour ${motionPreset?.label.toLowerCase() || 'le mouvement'}`,
      }
    }

    if (intent.systemClass === 'cable_routing' || intent.systemClass === 'pc_cabling' || intent.systemClass === 'electrical_harness') {
      return {
        autoRotate: false,
        lockView: true,
        cameraPosition: [0.25, 1.15, 4.7],
        modeLabel: 'Inspection routage',
        modeDetail: `Vue verrouillee pour ${motionPreset?.label.toLowerCase() || 'le routage'}`,
      }
    }

    return {
      autoRotate: false,
      lockView: true,
      cameraPosition: [0, 1.2, 4.85],
      modeLabel: 'Pose verrouillee',
      modeDetail: `Vue stable pour ${motionPreset?.label.toLowerCase() || 'la pose'}`,
    }
  }

  if (isCharacterLike(intent)) {
    return {
      autoRotate: false,
      lockView: false,
      cameraPosition: [0, 1.2, 4.85],
      modeLabel: 'Personnage stable',
      modeDetail: 'Pas de rotation auto sur personnage',
    }
  }

  return {
    autoRotate: true,
    lockView: false,
    cameraPosition: [0, 1.6, 4.6],
    modeLabel: 'Rotation douce',
    modeDetail: 'Orbite manuelle active',
  }
}

// v80ag: pipeline-stage priority for mesh selection. The bug: when a session
// has been through bake → texture → split → anim, multiple GLBs co-exist and
// the OLDER one was getting picked first because we iterated newest-message
// first but took FIRST match per message. If that older GLB was overwritten
// or moved, modelUrl resolved to a stale path and the viewer fell back to the
// reference image — which is exactly what the user observed.
//
// Fix: collect every GLB/OBJ in the session, then rank by pipeline stage
// (split > anim > textured > rigged > reshaped > baked > raw_mesh). Reference
// image still uses the simple first-match-newest-first since there's only
// one canonical reference per run.
// 27/09 (retour Juan: « sur le modele ... y a que du blanc »): deux families
// de livrables doivent jamais gagner le viewer.
//  - `*_geometrie.glb` = le meme maillage SANS materiau (controle de forme).
//    Aucun `baseColorTexture` -> TOUT BLANC dans three.js. C'est voulu pour la
//    forme, mais c'est le MAUVAIS fichier a afficher comme « le modele ».
//  - `*_matte*.glb` / `*_mesh*.glb` = etapes intermediaires non colorees.
// On les classe donc SOUS le livrable colore, sans les supprimer du classement:
// un `modele_couleurs.glb` doit toujours passer devant.
const MESH_STAGE_PRIORITY: { match: RegExp; rank: number }[] = [
  { match: /scene_couleurs\.glb$/i,         rank: 120 },
  { match: /modele_couleurs\.glb$/i,       rank: 118 },
  { match: /mouvement_couleurs\.glb$/i,    rank: 116 },
  { match: /_split_k\d+\.glb$/i,        rank: 100 },
  { match: /_split\.glb$/i,             rank:  95 },
  { match: /_anim(_v\d+)?\.glb$/i,      rank:  90 },
  { match: /_textured\.glb$/i,          rank:  80 },
  { match: /_RIGGED.*\.glb$/i,          rank:  70 },
  { match: /_manifoldfixed\.glb$/i,     rank:  60 },
  { match: /_reshaped\.glb$/i,          rank:  55 },
  { match: /_baked\.glb$/i,             rank:  50 },
  { match: /_mesh\.glb$/i,              rank:  40 },
  // Sans materiau -> blanc au viewer. Utile a la forme, interdit comme
  // « le modele » quand une version coloree existe (rang superieur).
  { match: /_geometrie\.glb$/i,         rank:  15 },
  { match: /_matte.*\.glb$/i,           rank:  12 },
  { match: /\.(glb|gltf|obj)$/i,        rank:  10 },
]

export function _meshRank(filePath: string): number {
  for (const { match, rank } of MESH_STAGE_PRIORITY) {
    if (match.test(filePath)) return rank
  }
  return 0
}

export function findSessionAssets(session: ConversationSession) {
  let referencePath: string | null = null
  const meshCandidates: string[] = []
  for (let index = session.messages.length - 1; index >= 0; index -= 1) {
    for (const filePath of [...(session.messages[index].images || [])].reverse()) {
      const lower = filePath.toLowerCase()
      if (/\.(glb|gltf|obj)$/.test(lower)) meshCandidates.push(filePath)
      else if (!referencePath && /\.(png|jpg|jpeg|webp)$/.test(lower)) referencePath = filePath
    }
  }
  // Pick the highest-priority mesh; ties broken by message recency (we walked
  // newest-first so meshCandidates is already newest-first per stage).
  let meshPath: string | null = null
  let bestRank = -1
  for (const cand of meshCandidates) {
    const r = _meshRank(cand)
    if (r > bestRank) {
      bestRank = r
      meshPath = cand
    }
  }
  return { referencePath, meshPath }
}

async function stageExistingReference(sourcePath: string, comfyuiPath: string, targetName: string) {
  const inputDir = `${comfyuiPath}/input`
  await fsMkdir(inputDir)
  const bytes = await fsReadBinary(sourcePath)
  const targetPath = `${inputDir}/${targetName}`
  await fsWriteBinary(targetPath, bytes)
  return { stagedPath: targetPath, filename: targetName }
}

function referenceDenoise(intent: ThreeDIntent, hasSeed: boolean, referenceSupport: ThreeDReferenceSupport | null = null) {
  if (!hasSeed) return undefined
  const strictIdentity = referenceSupport?.searchProfile.strictIdentity
  if (strictIdentity && (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature')) return 0.08
  if (strictIdentity && intent.referenceFraming === 'isolated_subject') return 0.1
  if (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') return 0.16
  if (intent.requiresDimensionalPrecision || intent.systemClass !== 'generic') return 0.18
  if (intent.purpose === 'body_part') return 0.18
  return 0.22
}

/** Store original materials so we can restore them after highlight */
const originalMaterialMap = new WeakMap<Mesh, MeshStandardMaterial | MeshStandardMaterial[]>()

// v77zan: default colour palette per PbrProfileKind so Hunyuan3D-shape-only
// meshes (no texture paint, no baseColor map) get a sensible colour instead
// of flat white when shown in the viewer.
function defaultColorForPbrKind(kind: string): string {
  switch (kind) {
    case 'chrome': return '#c0c5cc'
    case 'brushed_metal': return '#9aa0a6'
    case 'painted_metal': return '#5b6470'
    case 'glass': return '#cfe5ec'
    case 'gem': return '#7ed4ff'
    case 'plastic_glossy': return '#1f2937'
    case 'plastic_matte': return '#4b5563'
    case 'rubber': return '#1f1f1f'
    case 'tire': return '#161616'
    case 'wood': return '#8b6a3f'
    case 'fabric': return '#5f6f8c'
    case 'leather': return '#5b3a24'
    case 'skin': return '#d8b094'
    case 'fur': return '#7a5b3a'
    case 'feathers': return '#3a3f5e'
    case 'scales': return '#3f6b3f'
    case 'ceramic': return '#e9e4d8'
    case 'stone': return '#7a7670'
    case 'electronics': return '#1c2030'
    case 'character_default': return '#cfa07b'
    case 'creature_default': return '#7d6342'
    case 'product_default': return '#9aa0a6'
    case 'vehicle_default': return '#3f516b'
    case 'mechanism_default': return '#7a7065'
    default: return '#9ca3af'
  }
}
const HIGHLIGHT_COLOR = new Color('#4dd5a4')
const INSPECTION_COLORS = ['#e4574f', '#3bb3a9', '#e2b84c', '#6f9ee8', '#9a7bd1', '#d97f45', '#57a773', '#c95f92']

function inspectionColorForPart(name: string, index: number): Color {
  let hash = index + 17
  for (let i = 0; i < name.length; i += 1) {
    hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0
  }
  const hex = INSPECTION_COLORS[Math.abs(hash) % INSPECTION_COLORS.length]
  return new Color(hex)
}

// v82nu iter3: info-panel payload emitted by the 3D click raycaster.
// Aggregated for "Select All" mode by summing across all meshes in the model.
export type PartInfo = {
  name: string                           // mesh name or 'all'
  isAll: boolean                         // true for the Select-All aggregate
  materialName: string | null
  materialKind: string | null            // BSDF type: 'MeshStandardMaterial' etc.
  baseColorHex: string | null
  emissiveHex: string | null
  emissiveIntensity: number | null
  metalness: number | null
  roughness: number | null
  vertexCount: number
  triangleCount: number
  dimensionsMeters: [number, number, number]
  centerWorld: [number, number, number]
  hasMorphTargets: boolean
  hasSkinning: boolean
  bonesAttached: number
}

function _hexFromColor(c: Color | null | undefined): string | null {
  if (!c) return null
  return '#' + c.getHexString()
}

function _extractPartInfo(mesh: Mesh, model: Object3D): PartInfo {
  const matRaw = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material
  const mat = matRaw as MeshStandardMaterial | MeshPhysicalMaterial | undefined
  const geom = mesh.geometry
  const indexCount = geom?.index ? geom.index.count : (geom?.attributes?.position?.count || 0)
  const triangleCount = geom?.index ? Math.floor(geom.index.count / 3) : Math.floor((geom?.attributes?.position?.count || 0) / 3)
  const vertexCount = geom?.attributes?.position?.count || 0

  const box = new Box3().setFromObject(mesh)
  const size = new Vector3(); box.getSize(size)
  const center = new Vector3(); box.getCenter(center)

  // bones / skinning
  const skinned = mesh as SkinnedMesh
  const isSkinned = !!(skinned && (skinned as { isSkinnedMesh?: boolean }).isSkinnedMesh)
  let boneCount = 0
  if (isSkinned && skinned.skeleton) {
    boneCount = skinned.skeleton.bones?.length || 0
  } else {
    // ambient bone count from the whole model
    model.traverse((o) => {
      if ((o as { isBone?: boolean }).isBone) boneCount += 1
    })
  }

  return {
    name: mesh.name || mesh.parent?.name || 'unnamed_part',
    isAll: false,
    materialName: mat?.name || null,
    materialKind: (mat as { type?: string })?.type || null,
    baseColorHex: _hexFromColor(mat?.color as Color | undefined),
    emissiveHex: _hexFromColor(mat?.emissive as Color | undefined),
    emissiveIntensity: typeof mat?.emissiveIntensity === 'number' ? mat.emissiveIntensity : null,
    metalness: typeof mat?.metalness === 'number' ? mat.metalness : null,
    roughness: typeof mat?.roughness === 'number' ? mat.roughness : null,
    vertexCount,
    triangleCount: triangleCount > 0 ? triangleCount : Math.floor(indexCount / 3),
    dimensionsMeters: [size.x, size.y, size.z],
    centerWorld: [center.x, center.y, center.z],
    hasMorphTargets: !!(geom?.morphAttributes && Object.keys(geom.morphAttributes).length > 0),
    hasSkinning: isSkinned,
    bonesAttached: boneCount,
  }
}

function _aggregatePartInfo(model: Object3D): PartInfo {
  let vertexCount = 0
  let triangleCount = 0
  let bonesAttached = 0
  let hasSkinning = false
  let hasMorphTargets = false
  const sampledMaterials: string[] = []

  model.traverse((obj) => {
    if ((obj as Mesh).isMesh) {
      const mesh = obj as Mesh
      const geom = mesh.geometry
      vertexCount += geom?.attributes?.position?.count || 0
      const tri = geom?.index ? Math.floor(geom.index.count / 3)
        : Math.floor((geom?.attributes?.position?.count || 0) / 3)
      triangleCount += tri
      if ((mesh as { isSkinnedMesh?: boolean }).isSkinnedMesh) hasSkinning = true
      if (geom?.morphAttributes && Object.keys(geom.morphAttributes).length > 0) hasMorphTargets = true
      const mat = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material
      const mname = (mat as { name?: string })?.name
      if (mname && !sampledMaterials.includes(mname)) sampledMaterials.push(mname)
    }
    if ((obj as { isBone?: boolean }).isBone) bonesAttached += 1
  })

  const box = new Box3().setFromObject(model)
  const size = new Vector3(); box.getSize(size)
  const center = new Vector3(); box.getCenter(center)

  return {
    name: 'all',
    isAll: true,
    materialName: sampledMaterials.length > 1
      ? `${sampledMaterials.length} materiaux (${sampledMaterials.slice(0, 3).join(', ')}${sampledMaterials.length > 3 ? '…' : ''})`
      : (sampledMaterials[0] || null),
    materialKind: null,
    baseColorHex: null,
    emissiveHex: null,
    emissiveIntensity: null,
    metalness: null,
    roughness: null,
    vertexCount,
    triangleCount,
    dimensionsMeters: [size.x, size.y, size.z],
    centerWorld: [center.x, center.y, center.z],
    hasMorphTargets,
    hasSkinning,
    bonesAttached,
  }
}

/**
 * iter6.A: aurora.oled-atlas.v1 reader.
 *
 * The Blender OLED flipbook baker (motion_intent_bpy_runner._bind_flipbook_atlas_to_material)
 * tags each animated material with a custom property named `aurora_oled_atlas`
 * carrying frame_count / frame_w / frame_h / frame_rate / loop. The Blender glTF
 * exporter writes these custom props into the material's `extras` (KHR-extras)
 * which Three.js GLTFLoader copies into `material.userData.gltfExtras` (and also
 * mirrors flat into `material.userData` for backward compatibility on some
 * versions). We support both shapes.
 *
 * The glTF spec doesn't animate the Mapping node's location.x — only the static
 * `KHR_texture_transform.offset` is exported. So at draw-time we ourselves
 * step the UV offset based on `clock.elapsedTime * frame_rate` mod frame_count,
 * always computing absolute (not accumulating) so re-running KHR-loaded transforms
 * are overwritten cleanly.
 */
type OledAtlasMeta = {
  schema?: string
  frame_count: number
  frame_w?: number
  frame_h?: number
  frame_rate: number
  direction?: 'h' | 'v'
  loop?: boolean
}

type OledBinding = {
  texture: Texture
  meta: OledAtlasMeta
}

function _readOledAtlasMeta(material: MeshStandardMaterial | MeshPhysicalMaterial): OledAtlasMeta | null {
  const ud = (material.userData ?? {}) as Record<string, unknown>
  const extras = (ud.gltfExtras ?? ud.extras ?? null) as Record<string, unknown> | null
  const candidate = (extras && (extras as Record<string, unknown>).aurora_oled_atlas)
    ?? (ud as Record<string, unknown>).aurora_oled_atlas
  if (!candidate || typeof candidate !== 'object') return null
  const c = candidate as Record<string, unknown>
  const schema = typeof c.schema === 'string' ? c.schema : ''
  if (schema && schema !== 'aurora.oled-atlas.v1') return null
  const fc = Number(c.frame_count)
  const fr = Number(c.frame_rate)
  if (!Number.isFinite(fc) || fc < 2) return null
  if (!Number.isFinite(fr) || fr <= 0) return null
  const dir = (c.direction === 'v' ? 'v' : 'h') as 'h' | 'v'
  return {
    schema: schema || 'aurora.oled-atlas.v1',
    frame_count: Math.max(2, Math.round(fc)),
    frame_w: Number.isFinite(Number(c.frame_w)) ? Number(c.frame_w) : undefined,
    frame_h: Number.isFinite(Number(c.frame_h)) ? Number(c.frame_h) : undefined,
    frame_rate: fr,
    direction: dir,
    loop: c.loop !== false,
  }
}

/**
 * iter9.D: aurora.led-emission.v1 reader.
 *
 * The Blender LED baker (motion_intent_bpy_runner.bake_led_emission) writes
 * FCurves on the BSDF Emission Color/Strength sockets — but the glTF spec
 * doesn't export shader-node-socket animation, so the GLB ships with a
 * statically-coloured material. To rescue this, the baker also tags the
 * material with an `aurora_led_emission` extras block carrying the pattern
 * spec; we re-drive material.emissive + material.emissiveIntensity at draw
 * time using the same math the baker uses (parity), so the user sees the
 * LED chase / rainbow / breathing exactly as authored.
 */
type LedEmissionMeta = {
  schema?: string
  pattern: 'static_color' | 'breathing' | 'pulse' | 'chase' | 'rainbow'
  speed_hz: number
  colors: string[]
  emission_strength: number
  base_color?: string
  loop?: boolean
  // iter16.A: optional phase_offset in [0, 1] = unit-period fraction. Default
  // 0 preserves iter15 behaviour. The baker (cable_bundle_system,
  // led_strip_system) writes i/strand_count or i/led_count so the chase wave
  // travels ALONG the cable/strip instead of pulsing globally.
  phase_offset?: number
}

type LedBinding = {
  material: MeshStandardMaterial | MeshPhysicalMaterial
  meta: LedEmissionMeta
}

function _hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.startsWith('#') ? hex.slice(1) : hex
  if (h.length !== 6) return { r: 1, g: 0, b: 0.2 }
  const r = parseInt(h.slice(0, 2), 16) / 255
  const g = parseInt(h.slice(2, 4), 16) / 255
  const b = parseInt(h.slice(4, 6), 16) / 255
  return { r, g, b }
}

function _readLedEmissionMeta(material: MeshStandardMaterial | MeshPhysicalMaterial): LedEmissionMeta | null {
  const ud = (material.userData ?? {}) as Record<string, unknown>
  const extras = (ud.gltfExtras ?? ud.extras ?? null) as Record<string, unknown> | null
  const candidate = (extras && (extras as Record<string, unknown>).aurora_led_emission)
    ?? (ud as Record<string, unknown>).aurora_led_emission
  if (!candidate || typeof candidate !== 'object') return null
  const c = candidate as Record<string, unknown>
  const schema = typeof c.schema === 'string' ? c.schema : ''
  if (schema && schema !== 'aurora.led-emission.v1') return null
  const patternRaw = typeof c.pattern === 'string' ? c.pattern : 'rainbow'
  const allowed = ['static_color', 'breathing', 'pulse', 'chase', 'rainbow'] as const
  type P = typeof allowed[number]
  const pattern: P = (allowed as readonly string[]).includes(patternRaw) ? patternRaw as P : 'rainbow'
  const speedHz = Number(c.speed_hz)
  const strength = Number(c.emission_strength)
  const colorsRaw = Array.isArray(c.colors) ? c.colors : []
  const colors = colorsRaw.filter((x): x is string => typeof x === 'string' && x.length > 0)
  if (!Number.isFinite(speedHz) || speedHz <= 0) return null
  if (!Number.isFinite(strength) || strength < 0) return null
  if (colors.length === 0) colors.push('#ff0033')
  // iter16.A: phase_offset is optional, default 0 (back-compat with iter15).
  // Clamp to [0, 1] so a stray 1.5 doesn't blow up the period math.
  const phaseRaw = Number(c.phase_offset)
  const phaseOffset = Number.isFinite(phaseRaw) ? Math.max(0, Math.min(1, phaseRaw)) : 0
  return {
    schema: schema || 'aurora.led-emission.v1',
    pattern,
    speed_hz: speedHz,
    colors,
    emission_strength: strength,
    base_color: typeof c.base_color === 'string' ? c.base_color : colors[0],
    loop: c.loop !== false,
    phase_offset: phaseOffset,
  }
}

function _collectLedBindings(root: Object3D): LedBinding[] {
  const bindings: LedBinding[] = []
  root.traverse((child) => {
    const mesh = child as Mesh
    if (!mesh.isMesh) return
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    mats.forEach((rawMat) => {
      const mat = rawMat as MeshStandardMaterial | MeshPhysicalMaterial | undefined
      if (!mat) return
      const meta = _readLedEmissionMeta(mat)
      if (!meta) return
      // Initialise emissive so the very first frame already has the LED look
      // (avoids one-frame flash of black).
      const first = _hexToRgb(meta.base_color || meta.colors[0] || '#ff0033')
      mat.emissive = new Color(first.r, first.g, first.b)
      mat.emissiveIntensity = meta.emission_strength
      mat.needsUpdate = true
      bindings.push({ material: mat, meta })
    })
  })
  return bindings
}

/**
 * Evaluate the LED pattern at virtual time `t` (seconds) and return the
 * emissive RGB + intensity. Mirrors motion_intent_bpy_runner.bake_led_emission.
 */
function _evalLedPattern(meta: LedEmissionMeta, t: number): { r: number; g: number; b: number; intensity: number } {
  const period = 1 / meta.speed_hz
  // iter16.C: shift t by (phase_offset * period) so each material starts at
  // a different moment of the pattern. With phase_offset = i/N for N strands,
  // the chase wave propagates ALONG the cable instead of pulsing globally.
  // Default phase_offset = 0 (back-compat with iter15).
  const phaseOffset = meta.phase_offset ?? 0
  const tEffective = t + phaseOffset * period
  const phaseT = (tEffective / period) % 1
  const colors = meta.colors.length > 0 ? meta.colors : ['#ff0033']
  if (meta.pattern === 'static_color') {
    const c = _hexToRgb(colors[0])
    return { ...c, intensity: meta.emission_strength }
  }
  if (meta.pattern === 'breathing') {
    const phase = (Math.sin(2 * Math.PI * phaseT) + 1) * 0.5
    const c = _hexToRgb(colors[0])
    return { ...c, intensity: meta.emission_strength * phase }
  }
  if (meta.pattern === 'pulse') {
    const phase = phaseT < 0.5 ? 1 : 0
    const c = _hexToRgb(colors[0])
    return { ...c, intensity: meta.emission_strength * phase }
  }
  if (meta.pattern === 'chase') {
    const idx = Math.floor(phaseT * colors.length) % colors.length
    const c = _hexToRgb(colors[idx])
    return { ...c, intensity: meta.emission_strength }
  }
  // rainbow
  const hue = (tEffective * meta.speed_hz * 0.5) % 1
  const iH = Math.floor(hue * 6)
  const fH = hue * 6 - iH
  const q = 1 - fH
  let r = 0, g = 0, b = 0
  switch (iH % 6) {
    case 0: r = 1;  g = fH; b = 0; break
    case 1: r = q;  g = 1;  b = 0; break
    case 2: r = 0;  g = 1;  b = fH; break
    case 3: r = 0;  g = q;  b = 1; break
    case 4: r = fH; g = 0;  b = 1; break
    default: r = 1; g = 0;  b = q
  }
  return { r, g, b, intensity: meta.emission_strength }
}

function _collectOledBindings(root: Object3D): OledBinding[] {
  const bindings: OledBinding[] = []
  root.traverse((child) => {
    const mesh = child as Mesh
    if (!mesh.isMesh) return
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    mats.forEach((rawMat) => {
      const mat = rawMat as MeshStandardMaterial | MeshPhysicalMaterial | undefined
      if (!mat) return
      const meta = _readOledAtlasMeta(mat)
      if (!meta) return
      const tex = (mat as MeshStandardMaterial).map ?? null
      if (!tex) return
      // Configure texture once: nearest filter (no inter-frame bleed) + repeat wrap.
      tex.magFilter = NearestFilter
      tex.minFilter = NearestFilter
      tex.wrapS = RepeatWrapping
      tex.wrapT = RepeatWrapping
      tex.generateMipmaps = false
      // Set repeat to one-frame slice. Direction h=horizontal strip, v=vertical.
      if (meta.direction === 'v') {
        tex.repeat.set(1, 1 / meta.frame_count)
      } else {
        tex.repeat.set(1 / meta.frame_count, 1)
      }
      // Reset offset to avoid accumulating any pre-applied KHR_texture_transform.
      tex.offset.set(0, 0)
      tex.needsUpdate = true
      bindings.push({ texture: tex, meta })
    })
  })
  return bindings
}

/**
 * iter24.B: aurora.belt-scroll.v1 reader.
 *
 * Procedural belt-pulley meshes ship a thin marker-stripe texture on the belt
 * so the user can SEE the belt sliding along its path. The Blender baker tags
 * the belt material with `aurora_belt_scroll` extras (schema
 * aurora.belt-scroll.v1, see blender_bridge.pulley_belt_system). Three.js
 * doesn't animate the Mapping node's location.x out of the box, so at draw
 * time we step `material.map.offset` by `speed_uv_per_sec * delta` along U
 * (or V if direction='v') — same idea as the OLED atlas reader.
 */
type BeltScrollMeta = {
  schema?: string
  speed_uv_per_sec: number
  direction?: 'h' | 'v'
  loop?: boolean
}

type BeltScrollBinding = {
  texture: Texture
  meta: BeltScrollMeta
}

function _readBeltScrollMeta(material: MeshStandardMaterial | MeshPhysicalMaterial): BeltScrollMeta | null {
  const ud = (material.userData ?? {}) as Record<string, unknown>
  const extras = (ud.gltfExtras ?? ud.extras ?? null) as Record<string, unknown> | null
  const candidate = (extras && (extras as Record<string, unknown>).aurora_belt_scroll)
    ?? (ud as Record<string, unknown>).aurora_belt_scroll
  if (!candidate || typeof candidate !== 'object') return null
  const c = candidate as Record<string, unknown>
  const schema = typeof c.schema === 'string' ? c.schema : ''
  if (schema && schema !== 'aurora.belt-scroll.v1') return null
  const speed = Number(c.speed_uv_per_sec)
  if (!Number.isFinite(speed)) return null
  const dir = (c.direction === 'v' ? 'v' : 'h') as 'h' | 'v'
  return {
    schema: schema || 'aurora.belt-scroll.v1',
    speed_uv_per_sec: speed,
    direction: dir,
    loop: c.loop !== false,
  }
}

function _collectBeltBindings(root: Object3D): BeltScrollBinding[] {
  const bindings: BeltScrollBinding[] = []
  root.traverse((child) => {
    const mesh = child as Mesh
    if (!mesh.isMesh) return
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    mats.forEach((rawMat) => {
      const mat = rawMat as MeshStandardMaterial | MeshPhysicalMaterial | undefined
      if (!mat) return
      const meta = _readBeltScrollMeta(mat)
      if (!meta) return
      const tex = (mat as MeshStandardMaterial).map ?? null
      if (!tex) return
      // Belt marker stripes need crisp edges: nearest filter + repeat wrap.
      tex.magFilter = NearestFilter
      tex.minFilter = NearestFilter
      tex.wrapS = RepeatWrapping
      tex.wrapT = RepeatWrapping
      tex.generateMipmaps = false
      // Belt material ships with a stripe texture meant to repeat ~8x along
      // the belt loop. Don't override repeat: respect whatever the baker set
      // (default 1,1; if a custom belt repeat was authored we leave it alone).
      tex.offset.set(0, 0)
      tex.needsUpdate = true
      bindings.push({ texture: tex, meta })
    })
  })
  return bindings
}

/**
 * aurora.flow.v1 reader — continuous fluid flow (water / lava / any fluid).
 *
 * Fluid meshes (fountain water, cascade, lava) ship their material tagged with
 * `aurora_flow` extras written by the fluid stage / sculpted_water_animator:
 * { vitesse:number, direction:[u,v], schema:'aurora.flow.v1' }. Historically
 * this spec was embedded in the GLB but NO viewer consumer existed, so the
 * water only showed its baked morph ripples (looked almost static — the flow
 * never played). The mesh UVs are an xatlas atlas (islands, no repeat) so a
 * naive UV scroll (like the belt) drifts out of its island and smears the
 * neighbouring islands. Instead we inject a two-phase flow-map blend (Valve
 * water technique) via onBeforeCompile: two base-colour samples offset in the
 * flow direction by a BOUNDED, phase-reset displacement, cross-faded so the
 * surface streams continuously without ever drifting far from origin — no atlas
 * streaking. Runs ON TOP of the baked morph ripples (geometry) so the combined
 * read is water that genuinely "ruisselle". Injection is non-fatal: if the
 * material has no base map the binding is skipped and the mesh renders normally.
 */
type FlowMeta = { schema: string; speed: number; dir: [number, number] }

type FlowUniforms = {
  uAuroraFlowTime: { value: number }
  uAuroraFlowDir: { value: [number, number] }
  uAuroraFlowSpeed: { value: number }
  uAuroraFlowAmp: { value: number }
}

type FlowBinding = { uniforms: FlowUniforms }

function _readFlowMeta(material: MeshStandardMaterial | MeshPhysicalMaterial): FlowMeta | null {
  const ud = (material.userData ?? {}) as Record<string, unknown>
  const extras = (ud.gltfExtras ?? ud.extras ?? null) as Record<string, unknown> | null
  const candidate = (extras && (extras as Record<string, unknown>).aurora_flow)
    ?? (ud as Record<string, unknown>).aurora_flow
  if (!candidate || typeof candidate !== 'object') return null
  const c = candidate as Record<string, unknown>
  const schema = typeof c.schema === 'string' ? c.schema : ''
  if (schema && schema !== 'aurora.flow.v1') return null
  const speed = Number(c.vitesse)
  const dirRaw = Array.isArray(c.direction) ? c.direction : null
  if (!Number.isFinite(speed) || !dirRaw || dirRaw.length < 2) return null
  const dx = Number(dirRaw[0])
  const dy = Number(dirRaw[1])
  if (!Number.isFinite(dx) || !Number.isFinite(dy)) return null
  const len = Math.hypot(dx, dy) || 1
  return { schema: schema || 'aurora.flow.v1', speed, dir: [dx / len, dy / len] }
}

function _collectFlowBindings(root: Object3D): FlowBinding[] {
  const bindings: FlowBinding[] = []
  root.traverse((child) => {
    const mesh = child as Mesh
    if (!mesh.isMesh) return
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    mats.forEach((rawMat) => {
      const mat = rawMat as MeshStandardMaterial | MeshPhysicalMaterial | undefined
      if (!mat) return
      const meta = _readFlowMeta(mat)
      if (!meta) return
      // Need a base-colour map to flow; without it there is nothing to displace.
      if (!(mat as MeshStandardMaterial).map) return
      const uniforms: FlowUniforms = {
        uAuroraFlowTime: { value: 0 },
        uAuroraFlowDir: { value: [meta.dir[0], meta.dir[1]] },
        // `vitesse` is authored in concept units; scale to a gentle UV cycle rate.
        uAuroraFlowSpeed: { value: Math.max(0.02, Math.min(1.5, meta.speed * 0.2)) },
        // Bounded displacement: max |offset| = 0.5*amp UV, small enough to stay
        // inside the atlas island so neighbouring islands never smear in.
        uAuroraFlowAmp: { value: 0.12 },
      }
      const prev = mat.onBeforeCompile
      mat.onBeforeCompile = (shader, renderer) => {
        try { if (typeof prev === 'function') prev(shader, renderer) } catch { /* keep going */ }
        shader.uniforms.uAuroraFlowTime = uniforms.uAuroraFlowTime
        shader.uniforms.uAuroraFlowDir = uniforms.uAuroraFlowDir
        shader.uniforms.uAuroraFlowSpeed = uniforms.uAuroraFlowSpeed
        shader.uniforms.uAuroraFlowAmp = uniforms.uAuroraFlowAmp
        shader.fragmentShader = shader.fragmentShader
          .replace(
            '#include <common>',
            'uniform float uAuroraFlowTime;\nuniform vec2 uAuroraFlowDir;\nuniform float uAuroraFlowSpeed;\nuniform float uAuroraFlowAmp;\n#include <common>',
          )
          .replace(
            '#include <map_fragment>',
            [
              '#ifdef USE_MAP',
              '  vec4 _afBase = texture2D(map, vMapUv);',
              // Fluid mask derived from the texture itself (no hardcoded hue): a fluid
              // (water/lava) is chromatic/saturated; the stone or metal painted in the
              // SAME atlas is desaturated grey/tan. HSV saturation separates them, so
              // only the fluid flows and the stone stays perfectly still.
              '  float _afMx = max(max(_afBase.r, _afBase.g), _afBase.b);',
              '  float _afMn = min(min(_afBase.r, _afBase.g), _afBase.b);',
              '  float _afSat = _afMx > 0.001 ? (_afMx - _afMn) / _afMx : 0.0;',
              '  float _afMask = smoothstep(0.28, 0.52, _afSat);',
              // Two-phase flow-map: two samples offset along the flow direction by a
              // BOUNDED, phase-reset displacement (scaled by the mask so stone offset=0),
              // cross-faded so the surface streams continuously without atlas streaking.
              '  float _afCycle = fract(uAuroraFlowTime * uAuroraFlowSpeed);',
              '  float _afOff0 = _afCycle - 0.5;',
              '  float _afOff1 = fract(_afCycle + 0.5) - 0.5;',
              '  vec2 _afUv0 = vMapUv + uAuroraFlowDir * _afOff0 * uAuroraFlowAmp * _afMask;',
              '  vec2 _afUv1 = vMapUv + uAuroraFlowDir * _afOff1 * uAuroraFlowAmp * _afMask;',
              '  float _afLerp = abs(_afCycle * 2.0 - 1.0);',
              '  vec4 _afFlowed = mix(texture2D(map, _afUv0), texture2D(map, _afUv1), _afLerp);',
              '  vec4 sampledDiffuseColor = mix(_afBase, _afFlowed, _afMask);',
              '  diffuseColor *= sampledDiffuseColor;',
              '#endif',
            ].join('\n'),
          )
      }
      // Distinct cache key so this program is never shared with a non-flow material.
      mat.customProgramCacheKey = () => 'aurora_flow_v1'
      mat.needsUpdate = true
      bindings.push({ uniforms })
    })
  })
  return bindings
}

function InteractiveModel({
  url,
  autoRotate,
  onPartSelect,
  onPartInfo,
  selectAllToken,
  onAnimationsLoaded,
  onModelLoaded,
  playAnimations = true,
  animationSpeed = 1,
  manualTime = null,
  wireframe = false,
  materialMode = 'authored',
  activeClipIndex = -1,
  pbrProfile = null,
  onDurationChange,
  onTimeChange,
}: {
  url: string
  autoRotate: boolean
  onPartSelect?: (name: string | null) => void
  onPartInfo?: (info: PartInfo | null) => void
  selectAllToken?: number
  onAnimationsLoaded?: (clips: AnimationClip[]) => void
  onModelLoaded?: (model: Object3D) => void
  playAnimations?: boolean
  animationSpeed?: number
  manualTime?: number | null
  wireframe?: boolean
  materialMode?: ViewerMaterialMode
  activeClipIndex?: number
  pbrProfile?: PbrProfile | null
  onDurationChange?: (duration: number) => void
  onTimeChange?: (time: number) => void
}) {
  const groupRef = useRef<Group>(null)
  const [model, setModel] = useState<Object3D | null>(null)
  const [clips, setClips] = useState<AnimationClip[]>([])
  const mixerRef = useRef<AnimationMixer | null>(null)
  const highlightedRef = useRef<Mesh | null>(null)
  const actionsRef = useRef<ReturnType<AnimationMixer['clipAction']>[]>([])
  // iter6.A: OLED flipbook atlas bindings detected from material.userData.gltfExtras.
  // Populated on model load, animated by useFrame at draw-time.
  const oledBindingsRef = useRef<OledBinding[]>([])
  // iter7.C: virtual OLED clock — accumulates elapsed time only while
  // playAnimations=true. On pause the value freezes; on resume we keep
  // adding deltas. This gives smooth pause/resume (no snap to frame N when
  // wall-clock has advanced N seconds during the pause).
  const oledVirtualTimeRef = useRef<number>(0)
  // iter9.D: aurora.led-emission.v1 bindings + virtual clock (separate from
  // OLED so an unrelated speed_hz doesn't drag the OLED frame stepping).
  const ledBindingsRef = useRef<LedBinding[]>([])
  const ledVirtualTimeRef = useRef<number>(0)
  // iter24.B: aurora.belt-scroll.v1 bindings + virtual clock. Animates the
  // belt material's UV offset along U so the belt visibly slides along its
  // path while the pulleys rotate at the kinematic ratio. Same lifecycle as
  // OLED/LED bindings (collected on model load, reset on unmount).
  const beltBindingsRef = useRef<BeltScrollBinding[]>([])
  const beltVirtualTimeRef = useRef<number>(0)
  // aurora.flow.v1 bindings + virtual clock. Injects a two-phase flow-map blend
  // on the fluid material so water/lava visibly streams along its flow
  // direction, on top of the baked morph ripples. Same lifecycle as the others.
  const flowBindingsRef = useRef<FlowBinding[]>([])
  const flowVirtualTimeRef = useRef<number>(0)

  useEffect(() => {
    if (!model) return
    let meshIndex = 0
    let authoredPbr = false
    model.traverse((child) => {
      const m = (child as Mesh).material as MeshPhysicalMaterial | MeshPhysicalMaterial[] | undefined
      const list = Array.isArray(m) ? m : m ? [m] : []
      list.forEach((mm) => {
        const phys = mm as MeshPhysicalMaterial
        if ((phys.transmission ?? 0) > 0 || (phys.clearcoat ?? 0) > 0 || (phys.sheen ?? 0) > 0 || (phys.emissiveIntensity ?? 1) > 1.5) authoredPbr = true
      })
    })
    model.traverse((child) => {
      const mesh = child as Mesh
      if (!mesh.isMesh) return
      const partColor = inspectionColorForPart(mesh.name || mesh.parent?.name || 'part', meshIndex)
      meshIndex += 1
      const rawMats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
      // v77zan: Hunyuan3D shape-only meshes (texture paint disabled) ship
      // with NO material at all → Three.js falls back to a flat white
      // MeshBasicMaterial which makes the mesh look like a blank cube.
      // Synthesize a MeshStandardMaterial with the inferred PbrProfile's
      // baseColor when the mesh arrives material-less, so the user sees
      // a coloured silhouette instead of "white blob".
      const needsSynthetic = !mesh.material || (Array.isArray(mesh.material) && mesh.material.length === 0)
        || rawMats.every((m) => !m)
      const mats = needsSynthetic
        ? [(() => {
            const base = materialMode === 'diagnostic'
              ? '#' + partColor.getHexString()
              : pbrProfile ? defaultColorForPbrKind(pbrProfile.kind) : '#9ca3af'
            const synth = new MeshStandardMaterial({
              color: new Color(base),
              metalness: pbrProfile?.metalness ?? 0.1,
              roughness: pbrProfile?.roughness ?? 0.55,
              envMapIntensity: pbrProfile?.envMapIntensity ?? 1.2,
            })
            mesh.material = synth
            return synth
          })()]
        : rawMats
      const replacements: Array<MeshStandardMaterial | MeshPhysicalMaterial> = []
      mats.forEach((mat) => {
        if (mat && 'wireframe' in mat) {
          ;(mat as MeshStandardMaterial).wireframe = wireframe
        }
        if (materialMode === 'diagnostic' && mat) {
          const diagnostic = mat as MeshStandardMaterial
          diagnostic.color = partColor.clone()
          diagnostic.roughness = Math.min(diagnostic.roughness ?? 0.72, 0.72)
          diagnostic.metalness = Math.max(diagnostic.metalness ?? 0, 0.02)
          diagnostic.envMapIntensity = Math.max(diagnostic.envMapIntensity ?? 1, 1.45)
          diagnostic.needsUpdate = true
        }
        // v77zf: Meshy-grade PBR — Hunyuan3D-Paint exports baseColor only and
        // the GLB ships with roughness=1 metalness=0 (flat plastic). When a
        // PbrProfile was inferred from the prompt + subject, upgrade any
        // material that still has the post-paint flat default to a real PBR
        // material with chrome/glass/skin/fabric/etc characteristics. The
        // baseColorMap is preserved — we only override the surface response.
        if (materialMode === 'diagnostic' || !pbrProfile || !mat || authoredPbr) {
          if (mat && 'envMapIntensity' in mat) {
            ;(mat as MeshStandardMaterial).envMapIntensity = 1.35
          }
          return
        }
        const std = mat as MeshStandardMaterial
        const isFlatDefault =
          (std.metalness ?? 0) <= 0.05
          && (std.roughness ?? 1) >= 0.92
          && !(std as MeshStandardMaterial).metalnessMap
          && !(std as MeshStandardMaterial).roughnessMap
        const wantsPhysical = (
          pbrProfile.clearcoat !== undefined
          || pbrProfile.sheen !== undefined
          || pbrProfile.transmission !== undefined
          || pbrProfile.iridescence !== undefined
        )
        if (!isFlatDefault && !wantsPhysical) {
          std.envMapIntensity = pbrProfile.envMapIntensity
          return
        }
        if (wantsPhysical) {
          // Build a MeshPhysicalMaterial that mirrors the original baseColor /
          // map / normalMap and adds clearcoat / sheen / transmission as
          // dictated by the inferred profile. Replacing the array slot keeps
          // any future material swap logic working.
          const physical = new MeshPhysicalMaterial({
            color: std.color ?? new Color('#ffffff'),
            map: std.map ?? null,
            normalMap: std.normalMap ?? null,
            metalness: pbrProfile.metalness,
            roughness: pbrProfile.roughness,
            envMapIntensity: pbrProfile.envMapIntensity,
            transparent: std.transparent,
            opacity: std.opacity ?? 1,
          })
          if (pbrProfile.clearcoat !== undefined) physical.clearcoat = pbrProfile.clearcoat
          if (pbrProfile.clearcoatRoughness !== undefined) physical.clearcoatRoughness = pbrProfile.clearcoatRoughness
          if (pbrProfile.sheen !== undefined) physical.sheen = pbrProfile.sheen
          if (pbrProfile.iridescence !== undefined) physical.iridescence = pbrProfile.iridescence
          if (pbrProfile.transmission !== undefined) physical.transmission = pbrProfile.transmission
          if (pbrProfile.ior !== undefined) physical.ior = pbrProfile.ior
          if (pbrProfile.emissiveBoost !== undefined) {
            physical.emissive = (std.color ?? new Color('#ffffff')).clone()
            physical.emissiveIntensity = pbrProfile.emissiveBoost
          }
          physical.wireframe = wireframe
          physical.needsUpdate = true
          replacements.push(physical)
        } else {
          std.metalness = pbrProfile.metalness
          std.roughness = pbrProfile.roughness
          std.envMapIntensity = pbrProfile.envMapIntensity
          std.needsUpdate = true
          replacements.push(std)
        }
      })
      if (pbrProfile && replacements.length > 0) {
        mesh.material = replacements.length === 1 ? replacements[0] : replacements
      }
    })
  }, [model, wireframe, pbrProfile, materialMode])

  useEffect(() => {
    let cancelled = false
    let loadedObject: Object3D | null = null
    ;(async () => {
      const lowerUrl = url.toLowerCase()
      if (lowerUrl.endsWith('.glb') || lowerUrl.endsWith('.gltf')) {
        const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js')
        // iter11.C: KHR_draco_mesh_compression support. Bake exports now ship
        // with Draco compression (motion_intent_bpy_runner + rigify_autorig +
        // blender_bridge). Without DRACOLoader, a Draco-compressed GLB throws
        // "THREE.GLTFLoader: No DRACOLoader instance provided".
        // iter18.B: WASM decoder is now served from /draco/ (vite public dir)
        // so AuroraIA stays self-contained and works fully offline. Files copied
        // from node_modules/three/examples/jsm/libs/draco/ into application/public/draco/.
        const { DRACOLoader } = await import('three/examples/jsm/loaders/DRACOLoader.js')
        const dracoLoader = new DRACOLoader()
        dracoLoader.setDecoderPath('/draco/')
        const _gltfLoader = new GLTFLoader()
        _gltfLoader.setDRACOLoader(dracoLoader)
        _gltfLoader.load(url, (loadedModel) => {
          if (cancelled) return
          loadedObject = loadedModel.scene
          // iter6.A: scan all materials for aurora.oled-atlas.v1 metadata and
          // configure textures for client-side UV stepping. Done BEFORE setModel
          // so the bindings are ready by the first useFrame tick.
          oledBindingsRef.current = _collectOledBindings(loadedModel.scene)
          // iter7.C: reset OLED virtual clock on new model load (so a previously
          // accumulated time from a different model doesn't carry over).
          oledVirtualTimeRef.current = 0
          // iter9.D: collect aurora.led-emission.v1 bindings and reset clock.
          ledBindingsRef.current = _collectLedBindings(loadedModel.scene)
          ledVirtualTimeRef.current = 0
          // iter24.B: collect aurora.belt-scroll.v1 bindings (procedural belt loops).
          beltBindingsRef.current = _collectBeltBindings(loadedModel.scene)
          beltVirtualTimeRef.current = 0
          // aurora.flow.v1: collect fluid-flow bindings (fountain/cascade/lava).
          flowBindingsRef.current = _collectFlowBindings(loadedModel.scene)
          flowVirtualTimeRef.current = 0
          setModel(loadedModel.scene)
          onModelLoaded?.(loadedModel.scene)
          const loadedClips = (loadedModel.animations ?? []) as AnimationClip[]
          setClips(loadedClips)
          onAnimationsLoaded?.(loadedClips)
        }, undefined, () => { if (!cancelled) { setModel(null); setClips([]); onAnimationsLoaded?.([]); oledBindingsRef.current = []; ledBindingsRef.current = []; beltBindingsRef.current = []; flowBindingsRef.current = [] } })
        return
      }
      const { OBJLoader } = await import('three/examples/jsm/loaders/OBJLoader.js')
      new OBJLoader().load(url, (loadedModel) => {
        if (cancelled) return
        loadedModel.traverse((child) => {
          const meshChild = child as Mesh
          if (meshChild.isMesh) meshChild.material = new MeshStandardMaterial({ color: COLORS[0], roughness: 0.58, metalness: 0.12 })
        })
        loadedObject = loadedModel
        setModel(loadedModel)
        onModelLoaded?.(loadedModel)
        setClips([])
        onAnimationsLoaded?.([])
      }, undefined, () => { if (!cancelled) { setModel(null); setClips([]); onAnimationsLoaded?.([]) } })
    })().catch(() => { if (!cancelled) setModel(null) })
    return () => {
      cancelled = true
      mixerRef.current?.stopAllAction()
      mixerRef.current = null
      oledBindingsRef.current = []
      // iter7.C: reset virtual clock on unmount/url-change
      oledVirtualTimeRef.current = 0
      // iter9.D: cleanup LED bindings on unmount/url-change
      ledBindingsRef.current = []
      ledVirtualTimeRef.current = 0
      // iter24.B: cleanup belt-scroll bindings on unmount/url-change
      beltBindingsRef.current = []
      beltVirtualTimeRef.current = 0
      // aurora.flow.v1: cleanup fluid-flow bindings on unmount/url-change
      flowBindingsRef.current = []
      flowVirtualTimeRef.current = 0
      disposeTree(loadedObject)
    }
  }, [url, onAnimationsLoaded])

  useEffect(() => {
    mixerRef.current?.stopAllAction()
    actionsRef.current = []
    if (!model || clips.length === 0) {
      mixerRef.current = null
      onDurationChange?.(0)
      return
    }
    const mixer = new AnimationMixer(model)
    mixerRef.current = mixer
    const selected = activeClipIndex >= 0 && activeClipIndex < clips.length ? [clips[activeClipIndex]] : clips
    const actions = selected.map((clip) => {
      const action = mixer.clipAction(clip)
      action.setLoop(LoopRepeat, Infinity)
      if (!playAnimations) action.paused = true
      action.play()
      return action
    })
    actionsRef.current = actions
    const maxDuration = selected.reduce((max, clip) => Math.max(max, clip.duration), 0)
    onDurationChange?.(maxDuration)
    return () => {
      mixer.stopAllAction()
    }
  }, [model, clips, playAnimations, activeClipIndex, onDurationChange])

  useEffect(() => {
    if (!mixerRef.current) return
    mixerRef.current.timeScale = playAnimations ? animationSpeed : 0
  }, [playAnimations, animationSpeed])

  useEffect(() => {
    if (manualTime == null || !mixerRef.current) return
    mixerRef.current.setTime(manualTime)
  }, [manualTime])

  useFrame((state, delta) => {
    if (mixerRef.current && playAnimations && manualTime == null) {
      mixerRef.current.update(delta)
      onTimeChange?.(actionsRef.current[0]?.time ?? 0)
    }
    if (autoRotate && groupRef.current) groupRef.current.rotation.y += delta * 0.2
    // iter6.A: animate OLED flipbook atlases by stepping UV offset.
    // iter7.C: pause/resume smoothness — instead of using clock.elapsedTime
    // directly (which keeps advancing during the pause and snaps the frame
    // forward on resume), accumulate `delta` only while playAnimations=true.
    // manualTime scrub still wins (used by the timeline scrubber).
    if (oledBindingsRef.current.length > 0) {
      let t: number
      if (manualTime != null) {
        t = manualTime
      } else if (playAnimations) {
        oledVirtualTimeRef.current += delta * (animationSpeed ?? 1)
        t = oledVirtualTimeRef.current
      } else {
        // Paused — re-emit current offset (no advance). Re-emitting is cheap and
        // makes sure any stray KHR_texture_transform offset stays overwritten.
        t = oledVirtualTimeRef.current
      }
      for (const binding of oledBindingsRef.current) {
        const { texture, meta } = binding
        const fc = meta.frame_count
        const step = Math.floor(t * meta.frame_rate) % fc
        const u = step / fc
        // Set absolute (not accumulating) — overwrites any stale KHR offset.
        if (meta.direction === 'v') {
          texture.offset.set(0, u)
        } else {
          texture.offset.set(u, 0)
        }
      }
    }
    // iter9.D: drive aurora.led-emission.v1 bindings — write absolute
    // material.emissive + material.emissiveIntensity each frame so the user
    // sees the LED chase / rainbow / breathing as authored by the baker.
    if (ledBindingsRef.current.length > 0) {
      let tLed: number
      if (manualTime != null) {
        tLed = manualTime
      } else if (playAnimations) {
        ledVirtualTimeRef.current += delta * (animationSpeed ?? 1)
        tLed = ledVirtualTimeRef.current
      } else {
        tLed = ledVirtualTimeRef.current
      }
      for (const binding of ledBindingsRef.current) {
        const { material, meta } = binding
        const e = _evalLedPattern(meta, tLed)
        material.emissive.setRGB(e.r, e.g, e.b)
        material.emissiveIntensity = e.intensity
      }
    }
    // iter24.B: drive aurora.belt-scroll.v1 bindings — scroll the belt
    // material's UV offset along U (or V) at speed_uv_per_sec. Same
    // pause/scrub semantics as OLED/LED: virtual clock accumulates only when
    // playAnimations=true; manualTime overrides for timeline scrubbing.
    if (beltBindingsRef.current.length > 0) {
      let tBelt: number
      if (manualTime != null) {
        tBelt = manualTime
      } else if (playAnimations) {
        beltVirtualTimeRef.current += delta * (animationSpeed ?? 1)
        tBelt = beltVirtualTimeRef.current
      } else {
        tBelt = beltVirtualTimeRef.current
      }
      for (const binding of beltBindingsRef.current) {
        const { texture, meta } = binding
        const u = (tBelt * meta.speed_uv_per_sec)
        // Wrap to [0,1) so float drift never explodes after a long session.
        const wrapped = ((u % 1) + 1) % 1
        if (meta.direction === 'v') {
          texture.offset.set(0, wrapped)
        } else {
          texture.offset.set(wrapped, 0)
        }
      }
    }
    // aurora.flow.v1: advance the fluid-flow virtual clock and push it to each
    // material's shader uniform. Same pause/scrub semantics as OLED/LED/belt.
    if (flowBindingsRef.current.length > 0) {
      let tFlow: number
      if (manualTime != null) {
        tFlow = manualTime
      } else if (playAnimations) {
        flowVirtualTimeRef.current += delta * (animationSpeed ?? 1)
        tFlow = flowVirtualTimeRef.current
      } else {
        tFlow = flowVirtualTimeRef.current
      }
      for (const binding of flowBindingsRef.current) {
        binding.uniforms.uAuroraFlowTime.value = tFlow
      }
    }
  })

  const handleClick = useCallback((event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation()
    // Restore previous highlight
    if (highlightedRef.current) {
      const orig = originalMaterialMap.get(highlightedRef.current)
      if (orig) highlightedRef.current.material = orig as MeshStandardMaterial
      highlightedRef.current = null
    }
    // Highlight clicked mesh
    const hitMesh = event.object as Mesh
    if (hitMesh?.isMesh) {
      const currentMat = hitMesh.material
      if (!originalMaterialMap.has(hitMesh)) {
        originalMaterialMap.set(hitMesh, (Array.isArray(currentMat) ? currentMat.map((m) => (m as MeshStandardMaterial).clone()) : (currentMat as MeshStandardMaterial).clone()) as MeshStandardMaterial)
      }
      const highlightMat = (currentMat as MeshStandardMaterial).clone?.()
      if (highlightMat) {
        highlightMat.emissive = HIGHLIGHT_COLOR
        highlightMat.emissiveIntensity = 0.35
        hitMesh.material = highlightMat
      }
      highlightedRef.current = hitMesh
      const partName = hitMesh.name || hitMesh.parent?.name || 'unnamed_part'
      onPartSelect?.(partName)
      if (onPartInfo && model) {
        onPartInfo(_extractPartInfo(hitMesh, model))
      }
    }
  }, [onPartSelect, onPartInfo, model])

  const handlePointerMissed = useCallback(() => {
    // Click on empty space = deselect
    if (highlightedRef.current) {
      const orig = originalMaterialMap.get(highlightedRef.current)
      if (orig) highlightedRef.current.material = orig as MeshStandardMaterial
      highlightedRef.current = null
      onPartSelect?.(null)
      onPartInfo?.(null)
    }
  }, [onPartSelect, onPartInfo])

  // v82nu iter3: Select All — when the parent bumps selectAllToken, emit
  // an aggregated PartInfo across all meshes in the model. Useful for the
  // "tout selectionner" button which shows total polycount, dims, etc.
  useEffect(() => {
    if (selectAllToken == null || !model) return
    onPartSelect?.('all')
    if (onPartInfo) onPartInfo(_aggregatePartInfo(model))
  }, [selectAllToken, model, onPartSelect, onPartInfo])

  if (!model) return null
  return (
    <Center>
      <group ref={groupRef} onClick={handleClick} onPointerMissed={handlePointerMissed}>
        <primitive object={model} />
      </group>
    </Center>
  )
}

/** Camera controller that resets on double-click and auto-fits the model */
function CameraController({ viewer, modelLoaded }: { viewer: ViewerConfig; modelLoaded: boolean }) {
  const { camera, scene, gl } = useThree()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const controlsRef = useRef<any>(null)
  const defaultCameraPos = useMemo(() => new Vector3(...viewer.cameraPosition), [viewer.cameraPosition])
  const defaultTarget = useMemo(() => new Vector3(0, 0, 0), [])

  // Auto-fit camera to model bounds when loaded — ensures model is always centered and visible
  useEffect(() => {
    if (!modelLoaded) return
    // Small delay to ensure the model is fully loaded and the scene graph is updated
    const fitTimer = setTimeout(() => {
      const box = new Box3().setFromObject(scene)
      if (box.isEmpty()) return
      const boxCenter = box.getCenter(new Vector3())
      const boxSize = box.getSize(new Vector3())
      const maxDim = Math.max(boxSize.x, boxSize.y, boxSize.z)
      // Position camera at a comfortable distance, slightly above and to the side for 3/4 view
      const fitDistance = Math.max(maxDim * 2.5, 1.5)
      camera.position.set(
        boxCenter.x + fitDistance * 0.3,
        boxCenter.y + fitDistance * 0.25,
        boxCenter.z + fitDistance * 0.85,
      )
      camera.lookAt(boxCenter)
      camera.updateProjectionMatrix()
      if (controlsRef.current) {
        controlsRef.current.target.copy(boxCenter)
        controlsRef.current.update()
      }
    }, 300)
    return () => clearTimeout(fitTimer)
  }, [camera, modelLoaded, scene])

  // Double-click to reset view
  useEffect(() => {
    const canvas = gl.domElement
    const handleDblClick = () => {
      camera.position.copy(defaultCameraPos)
      if (controlsRef.current) {
        controlsRef.current.target.copy(defaultTarget)
        controlsRef.current.update()
      }
    }
    canvas.addEventListener('dblclick', handleDblClick)
    return () => canvas.removeEventListener('dblclick', handleDblClick)
  }, [camera, defaultCameraPos, defaultTarget, gl.domElement])

  return (
    <OrbitControls
      ref={controlsRef}
      enableDamping
      dampingFactor={0.08}
      enableRotate={!viewer.lockView}
      enablePan
      enableZoom
      panSpeed={1.2}
      zoomSpeed={1.4}
      rotateSpeed={0.8}
      minDistance={0.3}
      maxDistance={50}
      makeDefault
    />
  )
}

type CameraSnapKind = 'face' | 'side' | 'top' | 'iso' | null

function ViewerExportMenu({
  onPng,
  onObj,
  onStl,
  onGlb,
}: {
  onPng: () => void
  onObj: () => void
  onStl: () => void
  onGlb: () => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="pointer-events-auto relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="rounded-lg border border-aurora-border/60 bg-aurora-surface/80 px-2 py-1 text-[10px] font-medium text-aurora-text-dim hover:text-aurora-text transition-colors"
        title="Exporter en PNG / OBJ / STL / GLB"
      >
        💾 Export ▾
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 flex w-40 flex-col overflow-hidden rounded-lg border border-aurora-border bg-aurora-surface-2 shadow-xl">
          <button
            onClick={() => { setOpen(false); onPng() }}
            className="px-3 py-1.5 text-left text-[10px] text-aurora-text hover:bg-aurora-accent/10"
          >
            📷 PNG — capture viewer
          </button>
          <button
            onClick={() => { setOpen(false); onGlb() }}
            className="px-3 py-1.5 text-left text-[10px] text-aurora-text hover:bg-aurora-accent/10"
          >
            📦 GLB — fichier source
          </button>
          <button
            onClick={() => { setOpen(false); onObj() }}
            className="px-3 py-1.5 text-left text-[10px] text-aurora-text hover:bg-aurora-accent/10"
          >
            🗂 OBJ — mesh seul
          </button>
          <button
            onClick={() => { setOpen(false); onStl() }}
            className="px-3 py-1.5 text-left text-[10px] text-aurora-text hover:bg-aurora-accent/10"
          >
            🖨 STL — impression 3D
          </button>
        </div>
      )}
    </div>
  )
}

function CameraSnapHandler({ snap, onSnapHandled }: { snap: CameraSnapKind; onSnapHandled: () => void }) {
  const { camera, scene } = useThree()
  useEffect(() => {
    if (!snap) return
    const box = new Box3().setFromObject(scene)
    if (box.isEmpty()) return
    const size = box.getSize(new Vector3()).length() || 1
    const center = box.getCenter(new Vector3())
    const distance = size * 1.8
    const positions: Record<Exclude<CameraSnapKind, null>, Vector3> = {
      face: new Vector3(0, 0, distance),
      side: new Vector3(distance, 0, 0),
      top: new Vector3(0, distance, 0.001),
      iso: new Vector3(distance * 0.7, distance * 0.7, distance * 0.7),
    }
    const target = positions[snap].add(center)
    camera.position.copy(target)
    camera.lookAt(center)
    camera.updateProjectionMatrix()
    onSnapHandled()
  }, [snap, camera, scene, onSnapHandled])
  return null
}

/**
 * ProceduralEnvironment — installs a dynamically-built environment map so
 * MeshStandardMaterial / MeshPhysicalMaterial show real reflections instead
 * of looking flat-shaded.
 *
 * v55 layered loading:
 *   1. Try a real HDRI from Polyhaven CDN (high-quality, sharp reflections)
 *   2. Fall back to RoomEnvironment (built-in, instant, offline-friendly)
 *   3. If both fail, leave scene.environment null — directional + hemisphere
 *      lights already give a usable result.
 */
const HDRI_URLS: Record<string, string> = {
  studio: 'https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/studio_small_09_1k.hdr',
  outdoor: 'https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/sunset_in_the_chalk_quarry_1k.hdr',
  indoor: 'https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/photo_studio_loft_hall_1k.hdr',
}

function ProceduralEnvironment({ hdri = 'studio' }: { hdri?: 'studio' | 'outdoor' | 'indoor' | null }) {
  const { scene, gl } = useThree()
  useEffect(() => {
    let cancelled = false
    let activeRenderTarget: { dispose: () => void } | null = null
    let activeTexture: { dispose: () => void } | null = null
    ;(async () => {
      const { PMREMGenerator } = await import('three')
      const pmrem = new PMREMGenerator(gl)
      pmrem.compileEquirectangularShader?.()

      // Layer 1: Polyhaven HDRI when allowed (skipped if hdri === null).
      const hdriUrl = hdri ? HDRI_URLS[hdri] : null
      if (hdriUrl) {
        try {
          const { RGBELoader } = await import('three/examples/jsm/loaders/RGBELoader.js')
          const texture = await new Promise<{ dispose: () => void } | null>((resolve) => {
            new RGBELoader().load(
              hdriUrl,
              (tex) => resolve(tex as unknown as { dispose: () => void }),
              undefined,
              () => resolve(null),
            )
          })
          if (!cancelled && texture) {
            const target = pmrem.fromEquirectangular(texture as never)
            if (!cancelled) {
              scene.environment = target.texture
              activeRenderTarget = target
              activeTexture = texture
            }
            pmrem.dispose()
            return
          }
        } catch {
          // HDRI fetch failed (offline, CORS) — fall through to layer 2.
        }
      }

      // Layer 2: RoomEnvironment built-in scene.
      try {
        const { RoomEnvironment } = await import('three/examples/jsm/environments/RoomEnvironment.js')
        if (cancelled) {
          pmrem.dispose()
          return
        }
        const env = new RoomEnvironment()
        const target = pmrem.fromScene(env, 0.04)
        if (!cancelled) {
          scene.environment = target.texture
          activeRenderTarget = target
        }
        env.dispose?.()
      } catch {
        // RoomEnvironment unavailable in this Three.js build — skip silently.
      }
      pmrem.dispose()
    })()
    return () => {
      cancelled = true
      scene.environment = null
      activeRenderTarget?.dispose?.()
      activeTexture?.dispose?.()
    }
  }, [scene, gl, hdri])
  return null
}

/**
 * BonesOverlay — overlays a SkeletonHelper on every SkinnedMesh in the scene.
 * Useful for diagnosing rigged characters: you can see if Rigify generated
 * proper bone chains, if the IK targets are placed correctly, and if the
 * mesh follows the skeleton on animation. Toggleable via the viewer chrome.
 */
function BonesOverlay({ visible, modelRoot }: { visible: boolean; modelRoot: Object3D | null }) {
  const { scene } = useThree()
  useEffect(() => {
    if (!visible || !modelRoot) return
    const helpers: SkeletonHelper[] = []
    modelRoot.traverse((child) => {
      const skinned = child as SkinnedMesh
      if (skinned.isSkinnedMesh && skinned.skeleton) {
        const helper = new SkeletonHelper(skinned)
        ;(helper.material as { linewidth?: number }).linewidth = 2
        helpers.push(helper)
        scene.add(helper)
      }
    })
    // If no SkinnedMesh found, fall back to overlaying the root tree itself
    // so the user at least sees object hierarchy.
    if (helpers.length === 0) {
      const fallback = new SkeletonHelper(modelRoot)
      helpers.push(fallback)
      scene.add(fallback)
    }
    return () => {
      for (const helper of helpers) {
        scene.remove(helper)
        helper.dispose?.()
      }
    }
  }, [visible, modelRoot, scene])
  return null
}

function AxesOverlay({ visible }: { visible: boolean }) {
  const { scene } = useThree()
  useEffect(() => {
    if (!visible) return
    const helper = new AxesHelper(1.5)
    scene.add(helper)
    return () => {
      scene.remove(helper)
      helper.dispose?.()
    }
  }, [visible, scene])
  return null
}

function Scene3D({
  modelUrl,
  viewer,
  onPartSelect,
  onPartInfo,
  selectAllToken,
  onAnimationsLoaded,
  onModelLoaded,
  playAnimations = true,
  animationSpeed = 1,
  manualTime = null,
  wireframe = false,
  activeClipIndex = -1,
  materialMode = 'authored',
  showGrid = true,
  showAxes = false,
  showBones = false,
  hdri = 'studio',
  cameraSnap = null,
  onSnapHandled,
  onDurationChange,
  onTimeChange,
  onCanvasReady,
  pbrProfile = null,
}: {
  modelUrl: string
  viewer: ViewerConfig
  onPartSelect?: (name: string | null) => void
  onPartInfo?: (info: PartInfo | null) => void
  selectAllToken?: number
  onAnimationsLoaded?: (clips: AnimationClip[]) => void
  onModelLoaded?: (model: Object3D) => void
  playAnimations?: boolean
  animationSpeed?: number
  manualTime?: number | null
  wireframe?: boolean
  activeClipIndex?: number
  materialMode?: ViewerMaterialMode
  showGrid?: boolean
  showAxes?: boolean
  showBones?: boolean
  hdri?: 'studio' | 'outdoor' | 'indoor' | null
  cameraSnap?: CameraSnapKind
  onSnapHandled?: () => void
  onDurationChange?: (duration: number) => void
  onTimeChange?: (time: number) => void
  onCanvasReady?: (canvas: HTMLCanvasElement) => void
  pbrProfile?: PbrProfile | null
}) {
  const [modelLoaded, setModelLoaded] = useState(false)
  const [internalRoot, setInternalRoot] = useState<Object3D | null>(null)

  // Detect model loaded via key change
  useEffect(() => {
    setModelLoaded(false)
    const timer = setTimeout(() => setModelLoaded(true), 500)
    return () => clearTimeout(timer)
  }, [modelUrl])

  return (
    <Canvas
      camera={{ position: viewer.cameraPosition, fov: 46 }}
      dpr={[1.25, 2]}
      performance={{ min: 0.75 }}
      gl={{ antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: true }}
      className="rounded-[1.8rem]"
      onCreated={({ gl }) => {
        // v77ze: Meshy-style vivid rendering — ACES filmic tone mapping with a
        // gentle exposure boost gives saturated cinematic colors out of the
        // texture-paint pass instead of washed-out neutral output.
        gl.toneMapping = ACESFilmicToneMapping
        gl.toneMappingExposure = 1.18
        gl.outputColorSpace = SRGBColorSpace
        onCanvasReady?.(gl.domElement)
      }}
    >
      <color attach="background" args={[AURORA_V4_SKIN ? '#05070D' : '#091116']} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[5, 6, 5]} intensity={1.5} castShadow />
      <directionalLight position={[-3, 4, -2]} intensity={0.6} color={AURORA_V4_SKIN ? '#60A5FA' : '#37c7bf'} />
      <directionalLight position={[0, -3, 4]} intensity={0.3} color={AURORA_V4_SKIN ? '#8B5CF6' : '#ff6a3d'} />
      <directionalLight position={[-5, 2, 5]} intensity={0.4} color={AURORA_V4_SKIN ? '#22D3EE' : '#ffd166'} />
      <hemisphereLight args={['#b1e1ff', '#1a1a2e', 0.45]} />
      <ProceduralEnvironment hdri={hdri} />
      {showGrid && <gridHelper args={AURORA_V4_SKIN ? [10, 20, '#1E2A4A', '#0C1224'] : [10, 20, '#1a2a35', '#0d1a22']} position={[0, -0.01, 0]} />}
      <AxesOverlay visible={showAxes} />
      <BonesOverlay visible={showBones} modelRoot={internalRoot} />
      <CameraSnapHandler snap={cameraSnap} onSnapHandled={onSnapHandled ?? (() => undefined)} />
      <Suspense fallback={null}>
        <InteractiveModel
          url={modelUrl}
          autoRotate={viewer.autoRotate}
          onPartSelect={onPartSelect}
          onPartInfo={onPartInfo}
          selectAllToken={selectAllToken}
          onAnimationsLoaded={onAnimationsLoaded}
          onModelLoaded={(model) => { setInternalRoot(model); onModelLoaded?.(model) }}
          playAnimations={playAnimations}
          animationSpeed={animationSpeed}
          manualTime={manualTime}
          wireframe={wireframe}
          materialMode={materialMode}
          activeClipIndex={activeClipIndex}
          pbrProfile={pbrProfile}
          onDurationChange={onDurationChange}
          onTimeChange={onTimeChange}
        />
      </Suspense>
      <CameraController viewer={viewer} modelLoaded={modelLoaded} />
    </Canvas>
  )
}

export default function ModelView() {
  const { runtimeServices, visionModel, hardware } = useAppStore()
  const diagnostics = useStudioDiagnostics({ requiresTauri: true, requiresOllama: true, requiredFiles: [{ label: 'Pipeline Atlas', relativePath: 'python-services/aurora_3d_pipeline.py' }] })
  const { executeWithRuntime } = useManagedRuntime()
  const { pushMessage, getRecentMessages } = useModuleHistoryStore()
  const { trackGeneration, completeGeneration, failGeneration } = useGenerationTrackerStore()
  const recovery = useGenerationRecovery('3d')
  const activeTrackerIdRef = useRef<string | null>(null)
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const estImage = (f: File) => f.type.startsWith('image/')
    || /\.(png|jpe?g|webp|avif|bmp|gif|tiff?|heic|heif|jfif|svg)$/i.test(f.name || '')
  const [selectionCible, setSelectionCible] = useState<File | null>(null)
  const [bridgeUrlSelection, setBridgeUrlSelection] = useState('')
  const { pack: assetPack, preparePack } = useModuleAssetPack({ module: '3d', title: 'Pack modele 3D', assets: buildThreeDModuleAssets(visionModel, runtimeServices.comfyui.path, contextFiles.length > 0, !contextFiles.some(estImage)) })
  const [prompt, setPrompt] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [progress, setProgress] = useState('')
  // v77zag: live progress snapshot for the ThreeDProgressOverlay. Updated
  // from inside the onPythonProgress callback so it reflects every PROGRESS:
  // event the bridge / Tauri bus pushes — works identically in tunnel and
  // Tauri runtimes since onPythonProgress already abstracts the source.
  const [phaseSnapshot, setPhaseSnapshot] = useState<{ label: string; percent: number }>({ label: '', percent: 0 })
  const [error, setError] = useState<string | null>(null)
  const [workspace, setWorkspace] = useState<'model' | 'assembly'>('model')
  const importedOriginalUrl = useRef<string | null>(null)
  useEffect(() => () => { if (importedOriginalUrl.current) URL.revokeObjectURL(importedOriginalUrl.current) }, [])
  const [modelUrl, setModelUrl] = useState<string | null>(null)
  const [viewerFullscreen, setViewerFullscreen] = useState(false)
  const [viewerWebUrl, setViewerWebUrl] = useState<string | null>(null)
  const [referenceImageUrl, setReferenceImageUrl] = useState<string | null>(null)
  const [discoveredSourceWeb, setDiscoveredSourceWeb] = useState<{ site?: string; url?: string; title?: string } | null>(null)
  // Validation de la reference AVANT la reconstruction 3D (~20 min): l'utilisateur
  // accepte (vert) ou refuse (rouge, avec un motif optionnel) l'image en LOT. Sur
  // acceptation, la photo est VERROUILLEE (jamais retouchee, reproduite fidelement).
  const [refConfirm, setRefConfirm] = useState<{ urls: string[]; title: string; resolve: (d: { accepted: boolean; reason?: string }) => void } | null>(null)
  const [refReason, setRefReason] = useState('')
  const referenceConfirmEnabled = (() => { try { return localStorage.getItem('aurora3d_ref_confirm') !== '0' } catch { return true } })()
  // TRELLIS est prioritaire, mais une generation doit livrer un mesh lorsque le
  // premier moteur ne peut pas exporter sa texture. Le mode strict reste une
  // preference experte explicite (aurora3d_trellis_only=1), jamais le defaut.
  // Le pipeline libere le processus TRELLIS avant de charger Hunyuan, ce qui
  // evite de cumuler les deux modeles en VRAM.
  const trellisOnly = (() => { try { return localStorage.getItem('aurora3d_trellis_only') === '1' } catch { return false } })()
  const confirmReqHandledRef = useRef<Set<string>>(new Set())
  const renderRefBlobRef = useRef<((promptText: string, stepsOverride?: number, label?: string) => Promise<Blob>) | null>(null)
  const baseRefPromptRef = useRef<string>('')
  const referenceLockedRef = useRef<boolean>(false)
  // Lot d'images a valider (1 = mono-vue de depart; N = vues derivees quand la
  // mono-vue ne suffit pas). title decrit ce qu'on demande de valider.
  const askReferenceConfirm = useCallback((urls: string[], title: string) => {
    // Affichee PAR l'ecran de generation (surface unique, clics verrouilles);
    // repli sur la modale classique si l'ecran est desactive.
    const viaFx = fxAsk<{ accepted: boolean; reason?: string }>('3d', {
      id: `confirm-${Date.now()}`,
      kind: 'confirm_images',
      question: title,
      images: urls,
      allowText: true,
    })
    if (viaFx !== null) return viaFx
    return new Promise<{ accepted: boolean; reason?: string }>((resolve) => {
      setRefReason('')
      setRefConfirm({ urls, title, resolve })
    })
  }, [])
  const [referenceSupport, setReferenceSupport] = useState<ThreeDReferenceSupport | null>(null)
  const [viewPlan, setViewPlan] = useState<ThreeDViewPlan | null>(null)
  const [referenceAnalysis, setReferenceAnalysis] = useState<VisualReferenceAnalysis | null>(null)
  const [manualColorOverrides, setManualColorOverrides] = useState<ColorOverride[]>([])
  const [focusEntityIndexOverride, setFocusEntityIndexOverride] = useState<number | null>(null)
  const [isAnalyzingReference, setIsAnalyzingReference] = useState(false)
  const lastAnalyzedFileSignatureRef = useRef<string | null>(null)
  const [saveDialogData, setSaveDialogData] = useState<SaveDialogData | null>(null)
  const [promptLibraryOpen, setPromptLibraryOpen] = useState(false)
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null)
  const [detectedIntent, setDetectedIntent] = useState<ThreeDIntent | null>(null)
  const [selectedMotionPresetId, setSelectedMotionPresetId] = useState<string | null>(null)
  const [selectedPart, setSelectedPart] = useState<string | null>(null)
  // v82nu iter3: rich part-info panel + Select All + custom-motion zone
  const [selectedPartInfo, setSelectedPartInfo] = useState<PartInfo | null>(null)
  const [selectAllToken, setSelectAllToken] = useState(0)
  const [customMotionText, setCustomMotionText] = useState('')
  const [customMotionStatus, setCustomMotionStatus] = useState<'idle' | 'classifying' | 'baking' | 'done' | 'error'>('idle')
  const [customMotionResult, setCustomMotionResult] = useState<{ category: string; rationale: string; rebake?: boolean } | null>(null)
  const [playAnimations, setPlayAnimations] = useState(true)
  // Bouton MOUVEMENT : ON = on bake une vraie animation (le classifieur choisit laquelle),
  // OFF = mesh statique (la pose de génération, ex. "Caine en train de tomber" reste figée).
  // Lu via un ref dans generate() (useCallback) pour éviter une closure obsolète.
  const [motionEnabled, setMotionEnabled] = useState(true)
  const motionEnabledRef = useRef(true)
  const toggleMotion = useCallback(() => setMotionEnabled((v) => { motionEnabledRef.current = !v; return !v }), [])
  const [animationSpeed, setAnimationSpeed] = useState(1)
  const [animationClips, setAnimationClips] = useState<AnimationClip[]>([])
  const [activeClipIndex, setActiveClipIndex] = useState(-1)
  const [animationDuration, setAnimationDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [scrubTime, setScrubTime] = useState<number | null>(null)
  const [wireframe, setWireframe] = useState(false)
  const [viewerMaterialMode, setViewerMaterialMode] = useState<ViewerMaterialMode>('authored')
  const [isLoadingColors, setIsLoadingColors] = useState(false)
  const [colorLoadResult, setColorLoadResult] = useState<string | null>(null)
  const [showGrid, setShowGrid] = useState(true)
  const [showAxes, setShowAxes] = useState(false)
  const [showBones, setShowBones] = useState(false)
  const [boneCount, setBoneCount] = useState(0)
  const [hdriPreset, setHdriPreset] = useState<'studio' | 'outdoor' | 'indoor' | null>('studio')
  const [meshFaceCount, setMeshFaceCount] = useState(0)
  // stocke le rapport qualite mesh du dernier result TRELLIS.2/DreamGaussian
  // pour exposer un bouton 'Inspecter mesh' qui affiche tout (grade, watertight,
  // disconnected bodies, flatness, etc.) sans devoir relancer une generation.
  type MeshQualityReport = {
    grade?: string
    qualityOk?: boolean
    issues?: string[]
    warnings?: string[]
    vertexCount?: number
    faceCount?: number
    extents?: [number, number, number]
    flatnessRatio?: number
    aspectRatio?: number
    disconnectedBodies?: number
    degenerateFaceCount?: number
    isWatertight?: boolean
    surfaceArea?: number
    volume?: number
  }
  const [meshQualityReport, setMeshQualityReport] = useState<MeshQualityReport | null>(null)
  const [cameraSnap, setCameraSnap] = useState<CameraSnapKind>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const viewerContainerRef = useRef<HTMLDivElement | null>(null)
  const canvasElementRef = useRef<HTMLCanvasElement | null>(null)
  const modelRootRef = useRef<Object3D | null>(null)
  const handleAnimationsLoaded = useCallback((clips: AnimationClip[]) => {
    setAnimationClips(clips)
    setPlayAnimations(clips.length > 0)
    setAnimationSpeed(1)
    // Auto-play the first clip by default when a single one is available
    // (typical Rigify/Mixamo export). Only fall back to "all clips" when the
    // GLB ships multiple distinct animations the user might want to mix.
    setActiveClipIndex(clips.length === 1 ? 0 : -1)
    setScrubTime(null)
    setCurrentTime(0)
  }, [])
  const handleModelLoaded = useCallback((model: Object3D) => {
    modelRootRef.current = model
    // Count bones + faces across the whole model so the UI can advertise
    // "rigged with N bones" / "M faces" and trigger smart defaults:
    //   - bones >0    → auto-toggle the SkeletonHelper overlay so the user
    //                   sees the rig immediately on load (no hunting for it)
    //   - faces > 200k → surface a "mesh lourd, sauvetage suggere" hint
    let bones = 0
    let faces = 0
    model.traverse((child) => {
      const skinned = child as SkinnedMesh
      if (skinned.isSkinnedMesh && skinned.skeleton) {
        bones += skinned.skeleton.bones.length
      }
      const meshChild = child as Mesh
      if (meshChild.isMesh && meshChild.geometry) {
        const indexCount = meshChild.geometry.index?.count ?? 0
        const positionCount = meshChild.geometry.attributes?.position?.count ?? 0
        faces += indexCount > 0 ? indexCount / 3 : positionCount / 3
      }
    })
    setBoneCount(bones)
    setMeshFaceCount(Math.round(faces))
    // Smart default: open the bones overlay automatically on rigged meshes so
    // the user immediately sees the auto-rig result. If the user manually
    // toggled it off before a new model loads, we respect that intent —
    // reset to false on every load and re-enable only when bones are present.
    setShowBones(bones > 0)
  }, [])

  // Mobile reload rescue: if we come back to a fresh mount after a tab kill
  // but the bridge still has a 3D job running from the previous session,
  // surface a banner so the user knows their generation didn't vanish.
  const [pendingJobBanner, setPendingJobBanner] = useState<{ jobId: string; status: 'queued' | 'running' | 'done' } | null>(null)
  // v77zah: auto-reattach the live overlay when the user navigates back to
  // ModelView while a 3D job is still running on the PC. Without this the
  // generation looks "arrêtée" because the overlay's host component was
  // unmounted — but the job continues server-side. Re-arming the
  // onPythonProgress listener restores the percent / heartbeat / detail
  // line as if the user had never left.
  useEffect(() => {
    let alive = true
    const tick = async () => {
      const info = await peekResumableJob('model')
      if (!alive) return
      setPendingJobBanner(info)
      if (info && info.status === 'running' && !unlistenRef.current) {
        // Job still running, our listener is unarmed → reconnect.
        setIsGenerating(true)
        setPhaseSnapshot({
          label: 'Reconnexion a la generation en cours sur le PC...',
          percent: 60,
        })
        try {
          unlistenRef.current = await onPythonProgress((message) => {
            if (!message.startsWith('PROGRESS:')) return
            const parts = message.split(':')
            const stage = parts[1] || 'run'
            const detail = parts.slice(2).join(':') || stage
            setProgress(detail)
            const phaseProgress = stage === 'install' ? 82 : stage === 'device' || stage === 'bg' || stage === 'asset_scan' ? 84 : stage === 'asset_download' || stage === 'shape_fallback' || stage === 'shape_load' ? 86 : stage === 'shape_run' || stage === 'gaussian' ? 90 : stage === 'texture_load' || stage === 'texture_run' || stage === 'texture_retry' || stage === 'texture_warn' || stage === 'mesh_extract' ? 92 : stage === 'export' || stage === 'export_fallback' ? 95 : stage === 'procedural' ? 88 : stage === 'sfm' || stage === 'photogrammetry' ? 87 : stage === 'validate' ? 94 : stage === 'rig' ? 93 : 88
            setPhaseSnapshot({ label: detail, percent: phaseProgress })
          })
        } catch {
          // Bridge unreachable — overlay will surface the inactivity warning.
        }
      }
      if (info && info.status === 'done') {
        setIsGenerating(false)
        setPhaseSnapshot({ label: '', percent: 0 })
        unlistenRef.current?.()
        unlistenRef.current = null
      }
    }
    void tick()
    const id = window.setInterval(tick, 5_000)
    return () => { alive = false; window.clearInterval(id) }
  }, [])

  const triggerReferenceAnalysis = useCallback(async () => {
    const imageFile = contextFiles.find((file) => file.type.startsWith('image/') || /\.(png|jpe?g|webp|avif|bmp|gif|tiff?|heic|heif|jfif|svg)$/i.test(file.name || ''))
    if (!imageFile && !referenceImageUrl) return
    setIsAnalyzingReference(true)
    try {
      let blob: Blob | null = null
      if (imageFile) {
        blob = imageFile
      } else if (referenceImageUrl) {
        try {
          const resp = await fetch(referenceImageUrl)
          if (resp.ok) blob = await resp.blob()
        } catch { /* reference URL unreachable */ }
      }
      if (!blob) return
      const analysis = await analyzeReferenceImage({
        blob,
        model: visionModel,
        prompt: prompt || 'reference 3D subject',
        userRequestedSubject: prompt,
      })
      setReferenceAnalysis(analysis)
      // Reset focus override so the newly-detected dominant entity wins unless
      // the user explicitly picks another one.
      setFocusEntityIndexOverride(null)
    } finally {
      setIsAnalyzingReference(false)
    }
  }, [contextFiles, referenceImageUrl, visionModel, prompt])

  // Auto-run the analyzer as soon as the user drops an image reference so
  // the palette swatches and bounding boxes appear WITHOUT waiting for the
  // full 3D generation. Each upload is keyed by a stable signature so we
  // don't re-run on unrelated state changes.
  useEffect(() => {
    const imageFile = contextFiles.find((file) => file.type.startsWith('image/') || /\.(png|jpe?g|webp|avif|bmp|gif|tiff?|heic|heif|jfif|svg)$/i.test(file.name || ''))
    if (!imageFile) return
    const signature = `${imageFile.name}:${imageFile.size}:${imageFile.lastModified}`
    if (lastAnalyzedFileSignatureRef.current === signature) return
    lastAnalyzedFileSignatureRef.current = signature
    void triggerReferenceAnalysis()
  }, [contextFiles, triggerReferenceAnalysis])
  const exportModelAsObj = useCallback(async () => {
    const model = modelRootRef.current
    if (!model) return
    try {
      const { OBJExporter } = await import('three/examples/jsm/exporters/OBJExporter.js')
      const exporter = new OBJExporter()
      const objText = exporter.parse(model)
      const blob = new Blob([objText], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `aurora-3d-${Date.now()}.obj`
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch {
      // export indisponible (ex: runtime obsolete) — silencieux
    }
  }, [])
  const exportModelAsStl = useCallback(async () => {
    const model = modelRootRef.current
    if (!model) return
    try {
      const { STLExporter } = await import('three/examples/jsm/exporters/STLExporter.js')
      const exporter = new STLExporter()
      const stlText = exporter.parse(model)
      const blob = new Blob([stlText], { type: 'application/sla' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `aurora-3d-${Date.now()}.stl`
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch {
      // export STL indisponible
    }
  }, [])
  const downloadOriginalGlb = useCallback(async () => {
    if (!modelUrl) return
    try {
      const response = await fetch(modelUrl)
      if (!response.ok) return
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      const ext = modelUrl.toLowerCase().includes('.gltf') ? 'gltf' : 'glb'
      anchor.download = `aurora-3d-${Date.now()}.${ext}`
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch {
      // download raw indisponible (ex: blob source introuvable)
    }
  }, [modelUrl])

  // Mesh rescue: appel direct mesh_postprocess.py en mode aggressive sur le
  // mesh actuellement charge dans le viewer. Pratique pour l user qui voit
  // un artefact (spike, surface rugueuse, floater) et veut re-nettoyer sans
  // relancer toute la generation.
  const [isRescuing, setIsRescuing] = useState(false)
  const [rescueProgress, setRescueProgress] = useState<string | null>(null)
  const [rescueResult, setRescueResult] = useState<string | null>(null)
  const [isGeneratingPhysics, setIsGeneratingPhysics] = useState(false)

  // Physics chain shortcut: invoke the physics_chain_system Blender template
  // directly (Bullet rigid bodies + hinge constraints + bake_to_keyframes)
  // so the user gets a believable swinging chain / rope / pendulum / dominos
  // animation without first generating a mesh from a reference image.
  const generatePhysicsChain = useCallback(async () => {
    if (isGeneratingPhysics) return
    setIsGeneratingPhysics(true)
    setError(null)
    setProgress('Simulation physique Bullet...')
    try {
      const workspace = await getWorkspacePath()
      const runId = `physics_${Date.now()}`
      const active3dSession = useModuleHistoryStore.getState().getActiveSession('3d')
      const runPaths = buildThreeDRunOutputPaths(workspace, active3dSession, runId, 'simulation physique')
      const outputDir = runPaths.models
      await Promise.all([
        fsMkdir(runPaths.conversationDir),
        fsMkdir(runPaths.root),
        fsMkdir(runPaths.prompts),
        fsMkdir(runPaths.models),
        fsMkdir(runPaths.motion),
        fsMkdir(runPaths.audits),
      ])
      // Heuristic params: derive link count + length from the prompt when the
      // user described a chain ("longue chaine de 30 maillons", "pendule"...)
      const prompt = (typeof findLatestUserPrompt === 'function' ? findLatestUserPrompt(getRecentMessages('3d', 6)) : '') || ''
      await fsWriteBinary(`${runPaths.prompts}/${runId}_prompt.txt`, utf8Bytes(prompt || 'physics chain'))
      const linkCountMatch = prompt.match(/(\d+)\s*(maillons?|links?|elements?)/i)
      const linkCount = linkCountMatch ? Math.max(4, Math.min(48, Number(linkCountMatch[1]))) : 18
      const isRope = /\bcorde|rope\b/i.test(prompt)
      const isPendulum = /\bpendule|pendulum\b/i.test(prompt)
      const params = {
        link_count: linkCount,
        link_length: isRope ? 0.04 : 0.06,
        link_radius: isRope ? 0.008 : 0.012,
        anchor_top: !isPendulum,
        anchor_bottom: false,
        gravity: -9.81,
        swing_impulse: isPendulum ? 2.4 : 1.5,
        seconds: 5,
      }
      const result = await runProceduralModeling({
        template: 'physics_chain_system',
        prompt,
        parameters: params,
        outputDir,
        runId,
        format: 'glb',
      })
      if (result.ok && result.outputPath) {
        setModelUrl(toAssetUrl(result.outputPath))
        setProgress(`Chaine physique generee (${linkCount} maillons, ${result.animationFrames || 0} frames). Lis le clip pour voir le swing.`)
      } else {
        setError(result.error || 'Echec simulation physique.')
      }
    } catch (err) {
      setError(getErrorMessage(err, 'Echec simulation physique.'))
    } finally {
      setIsGeneratingPhysics(false)
    }
  }, [isGeneratingPhysics, getRecentMessages])
  const rescueMesh = useCallback(async () => {
    if (!modelUrl || isRescuing) return
    setIsRescuing(true)
    setRescueResult(null)
    setRescueProgress('Lecture du mesh...')
    try {
      const workspace = await getWorkspacePath()
      // Resolve the mesh file path. modelUrl may be an asset:// URL when
      // running inside Tauri, so we materialize the binary into a fresh
      // tmp file and run the rescue against that local path.
      const ts = Date.now()
      const loadedMeshPath = lastMeshPathRef.current
      const rescueDir = loadedMeshPath ? buildColorLoadOutputDir(workspace, loadedMeshPath).replace(/\/color_load_\d+$/, '') : `${workspace}/output/3d/rescue_manual_${ts}`
      await fsMkdir(rescueDir)
      const inputPath = `${rescueDir}/manual_rescue_in_${ts}.glb`
      const outputPath = `${rescueDir}/manual_rescue_out_${ts}.glb`
      try {
        const response = await fetch(modelUrl)
        if (!response.ok) throw new Error(`fetch ${response.status}`)
        const arrayBuffer = await response.arrayBuffer()
        await fsWriteBinary(inputPath, Array.from(new Uint8Array(arrayBuffer)))
      } catch (fetchError) {
        setRescueResult(`Echec lecture mesh: ${getErrorMessage(fetchError, '')}`)
        return
      }
      // detect a real-world dimension hint from the prompt and apply it
      // during rescue. The user typing "epee de 1m20" now exports a mesh
      // sized at exactly 1.2m on its largest axis; downstream rigging
      // (pendulum period T=2pi*sqrt(L/g), vehicle wheel radius) becomes
      // physically correct instead of relying on the generator's raw scale.
      const { rescueMeshAggressively: rescueFn, postProcessMesh: ppMesh, parsePromptDimension } = await import('../services/meshPostprocess')
      const dimHint = parsePromptDimension(prompt || '')
      let result
      if (dimHint) {
        result = await ppMesh({
          inputPath,
          outputPath,
          floaterRatio: 0.015,
          smoothIterations: 28,
          targetFaces: 45_000,
          targetDimensionMeters: dimHint.meters,
          targetDimensionAxis: dimHint.axis,
          onProgress: ({ stage, detail }) => setRescueProgress(detail ? `${stage}: ${detail}` : stage),
        })
      } else {
        result = await rescueFn(inputPath, outputPath, ({ stage, detail }) => {
          setRescueProgress(detail ? `${stage}: ${detail}` : stage)
        })
      }
      if (result.ok && result.outputPath) {
        setModelUrl(toAssetUrl(result.outputPath))
        const before = result.beforeFaces ?? 0
        const after = result.afterFaces ?? 0
        const dropped = result.droppedFloaters ?? 0
        const dimLabel = dimHint ? ` -> ${dimHint.meters.toFixed(2)}m sur axe ${dimHint.axis}` : ''
        setRescueResult(`Mesh nettoye: ${before}->${after} faces${dropped > 0 ? `, ${dropped} floaters drops` : ''}${dimLabel} (${result.engine ?? 'auto'}).`)
      } else {
        setRescueResult(`Sauvetage echoue: ${result.error || 'erreur inconnue'}`)
      }
    } catch (error) {
      setRescueResult(`Echec sauvetage: ${getErrorMessage(error, 'erreur inconnue')}`)
    } finally {
      setIsRescuing(false)
      setRescueProgress(null)
    }
  }, [modelUrl, isRescuing])
  const loadViewerColors = useCallback(async () => {
    if (!modelUrl || isLoadingColors) return
    setIsLoadingColors(true)
    setColorLoadResult(null)
    try {
      const referencePath = lastReferenceImagePathRef.current
      const meshPath = lastMeshPathRef.current
      if (referencePath && meshPath) {
        const workspace = await getWorkspacePath()
        const { getBridgeUrl } = await import('../utils/runtime')
        const outputDir = buildColorLoadOutputDir(workspace, meshPath)
        const sourcePrompt = (prompt.trim() || findLatestUserPrompt(getRecentMessages('3d', 6)) || '').trim()
        const resp = await fetch(`${getBridgeUrl()}/api/3d/auto-rescue`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mesh: meshPath,
            reference: referencePath,
            prompt: sourcePrompt || 'restore color and material zones from reference',
            output_dir: outputDir,
          }),
          signal: AbortSignal.timeout(420_000),
        })
        const data = await resp.json() as {
          ok?: boolean
          rescue?: { final_mesh?: string; initial_score?: number; final_score?: number; score_delta?: number }
          error?: string
        }
        if (data.ok && data.rescue?.final_mesh) {
          const finalMesh = data.rescue.final_mesh
          lastMeshPathRef.current = finalMesh
          setModelUrl(toAssetUrl(finalMesh))
          setViewerMaterialMode('authored')
          const initial = data.rescue.initial_score ?? 0
          const final = data.rescue.final_score ?? 0
          const delta = data.rescue.score_delta ?? (final - initial)
          setColorLoadResult(`Couleurs bakees depuis la reference (${initial.toFixed(0)} -> ${final.toFixed(0)}, delta ${delta >= 0 ? '+' : ''}${delta.toFixed(0)}).`)
          return
        }
        setColorLoadResult(`Bake couleur indisponible: ${data.error || 'reponse invalide'}. Mode inspection active.`)
      } else {
        setColorLoadResult('Aucune reference locale exploitable. Mode inspection couleur active.')
      }
      setViewerMaterialMode('diagnostic')
    } catch (error) {
      setColorLoadResult(`Bake couleur echoue: ${getErrorMessage(error)}. Mode inspection active.`)
      setViewerMaterialMode('diagnostic')
    } finally {
      setIsLoadingColors(false)
    }
  }, [modelUrl, isLoadingColors, prompt, getRecentMessages])
  const handleDurationChange = useCallback((duration: number) => {
    setAnimationDuration(duration)
  }, [])
  const handleTimeChange = useCallback((time: number) => {
    setCurrentTime(time)
  }, [])
  const handleCanvasReady = useCallback((canvas: HTMLCanvasElement) => {
    canvasElementRef.current = canvas
  }, [])
  const captureViewerScreenshot = useCallback(() => {
    const canvas = canvasElementRef.current
    if (!canvas) return
    try {
      const dataUrl = canvas.toDataURL('image/png')
      const anchor = document.createElement('a')
      anchor.href = dataUrl
      anchor.download = `aurora-3d-${Date.now()}.png`
      anchor.click()
    } catch {
      // preserveDrawingBuffer manquant ou canvas tainted — ignore silencieusement
    }
  }, [])
  const toggleFullscreen = useCallback(async () => {
    const el = viewerContainerRef.current
    if (!el) return
    if (!document.fullscreenElement) {
      await el.requestFullscreen?.().catch(() => undefined)
      setIsFullscreen(true)
    } else {
      await document.exitFullscreen?.().catch(() => undefined)
      setIsFullscreen(false)
    }
  }, [])
  useEffect(() => {
    const onChange = () => setIsFullscreen(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])
  const [meshFidelity, setMeshFidelity] = useState<MeshFidelityVerification | null>(null)
  const [lastAnalyzedPrompt, setLastAnalyzedPrompt] = useState('')
  const { addPrompt } = usePromptLibraryStore()
  const unlistenRef = useRef<(() => void) | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const lastReferenceImagePathRef = useRef<string | null>(null)
  const lastMeshPathRef = useRef<string | null>(null)
  const activeOllamaModel = contextFiles.length > 0 ? visionModel : AUXILIARY_ANALYSIS_MODEL
  const recentMessages = getRecentMessages('3d', 6)
  const latestUserPrompt = findLatestUserPrompt(recentMessages)
  const trimmedPrompt = prompt.trim()

  // v82nu iter3: submit custom motion text to /api/3d/custom-motion which
  // re-classifies (LLM) + re-bakes via motion_intent_baker. Keeps the
  // mesh path cached on lastMeshPathRef so the bake hits the right GLB.
  const handleCustomMotionSubmit = useCallback(async () => {
    const text = customMotionText.trim()
    if (!text) return
    const seedPrompt = (trimmedPrompt || latestUserPrompt || '').trim()
    if (!seedPrompt) {
      setCustomMotionStatus('error')
      setCustomMotionResult({ category: 'idle', rationale: 'Decris d abord un sujet pour donner un contexte au mouvement custom.' })
      return
    }
    try {
      setCustomMotionStatus('classifying')
      setCustomMotionResult(null)
      const { getBridgeUrl } = await import('../utils/runtime')
      const bridge = getBridgeUrl()
      const meshPath = lastMeshPathRef.current
      const body: Record<string, unknown> = { prompt: seedPrompt, custom_motion_text: text }
      if (meshPath) {
        body.input_glb = meshPath
        body.output_glb = meshPath.replace(/\.glb$/i, '_custom.glb')
        setCustomMotionStatus('baking')
      }
      const resp = await fetch(`${bridge}/api/3d/custom-motion`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(220_000),
      })
      const data = await resp.json() as { ok: boolean; intent?: { category: string; rationale: string }; bake?: { ok?: boolean; exported?: string } | null; error?: string }
      if (!data.ok || !data.intent) {
        setCustomMotionStatus('error')
        setCustomMotionResult({ category: 'error', rationale: data.error || 'Reponse invalide du bridge.' })
        return
      }
      setCustomMotionStatus('done')
      setCustomMotionResult({
        category: data.intent.category,
        rationale: data.intent.rationale,
        rebake: !!data.bake?.ok,
      })
      // If the bake succeeded and produced a new GLB, swap the viewer to it.
      if (data.bake?.ok && data.bake.exported) {
        const exported = data.bake.exported
        // Re-load the GLB into the viewer; lastMeshPathRef is updated below.
        try {
          const url = await toAssetUrl(exported)
          setModelUrl(url)
          lastMeshPathRef.current = exported
        } catch {
          // viewer keeps the prior URL; the bake file is still on disk.
        }
      }
    } catch (exc) {
      setCustomMotionStatus('error')
      setCustomMotionResult({ category: 'error', rationale: getErrorMessage(exc) })
    }
  }, [customMotionText, trimmedPrompt, latestUserPrompt])

  const draftIntent = trimmedPrompt && trimmedPrompt !== lastAnalyzedPrompt ? previewThreeDIntent(trimmedPrompt) : null
  const uiIntent = draftIntent || detectedIntent
  const selectedMotionPreset = resolveSelectedMotionPreset(uiIntent, selectedMotionPresetId)
  const viewerConfig = resolveViewerConfig(detectedIntent || uiIntent, selectedMotionPreset)
  // v77zf: infer a PBR profile from the analyzed prompt so the viewer can
  // upgrade flat baseColor-only GLB materials to chrome / glass / skin /
  // fabric / etc. Falls back to a neutral profile when no prompt is yet known
  // (e.g. session restored from disk before any prompt is typed).
  const viewerPbrProfile = useMemo(() => {
    if (!uiIntent) return null
    const sourcePrompt = (lastAnalyzedPrompt || trimmedPrompt || '').trim()
    if (!sourcePrompt) return null
    return inferPbrProfile(sourcePrompt, uiIntent.subjectKind)
  }, [uiIntent, lastAnalyzedPrompt, trimmedPrompt])

  const hydrateSession = useCallback((session: ConversationSession) => {
    const assets = findSessionAssets(session)
    lastReferenceImagePathRef.current = assets.referencePath
    lastMeshPathRef.current = assets.meshPath
    setReferenceImageUrl(assets.referencePath ? toAssetUrl(assets.referencePath) : null)
    setModelUrl(assets.meshPath ? toAssetUrl(assets.meshPath) : null)
    setReferenceSupport(null)
    setViewPlan(null)
    setError(null)
    setProgress('')
    setDetectedIntent(null)
    setSelectedMotionPresetId(null)
    setLastAnalyzedPrompt('')
  }, [])

  useEffect(() => {
    return () => {
      unlistenRef.current?.()
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  useEffect(() => {
    hydrateSession(useModuleHistoryStore.getState().getActiveSession('3d'))
  }, [hydrateSession])

  useEffect(() => {
    if (selectedMotionPresetId && !resolveSelectedMotionPreset(uiIntent, selectedMotionPresetId)) {
      setSelectedMotionPresetId(null)
    }
  }, [selectedMotionPresetId, uiIntent])

  // UNE PHOTO SUFFIT (30/07): exiger un prompt alors que l'utilisateur a
  // joint une image, c'est lui faire decrire ce que le systeme peut VOIR.
  // Avec une image attachee, la generation part sans texte; le sujet est
  // deduit de l'image (analyse vision cote pipeline).
  // TOUT FORMAT D'IMAGE EST ACCEPTE (30/07). Se fier au seul type MIME
  // rejetait le .webp (type souvent vide selon la source du fichier) — or
  // c'est justement le format qui conserve la TRANSPARENCE: convertir en JPG
  // aplatit l'alpha en damier et fausse l'analyse. On teste donc le MIME ET
  // l'extension, en couvrant les formats courants et modernes.
  const aUneImage = contextFiles.some(estImage)
  const canGenerate = (Boolean(prompt.trim()) || aUneImage) && !isGenerating && !diagnostics.blockingReason
  // UN BOUTON GRISE DOIT DIRE POURQUOI (30/07). Sans ce message, impossible de
  // savoir si c'est le prompt, l'image non reconnue ou un prerequis du poste
  // qui bloque — on tourne en rond a chaque fois.
  const raisonBlocage = isGenerating
    ? null
    : diagnostics.blockingReason
      ? `Prerequis: ${diagnostics.blockingReason}`
      : (!prompt.trim() && !aUneImage)
        ? (contextFiles.length > 0
            ? `Fichier joint non reconnu comme image (${contextFiles.map((f) => f.name || '?').join(', ')}). Ecrivez une demande, ou joignez une image.`
            : 'Ecrivez une demande, ou joignez simplement une photo.')
        : null

  // 31/07 (retour Juan): « ajoute un bouton pour arreter proprement sans me
  // creer un dossier fantome ... ou continue a pomper mon pc pour rien ».
  // Arret REEL: annulation du job cote bridge (le processus meurt), plus
  // aucun suivi local. La reprise auto reste utile au tunnel; ici on donne
  // le controle.
  // 31/07 (retour Juan, tunnel): revenir apres 1h30 doit montrer OU en est
  // la generation, et si c'est FINI, afficher le resultat avec ses boutons —
  // jamais une page vierge. Le bridge garde le job 4 h: on relit son stdout,
  // on en extrait le JSON final du pipeline et on raccroche le viewer.
  const recovererResultat = useCallback(async (jobId: string) => {
    try {
      const { getBridgeUrl: _gb } = await import('../utils/runtime')
      const bridge = _gb()
      const resp = await fetch(`${bridge}/api/python/job/${jobId}`)
      const job = await resp.json()
      const lignes = String(job?.output || '').split('\n')
      let resultat: Record<string, unknown> | null = null
      for (let i = lignes.length - 1; i >= 0; i -= 1) {
        const l = lignes[i].trim()
        if (l.startsWith('{') && l.includes('"ok"')) {
          try { resultat = JSON.parse(l); break } catch { /* ligne partielle */ }
        }
      }
      if (!resultat) { setError('Resultat introuvable dans le job — voir le dossier du run.'); return }
      const mesh = String((resultat.final_mesh as string) || (resultat.rigged_mesh as string) || '')
      if (resultat.ok && mesh) {
        const wsp = await getWorkspacePath()
        const rel = mesh.startsWith(`${wsp}/`) ? mesh.slice(wsp.length + 1) : mesh
        setViewerWebUrl(`${bridge}/aurora_viewer.html?file=${rel.split('/').map(encodeURIComponent).join('/')}`)
        setViewerFullscreen(true)
        setProgress(`Generation terminee — modele recupere (${rel.split('/').pop()})`)
        pushMessage('3d', { role: 'assistant', content: `Generation retrouvee apres reconnexion. Modele: ${rel}`, images: [mesh] })
      } else {
        setError(`La generation s'est terminee en echec: ${String(resultat.error || 'motif inconnu').slice(0, 200)}`)
      }
      clearResumableJob('model')
      setPendingJobBanner(null)
    } catch (e) {
      setError(`Recuperation impossible: ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [pushMessage])

  const stopRequestedRef = useRef(false)
  const stopGeneration = useCallback(async () => {
    stopRequestedRef.current = true
    try {
      const info = await peekResumableJob('model')
      if (info?.jobId) {
        const { getBridgeUrl: _gb } = await import('../utils/runtime')
        await fetch(`${_gb()}/api/python/cancel/${info.jobId}`, { method: 'POST' }).catch(() => null)
      }
    } catch { /* meme sans jobId on coupe le suivi */ }
    clearResumableJob('model')
    unlistenRef.current?.()
    unlistenRef.current = null
    setIsGenerating(false)
    setPendingJobBanner(null)
    setPhaseSnapshot({ label: '', percent: 0 })
    setProgress('Generation arretee proprement.')
    emitGenerationFx('3d', { active: false })
  }, [])

  useEffect(() => {
    const onFxStop = (e: Event) => {
      const det = (e as CustomEvent).detail as { module?: string } | undefined
      if (!det || det.module === '3d') void stopGeneration()
    }
    window.addEventListener('aurora-fx-stop', onFxStop)
    return () => window.removeEventListener('aurora-fx-stop', onFxStop)
  }, [stopGeneration])

  const generate = useCallback(async (promptOverride?: string) => {
    stopRequestedRef.current = false
    const imageJointe = contextFiles.find(estImage)
    // Sans texte mais AVEC une image: le sujet vient de l'image. On envoie un
    // prompt minimal neutre; le pipeline analyse la photo (vision) et n'a rien
    // a demander a l'utilisateur — l'information est deja dans l'image.
    const basePrompt = (promptOverride ?? prompt).trim()
      || (imageJointe ? 'reproduire fidelement le sujet de la photo fournie' : '')
    if (!basePrompt || isGenerating) return
    if (diagnostics.blockingReason) { setError(diagnostics.blockingReason); return }
    const currentPrompt = basePrompt
    const conversationHistory = getRecentMessages('3d', 6)
    setIsGenerating(true)
    setError(null)
    setProgress('Analyse de la demande 3D...')

    // Tracker la generation pour recovery apres refresh
    activeTrackerIdRef.current = trackGeneration({
      module: '3d',
      type: 'python_script',
      prompt: currentPrompt,
      startedAt: Date.now(),
      expectedOutputDir: '', // sera rempli dans le job
      expectedOutputPattern: 'juan_bike_.*\\.(glb|obj)',
    })

    try {
      await executeWithRuntime({
        module: '3d',
        title: 'Generation 3D',
        services: ['ollama'],
        prepare: async ({ setPhase }) => {
          const preview = previewThreeDIntent(currentPrompt)
          const characterRequest = ['character', 'creature', 'body_part'].includes(preview.subjectKind)
          const geometricRoute = !characterRequest && ['procedural', 'photogrammetry'].includes(preview.pipelineRouting.pipeline)
          if (!geometricRoute) {
            setPhase('Verification du moteur de reconstruction 3D...', 2)
            const workspace = await getWorkspacePath()
            const output = await runPythonScript(`${workspace}/python-services/aurora_3d_pipeline.py`, ['--check-runtime'])
            const readiness = parseLastJsonLine(output)
            if (!readiness?.ok) {
              throw new Error(String(readiness?.error || 'Moteur de reconstruction 3D indisponible sur le serveur'))
            }
          }
          setPhase('Initialisation des modèles...', 3)
          await preparePack(setPhase)
        },
        job: async ({ setPhase, ensureService }) => {
          const ensureComfy = () => ensureService('comfyui')
          setPhase('Analyse de la demande 3D...', 5)
          const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
          const preparedViews = resolvePreparedReferenceViews(preparedContext)
          const primaryPreparedImage = preparedViews.primary ?? pickPrimaryPreparedImage(preparedContext)
          // v77zao: subject-shift guard — if the new prompt's main subject does
          // NOT overlap with the conversation history (>= 2 word stems shared),
          // discard the history. This prevents "Système courroie poulie" stuck
          // in a session from polluting a fresh "guerrier elfique" intent
          // analysis. Otherwise keep the history (refinement / continuation).
          const promptStems = new Set(currentPrompt.toLowerCase().split(/\W+/).filter(w => w.length >= 4))
          const historyStems = new Set(
            conversationHistory.flatMap(m => m.content.toLowerCase().split(/\W+/)).filter(w => w.length >= 4)
          )
          const sharedStemCount = [...promptStems].filter(s => historyStems.has(s)).length
          const isContinuityOrEdit = EDIT_INTENT.test(currentPrompt) || /^(et|puis|aussi|maintenant|fais|pose|couleur|mati[eè]re|taille|texture|ajoute|modifie)\b/i.test(currentPrompt)
          const subjectShifted = conversationHistory.length > 0 && sharedStemCount < 2 && !isContinuityOrEdit
          const effectiveHistory = subjectShifted ? [] : conversationHistory
          if (subjectShifted) {
            console.warn('[ModelView] Subject shift detected, discarding conversation history to prevent contamination')
          }
          const conversationContext = buildConversationContext(effectiveHistory)
          let workingPrompt = conversationContext ? `${currentPrompt}\n\nContexte conversation 3D recente:\n${conversationContext}` : currentPrompt
          let historyPrompt = currentPrompt
          const intent = await analyzeThreeDIntent({ prompt: workingPrompt, model: visionModel, files: preparedContext, conversationHistory: effectiveHistory.map((message) => ({ role: message.role, content: message.content })) })
          setDetectedIntent(intent)
          setLastAnalyzedPrompt(currentPrompt)
          const activeMotionPreset = resolveSelectedMotionPreset(intent, selectedMotionPresetId)
          workingPrompt = [
            workingPrompt,
            '',
            `Intent 3D detecte: ${intent.summary}`,
            ...(activeMotionPreset
              ? ['Preset d action ou mouvement selectionne:', `- ${activeMotionPreset.label}`, `- ${activeMotionPreset.promptDirective}`]
              : []),
            'Contraintes 3D prioritaires:',
            ...intent.meshConstraints.slice(0, 4).map((item) => `- ${item}`),
            'Contraintes de mouvement ou articulation:',
            ...intent.motionGuidance.slice(0, 3).map((item) => `- ${item}`),
            ...(intent.movingPartsFocus.length > 0
              ? ['Sous-ensembles mobiles a rendre lisibles:', ...intent.movingPartsFocus.map((item) => `- ${item}`)]
              : []),
            ...(intent.anchoredPartsFocus.length > 0
              ? ['Sous-ensembles fixes ou ancrages a garder stables:', ...intent.anchoredPartsFocus.map((item) => `- ${item}`)]
              : []),
            ...(intent.needsResearch && intent.researchQueries.length > 0
              ? ['Recherche technique prioritaire:', ...intent.researchQueries.slice(0, 3).map((item) => `- ${item}`)]
              : []),
            ...(intent.motionRisks.length > 0
              ? ['Risques a respecter:', ...intent.motionRisks.slice(0, 2).map((item) => `- ${item}`)]
              : []),
          ].join('\n')
          if (activeMotionPreset) {
            historyPrompt = `${historyPrompt}\n\nPreset action/mouvement: ${activeMotionPreset.label}`
          }

          // Inject product/subject knowledge BEFORE distillation so FLUX knows what the subject IS
          // Without this, the distillation LLM has no idea what a "Strimer" or specific product looks like
          // and FLUX defaults to the manufacturer's most common product (e.g. PC case instead of cable)
          const productKnowledge = intent.referencePromptAdditions.filter((line) =>
            /^(THIS IS NOT|Visual description:|DO NOT generate|Generate ONLY|The .+ is a)/i.test(line),
          )
          if (productKnowledge.length > 0) {
            workingPrompt = [
              workingPrompt,
              '',
              'CRITICAL PRODUCT/SUBJECT IDENTITY (must be preserved in generation):',
              ...productKnowledge.map((line) => `- ${line}`),
            ].join('\n')
          }

          // Inject motion preset as a strong directive, not just a note
          if (activeMotionPreset) {
            workingPrompt = [
              workingPrompt,
              '',
              'ACTIVE MOTION/POSE DIRECTIVE (must be faithfully rendered):',
              `- Preset: ${activeMotionPreset.label}`,
              `- MANDATORY: ${activeMotionPreset.promptDirective}`,
              '- The generated reference MUST show the subject in this exact pose/motion state',
            ].join('\n')
          }

          // UN MOUVEMENT NOMME NE SE DEMANDE PAS A L'UTILISATEUR — on se
          // renseigne. "un guerrier qui fait le 6-7" declenchait une question
          // ("que veut dire 6-7 ?") alors que le resolveur (LLM + Wikipedia)
          // sait repondre seul. On le consulte pendant l'analyse; s'il
          // comprend, la biomecanique est injectee et AUCUNE question n'est
          // posee. S'il ne comprend pas, la question reste (en francais).
          let clarificationDejaResolue = false
          const nomDeMouvementRx = /\b(?:fais|refais|danse|execute|ex[ée]cute|fait)\s+(?:le|la|l'|un|une)\s*[\w\d]|\b(?:trend|tendance|meme|m[eè]me|d[ée]fi|challenge)\b/i
          // DES QU'un mouvement nomme est present — pas seulement quand le 1er
          // classifieur veut une question: le 2e (taskIntelligence) posait la
          // sienne ("pose statique nommee 6-7 ?") sans que le resolveur n'ait
          // jamais tourne. Avec la memoire des mouvements appris, ce passage
          // est instantane pour un mouvement deja connu.
          if (nomDeMouvementRx.test(workingPrompt)) {
            setPhase('Analyse — mouvement nommé détecté...', 8)
            try {
              const wsp = await getWorkspacePath()
              const trOut = await runPythonScript(`${wsp}/python-services/motion_trend_resolver.py`, ['--prompt', workingPrompt])
              const trLine = trOut.split('\n').map((l) => l.trim()).filter((l) => l.startsWith('{')).pop()
              const tr = trLine ? JSON.parse(trLine) as { named_move?: boolean; name?: string; description_en?: string; source?: string } : null
              if (tr?.named_move && tr.description_en) {
                workingPrompt = `${workingPrompt}\n\nMouvement nomme "${tr.name}" compris (${tr.source}): ${tr.description_en}`
                historyPrompt = `${historyPrompt}\n\nMouvement compris: ${tr.name}`
                clarificationDejaResolue = true
                setPhase(`Analyse — mouvement "${tr.name}" compris`, 10)
              }
            } catch { /* resolveur indisponible -> la question sera posee */ }
          }
          if (!clarificationDejaResolue && !aUneImage && intent.needsClarification && intent.clarificationQuestion) {
            setPhase('Analyse — clarification nécessaire', 12)
            // v77zh: surface the categorised options as quick-pick buttons so
            // the user clicks instead of typing — character anatomy, mechanism
            // motion, vehicle motion, material ambiguous, person reproduction
            // all carry concrete option strings the v77zg detector built.
            // La question est affichee PAR l'ecran de generation (surface
            // unique, opaque, clics verrouilles). L'ancienne modale empilee
            // etait illisible par transparence et laissait passer les clics
            // vers l'interface en dessous. Repli sur la modale si l'ecran de
            // generation est desactive.
            const viaFx1 = fxAsk<string | null>('3d', {
              id: `clar1-${Date.now()}`,
              kind: 'question',
              question: intent.clarificationQuestion!,
              options: intent.clarificationOptions.length > 0 ? intent.clarificationOptions : undefined,
              categoryLabel: intent.clarificationCategory ?? undefined,
              allowText: true,
            })
            const userAnswer = viaFx1 !== null ? await viaFx1 : await new Promise<string | null>((resolve) => setClarification({
              question: intent.clarificationQuestion!,
              options: intent.clarificationOptions.length > 0 ? intent.clarificationOptions : undefined,
              categoryLabel: intent.clarificationCategory ?? undefined,
              onRespond: resolve,
            }))
            setClarification(null)
            if (userAnswer) { workingPrompt = `${workingPrompt}\n\nPrecision 3D utilisateur: ${userAnswer}`; historyPrompt = `${historyPrompt}\n\nPrecision: ${userAnswer}` }
          }
          const workspacePath = await getWorkspacePath()
          const runId = `juan_bike_${Date.now()}`
          const active3dSession = useModuleHistoryStore.getState().getActiveSession('3d')
          const runPaths = buildThreeDRunOutputPaths(workspacePath, active3dSession, runId, prompt)
          const outputDir = runPaths.models
          await Promise.all([
            fsMkdir(runPaths.conversationDir),
            fsMkdir(runPaths.root),
            fsMkdir(runPaths.references),
            fsMkdir(runPaths.prompts),
            fsMkdir(runPaths.models),
            fsMkdir(runPaths.motion),
            fsMkdir(runPaths.audits),
            fsMkdir(runPaths.work),
            fsMkdir(runPaths.rescue),
          ])
          await fsWriteBinary(
            `${runPaths.prompts}/${runId}_prompt.txt`,
            utf8Bytes([
              `session_id=${active3dSession.id}`,
              `session_title=${active3dSession.title}`,
              `run_id=${runId}`,
              '',
              currentPrompt,
            ].join('\n')),
          )
          await fsWriteBinary(
            `${runPaths.audits}/manifest.json`,
            utf8Bytes(JSON.stringify({
              schema: 'aurora.3d.output_manifest.v1',
              session_id: active3dSession.id,
              session_title: active3dSession.title,
              run_id: runId,
              prompt: currentPrompt,
              directories: {
                references: runPaths.references,
                prompts: runPaths.prompts,
                models: runPaths.models,
                motion: runPaths.motion,
                audits: runPaths.audits,
                work: runPaths.work,
                rescue: runPaths.rescue,
              },
              created_at: new Date().toISOString(),
            }, null, 2)),
          )
          let referenceImagePath = `${runPaths.references}/${runId}_reference.png`
          const taskContext = await prepareTaskIntelligence({ module: '3d', prompt: workingPrompt, model: visionModel, files: preparedContext, setPhase, phaseBase: 5, phaseSpan: 10 })
          if (!clarificationDejaResolue && !aUneImage && taskContext.clarificationQuestion) {
            setPhase('Analyse — clarification utilisateur', 12)
            const viaFx2 = fxAsk<string | null>('3d', {
              id: `clar2-${Date.now()}`,
              kind: 'question',
              question: taskContext.clarificationQuestion!,
              allowText: true,
            })
            const userAnswer = viaFx2 !== null ? await viaFx2 : await new Promise<string | null>((resolve) => setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve, onAttachImage: (f) => setContextFiles((prev) => [...prev, f]) }))
            setClarification(null)
            if (userAnswer) { taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nPrecision utilisateur: ${userAnswer}`; taskContext.generationPrompt = `${taskContext.generationPrompt}\n\nUser clarification: ${userAnswer}`; historyPrompt = `${historyPrompt}\n\nPrecision: ${userAnswer}` }
          }
          const referenceSupportPlan = await prepareThreeDReferenceSupport({
            prompt: currentPrompt,
            intent,
            model: visionModel,
            researchContext: taskContext.researchContext,
            webSearchTerms: taskContext.analysis.webSearchTerms,
            requestedChanges: taskContext.generationContract.requestedChanges,
          })
          setReferenceSupport(referenceSupportPlan)
          // If user uploaded a single image without filename view tag, detect which view it is
          // so the planner can assign complementary views correctly
          const preparedImages = preparedContext.filter((f) => f.kind === 'image' && f.stagedPath)
          // TA PHOTO EST LA LOI (30/07): l'utilisateur a fourni un chat ailé,
          // la chaine a livre une femme issue d'une recherche web. Toute photo
          // utilisateur unique EST la face; la detection d'angle n'a le droit
          // de renommer que s'il y a PLUSIEURS photos a repartir.
          // 31/07: la detection VLM renommait une photo en « droite » alors
          // que c'etait la MEME image — vues fantomes. Plus AUCUN renommage
          // automatique: nom explicite (face/dos/...) sinon l'ordre (1=face,
          // 2=dos, 3=gauche, 4=droite), affiche a l'utilisateur.
          // (bloc de detection d'angle supprime — l'ordre des fichiers fait foi)

          // ── Analyze the real reference image so every downstream stage
          // (view planner, FLUX directives, correction loop) shares the same
          // palette / text / entity focus extracted from what the user uploaded
          // (or from the most faithful external reference if none was supplied).
          setPhase('Référence photo — analyse de la référence visuelle...', 18)
          let referenceAnalysisResult: VisualReferenceAnalysis | null = null
          try {
            let analysisBlob: Blob | null = null
            if (preparedImages[0]?.stagedPath) {
              const bytes = await fsReadBinary(preparedImages[0].stagedPath)
              analysisBlob = new Blob([new Uint8Array(bytes)], { type: 'image/png' })
            } else if (referenceSupportPlan.externalReference?.blob) {
              analysisBlob = referenceSupportPlan.externalReference.blob
            }
            if (analysisBlob) {
              referenceAnalysisResult = await analyzeReferenceImage({
                blob: analysisBlob,
                model: visionModel,
                prompt: currentPrompt,
                userRequestedSubject: referenceSupportPlan.searchProfile.subjectLabel,
              })
            }
          } catch { /* analyzer is best-effort; planner falls back to default */ }
          setReferenceAnalysis(referenceAnalysisResult)

          const promptColorOverrides = parseColorOverridesFromPrompt(currentPrompt)
          const effectiveOverrides = [...promptColorOverrides, ...manualColorOverrides]
          const mergedPalette = mergePaletteWithOverrides(
            referenceAnalysisResult?.palette || [],
            effectiveOverrides,
          )
          const focusIndexForPlan = focusEntityIndexOverride !== null
            ? focusEntityIndexOverride
            : referenceAnalysisResult?.dominantEntityIndex ?? -1

          // Gather structural facts from both the web research and the
          // reference-support search profile so each FLUX view directive is
          // grounded in the product's real spec, not just the user's photo.
          const researchAnchors: string[] = []
          const dimensionNotes = referenceSupportPlan.dimensionNotes || []
          if (dimensionNotes.length > 0) researchAnchors.push(...dimensionNotes.slice(0, 3))
          const requiredElements = referenceSupportPlan.searchProfile?.requiredElements || []
          if (requiredElements.length > 0) researchAnchors.push(...requiredElements.slice(0, 4))
          const researchContext = taskContext.researchContext || ''
          if (researchContext) {
            const bullets = researchContext
              .split(/\n|•|·|- /)
              .map((line) => line.trim())
              .filter((line) => line.length > 12 && line.length < 180)
              .slice(0, 4)
            researchAnchors.push(...bullets)
          }

          // Detail-focus zones that must survive the mesh reconstruction — the
          // analyzer's visible text labels and entity descriptions are high-
          // signal hints about where fine geometry lives (screens, logos,
          // connector blocks, fan hubs).
          const detailFocusZones: string[] = []
          if (referenceAnalysisResult) {
            for (const entry of referenceAnalysisResult.visibleText.slice(0, 4)) {
              detailFocusZones.push(`"${entry.text}" logo/text at ${entry.location || 'its natural spot'}`)
            }
            const focusEntity = focusIndexForPlan >= 0
              ? referenceAnalysisResult.entities[focusIndexForPlan]
              : undefined
            if (focusEntity?.description) {
              const micro = focusEntity.description.match(/(screen|display|oled|lcd|logo|vent|fan|blade|connector|port|usb|header|pin|button|wheel|knob|cap)[^.,;\n]{0,40}/gi)
              if (micro) detailFocusZones.push(...micro.map((m) => m.trim()).slice(0, 4))
            }
          }

          const overlayForPlanner: ThreeDViewOverlay = {
            palette: mergedPalette,
            visibleText: referenceAnalysisResult?.visibleText,
            entities: referenceAnalysisResult?.entities,
            focusEntityIndex: focusIndexForPlan,
            colorPromptNote: effectiveOverrides
              .map((o) => `${o.zone} ${o.hex}`)
              .join(', '),
            researchAnchors: Array.from(new Set(researchAnchors)).slice(0, 6),
            detailFocusZones: Array.from(new Set(detailFocusZones)).slice(0, 6),
          }

          if (aUneImage && preparedImages.length === 0) {
            // La piece jointe est une image mais le staging a echoue: on
            // REFUSE de continuer (la suite fabriquerait une reference
            // inventee — deja paye: portrait web livre a la place du sujet).
            throw new Error(`Votre photo n'a pas pu etre preparee (${contextFiles.map((f) => f.name).join(', ')}). Rejoignez-la et relancez.`)
          }
          if (preparedImages.length > 0) {
            setProgress(`Photo utilisateur = reference (${preparedImages.map((f) => f.name).join(', ')})`)
          }
          const referenceViewPlan = await prepareThreeDViewPlan({
            prompt: currentPrompt,
            intent,
            model: visionModel,
            researchContext: taskContext.researchContext,
            referenceSupport: referenceSupportPlan,
            preparedContext,
            enrichedDescription: taskContext.generationPrompt,
            overlay: overlayForPlanner,
          })
          setViewPlan(referenceViewPlan)

          // Build a FLUX-native visual description directly, bypassing the weak distillation
          // This is the AUTHORITATIVE prompt that FLUX will actually render
          setPhase('Référence photo — construction du prompt visuel FLUX...', 20)
          const fluxVisualPrompt = await buildFluxVisualDescription({
            prompt: currentPrompt,
            intent,
            model: visionModel,
            motionPreset: activeMotionPreset,
            researchContext: taskContext.researchContext,
          })
          // Override the distilled prompt with the direct FLUX-native description
          taskContext.generationPrompt = fluxVisualPrompt

          pushMessage('3d', { role: 'user', content: historyPrompt })
          const comfyuiPath = runtimeServices.comfyui.path

          // Autonomous synthetic view generation + per-view verification
          // — SAUF quand l'utilisateur a fourni sa photo (30/07): les vues
          // FLUX derivees du TEXTE perdaient les ailes et transformaient la
          // queue en patte (verifie sur le run happy.jpg). L'identite vient
          // de la photo: c'est MV-Adapter (image -> multivues), dans le
          // pipeline Python, qui derive les autres angles a partir d'ELLE.
          const hasSyntheticViews = preparedImages.length === 0
            && referenceViewPlan.assignments.some((a) => a.sourceKind === 'synthetic')
          let resolvedViewPlan = referenceViewPlan
          if (hasSyntheticViews) {
            setProgress('Generation autonome des vues individuelles...')
            setPhase('Référence photo — génération des vues FLUX...', 22)
            const baseSyntheticWorkflow = resolveReferenceWorkflow(intent, hardware, false, currentPrompt, referenceSupportPlan)
            // Push quality higher for synthetic multi-view — precision over speed
            const syntheticWorkflow = {
              ...baseSyntheticWorkflow,
              steps: baseSyntheticWorkflow.steps + 6,
            }

            // Find or generate the front view FIRST for cross-view consistency seeding
            const existingFrontAssignment = referenceViewPlan.assignments.find((a) => a.view === 'front' && a.sourceKind !== 'synthetic')
            const syntheticFrontAssignment = referenceViewPlan.assignments.find((a) => a.view === 'front' && a.sourceKind === 'synthetic')
            let frontSeedFilename: string | null = null

            if (existingFrontAssignment?.file?.stagedPath) {
              frontSeedFilename = existingFrontAssignment.file.stagedPath.split('/').pop() || null
            } else if (existingFrontAssignment?.externalReference) {
              const frontBlob = existingFrontAssignment.externalReference.blob
              const frontPath = `${runPaths.references}/${runId}_front_seed.png`
              await fsWriteBinary(frontPath, Array.from(new Uint8Array(await frontBlob.arrayBuffer())))
              frontSeedFilename = `${runId}_front_seed.png`
            } else if (syntheticFrontAssignment) {
              // Front view is also synthetic — generate it FIRST without seed so it becomes the consistency anchor
              setPhase('Référence photo — génération de la vue front ancre...', 24)
              const frontDirective = getSyntheticViewDirective(syntheticFrontAssignment)
              if (frontDirective) try {
                const frontBlob = await generateSyntheticView(
                  frontDirective,
                  syntheticWorkflow.style,
                  syntheticWorkflow.width,
                  syntheticWorkflow.height,
                  syntheticWorkflow.steps + 4,  // More steps for the anchor view
                  `${runId}_front_synth`,
                  null,  // No seed for front — it IS the anchor
                  ensureComfy,
                  { ollamaModelsToEvict: Array.from(new Set([visionModel, AUXILIARY_ANALYSIS_MODEL])) },
                )
                // Stage the front view for seeding other views
                const frontPath = `${runPaths.references}/${runId}_front_synth_seed.png`
                await fsWriteBinary(frontPath, Array.from(new Uint8Array(await frontBlob.arrayBuffer())))
                frontSeedFilename = `${runId}_front_synth_seed.png`

                // Mark front as resolved so generateAndVerifySyntheticViews skips it
                const frontIdx = referenceViewPlan.assignments.findIndex((a) => a.view === 'front')
                if (frontIdx >= 0) {
                  referenceViewPlan.assignments[frontIdx] = {
                    ...syntheticFrontAssignment,
                    resolvedBlob: frontBlob,
                    notes: [...syntheticFrontAssignment.notes, 'vue front generee comme ancre de coherence (sans seed)'],
                  }
                }
              } catch (ancreErr) {
                // NON FATAL: sans ancre, les vues partent sans graine (moins
                // coherentes) et, au pire, le pipeline genere SA reference.
                console.error('[3D] ancre synthetique impossible:', ancreErr)
                setProgress('Ancre de coherence indisponible — on continue sans graine...')
              }
            }

            const verifiedAssignments = await generateAndVerifySyntheticViews({
              plan: referenceViewPlan,
              intent,
              referenceSupport: referenceSupportPlan,
              prompt: currentPrompt,
              model: visionModel,
              style: syntheticWorkflow.style,
              width: syntheticWorkflow.width,
              height: syntheticWorkflow.height,
              steps: syntheticWorkflow.steps,
              runId,
              outputDir: runPaths.references,
              frontSeedFilename,
              setPhase,
              ensureComfy,
              vramGuard: { ollamaModelsToEvict: Array.from(new Set([visionModel, AUXILIARY_ANALYSIS_MODEL])) },
            })

            resolvedViewPlan = { ...referenceViewPlan, assignments: verifiedAssignments }
            setViewPlan(resolvedViewPlan)

            // Collect verification summaries
            const verifications = verifiedAssignments.filter((a) => a.verification)
            const passedViews = verifications.filter((a) => a.verification?.passed)
            const failedViews = verifications.filter((a) => !a.verification?.passed)
            if (verifications.length > 0) {
              setProgress(`Verification vues: ${passedViews.length} OK, ${failedViews.length} partielles`)
            }
          }

          const materializedViewPlan = await materializeViewPlan(resolvedViewPlan, runPaths.references, runId)
          const directMultiView = resolvedViewPlan.shouldUseMultiview && materializedViewPlan.assignments.length >= 2 && Boolean(materializedViewPlan.primaryPath)
          // detect a real-world dimension hint in the prompt so the FIRST mesh
          // ships at the requested size — no Sauvetage click required. Applied
          // as a post-process after generation (see dimensionHintForGen usage below).
          const dimensionHintForGen = (await import('../services/meshPostprocess')).parsePromptDimension(currentPrompt || '')
          // enforce bilateral symmetry on the YZ plane for character /
          // creature / body_part subjects. Closes the Meshy gap where left/
          // right shoulder height, ear size or facial features drift slightly.
          const wantsSymmetryEnforced = (
            intent.wantsSymmetry
            && (intent.subjectKind === 'character' || intent.subjectKind === 'creature' || intent.subjectKind === 'body_part')
          )
          const multiviewSummary = directMultiView
            ? `${materializedViewPlan.summary}${resolvedViewPlan.inferredFromOrder ? ' (ordre des vues inferes depuis les fichiers joints)' : ''}`
            : null
          let referenceSeedForWorkflow = Boolean(primaryPreparedImage?.stagedPath)
          let referenceVerificationSummary = ''
          // Recapitulatif de scene (entites / assemblage / manques) affiche
          // dans le message — vide si la demande n'etait pas une scene.
          let sceneReport = ''
          // 27/09 (retour Juan: « y a pas de multi-entite ... pas de scene »):
          // la reference passee au pipeline via --image n'est une VRAIE photo
          // que si l'utilisateur a TELECHARGE un fichier. Tout le reste (FLUX
          // synthetise depuis le texte, reference de session, reference web
          // externe, lot multi-vues) est une image de SYNTHESE qui ne montre
          // qu'un seul objet alors que le texte peut en demander plusieurs.
          // Le backend bloquait la scene multi-objets sur TOUTE presence
          // d'image : depuis l'UI la scene etait donc toujours coupee. On ne
          // marque `--synthetic-reference` que dans ce cas-la, pour ne jamais
          // laisser une photo utilisateur debiter en plusieurs sujets.
          const referenceIsUserPhoto = Boolean(primaryPreparedImage?.stagedPath)

          if (directMultiView && materializedViewPlan.primaryPath) {
            referenceImagePath = materializedViewPlan.primaryPath
            lastReferenceImagePathRef.current = referenceImagePath
            setReferenceImageUrl(toAssetUrl(referenceImagePath))
            setProgress(`Mode multivue autonome actif (${materializedViewPlan.summary})...`)
            setPhase('Référence photo — multi-vues prêtes pour reconstruction...', 35)
            const allRefs = materializedViewPlan.assignments.map((a) => ({
              url: toAssetUrl(a.path),
              role: a.view === 'front' ? 'face' : a.view === 'right' ? 'droite' : a.view === 'left' ? 'gauche' : 'dos',
            }))
            emitGenerationFx('3d', { active: true, phase: 'Référence photo — multi-vues prêtes', refs: allRefs })
            referenceSeedForWorkflow = true
            referenceVerificationSummary = `Reference multivue directe retenue: ${materializedViewPlan.summary}.`
          } else {
            const autoReusePath = !primaryPreparedImage?.stagedPath && EDIT_INTENT.test(currentPrompt) ? lastReferenceImagePathRef.current : null
            let referenceSeedOrigin: ReferenceSeedOrigin = primaryPreparedImage?.stagedPath ? 'user' : null
            let referenceSeed: { stagedPath: string; filename: string } | null = primaryPreparedImage?.stagedPath ? { stagedPath: primaryPreparedImage.stagedPath, filename: primaryPreparedImage.name } : null
            if (!referenceSeed && autoReusePath && comfyuiPath) {
              referenceSeed = await stageExistingReference(autoReusePath, comfyuiPath, `${runId}_resume_ref.png`)
              referenceSeedOrigin = 'session'
            }
            if (!referenceSeed && referenceSupportPlan.externalReference && comfyuiPath) {
              setProgress('Reference externe retenue pour fiabiliser la vue 3D...')
              setPhase('Reference externe retenue pour fiabiliser la vue 3D...', 60)
              const stagedExternal = await stageBlobToComfyInput(referenceSupportPlan.externalReference.blob, comfyuiPath, `${runId}_external_ref`)
              referenceSeed = { stagedPath: stagedExternal.absolutePath, filename: stagedExternal.filename }
              referenceSeedOrigin = 'external'
            }
            referenceSeedForWorkflow = Boolean(referenceSeed)
            // 30/07 (audit): un preset de pose ou un mot d'edition
            // (« ajoute une epee ») envoyait la reference en regeneration
            // FLUX TEXTE pure — l'identite de la photo etait reinventee.
            // Origine 'user' = la photo est intouchable; la pose et les
            // modifications se font en aval (MV-Adapter / mesh), pas en
            // reecrivant la reference.
            const shouldRegenerateReference = referenceSeedOrigin !== 'user'
              && (!referenceSeed || EDIT_INTENT.test(currentPrompt) || shouldRefineReferenceSeed(intent, activeMotionPreset, referenceSupportPlan, Boolean(referenceSeed), referenceSeedOrigin, currentPrompt))
            if (!shouldRegenerateReference && referenceSeed) {
              if (referenceSupportPlan.externalReference && referenceSeedOrigin !== 'user') {
                await fsWriteBinary(referenceImagePath, Array.from(new Uint8Array(await referenceSupportPlan.externalReference.blob.arrayBuffer())))
                referenceVerificationSummary = `Reference externe conservee telle quelle (${referenceSupportPlan.externalReference.score}/100).`
              } else {
                referenceImagePath = referenceSeed.stagedPath
                referenceVerificationSummary = referenceSeedOrigin === 'user'
                  ? 'Reference utilisateur prioritaire, sans regeneration.'
                  : 'Reference de session reutilisee sans regeneration.'
              }
              lastReferenceImagePathRef.current = referenceImagePath
              setReferenceImageUrl(toAssetUrl(referenceImagePath))
              setProgress('Reference 3D fiable retenue, preparation de la reconstruction...')
              setPhase('Référence photo — référence visuelle retenue...', 35)
              emitGenerationFx('3d', { active: true, phase: 'Référence photo — référence visuelle retenue', refs: [{ url: toAssetUrl(referenceImagePath), role: 'face' }] })
            } else try {
              setProgress(referenceSeed ? 'Refinement de la reference 3D...' : 'Generation de la reference image...')
              setPhase(referenceSeed ? 'Référence photo — raffinement de la vue...' : 'Référence photo — génération de la vue...', 25)
              const referenceWorkflow = resolveReferenceWorkflow(intent, hardware, Boolean(referenceSeed), currentPrompt, referenceSupportPlan)
              const baseReferencePrompt = buildReferencePrompt(taskContext.generationPrompt, intent, activeMotionPreset, referenceSupportPlan, referenceViewPlan, currentPrompt)
              const renderReferenceBlob = async (promptText: string, stepsOverride = referenceWorkflow.steps, label = 'Rendu de la reference en cours...') => {
                const workflow = createFlux2Workflow({
                  prompt: promptText,
                  width: referenceWorkflow.width,
                  height: referenceWorkflow.height,
                  steps: stepsOverride,
                  filenamePrefix: 'juan_bike_3d_ref',
                })
                return runReferenceWorkflow({
                  workflow,
                  setPhase,
                  pollRef,
                  phaseStart: 25,
                  label,
                  ensureComfy,
                  vramGuard: { ollamaModelsToEvict: Array.from(new Set([visionModel, AUXILIARY_ANALYSIS_MODEL])) },
                })
              }
              renderRefBlobRef.current = renderReferenceBlob
              baseRefPromptRef.current = baseReferencePrompt

              let imageBlob = await renderReferenceBlob(baseReferencePrompt)
              let referenceAssessment = await verifyGeneratedReferenceVisual({
                prompt: currentPrompt,
                model: visionModel,
                blob: imageBlob,
                profile: referenceSupportPlan.searchProfile,
                label: referenceSupportPlan.searchProfile.subjectLabel || 'Generated 3D reference',
              })
              const minimumReferenceScore = resolveReferenceMinimumScore(referenceSupportPlan)
              const isReferenceAccepted = (assessment: Awaited<ReturnType<typeof verifyGeneratedReferenceVisual>> | null) => Boolean(
                assessment?.usable
                && assessment.exactEnough
                && !assessment.pixelated
                && !assessment.cluttered
                && !assessment.wrongSubject
                && assessment.score >= minimumReferenceScore
              )

              if (!isReferenceAccepted(referenceAssessment)) {
                setProgress('Auto-correction de la reference 3D (tentative 1)...')
                setPhase('Référence photo — auto-correction de la vue (tentative 1)...', 30)
                const correctionPrompt = buildReferenceCorrectionPrompt(
                  baseReferencePrompt,
                  intent,
                  referenceSupportPlan,
                  referenceAssessment?.notes || 'subject drift or parasite context',
                )
                imageBlob = await renderReferenceBlob(correctionPrompt, referenceWorkflow.steps + 4, 'Rendu correctif de la reference...')
                referenceAssessment = await verifyGeneratedReferenceVisual({
                  prompt: currentPrompt,
                  model: visionModel,
                  blob: imageBlob,
                  profile: referenceSupportPlan.searchProfile,
                  label: `${referenceSupportPlan.searchProfile.subjectLabel || 'Generated 3D reference'} corrected`,
                })
              }

              // Third attempt: if subject is STILL wrong, use the direct FLUX visual description
              // (bypasses the distilled prompt entirely and uses pure product knowledge)
              if (!isReferenceAccepted(referenceAssessment) && (referenceAssessment?.wrongSubject || (referenceAssessment?.score ?? 0) < 40)) {
                setProgress('Sujet incorrect detecte - regeneration avec connaissance produit directe...')
                setPhase('Référence photo — régénération avec identité forcée...', 32)
                // Build a raw prompt from the FLUX visual description + strict correction
                const rawVisualPrompt = [
                  fluxVisualPrompt,
                  '',
                  'CRITICAL CORRECTION: The previous generation showed THE WRONG SUBJECT.',
                  `The user asked for: ${referenceSupportPlan.searchProfile.subjectLabel || currentPrompt}`,
                  `But got: ${referenceAssessment?.notes || 'a completely different object'}`,
                  'Generate EXACTLY the correct subject this time. Not a similar product, not the same brand\'s other product.',
                  ...intent.referencePromptAdditions.filter((l) => /^(THIS IS NOT|Visual description:|DO NOT generate)/i.test(l)).map((l) => `- ${l}`),
                ].filter(Boolean).join('\n')
                imageBlob = await renderReferenceBlob(rawVisualPrompt, referenceWorkflow.steps + 8, 'Regeneration avec identite forcee...')
                referenceAssessment = await verifyGeneratedReferenceVisual({
                  prompt: currentPrompt,
                  model: visionModel,
                  blob: imageBlob,
                  profile: referenceSupportPlan.searchProfile,
                  label: `${referenceSupportPlan.searchProfile.subjectLabel || 'Generated 3D reference'} product-guided`,
                })
              }

              if (!isReferenceAccepted(referenceAssessment) && referenceSupportPlan.externalReference && referenceSupportPlan.searchProfile.strictIdentity) {
                imageBlob = referenceSupportPlan.externalReference.blob
                referenceVerificationSummary = `Reference auto rejetee (${referenceAssessment?.notes || 'hors sujet'}). Fallback sur la reference externe stricte ${referenceSupportPlan.externalReference.title} (${referenceSupportPlan.externalReference.score}/100).`
                setProgress('Fallback vers la reference externe la plus fidele...')
                setPhase('Référence photo — fallback référence externe...', 35)
              } else {
                referenceVerificationSummary = referenceAssessment
                  ? `Verification reference: ${referenceAssessment.score}/100 - ${referenceAssessment.notes}`
                  : 'Verification reference indisponible.'
              }

              if (!isReferenceAccepted(referenceAssessment) && !(referenceSupportPlan.externalReference && referenceSupportPlan.searchProfile.strictIdentity)) {
                // v77zaq: hard mismatch should ONLY block when the SUBJECT itself
                // is wrong, never when only materials/colors drifted. Fantasy
                // prompts ("quartz body + obsidian panel + rose gold lotus
                // fans") routinely fail material checks but the subject (PC
                // case) is correctly rendered — reconstruction can still proceed
                // because Hunyuan3D shape doesn't depend on FLUX colors and the
                // texture pass + viewer's PbrProfile inference will recolor.
                const wrongSubject = Boolean(referenceAssessment?.wrongSubject)
                const hardMismatch = wrongSubject && (
                  referenceSupportPlan.searchProfile.strictIdentity
                  || isCharacterLike(intent)
                  || (intent.systemClass === 'pc_cabling' && intent.referenceFraming === 'isolated_subject')
                )
                if (hardMismatch) {
                  throw new Error(`La reference 3D reste insuffisamment fidele apres auto-correction: ${referenceAssessment?.notes || 'mauvais sujet ou trop de parasites'}`)
                }
                if (!wrongSubject) {
                  // Subject correct, only material/color drift — proceed with
                  // best-of attempts and let the texture pass / viewer correct.
                  referenceVerificationSummary = `${referenceVerificationSummary} (materiaux a affiner cote texture, sujet OK)`
                }
              }

              await fsWriteBinary(referenceImagePath, Array.from(new Uint8Array(await imageBlob.arrayBuffer())))
              lastReferenceImagePathRef.current = referenceImagePath
              setReferenceImageUrl(toAssetUrl(referenceImagePath))
              emitGenerationFx('3d', { active: true, phase: 'Référence photo — vue front prête', refs: [{ url: toAssetUrl(referenceImagePath), role: 'face' }] })
            } catch (refErr) {
              // ECHEC NON FATAL. Un 400 ComfyUI ici (mauvais graphe, modele
              // absent, service down) ne doit PAS tuer la generation.
              // Si une reference externe web a ete trouvee, on la sauvegarde directement !
              console.error('[3D] reference UI impossible, repli gracieux:', refErr)
              if (referenceSupportPlan.externalReference?.blob) {
                try {
                  await fsWriteBinary(referenceImagePath, Array.from(new Uint8Array(await referenceSupportPlan.externalReference.blob.arrayBuffer())))
                  lastReferenceImagePathRef.current = referenceImagePath
                  setReferenceImageUrl(toAssetUrl(referenceImagePath))
                  setProgress('Reference externe web conservee (repli direct sans FLUX)...')
                } catch { /* best effort */ }
              } else if (materializedViewPlan.primaryPath && await fsExists(materializedViewPlan.primaryPath)) {
                referenceImagePath = materializedViewPlan.primaryPath
                lastReferenceImagePathRef.current = referenceImagePath
                setReferenceImageUrl(toAssetUrl(referenceImagePath))
              }
              setProgress('Reference UI indisponible — le pipeline generera sa propre reference...')
              setPhase('Reference deleguee au pipeline (echec du rendu UI non bloquant)...', 66)
            }
          }
          const referenceWorkflow = resolveReferenceWorkflow(intent, hardware, referenceSeedForWorkflow, currentPrompt, referenceSupportPlan)
          const activePipeline = intent.pipelineRouting.pipeline

          // ── VALIDATION DE LA REFERENCE (vert/rouge) ──
          // Elle se fait desormais DANS le pipeline Aurora (--confirm-ref): le
          // pipeline s'arrete sur SA reference (la vraie entree de la reconstruction)
          // puis sur le LOT de vues derivees, emet PROGRESS:confirm_req:<request.json>
          // et attend la reponse. L'UI repond via l'overlay (voir onPythonProgress).
          // On ne valide plus ici une image que le backend n'utilise pas — une seule
          // demande, sur la bonne image, et le lot en une fois (pas du 1 par 1).

          // ── PIPELINE ROUTING: choose the best generation backend ──
          unlistenRef.current?.()
          unlistenRef.current = await onPythonProgress((message) => {
            if (!message.startsWith('PROGRESS:')) return
            const parts = message.split(':')
            const stage = parts[1] || 'run'
            if (stage === 'confirm_req') {
              // Le pipeline attend une validation vert/rouge (reference ou lot de
              // vues derivees). On lit la demande, on ouvre l'overlay, on ecrit la
              // reponse ({accepted, reason}) la ou le pipeline la poll.
              const reqPath = parts.slice(2).join(':').trim()
              if (reqPath) {
                void (async () => {
                  let beatTimer: number | undefined
                  try {
                    const raw = await fsReadBinary(reqPath)
                    const req = JSON.parse(new TextDecoder().decode(new Uint8Array(raw))) as { title?: string; images?: string[]; answer_path?: string; nonce?: string; alive_path?: string; mode?: string }
                    if (!req.answer_path || !Array.isArray(req.images) || req.images.length === 0) return
                    // Le pipeline REUTILISE le meme chemin a chaque nouvelle tentative
                    // (3 essais de photo, 3 essais de lot). Dedoublonner sur le chemin
                    // faisait ignorer en silence tout ce qui suivait la 1re demande.
                    // On dedoublonne sur le nonce: unique a chaque demande.
                    const key = `${reqPath}#${req.nonce || ''}`
                    if (confirmReqHandledRef.current.has(key)) return
                    confirmReqHandledRef.current.add(key)
                    // Battement de coeur: tant que la fenetre est ouverte devant
                    // l'utilisateur, le pipeline n'expire pas (sinon il acceptait
                    // tout seul au bout de 10 min et remplacait la photo sans reponse).
                    const alivePath = req.alive_path
                    if (alivePath) {
                      const beat = () => { void fsWriteBinary(alivePath, utf8Bytes(String(Date.now()))).catch(() => {}) }
                      beat()
                      beatTimer = window.setInterval(beat, 10_000)
                    }
                    // Trois modes du pipeline:
                    //   tri   -> oui / non (supprime) / peut-etre (garde et repropose)
                    //   choix -> galerie des "peut-etre": cliquer une image, valider
                    //   lot   -> accepter/refuser un ensemble (historique)
                    const urls = req.images.map((p) => toAssetUrl(p) + `?r=${Date.now()}`)
                    const titre = req.title || 'Valider ces images ?'
                    let reponse: Record<string, unknown>
                    if (req.mode === 'choix') {
                      const viaPick = fxAsk<{ choix: number }>('3d', {
                        id: `pick-${Date.now()}`, kind: 'pick_image',
                        question: titre, images: urls,
                      })
                      // 30/07 (audit): ecran fx coupe => on choisissait
                      // silencieusement la premiere image. Repli sur la
                      // modale classique: l'utilisateur repond par le numero.
                      let pick = viaPick !== null ? await viaPick : null
                      if (pick === null) {
                        const rep = await new Promise<string | null>((resolve) => setClarification({
                          question: `${titre} — reponds par le numero de l'image (1 a ${urls.length}).`,
                          options: urls.map((_, i) => `Image ${i + 1}`),
                          onRespond: resolve,
                        }))
                        setClarification(null)
                        const n = parseInt((rep || '').replace(/\D+/g, ''), 10)
                        pick = { choix: Number.isFinite(n) && n >= 1 && n <= urls.length ? n - 1 : 0 }
                      }
                      reponse = { accepted: true, verdict: 'choix', choix: pick.choix }
                    } else {
                      const viaTri = fxAsk<{ accepted: boolean; reason?: string; verdict?: string }>('3d', {
                        id: `tri-${Date.now()}`, kind: 'confirm_images',
                        question: titre, images: urls, allowText: true,
                        allowMaybe: req.mode === 'tri',
                        allowPickEach: req.mode === 'lot' && urls.length > 2,
                        allowPhoto: req.mode === 'photo',
                      })
                      const dec = viaTri !== null ? await viaTri : await askReferenceConfirm(urls, titre)
                      reponse = { accepted: dec.accepted, reason: (dec.reason || '').trim(),
                                  verdict: (dec as { verdict?: string }).verdict
                                    ?? (dec.accepted ? 'oui' : 'non'),
                                  jetees: (dec as { jetees?: number[] }).jetees ?? [],
                                  photo: (dec as { photo?: string }).photo ?? null }
                    }
                    await fsWriteBinary(req.answer_path, utf8Bytes(JSON.stringify(reponse)))
                  } catch { /* sans reponse le pipeline continue apres expiration */ } finally {
                    if (beatTimer !== undefined) window.clearInterval(beatTimer)
                  }
                })()
              }
              setProgress('En attente de votre validation (vert = garder, rouge = regenerer)...')
              setPhase('Validation par vous — la photo acceptee sera gardee telle quelle', 87)
              setPhaseSnapshot({ label: 'En attente de votre validation...', percent: 87 })
              return
            }
            if (message.startsWith('PROGRESS:reference:source_web:')) {
              try {
                const webJson = JSON.parse(message.slice('PROGRESS:reference:source_web:'.length))
                setDiscoveredSourceWeb(webJson)
              } catch {}
            }
            const detail = parts.slice(2).join(':') || parts[1] || 'Execution Python en cours...'
            setProgress(detail)
            const phaseProgress = stage === 'install' ? 82 : stage === 'device' || stage === 'bg' || stage === 'asset_scan' ? 84 : stage === 'asset_download' || stage === 'shape_fallback' || stage === 'shape_load' ? 86 : stage === 'shape_run' || stage === 'gaussian' ? 90 : stage === 'texture_load' || stage === 'texture_run' || stage === 'texture_retry' || stage === 'texture_warn' || stage === 'mesh_extract' ? 92 : stage === 'export' || stage === 'export_fallback' ? 95 : stage === 'procedural' ? 88 : stage === 'sfm' || stage === 'photogrammetry' ? 87 : stage === 'validate' ? 94 : stage === 'rig' ? 93 : 88
            setPhase(detail, phaseProgress)
            // v77zag: keep a local snapshot for the live overlay so the user
            // sees the percent / detail / heartbeat regardless of runtime.
            setPhaseSnapshot({ label: detail, percent: phaseProgress })
          })

          let result: ModelGenerationResult | null = null

          if (activePipeline === 'procedural' && intent.pipelineRouting.proceduralTemplate) {
            // ── PROCEDURAL PIPELINE: Blender Python (mechanisms, cables) ──
            setProgress(`Modelisation procedurale Blender (${intent.pipelineRouting.proceduralTemplate})...`)
            setPhase('Sculpture 3D — modélisation procédurale dans Blender...', 45)
            const proceduralResult = await runProceduralModeling({
              template: intent.pipelineRouting.proceduralTemplate as Parameters<typeof runProceduralModeling>[0]['template'],
              prompt: currentPrompt,
              parameters: {},
              outputDir,
              runId,
              format: 'glb',
            })
            if (proceduralResult.ok && proceduralResult.outputPath) {
              const proceduralTextured = ['humanoid_performer', 'strimer_plus_v2_cable', 'led_strip_system', 'pulley_belt_system', 'motherboard_layout'].includes(intent.pipelineRouting.proceduralTemplate || '')
              result = { ok: true, path: proceduralResult.outputPath, format: proceduralResult.format as 'glb' | 'obj' || 'glb', shape_model: `Blender Procedural (${intent.pipelineRouting.proceduralTemplate})`, shape_runtime: 'blender_headless', shape_strategy: intent.pipelineRouting.proceduralTemplate, textured: proceduralTextured, fallback_used: false, pipeline: 'procedural', animationFrames: proceduralResult.animationFrames }
            } else {
              // Fallback to AI generation
              setProgress('Procedural echoue, fallback vers generation IA...')
              setPhase('Sculpture 3D — fallback vers génération IA...', 45)
            }
          }

          if (activePipeline === 'photogrammetry') {
            // ── PHOTOGRAMMETRY PIPELINE: Meshroom/AliceVision ──
            const imageFiles = preparedContext.filter((f) => f.kind === 'image').map((f) => f.stagedPath || f.name)
            if (imageFiles.length >= 3) {
              setProgress(`Photogrammetrie Meshroom (${imageFiles.length} images)...`)
              setPhase('Sculpture 3D — reconstruction photogrammétrique...', 45)
              const photoOutput = await runPythonScript(`${workspacePath}/python-services/meshroom_run.py`, ['--images', imageFiles[0].replace(/[^/\\]*$/, ''), '--output-dir', outputDir, '--run-id', runId, '--format', 'glb'], { resumeKey: 'model' })
              const photoResult = parseLastJsonLine(photoOutput)
              if (photoResult?.ok && photoResult.path) {
                result = { ...photoResult, pipeline: 'photogrammetry' } as ModelGenerationResult
              } else {
                setProgress('Photogrammetrie echouee, fallback vers generation IA...')
                setPhase('Sculpture 3D — fallback vers génération IA...', 45)
              }
            }
          }

          // ── AI GENERATION PIPELINE (default + fallback) ──
          let auroraAttempted = false
          let auroraFailReason = ''
          if (!result) {
            // Voie principale: pipeline Aurora complet (TRELLIS.2-4B natif MIT, branche
            // qualite native, materiaux par zones). DreamGaussian ne sert plus que de
            // repli si ce pipeline echoue.
            auroraAttempted = true
            let auroraWatch: number | undefined
            try {
              setProgress('Atlas construit en qualite maximale...')
              setPhase('Sculpture 3D — géométrie native et maillage...', 50)
              const genDir = outputDir
              const genRel = genDir.startsWith(`${workspacePath}/`)
                ? genDir.slice(workspacePath.length + 1)
                : genDir
              await fsMkdir(genDir).catch(() => {})
              const auroraArgs = ['--prompt', currentPrompt, '--run-id', runId, '--output-dir', genDir, '--purpose', intent.purpose, '--max-precision']
              if (referenceConfirmEnabled) auroraArgs.push('--confirm-ref')
              const seenImgs = new Set<string>()
              let effectiveRefImg: string | null = null
              if (referenceImagePath && await fsExists(referenceImagePath)) {
                effectiveRefImg = referenceImagePath
              } else if (materializedViewPlan.primaryPath && await fsExists(materializedViewPlan.primaryPath)) {
                effectiveRefImg = materializedViewPlan.primaryPath
              } else {
                const candFront = `${runPaths.references}/${runId}_front_reference.png`
                if (await fsExists(candFront)) {
                  effectiveRefImg = candFront
                }
              }

              if (effectiveRefImg) {
                auroraArgs.push('--image', effectiveRefImg)
                seenImgs.add(effectiveRefImg)
                referenceImagePath = effectiveRefImg
                setReferenceImageUrl(toAssetUrl(effectiveRefImg))
              }
              for (const img of preparedImages) {
                if (img.stagedPath && !seenImgs.has(img.stagedPath) && await fsExists(img.stagedPath)) {
                  auroraArgs.push('--image', img.stagedPath)
                  seenImgs.add(img.stagedPath)
                }
              }
              if (directMultiView) {
                for (const { path } of materializedViewPlan.assignments) {
                  if (path && !seenImgs.has(path) && await fsExists(path)) {
                    auroraArgs.push('--image', path)
                    seenImgs.add(path)
                  }
                }
              }
              // Reference de SYNTHESE (rien de l'utilisateur n'a ete televerse) :
              // on previent le pipeline pour qu'il ne prenne pas cette image
              // comme un verrou anti-scene. Sans ce drapeau, toute demande
              // multi-objets depuis l'UI partait en un seul objet.
              if (auroraArgs.includes('--image') && !referenceIsUserPhoto) {
                auroraArgs.push('--synthetic-reference')
              }
              if (referenceImagePath) {
                emitGenerationFx('3d', { active: true, refs: [{ url: toAssetUrl(referenceImagePath), role: 'face' }] })
              }
              const refRoles: [string, string][] = [
                [`${genDir}/${runId}_reference.png`, 'face'],
                [`${genDir}/${runId}_reference_v2.png`, 'droite'],
                [`${genDir}/${runId}_reference_v3.png`, 'dos'],
              ]
              let meshEmitted = false
              auroraWatch = window.setInterval(() => {
                void (async () => {
                  try {
                    const refs: { url: string; role: string }[] = []
                    for (const [p, role] of refRoles) {
                      if (await fsExists(p)) refs.push({ url: toAssetUrl(p), role })
                    }
                    if (refs.length === 0 && referenceImagePath) refs.push({ url: toAssetUrl(referenceImagePath), role: 'face' })
                    const meshPath = `${genDir}/${runId}_mesh.glb`
                    const meshExists = !meshEmitted && await fsExists(meshPath)
                    if (meshExists) {
                      meshEmitted = true
                      setPhase('Matériaux & zones — textures et matériaux par zones...', 75)
                    }
                    emitGenerationFx('3d', {
                      active: true,
                      refs: refs.length ? refs : undefined,
                      meshUrl: (meshExists || meshEmitted) ? toAssetUrl(meshPath) : undefined,
                      meshInfo: meshEmitted ? 'géométrie native posée — texture & matériaux en cours' : undefined,
                    })
                  } catch { /* fichier pas encore là */ }
                })()
              }, 1500)
              // 31/07 (observation Juan, 3 fois): les modeles Ollama de la
              // phase d'analyse (vision 19 Go) restaient residents quand
              // TRELLIS commencait a deborder en RAM. Eviction TOTALE ici —
              // le pipeline rechargera ce qu'il lui faut, quand il le faut.
              setProgress('Liberation des modeles Ollama avant la reconstruction 3D...')
              try { await freeGpuBeforeFlux([]) } catch { /* jamais bloquant */ }
              const auroraOutput = await runPythonScript(`${workspacePath}/python-services/aurora_3d_pipeline.py`, auroraArgs, { resumeKey: 'model_ia' })
              const parsedAurora = parseLastJsonLine(auroraOutput) as unknown as { ok?: boolean; is_scene?: boolean; final_mesh?: string; scene_glb?: string; composants?: Record<string, { desc?: string; glb?: string; refus?: string | null }> | null; refuses?: { role: string; motif: string }[] | null; orphelins?: { objet: string; appui_manquant: string }[] | null; composition?: { objet: string; liaison?: string; sur?: string; ok: boolean }[] | null; livraison?: Record<string, string> | null; source_web?: { site?: string; url?: string; title?: string } } | null
              if (parsedAurora?.source_web) {
                setDiscoveredSourceWeb(parsedAurora.source_web)
              }
              // 27/09 (retour Juan: « aucune scene ... je sais pas ou est
              // l'image de reference »): le message n'annoncait ni la scene,
              // ni ses entites, ni ce qui manquait. On construit une phrase
              // explicite — elle est la SEULE chose qui distingue visuellement
              // "j'ai eu 2 objets" de "il m'en manque 1".
              sceneReport = (() => {
                if (!parsedAurora?.is_scene) return ''
                const parts: string[] = []
                const comp = parsedAurora.composants
                if (comp && Object.keys(comp).length) {
                  parts.push(`Scene multi-objets: ${Object.keys(comp).map((r) => {
                    const c = comp[r]
                    return c?.refus ? `${r} (REFUSE)` : r
                  }).join(' + ')}.`)
                }
                if (parsedAurora.composition?.length) {
                  const ok = parsedAurora.composition.filter((c) => c.ok).length
                  const ko = parsedAurora.composition.length - ok
                  parts.push(`Assemblage: ${ok} liaison(s) reussie(s)${ko ? `, ${ko} en echec` : ''}.`)
                }
                if (parsedAurora.refuses?.length) {
                  parts.push(`Entites refusees par la porte: ${parsedAurora.refuses.map((r) => `${r.role} — ${r.motif}`).join(' ; ')}.`)
                }
                if (parsedAurora.orphelins?.length) {
                  parts.push(`Non composees: ${parsedAurora.orphelins.map((o) => `${o.objet} (appui manquant: ${o.appui_manquant})`).join(' ; ')}.`)
                }
                return parts.join(' ')
              })()
              // 27/09: une SCENE multi-objets livre `scene_couleurs` (l'assemblage
              // compose) et non `modele_couleurs` (qui n'existe que pour une
              // entite seule). Sans cette ligne, candidateMesh tombait sur
              // `final_mesh` puis, a defaut, sur un chemin de run qui n'existe
              // pas -> le viewer n'affichait RIEN. `scene_couleurs` passe
              // devant `modele_couleurs`: la scene assemblee est le bon
              // livrable, et c'est elle qui porte les deux matieres.
              const candidateMesh = parsedAurora?.livraison?.scene_couleurs
                ?? parsedAurora?.livraison?.mouvement_couleurs
                ?? parsedAurora?.livraison?.modele_couleurs
                ?? parsedAurora?.final_mesh
                ?? `${genDir}/${runId}_final_materials.glb`

              let existingMeshPath: string | null = null
              for (const candidate of [
                candidateMesh,
                `${genDir}/${runId}_final_materials.glb`,
                `${genDir}/${runId}_matte.glb`,
                `${genDir}/${runId}_mesh.glb`,
                `${runPaths.models}/${runId}_mesh.glb`,
                `${runPaths.models}/${runId}_final_materials.glb`,
              ]) {
                if (candidate && await fsExists(candidate)) {
                  existingMeshPath = candidate
                  break
                }
              }

              if (existingMeshPath) {
                const finalRel = existingMeshPath.startsWith(`${workspacePath}/`)
                  ? existingMeshPath.slice(workspacePath.length + 1)
                  : existingMeshPath
                const { getBridgeUrl: _gbu } = await import('../utils/runtime')
                setViewerWebUrl(`${_gbu()}/aurora_viewer.html?file=${finalRel.split('/').map(encodeURIComponent).join('/')}`)
                result = {
                  ok: true,
                  path: existingMeshPath,
                  pipeline: 'ai_generation',
                  eu_compliant: true,
                  license: 'MIT',
                  shape_model: 'Atlas',
                  shape_input_mode: 'single_view',
                } as ModelGenerationResult
              } else {
                try {
                  const errMatch = auroraOutput.match(/"error":\s*"((?:[^"\\]|\\.)*)"/)
                  if (errMatch) auroraFailReason = JSON.parse(`"${errMatch[1]}"`)
                } catch { /* raison illisible */ }
                if (!auroraFailReason) {
                  const sentinel = auroraOutput.split('\n').reverse().find((l) => l.startsWith('PROGRESS:error:'))
                  if (sentinel) auroraFailReason = sentinel.slice('PROGRESS:error:'.length)
                }
                setProgress('Pipeline Aurora sans resultat exploitable, repli ancien chemin...')
              }
            } catch (auroraExc) {
              // 31/07 (retour Juan: « j'arrete la generation, elle se relance
              // automatiquement »): l'ANNULATION volontaire etait traitee
              // comme un echec de pipeline -> la chaine de repli relançait
              // une reconstruction. Un arret demande ARRETE tout.
              const excTxt = auroraExc instanceof Error ? auroraExc.message : String(auroraExc)
              if (stopRequestedRef.current || /annul/i.test(excTxt)) {
                setProgress('Generation arretee — rien ne sera relance.')
                setIsGenerating(false)
                emitGenerationFx('3d', { active: false })
                return
              }
              // La VRAIE raison d'abord: quand le script meurt (SIGTERM de la
              // sentinelle), le message d'exception ne garde qu'une ligne
              // d'info quelconque ("allocateur MANAGE actif") qui masque la
              // ligne SENTINELLE — l'utilisateur croyait a un bug TRELLIS
              // alors que la protection anti-gel venait de lui sauver son PC.
              const excMsg = auroraExc instanceof Error ? auroraExc.message : String(auroraExc)
              const sentinelle = excMsg.split('\n').reverse().find((l) => l.includes('SENTINELLE ANTI-GEL'))
              auroraFailReason = sentinelle
                ? `Protection anti-gel: ${sentinelle.replace(/^.*SENTINELLE ANTI-GEL/, 'SENTINELLE ANTI-GEL')}`
                : excMsg
              setProgress('Pipeline Aurora indisponible, repli ancien chemin...')
            } finally {
              if (auroraWatch !== undefined) window.clearInterval(auroraWatch)
            }
          }
          // TRELLIS-ONLY: si TRELLIS a ete tente et n'a rien rendu, on N'enchaine PAS
          // sur DreamGaussian (2e gros modele apres coup = risque de gel, et
          // l'utilisateur veut pouvoir s'en passer). Echec propre.
          if (!result && auroraAttempted && trellisOnly) {
            // MEME EN ECHEC, la structure de dossiers doit etre la structure
            // FRANCAISE lisible (prompt/reference/journal/travail) — sinon
            // l'utilisateur retombe sur l'ancien vrac et croit que la
            // reorganisation n'existe pas. Best-effort, sans bloquer l'erreur.
            try {
              void runPythonScript(`${workspacePath}/python-services/livraison_organisee.py`,
                ['--run-dir', runPaths.root, '--run-id', runId])
            } catch { /* rangement best-effort */ }
            const reason = auroraFailReason ? `${auroraFailReason} — ` : ''
            throw new Error(`${reason}TRELLIS.2 n a pas produit de mesh (mode TRELLIS-only, aucun repli tente). Relance la generation, ou reactive le repli DreamGaussian via aurora3d_trellis_only=0.`)
          }
          if (!result) {
            // Try DreamGaussian first if preferred (EU-safe MIT license)
            if (intent.pipelineRouting.dreamgaussianPreferred) {
              setProgress('Atlas construit (MIT, EU-safe)...')
              setPhase('Sculpture 3D — conversion du nuage en maillage...', 60)
              try {
                const dgOutput = await runPythonScript(`${workspacePath}/python-services/dreamgaussian_run.py`, ['--image', referenceImagePath, '--output-dir', outputDir, '--run-id', runId, '--format', 'glb'], { resumeKey: 'model' })
                const dgResult = parseLastJsonLine(dgOutput)
                if (dgResult?.ok && dgResult.path) {
                  result = { ...dgResult, pipeline: 'ai_generation' } as ModelGenerationResult
                }
              } catch {
                setProgress('Atlas ne dispose d aucune autre methode de construction.')
              }
            }

          }

          if (!result?.ok || !result.path) throw new Error(result?.error || 'Aucun pipeline n a produit de mesh exploitable.')

          if (dimensionHintForGen || wantsSymmetryEnforced) {
            const scaledPath = `${outputDir}/${runId}_scaled.glb`
            const scaleArgs = ['--input', result.path, '--output', scaledPath, '--intent-purpose', intent.purpose, '--motion-readiness', intent.motionReadiness]
            if (dimensionHintForGen) scaleArgs.push('--target-dimension-meters', String(dimensionHintForGen.meters), '--target-dimension-axis', dimensionHintForGen.axis)
            if (wantsSymmetryEnforced) scaleArgs.push('--enforce-symmetry')
            try {
              const scaleOutput = await runPythonScript(`${workspacePath}/python-services/mesh_postprocess.py`, scaleArgs)
              const scaleResult = parseLastJsonLine(scaleOutput)
              const scaledOutputPath = scaleResult?.ok ? scaleResult.outputPath : undefined
              if (scaledOutputPath) {
                result.path = scaledOutputPath
                setProgress(dimensionHintForGen
                  ? `Dimension appliquee: ${dimensionHintForGen.meters}m (axe ${dimensionHintForGen.axis})${wantsSymmetryEnforced ? ' + symetrie' : ''}`
                  : 'Symetrie bilaterale appliquee')
              }
            } catch { /* best-effort: le mesh brut reste valable sans ce post-traitement */ }
          }
          const confirmedPath = result.path

          // ══════════════════════════════════════════════════════════════
          // AUTO-CORRECTION LOOP: iterate until QA = PASS or diminishing returns
          // ══════════════════════════════════════════════════════════════
          let activeMeshPath = result.path
          let activeReferenceImagePath = referenceImagePath
          let correctionAttempt = 0
          let previousFidelityScore = -1
          let consecutiveNoImprove = 0
          const MAX_CORRECTION_ATTEMPTS = 8
          const FIDELITY_TARGET = 95
          const MIN_ACCEPTABLE_WITHOUT_TARGET = 92
          let meshFidelityResult: MeshFidelityVerification | null = null
          let meshFidelitySummary = ''
          let validationSummary = ''
          let correctionLog: string[] = []
          let bestFidelityScore = -1
          let bestMeshPath = activeMeshPath

          // eslint-disable-next-line no-constant-condition
          while (true) {
            if (result.shape_model === 'Atlas') {
              correctionLog.push('Voie Aurora native: gates internes du pipeline (acceptance, matieres, zones) deja passes — boucle de correction UI sautee pour ne pas degrader le natif')
              break
            }
            // ── Step A: Mesh quality gate from Python ──
            if (result.mesh_quality_ok === false && result.mesh_quality_issues?.length) {
              const qualityIssues = result.mesh_quality_issues.join('; ')
              setProgress(`Qualite mesh insuffisante: ${qualityIssues}. Sauvetage renforce...`)
              setPhase(`Sculpture 3D — optimisation qualité mesh (tentative ${correctionAttempt + 1})...`, 65)
              {
                setPhase('Sculpture 3D — post-process géométrique renforcé...', 66)
                const aggressivePath = `${outputDir}/${runId}_aggressive_${correctionAttempt}.glb`
                try {
                  const aggressiveOutput = await runPythonScript(
                    `${workspacePath}/python-services/mesh_postprocess.py`,
                    [
                      '--input', activeMeshPath,
                      '--output', aggressivePath,
                      '--intent-purpose', intent.purpose,
                      '--motion-readiness', intent.motionReadiness,
                      '--floater-ratio', '0.012',
                      '--smooth-iterations', '24',
                      '--target-faces', '50000',
                    ],
                  )
                  const aggressiveResult = parseLastJsonLine(aggressiveOutput)
                  if (aggressiveResult?.ok && aggressiveResult.outputPath) {
                    activeMeshPath = aggressiveResult.outputPath
                    result.path = aggressiveResult.outputPath
                    correctionLog.push('QualityGate: sauvetage agressif applique (mesh_postprocess)')
                  } else {
                    correctionLog.push(`QualityGate: mesh retenu malgre defauts: ${qualityIssues}`)
                  }
                } catch {
                  correctionLog.push(`QualityGate: mesh retenu malgre defauts: ${qualityIssues}`)
                }
              }
            }
            activeMeshPath = result.path || confirmedPath

            // ── Step B: Blender mesh validation + auto-fix ──
            if (intent.pipelineRouting.validationChecks.length > 0) {
              setProgress('Validation geometrique du mesh...')
              setPhase('Sculpture 3D — validation géométrique...', 68)
              try {
                const validationResult = await runMeshValidation({
                  meshPath: activeMeshPath,
                  checks: intent.pipelineRouting.validationChecks,
                  autoFix: false,
                  outputDir,
                  runId: `${runId}_v${correctionAttempt}`,
                })
                if (validationResult.ok && validationResult.validationReport) {
                  const report = validationResult.validationReport
                  result.validationReport = report
                  const issues = report.issues.filter((i) => i.severity === 'error' || i.severity === 'warning')
                  if (issues.length > 0 && issues.some((i) => i.autoFixAvailable)) {
                    setPhase('Sculpture 3D — auto-correction Blender...', 69)
                    const cleanupResult = await runMeshCleanup({
                      meshPath: activeMeshPath,
                      checks: intent.pipelineRouting.validationChecks,
                      autoFix: true,
                      outputDir,
                      runId: `${runId}_v${correctionAttempt}`,
                    })
                    if (cleanupResult.ok && cleanupResult.outputPath) {
                      activeMeshPath = cleanupResult.outputPath
                      result.path = cleanupResult.outputPath
                      validationSummary = `Validation: ${report.vertexCount}v, ${report.faceCount}f, ${issues.length} fix(es).`
                    }
                  } else if (issues.length === 0) {
                    validationSummary = `Validation OK: ${report.vertexCount}v, ${report.faceCount}f${report.watertight ? ', etanche' : ''}.`
                  } else {
                    validationSummary = `Validation: ${issues.length} probleme(s) non-fixable(s).`
                  }
                }
              } catch {
                validationSummary = validationSummary || 'Validation Blender non disponible.'
              }
            }

            // ── Step C: Mesh fidelity verification (vision model comparison) ──
            setProgress(`Capture du rendu mesh reel (passage ${correctionAttempt + 1})...`)
            setPhase('Matériaux & zones — rendu pour comparaison fidélité...', 72)
            try {
              let meshScreenshotBase64: string | null = null
              try {
                const screenshotPath = `${runPaths.audits}/${runId}_meshshot_${correctionAttempt}.png`
                const screenshotResult = await renderMeshScreenshot({
                  meshPath: activeMeshPath,
                  outputPath: screenshotPath,
                  views: ['front_3q'],
                })
                if (screenshotResult.ok && screenshotResult.screenshots.length > 0) {
                  const shotPath = screenshotResult.screenshots[0].path
                  const shotBytes = await fsReadBinary(shotPath)
                  meshScreenshotBase64 = btoa(String.fromCharCode(...new Uint8Array(shotBytes)))
                  correctionLog.push(`Mesh screenshot captured: ${shotPath}`)
                }
              } catch {
              }

              let refBase64: string | null = null
              try {
                const refBytes = await fsReadBinary(activeReferenceImagePath)
                refBase64 = btoa(String.fromCharCode(...new Uint8Array(refBytes)))
              } catch { }

              setProgress(`Verification fidelite mesh (passage ${correctionAttempt + 1})...`)
              setPhase('Matériaux & zones — comparaison mesh reel vs référence...', 74)
              meshFidelityResult = await verify3DMeshFidelity({
                meshScreenshotBase64: meshScreenshotBase64 || refBase64 || '',
                referenceImageBase64: meshScreenshotBase64 ? refBase64 : null,
                prompt: currentPrompt,
                intent,
                model: visionModel,
              })
              setMeshFidelity(meshFidelityResult)
            } catch {
              meshFidelityResult = null
            }

            // ── Step D: Decide whether to continue auto-correction ──
            if (!meshFidelityResult || meshFidelityResult.passed) {
              // QA PASS — exit the loop
              if (meshFidelityResult) {
                meshFidelitySummary = `Fidelite: ${meshFidelityResult.score}/100 — QA PASS.`
                correctionLog.push(`Passage ${correctionAttempt + 1}: score ${meshFidelityResult.score}/100 — PASS`)
              }
              break
            }

            // Build correction strategy from the fidelity analysis
            const correctionStrategy = buildMeshCorrectionStrategy({
              fidelity: meshFidelityResult,
              intent,
              prompt: currentPrompt,
              attemptNumber: correctionAttempt,
              meshQualityIssues: result.mesh_quality_issues,
              meshQualityWarnings: result.mesh_quality_warnings,
              meshGeometryGrade: result.mesh_geometry_grade,
              // v77zk: feed the v77zj humanoid proportion metrics into the
              // correction strategy so character/body_part retries get
              // anatomical-specific guidance instead of the generic prompt.
              humanoidMetrics: {
                aspectRatio: result.mesh_humanoid_aspect_ratio ?? null,
                headVertexFraction: result.mesh_head_vertex_fraction ?? null,
                headBodyWidthRatio: result.mesh_head_body_width_ratio ?? null,
              },
            })

            correctionLog.push(
              `Passage ${correctionAttempt + 1}: score ${meshFidelityResult.score}/100, ` +
              `categorie: ${meshFidelityResult.failureCategory}, ` +
              `corrections: ${correctionStrategy.corrections.join('+')}`
            )

            // Track the best result so far so we always keep the mesh that
            // scored highest even if a later retry regresses.
            if (meshFidelityResult.score > bestFidelityScore) {
              bestFidelityScore = meshFidelityResult.score
              bestMeshPath = activeMeshPath
            }

            // Check stop conditions. The user explicitly reported cases where
            // the loop gave up at 75/100 — we refuse to stop mid-way now:
            //   - target 95+ or the strategy explicitly says shouldContinue=false
            //     (which requires score >= 90, grade A, attempt >= 5)
            //   - OR hard cap (8 attempts) reached
            //   - plateaux are tolerated until attempt ~5 AND only when the
            //     score is already close (>= 92) so we never freeze at 75 or 80.
            const scoreImproved = previousFidelityScore < 0 || meshFidelityResult.score > previousFidelityScore
            if (scoreImproved) {
              consecutiveNoImprove = 0
            } else {
              consecutiveNoImprove += 1
            }
            const reachedTarget = meshFidelityResult.score >= FIDELITY_TARGET
            const hardCap = correctionAttempt + 1 >= MAX_CORRECTION_ATTEMPTS
            const lateGoodPlateau = consecutiveNoImprove >= 3
              && meshFidelityResult.score >= MIN_ACCEPTABLE_WITHOUT_TARGET
              && correctionAttempt + 1 >= 5

            if (reachedTarget || hardCap || !correctionStrategy.shouldContinue || lateGoodPlateau) {
              const stopReason = reachedTarget
                ? 'cible 95/100 atteinte'
                : hardCap
                  ? `plafond de ${MAX_CORRECTION_ATTEMPTS} passages atteint`
                  : lateGoodPlateau
                    ? `plateau a ${meshFidelityResult.score}/100 apres ${consecutiveNoImprove} passages (score deja >= ${MIN_ACCEPTABLE_WITHOUT_TARGET})`
                    : 'strategie epuisee'
              meshFidelitySummary = `Fidelite: ${meshFidelityResult.score}/100 apres ${correctionAttempt + 1} passage(s) — ${stopReason}.`
              if (meshFidelityResult.missingDetails.length > 0) meshFidelitySummary += ` Manque: ${meshFidelityResult.missingDetails.slice(0, 3).join(', ')}.`
              if (meshFidelityResult.artifacts.length > 0) meshFidelitySummary += ` Artefacts: ${meshFidelityResult.artifacts.slice(0, 2).join(', ')}.`
              if (meshFidelityResult.suggestions.length > 0) meshFidelitySummary += ` Suggestion: ${meshFidelityResult.suggestions[0]}.`
              // If a previous pass scored higher, fall back to that mesh rather
              // than shipping the regression.
              if (bestFidelityScore > meshFidelityResult.score && bestMeshPath) {
                activeMeshPath = bestMeshPath
                result.path = bestMeshPath
                correctionLog.push(`Reprise du mesh du meilleur passage (score ${bestFidelityScore}/100)`)
              }
              break
            }

            previousFidelityScore = meshFidelityResult.score
            correctionAttempt++

            // ── Step E: Re-generate reference if needed ──
            // 30/07 (audit): la boucle de correction remplacait la PHOTO de
            // l'utilisateur par une image FLUX texte des qu'un score de
            // fidelite baissait — le mesh final ne ressemblait plus a la
            // photo jointe, en silence. Reference d'origine utilisateur =
            // seule la reconstruction se corrige, jamais la reference.
            if (correctionStrategy.shouldRetryReference && preparedImages.length === 0) {
              setProgress(`Auto-correction reference (passage ${correctionAttempt})...`)
              setPhase(`Re-generation de la reference avec corrections ciblees...`, 85 + correctionAttempt)
              const correctionLines = correctionStrategy.referenceCorrections
              const paletteLine = overlayForPlanner.palette && overlayForPlanner.palette.length > 0
                ? `Colours must stay identical to the reference: ${overlayForPlanner.palette.slice(0, 6).map((p) => `${p.zone} ${p.hex}`).join(', ')}`
                : ''
              const textLine = overlayForPlanner.visibleText && overlayForPlanner.visibleText.length > 0
                ? `Keep these texts/logos verbatim: ${overlayForPlanner.visibleText.slice(0, 5).map((t) => `"${t.text}" ${t.location ? `(${t.location})` : ''}`).join('; ')}`
                : ''
              const focusLine = overlayForPlanner.entities
                && overlayForPlanner.focusEntityIndex !== undefined
                && overlayForPlanner.focusEntityIndex >= 0
                && overlayForPlanner.entities[overlayForPlanner.focusEntityIndex]
                ? `Subject is strictly "${overlayForPlanner.entities[overlayForPlanner.focusEntityIndex].label}" — ignore any other entity from the reference.`
                : ''
              const correctedRefPrompt = [
                taskContext.generationPrompt,
                '',
                `AUTO-CORRECTION PASS ${correctionAttempt} — TARGETED FIXES (apply until fidelity >= ${FIDELITY_TARGET}):`,
                ...correctionLines.map((l) => `- ${l}`),
                ...meshFidelityResult.suggestions.slice(0, 3).map((s) => `- Vision QA suggestion: ${s}`),
                '',
                `Previous fidelity score: ${meshFidelityResult.score}/100`,
                `Failure category: ${meshFidelityResult.failureCategory}`,
                meshFidelityResult.missingDetails.length > 0
                  ? `Missing details to ADD: ${meshFidelityResult.missingDetails.join(', ')}`
                  : '',
                meshFidelityResult.artifacts.length > 0
                  ? `Artifacts to REMOVE: ${meshFidelityResult.artifacts.join(', ')}`
                  : '',
                paletteLine,
                textLine,
                focusLine,
              ].filter(Boolean).join('\n')

              const correctedRefWorkflow = resolveReferenceWorkflow(intent, hardware, false, currentPrompt, referenceSupportPlan)
              const extraSteps = correctionStrategy.escalation === 'maximum' ? 12 : correctionStrategy.escalation === 'strong' ? 8 : 4
              const correctedWorkflow = createFlux2Workflow({
                prompt: buildReferencePrompt(correctedRefPrompt, intent, activeMotionPreset, referenceSupportPlan, referenceViewPlan, currentPrompt),
                width: correctedRefWorkflow.width,
                height: correctedRefWorkflow.height,
                steps: correctedRefWorkflow.steps + extraSteps,
                filenamePrefix: `juan_bike_3d_ref_corr${correctionAttempt}`,
              })
              try {
                const correctedRefBlob = await runReferenceWorkflow({
                  workflow: correctedWorkflow,
                  setPhase,
                  pollRef,
                  phaseStart: 86,
                  label: `Reference corrigee (passage ${correctionAttempt})...`,
                  ensureComfy,
                  vramGuard: { ollamaModelsToEvict: Array.from(new Set([visionModel, AUXILIARY_ANALYSIS_MODEL])) },
                })
                const correctedRefPath = `${runPaths.references}/${runId}_reference_corr${correctionAttempt}.png`
                await fsWriteBinary(correctedRefPath, Array.from(new Uint8Array(await correctedRefBlob.arrayBuffer())))
                activeReferenceImagePath = correctedRefPath
                setReferenceImageUrl(toAssetUrl(correctedRefPath))
                lastReferenceImagePathRef.current = correctedRefPath
                correctionLog.push(`Reference regeneree (passage ${correctionAttempt})`)
              } catch {
                correctionLog.push(`Reference correction echouee (passage ${correctionAttempt}), mesh conserve`)
              }
            }

            // ── Step F: Re-generate mesh with corrections ── (voie TRELLIS
            // uniquement desormais; pas de second pipeline de secours)
            if (correctionStrategy.shouldRetryMesh) {
              correctionLog.push(`Mesh retry non disponible (passage ${correctionAttempt}) — TRELLIS.2 est la seule voie de reconstruction`)
              break
            }
          }
          // ── END AUTO-CORRECTION LOOP ──

          // ── POST-LOOP: Auto-rig — humanoid via Rigify, vehicle via wheel
          // detection, mechanism via Bullet rigid bodies. The branch is driven
          // by intent.subjectKind so a car never receives a humanoid skeleton
          // again (which used to break deformation entirely). ──
          let riggingSummary = ''
          // v77ze: motion-verb-driven rig selection. When the user explicitly
          // says "drone qui vole", "ventilateur qui tourne" or "voiture qui
          // roule", the rig subject is upgraded so the GLB ships with the
          // matching animation (rolling wheels, rigid-body rotation, pendulum
          // swing) instead of the dull product turntable.
          const motionVerb = detectMotionVerbHint(currentPrompt)
          const baseIsCharacter = intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature' || intent.subjectKind === 'body_part'
          const isCharacter = baseIsCharacter || motionVerb === 'walking'
          const isVehicle = intent.subjectKind === 'vehicle' || motionVerb === 'rolling'
          const isMechanism = intent.subjectKind === 'mechanical_part'
            || intent.subjectKind === 'assembly'
            || intent.purpose === 'mechanical_part'
            || motionVerb === 'rotating'
            || motionVerb === 'flying'
            || motionVerb === 'mechanism'
          // v79: pendulum/hanging detection from prompt regex (not in
          // intent.subjectKind enum yet) + product/prop catch-all so even a
          // static object gets a 6s ambient turntable rotation.
          const promptLowerForRig = currentPrompt.toLowerCase()
          const isPendulum = motionVerb === 'swinging' || motionVerb === 'oscillating'
            || /\b(pendul|balancier|swing|hanging|pendulum|suspendu|accroche|chandelier|lustre|hammock|hamac)\b/i.test(promptLowerForRig)
          const isProductLike = !isCharacter && !isVehicle && !isMechanism && !isPendulum && (
            intent.subjectKind === 'product' || intent.subjectKind === 'tool' || intent.subjectKind === 'object'
          )
          const wantsRig = intent.motionReadiness === 'rig_candidate' || intent.motionReadiness === 'articulated' || isCharacter || isVehicle || isMechanism || isPendulum || isProductLike
          // 31/07 (audit): apres un run TRELLIS complet, l'UI re-mutait le
          // mesh HORS porte de qualite (re-rig, re-bake) — le fichier montre
          // n'etait plus celui que la porte avait juge. Le pipeline TRELLIS
          // possede son propre mouvement et ses portes: aucun post-traitement
          // UI par-dessus.
          if (intent.pipelineRouting.blenderRequired && wantsRig && result.shape_model !== 'Atlas') {
            const rigSubject: 'humanoid' | 'creature' | 'vehicle' | 'mechanism' | 'mechanical' | 'pendulum' | 'product' = isCharacter
              ? (intent.subjectKind === 'creature' ? 'creature' : 'humanoid')
              : isVehicle
                ? 'vehicle'
                : isMechanism
                  ? 'mechanism'
                  : isPendulum
                    ? 'pendulum'
                    : 'product'
            const rigLabel = rigSubject === 'vehicle'
              ? 'Detection roues + animation rolling...'
              : rigSubject === 'mechanism'
                ? 'Bake rigid bodies + hinges via Bullet...'
                : rigSubject === 'pendulum'
                  ? 'Pivot + balancier physique (T = 2π√(L/g))...'
                  : rigSubject === 'product'
                    ? 'Turntable ambiant 6s pour overview 360deg...'
                    : 'Auto-rigging Rigify (squelette + IK + breathing)...'
            setProgress(rigLabel)
            setPhase('Animation — ' + rigLabel, 88)
            try {
              // v75: pick the most relevant test_action based on prompt.
              // 'walk' beats 'applaud' as default because almost every
              // character request implies "should be able to move" not
              // "should clap once". Keywords override.
              const promptLower = currentPrompt.toLowerCase()
              const humanoidAction = /\b(idle|debout|standing|attente|stand)\b/i.test(promptLower)
                ? 'idle'
                : /\b(applaudir|clap|applaud|claps)\b/i.test(promptLower)
                  ? 'applaud'
                  : 'walk'

              // v78: when rigging a vehicle or mechanism, ask the Aurora
              // extension for realistic physical params (density, friction,
              // angular velocity) so the bake uses calibrated mass and the
              // bounce/rolling speeds match real-world expectations.
              let physicsOverrides: NonNullable<Parameters<typeof runAutoRig>[0]['physics']> | undefined
              if (rigSubject === 'vehicle' || rigSubject === 'mechanism') {
                try {
                  const { lookupPhysicsLaws } = await import('../services/auroraExtensionBridge')
                  const lookup = await lookupPhysicsLaws(currentPrompt.slice(0, 80), { hint: rigSubject })
                  if (lookup.ok) {
                    physicsOverrides = {
                      densityKgPerM3: lookup.data.densityKgPerM3,
                      frictionCoefficient: lookup.data.frictionCoefficient,
                      restitution: lookup.data.restitution,
                      angularVelocityRadPerS: lookup.data.angularVelocityRadPerS,
                      pendulumPeriodSeconds: lookup.data.pendulumPeriodSeconds,
                    }
                  }
                } catch {
                  // best-effort - extension may not be installed
                }
              }

              // v77zr: route through runAutoRigFromPrompt so the kinematics
              // library + custom-motion parser auto-resolve the appropriate
              // MotionDescriptor from (currentPrompt, intent) and bake a real
              // NLA action onto the rig before export. Falls back silently
              // to plain runAutoRig when no preset / parsed motion applies.
              const kinematicSubject =
                rigSubject === 'humanoid' ? 'character'
                  : rigSubject === 'creature' ? 'creature'
                    : rigSubject === 'vehicle' ? 'vehicle'
                      : rigSubject === 'mechanism' || rigSubject === 'pendulum' ? 'mechanism'
                        : 'object'
              const kinematicSystem = intent.systemClass
              const rigResult = await runAutoRigFromPrompt(
                {
                  meshPath: activeMeshPath,
                  rigSystem: 'rigify',
                  subjectKind: rigSubject,
                  style: /\b(anime|manga)\b/i.test(currentPrompt) ? 'anime' : 'realistic',
                  testAction: rigSubject === 'humanoid' ? humanoidAction : '',
                  outputDir,
                  runId,
                  physics: physicsOverrides,
                },
                currentPrompt,
                { subjectKind: kinematicSubject, systemClass: kinematicSystem },
              )
              if (rigResult.ok && rigResult.outputPath) {
                activeMeshPath = rigResult.outputPath
                result.path = rigResult.outputPath
                result.rigBones = rigResult.rigBones
                const kindLabel = rigSubject === 'vehicle' ? 'roues animees' : rigSubject === 'mechanism' ? 'rigid bodies bakes' : 'bones Rigify'
                const motionTag = rigResult.motionResolution?.ok
                  ? ` + motion=${rigResult.motionResolution.descriptor.id} (${rigResult.motionResolution.source})`
                  : ''
                riggingSummary = `Auto-rig (${rigSubject}) applique (${rigResult.rigBones || '?'} ${kindLabel})${motionTag}.`
              }
            } catch {
              riggingSummary = 'Auto-rig Blender non disponible.'
            }
          }

          // Final fidelity summary if not set in loop
          if (!meshFidelitySummary && meshFidelityResult) {
            meshFidelitySummary = `Fidelite: ${meshFidelityResult.score}/100 — ${meshFidelityResult.notes}`
          }
          if (correctionLog.length > 1) {
            meshFidelitySummary += ` (${correctionLog.length} passages d'auto-correction)`
          }

          // ── v82nu iter22: AUTO RESCUE chain (vertex colors → PBR materials) ──
          let autoRescueSummary = ''
          try {
            if (result.shape_model === 'Atlas') {
              throw new Error('Atlas gere sa propre qualite — auto-rescue UI saute')
            }
            const { getBridgeUrl: getRescueBridge } = await import('../utils/runtime')
            const rescueBridge = getRescueBridge()
            const rescueOutDir = runPaths.rescue
            setProgress('Auto-rescue mesh (score + bake colors si necessaire)...')
            setPhase('Matériaux & zones — application des matières PBR...', 80)
            const rescueResp = await fetch(`${rescueBridge}/api/3d/auto-rescue`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                mesh: activeMeshPath,
                reference: referenceImagePath,
                prompt: currentPrompt,
                output_dir: rescueOutDir,
              }),
              signal: AbortSignal.timeout(420_000),
            })
            const rescueData = await rescueResp.json() as {
              ok: boolean
              rescue?: {
                final_mesh?: string
                initial_score?: number
                final_score?: number
                score_delta?: number
                audit_trail?: Array<{ stage: string; ok?: boolean }>
              }
              error?: string
            }
            if (rescueData.ok && rescueData.rescue?.final_mesh) {
              const r = rescueData.rescue
              if (r.final_mesh && r.final_mesh !== activeMeshPath) {
                activeMeshPath = r.final_mesh
                result.path = r.final_mesh
              }
              const initial = r.initial_score ?? 0
              const final = r.final_score ?? 0
              const delta = r.score_delta ?? (final - initial)
              autoRescueSummary = `Auto-rescue: ${initial.toFixed(0)} → ${final.toFixed(0)} (Δ${delta >= 0 ? '+' : ''}${delta.toFixed(0)}).`
            } else if (rescueData.error) {
              autoRescueSummary = `Auto-rescue skip: ${rescueData.error.slice(0, 80)}.`
            }
          } catch (rescueExc) {
            autoRescueSummary = `Auto-rescue skip: ${getErrorMessage(rescueExc).slice(0, 80)}.`
          }
          if (autoRescueSummary) {
            meshFidelitySummary = meshFidelitySummary
              ? `${meshFidelitySummary} ${autoRescueSummary}`
              : autoRescueSummary
          }

          // ── v82nu iter8.A: AUTO motion-intent gate ────────────────────────
          let autoMotionSummary = ''
          if (!motionEnabledRef.current) {
            autoMotionSummary = 'Mouvement désactivé — mesh statique conservé.'
          } else try {
            const { getBridgeUrl } = await import('../utils/runtime')
            const bridge = getBridgeUrl()
            const autoMotionOutGlb = activeMeshPath.replace(/\.glb$/i, '_anim.glb')
            setProgress('Classification motion-intent (gemma3:12b)...')
            setPhase('Animation — classification motion-intent...', 90)
            const motResp = await fetch(`${bridge}/api/3d/auto-motion-bake`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                prompt: currentPrompt,
                input_glb: activeMeshPath,
                output_glb: autoMotionOutGlb,
                min_confidence: 0.75,
              }),
              signal: AbortSignal.timeout(700_000),
            })
            const motData = await motResp.json() as {
              ok: boolean
              intent?: { category: string; confidence: number; rationale: string }
              decision?: { baked: boolean; category: string; confidence: number; reason: string; size_before: number; size_after: number }
              glb_path?: string
              error?: string
            }
            if (motData.ok && motData.decision) {
              const dec = motData.decision
              if (dec.baked && motData.glb_path && motData.glb_path !== activeMeshPath) {
                activeMeshPath = motData.glb_path
                result.path = motData.glb_path
                autoMotionSummary = `Motion auto: ${dec.category} bake (conf=${dec.confidence.toFixed(2)}, ${(dec.size_after / 1024).toFixed(1)}KB).`
              } else {
                autoMotionSummary = `Motion auto: ${dec.category} (${dec.reason}).`
              }
            } else if (motData.error) {
              autoMotionSummary = `Motion auto indisponible: ${motData.error.slice(0, 80)}.`
            }
          } catch (motExc) {
            autoMotionSummary = `Motion auto skip: ${getErrorMessage(motExc).slice(0, 80)}.`
          }
          if (autoMotionSummary) {
            meshFidelitySummary = meshFidelitySummary
              ? `${meshFidelitySummary} ${autoMotionSummary}`
              : autoMotionSummary
          }

          let finalAcceptanceSummary = ''
          let finalAcceptanceRejectedReason = ''
          try {
            setProgress('Gate qualite finale 3D (texture, silhouette, mouvement)...')
            setPhase('Finalisation — contrôle qualité final 3D...', 95)
            const acceptanceOutput = await runPythonScript(
              `${workspacePath}/python-services/mesh_acceptance_gate.py`,
              [
                '--mesh', activeMeshPath,
                '--prompt', currentPrompt,
                '--kind', acceptanceKindForIntent(intent),
              ],
              { resumeKey: 'model' },
            )
            const acceptance = parseLastJsonLine(acceptanceOutput) as {
              ok?: boolean
              acceptance_ok?: boolean
              engineer_grade?: number
              threshold?: number
              hard_failures?: string[]
              suggested_fixes?: string[]
            } | null
            if (acceptance?.ok) {
              const grade = acceptance.engineer_grade ?? 0
              const threshold = acceptance.threshold ?? 0
              if (acceptance.acceptance_ok) {
                finalAcceptanceSummary = `Gate finale: OK (${grade.toFixed(0)}/${threshold}).`
              } else {
                const reason = (acceptance.hard_failures || []).slice(0, 2).join('; ') || 'verrou qualite non satisfait'
                finalAcceptanceSummary = `Gate finale: REJET (${grade.toFixed(0)}/${threshold}) - ${reason}.`
                finalAcceptanceRejectedReason = reason
              }
            }
          } catch (acceptanceExc) {
            finalAcceptanceSummary = `Gate finale indisponible: ${getErrorMessage(acceptanceExc).slice(0, 80)}.`
          }
          if (finalAcceptanceSummary) {
            meshFidelitySummary = meshFidelitySummary
              ? `${meshFidelitySummary} ${finalAcceptanceSummary}`
              : finalAcceptanceSummary
          }
          if (finalAcceptanceRejectedReason) {
            throw new Error(`Gate qualite finale 3D rejete: ${finalAcceptanceRejectedReason}`)
          }

          await fsWriteBinary(
            `${runPaths.audits}/final_manifest.json`,
            utf8Bytes(JSON.stringify({
              schema: 'aurora.3d.final_manifest.v1',
              session_id: active3dSession.id,
              session_title: active3dSession.title,
              run_id: runId,
              prompt: currentPrompt,
              reference_image: referenceImagePath,
              final_mesh: activeMeshPath,
              model_url: toAssetUrl(activeMeshPath),
              pipeline: result.pipeline,
              shape_model: result.shape_model,
              textured: result.textured,
              animation_frames: result.animationFrames ?? null,
              rig_bones: result.rigBones ?? null,
              validation_summary: validationSummary,
              rigging_summary: riggingSummary,
              quality_summary: meshFidelitySummary,
              created_at: new Date().toISOString(),
            }, null, 2)),
          )

          lastMeshPathRef.current = activeMeshPath
          setModelUrl(toAssetUrl(activeMeshPath))
          // v71: persist le rapport qualite mesh pour le bouton 'Inspecter mesh'.
          setMeshQualityReport({
            grade: result.mesh_geometry_grade,
            qualityOk: result.mesh_quality_ok,
            issues: result.mesh_quality_issues,
            warnings: result.mesh_quality_warnings,
            vertexCount: result.mesh_vertex_count,
            faceCount: result.mesh_face_count,
            extents: result.mesh_extents,
            flatnessRatio: result.mesh_flatness_ratio,
            aspectRatio: result.mesh_aspect_ratio,
            disconnectedBodies: result.mesh_disconnected_bodies,
            degenerateFaceCount: result.mesh_degenerate_face_count,
            isWatertight: result.mesh_is_watertight,
            surfaceArea: result.mesh_surface_area,
            volume: result.mesh_volume,
          })
          const shapeLabel = result.shape_model ? result.shape_model.split('/').pop() || result.shape_model : 'Atlas'
          const textureState = result.textured === false ? 'sans texture paint' : 'avec texture paint'
          const fallbackState = result.fallback_used ? ' via fallback shape autonome' : ''
          const pipelineLabel = activePipeline === 'procedural' ? 'Pipeline Atlas (procedural)' : activePipeline === 'photogrammetry' ? 'Pipeline Atlas (photogrammetrie)' : intent.pipelineRouting.dreamgaussianPreferred && result.shape_model?.includes('Atlas') ? 'Pipeline Atlas (MIT)' : 'Pipeline Atlas'
          const referencePassSummary = directMultiView
            ? `Reference multivue directe: ${multiviewSummary}.`
            : `Reference ${referenceWorkflow.style} ${referenceWorkflow.width}x${referenceWorkflow.height}.`
          const baseFidelityScore = activePipeline === 'procedural' ? 98 : activePipeline === 'photogrammetry' ? 97 : result.fallback_used ? 84 : (result.multiview_used || directMultiView) ? 96 : referenceWorkflow.style === 'technical_render' ? 92 : 90
          // Adjust fidelity score based on mesh verification
          const fidelityScore = meshFidelityResult ? Math.round((baseFidelityScore + meshFidelityResult.score) / 2) : baseFidelityScore
          setProgress(`${pipelineLabel}: mesh ${shapeLabel} ${textureState} genere${fallbackState}. ${validationSummary} ${riggingSummary} ${meshFidelitySummary}`.trim())
          setPhase('Finalisation — validation et chargement du modèle 3D...', 98)
          const syntheticViewsSummary = resolvedViewPlan.assignments.filter((a) => a.sourceKind === 'synthetic' && a.resolvedBlob).length
          const verifiedViewsSummary = resolvedViewPlan.assignments.filter((a) => a.verification?.passed).length
          const verificationFailedSummary = resolvedViewPlan.assignments.filter((a) => a.verification && !a.verification.passed).length
          const functionalDetailsSummary = resolvedViewPlan.assignments.flatMap((a) => a.verification?.functionalDetailsFound || []).filter(Boolean)
          const functionalMissingSummary = resolvedViewPlan.assignments.flatMap((a) => a.verification?.functionalDetailsMissing || []).filter(Boolean)
          const activeSourceWeb = discoveredSourceWeb?.url
            ? `Source web : ${discoveredSourceWeb.title ? `"${discoveredSourceWeb.title}" ` : ''}(${discoveredSourceWeb.site || 'web'} — ${discoveredSourceWeb.url}).`
            : (referenceSupportPlan.externalReference?.pageUrl
              ? `Source web : ${referenceSupportPlan.externalReference.title ? `"${referenceSupportPlan.externalReference.title}" ` : ''}(${(() => { try { return new URL(referenceSupportPlan.externalReference.pageUrl).hostname.replace(/^www\./, '') } catch { return 'web' } })()} — ${referenceSupportPlan.externalReference.pageUrl}).`
              : '')
          pushMessage('3d', { role: 'assistant', content: [`Intent 3D: ${intent.summary}.`, `Pipeline: ${pipelineLabel}.`, activeSourceWeb, activeMotionPreset ? `Preset applique: ${activeMotionPreset.label}.` : '', intent.movingPartsFocus[0] ? `Sous-ensembles mobiles: ${intent.movingPartsFocus.slice(0, 3).join(', ')}.` : '', intent.anchoredPartsFocus[0] ? `Sous-ensembles fixes: ${intent.anchoredPartsFocus.slice(0, 3).join(', ')}.` : '', referenceSupportPlan.sourceNotes[0] ? `${referenceSupportPlan.sourceNotes[0]}.` : '', referenceVerificationSummary ? `${referenceVerificationSummary}.` : '', resolvedViewPlan.sourceNotes[0] ? `${resolvedViewPlan.sourceNotes[0]}.` : '', referencePassSummary, sceneReport, referenceImagePath ? `Reference: ${referenceImagePath.split('/').slice(-2).join('/')}.` : '', `Mesh ${shapeLabel} ${textureState}${fallbackState}.`, result.multiview_used || directMultiView ? `Multivue active: ${multiviewSummary || `${result.view_count || materializedViewPlan.assignments.length} vues`}.` : '', syntheticViewsSummary > 0 ? `${syntheticViewsSummary} vue(s) generee(s) automatiquement.` : '', verifiedViewsSummary > 0 ? `${verifiedViewsSummary} vue(s) verifiee(s) OK.` : '', verificationFailedSummary > 0 ? `${verificationFailedSummary} vue(s) verification partielle.` : '', functionalDetailsSummary.length > 0 ? `Details fonctionnels confirmes: ${[...new Set(functionalDetailsSummary)].slice(0, 4).join(', ')}.` : '', functionalMissingSummary.length > 0 ? `Details manquants: ${[...new Set(functionalMissingSummary)].slice(0, 3).join(', ')}.` : '', resolvedViewPlan.verificationNotes[0] ? `Verification cle: ${resolvedViewPlan.verificationNotes[0]}.` : '', resolvedViewPlan.lightingNotes[0] ? `Signal lumineux: ${resolvedViewPlan.lightingNotes[0]}.` : '', validationSummary ? validationSummary : '', riggingSummary ? riggingSummary : '', meshFidelitySummary ? meshFidelitySummary : '', intent.motionRisks[0] ? `Risque principal: ${intent.motionRisks[0]}.` : '', result.compatibility_reason ? `Compatibilite: ${result.compatibility_reason}` : ''].filter(Boolean).join(' '), images: [referenceImagePath, activeMeshPath] })
          setSaveDialogData({ module: '3d', sourcePath: activeMeshPath, prompt: currentPrompt, fidelityScore, parameters: { format: result.format ?? 'glb', pipeline: activePipeline, shapeModel: result.shape_model, shapeSubfolder: result.shape_subfolder, shapeWeightFormat: result.shape_weight_format, shapeRuntime: result.shape_runtime, shapeStrategy: result.shape_strategy, shapeOffload: result.shape_offload, textureModel: result.texture_model, textureStrategy: result.texture_strategy, paintOffload: result.paint_offload, textured: result.textured, fallbackUsed: result.fallback_used, compatibilityReason: result.compatibility_reason, shapeInputMode: result.shape_input_mode ?? (directMultiView ? 'multiview' : 'single_view'), multiviewUsed: result.multiview_used ?? directMultiView, viewCount: result.view_count ?? (directMultiView ? materializedViewPlan.assignments.length : 1), multiviewSummary, viewPlanNotes: resolvedViewPlan.sourceNotes.join(' | '), viewVerificationNotes: resolvedViewPlan.verificationNotes.join(' | '), viewLightingNotes: resolvedViewPlan.lightingNotes.join(' | '), viewFunctionalVerification: resolvedViewPlan.functionalVerificationSummary.join(' | '), syntheticViewsGenerated: syntheticViewsSummary, viewsVerifiedOk: verifiedViewsSummary, viewsVerificationPartial: verificationFailedSummary, functionalDetailsConfirmed: functionalDetailsSummary.join(' | '), functionalDetailsMissing: functionalMissingSummary.join(' | '), intentPurpose: intent.purpose, intentSubjectKind: intent.subjectKind, systemClass: intent.systemClass, representationGoal: intent.representationGoal, referenceFraming: intent.referenceFraming, motionReadiness: intent.motionReadiness, pipelineJustifications: intent.pipelineRouting.justifications.map((j) => `${j.point} (${j.risk})`).join(' | '), validationChecks: intent.pipelineRouting.validationChecks.join(' | '), postProcessing: intent.pipelineRouting.postProcessing.join(' | '), validationSummary, riggingSummary, animationFrames: result.animationFrames, rigBones: result.rigBones, euCompliant: result.eu_compliant, license: result.license, motionRisks: intent.motionRisks.join(' | '), movingPartsFocus: intent.movingPartsFocus.join(' | '), anchoredPartsFocus: intent.anchoredPartsFocus.join(' | '), researchQueries: intent.researchQueries.join(' | '), motionPresetId: activeMotionPreset?.id ?? null, motionPresetLabel: activeMotionPreset?.label ?? null, motionPresetDirective: activeMotionPreset?.promptDirective ?? null, dimensionalPrecision: intent.requiresDimensionalPrecision, referenceMode: referenceSupportPlan.referenceMode, dimensionStrategy: referenceSupportPlan.dimensionStrategy, dimensionNotes: referenceSupportPlan.dimensionNotes.join(' | '), referenceSourceNotes: referenceSupportPlan.sourceNotes.join(' | '), referenceVerification: referenceVerificationSummary, externalReferenceTitle: referenceSupportPlan.externalReference?.title ?? null, referenceStyle: directMultiView ? 'direct_multiview' : referenceWorkflow.style, referenceResolution: directMultiView ? `direct:${materializedViewPlan.summary}` : `${referenceWorkflow.width}x${referenceWorkflow.height}`, referenceSteps: directMultiView ? 0 : referenceWorkflow.steps, meshFidelityScore: meshFidelityResult?.score ?? null, meshFidelityMissing: meshFidelityResult?.missingDetails?.join(' | ') ?? null, meshFidelityArtifacts: meshFidelityResult?.artifacts?.join(' | ') ?? null, meshFidelitySuggestions: meshFidelityResult?.suggestions?.join(' | ') ?? null, meshFidelityCategory: meshFidelityResult?.failureCategory ?? null, autoCorrectionPasses: correctionAttempt, autoCorrectionLog: correctionLog.join(' → '), meshGeometryGrade: result.mesh_geometry_grade ?? null, sourceWebSite: discoveredSourceWeb?.site ?? null, sourceWebUrl: discoveredSourceWeb?.url ?? referenceSupportPlan.externalReference?.pageUrl ?? null }, modelLabel: result.shape_model || pipelineLabel })
        },
      })
      // Generation terminee — marquer dans le tracker. L'annonce TTS utilisera
      // le label par défaut du module ("ton modèle 3D est prêt").
      if (activeTrackerIdRef.current) {
        completeGeneration(activeTrackerIdRef.current, {})
        activeTrackerIdRef.current = null
      }
      setViewerFullscreen(true)
    } catch (generationError) {
      if (activeTrackerIdRef.current) {
        failGeneration(activeTrackerIdRef.current, getErrorMessage(generationError))
        activeTrackerIdRef.current = null
      }
      setError(getErrorMessage(generationError, 'Le module 3D a echoue sans detail exploitable.'))
      setProgress('')
    } finally {
      setIsGenerating(false)
      // v77zag: clear the live progress snapshot so the overlay disappears.
      setPhaseSnapshot({ label: '', percent: 0 })
      unlistenRef.current?.()
      unlistenRef.current = null
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    }
  }, [activeOllamaModel, contextFiles, diagnostics.blockingReason, executeWithRuntime, getRecentMessages, hardware, isGenerating, preparePack, prompt, pushMessage, runtimeServices.comfyui.path, selectedMotionPresetId, visionModel])

  const applySelectedMotionPreset = useCallback(() => {
    if (!selectedMotionPreset) return
    const promptToRun = prompt.trim() || latestUserPrompt.trim()
    if (!promptToRun) return
    if (!prompt.trim()) {
      setPrompt(promptToRun)
    }
    void generate(promptToRun)
  }, [generate, latestUserPrompt, prompt, selectedMotionPreset])

  return (
    <><nav aria-label="Espace 3D" className="flex gap-2 px-3 py-3"><button type="button" aria-pressed={workspace === 'model'} className="min-h-11 rounded-xl border border-aurora-border px-4 text-sm" onClick={() => setWorkspace('model')}>Modèle original / génération</button><button type="button" aria-pressed={workspace === 'assembly'} className="min-h-11 rounded-xl border border-aurora-border px-4 text-sm" onClick={() => setWorkspace('assembly')}>Assemblage / impression</button></nav>
    {workspace === 'model' && <label className="mx-3 mb-3 block text-xs text-aurora-text-muted">Ouvrir un modèle dans le viewer original
      <input type="file" accept=".glb" className="block mt-2 w-full min-h-11" onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; if (file.size > 120 * 1024 * 1024) { setError('GLB limité à 120 Mo.'); return } if (importedOriginalUrl.current) URL.revokeObjectURL(importedOriginalUrl.current); importedOriginalUrl.current = URL.createObjectURL(file); setModelUrl(importedOriginalUrl.current); setError(null) }} />
    </label>}
    <div hidden={workspace !== 'assembly'} className="p-3 sm:p-6"><EngineeringExportPanel modelUrl={modelUrl} assemblyOnly active={workspace === 'assembly'} /></div>
    {workspace === 'model' && <div data-model-view="true" className="relative min-h-full flex flex-col">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 aurora-mesh opacity-35" />
        <div className="absolute -top-40 -right-20 h-80 w-80 rounded-full bg-indigo-500/15 blur-3xl" />
        <div className="absolute -bottom-40 -left-20 h-80 w-80 rounded-full bg-violet-500/15 blur-3xl" />
      </div>
      <div className="relative">
      <ThreeDProgressOverlay
        active={isGenerating}
        progress={progress}
        phaseLabel={phaseSnapshot.label || progress}
        phasePercent={phaseSnapshot.percent}
      />
      <ClarificationDialog request={clarification} />
      <RecoveryBanner
        recovery={recovery}
        onRecovered={(result) => {
          if (result.url) setModelUrl(result.url)
        }}
      />
      {pendingJobBanner && pendingJobBanner.status === 'done' && (
        <div className="mx-4 mt-3 rounded-xl border border-emerald-400/40 bg-emerald-500/10 px-4 py-2.5 text-[12px] text-emerald-100">
          <div className="font-semibold mb-0.5">✅ Une generation s est terminee pendant votre absence</div>
          <button
            type="button"
            onClick={() => void recovererResultat(pendingJobBanner.jobId)}
            className="mt-1 rounded-lg border border-emerald-300/40 px-3 py-1.5 text-xs hover:bg-emerald-400/10"
          >Afficher le resultat (viewer + telechargement)</button>
        </div>
      )}
      {pendingJobBanner && pendingJobBanner.status !== 'done' && (
        <div className="mx-4 mt-3 rounded-xl border border-amber-400/40 bg-amber-500/10 px-4 py-2.5 text-[12px] text-amber-100">
          <div className="font-semibold mb-0.5">⏳ Generation 3D en cours sur le PC</div>
          <p className="text-amber-200/80 leading-relaxed">
            L onglet a ete recharge pendant une generation ({pendingJobBanner.status === 'queued' ? 'en file' : 'en cours'}, jobId <code className="font-mono">{pendingJobBanner.jobId.slice(0, 10)}…</code>). Le PC continue le rendu. Relance &laquo; Generer &raquo; avec le meme prompt pour recuperer le mesh, ou
            <button
              type="button"
              onClick={() => void stopGeneration()}
              className="ml-1 underline hover:text-amber-50"
            >arrete-la proprement (le PC cesse de calculer)</button>.
          </p>
        </div>
      )}
      <SaveDialog data={saveDialogData} onClose={() => setSaveDialogData(null)} onSaved={(savedPath) => { addPrompt({ module: '3d', prompt: saveDialogData?.prompt ?? prompt, fidelityScore: saveDialogData?.fidelityScore ?? 90, parameters: saveDialogData?.parameters ?? {}, tags: ['3d'] }); setSaveDialogData(null); setProgress(`Resultat sauvegarde: ${savedPath}`) }} />
      <PromptLibraryPanel open={promptLibraryOpen} onClose={() => setPromptLibraryOpen(false)} currentModule="3d" onUsePrompt={(value) => setPrompt(value)} />
      <StudioHero icon={Box} eyebrow="Atelier 3D" title="Intent 3D, reference auto, reconstruction continue." description="Le module 3D distingue usage visuel, prototype imprimable, piece mecanique, personnage ou membre, recompose une reference FLUX si besoin, puis garde une vraie continuite de session." diagnostics={diagnostics} stats={[{ label: 'Tauri', value: diagnostics.runtimeLabel, tone: diagnostics.runtimeLabel.includes('Tauri') ? 'good' : 'warn' }, { label: 'ComfyUI', value: runtimeServices.comfyui.running ? 'Actif' : runtimeServices.comfyui.available ? 'Auto-start' : 'Absent', tone: runtimeServices.comfyui.running ? 'good' : runtimeServices.comfyui.available ? 'default' : 'warn' }, { label: 'Pack 3D', value: THREE_D_MODEL_PACK_LABEL }]} />
      <div className="grid gap-3 px-2 pb-6 pt-3 sm:gap-4 sm:px-6 sm:pb-8 sm:pt-4 2xl:grid-cols-[22rem_minmax(0,1fr)]">
        <div className="2xl:sticky 2xl:top-4 self-start w-full overflow-y-auto overscroll-contain scroll-shell max-h-[60vh] sm:max-h-[calc(100vh-12rem)] rounded-[1.4rem] sm:rounded-[1.8rem] border border-aurora-border/40 bg-aurora-surface/55 p-3 sm:p-4 space-y-3 sm:space-y-4">
          <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/70 p-4">
            <div className="flex items-start justify-between gap-3">
              <div><p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Brief 3D</p><p className="mt-2 text-sm text-aurora-text">Decris le but final, le type d objet et les contraintes utiles: visuel, impression, mecanique, personnage, membre, assemblage.</p></div>
              <div className="flex items-center gap-2">
                <button onClick={() => setPromptLibraryOpen(true)} title="Bibliotheque de prompts" className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] hover:bg-white/[0.09] text-white/40 hover:text-violet-400 transition-colors"><BookOpen size={14} /></button>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl gradient-accent text-white"><Sparkles size={18} /></div>
              </div>
            </div>
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Ex: piece mecanique imprimable pour charniere de boitier, 42 mm, symetrique, deux points de fixation, prototype propre" rows={6} className="mt-4 w-full resize-none rounded-2xl border border-aurora-border bg-aurora-bg/60 px-3 py-3 text-sm text-aurora-text outline-none transition-colors focus:border-aurora-accent/45" />
            <div className="mt-2 flex items-center gap-2">
              <VoicePushToTalk
                onTranscript={(text) => setPrompt((prev) => (prev.trim() ? `${prev}\n${text}` : text))}
                label="Dicter le brief 3D"
                size={36}
              />
              <span className="text-[11px] text-aurora-text-dim">Décris la pièce, le matériau, les contraintes — la dictée enchaîne plusieurs phrases.</span>
            </div>
          </div>
          <SessionSwitcher module="3d" onSessionChange={(session) => { hydrateSession(session); setContextFiles([]); setPrompt('') }} />
          {uiIntent && <div className="rounded-[1.4rem] border border-aurora-accent/20 bg-aurora-accent/8 px-4 py-3"><p className="text-[11px] uppercase tracking-[0.2em] text-aurora-accent-light">Intent detecte</p><p className="mt-2 text-sm text-aurora-text">{uiIntent.summary}</p><p className="mt-1 text-xs text-aurora-text-muted">{uiIntent.requiresDimensionalPrecision ? 'Mode precision: le module vise un prototype plus technique et protege la lisibilite structurelle.' : 'Mode visuel: le module privilegie une silhouette propre et une reference exploitable.'}</p><p className="mt-2 text-xs font-medium text-aurora-accent-light">Pipeline: {uiIntent.pipelineRouting.pipeline === 'procedural' ? 'Procedural Blender (cinematique exacte)' : uiIntent.pipelineRouting.pipeline === 'photogrammetry' ? 'Atlas en photogrammetrie (fidelite maximale)' : uiIntent.pipelineRouting.pipeline === 'hybrid' ? 'Hybride (procedural + IA)' : uiIntent.pipelineRouting.dreamgaussianPreferred ? 'Atlas (MIT, EU-safe)' : 'Atlas'}</p>{uiIntent.pipelineRouting.justifications.length > 0 && <p className="mt-1 text-xs text-aurora-text-muted">{uiIntent.pipelineRouting.justifications[0].point}</p>}{uiIntent.pipelineRouting.blenderRequired && <p className="mt-1 text-xs text-aurora-text-muted">Blender requis pour post-traitement{uiIntent.pipelineRouting.postProcessing.length > 0 ? `: ${uiIntent.pipelineRouting.postProcessing.slice(0, 2).join(', ')}` : ''}</p>}{uiIntent.pipelineRouting.validationChecks.length > 0 && <p className="mt-1 text-xs text-aurora-text-muted">Validation: {uiIntent.pipelineRouting.validationChecks.slice(0, 3).join(', ')}</p>}{uiIntent.motionGuidance.length > 0 && <p className="mt-2 text-xs text-aurora-text-muted">Mouvement: {uiIntent.motionGuidance[0]}</p>}{uiIntent.movingPartsFocus.length > 0 && <p className="mt-1 text-xs text-aurora-text-muted">Mobiles: {uiIntent.movingPartsFocus.slice(0, 3).join(', ')}</p>}{uiIntent.anchoredPartsFocus.length > 0 && <p className="mt-1 text-xs text-aurora-text-muted">Fixes: {uiIntent.anchoredPartsFocus.slice(0, 3).join(', ')}</p>}{uiIntent.motionRisks.length > 0 && <p className="mt-1 text-xs text-aurora-text-muted">Limite: {uiIntent.motionRisks[0]}</p>}{selectedMotionPreset && <p className="mt-2 text-xs text-aurora-accent-light">Preset actif: {selectedMotionPreset.label}</p>}</div>}
          {referenceSupport && <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface/70 px-4 py-3"><p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Reference pilotee</p><p className="mt-2 text-sm text-aurora-text">{referenceSupport.referenceMode === 'exact_reference' ? 'Sujet de reference connu: le pipeline cherche a coller au sujet reel avant de styliser la vue 3D.' : referenceSupport.referenceMode === 'known_subject' ? 'Sujet connu: le pipeline enrichit la reference 3D avec recherche et filtrage visuel.' : 'Sujet libre: la reference 3D reste surtout pilotee par le brief.'}</p>{referenceSupport.sourceNotes.length > 0 && <p className="mt-2 text-xs leading-relaxed text-aurora-text-muted">{referenceSupport.sourceNotes[0]}</p>}{referenceSupport.dimensionNotes.length > 0 && <p className="mt-2 text-xs leading-relaxed text-aurora-text-muted">Dimensions / rapports trouves: {referenceSupport.dimensionNotes.slice(0, 2).join(' | ')}</p>}</div>}
          {viewPlan && <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface/70 px-4 py-3"><p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Plan De Vues</p><p className="mt-2 text-sm text-aurora-text">{viewPlan.shouldUseMultiview ? 'Le module assemble plusieurs vues coherentes avant reconstruction.' : 'Le module reste en reference principale unique tant qu une multivue fiable n est pas garantie.'}</p>{viewPlan.sourceNotes[0] && <p className="mt-2 text-xs leading-relaxed text-aurora-text-muted">{viewPlan.sourceNotes[0]}</p>}{viewPlan.assignments.some((a) => a.sourceKind === 'synthetic') && <p className="mt-2 text-xs leading-relaxed text-aurora-accent-light">Generation autonome: {viewPlan.assignments.filter((a) => a.sourceKind === 'synthetic').map((a) => a.view).join(', ')} seront generees par FLUX + verifiees.</p>}{viewPlan.assignments.some((a) => a.verification) && <div className="mt-2 space-y-1">{viewPlan.assignments.filter((a) => a.verification).map((a) => <p key={a.view} className={`text-xs leading-relaxed ${a.verification?.passed ? 'text-aurora-text-muted' : 'text-aurora-red/80'}`}>{a.view}: {a.verification?.passed ? 'OK' : 'partiel'}{a.verification?.functionalDetailsFound.length ? ` (${a.verification.functionalDetailsFound.slice(0, 2).join(', ')})` : ''}{a.verification?.functionalDetailsMissing.length ? ` — manque: ${a.verification.functionalDetailsMissing.slice(0, 2).join(', ')}` : ''}</p>)}</div>}{viewPlan.verificationNotes.length > 0 && <p className="mt-2 text-xs leading-relaxed text-aurora-text-muted">Verification: {viewPlan.verificationNotes.slice(0, 2).join(' | ')}</p>}{viewPlan.lightingNotes.length > 0 && <p className="mt-1 text-xs leading-relaxed text-aurora-text-muted">Lumiere / LED: {viewPlan.lightingNotes.slice(0, 2).join(' | ')}</p>}{viewPlan.functionalVerificationSummary && viewPlan.functionalVerificationSummary.length > 0 && <p className="mt-1 text-xs leading-relaxed text-aurora-text-muted">{viewPlan.functionalVerificationSummary[0]}</p>}</div>}
          {recentMessages.length > 0 && <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface/70 px-4 py-3"><p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Continuite</p><p className="mt-2 text-sm text-aurora-text">La session 3D garde les derniers echanges et peut reprendre la derniere reference pour modifier le mesh au lieu de repartir de zero.</p></div>}
          <button
            onClick={toggleMotion}
            disabled={isGenerating}
            className={`flex w-full items-center justify-center gap-2 rounded-[1.4rem] px-4 py-2.5 text-xs font-medium transition-all disabled:opacity-40 ${motionEnabled ? 'gradient-accent text-white' : 'border border-aurora-border/50 bg-aurora-surface/70 text-aurora-text-dim hover:text-aurora-text'}`}
            title="ON: genere une vraie animation (le classifieur LLM choisit le mouvement d'apres le prompt). OFF: mesh statique (garde la pose generee, ex. une pose figee)."
          >
            {motionEnabled ? <span>🎬 Animation: ON — le mouvement sera genere</span> : <span>🧍 Animation: OFF — mesh statique</span>}
          </button>
          <button onClick={() => void generate()} disabled={!canGenerate} className={`flex w-full items-center justify-center gap-2 rounded-[1.4rem] px-4 py-3 text-sm font-medium transition-all ${canGenerate ? 'gradient-accent text-white glow-accent' : 'bg-aurora-surface-2 text-aurora-text-dim opacity-60 cursor-not-allowed'}`}>{isGenerating ? <><Loader2 size={18} className="animate-spin" /><span>{progress || 'Generation...'}</span></> : <><Layers3 size={18} /><span>{recentMessages.length > 0 ? 'Continuer le mesh' : 'Generer le mesh'}</span></>}</button>
          {raisonBlocage && <p className="mt-2 text-center text-xs text-aurora-text-muted">{raisonBlocage}</p>}
          {isGenerating && (
            <button
              onClick={() => void stopGeneration()}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-[1.4rem] border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-sm text-red-300 transition-colors hover:bg-red-500/20"
            >
              Arreter la generation (annulation propre, rien ne tourne en fond)
            </button>
          )}
          <button
            onClick={() => void generatePhysicsChain()}
            disabled={isGenerating || isGeneratingPhysics}
            className="flex w-full items-center justify-center gap-2 rounded-[1.4rem] border border-aurora-border/50 bg-aurora-surface/70 px-4 py-2.5 text-xs font-medium text-aurora-text-dim hover:text-aurora-text disabled:opacity-40"
            title="Genere une chaine physique animee (Bullet rigid bodies + hinge constraints, bake to keyframes). Ideal pour pendule, corde, dominos, swing."
          >
            {isGeneratingPhysics ? <><Loader2 size={14} className="animate-spin" /><span>Simulation physique...</span></> : <span>⛓ Generer chaine physique (Blender)</span>}
          </button>
          {(progress || error) && <div className="space-y-3">{progress && <div className="rounded-2xl border border-aurora-border/40 bg-aurora-surface/70 px-4 py-3"><p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Etat courant</p><p className="mt-2 text-sm text-aurora-text">{progress}</p></div>}{error && <div className="flex items-start gap-2 rounded-2xl border border-aurora-red/25 bg-aurora-red/10 px-3 py-3"><AlertCircle size={16} className="mt-0.5 shrink-0 text-aurora-red" /><p className="text-xs leading-relaxed text-aurora-red">{error}</p></div>}</div>}
          {referenceImageUrl && (
            <div className="rounded-[1.6rem] border border-aurora-border/40 bg-aurora-surface/65 p-4">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Reference 3D</p>
                {(discoveredSourceWeb?.site || referenceSupport?.externalReference?.title) && (
                  <a
                    href={discoveredSourceWeb?.url || referenceSupport?.externalReference?.pageUrl || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-full border border-aurora-accent/40 bg-aurora-accent/10 px-2.5 py-1 text-[11px] font-medium text-aurora-accent hover:bg-aurora-accent/20 transition-colors shadow-sm"
                    title={discoveredSourceWeb?.url || referenceSupport?.externalReference?.pageUrl || ''}
                  >
                    <Globe size={13} />
                    <span className="truncate max-w-[200px] font-mono">{discoveredSourceWeb?.site || referenceSupport?.externalReference?.title}</span>
                  </a>
                )}
              </div>
              {(discoveredSourceWeb?.title || referenceSupport?.externalReference?.title) && (
                <div className="mt-2 rounded-lg bg-aurora-surface/80 p-2 border border-aurora-border/30">
                  <p className="text-xs font-semibold text-aurora-text truncate">
                    {discoveredSourceWeb?.title || referenceSupport?.externalReference?.title}
                  </p>
                  {(discoveredSourceWeb?.url || referenceSupport?.externalReference?.pageUrl) && (
                    <a
                      href={discoveredSourceWeb?.url || referenceSupport?.externalReference?.pageUrl || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-aurora-accent/80 hover:text-aurora-accent hover:underline truncate block mt-0.5"
                    >
                      {discoveredSourceWeb?.url || referenceSupport?.externalReference?.pageUrl}
                    </a>
                  )}
                </div>
              )}
              {referenceSupport?.sourceNotes[0] && <p className="mt-2 text-xs leading-relaxed text-aurora-text-muted">{referenceSupport.sourceNotes[0]}</p>}
              {referenceSupport?.dimensionNotes.length ? <p className="mt-1 text-xs leading-relaxed text-aurora-text-muted">Dimensions / rapports retenus: {referenceSupport.dimensionNotes.slice(0, 2).join(' | ')}</p> : null}
              <img src={referenceImageUrl} alt="Reference 3D" className="mt-3 w-full rounded-[1.2rem] border border-aurora-border/35" />
            </div>
          )}
          <ReferenceInspectorPanel
            analysis={referenceAnalysis}
            referenceImageUrl={referenceImageUrl}
            focusEntityIndex={focusEntityIndexOverride ?? referenceAnalysis?.dominantEntityIndex ?? -1}
            onFocusEntityChange={setFocusEntityIndexOverride}
            manualOverrides={manualColorOverrides}
            onManualOverridesChange={setManualColorOverrides}
            onReanalyze={() => void triggerReferenceAnalysis()}
            isAnalyzing={isAnalyzingReference}
          />
          {contextFiles.length === 0 && !referenceImageUrl && (
            <p className="rounded-lg border border-aurora-border/35 bg-aurora-surface/50 px-3 py-2 text-[11px] text-aurora-text-dim">
              Ajoute une image de reference dans Pieces jointes pour que l IA detecte automatiquement entites, palette et textes.
            </p>
          )}
          {contextFiles.some(estImage) && (
            <button
              onClick={async () => {
                const img = contextFiles.find(estImage)
                if (!img) return
                const { getBridgeUrl: _gb2 } = await import('../utils/runtime')
                setBridgeUrlSelection(_gb2())
                setSelectionCible(img)
              }}
              className="mb-2 w-full rounded-xl border border-dashed border-aurora-accent/40 bg-aurora-accent/[0.06] px-3 py-2 text-xs text-aurora-accent-light transition-colors hover:border-aurora-accent/60"
            >
              Isoler le sujet sur la photo (clic / cadre / auto) — optionnel
            </button>
          )}
          {selectionCible && bridgeUrlSelection && (
            <SubjectSelectPanel
              file={selectionCible}
              bridgeUrl={bridgeUrlSelection}
              onReplaced={(nouveau) => setContextFiles((prev) => prev.map((f) => (f === selectionCible ? nouveau : f)))}
              onClose={() => setSelectionCible(null)}
            />
          )}
          <ContextFilesField files={contextFiles} onFilesChange={setContextFiles} accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm" hint="Ajoute vues de reference, PDF, cotes, schemas ou notes techniques pour enrichir la reconstruction 3D. Pour activer la multivue directe, nomme idealement les images avec front, back, left ou right." />
          <ModuleAssetPackCard pack={assetPack} />
          <StudioDiagnosticsPanel diagnostics={diagnostics} title="Preflight 3D" />
          <ConnectorRecommendationsPanel module="3d" compact />
        </div>
        {viewerFullscreen && viewerWebUrl && (
          <div className="fixed inset-0 z-[130] bg-[#06080d]">
            <iframe
              src={viewerWebUrl}
              title="Aurora Viewer"
              className="h-full w-full border-0"
            />
            <button
              type="button"
              onClick={() => setViewerFullscreen(false)}
              title="Retour au viewer compact"
              className="fixed right-6 top-6 z-[140] flex items-center gap-2 rounded-full border border-aurora-border/60 bg-aurora-surface px-4 py-2 text-sm text-aurora-text hover:bg-aurora-surface-2"
            >✕ Retour au viewer compact</button>
          </div>
        )}
        <div className={viewerFullscreen && !viewerWebUrl ? "fixed inset-0 z-[130] overflow-y-auto bg-[#06080d]" : "min-w-0 rounded-[1.8rem] border border-aurora-border/40 bg-aurora-surface/45 overflow-hidden"}>
          {viewerFullscreen && !viewerWebUrl && (
            <button
              type="button"
              onClick={() => setViewerFullscreen(false)}
              title="Fermer le viewer (retour a l'interface)"
              className="fixed right-6 top-6 z-[140] flex h-11 w-11 items-center justify-center rounded-full border border-aurora-border/60 bg-aurora-surface text-lg text-aurora-text hover:bg-aurora-surface-2"
            >✕</button>
          )}
          <div className="border-b border-aurora-border/30 px-5 py-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Viewer</p><h2 className="mt-1 text-lg font-semibold text-aurora-text">Mesh viewer</h2></div><div className="inline-flex items-center gap-2 rounded-full border border-aurora-border/35 bg-aurora-surface-2 px-3 py-1.5 text-[11px] text-aurora-text-dim">{viewerConfig.lockView ? <Lock size={12} /> : <Orbit size={12} />}<span>{viewerConfig.modeLabel} · {viewerConfig.modeDetail}</span></div></div></div>
          <div className="grid gap-3 p-3 sm:gap-5 sm:p-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
            <div className="min-h-[50vw] sm:min-h-[36rem]">
              {modelUrl ? (
                <div ref={viewerContainerRef} className="relative h-full overflow-hidden rounded-[1.8rem] border border-aurora-border/35 bg-[#091116]">
                  <Scene3D
                    key={`${modelUrl}-${selectedMotionPreset?.id ?? 'default'}-${viewerConfig.modeLabel}-${viewerPbrProfile?.kind ?? 'no-pbr'}-${viewerMaterialMode}`}
                    modelUrl={modelUrl}
                    viewer={viewerConfig}
                    onPartSelect={setSelectedPart}
                    onPartInfo={setSelectedPartInfo}
                    selectAllToken={selectAllToken}
                    onAnimationsLoaded={handleAnimationsLoaded}
                    onModelLoaded={handleModelLoaded}
                    playAnimations={playAnimations}
                    animationSpeed={animationSpeed}
                    manualTime={scrubTime}
                    wireframe={wireframe}
                    materialMode={viewerMaterialMode}
                    activeClipIndex={activeClipIndex}
                    showGrid={showGrid}
                    showAxes={showAxes}
                    showBones={showBones}
                    hdri={hdriPreset}
                    cameraSnap={cameraSnap}
                    onSnapHandled={() => setCameraSnap(null)}
                    onDurationChange={handleDurationChange}
                    onTimeChange={handleTimeChange}
                    onCanvasReady={handleCanvasReady}
                    pbrProfile={viewerPbrProfile}
                  />
                  <div className="pointer-events-none absolute left-3 top-3 z-10 flex flex-wrap gap-1">
                    {(['face', 'side', 'top', 'iso'] as const).map((view) => (
                      <button
                        key={view}
                        onClick={() => setCameraSnap(view)}
                        className="pointer-events-auto rounded-lg border border-aurora-border/60 bg-aurora-surface/80 px-2 py-1 text-[10px] font-medium text-aurora-text-dim hover:text-aurora-accent hover:border-aurora-accent/40 transition-colors"
                        title={`Vue ${view}`}
                      >
                        {view === 'face' ? 'Face' : view === 'side' ? 'Cote' : view === 'top' ? 'Dessus' : 'Iso'}
                      </button>
                    ))}
                  </div>
                  <div className="pointer-events-none absolute right-3 top-3 z-10 flex flex-wrap gap-1.5">
                    <button
                      onClick={() => setShowGrid((v) => !v)}
                      className={`pointer-events-auto rounded-lg border px-2 py-1 text-[10px] font-medium transition-colors ${
                        showGrid ? 'border-aurora-border/60 bg-aurora-surface/80 text-aurora-text-dim' : 'border-aurora-accent/50 bg-aurora-accent/15 text-aurora-accent'
                      }`}
                      title="Basculer la grille"
                    >
                      Grille {showGrid ? 'ON' : 'OFF'}
                    </button>
                    <button
                      onClick={() => setShowAxes((v) => !v)}
                      className={`pointer-events-auto rounded-lg border px-2 py-1 text-[10px] font-medium transition-colors ${
                        showAxes ? 'border-aurora-accent/50 bg-aurora-accent/15 text-aurora-accent' : 'border-aurora-border/60 bg-aurora-surface/80 text-aurora-text-dim hover:text-aurora-text'
                      }`}
                      title="Afficher les axes XYZ"
                    >
                      Axes {showAxes ? 'ON' : 'OFF'}
                    </button>
                    <button
                      onClick={() => setWireframe((v) => !v)}
                      className={`pointer-events-auto rounded-lg border px-2 py-1 text-[10px] font-medium transition-colors ${
                        wireframe ? 'border-aurora-accent/50 bg-aurora-accent/20 text-aurora-accent' : 'border-aurora-border/60 bg-aurora-surface/80 text-aurora-text-dim hover:text-aurora-text'
                      }`}
                      title="Basculer filaire / plein"
                    >
                      Filaire {wireframe ? 'ON' : 'OFF'}
                    </button>
                    <button
                      onClick={() => {
                        if (viewerMaterialMode === 'diagnostic') {
                          setViewerMaterialMode('authored')
                          setColorLoadResult(null)
                        } else {
                          void loadViewerColors()
                        }
                      }}
                      disabled={!modelUrl || isLoadingColors}
                      className={`pointer-events-auto inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-[10px] font-medium transition-colors ${
                        viewerMaterialMode === 'diagnostic'
                          ? 'border-aurora-accent/50 bg-aurora-accent/20 text-aurora-accent'
                          : 'border-aurora-border/60 bg-aurora-surface/80 text-aurora-text-dim hover:text-aurora-text disabled:opacity-40'
                      }`}
                      title="Bake les couleurs depuis la reference, ou active les couleurs d inspection si le mesh est blanc."
                    >
                      <Palette size={11} />
                      {isLoadingColors ? 'Couleurs...' : viewerMaterialMode === 'diagnostic' ? 'Original' : 'Charger couleurs'}
                    </button>
                    <button
                      onClick={() => setShowBones((v) => !v)}
                      className={`pointer-events-auto rounded-lg border px-2 py-1 text-[10px] font-medium transition-colors ${
                        showBones ? 'border-aurora-accent/50 bg-aurora-accent/20 text-aurora-accent' : 'border-aurora-border/60 bg-aurora-surface/80 text-aurora-text-dim hover:text-aurora-text'
                      }`}
                      title="Afficher le squelette / armature pour rigged characters"
                    >
                      Os {showBones ? 'ON' : 'OFF'}
                    </button>
                    <button
                      onClick={() => void rescueMesh()}
                      disabled={!modelUrl || isRescuing}
                      className={`pointer-events-auto rounded-lg border px-2 py-1 text-[10px] font-medium transition-colors ${
                        isRescuing
                          ? 'border-amber-400/50 bg-amber-400/15 text-amber-300'
                          : meshFaceCount > 200_000
                            ? 'border-amber-400/40 bg-amber-400/10 text-amber-200 hover:text-amber-100'
                            : 'border-aurora-border/60 bg-aurora-surface/80 text-aurora-text-dim hover:text-aurora-text disabled:opacity-40'
                      }`}
                      title={
                        meshFaceCount > 200_000
                          ? `Mesh lourd (${meshFaceCount.toLocaleString('fr')} faces). Sauvetage recommande: drop floaters + decimation 45k.`
                          : 'Lance un sauvetage agressif: drop floaters, smoothing fort, decimation. Utilise quand le mesh montre des artefacts.'
                      }
                    >
                      {isRescuing ? '⟳ Sauvetage...' : meshFaceCount > 200_000 ? `⚠ Sauvetage (${Math.round(meshFaceCount / 1000)}k)` : '🛟 Sauvetage'}
                    </button>
                    <button
                      onClick={() => {
                        const r = meshQualityReport
                        if (!r) {
                          window.alert('Pas de rapport mesh disponible — genere un mesh d abord pour avoir un audit.')
                          return
                        }
                        const lines: string[] = []
                        const grade = r.grade ?? '?'
                        const emoji = grade === 'A' ? '✅' : grade === 'B' ? '🟢' : grade === 'C' ? '🟡' : grade === 'D' ? '🟠' : '🔴'
                        lines.push(`${emoji} Grade geometrie: ${grade}`)
                        if (r.qualityOk !== undefined) lines.push(`Qualite OK: ${r.qualityOk ? 'oui' : 'NON — voir issues'}`)
                        lines.push('')
                        if (r.faceCount !== undefined) lines.push(`Faces: ${r.faceCount.toLocaleString('fr')}`)
                        if (r.vertexCount !== undefined) lines.push(`Vertices: ${r.vertexCount.toLocaleString('fr')}`)
                        if (r.extents) lines.push(`Dimensions: ${r.extents.map((v) => v.toFixed(3)).join(' x ')}`)
                        if (r.isWatertight !== undefined) lines.push(`Watertight (etanche): ${r.isWatertight ? 'oui' : 'non'}`)
                        if (r.disconnectedBodies !== undefined && r.disconnectedBodies >= 0) lines.push(`Corps disconnectes: ${r.disconnectedBodies}`)
                        if (r.flatnessRatio !== undefined) lines.push(`Ratio plat: ${r.flatnessRatio.toFixed(3)} ${r.flatnessRatio < 0.12 ? '(⚠ tres plat)' : ''}`)
                        if (r.aspectRatio !== undefined) lines.push(`Ratio aspect: ${r.aspectRatio.toFixed(3)}`)
                        if (r.degenerateFaceCount !== undefined && r.degenerateFaceCount > 0) lines.push(`Faces degenerees: ${r.degenerateFaceCount}`)
                        if (r.surfaceArea !== undefined && r.surfaceArea > 0) lines.push(`Surface: ${r.surfaceArea.toFixed(2)}`)
                        if (r.volume !== undefined && r.volume > 0) lines.push(`Volume: ${r.volume.toFixed(2)}`)
                        if (r.issues && r.issues.length > 0) {
                          lines.push('', 'Issues (bloquantes):')
                          for (const issue of r.issues) lines.push(`  ✗ ${issue}`)
                        }
                        if (r.warnings && r.warnings.length > 0) {
                          lines.push('', 'Avertissements:')
                          for (const w of r.warnings.slice(0, 6)) lines.push(`  ⚠ ${w}`)
                        }
                        if ((!r.issues || r.issues.length === 0) && (!r.warnings || r.warnings.length === 0)) {
                          lines.push('', 'Aucun probleme detecte ✓')
                        }
                        window.alert(lines.join('\n'))
                      }}
                      disabled={!modelUrl}
                      className="pointer-events-auto rounded-lg border border-aurora-border/60 bg-aurora-surface/80 px-2 py-1 text-[10px] font-medium text-aurora-text-dim hover:text-aurora-text disabled:opacity-40 transition-colors"
                      title="Affiche le rapport qualite du mesh: grade A-F, watertight, disconnected bodies, flatness, issues + warnings."
                    >
                      🔍 Inspecter
                    </button>
                    <select
                      value={hdriPreset ?? ''}
                      onChange={(event) => {
                        const next = event.target.value
                        setHdriPreset(next === '' ? null : (next as 'studio' | 'outdoor' | 'indoor'))
                      }}
                      className="pointer-events-auto rounded-lg border border-aurora-border/60 bg-aurora-surface/80 px-2 py-1 text-[10px] font-medium text-aurora-text-dim hover:text-aurora-text outline-none"
                      title="Environnement IBL (Polyhaven HDRI ou RoomEnvironment)"
                    >
                      <option value="studio">HDRI: Studio</option>
                      <option value="outdoor">HDRI: Exterieur</option>
                      <option value="indoor">HDRI: Interieur</option>
                      <option value="">HDRI: Auto</option>
                    </select>
                    <ViewerExportMenu
                      onPng={captureViewerScreenshot}
                      onObj={exportModelAsObj}
                      onStl={exportModelAsStl}
                      onGlb={downloadOriginalGlb}
                    />
                    <button
                      onClick={toggleFullscreen}
                      className="pointer-events-auto rounded-lg border border-aurora-border/60 bg-aurora-surface/80 px-2 py-1 text-[10px] font-medium text-aurora-text-dim hover:text-aurora-text transition-colors"
                      title="Plein ecran"
                    >
                      {isFullscreen ? '⤢ Exit' : '⤢ Plein'}
                    </button>
                  </div>
                  {(rescueProgress || rescueResult) && (
                    <div className="pointer-events-none absolute left-3 bottom-3 z-10 max-w-[60%] rounded-xl border border-aurora-border/60 bg-aurora-surface/85 px-3 py-2 backdrop-blur">
                      <p className="text-[10px] uppercase tracking-[0.18em] text-aurora-text-dim">Sauvetage mesh</p>
                      <p className="mt-1 text-[11px] leading-snug text-aurora-text">
                        {rescueProgress || rescueResult}
                      </p>
                    </div>
                  )}
                  {colorLoadResult && (
                    <div className="pointer-events-none absolute left-3 bottom-20 z-10 max-w-[60%] rounded-xl border border-aurora-border/60 bg-aurora-surface/85 px-3 py-2 backdrop-blur">
                      <p className="text-[10px] uppercase tracking-[0.18em] text-aurora-text-dim">Couleurs viewer</p>
                      <p className="mt-1 text-[11px] leading-snug text-aurora-text">{colorLoadResult}</p>
                    </div>
                  )}
                  {modelUrl && (boneCount > 0 || meshFaceCount > 0) && (
                    <div className="pointer-events-none absolute left-3 top-3 z-10 flex flex-col items-start gap-1 rounded-lg border border-aurora-border/50 bg-aurora-surface/85 px-2.5 py-1.5 backdrop-blur">
                      <span className="text-[9px] uppercase tracking-[0.18em] text-aurora-text-dim">Stats mesh</span>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10px] text-aurora-text">
                        {meshFaceCount > 0 && (
                          <span title="Faces (triangles) totales du mesh">
                            <span className="text-aurora-text-dim">faces</span>{' '}
                            <span className={meshFaceCount > 200_000 ? 'text-amber-300 font-semibold' : ''}>
                              {meshFaceCount >= 1000 ? `${Math.round(meshFaceCount / 1000)}k` : meshFaceCount}
                            </span>
                          </span>
                        )}
                        {boneCount > 0 && (
                          <span title="Bones de tous les SkinnedMesh">
                            <span className="text-aurora-text-dim">os</span>{' '}
                            <span className="text-aurora-accent font-semibold">{boneCount}</span>
                          </span>
                        )}
                        {animationClips.length > 0 && (
                          <span title="Clips d animation embarques dans le GLB">
                            <span className="text-aurora-text-dim">clips</span>{' '}
                            <span className="font-semibold">{animationClips.length}</span>
                          </span>
                        )}
                        {animationDuration > 0 && (
                          <span title="Duree totale du clip actif">
                            <span className="text-aurora-text-dim">dur.</span>{' '}
                            <span className="font-mono">{animationDuration.toFixed(1)}s</span>
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                  {(animationClips.length > 0 || boneCount > 0) && (
                    <div className="pointer-events-auto absolute right-3 bottom-16 z-10 flex flex-col items-end gap-1.5">
                      {boneCount > 0 && (
                        <span className="rounded-lg border border-aurora-accent/50 bg-aurora-accent/10 px-2 py-1 text-[10px] font-medium text-aurora-accent">
                          🦴 {boneCount} os {animationClips.length > 0 ? `· ${animationClips.length} clip${animationClips.length > 1 ? 's' : ''}` : ''}
                        </span>
                      )}
                      {animationClips.length > 0 && (
                        <div className="rounded-lg border border-aurora-border/60 bg-aurora-surface/85 px-2 py-1 text-[10px]">
                          <select
                            value={activeClipIndex}
                            onChange={(event) => setActiveClipIndex(Number(event.target.value))}
                            className="bg-transparent text-aurora-text outline-none"
                          >
                            {animationClips.length > 1 && <option value={-1}>Tous les clips</option>}
                            {animationClips.map((clip, index) => (
                              <option key={`clip-${index}`} value={index}>
                                {clip.name || `Clip ${index + 1}`} · {clip.duration.toFixed(1)}s
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                  )}
                  {animationDuration > 0 && (
                    <div className="pointer-events-none absolute inset-x-3 bottom-3 z-10 rounded-xl border border-aurora-border/60 bg-aurora-surface/80 px-3 py-2 backdrop-blur">
                      <div className="flex items-center gap-2 text-[10px] text-aurora-text-dim">
                        <span className="font-mono">{(scrubTime ?? currentTime).toFixed(2)}s</span>
                        <input
                          type="range"
                          min={0}
                          max={animationDuration}
                          step={0.01}
                          value={scrubTime ?? currentTime}
                          onChange={(event) => {
                            setScrubTime(Number(event.target.value))
                            setPlayAnimations(false)
                          }}
                          className="pointer-events-auto flex-1 accent-aurora-accent"
                        />
                        <span className="font-mono">{animationDuration.toFixed(2)}s</span>
                        {scrubTime != null && (
                          <button
                            onClick={() => {
                              setScrubTime(null)
                              setPlayAnimations(true)
                            }}
                            className="pointer-events-auto rounded-md border border-aurora-accent/40 px-2 py-0.5 text-[9px] font-medium text-aurora-accent hover:bg-aurora-accent/10"
                          >
                            Lire
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ) : referenceImageUrl ? <div className="grid h-full place-items-center rounded-[1.8rem] border border-aurora-border/35 bg-[#091116] p-6"><div className="max-w-xl text-center"><div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.4rem] gradient-accent text-white"><ImageIcon size={26} /></div><p className="mt-4 text-sm text-aurora-text">La référence est prête. L'agent Poly sculpte la géométrie 3D et le viewer l'affichera dès la fin de la génération.</p><img src={referenceImageUrl} alt="Reference en attente du mesh" className="mt-5 max-h-[60vh] rounded-[1.6rem] border border-aurora-border/35 shadow-2xl" /></div></div> : <div className="grid h-full place-items-center rounded-[1.8rem] border border-aurora-border/35 bg-[#091116]"><div className="text-center"><div className="mx-auto flex h-24 w-24 items-center justify-center rounded-[1.8rem] border border-aurora-border bg-aurora-surface-2"><Box size={40} className="text-aurora-text-dim" /></div><p className="mt-4 text-sm text-aurora-text-muted">Decris le but, choisis un preset sur la droite si besoin, puis laisse le module construire une reference propre avant la reconstruction.</p></div></div>}
            </div>
            <div className="space-y-4">
              <EngineeringExportPanel modelUrl={modelUrl} onAssemblyRequested={() => setWorkspace('assembly')} />
              <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface/70 p-4">
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Actions / Mouvement</p>
                <p className="mt-2 text-sm text-aurora-text">{uiIntent ? 'Les boutons affinent la prochaine generation et verrouillent la vue quand la lecture du mouvement doit rester claire.' : 'Ecris un prompt pour faire apparaitre des presets de pose ou d etude mecanique adaptes.'}</p>
                {uiIntent?.motionPresets.length ? <div className="mt-4 grid gap-2">{uiIntent.motionPresets.map((preset) => { const isActive = selectedMotionPresetId === preset.id; return <button key={preset.id} onClick={() => setSelectedMotionPresetId((current) => current === preset.id ? null : preset.id)} className={`rounded-2xl border px-3 py-3 text-left transition-colors ${isActive ? 'border-aurora-accent/50 bg-aurora-accent/15 text-aurora-text' : 'border-aurora-border/35 bg-aurora-surface-2/65 text-aurora-text-muted hover:border-aurora-accent/30 hover:text-aurora-text'}`}><p className="text-sm font-medium">{preset.label}</p><p className="mt-1 text-xs leading-relaxed opacity-80">{preset.description}</p></button> })}</div> : <p className="mt-4 text-xs text-aurora-text-muted">Aucun preset special detecte pour ce prompt. Le module utilisera seulement le brief libre.</p>}
                {selectedMotionPreset && <div className="mt-4 rounded-2xl border border-aurora-accent/20 bg-aurora-accent/8 px-3 py-3"><p className="text-xs uppercase tracking-[0.18em] text-aurora-accent-light">Preset actif</p><p className="mt-2 text-sm text-aurora-text">{selectedMotionPreset.label}</p><p className="mt-1 text-xs leading-relaxed text-aurora-text-muted">{selectedMotionPreset.description}</p><button onClick={applySelectedMotionPreset} disabled={isGenerating || !(prompt.trim() || latestUserPrompt.trim())} className={`mt-3 w-full rounded-xl px-3 py-2 text-xs transition-colors ${isGenerating || !(prompt.trim() || latestUserPrompt.trim()) ? 'border border-aurora-border/35 bg-aurora-surface-2/50 text-aurora-text-dim cursor-not-allowed' : 'gradient-accent text-white'}`}>Regenerer avec ce preset</button><button onClick={() => setSelectedMotionPresetId(null)} className="mt-3 w-full rounded-xl border border-aurora-border/35 bg-aurora-surface-2/70 px-3 py-2 text-xs text-aurora-text-muted transition-colors hover:border-aurora-accent/30 hover:text-aurora-text">Retirer le preset</button></div>}
              </div>
              <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface/70 p-4">
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Lecture viewer</p>
                <p className="mt-2 text-sm text-aurora-text">{viewerConfig.modeLabel}</p>
                <p className="mt-1 text-xs leading-relaxed text-aurora-text-muted">{viewerConfig.modeDetail}</p>
                {selectedPart && <p className="mt-2 text-xs text-aurora-accent-light">Composant selectionne: {selectedPart}</p>}
                <p className="mt-3 text-xs leading-relaxed text-aurora-text-muted">{selectedMotionPreset ? 'La prochaine generation prendra ce preset comme contrainte forte pour la pose ou l etude mecanique.' : isCharacterLike(uiIntent) ? 'Les personnages restent stables par defaut pour mieux lire la pose.' : 'Sans preset, le viewer garde sa rotation douce pour l inspection generale.'}</p>
                <p className="mt-2 text-[10px] text-aurora-text-dim">Clic = selectionner composant · Double-clic = reinitialiser la vue · Molette = zoom · Clic droit = deplacer</p>
              </div>
              {/* v82nu iter3 — Composant info (clic 3D) + Select All */}
              {modelUrl && (
                <div className="rounded-[1.4rem] border border-aurora-accent/25 bg-aurora-accent/5 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-accent">Composant info</p>
                    <button
                      type="button"
                      onClick={() => setSelectAllToken((v) => v + 1)}
                      className="rounded-lg border border-aurora-accent/40 bg-aurora-accent/15 px-2.5 py-1 text-[10px] font-medium text-aurora-accent hover:bg-aurora-accent/25 transition-colors"
                      title="Aggrege les infos sur tout le modele"
                    >
                      Tout selectionner
                    </button>
                  </div>
                  {selectedPartInfo ? (
                    <div className="mt-3 space-y-1.5 text-[11px] leading-relaxed">
                      <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Nom</span><span className="text-aurora-text font-medium truncate max-w-[10rem]" title={selectedPartInfo.name}>{selectedPartInfo.isAll ? `Modele complet` : selectedPartInfo.name}</span></div>
                      {selectedPartInfo.materialName && (
                        <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Materiau</span><span className="text-aurora-text truncate max-w-[10rem]" title={selectedPartInfo.materialName}>{selectedPartInfo.materialName}</span></div>
                      )}
                      {selectedPartInfo.materialKind && (
                        <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Type</span><span className="text-aurora-text">{selectedPartInfo.materialKind}</span></div>
                      )}
                      {selectedPartInfo.baseColorHex && (
                        <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Couleur base</span><span className="inline-flex items-center gap-1.5 text-aurora-text"><span className="inline-block h-3 w-3 rounded-full border border-aurora-border/60" style={{ backgroundColor: selectedPartInfo.baseColorHex }}></span>{selectedPartInfo.baseColorHex}</span></div>
                      )}
                      {selectedPartInfo.emissiveHex && selectedPartInfo.emissiveIntensity != null && selectedPartInfo.emissiveIntensity > 0 && (
                        <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Emission</span><span className="inline-flex items-center gap-1.5 text-aurora-text"><span className="inline-block h-3 w-3 rounded-full border border-aurora-border/60" style={{ backgroundColor: selectedPartInfo.emissiveHex, boxShadow: `0 0 6px ${selectedPartInfo.emissiveHex}` }}></span>{selectedPartInfo.emissiveHex} ×{selectedPartInfo.emissiveIntensity.toFixed(2)}</span></div>
                      )}
                      {selectedPartInfo.metalness != null && (
                        <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Metalness</span><span className="text-aurora-text">{selectedPartInfo.metalness.toFixed(2)}</span></div>
                      )}
                      {selectedPartInfo.roughness != null && (
                        <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Roughness</span><span className="text-aurora-text">{selectedPartInfo.roughness.toFixed(2)}</span></div>
                      )}
                      <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Vertex</span><span className="text-aurora-text">{selectedPartInfo.vertexCount.toLocaleString('fr-FR')}</span></div>
                      <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Triangles</span><span className="text-aurora-text">{selectedPartInfo.triangleCount.toLocaleString('fr-FR')}</span></div>
                      <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Dimensions</span><span className="text-aurora-text">{selectedPartInfo.dimensionsMeters.map((v) => v.toFixed(2)).join(' × ')} m</span></div>
                      {selectedPartInfo.bonesAttached > 0 && (
                        <div className="flex justify-between gap-2"><span className="text-aurora-text-dim">Os</span><span className="text-aurora-text">{selectedPartInfo.bonesAttached}</span></div>
                      )}
                      {selectedPartInfo.hasSkinning && <p className="mt-2 text-[10px] text-aurora-accent-light">Skinning detecte (mesh anime par armature)</p>}
                      {selectedPartInfo.hasMorphTargets && <p className="text-[10px] text-aurora-accent-light">Morph targets disponibles</p>}
                    </div>
                  ) : (
                    <p className="mt-3 text-[11px] leading-relaxed text-aurora-text-muted">Clique sur une face du modele pour afficher ses infos techniques (materiau, polycount, dimensions, animation), ou utilise « Tout selectionner » pour l aggregat.</p>
                  )}
                </div>
              )}
              {/* v82nu iter3 — Custom motion zone (LLM-driven) */}
              {modelUrl && (
                <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface/70 p-4">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Mouvement custom</p>
                  <p className="mt-2 text-xs leading-relaxed text-aurora-text-muted">Decris en texte libre comment animer le modele. L IA classifie en led_emission / fan_pwm / oled_screen / creature_organic / mechanical_simple / rigid_static, puis re-bake si un mesh est charge.</p>
                  <textarea
                    value={customMotionText}
                    onChange={(e) => setCustomMotionText(e.target.value)}
                    placeholder='Ex: "fais clignoter en bleu toutes les 200ms" ou "rotation lente axe Y a 60 RPM"'
                    rows={3}
                    className="mt-3 w-full rounded-xl border border-aurora-border/40 bg-aurora-surface-2/60 px-3 py-2 text-[12px] text-aurora-text placeholder:text-aurora-text-dim focus:border-aurora-accent/50 focus:outline-none"
                    disabled={customMotionStatus === 'classifying' || customMotionStatus === 'baking'}
                  />
                  <button
                    type="button"
                    onClick={handleCustomMotionSubmit}
                    disabled={!customMotionText.trim() || customMotionStatus === 'classifying' || customMotionStatus === 'baking'}
                    className={`mt-3 w-full rounded-xl px-3 py-2 text-xs transition-colors ${
                      !customMotionText.trim() || customMotionStatus === 'classifying' || customMotionStatus === 'baking'
                        ? 'border border-aurora-border/35 bg-aurora-surface-2/50 text-aurora-text-dim cursor-not-allowed'
                        : 'gradient-accent text-white'
                    }`}
                  >
                    {customMotionStatus === 'classifying' ? 'Classification IA…' : customMotionStatus === 'baking' ? 'Bake Blender…' : 'Appliquer le mouvement'}
                  </button>
                  {customMotionResult && (
                    <div className={`mt-3 rounded-xl border px-3 py-2 text-[11px] ${customMotionStatus === 'error' ? 'border-red-500/40 bg-red-500/10 text-red-300' : 'border-aurora-accent/30 bg-aurora-accent/8 text-aurora-text'}`}>
                      <p className="text-[10px] uppercase tracking-[0.18em] text-aurora-accent-light">{customMotionResult.category}</p>
                      <p className="mt-1 leading-relaxed">{customMotionResult.rationale}</p>
                      {customMotionResult.rebake && <p className="mt-1 text-[10px] text-aurora-accent">Mesh re-bake et recharge dans le viewer.</p>}
                    </div>
                  )}
                </div>
              )}
              {animationClips.length > 0 && (
                <div className="rounded-[1.4rem] border border-aurora-accent/30 bg-aurora-accent/5 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-accent">Animations mecaniques</p>
                    <span className="text-[10px] text-aurora-text-dim">{animationClips.length} clip{animationClips.length > 1 ? 's' : ''}</span>
                  </div>
                  <ul className="mt-2 space-y-1">
                    {animationClips.slice(0, 4).map((clip, index) => (
                      <li key={`${clip.name}-${index}`} className="flex items-center justify-between text-[11px]">
                        <span className="truncate text-aurora-text">{clip.name || `Animation ${index + 1}`}</span>
                        <span className="text-aurora-text-dim">{clip.duration.toFixed(1)}s</span>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-3 flex items-center gap-2">
                    <button
                      onClick={() => setPlayAnimations((value) => !value)}
                      className={`flex-1 rounded-xl px-3 py-2 text-[11px] font-medium transition-colors ${
                        playAnimations ? 'gradient-accent text-white' : 'border border-aurora-border bg-aurora-surface-2 text-aurora-text'
                      }`}
                    >
                      {playAnimations ? '⏸ Pause' : '▶ Lecture'}
                    </button>
                    <button
                      onClick={() => setAnimationSpeed((value) => (value >= 2 ? 0.25 : value >= 1 ? 2 : value >= 0.5 ? 1 : 0.5))}
                      className="rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-[11px] font-medium text-aurora-text-dim hover:text-aurora-text transition-colors"
                      title="Changer la vitesse"
                    >
                      ×{animationSpeed.toFixed(animationSpeed < 1 ? 2 : 1)}
                    </button>
                  </div>
                  <div className="mt-3">
                    <input
                      type="range"
                      min="0.1"
                      max="3"
                      step="0.1"
                      value={animationSpeed}
                      onChange={(event) => setAnimationSpeed(Number(event.target.value))}
                      className="w-full accent-aurora-accent"
                    />
                    <div className="flex justify-between text-[9px] text-aurora-text-dim">
                      <span>0.1×</span>
                      <span>1×</span>
                      <span>3×</span>
                    </div>
                  </div>
                  <p className="mt-3 text-[10px] leading-relaxed text-aurora-text-muted">
                    Les animations procedurales (courroie, engrenages, verin, charniere...) sont jouees automatiquement.
                    Mets en pause pour inspecter une position precise.
                  </p>
                </div>
              )}
              {meshFidelity && <div className={`rounded-[1.4rem] border px-4 py-3 ${meshFidelity.passed ? 'border-aurora-accent/20 bg-aurora-accent/8' : 'border-aurora-red/20 bg-aurora-red/8'}`}>
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Fidelite mesh</p>
                <p className={`mt-2 text-sm font-medium ${meshFidelity.passed ? 'text-aurora-accent-light' : meshFidelity.score >= 75 ? 'text-yellow-400' : 'text-aurora-red'}`}>{meshFidelity.score}/100 — {meshFidelity.passed ? 'QA PASS (95%+)' : meshFidelity.score >= 75 ? 'Acceptable mais perfectible' : 'Ameliorations necessaires'}</p>
                {meshFidelity.failureCategory && meshFidelity.failureCategory !== 'none' && <p className="mt-1 text-xs text-aurora-red/70">Categorie: {meshFidelity.failureCategory.replace(/_/g, ' ')}</p>}
                {meshFidelity.notes && <p className="mt-1 text-xs leading-relaxed text-aurora-text-muted">{meshFidelity.notes}</p>}
                {meshFidelity.missingDetails.length > 0 && <div className="mt-2"><p className="text-[10px] uppercase tracking-wider text-aurora-text-dim">Details manquants</p>{meshFidelity.missingDetails.slice(0, 5).map((d, i) => <p key={i} className="mt-1 text-xs text-aurora-text-muted">· {d}</p>)}</div>}
                {meshFidelity.artifacts.length > 0 && <div className="mt-2"><p className="text-[10px] uppercase tracking-wider text-aurora-text-dim">Artefacts</p>{meshFidelity.artifacts.slice(0, 3).map((a, i) => <p key={i} className="mt-1 text-xs text-aurora-red/80">· {a}</p>)}</div>}
                {meshFidelity.suggestions.length > 0 && <div className="mt-2"><p className="text-[10px] uppercase tracking-wider text-aurora-text-dim">Suggestions</p>{meshFidelity.suggestions.slice(0, 3).map((s, i) => <p key={i} className="mt-1 text-xs text-aurora-text-muted">· {s}</p>)}</div>}
              </div>}
            </div>
          </div>
        </div>
      </div>
      </div>

      {refConfirm && (
        // z-[220]: l'ecran de generation (GenerationFxHost) est un plein-ecran
        // opaque a z-index 118. A z-100 cette fenetre etait peinte DESSOUS —
        // invisible et inatteignable, d'ou "en attente de validation" sans rien
        // a valider. Elle doit passer au-dessus de TOUT (FX 118, toasts 200).
        <div className="fixed inset-0 z-[220] grid place-items-center bg-black/70 p-6 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-[1.6rem] border border-aurora-border/50 bg-aurora-surface/95 p-6 shadow-2xl">
            <p className="text-sm font-medium text-aurora-text">{refConfirm.title}</p>
            <p className="mt-1 text-xs text-aurora-text-muted">Validez avant la reconstruction 3D (~20 min). Acceptez si le sujet est le bon; refusez sinon (la photo acceptee est gardee telle quelle).</p>
            <div className={`mt-4 grid gap-3 ${refConfirm.urls.length > 1 ? 'grid-cols-2 sm:grid-cols-3' : 'grid-cols-1'}`}>
              {refConfirm.urls.map((u, i) => (
                <img key={i} src={u} alt={`Reference ${i + 1}`} className="max-h-[46vh] w-full rounded-[1rem] border border-aurora-border/40 bg-[#091116] object-contain" />
              ))}
            </div>
            <textarea value={refReason} onChange={(e) => setRefReason(e.target.value)} placeholder="Optionnel (seulement si vous refusez): pourquoi ca ne va pas / laquelle" rows={2} className="mt-4 w-full rounded-[0.9rem] border border-aurora-border/40 bg-aurora-surface-2 p-3 text-sm text-aurora-text placeholder:text-aurora-text-dim" />
            <div className="mt-4 flex items-center justify-end gap-3">
              <button type="button" onClick={() => { const r = refConfirm.resolve; setRefConfirm(null); r({ accepted: false, reason: refReason }) }} className="flex items-center gap-2 rounded-[0.9rem] border border-aurora-red/50 bg-aurora-red/15 px-4 py-2 text-sm font-medium text-aurora-red transition hover:bg-aurora-red/25"><X size={16} /> Refuser</button>
              <button type="button" onClick={() => { const r = refConfirm.resolve; setRefConfirm(null); r({ accepted: true }) }} className="flex items-center gap-2 rounded-[0.9rem] border border-emerald-500/50 bg-emerald-500/20 px-5 py-2 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/30"><Check size={16} /> Accepter</button>
            </div>
          </div>
        </div>
      )}
    </div>}</>
  )
}
