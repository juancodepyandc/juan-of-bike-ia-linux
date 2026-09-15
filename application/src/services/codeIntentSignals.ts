// ---------------------------------------------------------------------------
// Code intent keyword tables
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeProjectType } from './codeIntentTypes.ts'

export const FRAMEWORK_SIGNALS: Record<string, { projectType: CodeProjectType; frameworks: string[]; languages: string[] }> = {
  // Frontend SPA
  'react': { projectType: 'spa_react', frameworks: ['react'], languages: ['typescript', 'javascript'] },
  'vue': { projectType: 'spa_vue', frameworks: ['vue'], languages: ['typescript', 'javascript'] },
  'angular': { projectType: 'spa_angular', frameworks: ['angular'], languages: ['typescript'] },
  'svelte': { projectType: 'spa_svelte', frameworks: ['svelte'], languages: ['typescript', 'javascript'] },
  'sveltekit': { projectType: 'spa_svelte', frameworks: ['sveltekit'], languages: ['typescript'] },
  // SSR/Fullstack
  'next': { projectType: 'ssr_nextjs', frameworks: ['nextjs'], languages: ['typescript'] },
  'next.js': { projectType: 'ssr_nextjs', frameworks: ['nextjs'], languages: ['typescript'] },
  'nextjs': { projectType: 'ssr_nextjs', frameworks: ['nextjs'], languages: ['typescript'] },
  'nuxt': { projectType: 'ssr_nuxt', frameworks: ['nuxt'], languages: ['typescript'] },
  'remix': { projectType: 'ssr_remix', frameworks: ['remix'], languages: ['typescript'] },
  // Backend API
  'express': { projectType: 'api_express', frameworks: ['express'], languages: ['typescript', 'javascript'] },
  'fastapi': { projectType: 'api_fastapi', frameworks: ['fastapi'], languages: ['python'] },
  'django': { projectType: 'api_django', frameworks: ['django'], languages: ['python'] },
  'flask': { projectType: 'api_flask', frameworks: ['flask'], languages: ['python'] },
  'spring': { projectType: 'api_spring', frameworks: ['spring-boot'], languages: ['java'] },
  'spring boot': { projectType: 'api_spring', frameworks: ['spring-boot'], languages: ['java'] },
  'gin': { projectType: 'api_gin', frameworks: ['gin'], languages: ['go'] },
  'actix': { projectType: 'api_actix', frameworks: ['actix-web'], languages: ['rust'] },
  'rails': { projectType: 'fullstack_rails', frameworks: ['rails'], languages: ['ruby'] },
  'ruby on rails': { projectType: 'fullstack_rails', frameworks: ['rails'], languages: ['ruby'] },
  '.net': { projectType: 'api_dotnet', frameworks: ['.net'], languages: ['csharp'] },
  'asp.net': { projectType: 'api_dotnet', frameworks: ['asp.net'], languages: ['csharp'] },
  // Mobile & Cross-platform APK
  'react native': { projectType: 'mobile_rn', frameworks: ['react-native'], languages: ['typescript'] },
  'expo': { projectType: 'mobile_rn', frameworks: ['expo', 'react-native'], languages: ['typescript'] },
  'flutter': { projectType: 'mobile_flutter', frameworks: ['flutter'], languages: ['dart'] },
  'flet': { projectType: 'mobile_flutter', frameworks: ['flet'], languages: ['python'] },
  'kivy': { projectType: 'mobile_android', frameworks: ['kivy'], languages: ['python'] },
  'compose multiplatform': { projectType: 'mobile_android', frameworks: ['compose-multiplatform'], languages: ['kotlin'] },
  'jetpack compose': { projectType: 'mobile_android', frameworks: ['jetpack-compose'], languages: ['kotlin'] },
  'swiftui': { projectType: 'mobile_ios', frameworks: ['swiftui'], languages: ['swift'] },
  'capacitor': { projectType: 'mobile_rn', frameworks: ['capacitor'], languages: ['typescript', 'javascript'] },
  'maui': { projectType: 'mobile_rn', frameworks: ['maui'], languages: ['csharp'] },
  // Desktop & Native GUI
  'electron': { projectType: 'desktop_electron', frameworks: ['electron'], languages: ['typescript'] },
  'tauri': { projectType: 'desktop_tauri', frameworks: ['tauri'], languages: ['typescript', 'rust'] },
  'customtkinter': { projectType: 'desktop_app', frameworks: ['customtkinter'], languages: ['python'] },
  'tkinter': { projectType: 'desktop_app', frameworks: ['tkinter'], languages: ['python'] },
  'pyqt': { projectType: 'desktop_app', frameworks: ['pyqt'], languages: ['python'] },
  'pyqt5': { projectType: 'desktop_app', frameworks: ['pyqt5'], languages: ['python'] },
  'pyqt6': { projectType: 'desktop_app', frameworks: ['pyqt6'], languages: ['python'] },
  'pyside': { projectType: 'desktop_app', frameworks: ['pyside'], languages: ['python'] },
  'pyside6': { projectType: 'desktop_app', frameworks: ['pyside6'], languages: ['python'] },
  'slint': { projectType: 'desktop_tauri', frameworks: ['slint'], languages: ['rust'] },
  'iced': { projectType: 'desktop_app', frameworks: ['iced'], languages: ['rust'] },
  'egui': { projectType: 'desktop_app', frameworks: ['egui'], languages: ['rust'] },
  'qt': { projectType: 'desktop_app', frameworks: ['qt'], languages: ['cpp'] },
  'fyne': { projectType: 'desktop_app', frameworks: ['fyne'], languages: ['go'] },
  'wails': { projectType: 'desktop_app', frameworks: ['wails'], languages: ['go', 'typescript'] },
  'avalonia': { projectType: 'desktop_app', frameworks: ['avalonia'], languages: ['csharp'] },
  'wpf': { projectType: 'desktop_app', frameworks: ['wpf'], languages: ['csharp'] },
  // Data/ML
  'pandas': { projectType: 'data_python', frameworks: ['pandas'], languages: ['python'] },
  'numpy': { projectType: 'data_python', frameworks: ['numpy'], languages: ['python'] },
  'tensorflow': { projectType: 'data_python', frameworks: ['tensorflow'], languages: ['python'] },
  'pytorch': { projectType: 'data_python', frameworks: ['pytorch'], languages: ['python'] },
  'scikit': { projectType: 'data_python', frameworks: ['scikit-learn'], languages: ['python'] },
  'jupyter': { projectType: 'data_python', frameworks: ['jupyter'], languages: ['python'] },
  // Game
  'canvas': { projectType: 'game_web', frameworks: ['canvas'], languages: ['javascript'] },
  'webgl': { projectType: 'game_web', frameworks: ['webgl'], languages: ['javascript'] },
  'three.js': { projectType: 'game_web', frameworks: ['three.js'], languages: ['javascript'] },
  'phaser': { projectType: 'game_web', frameworks: ['phaser'], languages: ['javascript'] },
  'pixi': { projectType: 'game_web', frameworks: ['pixijs'], languages: ['javascript'] },
  'unity': { projectType: 'game_unity', frameworks: ['unity'], languages: ['csharp'] },
  // DevOps
  'docker': { projectType: 'devops_docker', frameworks: ['docker'], languages: ['yaml'] },
  'kubernetes': { projectType: 'devops_docker', frameworks: ['kubernetes'], languages: ['yaml'] },
}

export const LANGUAGE_SIGNALS: Record<string, { projectType: CodeProjectType; languages: string[] }> = {
  'python': { projectType: 'cli_python', languages: ['python'] },
  'rust': { projectType: 'system_rust', languages: ['rust'] },
  'cargo': { projectType: 'system_rust', languages: ['rust'] },
  'go': { projectType: 'cli_go', languages: ['go'] },
  'golang': { projectType: 'cli_go', languages: ['go'] },
  'java': { projectType: 'api_spring', languages: ['java'] },
  'kotlin': { projectType: 'api_spring', languages: ['kotlin'] },
  'c++': { projectType: 'system_cpp', languages: ['cpp'] },
  'cpp': { projectType: 'system_cpp', languages: ['cpp'] },
  'c language': { projectType: 'system_c', languages: ['c'] },
  'typescript': { projectType: 'cli_node', languages: ['typescript'] },
  'javascript': { projectType: 'cli_node', languages: ['javascript'] },
  'node': { projectType: 'cli_node', languages: ['javascript'] },
  'nodejs': { projectType: 'cli_node', languages: ['javascript'] },
  'bash': { projectType: 'script', languages: ['bash'] },
  'shell': { projectType: 'script', languages: ['bash'] },
  'powershell': { projectType: 'script', languages: ['powershell'] },
  'sql': { projectType: 'script', languages: ['sql'] },
  'php': { projectType: 'script', languages: ['php'] },
  'ruby': { projectType: 'script', languages: ['ruby'] },
  'dart': { projectType: 'cli_node', languages: ['dart'] },
  'swift': { projectType: 'script', languages: ['swift'] },
  'zig': { projectType: 'system_c', languages: ['zig'] },
  'lua': { projectType: 'script', languages: ['lua'] },
  'r': { projectType: 'data_python', languages: ['r'] },
  'scala': { projectType: 'cli_node', languages: ['scala'] },
  'elixir': { projectType: 'script', languages: ['elixir'] },
  'haskell': { projectType: 'script', languages: ['haskell'] },
}

export const FULLSTACK_SIGNALS = new Set([
  'fullstack', 'full-stack', 'full stack',
  'mern', 'mean', 'pern', 'lamp',
  'frontend et backend', 'front et back',
  'front-end et back-end',
])

export const WEB_SIGNALS = new Set([
  'site web', 'website', 'page web', 'webpage',
  'landing page', 'portfolio', 'blog',
  'html', 'css', 'web page',
  'site internet', 'page internet',
])

export const MOBILE_SIGNALS = new Set([
  'mobile', 'android', 'ios', 'iphone', 'ipad', 'smartphone',
  'apk', 'apk universel', 'universal apk', 'appli mobile', 'application mobile',
  'mobile app', 'cross platform mobile', 'cross-platform mobile',
  'react native', 'flutter', 'flet', 'kivy', 'compose multiplatform', 'capacitor',
])

export const DESKTOP_SIGNALS = new Set([
  'application de bureau', 'app de bureau', 'desktop app', 'application desktop',
  'application windows', 'app windows', 'windows app', 'application pc', 'app pc',
  'application mac', 'app mac', 'application linux', 'app linux',
  'native app', 'application native', 'client lourd', 'logiciel',
  'offline app', 'application locale', 'local app', 'programme bureau',
  'interface graphique', 'application graphique', 'gui',
  'tauri', 'electron', 'winui', 'win32', 'gtk', 'qt', 'tkinter', 'customtkinter', 'pyqt', 'pyside', 'fyne', 'wails', 'avalonia', 'wpf', 'slint',
])

export const API_SIGNALS = new Set([
  'api', 'rest', 'restful', 'graphql',
  'crud', 'endpoint', 'microservice',
  'backend', 'back-end', 'serveur',
  'jwt', 'auth', 'authentication',
  'websocket', 'grpc',
])

export const MULTIPAGE_SIGNALS = new Set([
  'multipage', 'multi-page', 'multi page',
  'dashboard', 'admin', 'e-commerce', 'ecommerce',
  'plateforme', 'platform', 'portail', 'portal',
  'application web', 'web app', 'webapp',
  'saas', 'crm', 'erp', 'cms',
  'routing', 'router', 'navigation',
  'pages', 'tableau de bord',
])

export const INTERACTIVE_WIDGET_SIGNALS = new Set([
  'calculatrice', 'calculateur', 'calculator',
  'convertisseur', 'converter',
  'minuteur', 'timer', 'chronometre', 'chronomètre', 'stopwatch',
  'generateur', 'générateur', 'generator',
  'synthetiseur', 'synthétiseur', 'synthesizer', 'synth',
  'drum machine', 'boite a rythme', 'boîte à rythme',
  'visualiseur', 'visualizer',
  'lecteur audio', 'audio player', 'music player',
  'soundboard', 'table d harmonie',
  'palette de couleur', 'color picker',
  'horloge', 'clock', 'world clock',
  'compteur', 'counter',
  'tableau blanc', 'whiteboard',
])

// ---------------------------------------------------------------------------
// Game detection signals (FR + EN) — triggers game_web project type
// ---------------------------------------------------------------------------
export const GAME_SIGNALS = new Set([
  // FR — generic
  'jeu', 'jeux', 'jeu video', 'jeu vidéo', 'mini jeu', 'mini-jeu',
  'jeu de tir', 'jeu de plateforme', 'jeu de course', 'jeu de strategie',
  'jeu de cartes', 'jeu de des', 'jeu de role', 'jeu de puzzle',
  'jeu d aventure', 'jeu d action', 'jeu de reflexion',
  'jeu 2d', 'jeu 3d', 'jeu canvas', 'jeu browser', 'jeu navigateur',
  'jouable', 'gameplay', 'score', 'vie', 'vies', 'niveau', 'niveaux',
  'ennemi', 'ennemis', 'projectile', 'sprite', 'collision',
  'platformer', 'shooter', 'infinite runner', 'endless runner',
  'flappy', 'snake', 'tetris', 'pong', 'breakout', 'asteroids', 'pac',
  'tower defense', 'match 3', 'match-3',
  // EN — generic
  'game', 'games', 'video game', 'mini game', 'mini-game', 'browser game',
  'game loop', 'game engine', 'playable', 'player', 'enemies', 'enemy',
  'health bar', 'game over', 'high score', 'leaderboard',
  '2d game', '3d game', 'canvas game', 'arcade', 'pixel art game',
])

// ---------------------------------------------------------------------------
// 3D app / scene signals (FR + EN) — triggers game_web when no other type found
// ---------------------------------------------------------------------------
export const THREED_APP_SIGNALS = new Set([
  // FR
  'application 3d', 'app 3d', 'scene 3d', 'scène 3d', 'visualisation 3d',
  'modele 3d', 'viewer 3d', 'visionneuse 3d', 'objet 3d',
  'animation 3d', 'rendu 3d', 'environnement 3d', 'monde 3d',
  'rotation 3d', 'orbit', 'camera 3d',
  // EN
  '3d app', '3d application', '3d scene', '3d model viewer', '3d viewer',
  '3d visualization', '3d environment', '3d world', '3d animation',
  'three.js', 'threejs', 'webgl', 'webgpu', 'glb', 'gltf', 'obj model',
  'orbit controls', 'perspective camera', 'point light', 'ambient light',
])

// ---------------------------------------------------------------------------
// Known game dictionary — maps detection tokens → exact mechanics spec
// ---------------------------------------------------------------------------
