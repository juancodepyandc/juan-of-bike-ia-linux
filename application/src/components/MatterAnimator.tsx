// Matière vivante du viewer (16/11/2026) : les gaz et l'eau des modèles générés se voient comme de la vraie
// matière, pas comme des bulles.
// - Gaz SIMULÉS (brume d'un vaporisateur, fumée, vapeur, flamme : nœuds `aurora_volume`, écrits par
//   python-services/monde/volume_gltf.py) : rendus en volume par lancer de rayons (services/matterVolume.ts).
// - Anciennes émissions faites de particules (GLB d'avant la simulation) : une bouffée douce par particule de
//   gaz ; les gouttes d'eau restent de vraies gouttes (leur maillage, leur matériau d'eau).
// - Eau sans écoulement déclaré (anciens GLB du moteur « monde », sans extras aurora_flow) : ses textures
//   défilent. Une eau qui porte aurora_flow est animée par le shader d'écoulement de ModelView.
import { useEffect, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { AdditiveBlending, CanvasTexture, Color, NormalBlending, RepeatWrapping, Sprite, SpriteMaterial } from 'three'
import type { Material, Mesh, MeshStandardMaterial, Object3D, Texture } from 'three'
import { GasVolume, readVolumeMeta, volumeSource } from '../services/matterVolume'

interface Rendu { couleur: string; opacite: number; additif: boolean; taille: number }

// particules de gaz des anciens GLB uniquement (les nouveaux portent un volume simulé)
const RENDUS_GAZ: Record<string, Rendu> = {
  brume: { couleur: '#eaf2ff', opacite: 0.22, additif: true, taille: 2.6 },
  vapeur: { couleur: '#f2f6ff', opacite: 0.2, additif: true, taille: 2.6 },
  fumee: { couleur: '#7f8389', opacite: 0.34, additif: false, taille: 2.8 },
  flamme: { couleur: '#ffad42', opacite: 0.9, additif: true, taille: 2.4 },
}

let textureDouce: Texture | null = null

/** Dégradé radial : cœur dense, bords qui s'évanouissent (une bouffée, pas une boule). */
function douce(): Texture {
  if (textureDouce) return textureDouce
  const toile = document.createElement('canvas')
  toile.width = toile.height = 128
  const ctx = toile.getContext('2d')
  if (ctx) {
    const degrade = ctx.createRadialGradient(64, 64, 0, 64, 64, 64)
    degrade.addColorStop(0, 'rgba(255,255,255,1)')
    degrade.addColorStop(0.3, 'rgba(255,255,255,0.6)')
    degrade.addColorStop(0.65, 'rgba(255,255,255,0.18)')
    degrade.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = degrade
    ctx.fillRect(0, 0, 128, 128)
  }
  textureDouce = new CanvasTexture(toile)
  return textureDouce
}

function materiaux(m: Mesh): Material[] {
  return Array.isArray(m.material) ? m.material : [m.material]
}

function ecoulementDeclare(mat: Material): boolean {
  const ud = (mat.userData ?? {}) as Record<string, unknown>
  const extras = (ud.gltfExtras ?? ud.extras ?? {}) as Record<string, unknown>
  return Boolean(extras.aurora_flow ?? ud.aurora_flow)
}

export function MatterAnimator({ modelRoot }: { modelRoot: Object3D | null }) {
  const eaux = useRef<Texture[]>([])
  const volumes = useRef<GasVolume[]>([])

  useEffect(() => {
    if (!modelRoot) return
    let annule = false
    const defaire: Array<() => void> = []
    const textures = new Set<Texture>()
    const particules: Array<[Object3D, Rendu]> = []
    const gaz: Object3D[] = []
    modelRoot.traverse((objet) => {
      if (readVolumeMeta(objet)) {
        gaz.push(objet)
        return
      }
      const type = (objet.userData as { emission?: string }).emission
      if (type && RENDUS_GAZ[type]) particules.push([objet, RENDUS_GAZ[type]])
      const m = objet as Mesh
      if (!m.isMesh) return
      for (const mat of materiaux(m)) {
        if (!/(^|_)eau(_|$)/.test(mat?.name || '') || ecoulementDeclare(mat)) continue
        const standard = mat as MeshStandardMaterial
        for (const t of [standard.map, standard.normalMap, standard.roughnessMap]) {
          if (!t) continue
          t.wrapS = RepeatWrapping
          t.wrapT = RepeatWrapping
          t.needsUpdate = true
          textures.add(t)
        }
      }
    })
    for (const noeud of gaz) {
      const meta = readVolumeMeta(noeud)
      const source = volumeSource(noeud)
      if (!meta || !source) continue
      source.then((tampon) => {
        if (annule) return
        const volume = new GasVolume(meta, tampon)
        noeud.add(volume.mesh)
        volumes.current.push(volume)
        console.info(`[matière] gaz simulé « ${meta.milieu} » : ${meta.dims.join('×')} cellules, ${meta.images} images`)
        defaire.push(() => {
          noeud.remove(volume.mesh)
          volume.dispose()
        })
      }).catch(() => { /* gaz illisible : le modèle reste affiché */ })
    }
    for (const [objet, rendu] of particules) {
      // le volume brut de la particule disparaît, sans toucher au matériau partagé
      const cacher = (m: Mesh) => {
        const avant = m.material
        m.material = materiaux(m).map((mat) => { const copie = mat.clone(); copie.visible = false; return copie }) as unknown as Material
        defaire.push(() => { m.material = avant })
      }
      if ((objet as Mesh).isMesh) cacher(objet as Mesh)
      objet.children.forEach((enfant) => { if ((enfant as Mesh).isMesh) cacher(enfant as Mesh) })
      const sprite = new Sprite(new SpriteMaterial({
        map: douce(),
        color: new Color(rendu.couleur),
        transparent: true,
        opacity: rendu.opacite,
        depthWrite: false,
        blending: rendu.additif ? AdditiveBlending : NormalBlending,
      }))
      sprite.scale.setScalar(rendu.taille)               // la particule est une sphère de rayon 1 mise à l'échelle
      sprite.renderOrder = 20
      objet.add(sprite)
      defaire.push(() => { objet.remove(sprite); (sprite.material as SpriteMaterial).dispose() })
    }
    eaux.current = [...textures]
    return () => {
      annule = true
      defaire.forEach((f) => f())
      eaux.current = []
      volumes.current = []
    }
  }, [modelRoot])

  useFrame((state, delta) => {
    const pas = Math.min(delta, 0.05)
    for (const t of eaux.current) {
      t.offset.x += 0.11 * pas                             // ≈ 0,4 m/s pour une texture d'eau de 4 m
      t.offset.y += 0.04 * pas
    }
    for (const v of volumes.current) v.update(state.clock.elapsedTime, state.camera)
  })

  return null
}
