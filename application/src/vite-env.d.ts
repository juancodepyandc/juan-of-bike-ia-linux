/// <reference types="vite/client" />

declare module '*.css' {}

// v82j4 : globals injected at build time via vite.config.ts define.
declare const __AURORA_COMMIT__: string
declare const __AURORA_BRANCH__: string
declare const __AURORA_BUILD_TS__: string
