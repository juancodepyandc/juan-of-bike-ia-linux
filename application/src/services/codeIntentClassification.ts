// ---------------------------------------------------------------------------
// Main deterministic intent classification
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeIntent, CodeIntentContext, CodeProjectType } from './codeIntentTypes.ts'
import { tryResolveIncrementReuse } from './codeIntentIncrementReuse.ts'
import { looksLikeDesktopAppRequest, looksLikeMobileAppRequest } from './codeIntentPlatformHeuristics.ts'
import {
  API_SIGNALS,
  FRAMEWORK_SIGNALS,
  FULLSTACK_SIGNALS,
  GAME_SIGNALS,
  INTERACTIVE_WIDGET_SIGNALS,
  LANGUAGE_SIGNALS,
  MULTIPAGE_SIGNALS,
  THREED_APP_SIGNALS,
  WEB_SIGNALS,
} from './codeIntentSignals.ts'
import { matchSemanticProjectSignal } from './codeIntentSemanticSignals.ts'
import { containsAnySignal, containsSignal, normalizeSignalText } from './codeIntentSignalUtils.ts'
import { finalizeCodeIntentClassification } from './codeIntentFinalization.ts'

export function classifyCodeIntent(prompt: string, context?: CodeIntentContext): CodeIntent {
  const lower = normalizeSignalText(prompt)

  const incrementIntent = tryResolveIncrementReuse(prompt, lower, context)
  if (incrementIntent) {
    return incrementIntent
  }
  // pivot_platform / pivot_feature / fresh_start → fall through to full reclassification

  let projectType: CodeProjectType = 'unknown'
  const languages: string[] = []
  const frameworks: string[] = []
  const features: string[] = []

  const semanticSignal = matchSemanticProjectSignal(lower)
  if (semanticSignal) {
    projectType = semanticSignal.projectType
    languages.push(...semanticSignal.languages)
    frameworks.push(...semanticSignal.frameworks)
    features.push(...semanticSignal.features)
  }

  // Step 1: detect framework signals (highest priority).
  // v89b: "react native" is a SUPERSTRING of "react" and the object order lists
  // 'react' first, so "app React Native … Expo" used to match 'react' and be
  // misclassified as a React web SPA. Match the compound explicitly first.
  // (A blanket longest-keyword reorder is wrong here: it would let 'three.js'
  // beat 'react' for "React + Three.js" and lose the react-three-fiber path.)
  if (projectType === 'unknown' && /\breact[-\s]native\b/i.test(lower)) {
    projectType = 'mobile_rn'
    frameworks.push('react-native', 'expo')
    languages.push('typescript')
    features.push('mobile-native')
  } else if (projectType === 'unknown') {
    for (const [keyword, signal] of Object.entries(FRAMEWORK_SIGNALS)) {
      if (containsSignal(lower, keyword)) {
        projectType = signal.projectType
        frameworks.push(...signal.frameworks)
        languages.push(...signal.languages)
        break
      }
    }
  }

  // Step 2: fullstack override
  if (projectType !== 'unknown') {
    for (const signal of FULLSTACK_SIGNALS) {
      if (containsSignal(lower, signal)) {
        if (projectType === 'spa_react' || projectType === 'api_express') {
          projectType = 'fullstack_mern'
        } else if (projectType === 'ssr_nextjs') {
          projectType = 'fullstack_nextjs'
        } else if (projectType === 'api_django') {
          projectType = 'fullstack_django'
        }
        break
      }
    }
  }

  // v89b: compute the explicit-web signal BEFORE the mobile/desktop native
  // steps. A prompt that says "application web", "navigateur"/"browser",
  // "responsive", or "mobile/desktop" is WEB design and must NEVER be routed to
  // React Native (mobile_rn) or Tauri (desktop). Previously this lived at step
  // 6b — AFTER step 3a — so "dashboard responsive mobile/desktop, ouvrable dans
  // un navigateur" was hijacked into a React Native app because the bare word
  // "mobile" in MOBILE_SIGNALS short-circuited looksLikeMobileAppRequest().
  const userExplicitlyAskedWeb =
    containsAnySignal(lower, WEB_SIGNALS)
    || /\bpage\s*web\b|\bsite\s*(?:web|internet)\b|\blanding\s*page\b|\bwebapp\b|\bweb\s*app\b|\bapplication\s+web\b|\bappli(?:cation)?\s+web\b|\bapp\s+web\b/i.test(lower)
    || /\bnavigateur\b|\bbrowser\b/i.test(lower)
    || /\bresponsive\b/i.test(lower)
    || /\bmobile[\s/–—-]*(?:first|desktop)\b/i.test(lower)
    || /\bmobile\s+(?:et|ou|\/|,)\s*(?:desktop|ordinateur|pc)\b/i.test(lower)
    // v95: le garde v89b ne couvrait que la formulation TECHNIQUE ("site web",
    // "responsive", "navigateur"). Un vrai humain ecrit « je veux un vrai site »,
    // « une page d accueil », « on vend en ligne » — et son « doit marcher sur
    // mobile » (= responsive) suffisait alors a le router vers React Native.
    // Cas reel: brief d une torrefaction artisanale, livre en application mobile.
    // `sur site` est exclu: il signifie « sur place », pas « site web ».
    || (/\bsites?\b/i.test(lower) && !/\bsur\s+sites?\b/i.test(lower))
    || /\bpage\s+d['’ ]accueil\b/i.test(lower)
    || /\bnos?\s+pages?\b|\bune\s+page\b/i.test(lower)

  // v89b: an explicit single-page / no-build request must NOT be upgraded to a
  // React SPA (which needs a bundler and can't be "directement ouvrable dans un
  // navigateur"). A "dashboard"/"tableau de bord" is a MULTIPAGE_SIGNAL but is
  // almost always a single page — so "tableau de bord ... en une seule page,
  // directement ouvrable dans un navigateur" must stay static_web, not spa_react.
  const wantsSinglePageStatic =
    /\bune?\s+seule?\s+page\b|\bsingle[-\s]?page\b|\bone[-\s]?page\b|\bmono[-\s]?page\b|\bpage\s+unique\b/i.test(lower)
    || /\bdirectement\s+ouvrable\b|\bouvrable\s+dans\s+un\s+navigateur\b|\bsans\s+build\b|\bsans\s+bundler\b|\bun\s+seul\s+fichier\b|\bfichier\s+html\s+unique\b/i.test(lower)

  // Step 3a: mobile app detection (before generic desktop so an explicit
  // "app android" wins over a vague "application") — but skipped entirely when
  // the user explicitly asked for a web/browser page.
  if (projectType === 'unknown' && !userExplicitlyAskedWeb && looksLikeMobileAppRequest(lower)) {
    if (/\b(?:flutter|dart|apk\s*universel|universal\s*apk|apk)\b/i.test(lower)) {
      projectType = 'mobile_flutter'
      frameworks.push('flutter')
      languages.push('dart')
      features.push('mobile-flutter', 'apk-universal')
    } else if (/\b(?:kotlin|android|compose)\b/i.test(lower) && !/\breact[-\s]?native\b/i.test(lower)) {
      projectType = 'mobile_android'
      frameworks.push('jetpack-compose')
      languages.push('kotlin')
      features.push('mobile-android')
    } else if (/\b(?:swift|swiftui|ios|iphone|ipad)\b/i.test(lower) && !/\breact[-\s]?native\b/i.test(lower)) {
      projectType = 'mobile_ios'
      frameworks.push('swiftui')
      languages.push('swift')
      features.push('mobile-ios')
    } else {
      projectType = 'mobile_rn'
      frameworks.push('react-native', 'expo')
      languages.push('typescript')
      features.push('mobile-native')
    }
  }

  // Step 3b: desktop/native app detection — same web guard.
  if (projectType === 'unknown' && !userExplicitlyAskedWeb && looksLikeDesktopAppRequest(lower)) {
    if (/\b(?:python|py)\b/i.test(lower)) {
      projectType = 'desktop_app'
      frameworks.push('customtkinter')
      languages.push('python')
      features.push('desktop-python-gui')
    } else if (/\b(?:c\+\+|cpp|qt)\b/i.test(lower)) {
      projectType = 'desktop_app'
      frameworks.push('qt')
      languages.push('cpp')
      features.push('desktop-cpp-qt')
    } else if (/\b(?:go|golang|fyne)\b/i.test(lower)) {
      projectType = 'desktop_app'
      frameworks.push('fyne')
      languages.push('go')
      features.push('desktop-go-gui')
    } else if (/\b(?:c#|csharp|\.net|avalonia|wpf)\b/i.test(lower)) {
      projectType = 'desktop_app'
      frameworks.push('avalonia')
      languages.push('csharp')
      features.push('desktop-csharp-gui')
    } else {
      projectType = 'desktop_tauri'
      frameworks.push('tauri')
      languages.push('typescript', 'rust')
      features.push('desktop-native')
    }
  }

  // Step 3c (v89b): an EXPLICIT web request resolves to a web front-end here,
  // with authority over the generic language/API heuristics below (step 5/6).
  // Without this, a bare language mention ("en JavaScript pur") or a negated
  // backend ("sans backend") preempted the late step-6b web check and the page
  // was misclassified as cli_node / api_express. Multipage signals pick a React
  // SPA unless the user asked for a single self-contained page.
  if (projectType === 'unknown' && userExplicitlyAskedWeb) {
    if (!wantsSinglePageStatic && containsAnySignal(lower, MULTIPAGE_SIGNALS)) {
      projectType = 'spa_react'
      frameworks.push('react', 'react-router')
      languages.push('typescript')
      features.push('multipage')
    } else {
      projectType = 'static_web'
      languages.push('html', 'css', 'javascript')
    }
  }

  // Step 4: multipage web detection (upgrades static_web → SPA)
  if (!wantsSinglePageStatic && (projectType === 'unknown' || projectType === 'static_web')) {
    for (const signal of MULTIPAGE_SIGNALS) {
      if (containsSignal(lower, signal)) {
        // Default multi-page to React SPA if no framework specified
        if (projectType === 'unknown' || projectType === 'static_web') {
          projectType = 'spa_react'
          frameworks.push('react', 'react-router')
          languages.push('typescript')
        }
        features.push('multipage')
        break
      }
    }
  }

  // Step 5: detect language signals if no framework found
  if (projectType === 'unknown') {
    for (const [keyword, signal] of Object.entries(LANGUAGE_SIGNALS)) {
      if (containsSignal(lower, keyword)) {
        projectType = signal.projectType
        languages.push(...signal.languages)
        break
      }
    }
  }

  // v89b: a NEGATED backend mention ("sans backend", "no backend", "pas de
  // serveur", "front-end only", "100% front") is the OPPOSITE of an API request
  // — it must not match API_SIGNALS via the bare word "backend"/"serveur".
  const negatesBackend =
    /\b(sans|pas\s+de|aucun|no|without|zero)\s+(back-?end|serveur|server|api)\b/i.test(lower)
    || /\b(front-?end|client)[-\s]?(only|seul|uniquement|pur)\b/i.test(lower)
    || /\b100\s*%\s*front/i.test(lower)

  // Step 6: API detection upgrades CLI to API — skipped when the user explicitly
  // asked for a web front-end or explicitly said "no backend".
  if (
    !userExplicitlyAskedWeb && !negatesBackend
    && (projectType === 'cli_node' || projectType === 'cli_python' || projectType === 'unknown')
  ) {
    for (const signal of API_SIGNALS) {
      if (containsSignal(lower, signal)) {
        if (languages.includes('python') || containsSignal(lower, 'python')) {
          projectType = 'api_fastapi'
          frameworks.push('fastapi')
          if (!languages.includes('python')) languages.push('python')
        } else {
          projectType = 'api_express'
          frameworks.push('express')
          if (!languages.includes('typescript')) languages.push('typescript')
        }
        features.push('api')
        break
      }
    }
  }

  // Step 6b: web detection — `userExplicitlyAskedWeb` is computed before the
  // mobile/desktop native steps (see above), so an explicit web request can
  // never be hijacked into React Native / Tauri, and a bare "application"/"jeu"
  // with no web mention still falls through to the native defaults below.
  if (projectType === 'unknown' && userExplicitlyAskedWeb) {
    projectType = 'static_web'
    languages.push('html', 'css', 'javascript')
  }

  // Step 6c: game detection — native desktop app by default (Tauri shell),
  // web only if the user explicitly said "jeu web", "dans le navigateur",
  // "canvas"/"webgl"/"three.js", etc. Aligns with user rule: "quand je dis
  // 'jeu', tu penses a une APP pas a un site web".
  if (projectType === 'unknown') {
    for (const signal of GAME_SIGNALS) {
      if (containsSignal(lower, signal)) {
        const wantsWebCanvas =
          containsAnySignal(lower, WEB_SIGNALS)
          || /\bcanvas\b|\bwebgl\b|\bthree\.?js\b|\bphaser\b|\bpixi\b|\bnavigateur\b|\bbrowser\b/i.test(lower)
        if (wantsWebCanvas) {
          projectType = 'game_web'
          frameworks.push('canvas')
          languages.push('javascript')
          features.push('game')
        } else {
          projectType = 'desktop_tauri'
          frameworks.push('tauri', 'react')
          languages.push('typescript', 'rust')
          features.push('desktop-native', 'game')
        }
        break
      }
    }
  }

  // Step 6d: 3D app/scene detection — same rule: desktop app by default, web
  // only if explicit web signal.
  if (projectType === 'unknown') {
    for (const signal of THREED_APP_SIGNALS) {
      if (containsSignal(lower, signal)) {
        const wantsWebCanvas =
          containsAnySignal(lower, WEB_SIGNALS)
          || /\bthree\.?js\b|\bwebgl\b|\bwebgpu\b|\bnavigateur\b|\bbrowser\b/i.test(lower)
        if (wantsWebCanvas) {
          projectType = 'game_web'
          frameworks.push('three.js')
          languages.push('javascript')
          features.push('3d')
        } else {
          projectType = 'desktop_tauri'
          frameworks.push('tauri', 'react', 'three.js')
          languages.push('typescript', 'rust')
          features.push('desktop-native', '3d')
        }
        break
      }
    }
  }

  // Step 6e: Interactive widgets & graphical UI tools
  // (calculatrice, convertisseur, minuteur, soundboard, palette, horloge, etc.)
  if (projectType === 'unknown' || projectType === 'script' || projectType.startsWith('cli_')) {
    const hasWidgetSignal = containsAnySignal(lower, INTERACTIVE_WIDGET_SIGNALS)
      || /\bcalculatrice\b|\bcalculator\b|\bconvertisseur\b|\bminuteur\b|\bchronometre\b|\bchronomètre\b|\bgenerateur\b|\bwidget\b|\bsoundboard\b|\bpalette\b/i.test(lower)
    const hasVisualGraphicSignal = userExplicitlyAskedWeb
      || /\bgraphisme\b|\bgraphismes\b|\bdesign\b|\bvisuel\b|\bminecraft\b|\bpixel[\s-]?art\b|\b8[\s-]?bit\b|\binterface\b|\bui\b|\btheme\b|\bthème\b|\bgui\b/i.test(lower)

    if (hasWidgetSignal || (hasVisualGraphicSignal && !/\b(script|cli|terminal|command\s*line)\b/i.test(lower))) {
      // Détermination fine selon le langage et la plateforme demandée
      if (/\b(?:python|py)\b/i.test(lower)) {
        projectType = 'desktop_app'
        frameworks.push('customtkinter')
        if (!languages.includes('python')) languages.push('python')
        features.push('interactive-widget', 'desktop-python-gui')
      } else if (/\b(?:c\+\+|cpp|qt)\b/i.test(lower)) {
        projectType = 'desktop_app'
        frameworks.push('qt')
        if (!languages.includes('cpp')) languages.push('cpp')
        features.push('interactive-widget', 'desktop-cpp-qt')
      } else if (/\b(?:rust|slint)\b/i.test(lower)) {
        projectType = 'desktop_tauri'
        frameworks.push('tauri')
        if (!languages.includes('rust')) languages.push('rust')
        features.push('interactive-widget', 'desktop-rust-gui')
      } else if (/\b(?:go|golang|fyne)\b/i.test(lower)) {
        projectType = 'desktop_app'
        frameworks.push('fyne')
        if (!languages.includes('go')) languages.push('go')
        features.push('interactive-widget', 'desktop-go-gui')
      } else if (/\b(?:c#|csharp|\.net|avalonia|wpf)\b/i.test(lower)) {
        projectType = 'desktop_app'
        frameworks.push('avalonia')
        if (!languages.includes('csharp')) languages.push('csharp')
        features.push('interactive-widget', 'desktop-csharp-gui')
      } else if (/\b(?:apk|flutter|dart)\b/i.test(lower)) {
        projectType = 'mobile_flutter'
        frameworks.push('flutter')
        if (!languages.includes('dart')) languages.push('dart')
        features.push('interactive-widget', 'mobile-flutter', 'apk-universal')
      } else {
        projectType = 'static_web'
        if (!languages.includes('html')) languages.push('html', 'css', 'javascript')
        features.push('interactive-widget', 'visual-ui')
      }
    }
  }

  // Step 7: "application" / "app" / "logiciel" / "outil" / "programme"
  //         generique sans contexte → APP NATIVE DESKTOP par defaut (Tauri).
  //         L utilisateur a explicitement demande ce comportement : "de base
  //         ca doit etre des apps, pas du web".
  if (projectType === 'unknown') {
    const mentionsGenericApp =
      /\bapplication\b/i.test(lower)
      || /\blogiciel\b/i.test(lower)
      || /\bsoftware\b/i.test(lower)
      || /\boutil\b/i.test(lower)
      || /\bapp\b/i.test(lower)
      || /\bprogramme\b/i.test(lower)

    if (mentionsGenericApp) {
      if (userExplicitlyAskedWeb) {
        projectType = 'spa_react'
        frameworks.push('react')
        languages.push('typescript')
        features.push('generic-webapp')
      } else {
        projectType = 'desktop_tauri'
        frameworks.push('tauri', 'react')
        languages.push('typescript', 'rust')
        features.push('desktop-native', 'generic-app')
      }
    }
  }

  // Step 8: fallback to script if nothing matched (short CLI scripts only).
  if (projectType === 'unknown') {
    projectType = 'script'
    languages.push('typescript')
  }

  return finalizeCodeIntentClassification({
    prompt,
    normalizedPrompt: lower,
    projectType,
    languages,
    frameworks,
    features,
  })
}
