// ---------------------------------------------------------------------------
// codeStarterTemplates — squelettes HTML CONCRETS injectes dans le prompt du
// Codeur pour chaque archetype. Sans exemple concret, les LLM produisent du
// HTML scolaire ("<h1>Bienvenue chez X</h1>" + liste a puces). Avec un
// squelette starter, le LLM le COPIE et le PERSONNALISE — c est le mecanisme
// qui rapproche le rendu d un studio premium.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent.ts'
import type { DesignArchetype } from './codeDesignDirectives.ts'
import { detectDesignArchetype } from './codeDesignDirectives.ts'
import { buildStructuredEmissionInstructions } from './codeProjectEmission.ts'

const STARTER_INTRO = [
  '## STARTER TEMPLATE — REFERENCE STRUCTURELLE NIVEAU SENIOR IC (v82m7)',
  '',
  'Le squelette ci-dessous est le NIVEAU MINIMUM (Linear / Vercel / Arc / Stripe / Anthropic / Apple).',
  'Tu T INSPIRES de la STRUCTURE et du SYSTEME (tokens, easing, density, hierarchie typo). Tu ADAPTES TOUT au sujet:',
  '',
  '## REGLE D ADAPTATION VS DUPLICATION',
  '- INTERDIT: livrer le squelette avec juste les couleurs changees. C est une boite a outils, pas un calque.',
  '- Les SECTIONS, le VOCABULAIRE visuel, les ANIMATIONS doivent etre PROPRES au sujet:',
  '  - Boisson / soda / alcool: bouteille SVG rotation scroll, bulles qui montent, courbes liquide, gamme saveurs (pas de "hotspots anatomy").',
  '  - Tech / electronique / ecouteur: exploded view + hotspots, materials gallery, specs grid, comparison.',
  '  - Mode / vetements / sneakers: lookbook editorial, marquee mots-cles, color picker, fit guide.',
  '  - Sport / velo / outdoor: trail map SVG path animee, KOM segments, gear breakdown.',
  '  - Voyage / hotel: scroll cinematic carte, gallery destinations, booking widget.',
  '  - Food / restaurant: menu cards photos plats, chef story, signature dish hero.',
  '  - Voiture: hero scroll 360, configurateur couleurs, specs comparees, perf graphs.',
  '  - SaaS / tool: bento mosaic features, dashboard mockup interactif, pricing.',
  '  - Portfolio / agence: WebGL hero, marquee mots, project tiles hover distortion.',
  '',
  'BARRE SENIOR IC v82m7 — REGLES DURES:',
  '- Type system editorial: Inter Variable BODY + Instrument Serif italic DISPLAY + JetBrains Mono KICKER. Le contraste serif italic/sans-serif est la signature 2025-2026. PAS Roboto par defaut, PAS Times.',
  '- Color system: oklch palette restreinte. UN SEUL accent. Backgrounds oklch(0.13 0.012 252) ou oklch(0.985 0.005 80). PAS de #ff0000/red/blue, PAS de primary+secondary+tertiary scolaire.',
  '- Layout: grille 12-col explicite avec col-span asymetriques. Container queries (@container) en complement des media. Mosaique inegale obligatoire (large/medium/small mix), JAMAIS auto-fit uniforme.',
  '- Motion tokens: --ease-out-expo cubic-bezier(0.16,1,0.3,1), --ease-spring cubic-bezier(0.32,0.72,0,1). Durees 160/240/480ms. Hover scale 1.02 max. Magnetic 6-8px max.',
  '- Scroll-driven natif: @supports (animation-timeline: view()) avec fallback IntersectionObserver. View Transitions API (document.startViewTransition) sur dark/light.',
  '- Glass Apple/Linear: backdrop-filter blur(20px) saturate(180%) + inset 0 1px 0 rgba(255,255,255,0.06).',
  '- Display headline: au moins UN mot en Instrument Serif italic highlighted (h1 .em avec ::before en accent-soft skew-3deg). C est ce qui differencie tutoriel vs senior.',
  '- Stats editorialisees: chiffres en Instrument Serif italic + sup en JetBrains Mono accent.',
  '- Counter ease-out-expo (1-Math.pow(1-t,4)) + Number.toLocaleString.',
  '- Cursor follow subtil mix-blend difference.',
  '- Tu utilises les images PLACEHOLDER_IMG_HERO / DETAIL / LIFESTYLE1 / LIFESTYLE2 dans <img src="..."> — l orchestrateur les relie aux fichiers optimises du bundle inter-module.',
  '- Au moins 7-10 sections RICHES propres au sujet.',
  '- Au moins 2 animations 3D / scroll-driven (rotateY scroll, perspective + preserve-3d, mesh blob, scroll-timeline).',
  '',
  'ANTI-PATTERNS INTERDITS (font scolaire — output rejete):',
  '- margin-top: 10px isole (utilise gap), couleurs nommees CSS, hex flashy default.',
  '- Bouton border-radius 50px ET shadow scolaire (0 4px 6px rgba(0,0,0,0.1)) ensemble.',
  '- Gradient banal sky-to-purple, font-weight bold seul sans hierarchie.',
  '- 3 couleurs primary/secondary/tertiary qui se battent. Cards toutes meme taille uniforme.',
  '- <h1>Bienvenue</h1>, <ul><li> simple, fond plat unie, divs colores sans matiere.',
  '- box-shadow neon multi-couleurs Discord 2018, border-radius mixtes incoherents.',
  '- Animation 800ms+ sur un hover (lourd).',
  '',
  'ADAPTATION COULEURS BRAND: Coca = rouge profond + crème, Tesla = blanc + rouge sang, Apple = neutres warm + un bleu, Stripe = purple electrique. Mais GARDE le systeme tokens / easing / hierarchie typo intact.',
  '',
]

// ---------------------------------------------------------------------------
// Apple product — exploded view, hotspots, flip cards, scroll-driven anims
// ---------------------------------------------------------------------------

const APPLE_PRODUCT_STARTER = String.raw`<!doctype html>
<html lang="fr" data-archetype="apple_product">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{{TITLE}} — {{SUBJECT}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" crossorigin>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap">
<style>
:root{--bg:#06060a;--bg-soft:#0c0c12;--fg:#f5f5f7;--fg-soft:rgba(245,245,247,.72);--fg-mute:rgba(245,245,247,.45);--border:rgba(245,245,247,.07);--border-strong:rgba(245,245,247,.14);--accent:#7c3aed;--accent-2:#22d3ee;--accent-3:#ec4899;--accent-4:#f59e0b;--radius:18px;--easing:cubic-bezier(.22,1,.36,1);--spring:cubic-bezier(.34,1.56,.64,1);}
*{box-sizing:border-box}html,body{margin:0;padding:0}html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--fg);font-family:'Inter',system-ui,sans-serif;font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased;overflow-x:hidden}
.mesh{position:fixed;inset:0;z-index:0;overflow:hidden;pointer-events:none}
.mesh::before,.mesh::after,.mesh span{content:"";position:absolute;border-radius:50%;filter:blur(160px);opacity:.45;animation:meshFloat 22s var(--easing) infinite alternate}
.mesh::before{width:620px;height:620px;background:radial-gradient(circle,#7c3aed,transparent 60%);top:-160px;left:-100px}
.mesh::after{width:560px;height:560px;background:radial-gradient(circle,#22d3ee,transparent 60%);bottom:-200px;right:-120px;animation-delay:-11s}
.mesh span{display:block;width:480px;height:480px;background:radial-gradient(circle,#ec4899,transparent 60%);top:40%;left:55%;animation-delay:-6s;opacity:.32}
@keyframes meshFloat{0%{transform:translate3d(0,0,0) scale(1)}100%{transform:translate3d(80px,60px,0) scale(1.2)}}
.noise{position:fixed;inset:0;z-index:1;pointer-events:none;opacity:.05;mix-blend-mode:overlay;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><filter id='n'><feTurbulence baseFrequency='1.5' numOctaves='2' seed='2'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>")}
main{position:relative;z-index:2}
.wrap{max-width:1280px;margin:0 auto;padding-inline:clamp(1rem,4vw,3rem)}
.eyebrow{display:inline-block;text-transform:uppercase;letter-spacing:.18em;font-size:.78rem;color:var(--accent-2);font-weight:600;padding:.45rem .9rem;border:1px solid var(--border-strong);border-radius:999px;background:rgba(34,211,238,.06);backdrop-filter:blur(10px)}
.nav{position:fixed;top:0;left:0;right:0;z-index:10;transition:.4s var(--easing);padding-block:18px;background:transparent}
.nav.scrolled{background:rgba(6,6,10,.7);backdrop-filter:blur(18px) saturate(160%);padding-block:10px;border-bottom:1px solid var(--border)}
.nav-inner{display:flex;align-items:center;justify-content:space-between;gap:24px}
.logo{display:flex;align-items:center;gap:10px;font-family:'Space Grotesk';font-weight:700;letter-spacing:-.01em;font-size:1.05rem}
.logo svg{width:26px;height:26px}
.nav-links{display:none;gap:28px;font-size:.92rem;color:var(--fg-soft)}
.nav-links a{color:inherit;text-decoration:none;transition:color .2s;position:relative}
.nav-links a:hover{color:var(--fg)}
@media(min-width:880px){.nav-links{display:flex}}
.cta{display:inline-flex;align-items:center;gap:8px;padding:.7rem 1.2rem;border-radius:999px;font-weight:600;text-decoration:none;color:#08080b;background:#f5f5f7;transition:all .25s var(--easing);font-size:.9rem}
.cta:hover{transform:translateY(-1px);box-shadow:0 14px 40px rgba(245,245,247,.18)}
.cta--ghost{background:transparent;color:var(--fg);border:1px solid var(--border-strong)}
.hero{min-height:100vh;display:grid;place-items:center;padding-block:160px 100px}
.hero-inner{display:grid;gap:42px;align-items:center;text-align:center}
@media(min-width:1024px){.hero-inner{grid-template-columns:1fr 1.05fr;gap:64px;text-align:left}}
.hero h1{font-family:'Space Grotesk',sans-serif;font-size:clamp(3rem,8.4vw,7rem);font-weight:700;letter-spacing:-.04em;line-height:1.02;margin:18px 0 22px;background:linear-gradient(180deg,#f5f5f7 0%,rgba(245,245,247,.62) 110%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.hero p.sub{font-size:clamp(1.05rem,1.4vw,1.25rem);color:var(--fg-soft);max-width:520px;margin:0 0 32px}
.hero-actions{display:flex;gap:14px;flex-wrap:wrap}
.hero-visual{position:relative;aspect-ratio:1;max-width:560px;margin:0 auto;width:100%}
.hero-visual img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:50%;filter:drop-shadow(0 60px 80px rgba(124,58,237,.35)) drop-shadow(0 24px 60px rgba(34,211,238,.25))}
.float{animation:floaty 7s var(--easing) infinite alternate}
@keyframes floaty{0%{transform:translateY(-12px) rotate(-2deg)}100%{transform:translateY(12px) rotate(2deg)}}
.reveal{opacity:0;transform:translateY(34px);transition:opacity .8s var(--easing),transform .8s var(--easing)}
.reveal.in{opacity:1;transform:translateY(0)}
.reveal--stagger>*{opacity:0;transform:translateY(20px);transition:opacity .6s var(--easing),transform .6s var(--easing)}
.reveal--stagger.in>*{opacity:1;transform:translateY(0)}
.reveal--stagger.in>*:nth-child(1){transition-delay:.05s}
.reveal--stagger.in>*:nth-child(2){transition-delay:.12s}
.reveal--stagger.in>*:nth-child(3){transition-delay:.19s}
.reveal--stagger.in>*:nth-child(4){transition-delay:.26s}
.reveal--stagger.in>*:nth-child(5){transition-delay:.33s}
.reveal--stagger.in>*:nth-child(6){transition-delay:.40s}
@media(prefers-reduced-motion:reduce){.reveal,.reveal--stagger>*{opacity:1;transform:none;transition:none}.float,.mesh::before,.mesh::after,.mesh span{animation:none}}
section{padding-block:clamp(64px,10vw,140px)}
.section-head{max-width:760px;margin:0 auto 56px;text-align:center}
.section-head h2{font-family:'Space Grotesk';font-weight:700;letter-spacing:-.03em;line-height:1.05;font-size:clamp(2.1rem,4.5vw,3.5rem);margin:14px 0 16px}
.section-head p{color:var(--fg-soft);font-size:1.05rem}
.exploded-stage{position:relative;aspect-ratio:1.25;max-width:880px;margin:0 auto;display:grid;place-items:center;--p:0}
.exploded-stage svg{width:100%;height:auto}
.part{transition:transform .15s linear}
.part.p-cap{transform:translate3d(calc(var(--p) * -150px), calc(var(--p) * -120px), 0) rotate(calc(var(--p) * -16deg))}
.part.p-driver{transform:translate3d(calc(var(--p) * -50px), calc(var(--p) * 40px), 0)}
.part.p-shell{transform:translate3d(calc(var(--p) * 60px), calc(var(--p) * -10px), 0)}
.part.p-stem{transform:translate3d(calc(var(--p) * 150px), calc(var(--p) * 120px), 0) rotate(calc(var(--p) * 12deg))}
.part.p-tip{transform:translate3d(calc(var(--p) * -180px), calc(var(--p) * 150px), 0)}
.hotspot{position:absolute;width:32px;height:32px;border-radius:50%;border:2px solid var(--accent-2);background:rgba(34,211,238,.25);cursor:pointer;display:grid;place-items:center;transition:.3s var(--easing);z-index:3;box-shadow:0 0 30px rgba(34,211,238,.4)}
.hotspot::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--accent-2);box-shadow:0 0 0 0 rgba(34,211,238,.6);animation:ping 2.4s var(--easing) infinite}
@keyframes ping{0%{box-shadow:0 0 0 0 rgba(34,211,238,.55)}80%,100%{box-shadow:0 0 0 22px rgba(34,211,238,0)}}
.hotspot:hover{transform:scale(1.3)}
.hotspot-label{position:absolute;background:rgba(13,13,18,.96);backdrop-filter:blur(14px);border:1px solid var(--border-strong);border-radius:14px;padding:14px 16px;min-width:240px;font-size:.88rem;line-height:1.5;color:var(--fg-soft);box-shadow:0 28px 60px rgba(0,0,0,.55);opacity:0;transform:translateY(8px);pointer-events:none;transition:.25s var(--easing);z-index:5;max-width:280px}
.hotspot-label strong{display:block;color:var(--fg);margin-bottom:4px;font-weight:600}
.hotspot:hover + .hotspot-label{opacity:1;transform:translateY(0)}
.flip-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
.flip{position:relative;aspect-ratio:.92;perspective:1200px;cursor:pointer}
.flip-inner{position:relative;width:100%;height:100%;transform-style:preserve-3d;transition:transform .9s var(--spring)}
.flip:hover .flip-inner,.flip.flipped .flip-inner{transform:rotateY(180deg)}
.flip-face{position:absolute;inset:0;border-radius:var(--radius);overflow:hidden;backface-visibility:hidden;-webkit-backface-visibility:hidden;border:1px solid var(--border)}
.flip-front{display:flex;flex-direction:column;justify-content:flex-end;padding:18px;background:linear-gradient(180deg,rgba(0,0,0,0) 30%,rgba(0,0,0,.65) 100%)}
.flip-front img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:-1;transition:.6s var(--easing)}
.flip:hover .flip-front img{transform:scale(1.06)}
.flip-front .label{font-family:'Space Grotesk';font-size:.95rem;font-weight:600}
.flip-front .meta{font-size:.72rem;color:var(--fg-mute);text-transform:uppercase;letter-spacing:.12em;margin-top:4px}
.flip-back{transform:rotateY(180deg);background:linear-gradient(150deg,#101019 0%,#1c1c2e 100%);padding:22px 20px;display:flex;flex-direction:column;gap:10px;justify-content:space-between}
.flip-back h4{font-family:'Space Grotesk';font-size:1.05rem;font-weight:700;margin:0}
.flip-back .desc{font-size:.85rem;color:var(--fg-soft);line-height:1.55}
.flip-hint{position:absolute;top:10px;right:10px;background:rgba(124,58,237,.85);backdrop-filter:blur(8px);border-radius:999px;padding:6px 12px;font-size:.66rem;text-transform:uppercase;letter-spacing:.12em;color:#fff;font-weight:700;z-index:2;display:flex;align-items:center;gap:5px;animation:hintPulse 2.4s ease-in-out infinite}
@keyframes hintPulse{0%,100%{transform:scale(1);box-shadow:0 0 0 0 rgba(124,58,237,.7)}50%{transform:scale(1.08);box-shadow:0 0 0 12px rgba(124,58,237,0)}}
.eye{display:inline-block;width:14px;height:14px;border-radius:50%;border:1.5px solid currentColor;position:relative}
.eye::after{content:"";position:absolute;inset:3px;border-radius:50%;background:currentColor;transition:.3s}
.flip:hover .eye::after,.flip.flipped .eye::after{transform:translateX(3px)}
.gallery{display:grid;grid-template-columns:repeat(12,1fr);grid-auto-rows:140px;gap:12px}
.tile{position:relative;border-radius:var(--radius);overflow:hidden;border:1px solid var(--border);cursor:pointer;transition:.4s var(--easing)}
.tile img{width:100%;height:100%;object-fit:cover;transition:.6s var(--easing);display:block}
.tile:hover{transform:translateY(-4px) scale(1.01);box-shadow:0 30px 60px rgba(0,0,0,.4)}
.tile:hover img{transform:scale(1.08)}
.tile .caption{position:absolute;bottom:14px;left:16px;right:16px;color:var(--fg);font-family:'Space Grotesk';font-weight:600;text-shadow:0 2px 12px rgba(0,0,0,.6);opacity:0;transition:.3s var(--easing)}
.tile:hover .caption{opacity:1}
.tile.t1{grid-column:span 6;grid-row:span 3}.tile.t2{grid-column:span 6;grid-row:span 2}.tile.t3{grid-column:span 4;grid-row:span 2}.tile.t4{grid-column:span 4;grid-row:span 2}.tile.t5{grid-column:span 4;grid-row:span 2}.tile.t6{grid-column:span 12;grid-row:span 2}
@media(max-width:780px){.gallery{grid-template-columns:repeat(2,1fr);grid-auto-rows:160px;gap:10px}.tile.t1,.tile.t2,.tile.t3,.tile.t4,.tile.t5,.tile.t6{grid-column:span 2;grid-row:span 1}}
.specs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1px;background:var(--border);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
.spec{padding:32px 28px;background:var(--bg-soft)}
.spec h3{font-size:.84rem;text-transform:uppercase;letter-spacing:.14em;color:var(--accent-2);margin:0 0 8px;font-weight:600}
.spec .num{font-family:'Space Grotesk';font-size:clamp(2rem,4vw,2.6rem);font-weight:700;letter-spacing:-.03em;line-height:1.05;margin:0}
.spec .unit{font-size:.95rem;color:var(--fg-mute);margin-left:4px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px}
.kpi{padding:36px 30px;border:1px solid var(--border);border-radius:var(--radius);background:linear-gradient(180deg,rgba(245,245,247,.025),rgba(245,245,247,0));transition:.3s var(--easing)}
.kpi:hover{border-color:rgba(124,58,237,.3);transform:translateY(-4px)}
.kpi-value{font-family:'Space Grotesk';font-size:clamp(2.6rem,5vw,3.8rem);font-weight:700;letter-spacing:-.03em;background:linear-gradient(180deg,var(--accent),var(--accent-3));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;line-height:1.05}
.kpi-label{margin-top:6px;color:var(--fg-soft);font-size:.95rem}
.compare{position:relative;max-width:880px;margin:0 auto;border-radius:var(--radius);overflow:hidden;border:1px solid var(--border);aspect-ratio:16/9;cursor:ew-resize;user-select:none}
.compare-side{position:absolute;inset:0;background-size:cover}
.compare-side img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.side-b{clip-path:inset(0 50% 0 0)}
.compare-handle{position:absolute;top:0;bottom:0;left:50%;width:2px;background:rgba(245,245,247,.85);pointer-events:none;z-index:3}
.compare-handle::after{content:"⇆";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#fff;color:#08080b;width:46px;height:46px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:1.05rem;box-shadow:0 8px 22px rgba(0,0,0,.5)}
.testimonials{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}
.tcard{padding:30px 26px;background:linear-gradient(180deg,rgba(245,245,247,.03),rgba(245,245,247,0));border:1px solid var(--border);border-radius:var(--radius);transition:.3s var(--easing)}
.tcard:hover{border-color:rgba(34,211,238,.3);transform:translateY(-4px)}
.tcard .stars{color:var(--accent-4);font-size:1rem;letter-spacing:2px;margin-bottom:14px}
.tcard p{font-size:1.02rem;line-height:1.55;margin:0 0 18px;font-style:italic}
.tcard .who{display:flex;align-items:center;gap:12px}
.tcard .who img{width:40px;height:40px;border-radius:50%;object-fit:cover;border:2px solid var(--border)}
.cta-final{text-align:center;padding-block:90px;border-top:1px solid var(--border);border-bottom:1px solid var(--border);background:radial-gradient(ellipse at center top,rgba(124,58,237,.18),transparent 60%)}
footer{padding-block:60px 40px;color:var(--fg-mute);font-size:.88rem}
.footer-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:36px;margin-bottom:36px}
.footer-grid h4{color:var(--fg);font-size:.92rem;margin:0 0 14px;font-weight:600}
.footer-grid a{color:var(--fg-mute);text-decoration:none;display:block;padding:6px 0;transition:.2s}
.footer-grid a:hover{color:var(--fg)}
.scroll-bar{position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,var(--accent),var(--accent-2));z-index:100;width:0;transition:width .12s linear}
</style>
</head>
<body>
<div class="mesh"><span></span></div>
<div class="noise"></div>
<div class="scroll-bar" id="scrollBar"></div>
<nav class="nav" id="nav">
  <div class="wrap nav-inner">
    <div class="logo"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="url(#g1)" stroke-width="2" fill="none"/><circle cx="12" cy="12" r="4" fill="url(#g1)"/><defs><linearGradient id="g1" x1="0" x2="24" y1="0" y2="24"><stop offset="0" stop-color="#7c3aed"/><stop offset="1" stop-color="#22d3ee"/></linearGradient></defs></svg>{{BRAND}}</div>
    <div class="nav-links"><a href="#anatomy">{{NAV1}}</a><a href="#materials">{{NAV2}}</a><a href="#gallery">{{NAV3}}</a><a href="#specs">{{NAV4}}</a><a href="#testimonials">{{NAV5}}</a></div>
    <a class="cta" href="#cta-final">{{CTA_NAV}}</a>
  </div>
</nav>
<main>
  <section class="hero wrap">
    <div class="hero-inner">
      <div class="reveal">
        <span class="eyebrow">{{EYEBROW_HERO}}</span>
        <h1>{{HERO_TITLE_LINE1}}<br>{{HERO_TITLE_LINE2}}</h1>
        <p class="sub">{{HERO_SUB}}</p>
        <div class="hero-actions"><a class="cta" href="#cta-final">{{CTA_PRIMARY}}</a><a class="cta cta--ghost" href="#anatomy">{{CTA_SECONDARY}}</a></div>
      </div>
      <div class="hero-visual reveal"><div class="float"><img src="PLACEHOLDER_IMG_HERO" alt="{{SUBJECT}} hero"></div></div>
    </div>
  </section>
  <section id="anatomy" class="anatomy">
    <div class="wrap">
      <div class="section-head reveal"><span class="eyebrow">{{EYEBROW_ANATOMY}}</span><h2>{{ANATOMY_TITLE}}</h2><p>{{ANATOMY_DESC}}</p></div>
      <div class="exploded-stage reveal" id="stage">
        <svg viewBox="0 0 800 600">
          <defs>
            <radialGradient id="shellG" cx="50%" cy="40%" r="60%"><stop offset="0" stop-color="#fafafa"/><stop offset=".4" stop-color="#dadbe0"/><stop offset="1" stop-color="#86868b"/></radialGradient>
            <linearGradient id="stemG" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#f5f5f7"/><stop offset="1" stop-color="#86868b"/></linearGradient>
            <radialGradient id="tipG" cx="50%" cy="40%" r="60%"><stop offset="0" stop-color="#1a1a22"/><stop offset="1" stop-color="#0a0a10"/></radialGradient>
            <radialGradient id="driverG" cx="50%" cy="50%" r="60%"><stop offset="0" stop-color="#7c3aed"/><stop offset=".7" stop-color="#3b82f6"/><stop offset="1" stop-color="#22d3ee"/></radialGradient>
          </defs>
          <ellipse class="part p-cap" cx="220" cy="200" rx="62" ry="46" fill="url(#shellG)" opacity=".95"/>
          <circle class="part p-driver" cx="400" cy="300" r="80" fill="url(#driverG)" opacity=".95"/>
          <ellipse class="part p-shell" cx="510" cy="280" rx="155" ry="180" fill="url(#shellG)" opacity=".55"/>
          <path class="part p-stem" d="M460 440 Q480 500 470 580 L440 580 Q436 500 428 445 Z" fill="url(#stemG)"/>
          <ellipse class="part p-tip" cx="270" cy="450" rx="40" ry="48" fill="url(#tipG)"/>
        </svg>
        <div class="hotspot" style="top:18%;left:32%" tabindex="0" aria-label="{{HOT1_TITLE}}"></div>
        <div class="hotspot-label"><strong>{{HOT1_TITLE}}</strong>{{HOT1_DESC}}</div>
        <div class="hotspot" style="top:46%;left:48%" tabindex="0" aria-label="{{HOT2_TITLE}}"></div>
        <div class="hotspot-label"><strong>{{HOT2_TITLE}}</strong>{{HOT2_DESC}}</div>
        <div class="hotspot" style="top:30%;left:64%" tabindex="0" aria-label="{{HOT3_TITLE}}"></div>
        <div class="hotspot-label"><strong>{{HOT3_TITLE}}</strong>{{HOT3_DESC}}</div>
        <div class="hotspot" style="top:65%;left:60%" tabindex="0" aria-label="{{HOT4_TITLE}}"></div>
        <div class="hotspot-label"><strong>{{HOT4_TITLE}}</strong>{{HOT4_DESC}}</div>
        <div class="hotspot" style="top:62%;left:36%" tabindex="0" aria-label="{{HOT5_TITLE}}"></div>
        <div class="hotspot-label"><strong>{{HOT5_TITLE}}</strong>{{HOT5_DESC}}</div>
      </div>
    </div>
  </section>
  <section id="materials">
    <div class="wrap">
      <div class="section-head reveal"><span class="eyebrow">{{EYEBROW_MATERIALS}}</span><h2>{{MATERIALS_TITLE}}</h2><p>{{MATERIALS_DESC}}</p></div>
      <div class="flip-grid reveal reveal--stagger">
        <div class="flip" tabindex="0"><span class="flip-hint"><span class="eye"></span>Retourne</span><div class="flip-inner"><div class="flip-face flip-front"><img src="PLACEHOLDER_IMG_DETAIL" alt="{{MAT1_TITLE}}"><span class="label">{{MAT1_TITLE}}</span><span class="meta">{{MAT1_META}}</span></div><div class="flip-face flip-back"><h4>{{MAT1_TITLE}}</h4><p class="desc">{{MAT1_DESC}}</p></div></div></div>
        <div class="flip" tabindex="0"><span class="flip-hint"><span class="eye"></span>Retourne</span><div class="flip-inner"><div class="flip-face flip-front"><img src="PLACEHOLDER_IMG_DETAIL" alt="{{MAT2_TITLE}}"><span class="label">{{MAT2_TITLE}}</span><span class="meta">{{MAT2_META}}</span></div><div class="flip-face flip-back"><h4>{{MAT2_TITLE}}</h4><p class="desc">{{MAT2_DESC}}</p></div></div></div>
        <div class="flip" tabindex="0"><span class="flip-hint"><span class="eye"></span>Retourne</span><div class="flip-inner"><div class="flip-face flip-front"><img src="PLACEHOLDER_IMG_DETAIL" alt="{{MAT3_TITLE}}"><span class="label">{{MAT3_TITLE}}</span><span class="meta">{{MAT3_META}}</span></div><div class="flip-face flip-back"><h4>{{MAT3_TITLE}}</h4><p class="desc">{{MAT3_DESC}}</p></div></div></div>
        <div class="flip" tabindex="0"><span class="flip-hint"><span class="eye"></span>Retourne</span><div class="flip-inner"><div class="flip-face flip-front"><img src="PLACEHOLDER_IMG_DETAIL" alt="{{MAT4_TITLE}}"><span class="label">{{MAT4_TITLE}}</span><span class="meta">{{MAT4_META}}</span></div><div class="flip-face flip-back"><h4>{{MAT4_TITLE}}</h4><p class="desc">{{MAT4_DESC}}</p></div></div></div>
        <div class="flip" tabindex="0"><span class="flip-hint"><span class="eye"></span>Retourne</span><div class="flip-inner"><div class="flip-face flip-front"><img src="PLACEHOLDER_IMG_DETAIL" alt="{{MAT5_TITLE}}"><span class="label">{{MAT5_TITLE}}</span><span class="meta">{{MAT5_META}}</span></div><div class="flip-face flip-back"><h4>{{MAT5_TITLE}}</h4><p class="desc">{{MAT5_DESC}}</p></div></div></div>
        <div class="flip" tabindex="0"><span class="flip-hint"><span class="eye"></span>Retourne</span><div class="flip-inner"><div class="flip-face flip-front"><img src="PLACEHOLDER_IMG_DETAIL" alt="{{MAT6_TITLE}}"><span class="label">{{MAT6_TITLE}}</span><span class="meta">{{MAT6_META}}</span></div><div class="flip-face flip-back"><h4>{{MAT6_TITLE}}</h4><p class="desc">{{MAT6_DESC}}</p></div></div></div>
      </div>
    </div>
  </section>
  <section id="gallery">
    <div class="wrap">
      <div class="section-head reveal"><span class="eyebrow">{{EYEBROW_GALLERY}}</span><h2>{{GALLERY_TITLE}}</h2><p>{{GALLERY_DESC}}</p></div>
      <div class="gallery reveal reveal--stagger">
        <div class="tile t1"><img src="PLACEHOLDER_IMG_LIFESTYLE1" alt=""><span class="caption">{{GALLERY_CAP1}}</span></div>
        <div class="tile t2"><img src="PLACEHOLDER_IMG_LIFESTYLE2" alt=""><span class="caption">{{GALLERY_CAP2}}</span></div>
        <div class="tile t3"><img src="PLACEHOLDER_IMG_DETAIL" alt=""><span class="caption">{{GALLERY_CAP3}}</span></div>
        <div class="tile t4"><img src="PLACEHOLDER_IMG_HERO" alt=""><span class="caption">{{GALLERY_CAP4}}</span></div>
        <div class="tile t5"><img src="PLACEHOLDER_IMG_LIFESTYLE1" alt=""><span class="caption">{{GALLERY_CAP5}}</span></div>
        <div class="tile t6"><img src="PLACEHOLDER_IMG_LIFESTYLE2" alt=""><span class="caption">{{GALLERY_CAP6}}</span></div>
      </div>
    </div>
  </section>
  <section id="specs">
    <div class="wrap">
      <div class="section-head reveal"><span class="eyebrow">{{EYEBROW_SPECS}}</span><h2>{{SPECS_TITLE}}</h2></div>
      <div class="specs reveal reveal--stagger">
        <div class="spec"><h3>{{SPEC1_LABEL}}</h3><p class="num">{{SPEC1_VALUE}}<span class="unit">{{SPEC1_UNIT}}</span></p><p>{{SPEC1_NOTE}}</p></div>
        <div class="spec"><h3>{{SPEC2_LABEL}}</h3><p class="num">{{SPEC2_VALUE}}<span class="unit">{{SPEC2_UNIT}}</span></p><p>{{SPEC2_NOTE}}</p></div>
        <div class="spec"><h3>{{SPEC3_LABEL}}</h3><p class="num">{{SPEC3_VALUE}}<span class="unit">{{SPEC3_UNIT}}</span></p><p>{{SPEC3_NOTE}}</p></div>
        <div class="spec"><h3>{{SPEC4_LABEL}}</h3><p class="num">{{SPEC4_VALUE}}<span class="unit">{{SPEC4_UNIT}}</span></p><p>{{SPEC4_NOTE}}</p></div>
        <div class="spec"><h3>{{SPEC5_LABEL}}</h3><p class="num">{{SPEC5_VALUE}}<span class="unit">{{SPEC5_UNIT}}</span></p><p>{{SPEC5_NOTE}}</p></div>
        <div class="spec"><h3>{{SPEC6_LABEL}}</h3><p class="num">{{SPEC6_VALUE}}<span class="unit">{{SPEC6_UNIT}}</span></p><p>{{SPEC6_NOTE}}</p></div>
      </div>
    </div>
  </section>
  <section id="kpis">
    <div class="wrap">
      <div class="section-head reveal"><span class="eyebrow">{{EYEBROW_KPIS}}</span><h2>{{KPIS_TITLE}}</h2></div>
      <div class="kpis reveal" id="kpisRow">
        <div class="kpi"><div class="kpi-value" data-target="{{KPI1_VALUE}}" data-suffix="{{KPI1_UNIT}}">0</div><div class="kpi-label">{{KPI1_LABEL}}</div></div>
        <div class="kpi"><div class="kpi-value" data-target="{{KPI2_VALUE}}" data-suffix="{{KPI2_UNIT}}" data-decimals="2">0</div><div class="kpi-label">{{KPI2_LABEL}}</div></div>
        <div class="kpi"><div class="kpi-value" data-target="{{KPI3_VALUE}}" data-suffix="{{KPI3_UNIT}}">0</div><div class="kpi-label">{{KPI3_LABEL}}</div></div>
        <div class="kpi"><div class="kpi-value" data-target="{{KPI4_VALUE}}" data-suffix="{{KPI4_UNIT}}">0</div><div class="kpi-label">{{KPI4_LABEL}}</div></div>
      </div>
    </div>
  </section>
  <section id="compare">
    <div class="wrap">
      <div class="section-head reveal"><span class="eyebrow">{{EYEBROW_COMPARE}}</span><h2>{{COMPARE_TITLE}}</h2><p>{{COMPARE_DESC}}</p></div>
      <div class="compare reveal" id="compare">
        <div class="compare-side side-a"><img src="PLACEHOLDER_IMG_HERO" alt=""></div>
        <div class="compare-side side-b" id="cb"><img src="PLACEHOLDER_IMG_LIFESTYLE2" alt=""></div>
        <div class="compare-handle" id="ch"></div>
      </div>
    </div>
  </section>
  <section id="testimonials">
    <div class="wrap">
      <div class="section-head reveal"><span class="eyebrow">{{EYEBROW_TESTI}}</span><h2>{{TESTI_TITLE}}</h2></div>
      <div class="testimonials reveal reveal--stagger">
        <div class="tcard"><div class="stars">★★★★★</div><p>"{{TESTI1}}"</p></div>
        <div class="tcard"><div class="stars">★★★★★</div><p>"{{TESTI2}}"</p></div>
        <div class="tcard"><div class="stars">★★★★★</div><p>"{{TESTI3}}"</p></div>
      </div>
    </div>
  </section>
  <section id="cta-final" class="cta-final"><div class="wrap reveal"><span class="eyebrow">{{EYEBROW_CTA_FINAL}}</span><h2 style="font-family:'Space Grotesk';font-size:clamp(2.4rem,5.5vw,4.4rem);font-weight:700;letter-spacing:-.03em;margin:18px auto 22px;max-width:780px">{{CTA_FINAL_TITLE}}</h2><p style="color:var(--fg-soft);max-width:520px;margin:0 auto 28px">{{CTA_FINAL_DESC}}</p><a class="cta" href="#" style="padding:1rem 1.6rem;font-size:1rem">{{CTA_FINAL_BUTTON}}</a></div></section>
  <footer><div class="wrap"><div class="footer-grid"><div><h4>{{BRAND}}</h4><a href="#">{{FOOT1A}}</a><a href="#">{{FOOT1B}}</a></div><div><h4>{{FOOT_COL2}}</h4><a href="#">{{FOOT2A}}</a><a href="#">{{FOOT2B}}</a></div><div><h4>{{FOOT_COL3}}</h4><a href="#">{{FOOT3A}}</a><a href="#">{{FOOT3B}}</a></div></div></div></footer>
</main>
<script>
const bar=document.getElementById('scrollBar');function updateBar(){const max=document.documentElement.scrollHeight-innerHeight;bar.style.width=Math.min(100,(scrollY/max)*100)+'%'}addEventListener('scroll',updateBar,{passive:true});updateBar();
const io=new IntersectionObserver((entries)=>{for(const e of entries)if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}},{threshold:.15});document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
const nav=document.getElementById('nav');addEventListener('scroll',()=>{nav.classList.toggle('scrolled',scrollY>40)},{passive:true});
const stage=document.getElementById('stage');function updateExploded(){if(!stage)return;const r=stage.getBoundingClientRect();const vh=innerHeight;const start=vh*0.95;const end=-r.height*0.4;const raw=(start-r.top)/(start-end);const p=Math.max(0,Math.min(1,raw));stage.style.setProperty('--p',p.toFixed(3))}addEventListener('scroll',updateExploded,{passive:true});addEventListener('resize',updateExploded);updateExploded();
const kpiSection=document.getElementById('kpisRow');const counterObs=new IntersectionObserver((entries)=>{for(const e of entries){if(!e.isIntersecting)continue;counterObs.disconnect();e.target.querySelectorAll('.kpi-value').forEach(el=>{const target=parseFloat(el.dataset.target||'0');const suffix=el.dataset.suffix||'';const decimals=parseInt(el.dataset.decimals||'0',10);const start=performance.now();const dur=1600;const tick=(t)=>{const p=Math.min((t-start)/dur,1);const eased=1-Math.pow(1-p,3);const v=(target*eased).toFixed(decimals);el.textContent=v+suffix;if(p<1)requestAnimationFrame(tick)};requestAnimationFrame(tick)})}},{threshold:.4});if(kpiSection)counterObs.observe(kpiSection);
const cmp=document.getElementById('compare');const cb=document.getElementById('cb');const ch=document.getElementById('ch');if(cmp&&cb&&ch){let drag=false;const setSplit=(r)=>{r=Math.max(.05,Math.min(.95,r));cb.style.clipPath=\`inset(0 \${(1-r)*100}% 0 0)\`;ch.style.left=(r*100)+'%'};cmp.addEventListener('pointerdown',(e)=>{drag=true;cmp.setPointerCapture(e.pointerId)});cmp.addEventListener('pointermove',(e)=>{if(!drag)return;setSplit(e.offsetX/cmp.clientWidth)});cmp.addEventListener('pointerup',(e)=>{drag=false;cmp.releasePointerCapture(e.pointerId)});setSplit(.5)}
document.querySelectorAll('.flip').forEach(card=>{card.addEventListener('click',()=>{card.classList.toggle('flipped')});card.addEventListener('keydown',(e)=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();card.classList.toggle('flipped')}})});
</script>
</body>
</html>`

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function getStarterTemplateForArchetype(archetype: DesignArchetype): string | null {
  switch (archetype) {
    case 'apple_product':
      return APPLE_PRODUCT_STARTER
    // Other archetypes fall back to the directives-only mode for now.
    default:
      return null
  }
}

/**
 * Build the starter template block injected in the system prompt of the
 * Codeur. Returns an empty string when the archetype has no template.
 */
export function buildStarterTemplateBlock(prompt: string, intent: CodeIntent): string {
  const archetype = detectDesignArchetype(prompt, intent)
  const tpl = getStarterTemplateForArchetype(archetype)
  if (!tpl) return ''

  // Trim safety: starter templates are large. We accept the cost on the
  // generation pass — llama4:scout (10M ctx) and qwen3-coder (32k+) both
  // handle this comfortably. The TEMPLATE block is what guarantees the
  // output stays at studio level.
  return [
    ...STARTER_INTRO,
    `<<<STARTER_TEMPLATE_${archetype.toUpperCase()}>>>`,
    tpl,
    '<<<END_STARTER_TEMPLATE>>>',
    '',
    'Substitution obligatoire des placeholders {{XXX}}:',
    '- {{TITLE}} = un titre court qui capte le sujet (ex: "Echo Pro" pour des ecouteurs).',
    '- {{SUBJECT}} = nom precis du sujet ("Coca-Cola Original Taste", "iPhone 16 Pro", etc.).',
    '- {{BRAND}} = nom de la marque (ex: "Coca-Cola", "AuroraSound", "Apple").',
    '- {{HERO_TITLE_LINE1}} / {{HERO_TITLE_LINE2}} = un slogan en deux lignes courtes et fortes.',
    '- {{HERO_SUB}} = sous-titre 2-3 phrases pas plus.',
    '- {{EYEBROW_*}} = mots tres courts uppercase (ex: "Anatomie", "Materiaux", "Performance").',
    '- {{HOT1_TITLE}} - {{HOT5_TITLE}} = noms des composants pertinents pour le sujet.',
    '- {{HOT1_DESC}} - {{HOT5_DESC}} = descriptions techniques courtes (1 phrase).',
    '- {{MAT1_TITLE}} - {{MAT6_TITLE}} = noms des variantes / finitions / saveurs / couleurs.',
    '- {{SPEC1_VALUE}} - {{SPEC6_VALUE}} = valeurs numeriques precises.',
    '- {{KPI1_VALUE}} - {{KPI4_VALUE}} = nombres pour les compteurs animes.',
    '- {{TESTI1}} - {{TESTI3}} = avis clients courts et credibles.',
    '- {{NAV1}} - {{NAV5}} = labels du menu nav (en lien avec les sections).',
    '',
    'Si tu ne respectes pas la STRUCTURE du squelette, le pipeline rejettera la livraison.',
    'Les images sont DEJA generees: utilise PLACEHOLDER_IMG_HERO, PLACEHOLDER_IMG_DETAIL, PLACEHOLDER_IMG_LIFESTYLE1, PLACEHOLDER_IMG_LIFESTYLE2 telles quelles dans <img src="...">.',
    '',
    'OUTPUT obligatoire (1 SEUL fichier index.html):',
    buildStructuredEmissionInstructions(),
    'Le seul fichier emis doit avoir path="index.html", language="html", encoding="utf8" et contenir le HTML complet personnalise dans les {{slots}}, en gardant 100% de la structure et du JS du squelette.',
  ].join('\n')
}
