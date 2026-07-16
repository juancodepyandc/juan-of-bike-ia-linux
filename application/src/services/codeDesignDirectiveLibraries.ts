import {
  CODE_THREE_ADDONS_BASE,
  CODE_THREE_CDN_BASE,
} from './codeRuntimeDependencies.ts'

export const CODE_DESIGN_CDN_LIBS = {
  three: `${CODE_THREE_CDN_BASE}/build/three.module.js`,
  threeOrbit: `${CODE_THREE_ADDONS_BASE}/controls/OrbitControls.js`,
  threeGLTF: `${CODE_THREE_ADDONS_BASE}/loaders/GLTFLoader.js`,
  threePostproc: `${CODE_THREE_ADDONS_BASE}/postprocessing/EffectComposer.js`,
  gsap: 'https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js',
  scrollTrigger: 'https://cdn.jsdelivr.net/npm/gsap@3/dist/ScrollTrigger.min.js',
  lenis: 'https://cdn.jsdelivr.net/npm/lenis@1/dist/lenis.min.js',
  lottie: 'https://cdn.jsdelivr.net/npm/lottie-web@5/build/player/lottie.min.js',
  splitText: 'https://cdn.jsdelivr.net/npm/split-type@0.3/umd/index.min.js',
  d3: 'https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js',
  chartjs: 'https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js',
  motionone: 'https://cdn.jsdelivr.net/npm/motion@12/dist/motion.min.js',
} as const
