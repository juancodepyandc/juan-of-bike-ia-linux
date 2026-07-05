// Validateur glTF 2.0 (lecture du JSON, pas le binaire GLB embedded).
// Vérifie la conformité minimale d'un asset 3D produit par le pipeline
// (Hunyuan3D + Blender export) avant de l'accepter dans la lib :
//
//   - structure glTF 2.0 cohérente (asset.version, scenes, nodes, meshes)
//   - références internes valides (chaque mesh ref existe, chaque material ref existe)
//   - matérials PBR avec baseColorFactor ou baseColorTexture
//   - meshes ont POSITION attribute
//   - animations cohérentes (channels pointent vers nodes valides)
//   - extensions déclarées dans extensionsUsed/extensionsRequired
//
// Module pur — pas de dépendance binaire/three.

export type GltfAsset = {
  version: string
  generator?: string
  copyright?: string
}

export type GltfRoot = {
  asset: GltfAsset
  scene?: number
  scenes?: Array<{ nodes?: number[]; name?: string }>
  nodes?: Array<{ mesh?: number; skin?: number; children?: number[]; name?: string }>
  meshes?: Array<{ primitives: Array<{ attributes: Record<string, number>; indices?: number; material?: number }>; name?: string }>
  materials?: Array<{ name?: string; pbrMetallicRoughness?: { baseColorFactor?: number[]; baseColorTexture?: { index: number }; metallicFactor?: number; roughnessFactor?: number }; normalTexture?: { index: number }; emissiveFactor?: number[] }>
  textures?: Array<{ source?: number; sampler?: number }>
  images?: Array<{ uri?: string; bufferView?: number; mimeType?: string }>
  accessors?: Array<{ bufferView?: number; componentType: number; count: number; type: string }>
  bufferViews?: Array<{ buffer: number; byteOffset?: number; byteLength: number }>
  buffers?: Array<{ uri?: string; byteLength: number }>
  animations?: Array<{ channels: Array<{ sampler: number; target: { node?: number; path: string } }>; samplers: Array<{ input: number; output: number; interpolation?: string }>; name?: string }>
  skins?: Array<{ joints: number[]; inverseBindMatrices?: number; skeleton?: number }>
  extensionsUsed?: string[]
  extensionsRequired?: string[]
}

export type GltfIssue = {
  severity: 'info' | 'warn' | 'error' | 'block'
  message: string
  /** Pointer JSON ("/meshes/0/primitives/0/attributes"). */
  pointer?: string
}

export type GltfValidationReport = {
  valid: boolean
  hasBlocker: boolean
  issues: GltfIssue[]
  /** Stats : mesh count, vertex count estimé, animation count, texture count. */
  stats: {
    meshes: number
    primitives: number
    materials: number
    animations: number
    textures: number
    skins: number
    nodes: number
  }
}

export function validateGltfJson(input: unknown): GltfValidationReport {
  const issues: GltfIssue[] = []
  const stats = {
    meshes: 0, primitives: 0, materials: 0, animations: 0,
    textures: 0, skins: 0, nodes: 0,
  }

  if (input == null || typeof input !== 'object') {
    return {
      valid: false,
      hasBlocker: true,
      issues: [{ severity: 'block', message: 'Input n\'est pas un objet JSON.' }],
      stats,
    }
  }
  const root = input as Partial<GltfRoot>

  // 1. Asset block obligatoire
  if (!root.asset || typeof root.asset !== 'object') {
    issues.push({ severity: 'block', message: 'asset block manquant.', pointer: '/asset' })
  } else {
    if (!root.asset.version) {
      issues.push({ severity: 'block', message: 'asset.version manquant.', pointer: '/asset/version' })
    } else if (!root.asset.version.startsWith('2.')) {
      issues.push({ severity: 'error', message: `glTF version ${root.asset.version} non supportée (attendu 2.x).`, pointer: '/asset/version' })
    }
  }

  // 2. Scenes / scene index par défaut
  if (!root.scenes || !Array.isArray(root.scenes) || root.scenes.length === 0) {
    issues.push({ severity: 'warn', message: 'Aucune scene déclarée — peut être chargé mais rien à rendre par défaut.', pointer: '/scenes' })
  } else if (root.scene != null && (root.scene < 0 || root.scene >= root.scenes.length)) {
    issues.push({ severity: 'error', message: `scene index ${root.scene} hors range (${root.scenes.length} scenes).`, pointer: '/scene' })
  }

  // 3. Nodes & cross-refs
  stats.nodes = root.nodes?.length ?? 0
  if (root.nodes) {
    for (let i = 0; i < root.nodes.length; i += 1) {
      const node = root.nodes[i]
      if (node.mesh != null && (!root.meshes || node.mesh < 0 || node.mesh >= root.meshes.length)) {
        issues.push({ severity: 'error', message: `Node ${i} ref mesh ${node.mesh} inexistant.`, pointer: `/nodes/${i}/mesh` })
      }
      if (node.children) {
        for (const c of node.children) {
          if (c < 0 || c >= (root.nodes?.length ?? 0)) {
            issues.push({ severity: 'error', message: `Node ${i} ref child ${c} hors range.`, pointer: `/nodes/${i}/children` })
          }
        }
      }
    }
  }

  // 4. Meshes : POSITION obligatoire
  stats.meshes = root.meshes?.length ?? 0
  if (root.meshes) {
    for (let i = 0; i < root.meshes.length; i += 1) {
      const mesh = root.meshes[i]
      if (!mesh.primitives || mesh.primitives.length === 0) {
        issues.push({ severity: 'error', message: `Mesh ${i} sans primitives.`, pointer: `/meshes/${i}/primitives` })
        continue
      }
      stats.primitives += mesh.primitives.length
      for (let p = 0; p < mesh.primitives.length; p += 1) {
        const prim = mesh.primitives[p]
        // POSITION peut être l'accessor index 0 — utiliser == null, pas falsy.
        if (prim.attributes == null || prim.attributes.POSITION == null) {
          issues.push({ severity: 'error', message: `Mesh ${i} primitive ${p} sans attribute POSITION.`, pointer: `/meshes/${i}/primitives/${p}/attributes` })
        }
        if (prim.material != null && (!root.materials || prim.material < 0 || prim.material >= root.materials.length)) {
          issues.push({ severity: 'error', message: `Mesh ${i} primitive ${p} ref material ${prim.material} inexistant.`, pointer: `/meshes/${i}/primitives/${p}/material` })
        }
      }
    }
  }

  // 5. Materials : doit avoir au moins un couleur de base
  stats.materials = root.materials?.length ?? 0
  if (root.materials) {
    for (let i = 0; i < root.materials.length; i += 1) {
      const mat = root.materials[i]
      const pbr = mat.pbrMetallicRoughness
      if (!pbr || (!pbr.baseColorFactor && !pbr.baseColorTexture)) {
        issues.push({ severity: 'warn', message: `Material ${i} sans baseColor — rendu apparaîtra blanc.`, pointer: `/materials/${i}/pbrMetallicRoughness` })
      }
    }
  }

  // 6. Textures → images → buffer cohérent
  stats.textures = root.textures?.length ?? 0
  if (root.textures) {
    for (let i = 0; i < root.textures.length; i += 1) {
      const tex = root.textures[i]
      if (tex.source != null && (!root.images || tex.source < 0 || tex.source >= root.images.length)) {
        issues.push({ severity: 'error', message: `Texture ${i} ref image ${tex.source} inexistante.`, pointer: `/textures/${i}/source` })
      }
    }
  }

  // 7. Animations
  stats.animations = root.animations?.length ?? 0
  if (root.animations) {
    for (let i = 0; i < root.animations.length; i += 1) {
      const anim = root.animations[i]
      if (!anim.channels || anim.channels.length === 0) {
        issues.push({ severity: 'warn', message: `Animation ${i} vide.`, pointer: `/animations/${i}` })
        continue
      }
      for (let c = 0; c < anim.channels.length; c += 1) {
        const ch = anim.channels[c]
        if (ch.sampler == null || ch.sampler < 0 || ch.sampler >= anim.samplers.length) {
          issues.push({ severity: 'error', message: `Animation ${i} channel ${c} sampler ${ch.sampler} invalide.`, pointer: `/animations/${i}/channels/${c}` })
        }
        if (ch.target.node != null && (!root.nodes || ch.target.node < 0 || ch.target.node >= root.nodes.length)) {
          issues.push({ severity: 'error', message: `Animation ${i} target node ${ch.target.node} inexistant.`, pointer: `/animations/${i}/channels/${c}/target/node` })
        }
      }
    }
  }

  // 8. Skins
  stats.skins = root.skins?.length ?? 0
  if (root.skins) {
    for (let i = 0; i < root.skins.length; i += 1) {
      const skin = root.skins[i]
      if (!skin.joints || skin.joints.length === 0) {
        issues.push({ severity: 'error', message: `Skin ${i} sans joints.`, pointer: `/skins/${i}/joints` })
      } else {
        for (const j of skin.joints) {
          if (!root.nodes || j < 0 || j >= root.nodes.length) {
            issues.push({ severity: 'error', message: `Skin ${i} joint ${j} hors range.`, pointer: `/skins/${i}/joints` })
            break
          }
        }
      }
    }
  }

  // 9. Extensions required mais absent de used
  if (root.extensionsRequired) {
    const used = new Set(root.extensionsUsed ?? [])
    for (const ext of root.extensionsRequired) {
      if (!used.has(ext)) {
        issues.push({ severity: 'error', message: `Extension required "${ext}" absente de extensionsUsed.`, pointer: '/extensionsRequired' })
      }
    }
  }

  const hasBlocker = issues.some((i) => i.severity === 'block')
  const hasError = issues.some((i) => i.severity === 'error')
  return {
    valid: !hasBlocker && !hasError,
    hasBlocker,
    issues,
    stats,
  }
}

/**
 * Lit la version glTF + générateur depuis un blob JSON, sans valider.
 * Utile pour les badges UI ("Blender 4.0", "Hunyuan3D-2").
 */
export function readGltfHeader(input: unknown): { version: string; generator: string | null } | null {
  if (input == null || typeof input !== 'object') return null
  const root = input as Partial<GltfRoot>
  if (!root.asset?.version) return null
  return { version: root.asset.version, generator: root.asset.generator ?? null }
}
