/**
 * codeDesignReference — pre-fab premium HTML starter that gets injected into
 * the codeur prompt as an EXAMPLE the LLM can study (not copy verbatim).
 *
 * Why: telling the LLM "fais un design pousse" yields scolaire output most
 * of the time. Showing it a concrete reference of what "pousse" means —
 * with real design tokens, real gradients, real micro-interactions — makes
 * it match the level. This is the same trick used by GPT-Engineer and v0.
 *
 * The reference is opinionated:
 * - Inter font from Google Fonts with preconnect
 * - Full CSS variables (color, space, radius, shadow, ease, duration)
 * - Mesh gradient hero with 3 animated blobs
 * - Glassmorphism nav + cards
 * - Scroll reveal via IntersectionObserver
 * - Magnetic hover on buttons
 * - Counter animation
 * - Marquee carousel
 * - Dark/light mode toggle with prefers-color-scheme detection
 *
 * The LLM is told: "Voici le NIVEAU de design attendu. Reprends les
 * patterns (variables, animations, structure) et adapte-les au sujet.
 * Ne livre PAS un site qui ressemble plus simple que ca."
 */

// v82m7 — PREMIUM_HTML_REFERENCE eleve au niveau ingenieur senior
// (Linear / Vercel / Arc / Stripe / Anthropic). Ancien starter etait scolaire:
// Inter par defaut, gradient violet→cyan→ambre Bootstrap-ish, accent vibrant
// + secondaire + tertiaire qui se battent. Cette version: oklch palette
// restreinte (1 accent), Inter Variable + Instrument Serif italic display,
// JetBrains Mono kicker, motion tokens (--ease-out-expo / --ease-spring),
// grille 12-col, container queries, view-transition-name, animation-timeline:
// view() pour scroll-driven natif, hover scale 1.02 max, magnetic spring.
export const PREMIUM_HTML_REFERENCE = String.raw`<!DOCTYPE html>
<html lang="fr" data-theme="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{{TITLE}}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    :root {
      /* Palette oklch — UN seul accent. Neutres warm-tinted slate. */
      --bg: oklch(0.13 0.012 252);          /* deep neutral, jamais #000 */
      --surface: oklch(0.16 0.014 252);
      --surface-elevated: oklch(0.19 0.016 252);
      --border: oklch(0.30 0.018 252 / 0.18);
      --border-strong: oklch(0.42 0.020 252 / 0.32);
      --fg: oklch(0.97 0.005 252);
      --fg-dim: oklch(0.97 0.005 252 / 0.62);
      --fg-faint: oklch(0.97 0.005 252 / 0.38);
      --accent: oklch(0.72 0.18 286);        /* electric violet, 1 accent */
      --accent-soft: oklch(0.72 0.18 286 / 0.14);

      --radius-1: 6px;
      --radius-2: 10px;
      --radius-3: 14px;
      --radius-4: 20px;
      --radius-pill: 999px;

      /* Spacing tokens — 4-base modular */
      --s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px; --s-5: 20px;
      --s-6: 24px; --s-8: 32px; --s-10: 40px; --s-12: 48px; --s-16: 64px;
      --s-20: 80px; --s-24: 96px; --s-32: 128px;

      /* Shadows — composites a 2-3 couches, jamais du flat */
      --sh-1: 0 1px 2px oklch(0 0 0 / 0.18);
      --sh-2: 0 1px 2px oklch(0 0 0 / 0.16), 0 8px 24px -4px oklch(0 0 0 / 0.18), inset 0 1px 0 oklch(1 0 0 / 0.04);
      --sh-3: 0 2px 4px oklch(0 0 0 / 0.16), 0 16px 32px -8px oklch(0 0 0 / 0.22), 0 32px 64px -24px oklch(0 0 0 / 0.28), inset 0 1px 0 oklch(1 0 0 / 0.06);
      --sh-glow: 0 0 0 1px oklch(0.72 0.18 286 / 0.12), 0 12px 36px -8px oklch(0.72 0.18 286 / 0.42);

      /* Easing tokens — vocabulaire senior */
      --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
      --ease-spring: cubic-bezier(0.32, 0.72, 0, 1);
      --ease-smooth: cubic-bezier(0.4, 0, 0.2, 1);
      --d-fast: 160ms;
      --d-base: 240ms;
      --d-slow: 480ms;

      --container: 1280px;
      --gutter: clamp(20px, 4vw, 56px);
    }
    [data-theme="light"] {
      --bg: oklch(0.985 0.005 80);
      --surface: oklch(1 0 0);
      --surface-elevated: oklch(0.98 0.006 80);
      --border: oklch(0.30 0.018 252 / 0.10);
      --border-strong: oklch(0.30 0.018 252 / 0.20);
      --fg: oklch(0.18 0.012 252);
      --fg-dim: oklch(0.18 0.012 252 / 0.62);
      --fg-faint: oklch(0.18 0.012 252 / 0.38);
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; }
    body {
      font: 400 15px/1.6 "Inter", "Inter Variable", system-ui, -apple-system, sans-serif;
      font-feature-settings: "ss01", "cv11";
      background: var(--bg);
      color: var(--fg);
      letter-spacing: -0.005em;
      overflow-x: hidden;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }
    .mono { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--fg-faint); }
    .display { font-family: "Instrument Serif", "Times New Roman", serif; font-style: italic; letter-spacing: -0.02em; line-height: 0.95; }
    .grid-12 { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: clamp(16px, 1.4vw, 24px); }
    @container (max-width: 720px) { .grid-12 { grid-template-columns: repeat(6, minmax(0, 1fr)); } }
    .container { width: 100%; max-width: var(--container); margin-inline: auto; padding-inline: var(--gutter); }
    /* Buttons — padding asymmetrique, hover scale 1.02 max, magnetic spring */
    .btn { display: inline-flex; align-items: center; gap: var(--s-2); padding: 10px 18px; border-radius: var(--radius-pill); font: 500 13px/1 "Inter", system-ui, sans-serif; letter-spacing: -0.005em; cursor: pointer; border: 1px solid transparent; transition: transform var(--d-base) var(--ease-spring), box-shadow var(--d-base) var(--ease-out-expo), background var(--d-fast) var(--ease-out-expo), border-color var(--d-fast) var(--ease-out-expo); will-change: transform; }
    .btn-primary { background: var(--fg); color: var(--bg); box-shadow: var(--sh-2); }
    .btn-primary:hover { transform: translateY(-1px) scale(1.02); box-shadow: var(--sh-3); }
    .btn-ghost { background: transparent; color: var(--fg); border-color: var(--border-strong); backdrop-filter: blur(8px); }
    .btn-ghost:hover { background: oklch(1 0 0 / 0.03); border-color: var(--border-strong); transform: translateY(-1px); }
    .btn-accent { background: var(--accent); color: oklch(0.13 0.012 252); box-shadow: var(--sh-glow); }
    .btn-accent:hover { transform: translateY(-1px) scale(1.02); }
    .btn .arrow { transition: transform var(--d-base) var(--ease-spring); }
    .btn:hover .arrow { transform: translateX(3px); }

    /* Nav — glass mesure, inset 1px white signature Apple/Linear */
    nav.top { position: fixed; inset: 0 0 auto 0; z-index: 50; padding: 14px 0; transition: padding var(--d-base) var(--ease-out-expo), background var(--d-base) var(--ease-out-expo), border-color var(--d-base) var(--ease-out-expo); border-bottom: 1px solid transparent; }
    nav.top.scrolled { padding: 10px 0; background: oklch(from var(--bg) l c h / 0.72); backdrop-filter: blur(20px) saturate(180%); -webkit-backdrop-filter: blur(20px) saturate(180%); border-bottom-color: var(--border); box-shadow: inset 0 1px 0 oklch(1 0 0 / 0.06); }
    nav.top .row { display: flex; align-items: center; justify-content: space-between; gap: var(--s-6); }
    nav.top .brand { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; font-size: 15px; letter-spacing: -0.015em; }
    nav.top .brand-mark { width: 22px; height: 22px; border-radius: 6px; background: linear-gradient(135deg, var(--accent), oklch(0.55 0.16 286)); box-shadow: var(--sh-glow); }
    nav.top ul { display: flex; gap: var(--s-6); list-style: none; }
    nav.top ul a { color: var(--fg-dim); text-decoration: none; font-size: 13px; transition: color var(--d-fast) var(--ease-out-expo); }
    nav.top ul a:hover { color: var(--fg); }

    /* Hero — grille 12-col, display italic serif, mesh gradient en arriere-plan */
    section.hero { position: relative; min-height: 100vh; display: flex; align-items: center; padding: 140px 0 96px; overflow: hidden; container-type: inline-size; }
    .hero-bg { position: absolute; inset: 0; pointer-events: none; z-index: 0; }
    .hero-bg .blob { position: absolute; border-radius: 50%; filter: blur(140px); will-change: transform; }
    .hero-bg .blob.a { width: 56vw; height: 56vw; max-width: 700px; max-height: 700px; background: oklch(0.72 0.18 286 / 0.42); top: -8%; left: -10%; animation: drift-a 24s var(--ease-smooth) infinite alternate; }
    .hero-bg .blob.b { width: 48vw; height: 48vw; max-width: 560px; max-height: 560px; background: oklch(0.62 0.14 240 / 0.32); bottom: -16%; right: -12%; animation: drift-b 32s var(--ease-smooth) infinite alternate; }
    @keyframes drift-a { to { transform: translate3d(80px, 60px, 0) scale(1.1); } }
    @keyframes drift-b { to { transform: translate3d(-60px, -40px, 0) scale(1.08); } }
    .hero-grain { position: absolute; inset: 0; pointer-events: none; opacity: 0.035; mix-blend-mode: overlay; background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><filter id='n'><feTurbulence baseFrequency='1.6' numOctaves='2' seed='3'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>"); z-index: 1; }
    .hero .container { position: relative; z-index: 2; }
    .hero-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: clamp(16px, 1.4vw, 24px); align-items: center; }
    .hero .copy { grid-column: 1 / span 12; display: grid; gap: 24px; }
    @container (min-width: 880px) { .hero .copy { grid-column: 1 / span 7; } .hero .visual { grid-column: 8 / span 5; } }
    @media (min-width: 880px) { .hero .copy { grid-column: 1 / span 7; } .hero .visual { grid-column: 8 / span 5; } }
    .hero .kicker { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 999px; background: oklch(1 0 0 / 0.04); border: 1px solid var(--border); font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--fg-dim); width: fit-content; }
    .hero .kicker .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 4px oklch(0.72 0.18 286 / 0.18); }
    .hero h1 { font-size: clamp(48px, 8.4vw, 96px); font-weight: 600; line-height: 0.96; letter-spacing: -0.04em; max-width: 14ch; }
    .hero h1 .em { font-family: "Instrument Serif", "Times New Roman", serif; font-style: italic; font-weight: 400; letter-spacing: -0.02em; color: var(--fg); position: relative; padding-inline: 0.05em; }
    .hero h1 .em::before { content: ""; position: absolute; inset: 0.18em -0.05em 0.05em; background: var(--accent-soft); border-radius: 6px; z-index: -1; transform: skewX(-3deg); }
    .hero p.lead { color: var(--fg-dim); font-size: clamp(15px, 1.2vw, 18px); line-height: 1.55; max-width: 52ch; }
    .hero .ctas { display: flex; gap: 12px; flex-wrap: wrap; }
    .hero .meta { display: flex; gap: 24px; flex-wrap: wrap; padding-top: 20px; border-top: 1px solid var(--border); margin-top: 12px; }
    .hero .meta .pair { display: grid; gap: 4px; }
    .hero .meta .pair .v { font-family: "Instrument Serif", serif; font-style: italic; font-size: 22px; line-height: 1; color: var(--fg); }
    .hero .meta .pair .l { font-family: "JetBrains Mono", monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--fg-faint); }
    .hero .visual { aspect-ratio: 1; max-width: 480px; justify-self: end; position: relative; }
    .hero .visual .frame { position: absolute; inset: 0; border-radius: 24px; overflow: hidden; border: 1px solid var(--border-strong); background: var(--surface); box-shadow: var(--sh-3); }
    .hero .visual .frame::after { content: ""; position: absolute; inset: 0; background: radial-gradient(circle at 30% 20%, oklch(1 0 0 / 0.08), transparent 60%); pointer-events: none; }
    .hero .visual img { width: 100%; height: 100%; object-fit: cover; }

    /* Section base */
    section { padding-block: clamp(80px, 12vw, 160px); position: relative; }
    .section-head { display: grid; gap: 16px; max-width: 720px; margin-bottom: clamp(48px, 6vw, 80px); }
    .section-head .kicker { font-family: "JetBrains Mono", monospace; font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent); display: inline-flex; align-items: center; gap: 8px; }
    .section-head .kicker::before { content: ""; width: 18px; height: 1px; background: var(--accent); }
    .section-head h2 { font-size: clamp(32px, 4.4vw, 56px); font-weight: 500; line-height: 1.05; letter-spacing: -0.03em; max-width: 22ch; }
    .section-head h2 .em { font-family: "Instrument Serif", serif; font-style: italic; font-weight: 400; }
    .section-head p { color: var(--fg-dim); font-size: 16px; line-height: 1.55; max-width: 60ch; }

    /* Features — mosaique inegale 12-col, pas une grille uniforme */
    .features-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: clamp(12px, 1.2vw, 20px); }
    .feature { padding: clamp(24px, 2.4vw, 36px); background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-4); position: relative; overflow: hidden; transition: transform var(--d-base) var(--ease-out-expo), border-color var(--d-fast) var(--ease-out-expo), background var(--d-fast) var(--ease-out-expo); }
    .feature::before { content: ""; position: absolute; inset: 0; background: radial-gradient(circle at var(--mx, 50%) var(--my, 50%), oklch(1 0 0 / 0.04), transparent 50%); opacity: 0; transition: opacity var(--d-base) var(--ease-out-expo); pointer-events: none; }
    .feature:hover { transform: translateY(-2px); border-color: var(--border-strong); background: var(--surface-elevated); }
    .feature:hover::before { opacity: 1; }
    .feature .ico { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 10px; background: oklch(1 0 0 / 0.04); border: 1px solid var(--border); color: var(--fg); margin-bottom: 20px; }
    .feature h3 { font-size: 18px; font-weight: 500; letter-spacing: -0.015em; margin-bottom: 8px; }
    .feature p { color: var(--fg-dim); font-size: 14px; line-height: 1.55; }
    .feature.large { grid-column: span 7; min-height: 320px; }
    .feature.medium { grid-column: span 5; min-height: 320px; }
    .feature.small { grid-column: span 4; }
    .feature.wide { grid-column: span 8; }
    @media (max-width: 880px) { .feature, .feature.large, .feature.medium, .feature.small, .feature.wide { grid-column: span 12; } }

    /* Numbers — chiffres editoriaux Instrument Serif italic */
    section.numbers { border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding-block: clamp(64px, 8vw, 120px); }
    .numbers-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: clamp(24px, 3vw, 48px); align-items: end; }
    .stat { grid-column: span 3; display: grid; gap: 8px; padding-block: 16px; }
    .stat .v { font-family: "Instrument Serif", serif; font-style: italic; font-size: clamp(48px, 6vw, 88px); font-weight: 400; line-height: 0.9; letter-spacing: -0.03em; color: var(--fg); }
    .stat .v sup { font-family: "JetBrains Mono", monospace; font-style: normal; font-size: 14px; vertical-align: super; color: var(--accent); margin-left: 4px; }
    .stat .l { font-family: "JetBrains Mono", monospace; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--fg-dim); }
    @media (max-width: 880px) { .stat { grid-column: span 6; } }

    /* CTA final — bandeau editorial centre, generous whitespace */
    section.cta-final { text-align: center; padding-block: clamp(96px, 14vw, 180px); }
    .cta-final h2 { font-size: clamp(40px, 6vw, 80px); font-weight: 500; line-height: 1; letter-spacing: -0.04em; max-width: 16ch; margin-inline: auto; }
    .cta-final h2 .em { font-family: "Instrument Serif", serif; font-style: italic; font-weight: 400; }
    .cta-final p { color: var(--fg-dim); font-size: 16px; line-height: 1.55; max-width: 50ch; margin: 24px auto 40px; }
    .cta-final .ctas { display: inline-flex; gap: 12px; flex-wrap: wrap; justify-content: center; }

    /* Footer — dense 4-col */
    footer { padding-block: 64px 40px; border-top: 1px solid var(--border); }
    .footer-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: clamp(24px, 3vw, 48px); align-items: start; }
    .footer-brand { grid-column: span 4; display: grid; gap: 16px; }
    .footer-brand .desc { color: var(--fg-dim); font-size: 13px; line-height: 1.55; max-width: 38ch; }
    .footer-col { grid-column: span 2; display: grid; gap: 12px; }
    .footer-col h4 { font-family: "JetBrains Mono", monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--fg-faint); }
    .footer-col ul { list-style: none; display: grid; gap: 10px; }
    .footer-col a { color: var(--fg-dim); text-decoration: none; font-size: 13px; transition: color var(--d-fast) var(--ease-out-expo); }
    .footer-col a:hover { color: var(--fg); }
    .footer-base { display: flex; align-items: center; justify-content: space-between; padding-top: 32px; margin-top: 48px; border-top: 1px solid var(--border); font-family: "JetBrains Mono", monospace; font-size: 11px; letter-spacing: 0.04em; color: var(--fg-faint); }
    @media (max-width: 880px) { .footer-brand, .footer-col { grid-column: span 6; } }

    /* Reveal — IntersectionObserver fallback. Modern: animation-timeline: view() */
    .reveal { opacity: 0; transform: translateY(20px); transition: opacity var(--d-slow) var(--ease-out-expo), transform var(--d-slow) var(--ease-out-expo); }
    .reveal.in { opacity: 1; transform: translateY(0); }
    .stagger > * { opacity: 0; transform: translateY(16px); transition: opacity var(--d-slow) var(--ease-out-expo), transform var(--d-slow) var(--ease-out-expo); }
    .stagger.in > * { opacity: 1; transform: translateY(0); }
    .stagger.in > *:nth-child(1) { transition-delay: 0.05s; }
    .stagger.in > *:nth-child(2) { transition-delay: 0.12s; }
    .stagger.in > *:nth-child(3) { transition-delay: 0.18s; }
    .stagger.in > *:nth-child(4) { transition-delay: 0.24s; }
    .stagger.in > *:nth-child(5) { transition-delay: 0.30s; }
    .stagger.in > *:nth-child(6) { transition-delay: 0.36s; }
    @supports (animation-timeline: view()) {
      .reveal-modern { animation: revealIn linear both; animation-timeline: view(); animation-range: entry 0% entry 60%; }
    }
    @keyframes revealIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

    /* Theme toggle */
    .theme-toggle { width: 32px; height: 32px; border-radius: 999px; border: 1px solid var(--border-strong); background: var(--surface); color: var(--fg-dim); cursor: pointer; transition: all var(--d-fast) var(--ease-out-expo); display: grid; place-items: center; }
    .theme-toggle:hover { color: var(--fg); }
    .theme-toggle svg { width: 14px; height: 14px; }

    /* Cursor follow blob — subtle, mix-blend difference */
    .cursor { position: fixed; pointer-events: none; width: 14px; height: 14px; border-radius: 50%; border: 1px solid var(--fg); transform: translate3d(-100px, -100px, 0); transition: transform 80ms linear, width var(--d-fast) var(--ease-spring), height var(--d-fast) var(--ease-spring); mix-blend-mode: difference; z-index: 100; }
    .cursor.on-link { width: 36px; height: 36px; }
    @media (hover: none) { .cursor { display: none; } }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation: none !important; transition: none !important; }
      .reveal, .stagger > * { opacity: 1; transform: none; }
    }
  </style>
</head>
<body>
  <div class="cursor" id="cursor" aria-hidden="true"></div>
  <nav class="top" id="topnav" aria-label="Primary">
    <div class="container row">
      <a class="brand" href="#"><span class="brand-mark"></span>{{BRAND}}</a>
      <ul role="list">
        <li><a href="#features">Features</a></li>
        <li><a href="#numbers">Numbers</a></li>
        <li><a href="#contact">Contact</a></li>
      </ul>
      <div style="display:flex;gap:10px;align-items:center">
        <button class="theme-toggle" id="themeBtn" aria-label="Toggle theme">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>
        </button>
        <a class="btn btn-primary" href="#cta">Get started <span class="arrow">→</span></a>
      </div>
    </div>
  </nav>

  <main>
    <section class="hero">
      <div class="hero-bg"><div class="blob a"></div><div class="blob b"></div></div>
      <div class="hero-grain"></div>
      <div class="container">
        <div class="hero-grid">
          <div class="copy reveal">
            <span class="kicker"><span class="dot"></span>{{EYEBROW}}</span>
            <h1>{{HEADLINE_PREFIX}} <span class="em">{{HEADLINE_EM}}</span> {{HEADLINE_SUFFIX}}</h1>
            <p class="lead">{{SUBHEAD}}</p>
            <div class="ctas">
              <a class="btn btn-primary" href="#cta">Start now <span class="arrow">→</span></a>
              <a class="btn btn-ghost" href="#features">See how it works</a>
            </div>
            <div class="meta">
              <div class="pair"><span class="v">{{META1_V}}</span><span class="l">{{META1_L}}</span></div>
              <div class="pair"><span class="v">{{META2_V}}</span><span class="l">{{META2_L}}</span></div>
              <div class="pair"><span class="v">{{META3_V}}</span><span class="l">{{META3_L}}</span></div>
            </div>
          </div>
          <div class="visual reveal"><div class="frame"><img src="{{HERO_IMG}}" alt="" loading="eager"/></div></div>
        </div>
      </div>
    </section>

    <section id="features">
      <div class="container">
        <div class="section-head reveal">
          <span class="kicker">{{SEC_KICKER}}</span>
          <h2>{{SEC_TITLE_PREFIX}} <span class="em">{{SEC_TITLE_EM}}</span></h2>
          <p>{{SEC_DESC}}</p>
        </div>
        <div class="features-grid stagger">
          <article class="feature large"><div class="ico"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2 4 7v10l8 5 8-5V7l-8-5Z"/></svg></div><h3>{{F1_TITLE}}</h3><p>{{F1_DESC}}</p></article>
          <article class="feature medium"><div class="ico"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 12h18M12 3v18"/></svg></div><h3>{{F2_TITLE}}</h3><p>{{F2_DESC}}</p></article>
          <article class="feature small"><div class="ico"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="9"/></svg></div><h3>{{F3_TITLE}}</h3><p>{{F3_DESC}}</p></article>
          <article class="feature small"><div class="ico"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4h16v16H4z"/></svg></div><h3>{{F4_TITLE}}</h3><p>{{F4_DESC}}</p></article>
          <article class="feature small"><div class="ico"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="m4 12 6-8 4 6 6-4"/></svg></div><h3>{{F5_TITLE}}</h3><p>{{F5_DESC}}</p></article>
          <article class="feature wide"><div class="ico"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 12h4l3-9 6 18 3-9h4"/></svg></div><h3>{{F6_TITLE}}</h3><p>{{F6_DESC}}</p></article>
        </div>
      </div>
    </section>

    <section class="numbers" id="numbers">
      <div class="container">
        <div class="numbers-grid stagger">
          <div class="stat"><span class="v" data-count="{{S1_VAL}}">0</span><span class="l">{{S1_LABEL}}</span></div>
          <div class="stat"><span class="v"><span data-count="{{S2_VAL}}">0</span><sup>{{S2_SUP}}</sup></span><span class="l">{{S2_LABEL}}</span></div>
          <div class="stat"><span class="v" data-count="{{S3_VAL}}">0</span><span class="l">{{S3_LABEL}}</span></div>
          <div class="stat"><span class="v" data-count="{{S4_VAL}}">0</span><span class="l">{{S4_LABEL}}</span></div>
        </div>
      </div>
    </section>

    <section class="cta-final" id="cta">
      <div class="container reveal">
        <h2>{{CTA_TITLE_PREFIX}} <span class="em">{{CTA_TITLE_EM}}</span></h2>
        <p>{{CTA_TEXT}}</p>
        <div class="ctas">
          <a class="btn btn-primary" href="#"><span>{{CTA_BUTTON}}</span> <span class="arrow">→</span></a>
          <a class="btn btn-ghost" href="#">Talk to us</a>
        </div>
      </div>
    </section>
  </main>

  <footer id="contact">
    <div class="container">
      <div class="footer-grid">
        <div class="footer-brand">
          <div class="brand"><span class="brand-mark"></span>{{BRAND}}</div>
          <p class="desc">{{FOOTER_DESC}}</p>
        </div>
        <div class="footer-col"><h4>Product</h4><ul><li><a href="#">Features</a></li><li><a href="#">Pricing</a></li><li><a href="#">Changelog</a></li></ul></div>
        <div class="footer-col"><h4>Company</h4><ul><li><a href="#">About</a></li><li><a href="#">Customers</a></li><li><a href="#">Careers</a></li></ul></div>
        <div class="footer-col"><h4>Resources</h4><ul><li><a href="#">Docs</a></li><li><a href="#">Blog</a></li><li><a href="#">Support</a></li></ul></div>
      </div>
      <div class="footer-base"><span>© {{YEAR}} {{BRAND}}</span><span>Crafted in {{CITY}}</span></div>
    </div>
  </footer>

  <script>
    // Theme toggle
    const root = document.documentElement;
    const stored = localStorage.getItem('theme');
    if (stored) root.setAttribute('data-theme', stored);
    else if (matchMedia('(prefers-color-scheme: light)').matches) root.setAttribute('data-theme', 'light');
    document.getElementById('themeBtn').addEventListener('click', () => {
      const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      const apply = () => { root.setAttribute('data-theme', next); localStorage.setItem('theme', next); };
      if (document.startViewTransition) document.startViewTransition(apply); else apply();
    });

    // Nav scroll state
    const nav = document.getElementById('topnav');
    addEventListener('scroll', () => nav.classList.toggle('scrolled', scrollY > 24), { passive: true });

    // Reveal — IntersectionObserver
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    }, { threshold: 0.18 });
    document.querySelectorAll('.reveal, .stagger').forEach((el) => io.observe(el));

    // Counters easeOutExpo
    document.querySelectorAll('[data-count]').forEach((el) => {
      const target = parseFloat(el.dataset.count);
      const cio = new IntersectionObserver((entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) return;
          cio.unobserve(e.target);
          const dur = 1400, start = performance.now();
          const tick = (now) => {
            const t = Math.min(1, (now - start) / dur);
            const eased = 1 - Math.pow(1 - t, 4);
            const v = target * eased;
            e.target.textContent = target % 1 === 0 ? Math.round(v).toLocaleString() : v.toFixed(1);
            if (t < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }
      }, { threshold: 0.5 });
      cio.observe(el);
    });

    // Magnetic buttons — spring easing, max 6px
    document.querySelectorAll('.btn').forEach((btn) => {
      btn.addEventListener('pointermove', (e) => {
        const r = btn.getBoundingClientRect();
        const x = (e.clientX - r.left - r.width / 2) * 0.18;
        const y = (e.clientY - r.top - r.height / 2) * 0.18;
        btn.style.transform = ` + '`translate3d(${x}px, ${y}px, 0)`' + `;
      });
      btn.addEventListener('pointerleave', () => { btn.style.transform = ''; });
    });

    // Feature cards — radial spotlight follows pointer
    document.querySelectorAll('.feature').forEach((card) => {
      card.addEventListener('pointermove', (e) => {
        const r = card.getBoundingClientRect();
        card.style.setProperty('--mx', ((e.clientX - r.left) / r.width) * 100 + '%');
        card.style.setProperty('--my', ((e.clientY - r.top) / r.height) * 100 + '%');
      });
    });

    // Hero blob mousemove parallax
    const hero = document.querySelector('.hero');
    let raf = null;
    if (hero) {
      hero.addEventListener('pointermove', (e) => {
        if (raf) return;
        raf = requestAnimationFrame(() => {
          const x = (e.clientX / innerWidth - 0.5) * 30;
          const y = (e.clientY / innerHeight - 0.5) * 30;
          hero.querySelectorAll('.blob').forEach((b, i) => { b.style.transform = ` + '`translate3d(${x * (i + 1) * 0.4}px, ${y * (i + 1) * 0.4}px, 0)`' + `; });
          raf = null;
        });
      });
    }

    // Cursor follow — subtle, mix-blend difference
    const cursor = document.getElementById('cursor');
    if (cursor && matchMedia('(hover: hover)').matches) {
      let cx = -100, cy = -100, tx = -100, ty = -100;
      addEventListener('pointermove', (e) => { tx = e.clientX; ty = e.clientY; });
      const tickC = () => { cx += (tx - cx) * 0.18; cy += (ty - cy) * 0.18; cursor.style.transform = ` + '`translate3d(${cx - 7}px, ${cy - 7}px, 0)`' + `; requestAnimationFrame(tickC); };
      requestAnimationFrame(tickC);
      document.querySelectorAll('a, button').forEach((el) => {
        el.addEventListener('pointerenter', () => cursor.classList.add('on-link'));
        el.addEventListener('pointerleave', () => cursor.classList.remove('on-link'));
      });
    }
  </script>
</body>
</html>`

/**
 * v76: starter Three.js complet — single-file ESM via CDN, scene cinematique
 * (5 lights, RoomEnvironment, post-processing UnrealBloom), 9 instances cubes
 * physiques en grille avec rotation animee delta-time, OrbitControls damping,
 * raycaster hover emissif, fog atmospherique. Le LLM reproduit ce niveau au
 * lieu d un cube isole tournant en MeshBasicMaterial.
 */
export const THREE_D_SCENE_REFERENCE = String.raw`<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Scene 3D Premium</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { width: 100%; height: 100%; overflow: hidden; background: #07090f; font-family: 'Inter', system-ui, sans-serif; color: #f5f7fa; }
    canvas { display: block; }
    .hud { position: fixed; top: 1.25rem; left: 1.25rem; padding: 0.85rem 1.1rem; backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); background: rgba(15, 22, 36, 0.55); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; box-shadow: 0 12px 40px -16px rgba(0,0,0,0.6); }
    .hud h1 { font-size: 0.95rem; font-weight: 600; letter-spacing: 0.04em; }
    .hud p { font-size: 0.72rem; color: rgba(245,247,250,0.6); margin-top: 0.25rem; letter-spacing: 0.02em; }
    .hud span { color: #74e8ff; font-weight: 600; }
  </style>
</head>
<body>
  <div class="hud">
    <h1>Scene 3D <span>Aurora</span></h1>
    <p>Glissez pour orbiter — molette pour zoomer — clic pour highlight</p>
  </div>
  <script type="importmap">
    {
      "imports": {
        "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
      }
    }
  </script>
  <script type="module">
    import * as THREE from 'three'
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
    import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
    import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
    import { RenderPass } from 'three/addons/postprocessing/RenderPass.js'
    import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js'
    import { OutputPass } from 'three/addons/postprocessing/OutputPass.js'

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x070912)
    scene.fog = new THREE.FogExp2(0x070912, 0.022)

    const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 200)
    camera.position.set(7, 5, 9)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    renderer.setSize(innerWidth, innerHeight)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.15
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    document.body.appendChild(renderer.domElement)

    const pmrem = new THREE.PMREMGenerator(renderer)
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture

    const hemi = new THREE.HemisphereLight(0xa3c8ff, 0xff8a3d, 0.45)
    scene.add(hemi)
    const key = new THREE.DirectionalLight(0xfff2cf, 1.8)
    key.position.set(8, 12, 6); key.castShadow = true
    key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0001
    key.shadow.camera.left = -12; key.shadow.camera.right = 12; key.shadow.camera.top = 12; key.shadow.camera.bottom = -12
    scene.add(key)
    const fillTeal = new THREE.PointLight(0x74e8ff, 18, 22, 2)
    fillTeal.position.set(-5, 4, -3); scene.add(fillTeal)
    const fillMagenta = new THREE.PointLight(0xff5fae, 14, 18, 2)
    fillMagenta.position.set(4, 2, -5); scene.add(fillMagenta)
    const accent = new THREE.SpotLight(0xfff5e6, 24, 30, Math.PI / 6, 0.4, 1.5)
    accent.position.set(0, 14, 0); accent.target.position.set(0, 0, 0)
    accent.castShadow = true; accent.shadow.mapSize.set(1024, 1024)
    scene.add(accent); scene.add(accent.target)

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(60, 60),
      new THREE.MeshPhysicalMaterial({ color: 0x0e1424, roughness: 0.42, metalness: 0.18, clearcoat: 0.18, clearcoatRoughness: 0.6 }),
    )
    ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground)

    const geometry = new THREE.IcosahedronGeometry(0.65, 0)
    const palette = [0x74e8ff, 0xff5fae, 0xa78bfa, 0xfacc15, 0x34d399]
    const meshes = []
    for (let i = 0; i < 9; i++) {
      const mat = new THREE.MeshPhysicalMaterial({
        color: palette[i % palette.length],
        roughness: 0.18,
        metalness: 0.55,
        clearcoat: 0.85,
        clearcoatRoughness: 0.05,
        emissive: 0x000000,
        emissiveIntensity: 0,
      })
      const mesh = new THREE.Mesh(geometry, mat)
      const col = i % 3, row = Math.floor(i / 3)
      mesh.position.set((col - 1) * 2.4, 1 + Math.sin(i * 1.7) * 0.4, (row - 1) * 2.4)
      mesh.castShadow = true; mesh.receiveShadow = true
      mesh.userData.baseColor = mat.color.clone()
      mesh.userData.spinSpeed = 0.4 + Math.random() * 0.6
      scene.add(mesh); meshes.push(mesh)
    }

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true; controls.dampingFactor = 0.06
    controls.autoRotate = true; controls.autoRotateSpeed = 0.6
    controls.target.set(0, 1, 0)
    renderer.domElement.addEventListener('pointerdown', () => { controls.autoRotate = false })

    const composer = new EffectComposer(renderer)
    composer.addPass(new RenderPass(scene, camera))
    composer.addPass(new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.65, 0.6, 0.85))
    composer.addPass(new OutputPass())

    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2(99, 99)
    addEventListener('pointermove', (e) => { pointer.x = (e.clientX / innerWidth) * 2 - 1; pointer.y = -(e.clientY / innerHeight) * 2 + 1 })

    addEventListener('resize', () => {
      camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix()
      renderer.setSize(innerWidth, innerHeight); composer.setSize(innerWidth, innerHeight)
    })

    const clock = new THREE.Clock()
    function loop() {
      const dt = clock.getDelta()
      const t = clock.getElapsedTime()
      meshes.forEach((m, idx) => {
        m.rotation.y += dt * m.userData.spinSpeed
        m.rotation.x += dt * m.userData.spinSpeed * 0.7
        m.position.y = 1 + Math.sin(t * 1.4 + idx * 0.7) * 0.35
      })
      raycaster.setFromCamera(pointer, camera)
      const hits = raycaster.intersectObjects(meshes)
      meshes.forEach((m) => { m.material.emissive.set(0x000000); m.material.emissiveIntensity = 0 })
      if (hits[0]) { hits[0].object.material.emissive.copy(hits[0].object.userData.baseColor); hits[0].object.material.emissiveIntensity = 0.9 }
      controls.update()
      composer.render()
      requestAnimationFrame(loop)
    }
    loop()
  </script>
</body>
</html>`

/**
 * Subject-specific design hints. The generic PREMIUM_HTML_REFERENCE covers
 * the universal patterns (mesh gradient hero, glassmorphism nav, scroll
 * reveal). These additional blocks tune the structure to the actual subject
 * the user is asking for — saas needs pricing tiers, ecommerce needs product
 * cards with cart, portfolio needs project gallery, dashboard needs sidebar.
 */
type SubjectVariant = 'saas' | 'portfolio' | 'ecommerce' | 'dashboard' | 'landing' | '3d_scene' | 'game' | 'mobile' | 'desktop' | 'brand_landing' | null

const SUBJECT_VARIANTS: Record<Exclude<SubjectVariant, null>, string[]> = {
  saas: [
    '### SECTIONS SPECIFIQUES SAAS (ajoute en plus de la structure de base)',
    '- Hero: focus value-prop B2B + 1 ligne courte explicite + capture d ecran/dashboard preview a droite (canvas/SVG anime).',
    '- Section "Logos clients" en marquee horizontal (animation translateX infinie 30s ease-linear).',
    '- "Features grid" 6-9 cards avec icone SVG + titre court + 2-3 lignes (pas de paragraphes).',
    '- "Comment ca marche" 3 etapes numerotees avec stepper visuel (cercles connectes par lignes).',
    '- "Pricing tiers": 3 plans (free/pro/enterprise) en cartes avec liste features + CTA. Le plan recommande a un border accent + label "Le plus populaire".',
    '- "Integrations": grille de 12-20 logos (SVG inline ou tile colore) qui s anime au hover.',
    '- "Testimonials" avec photo (svg avatar) + nom + role + 2 lignes.',
    '- "FAQ" accordion avec animation hauteur (max-height transition 350ms).',
    '- CTA final FORT: bouton XL gradient + microcopy rassurant ("essai gratuit, sans CB requise").',
  ],
  portfolio: [
    '### SECTIONS SPECIFIQUES PORTFOLIO (ajoute en plus de la structure de base)',
    '- Hero personnel: nom + role + 1 ligne mission, photo/illustration ronde a droite.',
    '- "Selected work" gallery masonry (grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)) + grid-auto-rows:minmax(200px, auto)).',
    '- Chaque project card: image preview + titre + tags + hover overlay avec description + lien.',
    '- Animation gallery: stagger fade-in (delay incremental 80ms par card via JS ou CSS animation-delay).',
    '- "Case study" detail: cover image, contexte 1 paragraphe, role+stack en bullets, screenshots avec scroll horizontal sur mobile.',
    '- "About me" colonne gauche photo, droite bio + skills tags (pills).',
    '- "Contact" form simple (3 fields) + email direct + reseaux (icons SVG inline).',
    '- Cursor custom (optional) ou cursor blob qui suit la souris (mousemove + translate3d throttled rAF).',
    '- Footer minimal avec annee dynamique.',
  ],
  ecommerce: [
    '### SECTIONS SPECIFIQUES ECOMMERCE (ajoute en plus de la structure de base)',
    '- Hero: best-seller en vedette + CTA "Decouvrir" + visuel produit central (image ou SVG stylise).',
    '- "Categories" grid 4-6 cards avec image + label, hover scale 1.04 + shadow accru.',
    '- "Products grid" 12-24 cards: image, badge promo si applicable, titre, prix barre + prix actuel, etoiles rating (svg), bouton "Ajouter au panier".',
    '- Quick view au hover: overlay translucent avec bouton "Voir details" (smooth scale-up).',
    '- "Filters sidebar" (desktop) ou drawer (mobile): categories, prix range, marques, taille, couleur (chips).',
    '- "Cart drawer" sticky right: items list, qty +/-, total, bouton "Commander". Anime avec slide-in 300ms.',
    '- "Reviews" carousel scroll horizontal scroll-snap-type:x mandatory.',
    '- Footer 4 cols: shop, aide, marque, newsletter form.',
    '- Trust badges: livraison gratuite, retour 30j, paiement secure, SAV.',
  ],
  dashboard: [
    '### SECTIONS SPECIFIQUES DASHBOARD (ajoute en plus de la structure de base)',
    '- Layout: sidebar fixe gauche (240px) + main contenu. Sidebar avec logo top, nav items (icone + label), user pill bottom.',
    '- Top bar dans le main: titre page courante, search bar centrale, notifications (icon + badge), theme toggle, avatar user.',
    '- "KPI cards" row: 4 cartes avec gros chiffre + delta % (vert/rouge avec fleche), sparkline mini SVG en bas.',
    '- "Main chart" panel: line/bar chart en CSS pur ou via canvas (axes + legend + tooltip on hover).',
    '- "Data table" avec header sticky, rows zebrees subtilement, hover row, sort icons, pagination.',
    '- "Activity feed" colonne droite: liste evenements recents avec icones colorees + timestamp.',
    '- "Quick actions" cards 2x2 avec icone gradient + label.',
    '- Skeleton loaders pendant le data fetch (CSS animation gradient sweep).',
    '- Tous les chiffres animes au mount via counter easeOutCubic 1200ms.',
    '- Mobile: sidebar devient drawer toggleable, KPI cards stackees, table scrollable horizontal.',
  ],
  landing: [
    '### SECTIONS SPECIFIQUES LANDING (ajoute en plus de la structure de base)',
    '- Hero focus: value-prop forte + 2 CTAs + visuel mockup/illustration impactant.',
    '- "Social proof": logos partners + chiffres cles (1M users, 4.8 rating).',
    '- "Features highlights" 3 colonnes avec icones colorees + 2 lignes chacune.',
    '- "How it works" 3 etapes numerotees illustrees.',
    '- "Pricing" simple (1-3 tiers) ou single CTA si gratuit.',
    '- "FAQ" accordion 5-8 questions.',
    '- Final CTA full-width section.',
  ],
  '3d_scene': [
    '### SECTIONS SPECIFIQUES SCENE 3D INTERACTIVE',
    '- IMPORTS THREE.JS via CDN ESM jsdelivr 0.160 — `import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"`.',
    '- OrbitControls + GLTFLoader + RGBELoader + RoomEnvironment + EffectComposer + UnrealBloomPass + OutputPass via examples/jsm/.',
    '- Si physique implicite: Rapier3D-compat — `import RAPIER from "https://cdn.jsdelivr.net/npm/@dimforge/rapier3d-compat@0.13.0/+esm"` puis `await RAPIER.init()`.',
    '- WebGLRenderer: `antialias:true, alpha:true, powerPreference:"high-performance"`, `setPixelRatio(min(devicePixelRatio, 2))`, `outputColorSpace = SRGBColorSpace`, `toneMapping = ACESFilmicToneMapping`, `toneMappingExposure ≈ 1.1`, `shadowMap.enabled = true`, `shadowMap.type = PCFSoftShadowMap`.',
    '- Camera: PerspectiveCamera(45-55 fov, aspect, 0.1, 200), position cinematique (3/4 angle).',
    '- ECLAIRAGE PREMIUM: HemisphereLight(skyBlue→groundOrange, 0.4-0.6) + DirectionalLight cle (1.5-2.5, castShadow, mapSize 2048, bias -0.0001) + PointLight/SpotLight accent coloree.',
    '- COULEURS LUMIERES stylees: pas du blanc plat — palette violet/orange / teal/magenta / gold/blue selon mood.',
    '- MATERIALS PBR uniquement: MeshStandardMaterial / MeshPhysicalMaterial (NEVER MeshBasic sauf billboards). Config roughness, metalness, clearcoat, transmission, ior, iridescence, sheen.',
    '- ENVIRONMENT: RoomEnvironment (built-in, offline) attache a `scene.environment` ET `scene.background = environment` ou un fond travaille (color sombre + fog).',
    '- POST-PROCESSING: RenderPass + UnrealBloomPass(threshold:0.85, strength:0.5-0.9, radius:0.6) + OutputPass. composer.render() au lieu de renderer.render().',
    '- COMPOSITION: minimum 5-15 objets distincts dans la scene, JAMAIS un seul mesh isole. Foreground/mid/background, regle des tiers.',
    '- ANIMATION: requestAnimationFrame avec DELTA TIME (clock.getDelta()), variations rotation/sin-flottement/pulse/bobbing.',
    '- INTERACTION: OrbitControls(enableDamping:true, dampingFactor:0.06, autoRotate:true jusqu au premier clic) + Raycaster sur pointermove pour highlight emissive.',
    '- Sol PBR (plane 100x100, MeshPhysicalMaterial clearcoat:0.1, roughness:0.4) + ombres recues + brouillard scene.fog atmospherique.',
    '- INSTANCED MESH si >100 objets repetitifs (foret, swarm, particules).',
    '- Shader GLSL custom (au moins UN): hologramme fresnel, glow rim, mesh gradient procedural, ou water sin+noise displacement.',
  ],
  game: [
    '### SECTIONS SPECIFIQUES JEU WEB (canvas 2D ou Three.js 3D)',
    '- Boucle de jeu: requestAnimationFrame avec delta time (`const delta = (now - lastTime) / 1000`) — JAMAIS setInterval.',
    '- Gestion clavier complete: keydown + keyup pour directions, prevention scroll par espace/fleches (e.preventDefault).',
    '- Gestion tactile (touchstart/touchend) si le jeu est jouable au tap.',
    '- localStorage pour les meilleurs scores (high score persistent).',
    '- Web Audio API: AudioContext cree au premier geste utilisateur (autoplay policy), 3+ sons synthetises (action, score, game over) via OscillatorNode + GainNode.',
    '- ECRANS COMPLETS obligatoires: demarrage stylise + jeu + pause (touche P/Escape) + game over avec score + meilleur score + bouton "Rejouer".',
    '- Progression: difficulte croissante (vitesse, ennemis, patterns).',
    '- "Juice" obligatoire: particles, screen shake (CSS transform translate), flash blanc 100ms, trainees, feedback immediat sur chaque action.',
    '- Responsive: canvas s adapte a la fenetre via resize listener (canvas.width/height = innerWidth/Height).',
    '- visibilitychange → pause auto quand l onglet perd le focus.',
    '- Cleanup: removeEventListener au destroy pour eviter les fuites au reload.',
  ],
  mobile: [
    '### SECTIONS SPECIFIQUES APP MOBILE (React Native ou Flutter)',
    '- React Native: `npx create-expo-app` avec Expo Router pour navigation file-based.',
    '- Flutter: `flutter create` avec Material 3 + Material You theming.',
    '- ATOMS premium: cards avec elevation/shadow + radius, buttons avec ripple/haptic feedback, inputs avec floating label.',
    '- LAYOUT respecte safe-area-insets (notch, home indicator) via SafeAreaView (RN) ou SafeArea (Flutter).',
    '- ANIMATIONS: react-native-reanimated v3 (RN) ou implicit/explicit animations (Flutter) pour transitions naturelles.',
    '- DARK MODE auto via prefers-color-scheme equivalent (Appearance API RN, MediaQuery Flutter).',
    '- TYPO premium: SF Pro/Roboto/Inter via expo-font ou GoogleFonts package.',
    '- ICONOGRAPHIE: lucide-react-native (RN) ou material-symbols (Flutter), 24px standard.',
    '- BOTTOM NAV ou tabs avec icones + labels, avec indicator anime au tab actif.',
    '- ECRANS: home, detail, search, settings, profile minimum.',
    '- Pull-to-refresh + infinite scroll quand pertinent.',
    '- Skeleton loaders pendant les fetchs (shimmer).',
  ],
  desktop: [
    '### SECTIONS SPECIFIQUES APP DESKTOP (Tauri ou Electron)',
    '- Tauri: shell Rust + frontend Vite/React, Cargo.toml + tauri.conf.json + src-tauri/.',
    '- Electron: main.js + preload.js + renderer.js, contextIsolation:true.',
    '- Window decoration: titleBarStyle:"hiddenInset" (mac) ou customisee (Win/Linux) pour look pro.',
    '- TRAFFIC LIGHTS macOS conserves, frame customise sur Win/Linux avec close/min/max boutons.',
    '- LAYOUT: sidebar gauche + main, comme une app desktop pro (Notion, Linear, VS Code).',
    '- COMMAND PALETTE Cmd+K avec fuzzy search (kbar, cmdk, ou implementation maison).',
    '- KEYBOARD SHORTCUTS visibles dans une cheatsheet (?). Tous les actions principales accessibles au clavier.',
    '- AUTO-UPDATER (Tauri updater plugin / electron-updater) configure.',
    '- TRAY ICON systeme avec menu contextuel.',
    '- SETTINGS persistantes (Tauri Store / electron-store).',
    '- Dark mode + theme switcher visible dans settings.',
    '- Fenetre min size raisonnable (800x600), launcher launches avec dimensions sauvegardees.',
  ],
  brand_landing: [
    '### SECTIONS SPECIFIQUES BRAND LANDING (page produit / marque iconique)',
    '',
    '⚠️ CHECKLIST OBLIGATOIRE A VERIFIER AVANT D ECRIRE LE PREMIER CARACTERE DE CODE:',
    '  [ ] Three.js scene avec produit 3D procedural (recipe productShape definie en amont).',
    '  [ ] ShaderMaterial Hologramme Fresnel sur halo entourant le produit (code copy-paste fourni plus bas — DOIT etre present sinon la sortie est REJETEE par la gate de fidelite).',
    '  [ ] EffectComposer + UnrealBloomPass (composer.render() au lieu de renderer.render()).',
    '  [ ] OrbitControls(autoRotate:true).',
    '  [ ] >= 2 markers PLACEHOLDER_SUBJECT_IMG_* dans la page.',
    '  [ ] Couleur primaire de la marque dominante 50-70% du visuel.',
    '  [ ] Nom de la marque dans <title>, <h1> du hero, et 3+ sections.',
    'Tu coches mentalement chacun avant de generer. Si un seul est manque, repense la structure AVANT le code.',
    '',
    '- LECTURE DU SUJET: cette page parle d UNE marque ou d UN produit precis (ex: Coca-Cola, Tesla, iPhone). La marque est citee dans le bloc VERROUILLAGE SUJET en amont.',
    '- HERO IMMERSIF: occupe au moins 100vh.',
    '  - Background: gradient vertical/diagonal aux COULEURS DE LA MARQUE (primaire vers noir, ou primaire vers secondaire). PAS le mesh-gradient violet/cyan/ambre du starter generique.',
    '  - Headline en clamp(3rem, 7vw, 6.5rem), font-weight 800-900, kerning serre (-0.03em). Gradient text optionnel mais subtil.',
    '  - Subheadline 1-2 lignes (max 18 mots) tournee marque/produit (ex: "Le rouge le plus celebre du monde, depuis 1886").',
    '  - 2 CTAs (primaire pleine + ghost/outline), accent primaire de la marque.',
    '  - Visuel principal a droite OU centre: <img src="PLACEHOLDER_SUBJECT_IMG" ...> (image reelle du produit/logo) + glow halo derriere via box-shadow ou ::after blur.',
    '  - Particle / bulle / etoile / flamme system en canvas absolute pointer-events:none, theme-coherent (bulles blanches pour soda, etoiles pour Apple, flammes pour Burger King, etc.).',
    '- SECTION HERITAGE / STORYTELLING: bandeau rapide avec date/origine + 1-2 lignes mythologiques de la marque, image lifestyle PLACEHOLDER_SUBJECT_IMG_2 en arriere-plan parallax.',
    '- SECTION PRODUITS / VARIANTES: grille 3-6 cards (chaque card = un produit ou une variante). Chaque card avec PLACEHOLDER_SUBJECT_IMG_* OU SVG inline marque-coherent. Hover = scale(1.04) + tilt 3D leger (transform: perspective(1000px) rotateY(...)) selon mouseX.',
    '- SECTION 3D / EFFET SIGNATURE: au moins UN bloc visuel ambitieux:',
    '  - Three.js via CDN ESM (https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js) — produit en rotation OrbitControls auto-rotate, MeshPhysicalMaterial PBR aux couleurs marque, environment + bloom.',
    '  - OU CSS 3D pur: produit (canette, bottle, phone) construit en plusieurs <div> avec transform translateZ + rotateY animation infinite.',
    '  - OU canvas particle system signature (bulles montant, vapeur, etoiles, fumee de pneu) plein ecran derriere la section.',
    '- SECTION GALLERY / SHOWCASE: parallax stack ou marquee horizontale d images reelles de la marque (PLACEHOLDER_SUBJECT_IMG_1...3 + reuse).',
    '- SECTION CHIFFRES / IMPACT: 3-4 KPI gigantesques anime au scroll (counter easeOutCubic 1500ms): "1.9 milliard de canettes/jour", "200 pays", etc. — adapte les chiffres au contexte de la marque.',
    '- SECTION CITATION ICONIQUE: une grosse citation a propos de la marque (jingle, slogan, phrase fondateur), typo serif/script imposante, contraste fort.',
    '- CTA FINAL pleine largeur: bandeau couleur primaire de la marque + headline puissante + bouton XL.',
    '- FOOTER 4 cols: marque (mini-logo SVG inline), liens, reseaux, newsletter.',
    '',
    '### EXIGENCES VISUELLES SPECIFIQUES BRAND',
    '- TYPO HERITAGE: si la marque a un wordmark celebre (Coca Spencerian, Disney, Ford italic), evoque-le via Google Fonts ("Pacifico", "Lobster", "Playfair Display Italic", "Bungee"). PAS Inter generique partout.',
    '- COULEURS PURES: la couleur primaire doit dominer 50-70% du visuel, secondaire 20-30%, neutres 10-20%. PAS de violet/rose generique du starter.',
    '- TEXTURES: noise overlay + leger grain + condensation/reflets selon contexte (ex: gouttelettes pour soda).',
    '- ANIMATIONS DECLENCHEES PAR SCROLL: chaque section reveal stagger, hero parallax sur scrollY, blob particle qui suit la souris.',
    '- AUCUNE STOCK PHOTO GENERIQUE: utilise les PLACEHOLDER_SUBJECT_IMG_* (images reelles de la marque). Si tu veux du complementaire, fais des SVG inline marque-coherent (logo simplifie, pictogrammes thematiques).',
    '',
    '### EFFET SHADER GLSL SIGNATURE — OBLIGATOIRE (NON-OPTIONNEL, COPIE LE BLOC CI-DESSOUS)',
    'CHAQUE page brand_landing DOIT inclure le shader Hologramme Fresnel ci-dessous. Pas de "tu peux choisir parmi A/B/C", c est le shader DEFAUT a integrer SAUF si tu prefere une autre option dans la liste qui suit. Copie ce code dans ton <script type="module"> apres avoir cree la scene principale, AVANT le rendu.',
    '',
    '```js',
    '// ===== SHADER HOLOGRAMME FRESNEL — copy-paste, change PRIMARY_COLOR_HEX =====',
    'const haloMat = new THREE.ShaderMaterial({',
    '  uniforms: {',
    '    uColor: { value: new THREE.Color("PRIMARY_COLOR_HEX") },  // <-- ex: "#F40009" pour Coca',
    '    uTime: { value: 0 },',
    '  },',
    '  vertexShader: `',
    '    varying vec3 vNormalW;',
    '    varying vec3 vViewDir;',
    '    void main() {',
    '      vec4 worldPos = modelMatrix * vec4(position, 1.0);',
    '      vNormalW = normalize(mat3(modelMatrix) * normal);',
    '      vViewDir = normalize(cameraPosition - worldPos.xyz);',
    '      gl_Position = projectionMatrix * viewMatrix * worldPos;',
    '    }',
    '  `,',
    '  fragmentShader: `',
    '    uniform vec3 uColor;',
    '    uniform float uTime;',
    '    varying vec3 vNormalW;',
    '    varying vec3 vViewDir;',
    '    void main() {',
    '      float fresnel = pow(1.0 - max(dot(vNormalW, vViewDir), 0.0), 3.0);',
    '      float pulse = 0.7 + 0.3 * sin(uTime * 2.0);',
    '      gl_FragColor = vec4(uColor * fresnel * 1.4 * pulse, fresnel);',
    '    }',
    '  `,',
    '  transparent: true,',
    '  blending: THREE.AdditiveBlending,',
    '  depthWrite: false,',
    '})',
    '// Halo mesh = clone du produit principal scaled-up 1.08x avec haloMat',
    'const halo = new THREE.Mesh(productMesh.geometry, haloMat)',
    'halo.scale.setScalar(1.08)',
    'productMesh.add(halo)',
    '// Animation update (dans le requestAnimationFrame loop):',
    '// haloMat.uniforms.uTime.value = clock.getElapsedTime()',
    '```',
    '',
    'CE BLOC EST OBLIGATOIRE. Si tu ne l inclus pas, le rendu sera rejete par la gate de fidelite.',
    '',
    '### ALTERNATIVES (si une option B/C/D/E te semble plus adaptee, tu peux la SUBSTITUER au shader Fresnel mais TOUJOURS mettre UN shader)',
    '',
    'Option A — Hologramme Fresnel sur le produit 3D (recommande pour can/bottle/phone/watch/headphones):',
    '```js',
    'const fresnelMat = new THREE.ShaderMaterial({',
    '  uniforms: {',
    '    uColor: { value: new THREE.Color("PRIMARY_COLOR_HEX") },',
    '    uTime: { value: 0 },',
    '    uIntensity: { value: 1.4 },',
    '  },',
    '  vertexShader: `',
    '    varying vec3 vWorldNormal;',
    '    varying vec3 vViewDir;',
    '    void main() {',
    '      vec4 worldPos = modelMatrix * vec4(position, 1.0);',
    '      vWorldNormal = normalize(mat3(modelMatrix) * normal);',
    '      vViewDir = normalize(cameraPosition - worldPos.xyz);',
    '      gl_Position = projectionMatrix * viewMatrix * worldPos;',
    '    }`,',
    '  fragmentShader: `',
    '    uniform vec3 uColor; uniform float uTime; uniform float uIntensity;',
    '    varying vec3 vWorldNormal; varying vec3 vViewDir;',
    '    void main() {',
    '      float fresnel = pow(1.0 - max(dot(vWorldNormal, vViewDir), 0.0), 3.0);',
    '      float pulse = 0.7 + 0.3 * sin(uTime * 2.0);',
    '      vec3 col = uColor * fresnel * uIntensity * pulse;',
    '      gl_FragColor = vec4(col, fresnel);',
    '    }`,',
    '  transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,',
    '})',
    '// puis chaque frame: fresnelMat.uniforms.uTime.value = clock.getElapsedTime()',
    '// applique-le sur un mesh halo legerement scale-up autour du produit principal.',
    '```',
    '',
    'Option B — Iridescence physique (recommande pour bag/shoe/cup/card):',
    '- MeshPhysicalMaterial avec iridescence: 1.0, iridescenceIOR: 1.5, iridescenceThicknessRange: [100, 800]',
    '- Reflets arc-en-ciel automatiques physiquement corrects, plus realistes que le shader fresnel.',
    '- Combine avec metalness:0.3, roughness:0.4 pour un soft sheen luxueux.',
    '',
    'Option C — Liquid mesh gradient background (recommande pour logo):',
    '```js',
    'const bgMat = new THREE.ShaderMaterial({',
    '  uniforms: { uTime: { value: 0 }, uColor1: { value: new THREE.Color("PRIMARY_COLOR_HEX") }, uColor2: { value: new THREE.Color("SECONDARY_COLOR_HEX") } },',
    '  vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position, 1.0); }`,',
    '  fragmentShader: `',
    '    uniform float uTime; uniform vec3 uColor1; uniform vec3 uColor2; varying vec2 vUv;',
    '    float fbm(vec2 p) { float v = 0.0; float a = 0.5;',
    '      for (int i = 0; i < 5; i++) { v += a * sin(p.x * 1.3 + p.y * 2.1 + uTime * 0.4); p *= 2.0; a *= 0.5; }',
    '      return v;',
    '    }',
    '    void main() {',
    '      float n = fbm(vUv * 3.0);',
    '      vec3 col = mix(uColor1, uColor2, smoothstep(-0.3, 0.7, n));',
    '      gl_FragColor = vec4(col, 1.0);',
    '    }`,',
    '})',
    '// applique sur PlaneGeometry plein-ecran derriere la scene (z=-10).',
    '```',
    '',
    'Option D — Particle attractor au curseur (recommande pour controller/console/headphones):',
    '- BufferGeometry avec 5000 points, attribut position random sphere',
    '- ShaderMaterial vertex shader morph position vers uniforms.uMouseTarget (Vec3 from raycaster on PlaneZ=0)',
    '- fragmentShader: distance fade + couleur primaire glowing',
    '- Le pointer attire les particules a la souris -> effet futuriste signature',
    '',
    'Option E — Scanline retro CRT post-processing (recommande pour brand vintage / gaming):',
    '- EffectComposer + RenderPass + custom ShaderPass:',
    '  fragmentShader vec2 sl = vec2(uv.x, mod(uv.y * 240.0 + time * 5.0, 1.0)); col *= 0.92 + 0.08 * sin(uv.y * 600.0)',
    '- Donne un look CRT TV vintage immersif.',
    '',
    '### POST-PROCESSING OBLIGATOIRE (au moins UnrealBloomPass)',
    '- import { EffectComposer } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/postprocessing/EffectComposer.js"',
    '- import { RenderPass } from ".../examples/jsm/postprocessing/RenderPass.js"',
    '- import { UnrealBloomPass } from ".../examples/jsm/postprocessing/UnrealBloomPass.js"',
    '- import { OutputPass } from ".../examples/jsm/postprocessing/OutputPass.js"',
    '- Bloom config: threshold:0.65, strength:0.85, radius:0.5 — fait briller la couleur primaire sans flouter le produit.',
    '- composer.setPixelRatio(min(devicePixelRatio, 2)); composer.setSize(w, h)',
    '- Boucle render: composer.render() au lieu de renderer.render() — sinon le bloom ne s applique pas.',
    '',
    '### EFFETS COMPLEMENTAIRES (NICE TO HAVE pour pousser au-dela du basique)',
    '- DOF / Bokeh: BokehPass(scene, camera, {focus:5, aperture:0.0008, maxblur:0.012}) — focus piqu sur le produit, arriere-plan flou cinematic.',
    '- Vignette: customShaderPass avec vec2 d=uv-0.5; col*=smoothstep(0.7,0.3,length(d)); — assombrissement bords pour focus central.',
    '- Chromatic aberration au scroll: shifter R/G/B channels par 1-2px sur scrollVelocity > 0.5 — effet glitch dynamique.',
    '- Film grain: ajout sin(rand(uv*time)) * 0.03 sur final color — texture cinema legere.',
    '',
    'OUVERTURE: tu peux composer plusieurs options simultanement (ex: Option A halo Fresnel SUR le produit + Option C gradient background + Bloom). Le but est un rendu qui ressemble a un site Awwwards SOTM, pas a un tutoriel debutant.',
  ],
}

const SAAS_PATTERNS = /\b(saas|abonnement|subscription|pricing|tarif|plan|enterprise|api|platform|productivit|crm|erp|outil pro)\b/i
const PORTFOLIO_PATTERNS = /\b(portfolio|portefeuille|cv|curriculum|developer\s*portfolio|projets|works|showcase|freelance|graphiste|photographe|artiste)\b/i
const ECOMMERCE_PATTERNS = /\b(boutique|shop|magasin|ecommerce|e-commerce|panier|cart|vente|produit|store|catalogue|prix|achat|click and collect)\b/i
const DASHBOARD_PATTERNS = /\b(dashboard|admin|console|analytics|stats|metrics|monitoring|kpi|backoffice|panel|tableau de bord)\b/i
const THREE_D_PATTERNS = /\b(three\.?js|threejs|webgl|webgpu|3d|scene 3d|model 3d|gltf|glb|orbit ?control|rapier|cannon|babylon)\b/i
const GAME_PATTERNS = /\b(jeu|game|arcade|puzzle|platformer|shooter|rpg|tetris|snake|pong|breakout|asteroid|2048|wordle|memory|chess|echecs|score|highscore|level|niveau)\b/i
const MOBILE_PATTERNS = /\b(react native|expo|flutter|mobile app|application mobile|ios app|android app|app smartphone|app telephone)\b/i
const DESKTOP_PATTERNS = /\b(electron|tauri|desktop app|application desktop|app native|windows app|macos app)\b/i

export function detectSubjectVariant(promptText: string): SubjectVariant {
  const lower = promptText.toLowerCase()
  // Order matters: most specific first.
  if (DESKTOP_PATTERNS.test(lower)) return 'desktop'
  if (MOBILE_PATTERNS.test(lower)) return 'mobile'
  if (THREE_D_PATTERNS.test(lower)) return '3d_scene'
  if (GAME_PATTERNS.test(lower)) return 'game'
  if (DASHBOARD_PATTERNS.test(lower)) return 'dashboard'
  if (ECOMMERCE_PATTERNS.test(lower)) return 'ecommerce'
  if (PORTFOLIO_PATTERNS.test(lower)) return 'portfolio'
  if (SAAS_PATTERNS.test(lower)) return 'saas'
  if (/\b(landing|home|accueil|hero)\b/i.test(lower)) return 'landing'
  return null
}

/**
 * Build the design reference snippet to inject into the codeur prompt.
 * The LLM is told this is the LEVEL expected — not a copy-paste source.
 *
 * v68: optionally append subject-specific section guidance based on the
 * detected variant from the user prompt.
 *
 * v71: `forcedVariant` lets the brand-anchor path pin the reference to the
 * `brand_landing` variant regardless of what the prompt would have detected
 * on its own ("article Coca Cola" alone does not trigger any variant).
 */
export function buildPremiumDesignReferenceBlock(promptHint?: string, forcedVariant?: string): string {
  // We slice the reference to keep token count reasonable (~2200 tokens).
  // The LLM does not need the full file: it needs the patterns.
  const reference = PREMIUM_HTML_REFERENCE
  const detected = promptHint ? detectSubjectVariant(promptHint) : null
  // Force the brand_landing variant when the orchestrator passed it — overrides
  // a weaker detection (e.g. landing) so brand pages always get brand sections.
  const variant: SubjectVariant = (forcedVariant && forcedVariant in SUBJECT_VARIANTS)
    ? (forcedVariant as Exclude<SubjectVariant, null>)
    : detected
  const subjectBlock = variant ? '\n\n' + SUBJECT_VARIANTS[variant].join('\n') : ''

  // v76: when 3d_scene is detected, swap PREMIUM_HTML_REFERENCE for the
  // Three.js starter — the LLM needs an actual working scene to mirror, not
  // a mesh-gradient landing page that has nothing to do with WebGL.
  const isThreeDScene = variant === '3d_scene'
  // v85c : slice the embedded reference HARD. The FULL PREMIUM_HTML_REFERENCE is
  // ~28.6k chars; embedding it verbatim pushed the CODEUR system prompt to
  // ~60k chars (~15k tokens) — larger than a safe 16 GB context window, so the
  // generation prompt got truncated and the model emitted nothing. The LLM
  // needs the PATTERNS (the bullets below) + a concrete TASTE, not the whole
  // file. A ~3000-char excerpt (head + hero + a section) conveys the level.
  const fullReference = isThreeDScene ? THREE_D_SCENE_REFERENCE : reference
  const usedReference = fullReference.length > 3000
    ? fullReference.slice(0, 3000) + '\n<!-- … extrait tronque : reproduis les PATTERNS ci-dessus avec TON contenu, ne copie pas ce HTML verbatim … -->'
    : fullReference
  const referenceLabel = isThreeDScene
    ? 'Voici un STARTER THREE.JS qui represente le NIVEAU exige sur toute scene 3D web.'
    : 'Voici un STARTER HTML qui represente le NIVEAU de design exige sur tout site/app que tu produis.'

  const patternBullets = isThreeDScene
    ? [
        '- ESM via importmap CDN jsdelivr (three@0.160 + addons)',
        '- 5 lights minimum: HemisphereLight + DirectionalLight castShadow + 2 PointLights coloreees + SpotLight accent',
        '- Materials PBR uniquement (MeshPhysicalMaterial avec clearcoat, roughness, metalness)',
        '- PMREMGenerator + RoomEnvironment pour reflections offline',
        '- Post-processing: EffectComposer + RenderPass + UnrealBloomPass + OutputPass',
        '- 9+ objets distincts (jamais un seul mesh isole)',
        '- Animation delta-time via clock.getDelta() (pas de Date.now)',
        '- OrbitControls enableDamping autoRotate jusqu au premier clic',
        '- Raycaster pointermove pour highlight emissive',
        '- Sol PBR + scene.fog + scene.background harmonise',
      ]
    : [
        '- v82m7 — barre senior IC: oklch palette restreinte (UN seul accent), Inter Variable + Instrument Serif italic display + JetBrains Mono kicker',
        '- Easing tokens en CSS variables: --ease-out-expo, --ease-spring (cubic-bezier(0.32,0.72,0,1)), --ease-smooth. Durees 160/240/480ms',
        '- Grille 12-col explicite (grid-template-columns: repeat(12, minmax(0, 1fr))), col-span asymetriques (hero copy span-7 / visual span-5)',
        '- Container queries (@container (min-width: 880px)) en complement des media queries',
        '- View Transitions API (document.startViewTransition) pour le swap dark/light',
        '- Scroll-driven natif quand supporte: @supports (animation-timeline: view()) + animation-range: entry 0% entry 60%',
        '- Glassmorphism Apple/Linear: backdrop-filter blur(20px) saturate(180%) + inset 0 1px 0 oklch(1 0 0 / 0.06) signature',
        '- Mosaique inegale (.feature.large/medium/small/wide) — JAMAIS une grille auto-fit uniforme',
        '- Display headline italic serif highlighted (.em avec ::before en accent-soft skew-3deg) — pas un h1 bold scolaire',
        '- Stats editorialisees: chiffres en Instrument Serif italic + sup en JetBrains Mono accent',
        '- Hover scale 1.02 max + magnetic spring (transform max 18% du delta), JAMAIS scale 1.1',
        '- Cursor follow subtil (14px outline, mix-blend-mode: difference, lerp 0.18) — pas une fleche custom',
        '- Counter ease-out-expo (Math.pow(1-t,4)) + Number.toLocaleString pour les milliers',
        '- Footer dense 12-col (4+2+2+2 + footer-base mono uppercase)',
        '- prefers-reduced-motion respecte strict',
      ]

  return [
    '## REFERENCE DESIGN PREMIUM (NIVEAU MINIMUM ATTENDU)',
    '',
    referenceLabel,
    'Ne le copie PAS verbatim. ETUDIE les patterns suivants et reproduis-les avec ton propre contenu adapte au sujet:',
    ...patternBullets,
    '',
    variant === 'brand_landing'
      ? 'NOTE BRAND: les couleurs, typo et accents du starter ci-dessous (violet/cyan/ambre, Inter) NE SONT PAS adaptes pour une page de marque. Utilise le starter pour les patterns techniques (CSS variables, scroll reveal, animations) mais REMPLACE la palette et la typo par celles dictees par le bloc VERROUILLAGE SUJET en amont.'
      : '',
    '',
    '```html',
    usedReference,
    '```',
    subjectBlock,
    '',
    'IMPORTANT (v82m7 — barre senior IC):',
    '- Le starter ci-dessus est le NIVEAU MINIMUM. Tu peux le DEPASSER, jamais le sous-dimensionner.',
    '- Reprends les TOKENS (oklch palette, easing, spacing, type system). Adapte les VALEURS au sujet.',
    '- Si tu mets un seul accent oklch et que tu dois ajouter une couleur dataviz, prends une 2e teinte cousine — JAMAIS un primary+secondary+tertiary scolaire.',
    '- Utilise au moins UNE phrase Instrument Serif italic dans un display (hero h1 .em, ou cta-final h2 .em). Le contraste serif italic / sans-serif est la signature 2025-2026.',
    '- Headline avec un fond accent skew-3deg (.em::before) sur le mot fort: c est ce qui differencie le tutoriel du senior.',
    '- Mosaique inegale obligatoire sur les features (pas une grille uniforme auto-fit).',
    '- Hover scale max 1.02. Magnetic max 6-8px. Jamais plus.',
    '- Dark mode par defaut + view-transitions sur le swap.',
    '- Si un mot du brief impose une autre teinte (Coca rouge, Tesla blanc, Stripe purple), remplace l accent oklch par la teinte BRANDEE — mais garde le reste du systeme.',
    variant ? `- Pour ce projet TYPE ${variant.toUpperCase()}: respecte aussi les SECTIONS SPECIFIQUES listees ci-dessus.` : '',
  ].filter(Boolean).join('\n')
}
