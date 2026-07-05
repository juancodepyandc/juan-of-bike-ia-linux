/**
 * vite.smoke.config — build de validation sans copie de public/.
 *
 * `vite build` copie les ~2,8 Go de public/ dans dist/ AVANT d'écrire les
 * chunks ; sur disque presque plein le build échoue en ENOSPC alors que la
 * seule chose à valider est la transformation + l'émission des chunks
 * (notamment les dynamic imports — cf. feedback vite-lazy-treeshake).
 *
 * Usage : npx vite build -c vite.smoke.config.ts   (sortie : dist-smoke/)
 */
import { defineConfig, mergeConfig, type ConfigEnv, type UserConfig } from 'vite'
import baseFactory from './vite.config'

export default defineConfig(async (env: ConfigEnv) => {
  const base = await (baseFactory as unknown as (env: ConfigEnv) => Promise<UserConfig>)(env)
  return mergeConfig(base, {
    publicDir: false,
    build: { outDir: 'dist-smoke', emptyOutDir: true },
  })
})
