/**
 * Chambre de diffusion FLUX.2 (WebGL) — écran de génération du module Image.
 *
 * Ce qui est montré vient uniquement de la génération en cours :
 *  - les mots réels de la demande, dont le sujet verrouillé et le texte exact à
 *    écrire, qui gravitent puis sont absorbés au moment réel de l'encodage du prompt ;
 *  - le flux de poids qui afflue vers la plaque pendant le vrai chargement du modèle ;
 *  - la plaque latente : grain dont l'amplitude suit la courbe de bruit du
 *    planificateur au pas k/N réellement atteint, grille des patchs FLUX, onde à
 *    chaque pas reçu ; l'aperçu latent réel de ComfyUI s'y dépose quand le serveur
 *    en envoie (sinon aucune image n'est inventée à sa place) ;
 *  - le cadran : un cran par pas de diffusion, allumé à l'arrivée réelle du pas ;
 *  - le décodage VAE puis la révélation de l'image finale, patch par patch.
 *
 * Synchronisation : l'étape et la sous-étape viennent des événements ComfyUI
 * (`readComfyLive`) et de l'étape réelle du module ; aucune ne dépend d'un minuteur.
 * Rendu borné (≤ 60 i/s, GPU basse consommation, densité réduite sur mobile).
 */
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { readComfyLive } from './comfyProgress.ts'
import { fluxSigmaAt, type ComfyStage } from './comfyStages.ts'

export type DiffusionStageProps = {
  accent: string
  phaseIdx: number
  phaseCount: number
  readPulseAt: () => number
  prompt?: string | null
  /** mots mis en avant (sujet verrouillé, texte exact) */
  subjectWords?: string[]
  inscriptionWords?: string[]
  aspect?: number | null
  /** début réel de la génération (Date.now) : un graphe enregistré avant n'est pas suivi */
  sessionStartedAt?: number
  refs?: { url: string; role: string }[] | null
  resultUrl?: string | null
  done?: boolean
  quality?: 'high' | 'low'
}


const STOP = new Set(['un', 'une', 'des', 'le', 'la', 'les', 'de', 'du', 'd', 'l', 'et', 'en', 'avec', 'a', 'à', 'au', 'aux', 'sur', 'dans', 'pour', 'moi', 'fais', 'fait', 'cree', 'crée', 'genere', 'génère', 'dessine', 'je', 'veux', 'voudrais', 'qui', 'que', 'ce', 'cette', 'son', 'sa', 'ses', 'forme', 'the', 'of', 'with', 'an'])

export function promptWords(prompt: string, max = 14): string[] {
  const words = (prompt || '')
    .replace(/["“”«»]/g, ' ')
    .split(/[\s,.;:!?()'’]+/u)
    .map((w) => w.trim())
    .filter((w) => w.length > 1 && !STOP.has(w.toLowerCase()))
  return Array.from(new Set(words)).slice(0, max)
}

const COLOR_WORDS: Array<[RegExp, string]> = [
  [/rouge|red|bordeaux|carmin/i, '#E5484D'], [/rose|pink/i, '#F472B6'], [/bleu|blue|azur|marine/i, '#3B82F6'],
  [/vert|green|emeraude|émeraude/i, '#22C55E'], [/jaune|yellow|or\b|dor[ée]|gold/i, '#F5C451'], [/orange/i, '#F97316'],
  [/violet|purple|mauve/i, '#8B5CF6'], [/noir|black|sombre/i, '#334155'], [/blanc|white|neige|porcelaine/i, '#E2E8F0'],
  [/turquoise|cyan/i, '#22D3EE'], [/marron|brun|bois|wood|terre/i, '#A16207'], [/verre|glass|cristal|transparent/i, '#A5F3FC'],
]

function paletteFor(prompt: string, accent: string): [THREE.Color, THREE.Color, THREE.Color] {
  const found = COLOR_WORDS.filter(([re]) => re.test(prompt)).map(([, c]) => new THREE.Color(c))
  const a = new THREE.Color(accent)
  const hsl = { h: 0, s: 0, l: 0 }
  a.getHSL(hsl)
  const b = new THREE.Color().setHSL((hsl.h + 0.12) % 1, Math.min(1, hsl.s * 0.9), 0.42)
  const c = new THREE.Color().setHSL((hsl.h + 0.62) % 1, 0.55, 0.18)
  return [found[0] ?? a, found[1] ?? b, found[2] ?? c]
}

const PLATE_VERT = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`

const PLATE_FRAG = /* glsl */ `
uniform float uTime;
uniform float uSigma;
uniform float uForm;
uniform float uPreviewMix;
uniform float uRefMix;
uniform float uReveal;
uniform float uWave;
uniform float uDecode;
uniform float uLoad;
uniform float uSeed;
uniform vec2 uGrid;
uniform vec3 uA;
uniform vec3 uB;
uniform vec3 uC;
uniform vec3 uAccent;
uniform sampler2D uPreview;
uniform sampler2D uRef;
uniform sampler2D uFinal;
varying vec2 vUv;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * noise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
  return v;
}

void main() {
  vec2 uv = vUv;
  vec2 cellId = floor(uv * uGrid);
  vec2 cuv = fract(uv * uGrid);
  float h = hash(cellId + uSeed);

  // champ latent : structures basses fréquences qui se figent quand le bruit baisse
  float drift = uTime * mix(0.02, 0.11, uSigma);
  vec2 w = vec2(fbm(uv * 2.6 + uSeed + drift), fbm(uv * 2.6 + 4.3 - drift));
  float base = fbm(uv * 1.8 + w * (1.2 + 0.8 * uSigma) + uSeed * 0.37);
  vec3 latent = mix(uC, mix(uA, uB, smoothstep(0.25, 0.85, w.y)), smoothstep(0.2, 0.8, base));
  latent += uAccent * 0.18 * smoothstep(0.62, 0.95, base);

  // grain gaussien du pas : amplitude = sigma du planificateur au pas réel
  float tick = floor(uTime * 20.0);
  float g = hash(uv * vec2(733.0, 977.0) + tick) - 0.5;
  float tokenFlicker = hash(cellId + tick * 0.37) - 0.5;
  vec3 grainCol = mix(vec3(1.0), normalize(latent + 0.05) * 1.35, 0.55);
  vec3 noisy = latent * (1.0 - 0.6 * uSigma) + grainCol * (g * 1.15 + tokenFlicker * 0.3) * uSigma;

  // aperçu latent réel envoyé par ComfyUI (si le serveur en transmet)
  vec3 prev = texture2D(uPreview, uv).rgb;
  noisy = mix(noisy, prev + vec3(g) * uSigma * 0.5, uPreviewMix);
  // référence réellement conditionnée (ReferenceLatent / Kontext), en filigrane
  vec3 refc = texture2D(uRef, uv).rgb;
  noisy = mix(noisy, refc, uRefMix * (0.35 + 0.25 * uSigma));

  // chargement du modèle : la plaque s'allume en balayage, des poids s'y inscrivent
  float loadFront = smoothstep(uLoad - 0.08, uLoad, 1.0 - uv.y);
  noisy *= mix(0.12, 1.0, max(loadFront, uForm));

  // grille des patchs FLUX (2×2 tokens latents) et onde du dernier pas reçu
  float edge = min(min(cuv.x, 1.0 - cuv.x), min(cuv.y, 1.0 - cuv.y));
  float grid = 1.0 - smoothstep(0.0, 0.06, edge);
  noisy += uAccent * grid * (0.05 + 0.12 * uSigma) * (1.0 - uReveal);
  float waveY = 1.0 - uWave;
  float band = exp(-pow((uv.y - waveY) * 16.0, 2.0)) * step(0.0, uWave) * step(uWave, 1.0);
  noisy += mix(uAccent, vec3(1.0), 0.4) * band * 0.45;

  // décodage VAE : les patchs se résolvent un à un (rangées depuis le haut + hasard)
  float dDelay = (1.0 - uv.y) * 0.6 + h * 0.4;
  float dec = smoothstep(dDelay, dDelay + 0.15, uDecode);
  vec3 sharp = mix(noisy, latent * 0.9 + 0.08, 0.35);
  noisy = mix(noisy, sharp, dec * (1.0 - uPreviewMix * 0.6));

  // révélation de l'image finale : bascule patch par patch depuis le centre
  float rDelay = length(uv - 0.5) * 0.9 + h * 0.35;
  float flip = smoothstep(rDelay, rDelay + 0.22, uReveal * 1.3);
  vec3 fin = texture2D(uFinal, uv).rgb;
  vec3 col = mix(noisy, fin, flip);
  col += mix(uAccent, vec3(1.0), 0.5) * flip * (1.0 - flip) * 2.2;

  // verre : reflet diagonal qui balaie lentement, franges chromatiques et ombre interne des bords
  float sweep = fract(uTime * 0.045) * 2.6 - 0.8;
  float sheen = exp(-pow((uv.x * 0.8 + uv.y * 0.6 - sweep) * 9.0, 2.0));
  col += vec3(0.9, 0.95, 1.0) * sheen * 0.10;
  float edgeD = min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y));
  col.r += (1.0 - smoothstep(0.0, 0.012, edgeD)) * 0.35;
  col.b += (1.0 - smoothstep(0.004, 0.02, edgeD)) * 0.35;
  col *= mix(0.55, 1.0, smoothstep(0.0, 0.06, edgeD));
  float vig = smoothstep(0.95, 0.35, length(uv - 0.5));
  col *= mix(0.72, 1.0, max(vig, flip));
  gl_FragColor = vec4(col, 1.0);
}
`

const HALO_FRAG = /* glsl */ `
uniform float uTime;
uniform float uSteps;
uniform float uMax;
uniform float uSigma;
uniform float uPulse;
uniform float uActive;
uniform vec3 uAccent;
varying vec2 vUv;
const float PI = 3.14159265;
void main() {
  vec2 p = vUv * 2.0 - 1.0;
  float r = length(p);
  float a = atan(p.y, p.x);
  float a01 = fract(0.25 - a / (2.0 * PI));
  vec3 col = vec3(0.0);
  float alpha = 0.0;
  // cadran des pas : un cran par pas réel, allumé à son arrivée
  float n = max(1.0, uMax);
  float idx = floor(a01 * n);
  float local = fract(a01 * n);
  float tickBand = smoothstep(0.865, 0.872, r) * (1.0 - smoothstep(0.93, 0.937, r));
  float tickShape = smoothstep(0.30, 0.38, local) * (1.0 - smoothstep(0.62, 0.70, local));
  float lit = step(idx + 0.5, uSteps);
  float current = 1.0 - step(0.5, abs(idx + 1.0 - uSteps));
  vec3 tickCol = mix(uAccent * 0.25, mix(uAccent, vec3(1.0), 0.3), lit);
  tickCol += vec3(1.0) * current * (0.5 + 0.5 * sin(uTime * 10.0));
  col += tickCol * tickBand * tickShape * uActive * 0.85;
  alpha += tickBand * tickShape * mix(0.3, 0.9, lit) * uActive;
  // arc de progression continu sous le cadran
  float prog = clamp(uSteps / n, 0.0, 1.0);
  float arc = smoothstep(0.80, 0.81, r) * (1.0 - smoothstep(0.83, 0.84, r));
  float arcLit = step(a01, prog);
  col += mix(uAccent * 0.12, uAccent * 1.4, arcLit) * arc;
  alpha += arc * mix(0.15, 0.95, arcLit);
  // anneau extérieur segmenté, tourne d'autant plus vite que le bruit est fort
  float seg = step(0.5, fract((a01 + uTime * (0.01 + 0.05 * uSigma)) * 24.0));
  float outer = smoothstep(0.975, 0.98, r) * (1.0 - smoothstep(0.99, 0.995, r));
  col += uAccent * 0.6 * outer * seg;
  alpha += outer * seg * 0.5;
  // onde émise à chaque événement réel
  float wave = (1.0 - smoothstep(0.0, 0.025, abs(r - (0.78 + uPulse * 0.25)))) * (1.0 - uPulse);
  col += mix(uAccent, vec3(1.0), 0.5) * wave;
  alpha += wave * 0.8;
  gl_FragColor = vec4(col, clamp(alpha, 0.0, 1.0));
}
`

const FLOW_VERT = /* glsl */ `
attribute vec4 aSeed;
uniform float uTime;
uniform float uPixelRatio;
uniform vec4 uMode;   // x: ambiance, y: chargement, z: encodage, w: diffusion
uniform float uBurst;
uniform float uSigma;
uniform vec2 uPlate;
varying float vAlpha;
varying float vHeat;
void main() {
  float s = aSeed.x, s2 = aSeed.y, s3 = aSeed.z, s4 = aSeed.w;
  // ambiance : nébuleuse lente autour de la plaque
  float ang = s * 6.2831 + uTime * (0.05 + s2 * 0.08);
  float rad = 2.4 + s3 * 3.2;
  vec3 neb = vec3(cos(ang) * rad, (s2 - 0.5) * 4.2, sin(ang) * rad * 0.6 - 1.5);
  // chargement : les poids affluent de l'arrière vers la plaque
  float lt = fract(uTime * (0.25 + s4 * 0.35) + s);
  vec3 farP = vec3((s2 - 0.5) * 9.0, (s3 - 0.5) * 6.0, -14.0);
  vec3 plateP = vec3((s2 - 0.5) * uPlate.x, (s3 - 0.5) * uPlate.y, 0.02);
  vec3 load = mix(farP, plateP, lt * lt);
  // encodage : spirale qui converge vers le centre de la plaque
  float et = fract(uTime * (0.18 + s4 * 0.2) + s3);
  float ea = s * 6.2831 + et * 9.0;
  float er = (1.0 - et) * (2.6 + s2 * 1.8);
  vec3 enc = vec3(cos(ea) * er, sin(ea) * er * 0.75, (1.0 - et) * 1.2);
  // diffusion : tourbillon du champ de vitesse, rayon et vitesse suivent le bruit restant
  float da = s * 6.2831 + uTime * (0.35 + 1.4 * uSigma) * (0.6 + s2);
  float dr = mix(max(uPlate.x, uPlate.y) * 0.55, 1.2 + s3 * 2.8, 0.25 + 0.75 * uSigma);
  vec3 dif = vec3(cos(da) * dr, (s4 - 0.5) * uPlate.y * 1.25 + sin(da * 2.0 + s) * 0.15, sin(da) * dr * 0.45 + 0.3);
  vec3 p = neb * uMode.x + load * uMode.y + enc * uMode.z + dif * uMode.w;
  p += normalize(p + vec3(0.0001)) * uBurst * (2.5 + s2 * 3.0);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = (1.4 + s4 * 2.8) * uPixelRatio * (8.5 / max(0.6, -mv.z));
  vAlpha = (0.25 + 0.75 * s3) * (1.0 - uBurst * 0.85) * (uMode.y > 0.01 ? mix(1.0, lt, uMode.y) : 1.0);
  vHeat = uMode.w * uSigma + uMode.y * 0.6;
}
`

const FLOW_FRAG = /* glsl */ `
uniform vec3 uAccent;
uniform vec3 uA;
varying float vAlpha;
varying float vHeat;
void main() {
  vec2 q = gl_PointCoord - 0.5;
  float d = length(q);
  if (d > 0.5) discard;
  float soft = smoothstep(0.5, 0.0, d);
  vec3 col = mix(mix(uAccent, uA, 0.35), vec3(1.0), soft * soft * 0.5 + vHeat * 0.2);
  gl_FragColor = vec4(col, soft * vAlpha);
}
`

type WordSprite = { sprite: THREE.Sprite; mat: THREE.SpriteMaterial; tex: THREE.CanvasTexture; seed: number; kind: 'word' | 'subject' | 'text'; absorbedAt: number | null }

function wordTexture(word: string, kind: WordSprite['kind'], accent: string): { tex: THREE.CanvasTexture; aspect: number } {
  const cv = document.createElement('canvas')
  const fontPx = 64
  const ctx = cv.getContext('2d')!
  const label = kind === 'text' ? `« ${word} »` : word
  ctx.font = `600 ${fontPx}px Inter, 'Segoe UI', system-ui, sans-serif`
  const tw = Math.ceil(ctx.measureText(label).width)
  const tag = kind === 'text' ? 'TEXTE EXACT' : kind === 'subject' ? 'SUJET' : ''
  cv.width = Math.max(64, tw + 48)
  cv.height = tag ? 128 : 96
  const c = cv.getContext('2d')!
  c.font = `600 ${fontPx}px Inter, 'Segoe UI', system-ui, sans-serif`
  c.textBaseline = 'middle'
  const color = kind === 'text' ? '#FDE68A' : kind === 'subject' ? '#FFFFFF' : '#CFE3FF'
  c.shadowColor = kind === 'word' ? accent : kind === 'text' ? '#F59E0B' : accent
  c.shadowBlur = 18
  c.fillStyle = color
  c.fillText(label, 24, tag ? 78 : 50)
  if (tag) {
    c.shadowBlur = 0
    c.font = `700 22px 'Cascadia Code', Consolas, monospace`
    c.fillStyle = kind === 'text' ? '#F59E0B' : accent
    c.fillText(tag, 26, 22)
  }
  const tex = new THREE.CanvasTexture(cv)
  tex.colorSpace = THREE.SRGBColorSpace
  return { tex, aspect: cv.width / cv.height }
}

const BLANK = (() => {
  const t = new THREE.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1)
  t.needsUpdate = true
  return t
})

class DiffusionScene {
  private readonly renderer: THREE.WebGLRenderer
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(36, 1, 0.1, 100)
  private readonly rig = new THREE.Group()
  private readonly plateMat: THREE.ShaderMaterial
  private readonly haloMat: THREE.ShaderMaterial
  private readonly flowMat: THREE.ShaderMaterial
  private readonly plate: THREE.Mesh
  private readonly frame: THREE.LineSegments
  private readonly words: WordSprite[] = []
  private readonly refSprites: { sprite: THREE.Sprite; mat: THREE.SpriteMaterial; tex: THREE.Texture; at: number }[] = []
  private readonly ro: ResizeObserver
  private readonly loader = new THREE.TextureLoader()
  private readonly blankPreview = BLANK()
  private readonly blankRef = BLANK()
  private readonly blankFinal = BLANK()
  private raf = 0
  private alive = true
  private last = 0
  private plateW = 3
  private plateH = 3
  private pointer = { x: 0, y: 0 }
  private previewUrl: string | null = null
  private previewTex: THREE.Texture | null = null
  private previewMix = 0
  private finalUrl: string | null = null
  private finalTex: THREE.Texture | null = null
  private revealStart = 0
  private refUrl: string | null = null
  private refTex: THREE.Texture | null = null
  private lastStep = 0
  private stepAt = 0
  private stageSeen: ComfyStage = 'queued'
  private stageAt = 0
  private mode = new THREE.Vector4(1, 0, 0, 0)
  private sigmaShown = 1
  private decodeShown = 0
  private loadShown = 0
  private formShown = 0
  props: DiffusionStageProps

  constructor(private readonly host: HTMLDivElement, props: DiffusionStageProps) {
    this.props = props
    const low = props.quality === 'low'
    this.renderer = new THREE.WebGLRenderer({ antialias: !low, alpha: true, powerPreference: 'low-power' })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, low ? 1.25 : 1.75))
    this.renderer.setClearColor(0x000000, 0)
    host.appendChild(this.renderer.domElement)
    Object.assign(this.renderer.domElement.style, { position: 'absolute', inset: '0', width: '100%', height: '100%' })
    this.camera.position.set(0, 0, 8.2)
    this.scene.add(this.rig)

    const accent = new THREE.Color(props.accent)
    const [pa, pb, pc] = paletteFor(props.prompt || '', props.accent)
    const aspect = Math.max(0.5, Math.min(2.1, props.aspect || 1))
    this.plateH = aspect >= 1 ? 3.2 / aspect : 3.2
    this.plateW = this.plateH * aspect
    const seed = Array.from(props.prompt || 'aurora').reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) % 997, 7) / 97

    this.plateMat = new THREE.ShaderMaterial({
      vertexShader: PLATE_VERT,
      fragmentShader: PLATE_FRAG,
      uniforms: {
        uTime: { value: 0 }, uSigma: { value: 1 }, uForm: { value: 0 }, uPreviewMix: { value: 0 }, uRefMix: { value: 0 },
        uReveal: { value: 0 }, uWave: { value: -1 }, uDecode: { value: 0 }, uLoad: { value: 0 }, uSeed: { value: seed },
        uGrid: { value: new THREE.Vector2(Math.round(32 * aspect), 32) },
        uA: { value: pa }, uB: { value: pb }, uC: { value: pc }, uAccent: { value: accent },
        uPreview: { value: this.blankPreview }, uRef: { value: this.blankRef }, uFinal: { value: this.blankFinal },
      },
    })
    this.plate = new THREE.Mesh(new THREE.PlaneGeometry(this.plateW, this.plateH), this.plateMat)
    this.rig.add(this.plate)

    // reflet de la plaque sur un sol sombre (même rendu, retourné et estompé)
    const reflMat = this.plateMat.clone()
    reflMat.uniforms = this.plateMat.uniforms
    reflMat.transparent = true
    reflMat.depthWrite = false
    reflMat.side = THREE.DoubleSide
    // miroir : la rangée du bas de la plaque (uv.y = 0) touche le haut du reflet, qui s'estompe vers le bas
    reflMat.fragmentShader = PLATE_FRAG.replace(
      'gl_FragColor = vec4(col, 1.0);',
      'gl_FragColor = vec4(col * 0.55, 0.30 * (1.0 - smoothstep(0.0, 0.42, vUv.y)));',
    )
    const refl = new THREE.Mesh(new THREE.PlaneGeometry(this.plateW, this.plateH), reflMat)
    refl.scale.y = -1
    refl.position.set(0, -this.plateH - 0.06, -0.08)
    this.rig.add(refl)

    // halo arrière (lueur additive) et cadran des pas
    const glowMat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: { uAccent: { value: accent } },
      vertexShader: PLATE_VERT,
      fragmentShader: /* glsl */ `uniform vec3 uAccent; varying vec2 vUv; void main(){ float d = length(vUv - 0.5) * 2.0; float a = pow(max(0.0, 1.0 - d), 2.2) * 0.55; gl_FragColor = vec4(uAccent * a, a); }`,
    })
    const glow = new THREE.Mesh(new THREE.PlaneGeometry(this.plateW * 2.4, this.plateH * 2.4), glowMat)
    glow.position.z = -0.6
    this.rig.add(glow)

    const haloSize = Math.max(this.plateW, this.plateH) * 1.62
    this.haloMat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 }, uSteps: { value: 0 }, uMax: { value: 28 }, uSigma: { value: 1 }, uPulse: { value: 1 },
        uActive: { value: 0 }, uAccent: { value: accent },
      },
      vertexShader: PLATE_VERT,
      fragmentShader: HALO_FRAG,
    })
    const halo = new THREE.Mesh(new THREE.PlaneGeometry(haloSize, haloSize), this.haloMat)
    halo.position.z = -0.25
    this.rig.add(halo)

    // cadre de verre : contour et équerres
    const w2 = this.plateW / 2 + 0.06, h2 = this.plateH / 2 + 0.06, k = 0.32
    const pts = [
      -w2, -h2, 0, w2, -h2, 0, w2, -h2, 0, w2, h2, 0, w2, h2, 0, -w2, h2, 0, -w2, h2, 0, -w2, -h2, 0,
      -w2 - 0.08, h2 + 0.08, 0, -w2 - 0.08 + k, h2 + 0.08, 0, -w2 - 0.08, h2 + 0.08, 0, -w2 - 0.08, h2 + 0.08 - k, 0,
      w2 + 0.08, h2 + 0.08, 0, w2 + 0.08 - k, h2 + 0.08, 0, w2 + 0.08, h2 + 0.08, 0, w2 + 0.08, h2 + 0.08 - k, 0,
      -w2 - 0.08, -h2 - 0.08, 0, -w2 - 0.08 + k, -h2 - 0.08, 0, -w2 - 0.08, -h2 - 0.08, 0, -w2 - 0.08, -h2 - 0.08 + k, 0,
      w2 + 0.08, -h2 - 0.08, 0, w2 + 0.08 - k, -h2 - 0.08, 0, w2 + 0.08, -h2 - 0.08, 0, w2 + 0.08, -h2 - 0.08 + k, 0,
    ]
    const fg = new THREE.BufferGeometry()
    fg.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3))
    this.frame = new THREE.LineSegments(fg, new THREE.LineBasicMaterial({ color: accent, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending }))
    this.frame.position.z = 0.01
    this.rig.add(this.frame)

    // champ de flux (particules GPU)
    const count = low ? 1800 : 5200
    const seeds = new Float32Array(count * 4)
    for (let i = 0; i < seeds.length; i++) seeds[i] = Math.random()
    const flowGeo = new THREE.BufferGeometry()
    flowGeo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(count * 3), 3))
    flowGeo.setAttribute('aSeed', new THREE.Float32BufferAttribute(seeds, 4))
    flowGeo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 40)
    this.flowMat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 }, uPixelRatio: { value: this.renderer.getPixelRatio() }, uMode: { value: this.mode },
        uBurst: { value: 0 }, uSigma: { value: 1 }, uPlate: { value: new THREE.Vector2(this.plateW, this.plateH) },
        uAccent: { value: accent }, uA: { value: pa },
      },
      vertexShader: FLOW_VERT,
      fragmentShader: FLOW_FRAG,
    })
    this.rig.add(new THREE.Points(flowGeo, this.flowMat))

    this.buildWords()

    this.ro = new ResizeObserver(() => this.resize())
    this.ro.observe(host)
    this.resize()
    host.addEventListener('pointermove', this.onPointer)
    this.raf = requestAnimationFrame(this.tick)
  }

  private onPointer = (e: PointerEvent) => {
    const r = this.host.getBoundingClientRect()
    this.pointer.x = ((e.clientX - r.left) / Math.max(1, r.width)) * 2 - 1
    this.pointer.y = ((e.clientY - r.top) / Math.max(1, r.height)) * 2 - 1
  }

  private buildWords() {
    const p = this.props
    const words = promptWords(p.prompt || '')
    const subject = new Set((p.subjectWords ?? []).map((w) => w.toLowerCase()))
    const text = new Set((p.inscriptionWords ?? []).map((w) => w.toLowerCase()))
    const all = [...(p.inscriptionWords ?? []), ...words.filter((w) => !text.has(w.toLowerCase()))].slice(0, 14)
    all.forEach((w, i) => {
      const kind: WordSprite['kind'] = text.has(w.toLowerCase()) ? 'text' : subject.has(w.toLowerCase()) ? 'subject' : 'word'
      const { tex, aspect } = wordTexture(w, kind, p.accent)
      const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0 })
      const sprite = new THREE.Sprite(mat)
      const h = kind === 'word' ? 0.32 : 0.42
      sprite.scale.set(h * aspect * (kind === 'word' ? 1 : 0.85), h * (kind === 'word' ? 1 : 1.3), 1)
      this.rig.add(sprite)
      this.words.push({ sprite, mat, tex, seed: (i + 0.5) / Math.max(1, all.length), kind, absorbedAt: null })
    })
  }

  private resize() {
    const w = Math.max(1, this.host.clientWidth)
    const h = Math.max(1, this.host.clientHeight)
    this.renderer.setSize(w, h, false)
    this.camera.aspect = w / h
    // la plaque, son cadran et les mots tiennent dans la vue, quel que soit le format
    const fit = Math.max(this.plateH * 1.9, (this.plateW * 1.9) / this.camera.aspect)
    this.camera.position.z = fit / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)))
    this.camera.updateProjectionMatrix()
  }

  private setPreview(url: string | null) {
    if (!url || url === this.previewUrl) return
    this.previewUrl = url
    this.loader.load(url, (tex) => {
      if (!this.alive) { tex.dispose(); return }
      tex.colorSpace = THREE.SRGBColorSpace
      this.previewTex?.dispose()
      this.previewTex = tex
      this.plateMat.uniforms.uPreview.value = tex
    })
  }

  private setFinal(url: string | null) {
    if (!url || url === this.finalUrl) return
    this.finalUrl = url
    this.loader.load(url, (tex) => {
      if (!this.alive) { tex.dispose(); return }
      tex.colorSpace = THREE.SRGBColorSpace
      this.finalTex = tex
      this.plateMat.uniforms.uFinal.value = tex
      this.revealStart = performance.now()
    })
  }

  private setRef(url: string | null) {
    if (!url || url === this.refUrl) return
    this.refUrl = url
    this.loader.load(url, (tex) => {
      if (!this.alive) { tex.dispose(); return }
      tex.colorSpace = THREE.SRGBColorSpace
      this.refTex = tex
      this.plateMat.uniforms.uRef.value = tex
      const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, opacity: 0 })
      const sprite = new THREE.Sprite(mat)
      const ar = tex.image && tex.image.width ? tex.image.width / tex.image.height : 1
      sprite.scale.set(1.2 * ar, 1.2, 1)
      this.rig.add(sprite)
      this.refSprites.push({ sprite, mat, tex, at: performance.now() })
    })
  }

  private tick = (now: number) => {
    if (!this.alive) return
    this.raf = requestAnimationFrame(this.tick)
    if (now - this.last < 15) return
    const dt = Math.min(0.1, (now - this.last) / 1000)
    this.last = now
    const t = now / 1000
    const p = this.props
    const live = readComfyLive()
    // seul le graphe soumis par cette génération pilote la plaque (pas un rendu précédent)
    const ownRun = live.module === 'image' && live.runAt >= (p.sessionStartedAt ?? 0) - 1000
    const stage: ComfyStage = ownRun ? live.stage : 'queued'
    if (stage !== this.stageSeen) { this.stageSeen = stage; this.stageAt = now }
    if (ownRun && live.step !== this.lastStep) { this.lastStep = live.step; this.stepAt = now }
    if (ownRun) this.setPreview(live.previewUrl)
    this.setFinal(p.resultUrl ?? null)
    if (p.refs?.length) this.setRef(p.refs[0].url)

    const diffusing = p.phaseIdx >= 2 && !p.done
    const sampling = ownRun && stage === 'sampling'
    const decoding = ownRun && (stage === 'decode' || stage === 'upscale' || stage === 'save' || stage === 'done')
    const loading = ownRun && (stage === 'load_model' || stage === 'load_text_encoder' || stage === 'load_vae')
    const encoding = ownRun && (stage === 'encode_text' || stage === 'encode_reference')

    // bruit réel : courbe du planificateur au pas atteint (1 avant le premier pas, 0 après décodage)
    const sigmaTarget = p.done || decoding ? 0 : sampling ? fluxSigmaAt(live.step, live.max) : 1
    this.sigmaShown += (sigmaTarget - this.sigmaShown) * Math.min(1, dt * 4)
    const loadTarget = loading ? Math.min(0.92, (now - this.stageAt) / 9000) : diffusing || p.done ? 1 : 0.15
    this.loadShown += (loadTarget - this.loadShown) * Math.min(1, dt * 2.5)
    const formTarget = p.phaseIdx >= 2 || p.done ? 1 : p.phaseIdx === 1 ? 0.35 : 0.18
    this.formShown += (formTarget - this.formShown) * Math.min(1, dt * 1.5)
    const decodeTarget = p.done ? 1 : decoding ? 1 : 0
    this.decodeShown += (decodeTarget - this.decodeShown) * Math.min(1, dt * (decoding ? 1.2 : 3))

    // mélange des comportements du flux selon la sous-étape réelle
    const target = new THREE.Vector4(
      !diffusing && !loading && !encoding ? 1 : 0,
      loading ? 1 : 0,
      encoding ? 1 : 0,
      sampling || (diffusing && !loading && !encoding) ? 1 : 0,
    )
    const sum = target.x + target.y + target.z + target.w || 1
    target.multiplyScalar(1 / sum)
    this.mode.lerp(target, Math.min(1, dt * 2.2))

    const previewTarget = ownRun && this.previewTex && !p.done ? 1 : 0
    this.previewMix += (previewTarget - this.previewMix) * Math.min(1, dt * 3)
    const reveal = this.finalTex ? Math.min(1, (now - this.revealStart) / 1800) : 0

    const u = this.plateMat.uniforms
    u.uTime.value = t
    u.uSigma.value = this.sigmaShown
    u.uForm.value = this.formShown
    u.uLoad.value = this.loadShown
    u.uDecode.value = this.decodeShown
    u.uPreviewMix.value = this.previewMix
    u.uRefMix.value = this.refTex && !p.done ? Math.min(1, p.phaseIdx >= 1 ? 1 : 0) : 0
    u.uReveal.value = reveal
    u.uWave.value = sampling ? Math.min(1.2, (now - this.stepAt) / 700) : -1

    const pulse = Math.min(1, (Date.now() - p.readPulseAt()) / 900)
    const h = this.haloMat.uniforms
    h.uTime.value = t
    h.uSteps.value = ownRun ? live.step : 0
    h.uMax.value = ownRun && live.max ? live.max : 28
    h.uSigma.value = this.sigmaShown
    h.uPulse.value = pulse
    h.uActive.value += ((diffusing || sampling || p.done ? 1 : 0.25) - h.uActive.value) * Math.min(1, dt * 2)

    const f = this.flowMat.uniforms
    f.uTime.value = t
    f.uSigma.value = this.sigmaShown
    f.uBurst.value = p.done ? Math.min(1, reveal * 1.4) : 0

    // mots de la demande : orbite pendant l'analyse, absorption au vrai moment de l'encodage
    const absorbing = encoding || sampling || decoding || p.phaseIdx >= 2 || p.done
    const nWords = this.words.length
    this.words.forEach((wd, i) => {
      if (absorbing && wd.absorbedAt == null) wd.absorbedAt = now + i * 110
      const ang = wd.seed * Math.PI * 2 + t * 0.12
      const radX = this.plateW * 0.5 + 1.3 + (i % 3) * 0.35
      const radY = this.plateH * 0.5 + 0.55 + ((i * 7) % 3) * 0.2
      const ox = Math.cos(ang) * radX
      const oy = Math.sin(ang) * radY * 0.95
      const oz = 0.6 + Math.sin(t * 0.5 + i) * 0.25
      let a = 0.95
      let x = ox, y = oy, z = oz
      if (wd.absorbedAt != null && now >= wd.absorbedAt) {
        const k = Math.min(1, (now - wd.absorbedAt) / 1300)
        const e = k * k * (3 - 2 * k)
        x = ox * (1 - e)
        y = oy * (1 - e)
        z = oz * (1 - e) + 0.05
        a = 1 - e
      }
      wd.sprite.position.set(x, y, z)
      wd.mat.opacity = Math.max(0, Math.min(1, a)) * (p.done ? 0 : 1) * (nWords ? 1 : 0)
    })

    // référence : glisse vers la plaque à l'étape « Référence visuelle »
    for (const r of this.refSprites) {
      const k = Math.min(1, (now - r.at) / 1600)
      const e = k * k * (3 - 2 * k)
      r.sprite.position.set(-this.plateW * 0.5 - 1.4 + e * (this.plateW * 0.5 + 1.4), 0.2 * (1 - e), 0.9 * (1 - e) + 0.03)
      r.mat.opacity = (1 - e * 0.95) * (p.done ? 0 : 1)
      r.sprite.scale.multiplyScalar(1 - dt * 0.4 * e)
    }

    // parallaxe douce (pointeur + respiration)
    const tx = this.pointer.y * 0.08 + Math.sin(t * 0.31) * 0.035
    const ty = this.pointer.x * 0.12 + Math.sin(t * 0.23) * 0.06
    this.rig.rotation.x += (tx - this.rig.rotation.x) * Math.min(1, dt * 3)
    this.rig.rotation.y += (ty * (p.done ? 0.2 : 1) - this.rig.rotation.y) * Math.min(1, dt * 3)
    ;(this.frame.material as THREE.LineBasicMaterial).opacity = 0.55 + 0.35 * (1 - pulse)

    this.renderer.render(this.scene, this.camera)
  }

  dispose() {
    this.alive = false
    cancelAnimationFrame(this.raf)
    this.ro.disconnect()
    this.host.removeEventListener('pointermove', this.onPointer)
    for (const w of this.words) { w.tex.dispose(); w.mat.dispose() }
    for (const r of this.refSprites) { r.mat.dispose() }
    this.previewTex?.dispose()
    this.finalTex?.dispose()
    this.refTex?.dispose()
    this.blankPreview.dispose(); this.blankRef.dispose(); this.blankFinal.dispose()
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

export default function DiffusionStage(props: DiffusionStageProps) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const sceneRef = useRef<DiffusionScene | null>(null)
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let scene: DiffusionScene | null = null
    try {
      scene = new DiffusionScene(host, props)
      sceneRef.current = scene
    } catch {
      // WebGL indisponible : l'écran garde son HUD et sa scène 2D
    }
    return () => { scene?.dispose(); sceneRef.current = null }
    // la scène est construite une fois par génération (prompt, format, qualité)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.prompt, props.aspect, props.quality])
  if (sceneRef.current) sceneRef.current.props = props
  useEffect(() => { if (sceneRef.current) sceneRef.current.props = props })
  return <div ref={hostRef} style={{ position: 'absolute', inset: 0, overflow: 'hidden' }} />
}
