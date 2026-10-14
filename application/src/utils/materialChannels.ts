import type { MeshStandardMaterial, MeshPhysicalMaterialParameters } from 'three'

/** Preserve authored visual channels when adding physical shading features. */
export function materialChannels(source: MeshStandardMaterial, geometryHasColors = false): MeshPhysicalMaterialParameters {
  return {
    color: source.color, map: source.map, vertexColors: source.vertexColors || geometryHasColors,
    normalMap: source.normalMap, normalMapType: source.normalMapType, normalScale: source.normalScale,
    roughnessMap: source.roughnessMap, metalnessMap: source.metalnessMap,
    aoMap: source.aoMap, aoMapIntensity: source.aoMapIntensity,
    emissive: source.emissive, emissiveMap: source.emissiveMap, emissiveIntensity: source.emissiveIntensity,
    alphaMap: source.alphaMap, alphaTest: source.alphaTest,
    transparent: source.transparent, opacity: source.opacity,
    side: source.side, flatShading: source.flatShading, toneMapped: source.toneMapped,
  }
}
