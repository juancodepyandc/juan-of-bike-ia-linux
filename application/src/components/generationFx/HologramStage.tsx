/**
 * Hologramme 3D (WebGL) de la génération en cours.
 *
 * Ce qui est montré provient uniquement de la demande en cours :
 *  - vues de référence réelles → nuage reconstruit (silhouette + épaisseur du
 *    profil quand il existe) qui converge à l'arrivée des vues ;
 *  - maillage GLB produit (intermédiaire ou final) → matérialisation de bas en
 *    haut avec un matériau holographique (Fresnel, balayage), couleurs et
 *    textures réelles révélées à l'étape « Matériaux » ;
 *  - pièces STL mesurées (ingénierie) → points échantillonnés réels.
 * Sans donnée : l'émetteur seul, sans sujet inventé.
 *
 * Synchronisation : chaque arrivée de donnée déclenche sa transition au moment
 * où elle est reçue ; chaque événement réel du pipeline émet une onde ; la jauge
 * de l'émetteur affiche la progression mesurée (rotation indéterminée sinon) ;
 * l'étape réelle pilote couleurs, glitch, animation du maillage et finalisation.
 * Rendu borné (≤ 60 i/s, préférence GPU basse consommation) pour ne pas
 * concurrencer le moteur de génération qui occupe la carte graphique.
 */
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { bridgeFetch } from '../../utils/bridgeAuth.ts'
import {
  buildSilhouetteCloud,
  foregroundMask,
  pickViews,
  type RGBAImage,
  type ViewInput,
} from './hologramSources.ts'
import {
  generateHolographicSplats,
  type LiveJointPreview,
  type LivePartGeometryPreview,
} from '../../services/threeDSubAgentsOrchestrator.ts'

export type HologramRef = { url: string; role: string }
export type HologramSource = 'emitter' | 'relief' | 'hull' | 'mesh' | 'parts'
export type HologramStatus = { source: HologramSource; points: number; views: number; note: string }

export type HologramStageProps = {
  accent: string
  phaseIdx: number
  phaseCount: number
  /** progression mesurée 0..1 (même valeur que le HUD), ou -1 si non mesurée */
  readProgress: () => number
  /** instant (Date.now) du dernier événement réel du pipeline */
  readPulseAt: () => number
  refs?: HologramRef[] | null
  meshUrl?: string | null
  parts?: LivePartGeometryPreview[] | null
  joints?: LiveJointPreview[] | null
  done?: boolean
  quality?: 'high' | 'low'
  interactive?: boolean
  onStatus?: (status: HologramStatus) => void
}

type Anim = { from: number; to: number; start: number; dur: number }

const animAt = (a: Anim, now: number) => {
  const t = Math.max(0, Math.min(1, (now - a.start) / Math.max(1, a.dur)))
  const e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
  return a.from + (a.to - a.from) * e
}

const POINT_VERT = /* glsl */ `
attribute vec3 aScatter;
attribute vec3 aColor;
attribute float aSeed;
attribute float aKind;
uniform float uTime;
uniform float uMorph;
uniform float uPixelRatio;
uniform float uSize;
uniform float uGlitch;
uniform float uPulseH;
uniform float uMinY;
uniform float uMaxY;
uniform float uReveal;
varying vec3 vColor;
varying float vAlpha;
varying float vKind;
varying float vBand;
void main() {
  float h01 = clamp((position.y - uMinY) / max(0.001, uMaxY - uMinY), 0.0, 1.0);
  float delay = h01 * 0.5 + aSeed * 0.35;
  float m = smoothstep(delay, delay + 0.22, uMorph);
  vec3 swirl = aScatter;
  float ang = uTime * (0.3 + aSeed * 0.6) + aSeed * 6.2831;
  float c = cos(ang), s = sin(ang);
  swirl.xz = mat2(c, -s, s, c) * swirl.xz;
  swirl.y += sin(uTime * 0.7 + aSeed * 12.0) * 0.06;
  vec3 p = mix(swirl, position, m);
  float slice = floor(p.y * 22.0);
  float rnd = fract(sin(slice * 91.7 + floor(uTime * 8.0) * 13.1) * 43758.5453);
  p.x += step(1.0 - uGlitch * 0.16, rnd) * uGlitch * 0.09 * sin(slice * 12.3 + uTime);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float size = uSize * (aKind > 1.5 ? 1.4 : (aKind > 0.5 ? 0.75 : 1.0));
  gl_PointSize = size * uPixelRatio * (3.2 / max(0.5, -mv.z));
  float revealY = mix(uMinY, uMaxY, uReveal);
  float above = smoothstep(revealY - 0.01, revealY + 0.05, p.y);
  vBand = 1.0 - smoothstep(0.0, 0.05, abs(p.y - revealY));
  float ring = uPulseH >= 0.0 ? (1.0 - smoothstep(0.0, 0.07, abs(h01 - uPulseH))) * (1.0 - uPulseH) : 0.0;
  vAlpha = mix(1.0, 0.12, above) * (aKind > 0.5 && aKind < 1.5 ? 0.38 : 1.0) * mix(0.45, 1.0, m) + ring * 0.7;
  vColor = aColor;
  vKind = aKind;
}
`

const POINT_FRAG = /* glsl */ `
uniform vec3 uAccent;
uniform float uColorMix;
uniform float uTime;
uniform float uOpacity;
varying vec3 vColor;
varying float vAlpha;
varying float vKind;
varying float vBand;
void main() {
  vec2 q = gl_PointCoord - 0.5;
  float d = length(q);
  if (d > 0.5) discard;
  float soft = smoothstep(0.5, 0.0, d);
  vec3 holo = mix(uAccent, vec3(1.0), 0.12 + 0.3 * soft * soft);
  vec3 col = mix(holo, vColor * 1.2 + uAccent * 0.08, uColorMix);
  if (vKind > 1.5) col = mix(col, uAccent * 1.5 + 0.15, 0.55 * (1.0 - uColorMix * 0.6));
  col += vBand * vec3(0.8, 1.0, 1.0) * 0.9;
  float flicker = 0.9 + 0.1 * sin(uTime * 41.0 + gl_FragCoord.y * 0.9);
  float scan = 0.8 + 0.2 * sin(gl_FragCoord.y * 1.3 - uTime * 16.0);
  gl_FragColor = vec4(col * flicker * scan, soft * vAlpha * uOpacity);
}
`

const DISK_VERT = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`

const DISK_FRAG = /* glsl */ `
uniform float uTime;
uniform vec3 uAccent;
uniform float uPulse;
uniform float uBoot;
uniform float uProgress;
varying vec2 vUv;
void main() {
  vec2 p = vUv * 2.0 - 1.0;
  float r = length(p);
  if (r > 1.0) discard;
  float ang = atan(p.y, p.x);
  float a01 = fract(ang / 6.2831853 + 0.25);
  float rings = smoothstep(0.022, 0.0, abs(r - 0.97)) * 0.9 + smoothstep(0.012, 0.0, abs(r - 0.7)) * 0.45;
  float wave = fract(r * 3.0 - uTime * 0.42);
  rings += smoothstep(0.06, 0.0, abs(wave - 0.5) - 0.44) * 0.22 * (1.0 - r);
  float ticks = step(0.9, fract(a01 * 48.0)) * smoothstep(0.84, 0.86, r) * (1.0 - smoothstep(0.9, 0.92, r));
  float band = smoothstep(0.78, 0.8, r) * (1.0 - smoothstep(0.83, 0.85, r));
  float gauge;
  if (uProgress >= 0.0) {
    gauge = band * (step(a01, uProgress) * 1.1 + 0.12);
  } else {
    float head = fract(uTime * 0.18);
    float dist = fract(a01 - head + 1.0);
    gauge = band * (smoothstep(0.22, 0.0, dist) * 0.9 + 0.1);
  }
  float core = exp(-r * r * 10.0) * 0.55;
  float pulse = uPulse >= 0.0 ? smoothstep(0.045, 0.0, abs(r - uPulse)) * (1.0 - uPulse) : 0.0;
  float alpha = (rings + ticks * 0.55 + gauge + core + pulse) * uBoot;
  vec3 col = uAccent * (0.65 + core) + vec3(pulse + gauge * 0.35);
  gl_FragColor = vec4(col, clamp(alpha, 0.0, 1.0));
}
`

const CONE_FRAG = /* glsl */ `
uniform float uTime;
uniform vec3 uAccent;
uniform float uBoot;
varying vec2 vUv;
void main() {
  float a = pow(1.0 - vUv.y, 1.7) * 0.15 * uBoot;
  float streaks = 0.6 + 0.4 * sin(vUv.x * 6.2831853 * 19.0 + uTime * 1.4) * sin(vUv.x * 6.2831853 * 7.0 - uTime * 0.6);
  float travel = smoothstep(0.1, 0.0, abs(fract(vUv.y - uTime * 0.22) - 0.5) - 0.4) * 0.4;
  gl_FragColor = vec4(uAccent * 1.1, a * streaks + a * travel);
}
`

function makeHoloMaterial(
  orig: THREE.Material,
  common: { uTime: THREE.IUniform; uAccent: THREE.IUniform; uColorMix: THREE.IUniform },
  meshU: { uReveal: THREE.IUniform; uOpacity: THREE.IUniform },
): THREE.MeshStandardMaterial {
  const src = orig as Partial<THREE.MeshStandardMaterial>
  const mat = new THREE.MeshStandardMaterial({
    color: src.color ? src.color.clone() : new THREE.Color(0xffffff),
    map: src.map ?? null,
    vertexColors: Boolean(src.vertexColors),
    roughness: 0.55,
    metalness: 0.05,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
  })
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uTime = common.uTime
    shader.uniforms.uAccent = common.uAccent
    shader.uniforms.uColorMix = common.uColorMix
    shader.uniforms.uReveal = meshU.uReveal
    shader.uniforms.uOpacity = meshU.uOpacity
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vHoloWorld;')
      .replace('#include <project_vertex>', '#include <project_vertex>\nvHoloWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;')
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        '#include <common>\nvarying vec3 vHoloWorld;\nuniform float uTime;\nuniform vec3 uAccent;\nuniform float uColorMix;\nuniform float uReveal;\nuniform float uOpacity;',
      )
      .replace(
        '#include <dithering_fragment>',
        `#include <dithering_fragment>
        if (vHoloWorld.y > uReveal) discard;
        vec3 vd = normalize(vViewPosition);
        float fres = pow(1.0 - clamp(abs(dot(normalize(normal), vd)), 0.0, 1.0), 2.0);
        float scan = 0.62 + 0.38 * sin(vHoloWorld.y * 115.0 - uTime * 5.0);
        float band = 1.0 - smoothstep(0.0, 0.05, uReveal - vHoloWorld.y);
        vec3 holo = uAccent * (0.2 + 1.15 * fres) * scan;
        vec3 lit = gl_FragColor.rgb;
        vec3 col = mix(holo, lit * 0.9 + uAccent * fres * 0.45, uColorMix) + band * vec3(0.85, 1.0, 1.0);
        float a = ((0.14 + 0.8 * fres) * scan * (1.0 - uColorMix) + (0.5 + 0.4 * fres) * uColorMix) * uOpacity + band;
        gl_FragColor = vec4(col, clamp(a, 0.0, 1.0));`,
      )
  }
  mat.customProgramCacheKey = () => 'aurora-holo-mesh-v1'
  return mat
}

async function fetchBlob(url: string): Promise<Blob> {
  const r = await bridgeFetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.blob()
}

async function loadView(url: string, maxDim: number): Promise<ViewInput | null> {
  try {
    const blob = await fetchBlob(url)
    const bmp = await createImageBitmap(blob)
    const scale = Math.min(1, maxDim / Math.max(bmp.width, bmp.height))
    const w = Math.max(8, Math.round(bmp.width * scale))
    const h = Math.max(8, Math.round(bmp.height * scale))
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) return null
    ctx.drawImage(bmp, 0, 0, w, h)
    bmp.close?.()
    const id = ctx.getImageData(0, 0, w, h)
    const img: RGBAImage = { width: w, height: h, data: id.data }
    const res = foregroundMask(img)
    return res ? { img, mask: res.mask } : null
  } catch {
    return null
  }
}

function isCompleteGlb(buf: ArrayBuffer): boolean {
  if (buf.byteLength < 28) return false
  const v = new DataView(buf)
  return v.getUint32(0, true) === 0x46546c67 && v.getUint32(4, true) === 2 && v.getUint32(8, true) === buf.byteLength
}

type Cloud = {
  points: THREE.Points
  mat: THREE.ShaderMaterial
  morph: Anim
  fade: Anim
  tag: string
}

class HoloEngine {
  private readonly host: HTMLElement
  private readonly getProps: () => HologramStageProps
  private readonly renderer: THREE.WebGLRenderer
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(35, 1, 0.05, 60)
  private readonly root = new THREE.Group()
  private readonly common = {
    uTime: { value: 0 },
    uAccent: { value: new THREE.Color('#60A5FA') },
    uColorMix: { value: 0 },
    uGlitch: { value: 0.25 },
    uPulseH: { value: -1 },
    uPixelRatio: { value: 1 },
  }
  private readonly diskU = {
    uTime: this.common.uTime,
    uAccent: this.common.uAccent,
    uPulse: { value: -1 },
    uBoot: { value: 0 },
    uProgress: { value: -1 },
  }
  private readonly meshU = { uReveal: { value: -2 }, uOpacity: { value: 1 } }
  private readonly scanRing: THREE.Mesh
  private clouds: Cloud[] = []
  private meshRoot: THREE.Group | null = null
  private meshMaterials: THREE.Material[] = []
  private meshTextures: THREE.Texture[] = []
  private meshReveal: Anim = { from: 0, to: 0, start: 0, dur: 1 }
  private mixer: THREE.AnimationMixer | null = null
  private clips: THREE.AnimationClip[] = []
  private playing = false
  private colorMix = 0
  private glitch = 0.25
  private yaw = 0
  private pitch = 0.12
  private dragging = false
  private lastX = 0
  private lastY = 0
  private raf = 0
  private lastFrame = 0
  private lastTick = performance.now()
  private readonly bootAt = performance.now()
  private visible = true
  private disposed = false
  private refsKey = ''
  private refsToken = 0
  private meshUrl: string | null = null
  private meshToken = 0
  private partsKey = ''
  private heavyMesh = false
  private readonly ro: ResizeObserver
  private readonly io: IntersectionObserver | null
  private readonly onVis = () => this.loop()

  constructor(host: HTMLElement, getProps: () => HologramStageProps) {
    this.host = host
    this.getProps = getProps
    const low = getProps().quality === 'low'
    this.renderer = new THREE.WebGLRenderer({ antialias: !low, alpha: true, powerPreference: 'low-power' })
    const dpr = Math.min(window.devicePixelRatio || 1, low ? 1 : 1.5)
    this.renderer.setPixelRatio(dpr)
    this.common.uPixelRatio.value = dpr
    this.renderer.setClearColor(0x000000, 0)
    this.renderer.domElement.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:none'
    host.appendChild(this.renderer.domElement)

    this.scene.add(this.root)
    this.scene.add(new THREE.AmbientLight(0xffffff, 1.1))
    const key = new THREE.DirectionalLight(0xffffff, 1.6)
    key.position.set(2, 3, 4)
    this.scene.add(key)

    // émetteur : disque à anneaux + jauge, cône de lumière, couronne de particules
    const disk = new THREE.Mesh(
      new THREE.CircleGeometry(1.32, 96),
      new THREE.ShaderMaterial({
        uniforms: this.diskU,
        vertexShader: DISK_VERT,
        fragmentShader: DISK_FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
      }),
    )
    disk.rotation.x = -Math.PI / 2
    disk.position.y = -1.04
    this.scene.add(disk)
    const coneH = 2.4
    const cone = new THREE.Mesh(
      new THREE.CylinderGeometry(1.2, 0.98, coneH, 72, 1, true),
      new THREE.ShaderMaterial({
        uniforms: { uTime: this.common.uTime, uAccent: this.common.uAccent, uBoot: this.diskU.uBoot },
        vertexShader: DISK_VERT,
        fragmentShader: CONE_FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
      }),
    )
    cone.position.y = -1.04 + coneH / 2
    this.scene.add(cone)
    const ringCount = low ? 220 : 420
    const ringPos = new Float32Array(ringCount * 3)
    for (let i = 0; i < ringCount; i++) {
      const a = (i / ringCount) * Math.PI * 2
      const r = 1.3 + Math.sin(i * 7.31) * 0.05
      ringPos[i * 3] = Math.cos(a) * r
      ringPos[i * 3 + 1] = -1.02 + Math.abs(Math.sin(i * 3.17)) * 0.06
      ringPos[i * 3 + 2] = Math.sin(a) * r
    }
    const ring = this.makePoints(ringPos, null, null, 'ring', 1, 2.4)
    ring.points.renderOrder = 1
    this.scene.add(ring.points)
    this.clouds.push(ring)

    this.scanRing = new THREE.Mesh(
      new THREE.RingGeometry(1.06, 1.12, 128),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }),
    )
    this.scanRing.rotation.x = -Math.PI / 2
    this.scene.add(this.scanRing)

    this.ro = new ResizeObserver(() => this.resize())
    this.ro.observe(host)
    this.io = typeof IntersectionObserver !== 'undefined'
      ? new IntersectionObserver((entries) => {
        this.visible = entries.some((e) => e.isIntersecting)
        if (this.visible) this.loop()
      })
      : null
    this.io?.observe(host)
    document.addEventListener('visibilitychange', this.onVis)
    this.bindPointer()
    this.resize()
    this.loop()
  }

  private bindPointer() {
    const el = this.renderer.domElement
    el.addEventListener('pointerdown', (e) => {
      if (!this.getProps().interactive) return
      this.dragging = true
      this.lastX = e.clientX
      this.lastY = e.clientY
      el.setPointerCapture?.(e.pointerId)
    })
    el.addEventListener('pointermove', (e) => {
      if (!this.dragging) return
      this.yaw += (e.clientX - this.lastX) * 0.01
      this.pitch = Math.max(-0.35, Math.min(0.6, this.pitch + (e.clientY - this.lastY) * 0.006))
      this.lastX = e.clientX
      this.lastY = e.clientY
    })
    const end = () => { this.dragging = false }
    el.addEventListener('pointerup', end)
    el.addEventListener('pointercancel', end)
    el.addEventListener('pointerleave', end)
  }

  private resize() {
    const w = Math.max(1, this.host.clientWidth)
    const h = Math.max(1, this.host.clientHeight)
    this.renderer.setSize(w, h, false)
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
  }

  private makePoints(
    positions: Float32Array,
    colors: Float32Array | null,
    kinds: Float32Array | null,
    tag: string,
    morphFrom: number,
    size: number,
  ): Cloud {
    const count = positions.length / 3
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    const scatter = new Float32Array(count * 3)
    const seeds = new Float32Array(count)
    let s = 2463534242
    const rnd = () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return (s >>> 0) / 4294967296 }
    let minY = Infinity
    let maxY = -Infinity
    for (let i = 0; i < count; i++) {
      const a = rnd() * Math.PI * 2
      const r = 0.25 + Math.sqrt(rnd()) * 1.05
      scatter[i * 3] = Math.cos(a) * r
      scatter[i * 3 + 1] = -1 + rnd() * 2.3
      scatter[i * 3 + 2] = Math.sin(a) * r
      seeds[i] = rnd()
      const y = positions[i * 3 + 1]
      if (y < minY) minY = y
      if (y > maxY) maxY = y
    }
    geo.setAttribute('aScatter', new THREE.BufferAttribute(scatter, 3))
    geo.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1))
    geo.setAttribute('aColor', new THREE.BufferAttribute(colors ?? new Float32Array(count * 3).fill(1), 3))
    geo.setAttribute('aKind', new THREE.BufferAttribute(kinds ?? new Float32Array(count), 1))
    const mat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: this.common.uTime,
        uAccent: this.common.uAccent,
        uColorMix: tag === 'ring' ? { value: 0 } : this.common.uColorMix,
        uGlitch: tag === 'ring' ? { value: 0 } : this.common.uGlitch,
        uPulseH: tag === 'ring' ? { value: -1 } : this.common.uPulseH,
        uPixelRatio: this.common.uPixelRatio,
        uMorph: { value: morphFrom },
        uOpacity: { value: 1 },
        uSize: { value: size },
        uMinY: { value: Number.isFinite(minY) ? minY : -1 },
        uMaxY: { value: Number.isFinite(maxY) ? maxY : 1 },
        uReveal: { value: 1.2 },
      },
      vertexShader: POINT_VERT,
      fragmentShader: POINT_FRAG,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const points = new THREE.Points(geo, mat)
    points.frustumCulled = false
    const now = performance.now()
    return { points, mat, tag, morph: { from: morphFrom, to: 1, start: now, dur: 2600 }, fade: { from: 0, to: 1, start: now, dur: 700 } }
  }

  /** Remplace les nuages du sujet : l'ancien s'efface pendant que le nouveau converge. */
  private setSubjectCloud(positions: Float32Array, colors: Float32Array | null, kinds: Float32Array | null, tag: string) {
    const now = performance.now()
    for (const c of this.clouds) {
      if (c.tag === 'ring' || c.tag.startsWith('fading')) continue
      c.fade = { from: Number(c.mat.uniforms.uOpacity.value), to: 0, start: now, dur: 1400 }
      c.tag = `fading:${c.tag}`
    }
    const low = this.getProps().quality === 'low'
    // taille à l'écran ≈ 2–3 px : nuage dense (moins de points en qualité basse, donc plus gros)
    const size = tag === 'mesh' ? 2.2 : tag === 'parts' ? 3.2 : low ? 3.6 : 3
    const cloud = this.makePoints(positions, colors, kinds, tag, 0, size)
    this.root.add(cloud.points)
    this.clouds.push(cloud)
  }

  private status(source: HologramSource, points: number, views: number, note: string) {
    try { this.getProps().onStatus?.({ source, points, views, note }) } catch { /* affichage seul */ }
  }

  async setReferences(refs: HologramRef[]) {
    const key = refs.map((r) => `${r.role}:${r.url}`).join('|')
    if (key === this.refsKey) return
    this.refsKey = key
    const token = ++this.refsToken
    if (this.meshRoot || this.partsKey) return
    const { front, side, back } = pickViews(refs)
    if (!front) {
      this.status('emitter', 0, 0, 'En attente des vues de référence de la demande')
      return
    }
    const low = this.getProps().quality === 'low'
    const maxDim = low ? 120 : 168
    const [f, s, b] = await Promise.all([front, side, back].map((r) => (r ? loadView(r.url, maxDim) : Promise.resolve(null))))
    if (token !== this.refsToken || this.disposed || this.meshRoot) return
    if (!f) {
      this.status('emitter', 0, 0, 'Vue de référence reçue mais sujet non séparable du fond')
      return
    }
    const cloud = buildSilhouetteCloud(f, {
      side: s,
      back: b,
      sideRole: side?.role === 'gauche' ? 'gauche' : 'droite',
      maxPoints: low ? 14000 : 32000,
      seed: key.length * 7919,
    })
    if (!cloud || token !== this.refsToken) return
    this.setSubjectCloud(cloud.positions, cloud.colors, cloud.kinds, 'refs')
    const views = [f, s, b].filter(Boolean).length
    this.status(
      cloud.method,
      cloud.count,
      views,
      cloud.method === 'hull'
        ? `Reconstruit depuis ${views} vue(s) réelle(s) : silhouette de face, épaisseur du profil`
        : `Relief reconstruit depuis la silhouette de la vue de face${views > 1 ? ' (dos pour la face arrière)' : ''}`,
    )
  }

  setParts(parts: LivePartGeometryPreview[] | null | undefined, joints: LiveJointPreview[] | null | undefined) {
    const valid = (parts ?? []).filter((p) => (p.sample_points_mm?.length ?? 0) > 0 || (p.dimensions_mm?.length ?? 0) >= 3)
    const key = valid.map((p) => `${p.id}:${p.sample_points_mm?.length ?? 0}:${p.dimensions_mm?.join('x') ?? ''}`).join('|')
    if (key === this.partsKey) return
    this.partsKey = key
    if (!valid.length || this.meshRoot) return
    const splats = generateHolographicSplats('', this.getProps().quality === 'low' ? 5000 : 12000, valid, joints ?? undefined)
    const n = splats.length
    const pos = new Float32Array(n * 3)
    const col = new Float32Array(n * 3)
    const kind = new Float32Array(n)
    let minY = Infinity
    let maxY = -Infinity
    for (const sp of splats) { minY = Math.min(minY, -sp.y); maxY = Math.max(maxY, -sp.y) }
    const span = Math.max(1e-3, maxY - minY)
    const scale = 2 / Math.max(span, 1.45)
    splats.forEach((sp, i) => {
      pos[i * 3] = sp.x * scale
      pos[i * 3 + 1] = (-sp.y - minY) * scale - 1
      pos[i * 3 + 2] = sp.z * scale
      col[i * 3] = sp.color[0] / 255
      col[i * 3 + 1] = sp.color[1] / 255
      col[i * 3 + 2] = sp.color[2] / 255
      kind[i] = sp.isJointNode ? 2 : 0
    })
    this.setSubjectCloud(pos, col, kind, 'parts')
    this.status('parts', n, 0, `${valid.length} pièce(s) STL mesurée(s) — points échantillonnés réels`)
  }

  async setMesh(url: string | null) {
    if (url === this.meshUrl) return
    this.meshUrl = url
    const token = ++this.meshToken
    if (!url) return
    const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js')
    const { DRACOLoader } = await import('three/examples/jsm/loaders/DRACOLoader.js')
    const loader = new GLTFLoader()
    const draco = new DRACOLoader()
    draco.setDecoderPath('/draco/')
    loader.setDRACOLoader(draco)
    try {
      const { MeshoptDecoder } = await import('three/examples/jsm/libs/meshopt_decoder.module.js')
      if (MeshoptDecoder) loader.setMeshoptDecoder(MeshoptDecoder)
    } catch { /* décodeur optionnel */ }
    for (let attempt = 0; attempt < 7; attempt++) {
      if (token !== this.meshToken || this.disposed) return
      try {
        const buf = await (await fetchBlob(url)).arrayBuffer()
        // un GLB encore en cours d'écriture est attendu, pas affiché tronqué
        if (!isCompleteGlb(buf)) throw new Error('incomplete')
        const gltf = await new Promise<{ scene: THREE.Group; animations: THREE.AnimationClip[] }>((resolve, reject) =>
          loader.parse(buf, '', (g) => resolve(g as unknown as { scene: THREE.Group; animations: THREE.AnimationClip[] }), reject),
        )
        if (token !== this.meshToken || this.disposed) return
        this.installMesh(gltf.scene, gltf.animations ?? [])
        draco.dispose()
        return
      } catch {
        await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)))
      }
    }
    draco.dispose()
    this.status('emitter', 0, 0, 'Maillage annoncé mais pas encore lisible')
  }

  private installMesh(object: THREE.Group, animations: THREE.AnimationClip[]) {
    this.removeMesh()
    const box = new THREE.Box3().setFromObject(object)
    const size = box.getSize(new THREE.Vector3())
    const center = box.getCenter(new THREE.Vector3())
    const scale = Math.min(2 / Math.max(1e-6, size.y), 2.4 / Math.max(1e-6, size.x, size.z))
    const holder = new THREE.Group()
    object.scale.setScalar(scale)
    object.position.set(-center.x * scale, -box.min.y * scale - 1, -center.z * scale)
    holder.add(object)
    holder.updateMatrixWorld(true)
    let triangles = 0
    const meshes: THREE.Mesh[] = []
    object.traverse((o) => {
      const m = o as THREE.Mesh
      if (!m.isMesh || !m.geometry) return
      meshes.push(m)
      const geo = m.geometry as THREE.BufferGeometry
      triangles += (geo.index ? geo.index.count : geo.attributes.position.count) / 3
      const mats = Array.isArray(m.material) ? m.material : [m.material]
      const holo = mats.map((orig) => {
        const hm = makeHoloMaterial(orig, this.common, this.meshU)
        if (hm.map) this.meshTextures.push(hm.map)
        orig.dispose()
        this.meshMaterials.push(hm)
        return hm
      })
      m.material = Array.isArray(m.material) ? holo : holo[0]
      m.frustumCulled = false
    })
    this.heavyMesh = triangles > 300000
    // points échantillonnés sur la surface réelle du maillage
    const budget = this.getProps().quality === 'low' ? 3500 : 9000
    const pos: number[] = []
    const col: number[] = []
    void import('three/examples/jsm/math/MeshSurfaceSampler.js').then(({ MeshSurfaceSampler }) => {
      if (this.disposed || this.meshRoot !== holder) return
      const p = new THREE.Vector3()
      const c = new THREE.Color()
      const per = Math.max(200, Math.floor(budget / Math.max(1, meshes.length)))
      for (const m of meshes) {
        try {
          const sampler = new MeshSurfaceSampler(m).build()
          const hasColor = Boolean((m.geometry as THREE.BufferGeometry).attributes.color)
          for (let i = 0; i < per; i++) {
            if (hasColor) sampler.sample(p, undefined, c)
            else sampler.sample(p)
            p.applyMatrix4(m.matrixWorld)
            pos.push(p.x, p.y, p.z)
            if (hasColor) col.push(c.r, c.g, c.b)
            else col.push(1, 1, 1)
          }
        } catch { /* maillage non échantillonnable : la surface suffit */ }
      }
      if (pos.length) this.setSubjectCloud(Float32Array.from(pos), Float32Array.from(col), null, 'mesh')
    }).catch(() => undefined)
    this.root.add(holder)
    this.meshRoot = holder
    const now = performance.now()
    this.meshReveal = { from: 0, to: 1, start: now, dur: 2800 }
    this.meshU.uOpacity.value = 1
    this.clips = animations
    this.mixer = animations.length ? new THREE.AnimationMixer(object) : null
    this.playing = false
    this.status('mesh', Math.round(triangles), 0, `Maillage réel produit par le pipeline (${Math.round(triangles).toLocaleString('fr-FR')} triangles)`)
  }

  private removeMesh() {
    if (!this.meshRoot) return
    this.root.remove(this.meshRoot)
    this.meshRoot.traverse((o) => {
      const m = o as THREE.Mesh
      if (m.isMesh) m.geometry?.dispose()
    })
    for (const m of this.meshMaterials) m.dispose()
    for (const t of this.meshTextures) t.dispose()
    this.meshMaterials = []
    this.meshTextures = []
    this.mixer?.stopAllAction()
    this.mixer = null
    this.meshRoot = null
  }

  private loop() {
    if (this.disposed || this.raf) return
    const tick = (t: number) => {
      this.raf = 0
      if (this.disposed) return
      if (document.hidden || !this.visible) return
      const minGap = this.heavyMesh ? 32 : 16
      if (t - this.lastFrame >= minGap - 1) {
        this.lastFrame = t
        this.frame(t)
      }
      this.raf = requestAnimationFrame(tick)
    }
    this.raf = requestAnimationFrame(tick)
  }

  private frame(now: number) {
    const p = this.getProps()
    const dt = Math.min(0.1, Math.max(0, (now - this.lastTick) / 1000))
    this.lastTick = now
    const wall = Date.now()
    this.common.uTime.value = now / 1000
    this.common.uAccent.value.set(p.accent)
    const pulseAge = wall - p.readPulseAt()
    this.diskU.uPulse.value = pulseAge >= 0 && pulseAge < 900 ? pulseAge / 900 : -1
    this.common.uPulseH.value = pulseAge >= 0 && pulseAge < 1400 ? pulseAge / 1400 : -1
    this.diskU.uBoot.value = Math.min(1, (now - this.bootAt) / 900)
    const prog = p.readProgress()
    this.diskU.uProgress.value = Number.isFinite(prog) && prog >= 0 ? Math.min(1, prog) : -1

    const hasSubject = this.clouds.some((c) => c.tag !== 'ring' && !c.tag.startsWith('fading')) || Boolean(this.meshRoot)
    const phase = p.phaseIdx
    const colorTarget = !hasSubject ? 0 : p.done ? 1 : phase >= 3 ? 0.85 : phase >= 2 ? 0.28 : 0.12
    this.colorMix += (colorTarget - this.colorMix) * (1 - Math.exp(-dt / 0.9))
    this.common.uColorMix.value = this.colorMix
    const glitchBase = p.done ? 0 : phase >= p.phaseCount - 1 ? 0.04 : phase >= 3 ? 0.12 : 0.26
    const glitchTarget = glitchBase + (pulseAge >= 0 && pulseAge < 260 ? 0.55 : 0)
    this.glitch += (glitchTarget - this.glitch) * (1 - Math.exp(-dt / 0.12))
    this.common.uGlitch.value = this.glitch

    if (!this.dragging) this.root.rotation.y += dt * (p.done ? 0.16 : 0.3)
    const dist = this.camera.aspect < 0.85 ? 5.3 : 4.15
    const yaw = this.yaw
    this.camera.position.set(Math.sin(yaw) * dist * Math.cos(this.pitch), 0.35 + Math.sin(this.pitch) * dist, Math.cos(yaw) * dist * Math.cos(this.pitch))
    this.camera.lookAt(0, -0.08, 0)

    // nuages : convergence et fondus
    const keep: Cloud[] = []
    for (const c of this.clouds) {
      c.mat.uniforms.uMorph.value = animAt(c.morph, now)
      const op = animAt(c.fade, now)
      c.mat.uniforms.uOpacity.value = op
      if (c.tag.startsWith('fading') && now - c.fade.start >= c.fade.dur) {
        this.root.remove(c.points)
        this.scene.remove(c.points)
        c.points.geometry.dispose()
        c.mat.dispose()
        continue
      }
      keep.push(c)
    }
    this.clouds = keep

    // maillage : matérialisation de bas en haut au moment de son arrivée
    const ringMat = this.scanRing.material as THREE.MeshBasicMaterial
    ringMat.color.set(p.accent)
    if (this.meshRoot) {
      const rv = p.done ? 1 : animAt(this.meshReveal, now)
      const y = -1 + 2.08 * rv
      this.meshU.uReveal.value = rv >= 1 ? 9 : y
      this.scanRing.position.y = y
      ringMat.opacity = rv < 1 ? 0.75 : Math.max(0, ringMat.opacity - dt * 1.5)
      for (const c of this.clouds) if (c.tag === 'mesh') c.mat.uniforms.uReveal.value = rv >= 1 ? 1.2 : rv
      if (this.mixer && this.clips.length && (phase >= 4 || p.done)) {
        if (!this.playing) {
          this.mixer.clipAction(this.clips[0]).play()
          this.playing = true
        }
        this.mixer.update(dt)
      }
    } else if (hasSubject && phase === 2) {
      // sculpture en cours sans maillage encore lisible : balayage d'inspection
      const y = -1 + (1 + Math.sin(now * 0.0011)) * 1.02
      this.scanRing.position.y = y
      ringMat.opacity = 0.45
    } else {
      ringMat.opacity = Math.max(0, ringMat.opacity - dt * 1.5)
    }
    this.renderer.render(this.scene, this.camera)
  }

  dispose() {
    this.disposed = true
    cancelAnimationFrame(this.raf)
    this.ro.disconnect()
    this.io?.disconnect()
    document.removeEventListener('visibilitychange', this.onVis)
    this.removeMesh()
    this.scene.traverse((o) => {
      const m = o as THREE.Mesh
      if (m.geometry) m.geometry.dispose()
      const mat = m.material as THREE.Material | THREE.Material[] | undefined
      if (Array.isArray(mat)) mat.forEach((x) => x.dispose())
      else mat?.dispose()
    })
    this.renderer.dispose()
    this.renderer.domElement.remove()
  }
}

export default function HologramStage(props: HologramStageProps) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const propsRef = useRef(props)
  propsRef.current = props
  const engineRef = useRef<HoloEngine | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!hostRef.current) return
    try {
      engineRef.current = new HoloEngine(hostRef.current, () => propsRef.current)
    } catch {
      setFailed(true)
    }
    return () => {
      engineRef.current?.dispose()
      engineRef.current = null
    }
  }, [])

  const refsKey = (props.refs ?? []).map((r) => `${r.role}:${r.url}`).join('|')
  useEffect(() => {
    void engineRef.current?.setReferences(props.refs ?? [])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refsKey])
  useEffect(() => {
    void engineRef.current?.setMesh(props.meshUrl ?? null)
  }, [props.meshUrl])
  const partsKey = (props.parts ?? []).map((p) => `${p.id}:${p.sample_points_mm?.length ?? 0}`).join('|')
  useEffect(() => {
    engineRef.current?.setParts(props.parts, props.joints)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partsKey, props.joints?.length])

  return (
    <div ref={hostRef} style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
      {failed && (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: '#9AA5BC', fontSize: 12 }}>
          Aperçu holographique indisponible (WebGL désactivé sur cet appareil).
        </div>
      )}
    </div>
  )
}
