import { captureOwnerStack } from 'react'

declare global {
  interface Window {
    __auroraReactKeyStacks?: string[]
  }
}

export function installReactKeyProbe() {
  const originalError = console.error
  window.__auroraReactKeyStacks = []
  console.error = (...args: unknown[]) => {
    if (String(args[0] || '').includes('same key')) {
      const ownerStack = captureOwnerStack?.()
      if (ownerStack) window.__auroraReactKeyStacks?.push(ownerStack)
    }
    originalError(...args)
  }
}
