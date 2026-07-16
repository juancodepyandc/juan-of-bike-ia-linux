import type { DesignArchetype } from './codeDesignDirectives.ts'

export type ArchetypeKB = {
  inspirationSites: string[]
  searchAnchors: string[]
  paletteHints: string[]
  knownLibs: string[]
}

export const ARCHETYPE_KB: Record<DesignArchetype, ArchetypeKB> = {
  apple_product: {
    inspirationSites: [
      'apple.com/airpods-pro',
      'apple.com/iphone-15-pro',
      'nothing.tech/products/phone-2',
      'studio.design',
      'rauno.me',
    ],
    searchAnchors: [
      'apple product page exploded view scroll',
      'product anatomy hotspots web design',
      'product page scroll cinematic awwwards',
      'apple style scrollytelling product reveal',
    ],
    paletteHints: ['#fafafa', '#0a0a0b', '#86868b', '#0066cc'],
    knownLibs: ['three.js', 'gsap ScrollTrigger', 'lenis', 'split-type'],
  },
  narrative_landing: {
    inspirationSites: [
      'stripe.com',
      'linear.app',
      'vercel.com',
      'resend.com',
      'plain.com',
    ],
    searchAnchors: [
      'modern saas landing page 2025',
      'gradient mesh hero section design',
      'bento grid landing page',
      'awwwards landing page premium',
    ],
    paletteHints: ['#0d1117', '#7c3aed', '#3b82f6', '#22c55e'],
    knownLibs: ['gsap', 'ScrollTrigger', 'Lenis'],
  },
  dashboard_dataviz: {
    inspirationSites: [
      'linear.app',
      'vercel.com/dashboard',
      'plane.so',
      'cron.com',
      'arc.net',
    ],
    searchAnchors: [
      'modern admin dashboard ui design',
      'glassmorphism analytics dashboard',
      'bento grid dashboard layout',
      'dataviz dashboard inspiration 2025',
    ],
    paletteHints: ['#0e0e11', '#a78bfa', '#22d3ee', '#fbbf24'],
    knownLibs: ['Chart.js', 'D3', 'Lucide icons'],
  },
  portfolio_immersive: {
    inspirationSites: [
      'awwwards.com',
      'cssdesignawards.com',
      'siteInspire.com',
      'fwa.com',
      'tobiaswittwer.com',
    ],
    searchAnchors: [
      'awwwards portfolio webgl',
      'creative agency website award winning',
      'portfolio design 2025 immersive',
      'studio website webgl distortion',
    ],
    paletteHints: ['#000000', '#ffffff', '#ff0000'],
    knownLibs: ['three.js', 'GSAP', 'Lenis', 'OGL'],
  },
  ecommerce_premium: {
    inspirationSites: [
      'aimeleondore.com',
      'bose.com',
      'allbirds.com',
      'tracksmith.com',
      'patagonia.com',
    ],
    searchAnchors: [
      'premium ecommerce product page design',
      'editorial fashion store website',
      'product page galerie zoom interactive',
      'shopify premium theme design 2025',
    ],
    paletteHints: ['#fafafa', '#1a1a1a', '#c8a96a'],
    knownLibs: ['GSAP', 'Swiper', 'Lenis'],
  },
  saas_marketing: {
    inspirationSites: [
      'linear.app',
      'attio.com',
      'tella.tv',
      'cal.com',
      'cron.com',
    ],
    searchAnchors: [
      'modern saas pricing page design',
      'b2b product page premium 2025',
      'saas landing page bento grid features',
      'awwwards saas page',
    ],
    paletteHints: ['#0d0d0f', '#5b8def', '#22c55e'],
    knownLibs: ['gsap', 'lottie', 'rive'],
  },
  editorial_story: {
    inspirationSites: [
      'pudding.cool',
      'theverge.com/features',
      'nytimes.com',
      'bloomberg.com/graphics',
    ],
    searchAnchors: [
      'editorial long form scroll story',
      'pudding cool style article web',
      'newspaper interactive feature design',
      'editorial typography web 2025',
    ],
    paletteHints: ['#fafafa', '#1a1a1a', '#c0392b'],
    knownLibs: ['scrollama', 'd3', 'gsap'],
  },
  scroll_3d_journey: {
    inspirationSites: [
      'igloo.inc',
      'active.theory',
      'unseen.co',
      'lusion.co',
      'rauno.me',
    ],
    searchAnchors: [
      'pinned scroll three.js website',
      'webgl scroll cinematic experience',
      'awwwards three.js scroll story',
      'scroll triggered camera three.js',
    ],
    paletteHints: ['#000000', '#0a0a0b', '#ec4899'],
    knownLibs: ['three.js', 'GSAP ScrollTrigger', 'Lenis', 'EffectComposer'],
  },
  microsite_event: {
    inspirationSites: [
      'reactconf.com',
      'thefwa.com',
      'youfest.fr',
      'hackathon.com',
    ],
    searchAnchors: [
      'event microsite festival landing',
      'conference website design 2025',
      'festival lineup grid design',
      'concert event website inspiration',
    ],
    paletteHints: ['#0d0d1a', '#ec4899', '#fbbf24'],
    knownLibs: ['gsap', 'lenis'],
  },
  minimal_brutalist: {
    inspirationSites: [
      'brutalistwebsites.com',
      'bauhaus-movement.com',
      'isamtype.com',
    ],
    searchAnchors: [
      'brutalist web design 2025',
      'editorial swiss style website',
      'minimalist mono typography web',
    ],
    paletteHints: ['#000000', '#ffffff', '#ff0000'],
    knownLibs: ['none', 'css only'],
  },
  mobile_native_premium: {
    inspirationSites: [
      'mobbin.com',
      'apple.com/ios',
      'linear.app/mobile',
    ],
    searchAnchors: [
      'mobile app design ios premium 2025',
      'react native premium ui',
      'flutter premium design',
    ],
    paletteHints: ['#0d0d1a', '#7c3aed'],
    knownLibs: ['react-native-reanimated', 'gorhom bottom sheet'],
  },
  desktop_native_app: {
    inspirationSites: [
      'linear.app',
      'arc.net',
      'cron.com',
    ],
    searchAnchors: [
      'desktop app ui design modern 2025',
      'tauri electron premium design',
      'native app sidebar dashboard',
    ],
    paletteHints: ['#0d0d11', '#5b8def'],
    knownLibs: ['lucide', 'cmdk'],
  },
  game_visual_premium: {
    inspirationSites: [
      'js13kgames.com',
      'arcade.makecode.com',
    ],
    searchAnchors: [
      'canvas game juicy effects',
      'web game neon visuals',
      'browser game particles screen shake',
    ],
    paletteHints: ['#0a0a0b', '#ec4899', '#22d3ee'],
    knownLibs: ['none — vanilla canvas + Web Audio'],
  },
  data_dense_enterprise: {
    inspirationSites: [
      'linear.app',
      'retable.io',
      'airtable.com',
      'attio.com',
      'grafana.com',
    ],
    searchAnchors: [
      'data dense enterprise table UI design',
      'admin data grid dashboard UX',
      'operations backoffice dense interface',
      'enterprise app table filters drawer design',
    ],
    paletteHints: ['#0f172a', '#2563eb', '#14b8a6', '#f8fafc'],
    knownLibs: ['TanStack Table', 'D3', 'Chart.js', 'Lucide icons'],
  },
  ide_code_editor: {
    inspirationSites: [
      'code.visualstudio.com',
      'zed.dev',
      'cursor.com',
      'replit.com',
      'stackblitz.com',
    ],
    searchAnchors: [
      'modern IDE UI file tree editor terminal',
      'code editor interface design command palette',
      'developer tool dark UI workspace',
      'terminal panel status bar IDE UX',
    ],
    paletteHints: ['#0d1117', '#1f6feb', '#2ea043', '#f0f6fc'],
    knownLibs: ['CodeMirror 6', 'Monaco editor', 'xterm.js', 'cmdk'],
  },
  os_shell: {
    inspirationSites: [
      'gnome.org',
      'kde.org',
      'wezfurlong.org/wezterm',
      'warp.dev',
      'system76.com/pop',
    ],
    searchAnchors: [
      'operating system shell UI boot console design',
      'terminal dashboard process monitor UI',
      'kernel boot log interface typography',
      'system monitor console design',
    ],
    paletteHints: ['#020617', '#22c55e', '#38bdf8', '#e2e8f0'],
    knownLibs: ['xterm.js', 'Canvas 2D', 'WebGL terminal effects'],
  },
  default_premium: {
    inspirationSites: [
      'awwwards.com',
      'godly.website',
      'siteInspire.com',
    ],
    searchAnchors: [
      'modern web design 2025 premium',
      'awwwards site of the day',
      'godly best modern web designs',
    ],
    paletteHints: ['#0d0d11', '#7c3aed'],
    knownLibs: ['gsap', 'lenis'],
  },
}
