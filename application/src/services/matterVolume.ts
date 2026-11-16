// Gaz simulés rendus comme de la vraie matière (16/11/2026).
//
// Le moteur « monde » simule une brume de vaporisateur, une fumée, une vapeur ou une flamme par les équations
// de Navier-Stokes (python-services/monde/gaz.py) et écrit le résultat dans le GLB : un nœud vide dont les
// extras `aurora_volume` (schéma aurora.volume.v1) décrivent la boîte, la cadence et l'optique du milieu, et
// désignent une vue du tampon binaire où sont rangées les images (uint8 en racine de la densité, zlib, x le plus
// rapide, canaux densité[/chaleur] entrelacés). Ici : la vue est lue par le parseur glTF, chaque image est
// décompressée à la demande dans une texture 3D, et le gaz est rendu par lancer de rayons — diffusion simple
// avec ombre propre vers la lumière, fonction de phase de Henyey-Greenstein (une brume de gouttelettes s'illumine
// à contre-jour), lumière du ciel, émission de corps noir pour une flamme. Deux images voisines sont fondues
// pour un mouvement continu. Un fin bruit fractal animé ajoute le détail plus petit que la grille simulée.
import {
  BackSide,
  BoxGeometry,
  ClampToEdgeWrapping,
  CustomBlending,
  Data3DTexture,
  FrontSide,
  GLSL3,
  LinearFilter,
  Mesh,
  OneFactor,
  OneMinusSrcAlphaFactor,
  Quaternion,
  RGFormat,
  RedFormat,
  ShaderMaterial,
  UnsignedByteType,
  Vector3,
} from 'three'
import type { Camera, Object3D } from 'three'
import { unzlibSync } from 'three/examples/jsm/libs/fflate.module.js'

export interface VolumeMeta {
  schema: 'aurora.volume.v1'
  milieu: string
  dims: [number, number, number]
  boite: { min: [number, number, number]; max: [number, number, number] }
  fps: number
  images: number
  canaux: string[]
  bufferView: number
  decalages: number[]
  direction?: [number, number, number]
  optique: { albedo: [number, number, number]; extinction: number; anisotropie: number; emission: number }
}

interface GltfParserLike { getDependency: (type: string, index: number) => Promise<unknown> }

const SOURCES = new WeakMap<Object3D, Promise<ArrayBuffer>>()

function triple(v: unknown): v is [number, number, number] {
  return Array.isArray(v) && v.length === 3 && v.every((x) => Number.isFinite(Number(x)))
}

/** Les extras d'un nœud décrivent-ils un gaz simulé lisible ? */
export function readVolumeMeta(o: Object3D): VolumeMeta | null {
  const raw = (o.userData as { aurora_volume?: unknown }).aurora_volume
  if (!raw || typeof raw !== 'object') return null
  const m = raw as Record<string, unknown>
  if (m.schema !== 'aurora.volume.v1') return null
  const boite = m.boite as Record<string, unknown> | undefined
  const optique = m.optique as Record<string, unknown> | undefined
  const decalages = m.decalages as unknown[] | undefined
  if (!triple(m.dims) || !boite || !triple(boite.min) || !triple(boite.max) || !optique) return null
  if (!Array.isArray(decalages) || decalages.length !== Number(m.images) + 1 || !Number.isInteger(m.bufferView)) return null
  return m as unknown as VolumeMeta
}

/** À l'ouverture d'un GLB : chaque gaz est relié à sa vue binaire (lue une fois, à la demande du rendu). */
export function registerVolumeSources(gltf: { scene: Object3D; parser?: GltfParserLike }): number {
  const parser = gltf.parser
  if (!parser) return 0
  let n = 0
  gltf.scene.traverse((o) => {
    const meta = readVolumeMeta(o)
    if (!meta) return
    SOURCES.set(o, parser.getDependency('bufferView', meta.bufferView) as Promise<ArrayBuffer>)
    n += 1
  })
  return n
}

export function volumeSource(o: Object3D): Promise<ArrayBuffer> | null {
  return SOURCES.get(o) ?? null
}

const VERT = /* glsl */ `
out vec3 vLocal;
void main() {
  vLocal = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`

// three r183 : un ShaderMaterial écrit en GLSL3 déclare lui-même sa sortie ; les morceaux de tone mapping et
// d'espace colorimétrique inclus en fin de shader écrivent `gl_FragColor`, d'où la définition.
const FRAG = /* glsl */ `
precision highp float;
precision highp sampler3D;
layout(location = 0) out highp vec4 pc_fragColor;
#define gl_FragColor pc_fragColor
in vec3 vLocal;
uniform sampler3D uA;
uniform sampler3D uB;
uniform float uMix;
uniform vec3 uCam;
uniform vec3 uHalf;
uniform vec3 uLight;
uniform vec3 uLightColor;
uniform vec3 uAmbient;
uniform vec3 uAlbedo;
uniform float uSigma;
uniform float uG;
uniform float uEmission;
uniform float uFlame;
uniform float uVoxel;
uniform float uTime;
uniform float uDetail;
uniform vec3 uDrift;

float hash3(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float noise3(vec3 x) {
  vec3 i = floor(x);
  vec3 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), f.x), mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), f.x), mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}
float fbm(vec3 p) {
  float a = 0.5, s = 0.0;
  for (int i = 0; i < 4; i++) { s += a * noise3(p); p = p * 2.07 + vec3(11.3, 7.1, 3.7); a *= 0.5; }
  return s / 0.9375;
}
vec2 field(vec3 p) {
  vec3 uvw = p / (2.0 * uHalf) + 0.5;
  vec2 q = mix(texture(uA, uvw).rg, texture(uB, uvw).rg, uMix);
  return q * q;
}
float phaseHG(float c, float g) {
  float g2 = g * g;
  return (1.0 - g2) / pow(max(1.0 + g2 - 2.0 * g * c, 1e-4), 1.5);
}
vec2 boxHit(vec3 ro, vec3 rd) {
  vec3 inv = 1.0 / rd;
  vec3 t0 = (-uHalf - ro) * inv;
  vec3 t1 = (uHalf - ro) * inv;
  vec3 lo = min(t0, t1);
  vec3 hi = max(t0, t1);
  return vec2(max(max(lo.x, lo.y), lo.z), min(min(hi.x, hi.y), hi.z));
}
vec3 blackbody(float t) {
  vec3 c = mix(vec3(0.0), vec3(0.55, 0.04, 0.0), smoothstep(0.0, 0.25, t));
  c = mix(c, vec3(1.0, 0.36, 0.04), smoothstep(0.2, 0.55, t));
  c = mix(c, vec3(1.0, 0.75, 0.32), smoothstep(0.5, 0.85, t));
  return mix(c, vec3(1.0, 0.95, 0.85), smoothstep(0.85, 1.0, t));
}
void main() {
  vec3 ro = uCam;
  vec3 rd = normalize(vLocal - uCam);
  vec2 t = boxHit(ro, rd);
  t.x = max(t.x, 0.0);
  if (t.y <= t.x) discard;
  float ds = uVoxel * 0.6;
  float s = t.x + ds * fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
  float T = 1.0;
  vec3 col = vec3(0.0);
  float phase = phaseHG(dot(rd, uLight), uG);
  for (int i = 0; i < 640; i++) {
    if (s >= t.y || T < 0.008) break;
    vec3 p = ro + rd * s;
    vec2 f = field(p);
    float d = f.x;
    float heat = f.y * uFlame;
    if (d > 0.0004 || heat > 0.002) {
      if (uDetail > 0.0) {
        vec3 q = p / uVoxel * 0.32 - uDrift * uTime;
        d *= mix(1.0, 0.25 + 1.5 * fbm(q), uDetail);
      }
      float tau = 0.0;
      float dl = uVoxel;
      vec3 q2 = p;
      for (int j = 0; j < 6; j++) {
        q2 += uLight * dl;
        if (any(greaterThan(abs(q2), uHalf))) break;
        tau += field(q2).x * dl;
        dl *= 1.6;
      }
      vec3 lum = uAlbedo * (uLightColor * exp(-tau * uSigma) * phase + uAmbient);
      float a = 1.0 - exp(-d * uSigma * ds);
      col += T * a * lum;
      if (heat > 0.002) col += T * blackbody(heat) * uEmission * heat * (ds / uVoxel) * 0.06;
      T *= 1.0 - a;
    }
    s += ds;
  }
  float alpha = 1.0 - T;
  if (alpha < 0.002 && dot(col, col) < 1e-6) discard;
  gl_FragColor = vec4(col, alpha);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`

// Détail sous la grille : marqué pour les gaz turbulents, discret pour une flamme (déjà vive).
const DETAIL: Record<string, number> = { brume: 0.55, fumee: 0.6, vapeur: 0.6, flamme: 0.35 }
// Lumière principale (direction monde vers la lumière) : celle, haute et de face, du studio du viewer.
const LUMIERE = new Vector3(0.45, 0.85, 0.35).normalize()

export class GasVolume {
  readonly mesh: Mesh
  private readonly material: ShaderMaterial
  private readonly textures: [Data3DTexture, Data3DTexture]
  private readonly frames: [number, number] = [-1, -1]
  private readonly bytes: Uint8Array
  private readonly half: Vector3
  private readonly tmp = new Vector3()
  private readonly quat = new Quaternion()

  constructor(private readonly meta: VolumeMeta, buffer: ArrayBuffer) {
    this.bytes = new Uint8Array(buffer)
    const [nx, ny, nz] = meta.dims
    const canaux = meta.canaux.length > 1 ? 2 : 1
    const texture = () => {
      const t = new Data3DTexture(new Uint8Array(nx * ny * nz * canaux), nx, ny, nz)
      t.format = canaux === 2 ? RGFormat : RedFormat
      t.type = UnsignedByteType
      t.minFilter = LinearFilter
      t.magFilter = LinearFilter
      t.wrapS = ClampToEdgeWrapping
      t.wrapT = ClampToEdgeWrapping
      t.wrapR = ClampToEdgeWrapping
      t.unpackAlignment = 1
      t.needsUpdate = true
      return t
    }
    this.textures = [texture(), texture()]
    const mn = new Vector3(...meta.boite.min)
    const mx = new Vector3(...meta.boite.max)
    const taille = mx.clone().sub(mn)
    this.half = taille.clone().multiplyScalar(0.5)
    const flamme = meta.canaux.includes('chaleur')
    const dir = meta.direction ? new Vector3(...meta.direction).normalize() : new Vector3(0, 1, 0)
    this.material = new ShaderMaterial({
      glslVersion: GLSL3,
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: {
        uA: { value: this.textures[0] },
        uB: { value: this.textures[1] },
        uMix: { value: 0 },
        uCam: { value: new Vector3() },
        uHalf: { value: this.half.clone() },
        uLight: { value: LUMIERE.clone() },
        uLightColor: { value: new Vector3(2.4, 2.35, 2.25) },
        uAmbient: { value: new Vector3(0.42, 0.46, 0.55) },
        uAlbedo: { value: new Vector3(...meta.optique.albedo) },
        uSigma: { value: Math.max(1e-6, Number(meta.optique.extinction)) },
        uG: { value: Number(meta.optique.anisotropie) || 0 },
        uEmission: { value: Number(meta.optique.emission) || 0 },
        uFlame: { value: flamme ? 1 : 0 },
        uVoxel: { value: taille.x / nx },
        uTime: { value: 0 },
        uDetail: { value: DETAIL[meta.milieu] ?? 0.5 },
        // le détail dérive avec le gaz : quelques cellules par seconde dans le sens de l'émission
        uDrift: { value: dir.multiplyScalar(0.9) },
      },
      transparent: true,
      depthWrite: false,
      blending: CustomBlending,
      blendSrc: OneFactor,
      blendDst: OneMinusSrcAlphaFactor,
      side: FrontSide,
    })
    this.mesh = new Mesh(new BoxGeometry(taille.x, taille.y, taille.z), this.material)
    this.mesh.position.copy(mn.add(mx).multiplyScalar(0.5))
    this.mesh.name = `aurora_volume_${meta.milieu}`
    this.mesh.renderOrder = 30
  }

  private decoder(image: number, cible: Data3DTexture): void {
    const debut = this.meta.decalages[image]
    const fin = this.meta.decalages[image + 1]
    const brut = unzlibSync(this.bytes.subarray(debut, fin))
    const data = cible.image.data as Uint8Array
    data.set(brut.subarray(0, data.length))
    cible.needsUpdate = true
  }

  /** Avance le gaz à l'instant `temps` (s, en boucle) et oriente le rendu pour la caméra. */
  update(temps: number, camera: Camera): void {
    const n = this.meta.images
    const f = (((temps * this.meta.fps) % n) + n) % n
    const i = Math.floor(f)
    const j = (i + 1) % n
    const u = this.material.uniforms
    if (this.frames[0] !== i) {
      if (this.frames[1] === i) {
        this.textures.reverse()
        this.frames.reverse()
      } else {
        this.decoder(i, this.textures[0])
        this.frames[0] = i
      }
    }
    if (this.frames[1] !== j) {
      this.decoder(j, this.textures[1])
      this.frames[1] = j
    }
    u.uA.value = this.textures[0]
    u.uB.value = this.textures[1]
    u.uMix.value = f - i
    u.uTime.value = temps
    camera.getWorldPosition(this.tmp)
    this.mesh.worldToLocal(this.tmp)
    ;(u.uCam.value as Vector3).copy(this.tmp)
    const dedans = Math.abs(this.tmp.x) < this.half.x && Math.abs(this.tmp.y) < this.half.y && Math.abs(this.tmp.z) < this.half.z
    // caméra dans le nuage : on rend les faces arrière, sans test de profondeur (sinon rien ne s'affiche)
    this.material.side = dedans ? BackSide : FrontSide
    this.material.depthTest = !dedans
    this.mesh.getWorldQuaternion(this.quat).invert()
    ;(u.uLight.value as Vector3).copy(LUMIERE).applyQuaternion(this.quat).normalize()
  }

  dispose(): void {
    this.mesh.geometry.dispose()
    this.material.dispose()
    this.textures.forEach((t) => t.dispose())
  }
}
