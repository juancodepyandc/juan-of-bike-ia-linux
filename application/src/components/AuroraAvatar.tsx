import { Suspense, useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import AvatarLive2D, { type FaceFeatures2D } from './AvatarLive2D.tsx'
import AvatarTalkingVideo from './AvatarTalkingVideo.tsx'
import { VRMLoaderPlugin, VRMExpressionPresetName } from '@pixiv/three-vrm'
import type { VRM } from '@pixiv/three-vrm'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { textToPhonemeTimelineV2 } from '../services/voiceFrPhonemizer.ts'
import {
  Box3, BoxGeometry, BufferAttribute, Color, CylinderGeometry, Group,
  MathUtils, Mesh, MeshBasicMaterial, MeshStandardMaterial,
  Plane, PlaneGeometry, PointLight, SphereGeometry, SRGBColorSpace,
  SkinnedMesh, TextureLoader, Vector3,
} from 'three'
import { motion } from 'framer-motion'
import type { MutableRefObject } from 'react'
import type { VoiceLivePhase, RhubarbCue } from '../hooks/useVoiceLive.ts'
import type { AvatarType } from '../types/app.ts'

interface Props {
  phase: VoiceLivePhase
  volumeLevel: number
  speakingAmplitude: number
  avatarPath?: string
  avatarType?: AvatarType
  /** Texte en cours de prononciation — timeline phonémique text-based (fallback Rhubarb) */
  spokenText?: string
  /** Émotion détectée dans la réponse */
  emotion?: 'neutral' | 'happy' | 'thinking' | 'surprised' | 'sad' | 'excited' | 'focused'
  /** Phase 1 — formants RMS temps réel depuis Web Audio API (mis à jour 60fps, pas de re-render) */
  formantsRef?: MutableRefObject<{ low: number; mid: number }>
  /** Phase 2 — élément audio TTS (pour audio.currentTime frame-accurate) */
  audioRef?: MutableRefObject<HTMLAudioElement | null>
  /** Phase 2 — cues Rhubarb Lip Sync {start, end, value: A..H|X} */
  phonemeCuesRef?: MutableRefObject<RhubarbCue[]>
  /** Mode d animation du personnage (humanoid par defaut) */
  animationMode?: 'humanoid' | 'creature' | 'robot' | 'abstract'
}

// ================================================================
//  HELPERS RHUBARB — lookup + mapping vers VRM / morph targets
// ================================================================

/** Cherche la cue active au temps t (recherche arrière = dernier cue commencé) */
function getRhubarbViseme(cues: RhubarbCue[], t: number): string {
  if (!cues.length) return 'X'
  for (let i = cues.length - 1; i >= 0; i--) {
    if (t >= cues[i].start) return cues[i].value
  }
  return 'X'
}

/** Rhubarb A..H → cibles VRM {aa, oh, ee} (scalées par amp) */
function rhubarbToVrm(v: string, amp: number) {
  const a = amp
  switch (v) {
    case 'A': return { aa: a * 0.85, oh: 0,        ee: 0 }
    case 'B': return { aa: a * 0.05, oh: 0,        ee: 0 }
    case 'C': return { aa: 0,        oh: 0,        ee: a * 0.60 }
    case 'D': return { aa: a * 0.20, oh: 0,        ee: a * 0.40 }
    case 'E': return { aa: a * 0.30, oh: a * 0.60, ee: 0 }
    case 'F': return { aa: 0,        oh: a * 0.70, ee: 0 }
    case 'G': return { aa: a * 0.40, oh: 0,        ee: 0 }
    case 'H': return { aa: a * 0.25, oh: 0,        ee: 0 }
    default:  return { aa: 0,        oh: 0,        ee: 0 }  // X silence
  }
}

/** Rhubarb A..H → {jaw, funnel, stretch} pour morph targets */
function rhubarbToMorph(v: string, amp: number) {
  const a = amp
  switch (v) {
    case 'A': return { jaw: a * 0.85, funnel: 0,        stretch: 0 }
    case 'B': return { jaw: a * 0.05, funnel: a * 0.10, stretch: 0 }
    case 'C': return { jaw: a * 0.30, funnel: 0,        stretch: a * 0.35 }
    case 'D': return { jaw: a * 0.40, funnel: 0,        stretch: a * 0.25 }
    case 'E': return { jaw: a * 0.50, funnel: a * 0.40, stretch: 0 }
    case 'F': return { jaw: a * 0.30, funnel: a * 0.65, stretch: 0 }
    case 'G': return { jaw: a * 0.40, funnel: 0,        stretch: 0 }
    case 'H': return { jaw: a * 0.25, funnel: 0,        stretch: a * 0.15 }
    default:  return { jaw: 0,        funnel: 0,        stretch: 0 }
  }
}

// ================================================================
//  PHONEME TIMELINE — fallback text-based quand Rhubarb absent
// ================================================================

type Viseme = 'silence' | 'aa' | 'ee' | 'ii' | 'oo' | 'uu' | 'mm' | 'ff' | 'ss' | 'sh' | 'pp' | 'nn'
interface PhonemeFrame { viseme: Viseme; duration: number; stress: number }

function textToPhonemeTimeline(text: string): PhonemeFrame[] {
  // Le phonemizer rule-based FR (voiceFrPhonemizer) gère les nasales,
  // digraphes (ch/ph/qu/gn), R uvulaire, durées par IPA. Beaucoup plus
  // précis que l'ancien mapping lettre → visème ad-hoc qui vivait ici.
  return textToPhonemeTimelineV2(text)
}

// ================================================================
//  EMOTION DETECTION
// ================================================================

type Emotion = 'neutral' | 'happy' | 'thinking' | 'surprised' | 'sad' | 'excited' | 'focused'

function detectEmotion(text: string, phase: VoiceLivePhase): Emotion {
  if (phase === 'thinking') return 'thinking'
  if (phase === 'listening') return 'focused'
  if (!text) return 'neutral'
  const t = text.toLowerCase()
  if (/\b(haha|rire|drole|amusant|genial|super|cool|bravo|felicitations|:D|\bxD\b)\b/i.test(t)) return 'happy'
  if (/\b(wow|incroyable|extraordinaire|impressionnant|!{2,})\b/i.test(t)) return 'surprised'
  if (/\b(hmm|voyons|alors|en fait|c'est-a-dire|autrement dit|reflechissons)\b/i.test(t)) return 'thinking'
  if (/\b(desole|malheureusement|dommage|triste|echec)\b/i.test(t)) return 'sad'
  if (/\b(exactement|parfait|excellent|magnifique|formidable)\b/i.test(t)) return 'excited'
  if (/\b(analyse|calcul|formule|equation|algorithme|resultat)\b/i.test(t)) return 'focused'
  return 'neutral'
}

// ================================================================
//  VRM AVATAR — @pixiv/three-vrm, expressions natives + lip sync
// ================================================================
function VRMAvatar({
  phase, speakingAmplitude, avatarPath, spokenText, emotion: propEmotion,
  formantsRef, audioRef, phonemeCuesRef,
}: Props & { avatarPath: string }) {
  const { scene, camera } = useThree()
  const vrmRef = useRef<VRM | null>(null)
  const prevAmp = useRef(0)
  const blinkT = useRef(2 + Math.random() * 3)
  const timelineRef = useRef<PhonemeFrame[]>([])
  const frameIdx = useRef(0)
  const frameTime = useRef(0)
  const emotionRef = useRef<Emotion>('neutral')

  useEffect(() => {
    if (spokenText && phase === 'speaking') {
      timelineRef.current = textToPhonemeTimeline(spokenText)
      frameIdx.current = 0; frameTime.current = 0
    }
  }, [spokenText, phase])

  useEffect(() => {
    emotionRef.current = propEmotion || detectEmotion(spokenText || '', phase)
  }, [propEmotion, spokenText, phase])

  useEffect(() => {
    const loader = new GLTFLoader()
    loader.register((parser) => new VRMLoaderPlugin(parser))
    loader.load(avatarPath, (gltf) => {
      const vrm = gltf.userData.vrm as VRM
      if (!vrm) return
      vrm.humanoid?.resetNormalizedPose()
      const leftArm  = vrm.humanoid?.getNormalizedBoneNode('leftUpperArm')
      const rightArm = vrm.humanoid?.getNormalizedBoneNode('rightUpperArm')
      if (leftArm)  leftArm.rotation.z  =  1.1
      if (rightArm) rightArm.rotation.z = -1.1
      const leftFore  = vrm.humanoid?.getNormalizedBoneNode('leftLowerArm')
      const rightFore = vrm.humanoid?.getNormalizedBoneNode('rightLowerArm')
      if (leftFore)  leftFore.rotation.z  =  0.3
      if (rightFore) rightFore.rotation.z = -0.3
      vrm.scene.rotation.y = 0
      scene.add(vrm.scene)
      vrmRef.current = vrm
      vrm.update(0)

      // Cadrage tête + buste
      const headBone = vrm.humanoid?.getNormalizedBoneNode('head')
      if (headBone) {
        const pos = new Vector3()
        headBone.getWorldPosition(pos)
        camera.position.set(pos.x, pos.y + 0.05, pos.z + 0.28)
        camera.lookAt(pos.x, pos.y - 0.04, pos.z)
      } else {
        const box = new Box3().setFromObject(vrm.scene)
        const c = box.getCenter(new Vector3())
        const s = box.getSize(new Vector3())
        camera.position.set(c.x, c.y + s.y * 0.2, c.z + s.y * 0.45)
        camera.lookAt(c.x, c.y + s.y * 0.15, c.z)
      }
    })
    return () => { if (vrmRef.current) { scene.remove(vrmRef.current.scene); vrmRef.current = null } }
  }, [scene, camera, avatarPath])

  useFrame((_, dt) => {
    const vrm = vrmRef.current
    if (!vrm) return
    vrm.update(dt)
    const t = performance.now() / 1000
    const a = MathUtils.lerp(prevAmp.current, speakingAmplitude, 0.4)
    prevAmp.current = a
    const expr = vrm.expressionManager
    if (!expr) return
    const emo = emotionRef.current

    // Clignement
    blinkT.current -= dt
    if (blinkT.current <= 0) {
      blinkT.current = (emo === 'excited' ? 1.5 : phase === 'speaking' ? 2 : 3) + Math.random() * 2.5
      expr.setValue(VRMExpressionPresetName.Blink, 1)
      setTimeout(() => vrm.expressionManager?.setValue(VRMExpressionPresetName.Blink, 0), 130)
    }

    // ─── Lip sync — priorité Rhubarb > text timeline > formants ────────
    if (phase === 'speaking' && a > 0.02) {
      let targets = { aa: 0, oh: 0, ee: 0 }
      const cues = phonemeCuesRef?.current ?? []
      const audioT = audioRef?.current?.currentTime ?? -1

      if (cues.length > 0 && audioT >= 0) {
        // RHUBARB — frame-accurate lip sync
        const v = getRhubarbViseme(cues, audioT)
        targets = rhubarbToVrm(v, a)
      } else if (timelineRef.current.length > 0) {
        // TEXT TIMELINE — fallback phonémique
        frameTime.current += dt * 1000
        while (frameIdx.current < timelineRef.current.length &&
               frameTime.current >= timelineRef.current[frameIdx.current].duration) {
          frameTime.current -= timelineRef.current[frameIdx.current].duration
          frameIdx.current++
        }
        const frame = timelineRef.current[frameIdx.current % timelineRef.current.length]
        const stress = frame.stress * a
        // Boost des voyelles par formants réels si disponibles
        const f = formantsRef?.current ?? { low: 0, mid: 0 }
        const lowBoost = 1 + f.low * 0.5
        const midBoost = 1 + f.mid * 0.5
        switch (frame.viseme) {
          case 'aa': targets.aa = stress * 0.80 * lowBoost; break
          case 'ee': targets.ee = stress * 0.60 * midBoost; break
          case 'ii': targets.ee = stress * 0.70 * midBoost; break
          case 'oo': targets.oh = stress * 0.70 * lowBoost; break
          case 'uu': targets.oh = stress * 0.50 * lowBoost; targets.ee = stress * 0.20; break
          case 'mm': case 'pp': targets.aa = stress * 0.10; break
          case 'ff': targets.ee = stress * 0.30; targets.aa = stress * 0.15; break
          case 'ss': case 'sh': targets.ee = stress * 0.20; break
          case 'nn': targets.aa = stress * 0.20; targets.ee = stress * 0.10; break
          default: break
        }
      } else {
        // FORMANTS SEULS — lecture directe des bandes fréquentielles
        const f = formantsRef?.current ?? { low: 0, mid: 0 }
        targets.aa = a * f.low * 0.75
        targets.oh = a * f.low * 0.35
        targets.ee = a * f.mid * 0.65
      }

      expr.setValue('aa', MathUtils.lerp(expr.getValue('aa') ?? 0, Math.min(1, targets.aa), 0.35))
      expr.setValue('oh', MathUtils.lerp(expr.getValue('oh') ?? 0, Math.min(1, targets.oh), 0.35))
      expr.setValue('ee', MathUtils.lerp(expr.getValue('ee') ?? 0, Math.min(1, targets.ee), 0.35))
    } else {
      expr.setValue('aa', MathUtils.lerp(expr.getValue('aa') ?? 0, 0, 0.15))
      expr.setValue('oh', MathUtils.lerp(expr.getValue('oh') ?? 0, 0, 0.15))
      expr.setValue('ee', MathUtils.lerp(expr.getValue('ee') ?? 0, 0, 0.15))
    }
    // ────────────────────────────────────────────────────────────────────

    // Mimiques émotionnelles
    switch (emo) {
      case 'happy':
        expr.setValue(VRMExpressionPresetName.Happy, MathUtils.lerp(expr.getValue(VRMExpressionPresetName.Happy) ?? 0, 0.35, 0.04))
        expr.setValue(VRMExpressionPresetName.Surprised, 0)
        expr.setValue(VRMExpressionPresetName.LookUp, 0)
        break
      case 'surprised':
        expr.setValue(VRMExpressionPresetName.Surprised, MathUtils.lerp(expr.getValue(VRMExpressionPresetName.Surprised) ?? 0, 0.4, 0.06))
        expr.setValue(VRMExpressionPresetName.Happy, 0.1)
        break
      case 'thinking':
        expr.setValue(VRMExpressionPresetName.Happy, 0)
        expr.setValue(VRMExpressionPresetName.Surprised, 0)
        expr.setValue(VRMExpressionPresetName.LookUp, MathUtils.lerp(expr.getValue(VRMExpressionPresetName.LookUp) ?? 0, 0.35, 0.03))
        break
      case 'sad':
        expr.setValue(VRMExpressionPresetName.Happy, 0)
        expr.setValue(VRMExpressionPresetName.Surprised, 0)
        expr.setValue(VRMExpressionPresetName.LookUp, 0)
        break
      case 'excited':
        expr.setValue(VRMExpressionPresetName.Happy, MathUtils.lerp(expr.getValue(VRMExpressionPresetName.Happy) ?? 0, 0.5, 0.05))
        expr.setValue(VRMExpressionPresetName.Surprised, 0.15)
        break
      case 'focused':
        expr.setValue(VRMExpressionPresetName.Happy, 0.12)
        expr.setValue(VRMExpressionPresetName.Surprised, 0.08)
        break
      default:
        expr.setValue(VRMExpressionPresetName.Happy, MathUtils.lerp(expr.getValue(VRMExpressionPresetName.Happy) ?? 0, 0.08, 0.03))
        expr.setValue(VRMExpressionPresetName.Surprised, MathUtils.lerp(expr.getValue(VRMExpressionPresetName.Surprised) ?? 0, 0, 0.03))
        expr.setValue(VRMExpressionPresetName.LookUp, MathUtils.lerp(expr.getValue(VRMExpressionPresetName.LookUp) ?? 0, 0, 0.03))
    }

    // Mouvements de tête
    const head = vrm.humanoid?.getNormalizedBoneNode('head')
    if (head) {
      if (emo === 'thinking') {
        head.rotation.y = MathUtils.lerp(head.rotation.y, Math.sin(t * 0.3) * 0.1, 0.02)
        head.rotation.x = MathUtils.lerp(head.rotation.x, -0.06, 0.02)
        head.rotation.z = MathUtils.lerp(head.rotation.z, Math.sin(t * 0.15) * 0.04, 0.02)
      } else if (phase === 'speaking') {
        head.rotation.y = MathUtils.lerp(head.rotation.y, Math.sin(t * 0.4) * a * 0.05, 0.04)
        head.rotation.x = MathUtils.lerp(head.rotation.x, Math.sin(t * 0.7) * a * 0.02, 0.04)
        head.rotation.z = MathUtils.lerp(head.rotation.z, 0, 0.03)
      } else if (emo === 'surprised') {
        head.rotation.x = MathUtils.lerp(head.rotation.x, -0.04, 0.05)
        head.rotation.y = MathUtils.lerp(head.rotation.y, 0, 0.03)
        head.rotation.z = MathUtils.lerp(head.rotation.z, 0, 0.03)
      } else {
        head.rotation.y = MathUtils.lerp(head.rotation.y, Math.sin(t * 0.12) * 0.02, 0.02)
        head.rotation.x = MathUtils.lerp(head.rotation.x, 0, 0.02)
        head.rotation.z = MathUtils.lerp(head.rotation.z, 0, 0.02)
      }
    }

    // Respiration
    const spine = vrm.humanoid?.getNormalizedBoneNode('spine')
    if (spine) spine.rotation.x = Math.sin(t * 1.2) * 0.006
  })

  return null
}

// ================================================================
//  GLB AVATAR avec morph targets (jawOpen, eyeBlink, etc.)
// ================================================================
function GLBMorphAvatar({
  phase, speakingAmplitude, avatarPath, spokenText, emotion: propEmotion,
  formantsRef, audioRef, phonemeCuesRef,
}: Props & { avatarPath: string }) {
  const { scene, camera } = useThree()
  const meshRef = useRef<SkinnedMesh | Mesh | null>(null)
  const sceneRef = useRef<any>(null)
  const dictRef = useRef<Record<string, number>>({})
  const prevAmp = useRef(0)
  const blinkT = useRef(2 + Math.random() * 3)
  const timelineRef = useRef<PhonemeFrame[]>([])
  const frameIdx = useRef(0)
  const frameTime = useRef(0)
  const emotionRef = useRef<Emotion>('neutral')

  useEffect(() => {
    if (spokenText && phase === 'speaking') {
      timelineRef.current = textToPhonemeTimeline(spokenText)
      frameIdx.current = 0; frameTime.current = 0
    }
  }, [spokenText, phase])

  useEffect(() => {
    emotionRef.current = propEmotion || detectEmotion(spokenText || '', phase)
  }, [propEmotion, spokenText, phase])

  useEffect(() => {
    const loader = new GLTFLoader()
    loader.load(avatarPath, (gltf) => {
      scene.add(gltf.scene)
      sceneRef.current = gltf.scene

      gltf.scene.traverse((c: any) => {
        if (c.isMesh && c.morphTargetDictionary && c.morphTargetInfluences) {
          meshRef.current = c
          dictRef.current = c.morphTargetDictionary
          // Phase 3 — remplacer tout material non-Standard pour activer le PBR
          if (!(c.material instanceof MeshStandardMaterial)) {
            const oldColor = c.material?.color?.getHex?.() ?? 0xefc9a0
            c.material = new MeshStandardMaterial({
              color: oldColor,
              roughness: 0.55, metalness: 0.04,
            })
          } else if (!c.material.map) {
            c.material.color.setHex(0xefc9a0)
            c.material.roughness = 0.55; c.material.metalness = 0.04; c.material.needsUpdate = true
          }
        }
      })

      // Cadrage tête + buste (top 45 % du modèle)
      const box = new Box3().setFromObject(gltf.scene)
      const center = box.getCenter(new Vector3())
      const size   = box.getSize(new Vector3())
      const bustY  = center.y + size.y * 0.15
      camera.position.set(center.x, bustY, center.z + Math.max(size.x, size.y) * 0.85)
      camera.lookAt(center.x, bustY, center.z)

      // ClippingPlane — masque jambes/bas du corps, ne montre que tête + buste
      const waistCutY = box.min.y + size.y * 0.38
      const clipPlane = new Plane(new Vector3(0, 1, 0), -waistCutY)
      gltf.scene.traverse((c: any) => {
        if (c.isMesh) {
          const mats = Array.isArray(c.material) ? c.material : [c.material]
          mats.forEach((m: any) => { if (m) { m.clippingPlanes = [clipPlane]; m.needsUpdate = true } })
        }
      })
    })
    return () => { if (sceneRef.current) scene.remove(sceneRef.current) }
  }, [scene, camera, avatarPath])

  useFrame((_, dt) => {
    const mesh = meshRef.current as any
    if (!mesh?.morphTargetInfluences) return
    const m = mesh.morphTargetInfluences
    const d = dictRef.current
    const t = performance.now() / 1000
    const a = MathUtils.lerp(prevAmp.current, speakingAmplitude, 0.4)
    prevAmp.current = a
    const emo = emotionRef.current
    const set = (name: string, val: number, rate: number) => {
      if (d[name] !== undefined) m[d[name]] = MathUtils.lerp(m[d[name]], val, rate)
    }

    // Clignement
    blinkT.current -= dt
    if (blinkT.current <= 0) {
      blinkT.current = (emo === 'excited' ? 1.5 : phase === 'speaking' ? 2 : 3) + Math.random() * 2
      set('eyeBlink_L', 1, 1); set('eyeBlink_R', 1, 1)
      setTimeout(() => {
        if (mesh.morphTargetInfluences && d.eyeBlink_L !== undefined) {
          mesh.morphTargetInfluences[d.eyeBlink_L] = 0
          mesh.morphTargetInfluences[d.eyeBlink_R] = 0
        }
      }, 120)
    }

    // ─── Lip sync — priorité Rhubarb > text timeline > formants ────────
    if (phase === 'speaking' && a > 0.02) {
      const cues  = phonemeCuesRef?.current ?? []
      const audioT = audioRef?.current?.currentTime ?? -1
      const f = formantsRef?.current ?? { low: 0, mid: 0 }

      if (cues.length > 0 && audioT >= 0) {
        // RHUBARB
        const { jaw, funnel, stretch } = rhubarbToMorph(getRhubarbViseme(cues, audioT), a)
        set('jawOpen', jaw, 0.4); set('mouthFunnel', funnel, 0.3)
        set('mouthStretch_L', stretch, 0.25); set('mouthStretch_R', stretch, 0.25)
      } else if (timelineRef.current.length > 0) {
        // TEXT TIMELINE + boost formants
        frameTime.current += dt * 1000
        while (frameIdx.current < timelineRef.current.length &&
               frameTime.current >= timelineRef.current[frameIdx.current].duration) {
          frameTime.current -= timelineRef.current[frameIdx.current].duration
          frameIdx.current++
        }
        const frame = timelineRef.current[frameIdx.current % timelineRef.current.length]
        const stress = frame.stress * a
        const lb = 1 + f.low * 0.5; const mb = 1 + f.mid * 0.5
        switch (frame.viseme) {
          case 'aa':
            set('jawOpen', stress * 0.80 * lb, 0.4); set('mouthFunnel', 0, 0.2)
            set('mouthStretch_L', stress * 0.15, 0.25); set('mouthStretch_R', stress * 0.15, 0.25); break
          case 'ee': case 'ii':
            set('jawOpen', stress * 0.30 * mb, 0.4); set('mouthStretch_L', stress * 0.35 * mb, 0.25)
            set('mouthStretch_R', stress * 0.35 * mb, 0.25); set('mouthFunnel', 0, 0.2); break
          case 'oo': case 'uu':
            set('jawOpen', stress * 0.40 * lb, 0.4); set('mouthFunnel', stress * 0.60 * lb, 0.25)
            set('mouthStretch_L', 0, 0.2); set('mouthStretch_R', 0, 0.2); break
          case 'mm': case 'pp':
            set('jawOpen', 0.02, 0.5); set('mouthFunnel', 0, 0.3); break
          case 'ff':
            set('jawOpen', stress * 0.15, 0.4); set('mouthFunnel', stress * 0.20, 0.25); break
          case 'ss': case 'sh':
            set('jawOpen', stress * 0.10, 0.4); set('mouthStretch_L', stress * 0.20, 0.25)
            set('mouthStretch_R', stress * 0.20, 0.25); break
          default:
            set('jawOpen', 0, 0.12); set('mouthFunnel', 0, 0.1)
            set('mouthStretch_L', 0, 0.1); set('mouthStretch_R', 0, 0.1)
        }
        set('mouthLowerDown_L', a * 0.3 * frame.stress, 0.35)
        set('mouthLowerDown_R', a * 0.3 * frame.stress, 0.35)
      } else {
        // FORMANTS seuls
        set('jawOpen', a * f.low * 0.80, 0.4); set('mouthFunnel', a * f.low * 0.40, 0.3)
        set('mouthStretch_L', a * f.mid * 0.35, 0.25); set('mouthStretch_R', a * f.mid * 0.35, 0.25)
        set('mouthLowerDown_L', a * 0.3, 0.35); set('mouthLowerDown_R', a * 0.3, 0.35)
      }

      set('mouthSmile_L', emo === 'happy' || emo === 'excited' ? 0.25 : 0.1, 0.1)
      set('mouthSmile_R', emo === 'happy' || emo === 'excited' ? 0.25 : 0.1, 0.1)
      set('browInnerUp', emo === 'surprised' ? 0.5 : emo === 'thinking' ? 0.35 : a * 0.2, 0.1)
      set('browOuterUp_L', emo === 'surprised' ? 0.3 : 0, 0.1)
      set('browOuterUp_R', emo === 'surprised' ? 0.3 : 0, 0.1)
      set('browDown_L', emo === 'focused' || emo === 'sad' ? 0.2 : 0, 0.08)
      set('browDown_R', emo === 'focused' || emo === 'sad' ? 0.2 : 0, 0.08)
    } else {
      set('jawOpen', 0, 0.12); set('mouthFunnel', 0, 0.1)
      set('mouthStretch_L', 0, 0.1); set('mouthStretch_R', 0, 0.1)
      set('mouthLowerDown_L', 0, 0.1); set('mouthLowerDown_R', 0, 0.1)
      set('mouthSmile_L', emo === 'happy' ? 0.2 : phase === 'listening' ? 0.15 : 0.05, 0.05)
      set('mouthSmile_R', emo === 'happy' ? 0.2 : phase === 'listening' ? 0.15 : 0.05, 0.05)
      set('browInnerUp', emo === 'thinking' ? 0.3 : emo === 'surprised' ? 0.4 : 0, 0.05)
      set('browDown_L', emo === 'focused' ? 0.15 : 0, 0.05)
      set('browDown_R', emo === 'focused' ? 0.15 : 0, 0.05)
    }
    // ────────────────────────────────────────────────────────────────────

    // Mouvements de tête
    if (emo === 'thinking') {
      sceneRef.current.rotation.y = MathUtils.lerp(sceneRef.current.rotation.y, Math.sin(t * 0.3) * 0.1, 0.02)
      sceneRef.current.rotation.x = MathUtils.lerp(sceneRef.current.rotation.x, -0.06, 0.02)
    } else if (phase === 'speaking') {
      sceneRef.current.rotation.y = MathUtils.lerp(sceneRef.current.rotation.y, Math.sin(t * 0.4) * a * 0.05, 0.04)
      sceneRef.current.rotation.x = MathUtils.lerp(sceneRef.current.rotation.x, Math.sin(t * 0.7) * a * 0.02, 0.04)
    } else {
      sceneRef.current.rotation.y = MathUtils.lerp(sceneRef.current.rotation.y, Math.sin(t * 0.12) * 0.02, 0.02)
      sceneRef.current.rotation.x = MathUtils.lerp(sceneRef.current.rotation.x, 0, 0.02)
    }
  })

  return null
}

// ================================================================
//  HELPERS morph targets procéduraux pour GLBStaticAvatar
// ================================================================
function computeFrontUVs(geometry: any, bbox: Box3) {
  const posAttr = geometry.attributes.position
  if (!posAttr) return
  const count = posAttr.count
  const min = bbox.min
  const size = bbox.getSize(new Vector3())
  const uvs = new Float32Array(count * 2)
  for (let i = 0; i < count; i++) {
    uvs[i * 2]     = (posAttr.getX(i) - min.x) / size.x
    uvs[i * 2 + 1] = (posAttr.getY(i) - min.y) / size.y
  }
  geometry.setAttribute('uv', new BufferAttribute(uvs, 2))
}

// ================================================================
//  COULEURS DOMINANTES — extraction via Canvas depuis l image FLUX
// ================================================================

interface ReferenceColors {
  top: [number, number, number]    // haut de l image -> cheveux/coiffe
  mid: [number, number, number]    // milieu de l image -> visage/peau
  bot: [number, number, number]    // bas de l image -> vetement
}

/**
 * Analyse une image via Canvas et extrait 3 couleurs dominantes par bande verticale.
 * Ignore les pixels quasi-blancs (fond) et quasi-transparents.
 */
async function sampleDominantColorsFromUrl(url: string): Promise<ReferenceColors | null> {
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const i = new Image()
      i.crossOrigin = 'anonymous'
      i.onload = () => resolve(i)
      i.onerror = () => reject(new Error('image load failed'))
      i.src = url
    })

    const w = 128
    const h = 128
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) return null
    ctx.drawImage(img, 0, 0, w, h)
    const data = ctx.getImageData(0, 0, w, h).data

    const accumulate = (yStart: number, yEnd: number): [number, number, number] => {
      let r = 0, g = 0, b = 0, n = 0
      for (let y = yStart; y < yEnd; y++) {
        for (let x = 0; x < w; x++) {
          const idx = (y * w + x) * 4
          const pr = data[idx]
          const pg = data[idx + 1]
          const pb = data[idx + 2]
          const pa = data[idx + 3]
          if (pa < 200) continue
          // Ignorer pixels presque blancs (fond FLUX) et presque noirs (ombres profondes)
          const lum = (pr + pg + pb) / 3
          if (lum > 245 || lum < 10) continue
          r += pr; g += pg; b += pb; n++
        }
      }
      if (n === 0) return [200, 180, 160]  // fallback peau chaleureuse
      return [Math.round(r / n), Math.round(g / n), Math.round(b / n)]
    }

    return {
      top: accumulate(0, Math.floor(h * 0.33)),
      mid: accumulate(Math.floor(h * 0.28), Math.floor(h * 0.62)),
      bot: accumulate(Math.floor(h * 0.60), h),
    }
  } catch (err) {
    console.warn('[sampleDominantColorsFromUrl] failed:', err)
    return null
  }
}

/**
 * Applique des vertex colors au mesh: top band = couleur cheveux, mid = peau, bot = vetement.
 * Interpolation smoothstep entre les bandes pour eviter les lignes de demarcation brutales.
 */
function applyHeightBandedVertexColors(
  geometry: any,
  bbox: Box3,
  colors: ReferenceColors,
) {
  const posAttr = geometry.attributes.position
  if (!posAttr) return
  const count = posAttr.count
  const colorArr = new Float32Array(count * 3)

  const minY = bbox.min.y
  const sizeY = bbox.max.y - bbox.min.y || 1

  const [tr, tg, tb] = colors.top.map(v => v / 255)
  const [mr, mg, mb] = colors.mid.map(v => v / 255)
  const [br, bg, bb] = colors.bot.map(v => v / 255)

  const smoothstep = (edge0: number, edge1: number, x: number) => {
    const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)))
    return t * t * (3 - 2 * t)
  }

  for (let i = 0; i < count; i++) {
    const y = posAttr.getY(i)
    const rel = (y - minY) / sizeY  // 0 = bas, 1 = haut

    // Zones:  [0..0.38] = vetement (bot)   [0.38..0.72] = peau (mid)   [0.72..1.0] = cheveux (top)
    const wBot = 1 - smoothstep(0.32, 0.46, rel)
    const wTop = smoothstep(0.65, 0.80, rel)
    const wMid = Math.max(0, 1 - wBot - wTop)

    colorArr[i * 3]     = wBot * br + wMid * mr + wTop * tr
    colorArr[i * 3 + 1] = wBot * bg + wMid * mg + wTop * tg
    colorArr[i * 3 + 2] = wBot * bb + wMid * mb + wTop * tb
  }

  geometry.setAttribute('color', new BufferAttribute(colorArr, 3))
}

function createProceduralMorphs(mesh: Mesh): boolean {
  const geo = mesh.geometry
  const posAttr = geo.attributes.position
  if (!posAttr) return false
  const count = posAttr.count
  geo.computeBoundingBox()
  if (!geo.boundingBox) return false
  const cen = geo.boundingBox.getCenter(new Vector3())
  const sz  = geo.boundingBox.getSize(new Vector3())
  const N = 6
  const morph = Array.from({ length: N }, () => new Float32Array(count * 3))

  for (let i = 0; i < count; i++) {
    const x = posAttr.getX(i), y = posAttr.getY(i), z = posAttr.getZ(i)
    const rx = (x - cen.x) / sz.x, ry = (y - cen.y) / sz.y, rz = (z - cen.z) / sz.z
    if (rz < -0.1) continue
    const fw = Math.min(1, (rz + 0.1) / 0.4)

    // [0] jawOpen
    if (ry < -0.05) {
      const s = Math.min(1, (-ry - 0.05) / 0.3) * fw
      morph[0][i * 3 + 1] = -s * sz.y * 0.10
      morph[0][i * 3 + 2] =  s * sz.y * 0.02
    }
    // [1] eyeBlinkL
    if (ry > 0.06 && ry < 0.30 && rx > 0.01) {
      const s = Math.max(0, 1 - Math.abs(ry - 0.18) / 0.12) * Math.max(0, 1 - Math.abs(rx - 0.14) / 0.16) * fw
      if (s > 0.01) morph[1][i * 3 + 1] = -s * sz.y * 0.025
    }
    // [2] eyeBlinkR
    if (ry > 0.06 && ry < 0.30 && rx < -0.01) {
      const s = Math.max(0, 1 - Math.abs(ry - 0.18) / 0.12) * Math.max(0, 1 - Math.abs(rx + 0.14) / 0.16) * fw
      if (s > 0.01) morph[2][i * 3 + 1] = -s * sz.y * 0.025
    }
    // [3] mouthSmileL
    if (ry > -0.22 && ry < -0.02 && rx > 0.06 && rx < 0.32) {
      const s = Math.max(0, 1 - Math.abs(ry + 0.11) / 0.1) * Math.max(0, 1 - Math.abs(rx - 0.17) / 0.12) * fw
      morph[3][i * 3 + 1] = s * sz.y * 0.035
    }
    // [4] mouthSmileR
    if (ry > -0.22 && ry < -0.02 && rx < -0.06 && rx > -0.32) {
      const s = Math.max(0, 1 - Math.abs(ry + 0.11) / 0.1) * Math.max(0, 1 - Math.abs(rx + 0.17) / 0.12) * fw
      morph[4][i * 3 + 1] = s * sz.y * 0.035
    }
    // [5] mouthFunnel
    if (ry > -0.20 && ry < 0.03 && Math.abs(rx) < 0.16) {
      const s = Math.max(0, 1 - Math.abs(ry + 0.08) / 0.12) * Math.max(0, 1 - Math.abs(rx) / 0.16) * fw
      morph[5][i * 3 + 2] =  s * sz.y * 0.03
      morph[5][i * 3 + 0] = -rx * s * 0.4
    }
  }

  if (!geo.morphAttributes.position) geo.morphAttributes.position = []
  for (const m of morph) geo.morphAttributes.position.push(new BufferAttribute(m, 3))
  geo.morphTargetsRelative = true
  mesh.morphTargetDictionary  = { jawOpen: 0, eyeBlinkL: 1, eyeBlinkR: 2, mouthSmileL: 3, mouthSmileR: 4, mouthFunnel: 5 }
  mesh.morphTargetInfluences  = new Array(N).fill(0)
  mesh.updateMorphTargets()
  return true
}

// ================================================================
//  GLB STATIC AVATAR (Hunyuan3D) — morph targets procéduraux
// ================================================================
function GLBStaticAvatar({
  phase, speakingAmplitude, avatarPath, spokenText, emotion: propEmotion,
  formantsRef, audioRef, phonemeCuesRef,
}: Props & { avatarPath: string }) {
  const { scene, camera } = useThree()
  const meshRef    = useRef<Mesh | null>(null)
  const sceneRef   = useRef<any>(null)
  const prevAmp    = useRef(0)
  const blinkT     = useRef(2 + Math.random() * 3)
  const emotionRef = useRef<Emotion>('neutral')
  const timelineRef = useRef<PhonemeFrame[]>([])
  const frameIdx   = useRef(0)
  const frameTime  = useRef(0)
  const morphOk    = useRef(false)

  useEffect(() => {
    if (spokenText && phase === 'speaking') {
      timelineRef.current = textToPhonemeTimeline(spokenText)
      frameIdx.current = 0; frameTime.current = 0
    }
  }, [spokenText, phase])

  useEffect(() => {
    emotionRef.current = propEmotion || detectEmotion(spokenText || '', phase)
  }, [propEmotion, spokenText, phase])

  useEffect(() => {
    const loader = new GLTFLoader()
    loader.load(avatarPath, (gltf) => {
      scene.add(gltf.scene)
      sceneRef.current = gltf.scene

      let mainMesh: Mesh | null = null
      let maxVerts = 0
      gltf.scene.traverse((c: any) => {
        if (c.isMesh && c.geometry) {
          const cnt = c.geometry.attributes.position?.count || 0
          // Phase 3 — MeshStandardMaterial PBR + couleur peau chaleureuse si pas de texture
          if (!(c.material instanceof MeshStandardMaterial)) {
            c.material = new MeshStandardMaterial({
              color: 0xefc9a0, roughness: 0.55, metalness: 0.04,
            })
          } else if (!c.material.map && !c.geometry.attributes.color) {
            c.material.color.setHex(0xefc9a0)
            c.material.roughness = 0.55; c.material.metalness = 0.04; c.material.needsUpdate = true
          }
          if (cnt > maxVerts) { maxVerts = cnt; mainMesh = c }
        }
      })

      if (mainMesh) {
        meshRef.current = mainMesh
        morphOk.current = createProceduralMorphs(mainMesh)
      }

      // Phase 3 — cadrage tête + buste (top ~50 % du modèle)
      const box = new Box3().setFromObject(gltf.scene)
      const cen = box.getCenter(new Vector3())
      const sz  = box.getSize(new Vector3())
      const bustY = cen.y + sz.y * 0.12
      camera.position.set(cen.x, bustY, cen.z + Math.max(sz.x, sz.y) * 1.05)
      camera.lookAt(cen.x, bustY, cen.z)

      // ClippingPlane — masque jambes/bas du corps, ne montre que tête + buste
      const waistCutY = box.min.y + sz.y * 0.38
      const clipPlane = new Plane(new Vector3(0, 1, 0), -waistCutY)
      gltf.scene.traverse((c: any) => {
        if (c.isMesh) {
          const mats = Array.isArray(c.material) ? c.material : [c.material]
          mats.forEach((m: any) => { if (m) { m.clippingPlanes = [clipPlane]; m.needsUpdate = true } })
        }
      })

      // Charger la texture de reference FLUX si disponible.
      // Strategie combinee:
      //   1. Analyser l image pour extraire les 3 couleurs dominantes (cheveux / peau / vetement)
      //      et les appliquer comme vertex colors selon la hauteur Y du vertex.
      //      -> l avatar prend immediatement les bonnes couleurs (ex: Natsu rose/cremeux/noir)
      //      meme si le UV mapping est imparfait (plus de beige uniforme).
      //   2. En bonus, projeter l image comme texture frontale (UV X/Y) pour plus de detail
      //      sur la face avant uniquement (la mesh arriere garde les vertex colors).
      const refPath = avatarPath.replace(/\.glb$/i, '_ref.png')

      const applyReferenceColors = async () => {
        try {
          const samples = await sampleDominantColorsFromUrl(refPath)
          if (!samples) return

          const meshBox = new Box3().setFromObject(gltf.scene)
          const boxCen = meshBox.getCenter(new Vector3())
          const boxSz  = meshBox.getSize(new Vector3())

          gltf.scene.traverse((c: any) => {
            if (!c.isMesh || !c.geometry) return
            if (!(c.material instanceof MeshStandardMaterial)) return

            // Vertex colors par zone verticale (haut=cheveux, milieu=peau, bas=vetement)
            applyHeightBandedVertexColors(c.geometry, meshBox, samples)

            c.material.vertexColors = true
            // Si pas de texture native, couleur blanche neutre pour laisser les vertex colors s exprimer
            if (!c.material.map) {
              c.material.color.setHex(0xffffff)
            }
            c.material.roughness = 0.55
            c.material.metalness = 0.03
            c.material.needsUpdate = true
          })

          // Bonus: texture frontale projetee (si le mesh avant-gauche/-droite est assez plat)
          new TextureLoader().load(
            refPath,
            (tex) => {
              tex.colorSpace = SRGBColorSpace
              gltf.scene.traverse((c: any) => {
                if (!c.isMesh || !c.geometry) return
                if (!(c.material instanceof MeshStandardMaterial)) return
                if (c.material.map) return  // texture deja presente
                // Projeter en UV frontale seulement (tous les vertex, mais la texture a
                // un fond souvent neutre, combine avec vertex colors ca donne un bon rendu)
                computeFrontUVs(c.geometry, meshBox)
                c.material.map = tex
                // Mix: texture * vertexColor -> les couleurs dominantes adoucissent la texture etiree
                c.material.needsUpdate = true
              })
            },
            undefined,
            (err) => { console.warn('[AuroraAvatar] texture load failed, fallback vertex colors only:', err) },
          )

          void boxCen; void boxSz
        } catch (err) {
          console.warn('[AuroraAvatar] applyReferenceColors failed:', err)
        }
      }
      void applyReferenceColors()
    })
    return () => { if (sceneRef.current) scene.remove(sceneRef.current) }
  }, [scene, camera, avatarPath])

  useFrame((_, dt) => {
    if (!sceneRef.current) return
    const t   = performance.now() / 1000
    const a   = MathUtils.lerp(prevAmp.current, speakingAmplitude, 0.4)
    prevAmp.current = a
    const emo = emotionRef.current
    const mesh = meshRef.current as any
    const m    = mesh?.morphTargetInfluences

    if (m && morphOk.current) {
      const set = (idx: number, val: number, rate: number) => {
        if (idx < m.length) m[idx] = MathUtils.lerp(m[idx], val, rate)
      }

      // Clignement
      blinkT.current -= dt
      if (blinkT.current <= 0) {
        blinkT.current = (emo === 'excited' ? 1.5 : phase === 'speaking' ? 2 : 3) + Math.random() * 2.5
        set(1, 1, 1); set(2, 1, 1)
        setTimeout(() => { if (mesh.morphTargetInfluences) { m[1] = 0; m[2] = 0 } }, 130)
      }

      // ─── Lip sync — priorité Rhubarb > text timeline > formants ────────
      if (phase === 'speaking' && a > 0.02) {
        const cues   = phonemeCuesRef?.current ?? []
        const audioT = audioRef?.current?.currentTime ?? -1
        const f = formantsRef?.current ?? { low: 0, mid: 0 }
        let jaw = 0, funnel = 0, smile = 0

        if (cues.length > 0 && audioT >= 0) {
          const { jaw: j, funnel: fn } = rhubarbToMorph(getRhubarbViseme(cues, audioT), a)
          jaw = j; funnel = fn
        } else if (timelineRef.current.length > 0) {
          frameTime.current += dt * 1000
          while (frameIdx.current < timelineRef.current.length &&
                 frameTime.current >= timelineRef.current[frameIdx.current].duration) {
            frameTime.current -= timelineRef.current[frameIdx.current].duration
            frameIdx.current++
          }
          const fr = timelineRef.current[frameIdx.current % timelineRef.current.length]
          const s  = fr.stress * a
          const lb = 1 + f.low * 0.5; const mb = 1 + f.mid * 0.5
          switch (fr.viseme) {
            case 'aa':               jaw = s * 0.90 * lb;  smile = s * 0.10; break
            case 'ee': case 'ii':    jaw = s * 0.30 * mb;  smile = s * 0.35 * mb; break
            case 'oo': case 'uu':    jaw = s * 0.50 * lb;  funnel = s * 0.70 * lb; break
            case 'mm': case 'pp':    jaw = 0.05; funnel = s * 0.15; break
            case 'ff':               jaw = s * 0.15; funnel = s * 0.20; break
            case 'ss': case 'sh':    jaw = s * 0.10; smile = s * 0.20; break
            case 'nn':               jaw = s * 0.20; break
            default: break
          }
        } else {
          jaw = a * f.low * 0.80; funnel = a * f.low * 0.40
        }

        set(0, jaw, 0.4); set(5, funnel, 0.3); set(3, smile, 0.25); set(4, smile, 0.25)
      } else {
        set(0, 0, 0.12); set(5, 0, 0.1)
        const smTarget = emo === 'happy' || emo === 'excited' ? 0.4
          : emo === 'sad' ? 0 : phase === 'listening' ? 0.15 : 0.05
        set(3, smTarget, 0.05); set(4, smTarget, 0.05)
      }
      // ────────────────────────────────────────────────────────────────────
    }

    // Mouvements de tête
    const sc = sceneRef.current
    if (emo === 'thinking') {
      sc.rotation.y = MathUtils.lerp(sc.rotation.y, Math.sin(t * 0.25) * 0.06, 0.03)
      sc.rotation.z = MathUtils.lerp(sc.rotation.z, Math.sin(t * 0.15) * 0.03, 0.02)
      sc.rotation.x = MathUtils.lerp(sc.rotation.x, -0.04, 0.02)
    } else if (phase === 'speaking') {
      sc.rotation.y = MathUtils.lerp(sc.rotation.y, Math.sin(t * 0.4) * a * 0.05, 0.04)
      sc.rotation.x = MathUtils.lerp(sc.rotation.x, Math.sin(t * 0.7) * a * 0.02, 0.04)
      sc.rotation.z = MathUtils.lerp(sc.rotation.z, 0, 0.03)
    } else if (emo === 'surprised') {
      sc.rotation.x = MathUtils.lerp(sc.rotation.x, -0.03, 0.04)
      sc.rotation.y = MathUtils.lerp(sc.rotation.y, 0, 0.03)
    } else {
      sc.rotation.y = MathUtils.lerp(sc.rotation.y, Math.sin(t * 0.12) * 0.02, 0.02)
      sc.rotation.x = MathUtils.lerp(sc.rotation.x, 0, 0.02)
      sc.rotation.z = MathUtils.lerp(sc.rotation.z, 0, 0.02)
    }
    sc.scale.y = MathUtils.lerp(sc.scale.y, 1 + Math.sin(t * 1.2) * 0.003, 0.05)
  })

  return null
}

// ================================================================
//  IMAGE 2D ANIMÉE — plan subdivisé avec morph targets procéduraux
// ================================================================
function ImageAnimatedAvatar({
  phase, speakingAmplitude, imagePath, spokenText, emotion: propEmotion,
  formantsRef, audioRef, phonemeCuesRef,
}: Props & { imagePath: string }) {
  const { scene, camera } = useThree()
  const meshRef    = useRef<Mesh | null>(null)
  const sceneRef   = useRef<any>(null)
  const prevAmp    = useRef(0)
  const blinkT     = useRef(2 + Math.random() * 3)
  const emotionRef = useRef<Emotion>('neutral')
  const timelineRef = useRef<PhonemeFrame[]>([])
  const frameIdx   = useRef(0)
  const frameTime  = useRef(0)

  useEffect(() => {
    if (spokenText && phase === 'speaking') {
      timelineRef.current = textToPhonemeTimeline(spokenText)
      frameIdx.current = 0; frameTime.current = 0
    }
  }, [spokenText, phase])

  useEffect(() => {
    emotionRef.current = propEmotion || detectEmotion(spokenText || '', phase)
  }, [propEmotion, spokenText, phase])

  useEffect(() => {
    const geo = new PlaneGeometry(2, 2.4, 40, 50)
    const pos = geo.attributes.position
    const count = pos.count
    const N = 6
    const morph = Array.from({ length: N }, () => new Float32Array(count * 3))

    for (let i = 0; i < count; i++) {
      const x = pos.getX(i), y = pos.getY(i)
      const nx = x / 1, ny = y / 1.2

      // [0] jawOpen
      if (ny < -0.05) {
        const s = Math.min(1, (-ny - 0.05) / 0.5) * Math.max(0, 1 - Math.abs(nx) / 0.8)
        morph[0][i * 3 + 1] = -s * 0.18
      }
      // [1] eyeBlinkL
      if (ny > 0.15 && ny < 0.55 && nx > 0.0) {
        const s = Math.max(0, 1 - Math.abs(ny - 0.35) / 0.15) * Math.max(0, 1 - Math.abs(nx - 0.28) / 0.22)
        if (s > 0.01) morph[1][i * 3 + 1] = -s * 0.06
      }
      // [2] eyeBlinkR
      if (ny > 0.15 && ny < 0.55 && nx < 0.0) {
        const s = Math.max(0, 1 - Math.abs(ny - 0.35) / 0.15) * Math.max(0, 1 - Math.abs(nx + 0.28) / 0.22)
        if (s > 0.01) morph[2][i * 3 + 1] = -s * 0.06
      }
      // [3] mouthSmileL
      if (ny > -0.35 && ny < -0.05 && nx > 0.1 && nx < 0.6) {
        const s = Math.max(0, 1 - Math.abs(ny + 0.18) / 0.12) * Math.max(0, 1 - Math.abs(nx - 0.3) / 0.2)
        morph[3][i * 3 + 1] = s * 0.06
      }
      // [4] mouthSmileR
      if (ny > -0.35 && ny < -0.05 && nx < -0.1 && nx > -0.6) {
        const s = Math.max(0, 1 - Math.abs(ny + 0.18) / 0.12) * Math.max(0, 1 - Math.abs(nx + 0.3) / 0.2)
        morph[4][i * 3 + 1] = s * 0.06
      }
      // [5] mouthFunnel
      if (ny > -0.3 && ny < 0.02 && Math.abs(nx) < 0.25) {
        const s = Math.max(0, 1 - Math.abs(ny + 0.14) / 0.15) * Math.max(0, 1 - Math.abs(nx) / 0.25)
        morph[5][i * 3 + 2] =  s * 0.08
        morph[5][i * 3 + 0] = -nx * s * 0.15
      }
    }

    if (!geo.morphAttributes.position) geo.morphAttributes.position = []
    for (const m of morph) geo.morphAttributes.position.push(new BufferAttribute(m, 3))
    geo.morphTargetsRelative = true

    new TextureLoader().load(imagePath, (tex) => {
      tex.colorSpace = SRGBColorSpace
      const mat  = new MeshBasicMaterial({ map: tex, transparent: false })
      const mesh = new Mesh(geo, mat)
      mesh.morphTargetDictionary = { jawOpen: 0, eyeBlinkL: 1, eyeBlinkR: 2, mouthSmileL: 3, mouthSmileR: 4, mouthFunnel: 5 }
      mesh.morphTargetInfluences = new Array(N).fill(0)
      scene.add(mesh)
      meshRef.current  = mesh
      sceneRef.current = mesh
      camera.position.set(0, 0, 1.65)
      camera.lookAt(0, 0, 0)
    })

    return () => { if (sceneRef.current) scene.remove(sceneRef.current); geo.dispose() }
  }, [scene, camera, imagePath])

  useFrame((_, dt) => {
    const mesh = meshRef.current as any
    if (!mesh?.morphTargetInfluences) return
    const m   = mesh.morphTargetInfluences
    const t   = performance.now() / 1000
    const a   = MathUtils.lerp(prevAmp.current, speakingAmplitude, 0.4)
    prevAmp.current = a
    const emo = emotionRef.current

    const set = (idx: number, val: number, rate: number) => {
      if (idx < m.length) m[idx] = MathUtils.lerp(m[idx], val, rate)
    }

    // Clignement
    blinkT.current -= dt
    if (blinkT.current <= 0) {
      blinkT.current = (emo === 'excited' ? 1.5 : phase === 'speaking' ? 2.2 : 3.5) + Math.random() * 2.5
      set(1, 1, 1); set(2, 1, 1)
      setTimeout(() => { if (mesh.morphTargetInfluences) { m[1] = 0; m[2] = 0 } }, 140)
    }

    // ─── Lip sync — priorité Rhubarb > text timeline > formants ────────
    if (phase === 'speaking' && a > 0.02) {
      const cues   = phonemeCuesRef?.current ?? []
      const audioT = audioRef?.current?.currentTime ?? -1
      const f = formantsRef?.current ?? { low: 0, mid: 0 }
      let jaw = 0, funnel = 0, smile = 0

      if (cues.length > 0 && audioT >= 0) {
        const { jaw: j, funnel: fn } = rhubarbToMorph(getRhubarbViseme(cues, audioT), a)
        jaw = j; funnel = fn
      } else if (timelineRef.current.length > 0) {
        frameTime.current += dt * 1000
        while (frameIdx.current < timelineRef.current.length &&
               frameTime.current >= timelineRef.current[frameIdx.current].duration) {
          frameTime.current -= timelineRef.current[frameIdx.current].duration
          frameIdx.current++
        }
        const fr = timelineRef.current[frameIdx.current % timelineRef.current.length]
        const s  = fr.stress * a
        const lb = 1 + f.low * 0.5; const mb = 1 + f.mid * 0.5
        switch (fr.viseme) {
          case 'aa':            jaw = s * 0.85 * lb;  smile = s * 0.08; break
          case 'ee': case 'ii': jaw = s * 0.25 * mb;  smile = s * 0.35 * mb; break
          case 'oo': case 'uu': jaw = s * 0.45 * lb;  funnel = s * 0.70 * lb; break
          case 'mm': case 'pp': jaw = 0.04; break
          case 'ff':            jaw = s * 0.12; funnel = s * 0.20; break
          case 'ss': case 'sh': jaw = s * 0.08; smile = s * 0.20; break
          case 'nn':            jaw = s * 0.18; break
          default: break
        }
      } else {
        jaw = a * f.low * 0.75; funnel = a * f.low * 0.35
      }

      set(0, jaw, 0.45); set(5, funnel, 0.35); set(3, smile, 0.3); set(4, smile, 0.3)
    } else {
      set(0, 0, 0.12); set(5, 0, 0.1)
      const sm = emo === 'happy' || emo === 'excited' ? 0.35
        : emo === 'sad' ? 0 : phase === 'listening' ? 0.12 : 0.04
      set(3, sm, 0.05); set(4, sm, 0.05)
    }
    // ────────────────────────────────────────────────────────────────────

    if (mesh) {
      if (emo === 'thinking') {
        mesh.rotation.y = MathUtils.lerp(mesh.rotation.y, Math.sin(t * 0.25) * 0.04, 0.03)
        mesh.rotation.z = MathUtils.lerp(mesh.rotation.z, Math.sin(t * 0.15) * 0.02, 0.02)
      } else if (phase === 'speaking') {
        mesh.rotation.y = MathUtils.lerp(mesh.rotation.y, Math.sin(t * 0.4) * a * 0.03, 0.04)
        mesh.rotation.x = MathUtils.lerp(mesh.rotation.x, Math.sin(t * 0.7) * a * 0.012, 0.04)
      } else {
        mesh.rotation.y = MathUtils.lerp(mesh.rotation.y, Math.sin(t * 0.12) * 0.015, 0.02)
        mesh.rotation.x = MathUtils.lerp(mesh.rotation.x, 0, 0.02)
        mesh.rotation.z = MathUtils.lerp(mesh.rotation.z, 0, 0.02)
      }
    }
  })

  return null
}

// ================================================================
//  Phase 3 — TÊTE PROCÉDURALE COLORÉE
//  avatarPath = JSON string: '{"skin":"#f0c9a0","eyes":"#4a9eff","hair":"#2c1b0e"}'
// ================================================================
function ProceduralHeadAvatar({
  phase, speakingAmplitude, avatarPath, spokenText, emotion: propEmotion,
  formantsRef, audioRef, phonemeCuesRef,
}: Props & { avatarPath: string }) {
  const { scene, camera } = useThree()
  const groupRef     = useRef<Group | null>(null)
  const mouthRef     = useRef<Mesh | null>(null)
  const leftEyeRef   = useRef<Mesh | null>(null)
  const rightEyeRef  = useRef<Mesh | null>(null)
  const leftBrowRef  = useRef<Mesh | null>(null)
  const rightBrowRef = useRef<Mesh | null>(null)
  const lIrisRef     = useRef<Mesh | null>(null)
  const rIrisRef     = useRef<Mesh | null>(null)
  const lPupilRef    = useRef<Mesh | null>(null)
  const rPupilRef    = useRef<Mesh | null>(null)
  const prevAmp     = useRef(0)
  const blinkT      = useRef(2 + Math.random() * 3)
  const emotionRef  = useRef<Emotion>('neutral')
  const timelineRef = useRef<PhonemeFrame[]>([])
  const frameIdx    = useRef(0)
  const frameTime   = useRef(0)

  useEffect(() => {
    if (spokenText && phase === 'speaking') {
      timelineRef.current = textToPhonemeTimeline(spokenText)
      frameIdx.current = 0; frameTime.current = 0
    }
  }, [spokenText, phase])

  useEffect(() => {
    emotionRef.current = propEmotion || detectEmotion(spokenText || '', phase)
  }, [propEmotion, spokenText, phase])

  useEffect(() => {
    // Parse colors from JSON avatarPath
    let skin = '#f0c9a0', eyes = '#4a9eff', hair = '#2c1b0e'
    try {
      if (avatarPath.startsWith('{')) {
        const c = JSON.parse(avatarPath)
        if (c.skin) skin = c.skin
        if (c.eyes) eyes = c.eyes
        if (c.hair) hair = c.hair
      }
    } catch {}

    const skinMat    = new MeshStandardMaterial({ color: new Color(skin), roughness: 0.65, metalness: 0.02 })
    const eyeWhiteMat = new MeshStandardMaterial({ color: 0xffffff, roughness: 0.18, metalness: 0.0 })
    const irisMat    = new MeshStandardMaterial({ color: new Color(eyes), roughness: 0.08, metalness: 0.3 })
    const pupilMat   = new MeshStandardMaterial({ color: 0x111111, roughness: 0.1, metalness: 0.1 })
    const hairMat    = new MeshStandardMaterial({ color: new Color(hair), roughness: 0.78, metalness: 0.0 })
    const mouthMat   = new MeshStandardMaterial({ color: 0x7a2c2c, roughness: 0.5, metalness: 0.0 })

    const group = new Group()

    // ── Tête ──────────────────────────────────────────────────────
    const headGeo = new SphereGeometry(0.5, 40, 40)
    group.add(new Mesh(headGeo, skinMat))

    // ── Cheveux (dôme supérieur légèrement plus large) ────────────
    const hairGeo = new SphereGeometry(0.535, 40, 40, 0, Math.PI * 2, 0, Math.PI * 0.56)
    const hairMesh = new Mesh(hairGeo, hairMat)
    hairMesh.position.y = 0.03
    group.add(hairMesh)

    // ── Cou ───────────────────────────────────────────────────────
    const neckGeo = new CylinderGeometry(0.17, 0.20, 0.28, 24)
    const neckMesh = new Mesh(neckGeo, skinMat)
    neckMesh.position.y = -0.61
    group.add(neckMesh)

    // ── Buste (épaules) ───────────────────────────────────────────
    const bustGeo = new CylinderGeometry(0.44, 0.52, 0.22, 24)
    const bustMesh = new Mesh(bustGeo, skinMat)
    bustMesh.position.y = -0.84
    group.add(bustMesh)

    // ── Yeux blancs ───────────────────────────────────────────────
    const eyeGeo = new SphereGeometry(0.088, 20, 20)
    const lEye = new Mesh(eyeGeo, eyeWhiteMat)
    lEye.position.set(0.162, 0.062, 0.435)
    group.add(lEye)
    leftEyeRef.current = lEye

    const rEye = new Mesh(eyeGeo, eyeWhiteMat)
    rEye.position.set(-0.162, 0.062, 0.435)
    group.add(rEye)
    rightEyeRef.current = rEye

    // ── Iris colorés ──────────────────────────────────────────────
    const irisGeo = new SphereGeometry(0.058, 16, 16)
    const lIris = new Mesh(irisGeo, irisMat)
    lIris.position.set(0.162, 0.062, 0.470)
    group.add(lIris)
    lIrisRef.current = lIris
    const rIris = new Mesh(irisGeo, irisMat)
    rIris.position.set(-0.162, 0.062, 0.470)
    group.add(rIris)
    rIrisRef.current = rIris

    // ── Pupilles ──────────────────────────────────────────────────
    const pupilGeo = new SphereGeometry(0.028, 12, 12)
    const lPupil = new Mesh(pupilGeo, pupilMat)
    lPupil.position.set(0.162, 0.062, 0.490)
    group.add(lPupil)
    lPupilRef.current = lPupil
    const rPupil = new Mesh(pupilGeo, pupilMat)
    rPupil.position.set(-0.162, 0.062, 0.490)
    group.add(rPupil)
    rPupilRef.current = rPupil

    // ── Sourcils ──────────────────────────────────────────────────
    const browGeo = new BoxGeometry(0.13, 0.022, 0.025)
    const lBrow = new Mesh(browGeo, hairMat)
    lBrow.position.set(0.162, 0.195, 0.435)
    lBrow.rotation.z = -0.12  // léger arc naturel
    group.add(lBrow)
    leftBrowRef.current = lBrow

    const rBrow = new Mesh(browGeo, hairMat)
    rBrow.position.set(-0.162, 0.195, 0.435)
    rBrow.rotation.z = 0.12  // symétrique
    group.add(rBrow)
    rightBrowRef.current = rBrow

    // ── Bouche (disque plat, anime scale.y pour l'ouverture) ──────
    const mouthGeo = new CylinderGeometry(0.095, 0.075, 0.04, 20)
    const mouthMesh = new Mesh(mouthGeo, mouthMat)
    mouthMesh.position.set(0, -0.215, 0.455)
    mouthMesh.rotation.x = Math.PI / 2  // allongé horizontal
    mouthMesh.scale.set(1, 0.18, 1)     // très plat = bouche fermée
    group.add(mouthMesh)
    mouthRef.current = mouthMesh

    scene.add(group)
    groupRef.current = group

    // Cadrage tête + haut buste
    camera.position.set(0, 0.05, 1.70)
    camera.lookAt(0, -0.12, 0)

    return () => {
      scene.remove(group)
      ;[headGeo, hairGeo, neckGeo, bustGeo, eyeGeo, irisGeo, pupilGeo, mouthGeo, browGeo].forEach(g => g.dispose())
      ;[skinMat, eyeWhiteMat, irisMat, pupilMat, hairMat, mouthMat].forEach(m => m.dispose())
      groupRef.current = null; mouthRef.current = null
      leftEyeRef.current = null; rightEyeRef.current = null
      leftBrowRef.current = null; rightBrowRef.current = null
      lIrisRef.current = null; rIrisRef.current = null
      lPupilRef.current = null; rPupilRef.current = null
    }
  }, [scene, camera, avatarPath])

  useFrame((_, dt) => {
    const group = groupRef.current
    if (!group) return
    const t = performance.now() / 1000
    const a = MathUtils.lerp(prevAmp.current, speakingAmplitude, 0.4)
    prevAmp.current = a
    const emo = emotionRef.current

    // ── Clignement ────────────────────────────────────────────────
    blinkT.current -= dt
    if (blinkT.current <= 0) {
      blinkT.current = (emo === 'excited' ? 1.5 : phase === 'speaking' ? 2 : 3) + Math.random() * 2.5
      if (leftEyeRef.current)  leftEyeRef.current.scale.y  = 0.04
      if (rightEyeRef.current) rightEyeRef.current.scale.y = 0.04
      if (lIrisRef.current)  lIrisRef.current.scale.y  = 0.04
      if (rIrisRef.current)  rIrisRef.current.scale.y  = 0.04
      if (lPupilRef.current) lPupilRef.current.scale.y = 0.04
      if (rPupilRef.current) rPupilRef.current.scale.y = 0.04
      setTimeout(() => {
        if (leftEyeRef.current)  leftEyeRef.current.scale.y  = 1
        if (rightEyeRef.current) rightEyeRef.current.scale.y = 1
        if (lIrisRef.current)  lIrisRef.current.scale.y  = 1
        if (rIrisRef.current)  rIrisRef.current.scale.y  = 1
        if (lPupilRef.current) lPupilRef.current.scale.y = 1
        if (rPupilRef.current) rPupilRef.current.scale.y = 1
      }, 130)
    }

    // ── Sourcils — animation émotionnelle ─────────────────────────
    if (leftBrowRef.current && rightBrowRef.current) {
      const lBrow = leftBrowRef.current
      const rBrow = rightBrowRef.current
      let browY   = 0.195   // hauteur repos
      let browRzL = -0.12   // arc repos gauche
      let browRzR =  0.12   // arc repos droite

      if (emo === 'surprised') {
        browY   = MathUtils.lerp(lBrow.position.y, 0.230, 0.06)
        browRzL = MathUtils.lerp(lBrow.rotation.z, -0.06, 0.06)
        browRzR = MathUtils.lerp(rBrow.rotation.z,  0.06, 0.06)
      } else if (emo === 'thinking' || emo === 'focused') {
        browY   = MathUtils.lerp(lBrow.position.y, 0.188, 0.04)
        browRzL = MathUtils.lerp(lBrow.rotation.z, -0.22, 0.04)
        browRzR = MathUtils.lerp(rBrow.rotation.z,  0.22, 0.04)
      } else if (emo === 'happy' || emo === 'excited') {
        browY   = MathUtils.lerp(lBrow.position.y, 0.212, 0.05)
        browRzL = MathUtils.lerp(lBrow.rotation.z, -0.08, 0.05)
        browRzR = MathUtils.lerp(rBrow.rotation.z,  0.08, 0.05)
      } else if (emo === 'sad') {
        browY   = MathUtils.lerp(lBrow.position.y, 0.190, 0.04)
        browRzL = MathUtils.lerp(lBrow.rotation.z,  0.18, 0.04)  // froncé interne
        browRzR = MathUtils.lerp(rBrow.rotation.z, -0.18, 0.04)
      } else {
        browY   = MathUtils.lerp(lBrow.position.y, 0.195, 0.03)
        browRzL = MathUtils.lerp(lBrow.rotation.z, -0.12, 0.03)
        browRzR = MathUtils.lerp(rBrow.rotation.z,  0.12, 0.03)
      }
      lBrow.position.y = browY; lBrow.rotation.z = browRzL
      rBrow.position.y = browY; rBrow.rotation.z = browRzR
    }

    // ── Regard (gaze) — dérive douce + réactivité vocale ──────────
    if (lIrisRef.current && rIrisRef.current && lPupilRef.current && rPupilRef.current) {
      // Drift sinusoïdal lent — regard vivant au repos
      const gazeX = Math.sin(t * 0.18) * 0.012 + Math.sin(t * 0.07) * 0.006
      const gazeY = Math.sin(t * 0.13) * 0.008 + Math.sin(t * 0.05) * 0.004

      // Pendant la parole : léger déplacement naturel
      const speakOffX = phase === 'speaking' ? Math.sin(t * 0.55) * a * 0.010 : 0
      const speakOffY = phase === 'speaking' ? Math.sin(t * 0.40) * a * 0.005 : 0

      const gx = gazeX + speakOffX
      const gy = gazeY + speakOffY

      lIrisRef.current.position.x  = MathUtils.lerp(lIrisRef.current.position.x,  0.162 + gx, 0.06)
      lIrisRef.current.position.y  = MathUtils.lerp(lIrisRef.current.position.y,  0.062 + gy, 0.06)
      rIrisRef.current.position.x  = MathUtils.lerp(rIrisRef.current.position.x, -0.162 + gx, 0.06)
      rIrisRef.current.position.y  = MathUtils.lerp(rIrisRef.current.position.y,  0.062 + gy, 0.06)

      lPupilRef.current.position.x = MathUtils.lerp(lPupilRef.current.position.x,  0.162 + gx, 0.06)
      lPupilRef.current.position.y = MathUtils.lerp(lPupilRef.current.position.y,  0.062 + gy, 0.06)
      rPupilRef.current.position.x = MathUtils.lerp(rPupilRef.current.position.x, -0.162 + gx, 0.06)
      rPupilRef.current.position.y = MathUtils.lerp(rPupilRef.current.position.y,  0.062 + gy, 0.06)
    }

    // ── Lip sync (Rhubarb > timeline > formants) ──────────────────
    if (mouthRef.current) {
      let openTarget = 0
      if (phase === 'speaking' && a > 0.02) {
        const cues  = phonemeCuesRef?.current ?? []
        const audioT = audioRef?.current?.currentTime ?? -1
        const f = formantsRef?.current ?? { low: 0, mid: 0 }

        if (cues.length > 0 && audioT >= 0) {
          const { jaw } = rhubarbToMorph(getRhubarbViseme(cues, audioT), a)
          openTarget = jaw
        } else if (timelineRef.current.length > 0) {
          frameTime.current += dt * 1000
          while (frameIdx.current < timelineRef.current.length &&
                 frameTime.current >= timelineRef.current[frameIdx.current].duration) {
            frameTime.current -= timelineRef.current[frameIdx.current].duration
            frameIdx.current++
          }
          const fr = timelineRef.current[frameIdx.current % timelineRef.current.length]
          const s = fr.stress * a
          const lb = 1 + f.low * 0.5
          switch (fr.viseme) {
            case 'aa':               openTarget = s * 0.90 * lb; break
            case 'ee': case 'ii':    openTarget = s * 0.30; break
            case 'oo': case 'uu':    openTarget = s * 0.55 * lb; break
            case 'mm': case 'pp':    openTarget = 0.06; break
            case 'ff':               openTarget = s * 0.18; break
            case 'ss': case 'sh':    openTarget = s * 0.12; break
            default:                 openTarget = s * 0.22; break
          }
        } else {
          openTarget = a * f.low * 0.75
        }
      }
      // scale.y : 0.18 = fermée, until ~4.5 = grande ouverture
      mouthRef.current.scale.y = MathUtils.lerp(
        mouthRef.current.scale.y,
        Math.max(0.12, Math.min(4.5, 0.18 + openTarget * 4.0)),
        0.3,
      )
    }

    // ── Mouvements de tête ────────────────────────────────────────
    if (emo === 'thinking') {
      group.rotation.y = MathUtils.lerp(group.rotation.y, Math.sin(t * 0.3) * 0.10, 0.02)
      group.rotation.x = MathUtils.lerp(group.rotation.x, -0.06, 0.02)
      group.rotation.z = MathUtils.lerp(group.rotation.z, Math.sin(t * 0.15) * 0.04, 0.02)
    } else if (phase === 'speaking') {
      group.rotation.y = MathUtils.lerp(group.rotation.y, Math.sin(t * 0.4) * a * 0.05, 0.04)
      group.rotation.x = MathUtils.lerp(group.rotation.x, Math.sin(t * 0.7) * a * 0.02, 0.04)
      group.rotation.z = MathUtils.lerp(group.rotation.z, 0, 0.03)
    } else if (emo === 'surprised') {
      group.rotation.x = MathUtils.lerp(group.rotation.x, -0.04, 0.05)
      group.rotation.y = MathUtils.lerp(group.rotation.y, 0, 0.03)
      group.rotation.z = MathUtils.lerp(group.rotation.z, 0, 0.03)
    } else {
      group.rotation.y = MathUtils.lerp(group.rotation.y, Math.sin(t * 0.12) * 0.02, 0.02)
      group.rotation.x = MathUtils.lerp(group.rotation.x, 0, 0.02)
      group.rotation.z = MathUtils.lerp(group.rotation.z, 0, 0.02)
    }

    // Respiration légère
    group.scale.y = MathUtils.lerp(group.scale.y, 1 + Math.sin(t * 1.2) * 0.003, 0.05)
  })

  return null
}

// ================================================================
//  Phase 3 — lumière dynamique colorée (réactivité émotionnelle)
// ================================================================
function DynamicLight({ phase, speakingAmplitude, emotion }: {
  phase: VoiceLivePhase; speakingAmplitude: number; emotion?: string
}) {
  const lightRef = useRef<PointLight>(null)
  useFrame(() => {
    if (!lightRef.current) return
    const t = performance.now() / 1000
    const pulse = phase === 'speaking' ? speakingAmplitude * 0.4 : 0
    lightRef.current.intensity = 0.18 + pulse + Math.sin(t * 1.8) * 0.04
  })
  const col = phase === 'listening' ? '#ff6b3d'
    : phase === 'speaking' ? '#7cf0a5'
    : phase === 'thinking' ? '#74e8ff'
    : '#e8d5ff'
  return <pointLight ref={lightRef} position={[0, 1.5, 1.2]} color={col} distance={5} />
}

// ================================================================
//  COMPOSANT PRINCIPAL
// ================================================================
export default function AuroraAvatar(props: Props) {
  const { phase, volumeLevel, speakingAmplitude } = props
  const avatarPath = props.avatarPath || '/avatars/aurora-default.vrm'
  const avatarType = props.avatarType || 'vrm'
  const gc = phase === 'listening' ? '#ff6b3d' : phase === 'speaking' ? '#7cf0a5' : phase === 'thinking' ? '#74e8ff' : '#fff'

  // ================================================================
  //  LIVE 2D (FLUX image animee) -- sort du canvas Three.js car Canvas 2D pur
  // ================================================================
  // avatarPath pour live2d-flux: JSON stringifie { imageSrc, features }
  // Fallback: si avatarPath n est pas JSON, on le traite comme URL directe d image.
  const live2dConfig = useMemo(() => {
    if (avatarType !== 'live2d-flux') return null
    try {
      const parsed = JSON.parse(avatarPath)
      if (parsed && typeof parsed === 'object' && parsed.imageSrc) {
        return {
          imageSrc: String(parsed.imageSrc),
          features: (parsed.features || null) as FaceFeatures2D | null,
        }
      }
    } catch {
      // pas un JSON -> avatarPath est l URL directe
    }
    return { imageSrc: avatarPath, features: null }
  }, [avatarType, avatarPath])

  // Talking video: MP4 pre-genere par SadTalker -- realisme max
  if (avatarType === 'talking-video') {
    // avatarPath = JSON { videoSrc, idleVideoSrc? } ou URL directe
    let videoSrc: string | null = null
    let idleVideoSrc: string | null = null
    try {
      const parsed = JSON.parse(avatarPath)
      if (parsed && typeof parsed === 'object') {
        videoSrc = parsed.videoSrc || null
        idleVideoSrc = parsed.idleVideoSrc || null
      }
    } catch {
      videoSrc = avatarPath
    }
    return (
      <div className="relative flex items-center justify-center" style={{ width: 220, height: 240 }}>
        <AvatarTalkingVideo
          phase={phase}
          videoSrc={videoSrc}
          idleVideoSrc={idleVideoSrc}
          audioRef={props.audioRef}
          size={220}
        />
        {phase !== 'idle' && (
          <motion.div
            animate={{
              scale: phase === 'speaking' ? 1 + speakingAmplitude * 0.06 : phase === 'listening' ? 1 + volumeLevel * 0.05 : 1,
              opacity: 0.35,
            }}
            className="absolute rounded-2xl pointer-events-none"
            style={{ width: 228, height: 248, border: `2px solid ${gc}40`, filter: 'blur(1px)' }}
          />
        )}
      </div>
    )
  }

  if (avatarType === 'live2d-flux' && live2dConfig) {
    return (
      <div className="relative flex items-center justify-center" style={{ width: 220, height: 240 }}>
        <AvatarLive2D
          phase={phase}
          volumeLevel={volumeLevel}
          speakingAmplitude={speakingAmplitude}
          imageSrc={live2dConfig.imageSrc}
          features={live2dConfig.features}
          spokenText={props.spokenText}
          audioRef={props.audioRef}
          phonemeCuesRef={props.phonemeCuesRef}
          animationMode={props.animationMode || 'humanoid'}
          size={220}
        />
        {phase !== 'idle' && (
          <motion.div
            animate={{
              scale: phase === 'speaking' ? 1 + speakingAmplitude * 0.06 : phase === 'listening' ? 1 + volumeLevel * 0.05 : 1,
              opacity: 0.35,
            }}
            className="absolute rounded-2xl pointer-events-none"
            style={{ width: 228, height: 248, border: `2px solid ${gc}40`, filter: 'blur(1px)' }}
          />
        )}
      </div>
    )
  }

  return (
    <div className="relative flex items-center justify-center" style={{ width: 220, height: 240 }}>
      <div className="rounded-2xl overflow-hidden" style={{ width: 220, height: 240, background: '#0c0d1a' }}>
        {/* Phase 3 — canvas PBR: localClippingEnabled, FOV resserré sur buste */}
        <Canvas
          dpr={[1, 2]}
          camera={{ fov: 36, near: 0.01, far: 100 }}
          gl={{ antialias: true, localClippingEnabled: true }}
          style={{ background: 'linear-gradient(160deg, #14142a 0%, #0a0b18 60%, #0e0a1e 100%)' }}
        >
          {/* Phase 3 — éclairage PBR : ambiance chaude + lumière froide de remplissage + rim light violet */}
          <ambientLight intensity={0.75} color="#fff5e8" />
          <directionalLight position={[1.5, 3, 4]}  intensity={1.20} color="#ffeedd" />
          <directionalLight position={[-1.5, 2, 2]} intensity={0.40} color="#c8e0ff" />
          <directionalLight position={[0, -1, -2]}  intensity={0.10} color="#ffffff" />
          {/* Rim light arrière pour séparer le sujet du fond */}
          <pointLight position={[-1.8, 2.5, -2]} intensity={0.35} color="#9966ff" distance={8} />
          {/* Lumière dynamique réactive à la voix */}
          <DynamicLight phase={phase} speakingAmplitude={speakingAmplitude} emotion={props.emotion} />

          <Suspense fallback={null}>
            {avatarType === 'vrm'         && <VRMAvatar           {...props} avatarPath={avatarPath} />}
            {avatarType === 'glb-morphs'  && <GLBMorphAvatar       {...props} avatarPath={avatarPath} />}
            {avatarType === 'glb-static'  && <GLBStaticAvatar      {...props} avatarPath={avatarPath} />}
            {avatarType === 'image-2d'    && <ImageAnimatedAvatar  {...props} imagePath={avatarPath} />}
            {avatarType === 'procedural'  && <ProceduralHeadAvatar {...props} avatarPath={avatarPath} />}
          </Suspense>
        </Canvas>
      </div>

      {/* Anneau de réactivité */}
      {phase !== 'idle' && (
        <motion.div
          animate={{
            scale: phase === 'speaking' ? 1 + speakingAmplitude * 0.06 : phase === 'listening' ? 1 + volumeLevel * 0.05 : 1,
            opacity: 0.35,
          }}
          className="absolute rounded-2xl pointer-events-none"
          style={{ width: 228, height: 248, border: `2px solid ${gc}40`, filter: 'blur(1px)' }}
        />
      )}

      {/* Particules de réflexion */}
      {phase === 'thinking' && (
        <div className="absolute" style={{ right: -4, top: 20 }}>
          {[0, 1, 2].map(i => (
            <motion.div key={i}
              animate={{ y: [-3, -18 - i * 7], opacity: [0, 0.35, 0] }}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.4 }}
              className="absolute rounded-full"
              style={{ width: 4 + i, height: 4 + i, background: 'rgba(116,232,255,0.3)', right: i * 4 }} />
          ))}
        </div>
      )}
    </div>
  )
}
