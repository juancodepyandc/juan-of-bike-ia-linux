// ---------------------------------------------------------------------------
// codeTsConfigPolicy — le tsconfig emis doit etre compatible avec sa stack.
//
// MESURE (run v130): 84 erreurs, 30 % du run, sur DEUX lignes de vite.config.ts
//
//   vite.config.ts(1,30): TS2307 Cannot find module 'vite'
//   vite.config.ts(2,19): TS2307 Cannot find module '@vitejs/plugin-react'
//
// Les deux paquets EXISTENT et etaient declares — verifie au registre npm:
// vite@8.2.1, @vitejs/plugin-react@6.0.5. Le defaut vivait dans le tsconfig:
// `"moduleResolution": "node"`, la resolution Node10, qui IGNORE le champ
// `exports` des paquets. Or c est le SEUL endroit ou vite@8 et plugin-react@6
// exposent leurs types. TypeScript se plaignait donc d un module absent alors
// qu il etait installe.
//
// Le modele n a rien invente: il a ecrit une valeur parfaitement legale, mais
// incompatible avec sa propre stack. Aucune passe de modele ne doit etre
// depensee pour cela.
// ---------------------------------------------------------------------------

const ESM_MODULES = ['esnext', 'es2022', 'preserve']
const NODE10 = ['node', 'node10', '']

export function repairGeneratedTsConfig(config: Record<string, unknown>) {
  const compilerOptions =
    config.compilerOptions && typeof config.compilerOptions === 'object' && !Array.isArray(config.compilerOptions)
      ? { ...(config.compilerOptions as Record<string, unknown>) }
      : {}

  compilerOptions.noUnusedLocals = false
  compilerOptions.noUnusedParameters = false

  if (NODE10.includes(String(compilerOptions.moduleResolution ?? '').toLowerCase())) {
    compilerOptions.moduleResolution = 'bundler'
    // `bundler` exige un module ESM, sinon TypeScript refuse la combinaison.
    if (!ESM_MODULES.includes(String(compilerOptions.module ?? '').toLowerCase())) {
      compilerOptions.module = 'ESNext'
    }
  }

  return { ...config, compilerOptions }
}
