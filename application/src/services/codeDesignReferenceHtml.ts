/** Premium HTML reference used as design-level exemplar. */

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
