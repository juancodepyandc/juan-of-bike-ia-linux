import { lazy, type ComponentType } from 'react'
import { readUiSkin, type UiSkinId } from './uiSkin'

type ViewMod = { default: ComponentType }

export function pickView(loaders: Partial<Record<UiSkinId, () => Promise<ViewMod>>>): ComponentType {
  const skin = readUiSkin()
  const loader = loaders[skin]
    ?? (skin === 'aurora_v4' ? loaders.aurora_v1 : undefined)
    ?? loaders.manga
    ?? loaders.aurora_v1
    ?? loaders.aurora_v3
  if (!loader) {
    throw new Error(`pickView: no loader registered for skin=${skin}`)
  }
  return lazy(loader)
}
