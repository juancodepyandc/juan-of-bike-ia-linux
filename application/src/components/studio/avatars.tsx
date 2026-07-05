// @ts-nocheck
// Studio avatar system — ported from v10 design.
// Auto-injects 40 keyframes (a10-*) on first import.
// Public API: Avatar, AvatarMini, FightCloud, Onomatopee, P (persona data), mixColor.
import React from 'react';

// v10/avatars.jsx — Aurora V10 portrait anatomies
// 7 personae × 35+ face SVG elements + 25+ body elements
// 40+ CSS keyframes applying 12 Pixar principles
// Public API exposed on window: Avatar, AvatarMini, P, FightCloud, Onomatopee
  // ─────────────────────────────────────────────────────────
  //  KEYFRAMES — 40+ animations, all eased with cubic-bezier
  // ─────────────────────────────────────────────────────────
  const KEYFRAMES = `
  /* ── Pixar principle 1: Squash & Stretch ──
     Lid sits OPEN (squashed flat) most of the cycle and briefly closes
     for the blink. v82s fix: original keyframes had the open/closed states
     inverted, leaving the eyes covered by skin-coloured lid 93 % of the
     time which read as "asleep" in the rendered roster. */
  @keyframes a10-blink-squash {
    0%,93%,100% { transform: scaleY(0.06); }
    95% { transform: scaleY(1); }
    97% { transform: scaleY(0.7); }
    99% { transform: scaleY(0.06); }
  }
  /* ── Principle 2: Anticipation ── */
  @keyframes a10-cloud-shake {
    0%,82%,100% { transform: translate(0,0) rotate(0deg); }
    85% { transform: translate(-2px,-1px) rotate(-1deg); }
    88% { transform: translate(2px,1px) rotate(1deg); }
    91% { transform: translate(-1px,2px) rotate(-.5deg); }
    94% { transform: translate(0,0) rotate(0deg); }
  }
  /* ── Principle 5: Follow-through ── */
  @keyframes a10-hair-follow {
    0%,100% { transform: translateX(0) rotate(0deg); }
    35% { transform: translateX(-1.5px) rotate(-.6deg); }
    65% { transform: translateX(1.5px) rotate(.6deg); }
  }
  @keyframes a10-scarf-wave {
    0%,100% { transform: translateY(0) rotate(0deg); }
    25% { transform: translateY(-1px) rotate(-2deg); }
    50% { transform: translateY(2px) rotate(0deg); }
    75% { transform: translateY(-1.5px) rotate(2deg); }
  }
  /* ── Breathing pose-to-pose ── */
  @keyframes a10-breath {
    0%,100% { transform: translate(0,0); }
    25% { transform: translate(.5px,-1.5px); }
    50% { transform: translate(0,-2.2px); }
    75% { transform: translate(-.4px,-1.2px); }
  }
  @keyframes a10-head-turn {
    0%,100% { transform: rotate(0deg) translateX(0); }
    25% { transform: rotate(-3deg) translateX(-1px); }
    50% { transform: rotate(0deg) translateX(0); }
    75% { transform: rotate(4deg) translateX(1px); }
  }
  @keyframes a10-saccade {
    0%,40%,80%,100% { transform: translate(0,0); }
    20% { transform: translate(1.4px,-.4px); }
    60% { transform: translate(-1.2px,.4px); }
  }
  @keyframes a10-weight-shift {
    0%,100% { transform: translateX(0); }
    50% { transform: translateX(2.2px); }
  }
  /* ── Gesture loops ── */
  @keyframes a10-finger-tap {
    0%,100% { transform: translateY(0); }
    20% { transform: translateY(-3px); } /* anticipation lift */
    35% { transform: translateY(1.5px); } /* impact */
    55% { transform: translateY(0); }
  }
  @keyframes a10-brush-arc {
    0%,100% { transform: rotate(-12deg) translate(0,0); }
    25% { transform: rotate(-2deg) translate(3px,-2px); }
    50% { transform: rotate(8deg) translate(7px,-1px); }
    75% { transform: rotate(2deg) translate(3px,2px); }
  }
  @keyframes a10-page-flip {
    0%,80%,100% { transform: rotateY(0); }
    40% { transform: rotateY(-78deg); }
    60% { transform: rotateY(-78deg); }
  }
  @keyframes a10-glasses-slide {
    0%,100% { transform: translateY(0); }
    40% { transform: translateY(.8px); }
    70% { transform: translateY(.4px); }
  }
  @keyframes a10-pen-trace {
    0%,100% { transform: translate(0,0); }
    33% { transform: translate(7px,2px); }
    66% { transform: translate(3px,5px); }
  }
  @keyframes a10-nod {
    0%,100% { transform: translateY(0) rotate(0deg); }
    40% { transform: translateY(2px) rotate(2deg); }
    70% { transform: translateY(-1px) rotate(-1deg); }
  }
  @keyframes a10-mic-bob {
    0%,100% { transform: translate(0,0); }
    50% { transform: translate(0,-2px); }
  }
  @keyframes a10-walk-L { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-3px)} }
  @keyframes a10-walk-R { 0%,50%,100%{transform:translateY(0)} 25%{transform:translateY(-3px)} }
  /* ── Mouth viseme states ── */
  @keyframes a10-mouth-speak {
    0%,100% { transform: scale(1,1); }
    20% { transform: scale(.7,1.6); } /* O */
    40% { transform: scale(1.3,.7); } /* A */
    60% { transform: scale(.9,.9); } /* E */
    80% { transform: scale(1.15,.5); } /* I */
  }
  /* ── Brow secondary motion (pixar 8) ── */
  @keyframes a10-brow-furrow {
    0%,100% { transform: translateY(0) rotate(0deg); }
    50% { transform: translateY(1.5px) rotate(-3deg); }
  }
  @keyframes a10-brow-raise {
    0%,100% { transform: translateY(0); }
    50% { transform: translateY(-2px); }
  }
  @keyframes a10-cheek-flush {
    0%,100% { opacity: .35; }
    50% { opacity: .68; }
  }
  /* ── Tongue tip out (Mira concentration) ── */
  @keyframes a10-tongue-peek {
    0%,80%,100% { transform: translate(0,0); opacity:0; }
    40%,60% { transform: translate(2px,1px); opacity:1; }
  }
  /* ── Eye widen (Lou surprise on fail) ── */
  @keyframes a10-eye-widen {
    0%,90%,100% { transform: scale(1); }
    35% { transform: scale(1.32,1.28); }
    55% { transform: scale(1.18,1.18); }
  }
  /* ── Holo & hover ── */
  @keyframes a10-holo-pulse {
    0%,100% { transform: scale(1); opacity:.78; }
    50% { transform: scale(1.18); opacity:1; }
  }
  /* ── FightCloud limb-poke (exaggerated, principle 10) ── */
  @keyframes a10-limb-out {
    0% { transform: translate(0,0) rotate(0deg) scale(.4); opacity:0; }
    18% { transform: translate(var(--lx,0),var(--ly,0)) rotate(var(--lr,0deg)) scale(1.32); opacity:1; }
    52% { transform: translate(calc(var(--lx,0) * 1.05), calc(var(--ly,0) * 1.05)) rotate(var(--lr,0deg)) scale(1.18); opacity:1; }
    78% { transform: translate(calc(var(--lx,0) * .92), calc(var(--ly,0) * .92)) rotate(var(--lr,0deg)) scale(1.05); opacity:.92; }
    100% { transform: translate(0,0) rotate(0deg) scale(.4); opacity:0; }
  }
  @keyframes a10-spark {
    0% { transform: scale(0); opacity:0; }
    20% { transform: scale(1.4); opacity:1; }
    100% { transform: scale(0) translate(var(--sx,0),var(--sy,0)); opacity:0; }
  }
  @keyframes a10-smoke-rise {
    0% { transform: translateY(0) scale(.6); opacity:0; }
    30% { opacity:.6; }
    100% { transform: translateY(-46px) scale(1.6); opacity:0; }
  }
  @keyframes a10-onomatopee {
    0% { transform: scale(.2) rotate(-12deg); opacity:0; }
    18% { transform: scale(1.4) rotate(-6deg); opacity:1; }
    34% { transform: scale(1) rotate(-3deg); opacity:1; }
    78% { transform: scale(1.04) rotate(-3deg); opacity:1; }
    100% { transform: scale(.6) rotate(0deg); opacity:0; }
  }
  /* ── UI behaviour ── */
  @keyframes a10-caret-blink { 0%,49%,100%{opacity:1} 50%,99%{opacity:0} }
  @keyframes a10-progress-fill {
    0%,18%{width:0%}
    72%{width:87%}
    88%,100%{width:0%}
  }
  @keyframes a10-cursor-pulse { 0%,100%{transform:scale(1);opacity:.8} 50%{transform:scale(1.18);opacity:1} }
  @keyframes a10-radar-sweep { 0%{transform:rotate(0)} 100%{transform:rotate(360deg)} }
  @keyframes a10-anki-flip { 0%,40%{transform:rotateY(0)} 60%,100%{transform:rotateY(180deg)} }
  @keyframes a10-shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
  @keyframes a10-pulse-dot { 0%,100%{transform:scale(1);opacity:1} 50%{transform:scale(1.4);opacity:.5} }
  @keyframes a10-formant {
    0%,100% { transform: scaleY(.4); }
    50% { transform: scaleY(1); }
  }
  @keyframes a10-tree-grow {
    0%{transform:scale(0);opacity:0}
    100%{transform:scale(1);opacity:1}
  }
  @keyframes a10-stroke-draw {
    0%{stroke-dashoffset:300}
    100%{stroke-dashoffset:0}
  }
  @keyframes a10-fade-in { 0%{opacity:0} 100%{opacity:1} }
  @keyframes a10-flash {
    0%,100% { opacity:0; }
    8% { opacity:.85; }
    20% { opacity:0; }
  }
  `;

  // ─────────────────────────────────────────────────────────
  //  PERSONA DATA — 7 distinct skin tones + hair + clothing
  // ─────────────────────────────────────────────────────────
  const P = {
    sage:  { name: 'Sage',  role: 'Orchestrator',
             skin: '#c79570', skinHL: '#e3b48f', skinSh: '#8e5e44', skinDeep: '#5e3c2a',
             hair: '#b8b0a8', hairDark: '#7a7268', hairHL: '#e6dfd7',
             brow: '#8a7a6e', eye: '#5a4530', lip: '#a35f4e', lipSh: '#7a3f30',
             cheek: '#d68a72',
             pomme: false, glasses: false, gender:'f',
             cloth: 'sage-coat',
             clothBase:'#c89a6a', clothShade:'#8b6a44', clothHL:'#e2bb8e', clothAccent:'#8b1f2d',
             accent:'#8b1f2d',
             delaySeed: 0.31,
             gesture: 'orchestrate' },
    lou:   { name: 'Lou',   role: 'Code',
             skin: '#f5d8b8', skinHL: '#fde8d0', skinSh: '#c89870', skinDeep: '#9a6840',
             hair: '#8b5a2a', hairDark: '#5a3a18', hairHL: '#c89060',
             brow: '#5e3b18', eye: '#3a2a16', lip: '#b87060', lipSh: '#8a4a3a',
             cheek: '#f0a890',
             pomme: true, glasses: false, gender:'m',
             cloth: 'lou-hoodie',
             clothBase:'#1e3a5f', clothShade:'#0f1f3a', clothHL:'#3a5a85', clothAccent:'#ffffff',
             accent:'#3a86ff',
             delaySeed: 0.83,
             gesture: 'typing' },
    mira:  { name: 'Mira',  role: 'Image',
             skin: '#c9a075', skinHL: '#e6c498', skinSh: '#8c6644', skinDeep: '#5e4228',
             hair: '#c8521e', hairDark: '#8a3410', hairHL: '#f08a4a',
             brow: '#7a3010', eye: '#4a2810', lip: '#b34530', lipSh: '#7a2a1c',
             cheek: '#e89878',
             pomme: false, glasses: false, gender:'f',
             cloth: 'mira-apron',
             clothBase:'#a89888', clothShade:'#6e6258', clothHL:'#c8b8a8', clothAccent:'#ffd040',
             accent:'#e85d2a',
             delaySeed: 1.27,
             gesture: 'painting' },
    diego: { name: 'Diego', role: 'Voice',
             skin: '#a87854', skinHL: '#c89878', skinSh: '#7a523a', skinDeep: '#4a2e1c',
             hair: '#1a1410', hairDark: '#000000', hairHL: '#3e342a',
             brow: '#0a0808', eye: '#1a0e08', lip: '#9a4838', lipSh: '#6a2a20',
             cheek: '#c87a5e',
             pomme: true, glasses: false, gender:'m',
             cloth: 'diego-hoodie',
             clothBase:'#722f2f', clothShade:'#4a1c1c', clothHL:'#9a4040', clothAccent:'#cccccc',
             accent:'#c8a060',
             delaySeed: 1.71,
             gesture: 'speaking' },
    tess:  { name: 'Tess',  role: 'Lead',
             skin: '#e8c0a0', skinHL: '#f6dcc0', skinSh: '#b88a68', skinDeep: '#80583a',
             hair: '#c8b896', hairDark: '#8a7a5a', hairHL: '#e8dcc0',
             brow: '#8a7a5a', eye: '#3e5a4a', lip: '#c0604e', lipSh: '#8a3e30',
             cheek: '#ec9c80',
             pomme: false, glasses: true, gender:'f',
             cloth: 'tess-blazer',
             clothBase:'#1a1a1a', clothShade:'#000000', clothHL:'#3a3a3a', clothAccent:'#f0e4d0',
             accent:'#3a86ff',
             delaySeed: 2.13,
             gesture: 'pointing' },
    sam:   { name: 'Sam',   role: 'Academy',
             skin: '#8a5b3a', skinHL: '#a8784e', skinSh: '#5e3c20', skinDeep: '#3a2410',
             hair: '#4a2a16', hairDark: '#2a1408', hairHL: '#7a4a28',
             brow: '#2a1408', eye: '#2a1606', lip: '#8a4030', lipSh: '#5a221a',
             cheek: '#a86848',
             pomme: false, glasses: true, gender:'m',
             cloth: 'sam-knit',
             clothBase:'#c9b08a', clothShade:'#8a7858', clothHL:'#e0cfa8', clothAccent:'#5a4838',
             accent:'#5a4838',
             delaySeed: 2.57,
             gesture: 'reading' },
    yann:  { name: 'Yann',  role: 'Cyber',
             skin: '#ecc4a0', skinHL: '#f8dec0', skinSh: '#b08868', skinDeep: '#7a5638',
             hair: '#1a1828', hairDark: '#080812', hairHL: '#3a3850',
             brow: '#080812', eye: '#1a2030', lip: '#a85848', lipSh: '#6a322a',
             cheek: '#eea088',
             pomme: true, glasses: false, gender:'m',
             cloth: 'yann-shirt',
             clothBase:'#a8c8e8', clothShade:'#7898b8', clothHL:'#d0e0f0', clothAccent:'#3a4a5a',
             accent:'#20a878',
             delaySeed: 2.97,
             gesture: 'whiteboard' },
  };

  // Helper: deterministic pseudo-jitter from delaySeed
  const jit = (seed, k) => ((seed * 7919 * k) % 1) * 0.7 - 0.35;

  // ─────────────────────────────────────────────────────────
  //  HAIR STRAND GENERATOR — distinct fringe per persona
  // ─────────────────────────────────────────────────────────
  function makeHair(persona) {
    const p = P[persona];
    // 12-18 strands; each strand is a 4-6 point path covering forehead and temples.
    // We curate 4 silhouettes hand-tuned per persona to vary the look.
    const styles = {
      sage: { // silver bob, side-parted, soft fringe
        back: 'M 60 78 Q 35 110 50 188 Q 60 220 92 222 L 148 222 Q 180 220 190 188 Q 205 110 180 78 Q 165 60 120 56 Q 75 60 60 78 Z',
        strands: [
          'M 78 78 Q 86 64 110 60 Q 122 58 132 64 Q 122 70 102 76 Q 86 82 78 78 Z',
          'M 92 70 Q 108 56 132 58 Q 148 64 138 74 Q 122 76 110 78 Q 98 78 92 70 Z',
          'M 70 86 Q 64 100 70 122 Q 76 106 80 94 Q 76 88 70 86 Z',
          'M 168 86 Q 174 100 170 124 Q 162 108 158 96 Q 162 88 168 86 Z',
          'M 138 60 Q 156 64 168 80 Q 158 76 144 72 Q 138 66 138 60 Z',
          'M 102 64 L 96 78 L 92 76 L 98 64 Z',
          'M 116 60 L 116 76 L 112 76 L 112 60 Z',
          'M 130 62 L 134 76 L 130 78 L 126 64 Z',
          'M 144 64 L 152 78 L 148 80 L 140 66 Z',
          'M 84 72 L 80 86 L 76 84 L 80 70 Z',
          'M 156 72 L 162 86 L 158 88 L 152 74 Z',
          'M 108 58 L 110 70 L 106 70 L 104 60 Z',
        ],
      },
      lou: { // honey brown, messy boy-cut, fringe sweeping right
        back: 'M 64 80 Q 42 116 56 178 Q 70 210 96 218 L 144 218 Q 174 212 186 180 Q 200 116 178 80 Q 158 60 120 56 Q 82 60 64 80 Z',
        strands: [
          'M 80 70 Q 100 54 138 58 Q 158 62 156 78 Q 132 70 108 76 Q 90 80 80 70 Z',
          'M 88 64 Q 110 50 142 56 Q 154 64 144 70 Q 120 64 100 70 Q 90 70 88 64 Z',
          'M 76 78 Q 88 68 108 70 Q 96 80 84 84 Q 76 82 76 78 Z',
          'M 154 72 Q 168 76 174 88 Q 168 96 158 92 Q 152 84 154 72 Z',
          'M 96 68 L 92 84 L 88 82 L 94 66 Z',
          'M 112 62 L 108 78 L 104 76 L 110 60 Z',
          'M 128 60 L 130 76 L 126 76 L 122 60 Z',
          'M 142 62 L 148 78 L 144 80 L 138 64 Z',
          'M 156 68 L 164 82 L 160 84 L 152 70 Z',
          'M 84 74 L 80 88 L 76 86 L 80 72 Z',
          'M 100 64 L 102 78 L 98 78 L 96 62 Z',
          'M 122 56 L 124 72 L 120 72 L 118 56 Z',
          'M 134 58 L 138 74 L 134 76 L 130 58 Z',
          'M 150 66 L 156 80 L 152 82 L 146 68 Z',
        ],
      },
      mira: { // copper red, shoulder length with bandana, wild fringe
        back: 'M 56 76 Q 30 120 48 200 Q 60 232 96 234 L 148 234 Q 184 232 196 200 Q 212 120 184 76 Q 162 50 120 48 Q 76 50 56 76 Z',
        strands: [
          'M 78 72 Q 102 50 140 54 Q 162 60 158 78 Q 130 70 104 76 Q 88 80 78 72 Z',
          'M 90 60 Q 116 46 146 52 Q 158 60 148 68 Q 122 60 102 66 Q 90 66 90 60 Z',
          'M 70 88 Q 60 110 64 140 Q 72 122 78 102 Q 76 92 70 88 Z',
          'M 168 86 Q 178 108 174 138 Q 166 122 160 100 Q 162 90 168 86 Z',
          'M 96 64 L 90 84 L 86 82 L 94 62 Z',
          'M 110 58 L 106 78 L 102 76 L 108 56 Z',
          'M 124 56 L 124 76 L 120 76 L 120 56 Z',
          'M 138 58 L 142 78 L 138 80 L 134 58 Z',
          'M 152 62 L 158 80 L 154 82 L 148 64 Z',
          'M 80 82 L 74 100 L 70 98 L 76 80 Z',
          'M 162 80 L 168 98 L 164 100 L 158 82 Z',
          'M 102 60 L 100 78 L 96 78 L 98 60 Z',
          'M 132 60 L 134 78 L 130 78 L 128 60 Z',
          'M 116 50 L 118 70 L 114 70 L 112 50 Z',
          'M 86 70 L 82 88 L 78 86 L 82 68 Z',
          'M 156 72 L 164 90 L 160 92 L 152 74 Z',
        ],
      },
      diego: { // raven black, slick back, short
        back: 'M 70 82 Q 50 118 60 174 Q 72 206 96 214 L 144 214 Q 170 208 180 176 Q 192 118 172 82 Q 154 64 120 60 Q 86 64 70 82 Z',
        strands: [
          'M 80 76 Q 102 60 140 62 Q 160 68 154 80 Q 130 72 108 78 Q 90 82 80 76 Z',
          'M 92 66 Q 116 54 144 58 Q 152 66 144 72 Q 120 66 102 70 Q 92 70 92 66 Z',
          'M 76 84 Q 86 76 100 78 Q 92 88 84 90 Q 76 88 76 84 Z',
          'M 158 80 Q 168 84 172 94 Q 166 102 158 98 Q 154 90 158 80 Z',
          'M 100 70 L 96 82 L 92 80 L 98 68 Z',
          'M 114 64 L 112 78 L 108 78 L 110 62 Z',
          'M 128 62 L 130 76 L 126 76 L 124 62 Z',
          'M 142 64 L 148 78 L 144 80 L 138 66 Z',
          'M 154 72 L 160 86 L 156 88 L 150 74 Z',
          'M 84 80 L 80 92 L 76 90 L 80 78 Z',
          'M 122 60 L 122 74 L 118 74 L 118 60 Z',
          'M 136 64 L 138 78 L 134 78 L 132 62 Z',
        ],
      },
      tess: { // ash blonde lob, tucked behind ear right
        back: 'M 58 80 Q 36 120 50 196 Q 64 226 96 228 L 148 228 Q 178 226 192 196 Q 206 120 184 80 Q 162 58 120 56 Q 78 58 58 80 Z',
        strands: [
          'M 78 72 Q 102 56 140 60 Q 158 68 154 82 Q 130 72 104 78 Q 86 80 78 72 Z',
          'M 88 60 Q 114 48 144 54 Q 156 62 146 70 Q 122 62 100 68 Q 88 66 88 60 Z',
          'M 68 90 Q 58 116 64 152 Q 74 130 80 102 Q 76 94 68 90 Z',
          'M 170 86 Q 180 110 178 144 Q 168 124 162 100 Q 164 90 170 86 Z',
          'M 100 62 L 96 80 L 92 78 L 96 60 Z',
          'M 114 58 L 112 76 L 108 76 L 110 56 Z',
          'M 126 56 L 128 76 L 124 76 L 122 56 Z',
          'M 140 58 L 144 78 L 140 80 L 136 60 Z',
          'M 154 64 L 160 82 L 156 84 L 150 66 Z',
          'M 80 78 L 76 96 L 72 94 L 76 76 Z',
          'M 162 78 L 168 96 L 164 98 L 158 80 Z',
          'M 108 56 L 110 76 L 106 76 L 104 56 Z',
          'M 132 56 L 134 76 L 130 76 L 128 56 Z',
        ],
      },
      sam: { // chocolate brown short, slight wave
        back: 'M 68 80 Q 48 116 60 178 Q 72 208 98 214 L 142 214 Q 168 210 178 178 Q 192 116 172 80 Q 152 62 120 58 Q 86 62 68 80 Z',
        strands: [
          'M 80 74 Q 100 58 140 62 Q 158 68 154 82 Q 132 72 108 78 Q 90 82 80 74 Z',
          'M 90 64 Q 114 52 142 58 Q 152 66 142 72 Q 118 64 100 70 Q 90 68 90 64 Z',
          'M 74 84 Q 86 78 102 80 Q 92 90 84 92 Q 74 88 74 84 Z',
          'M 158 82 Q 170 86 172 96 Q 166 104 156 100 Q 154 90 158 82 Z',
          'M 102 66 L 98 80 L 94 78 L 100 64 Z',
          'M 116 60 L 114 76 L 110 76 L 112 58 Z',
          'M 130 60 L 132 76 L 128 76 L 126 58 Z',
          'M 144 64 L 150 78 L 146 80 L 140 66 Z',
          'M 86 76 L 82 90 L 78 88 L 82 74 Z',
          'M 124 58 L 124 74 L 120 74 L 120 58 Z',
          'M 138 60 L 142 76 L 138 78 L 134 60 Z',
          'M 154 68 L 160 82 L 156 84 L 150 70 Z',
        ],
      },
      yann: { // blue-black, side-parted, professional, slightly receding
        back: 'M 70 82 Q 52 118 62 176 Q 74 206 98 212 L 142 212 Q 168 208 178 176 Q 190 118 170 82 Q 152 66 120 64 Q 88 66 70 82 Z',
        strands: [
          'M 82 76 Q 102 64 138 66 Q 158 70 152 82 Q 130 74 108 80 Q 90 82 82 76 Z',
          'M 92 68 Q 114 58 140 62 Q 152 68 144 74 Q 120 68 102 72 Q 92 72 92 68 Z',
          'M 100 70 L 96 84 L 92 82 L 98 68 Z',
          'M 114 64 L 112 80 L 108 80 L 110 62 Z',
          'M 128 64 L 130 80 L 126 80 L 124 62 Z',
          'M 142 66 L 146 80 L 142 82 L 138 66 Z',
          'M 156 72 L 160 84 L 156 86 L 152 72 Z',
          'M 78 82 L 74 96 L 70 94 L 74 80 Z',
          'M 162 82 L 166 94 L 162 96 L 158 82 Z',
          'M 122 62 L 122 78 L 118 78 L 118 62 Z',
          'M 136 64 L 140 78 L 136 80 L 132 64 Z',
          'M 88 78 L 86 92 L 82 92 L 84 78 Z',
        ],
      },
    };
    return styles[persona];
  }

  // ─────────────────────────────────────────────────────────
  //  CLOTHING RENDERERS — signature outfit per persona
  // ─────────────────────────────────────────────────────────
  function ClothSage({ p }) {
    return (
      <g>
        {/* coat body */}
        <path d="M 38 280 Q 50 250 90 246 L 150 246 Q 190 250 202 280 L 210 380 L 30 380 Z" fill={p.clothBase}/>
        {/* lapel left */}
        <path d="M 90 246 L 86 280 L 110 290 L 116 256 Z" fill={p.clothShade}/>
        {/* lapel right */}
        <path d="M 150 246 L 154 280 L 130 290 L 124 256 Z" fill={p.clothShade}/>
        {/* coat highlight */}
        <path d="M 50 270 Q 56 310 62 360 L 68 380 L 56 380 Z" fill={p.clothHL} opacity=".5"/>
        {/* shadow under arm right */}
        <path d="M 184 270 Q 196 320 200 380 L 188 380 Z" fill={p.clothShade} opacity=".7"/>
        {/* gold buttons */}
        <circle cx="120" cy="296" r="2.2" fill="#c89048"/>
        <circle cx="120" cy="320" r="2.2" fill="#c89048"/>
        <circle cx="120" cy="344" r="2.2" fill="#c89048"/>
        <circle cx="120" cy="296" r=".8" fill="#fff" opacity=".7"/>
        <circle cx="120" cy="320" r=".8" fill="#fff" opacity=".7"/>
        <circle cx="120" cy="344" r=".8" fill="#fff" opacity=".7"/>
        {/* fold lines */}
        <path d="M 80 280 L 76 360" stroke={p.clothShade} strokeWidth="1" opacity=".5" fill="none"/>
        <path d="M 160 280 L 164 360" stroke={p.clothShade} strokeWidth="1" opacity=".5" fill="none"/>
        <path d="M 102 320 L 98 380" stroke={p.clothShade} strokeWidth=".7" opacity=".4" fill="none"/>
        <path d="M 138 320 L 142 380" stroke={p.clothShade} strokeWidth=".7" opacity=".4" fill="none"/>
        {/* scarf — burgundy double tour */}
        <g style={{ transformOrigin:'120px 248px', animation:'a10-scarf-wave 5.3s ease-in-out infinite' }}>
          <path d="M 84 244 Q 100 248 120 252 Q 140 248 156 244 L 158 264 Q 140 268 120 272 Q 100 268 82 264 Z" fill="#8b1f2d"/>
          <path d="M 92 248 Q 110 252 128 254 Q 144 252 154 248 L 154 256 Q 138 260 122 262 Q 106 260 92 256 Z" fill="#6a121f"/>
          {/* scarf knot */}
          <path d="M 108 258 Q 120 262 132 258 L 134 280 Q 122 284 110 280 Z" fill="#8b1f2d"/>
          <path d="M 110 280 L 108 320 L 118 320 L 122 280 Z" fill="#6a121f"/>
          <path d="M 128 280 L 130 320 L 122 320 L 120 280 Z" fill="#8b1f2d"/>
        </g>
      </g>
    );
  }

  function ClothLou({ p }) {
    return (
      <g>
        {/* hoodie body navy */}
        <path d="M 40 280 Q 50 252 90 248 L 150 248 Q 190 252 200 280 L 208 380 L 32 380 Z" fill={p.clothBase}/>
        {/* hood collar tombée */}
        <path d="M 86 246 Q 70 240 60 256 Q 56 274 70 280 L 96 270 Z" fill={p.clothShade}/>
        <path d="M 154 246 Q 170 240 180 256 Q 184 274 170 280 L 144 270 Z" fill={p.clothShade}/>
        {/* white t-shirt under zip */}
        <path d="M 110 252 L 130 252 L 134 286 L 106 286 Z" fill="#f4f4f4"/>
        <path d="M 110 252 L 116 264 L 124 264 L 130 252" stroke={p.skinSh} strokeWidth=".8" fill="none" opacity=".5"/>
        {/* zip line */}
        <path d="M 120 252 L 120 286" stroke={p.clothHL} strokeWidth="1.2"/>
        <circle cx="120" cy="288" r="2" fill={p.clothHL}/>
        {/* zip teeth */}
        {Array.from({length:9}, (_,i)=>(
          <line key={i} x1="118" x2="122" y1={254+i*4} y2={254+i*4} stroke={p.clothHL} strokeWidth=".4"/>
        ))}
        {/* drawstrings */}
        <path d="M 104 268 L 100 320" stroke="#f4f4f4" strokeWidth="1.4"/>
        <path d="M 136 268 L 140 320" stroke="#f4f4f4" strokeWidth="1.4"/>
        <circle cx="100" cy="322" r="1.6" fill="#f4f4f4"/>
        <circle cx="140" cy="322" r="1.6" fill="#f4f4f4"/>
        {/* highlight */}
        <path d="M 50 280 Q 54 320 56 380 L 46 380 Z" fill={p.clothHL} opacity=".4"/>
        {/* shadow */}
        <path d="M 188 280 Q 196 320 198 380 L 188 380 Z" fill={p.clothShade} opacity=".6"/>
        {/* fold lines */}
        <path d="M 84 290 L 78 360" stroke={p.clothShade} strokeWidth=".8" opacity=".5" fill="none"/>
        <path d="M 156 290 L 162 360" stroke={p.clothShade} strokeWidth=".8" opacity=".5" fill="none"/>
        <path d="M 100 330 Q 96 360 92 380" stroke={p.clothShade} strokeWidth=".6" opacity=".4" fill="none"/>
        <path d="M 140 330 Q 144 360 148 380" stroke={p.clothShade} strokeWidth=".6" opacity=".4" fill="none"/>
        {/* pocket */}
        <path d="M 78 326 L 162 326 L 158 358 L 82 358 Z" fill="none" stroke={p.clothShade} strokeWidth=".7" opacity=".6"/>
      </g>
    );
  }

  function ClothMira({ p }) {
    return (
      <g>
        {/* striped t-shirt */}
        <path d="M 40 280 Q 52 252 90 248 L 150 248 Q 188 252 200 280 L 208 380 L 32 380 Z" fill="#f0ece4"/>
        {Array.from({length:12}, (_,i)=>(
          <rect key={i} x="32" y={252+i*11} width="180" height="4" fill="#1a3a5e" opacity=".7"/>
        ))}
        {/* sleeves rolled */}
        <path d="M 40 280 L 28 320 L 50 322 L 56 286 Z" fill="#f0ece4"/>
        <path d="M 200 280 L 212 320 L 192 322 L 184 286 Z" fill="#f0ece4"/>
        {/* apron - taupe */}
        <path d="M 60 268 Q 78 264 96 262 L 144 262 Q 162 264 180 268 L 184 380 L 56 380 Z" fill={p.clothBase}/>
        {/* apron strap */}
        <path d="M 92 248 L 96 268" stroke={p.clothShade} strokeWidth="3"/>
        <path d="M 148 248 L 144 268" stroke={p.clothShade} strokeWidth="3"/>
        {/* paint stains */}
        <path d="M 92 296 Q 98 290 106 294 Q 110 304 100 308 Q 90 306 92 296 Z" fill="#e85d2a"/>
        <path d="M 148 322 Q 156 316 164 322 Q 168 332 158 336 Q 148 334 148 322 Z" fill="#3a86ff"/>
        <path d="M 116 354 Q 122 348 130 352 Q 134 360 126 364 Q 118 362 116 354 Z" fill="#ffd040"/>
        {/* small splatters */}
        <circle cx="84" cy="310" r="1.4" fill="#e85d2a"/>
        <circle cx="170" cy="296" r="1.6" fill="#3a86ff"/>
        <circle cx="138" cy="288" r="1" fill="#ffd040"/>
        <circle cx="76" cy="350" r="1.2" fill="#e85d2a"/>
        {/* apron pocket */}
        <path d="M 78 330 L 162 330 L 160 360 L 80 360 Z" fill="none" stroke={p.clothShade} strokeWidth=".7" opacity=".6"/>
        {/* fold */}
        <path d="M 100 270 L 92 380" stroke={p.clothShade} strokeWidth=".8" opacity=".5" fill="none"/>
        <path d="M 140 270 L 148 380" stroke={p.clothShade} strokeWidth=".8" opacity=".5" fill="none"/>
      </g>
    );
  }

  function ClothDiego({ p }) {
    return (
      <g>
        {/* black t-shirt */}
        <path d="M 50 282 Q 60 256 90 254 L 150 254 Q 180 256 190 282 L 196 380 L 44 380 Z" fill="#1a1a1a"/>
        {/* burgundy hoodie */}
        <path d="M 38 290 Q 48 260 86 252 L 88 248 Q 78 252 70 246 L 68 252 Q 56 256 50 274 L 38 290 Z M 202 290 Q 192 260 154 252 L 152 248 Q 162 252 170 246 L 172 252 Q 184 256 190 274 Z" fill={p.clothBase}/>
        <path d="M 38 290 Q 36 326 32 380 L 56 380 Q 56 322 60 290 Z" fill={p.clothBase}/>
        <path d="M 202 290 Q 204 326 208 380 L 184 380 Q 184 322 180 290 Z" fill={p.clothBase}/>
        {/* hood opening V */}
        <path d="M 86 252 L 110 282 L 130 282 L 154 252 Q 142 256 120 256 Q 98 256 86 252 Z" fill={p.clothShade}/>
        {/* chain */}
        <path d="M 100 286 Q 120 296 140 286" stroke="#c8c8c8" strokeWidth="1.2" fill="none"/>
        {Array.from({length:8}, (_,i)=>{
          const x = 100 + i*5; const y = 286 + Math.sin(i/2.5)*4;
          return <circle key={i} cx={x} cy={y} r="1" fill="#dcdcdc"/>;
        })}
        {/* headphones around neck */}
        <path d="M 80 226 Q 120 200 160 226" stroke="#1a1a1a" strokeWidth="3.5" fill="none"/>
        <ellipse cx="78" cy="226" rx="9" ry="11" fill="#1a1a1a"/>
        <ellipse cx="78" cy="226" rx="6" ry="8" fill="#3a3a3a"/>
        <circle cx="78" cy="226" r="2.2" fill="#0a0a0a"/>
        <ellipse cx="162" cy="226" rx="9" ry="11" fill="#1a1a1a"/>
        <ellipse cx="162" cy="226" rx="6" ry="8" fill="#3a3a3a"/>
        <circle cx="162" cy="226" r="2.2" fill="#0a0a0a"/>
        {/* hood highlight */}
        <path d="M 50 290 Q 52 320 54 380 L 46 380 Z" fill={p.clothHL} opacity=".35"/>
        <path d="M 192 290 Q 196 320 198 380 L 184 380 Z" fill={p.clothShade} opacity=".5"/>
        <path d="M 88 256 L 84 360" stroke={p.clothShade} strokeWidth=".8" opacity=".5" fill="none"/>
        <path d="M 152 256 L 156 360" stroke={p.clothShade} strokeWidth=".8" opacity=".5" fill="none"/>
      </g>
    );
  }

  function ClothTess({ p }) {
    return (
      <g>
        {/* cream blouse */}
        <path d="M 70 252 Q 90 248 120 248 Q 150 248 170 252 L 174 320 L 66 320 Z" fill={p.clothAccent}/>
        {/* black blazer */}
        <path d="M 36 280 Q 48 250 86 246 L 90 248 L 96 280 L 110 296 L 130 296 L 144 280 L 150 248 L 154 246 Q 192 250 204 280 L 212 380 L 28 380 Z" fill={p.clothBase}/>
        {/* notched lapels */}
        <path d="M 86 246 L 96 280 L 112 290 L 116 254 L 110 250 Z" fill={p.clothShade}/>
        <path d="M 154 246 L 144 280 L 128 290 L 124 254 L 130 250 Z" fill={p.clothShade}/>
        {/* notch detail */}
        <path d="M 96 264 L 90 270 L 92 274 L 100 270 Z" fill={p.clothBase}/>
        <path d="M 144 264 L 150 270 L 148 274 L 140 270 Z" fill={p.clothBase}/>
        {/* glasses on neckline */}
        <g transform="translate(106 290)">
          <ellipse cx="0" cy="0" rx="6" ry="3" fill="none" stroke="#1a1a1a" strokeWidth="1"/>
          <ellipse cx="14" cy="0" rx="6" ry="3" fill="none" stroke="#1a1a1a" strokeWidth="1"/>
          <line x1="6" y1="0" x2="8" y2="0" stroke="#1a1a1a" strokeWidth="1"/>
          <line x1="-6" y1="0" x2="-10" y2="-2" stroke="#1a1a1a" strokeWidth="1"/>
        </g>
        {/* button single */}
        <circle cx="120" cy="328" r="2" fill="#0a0a0a"/>
        <circle cx="120" cy="328" r=".7" fill={p.clothHL} opacity=".7"/>
        <path d="M 60 290 Q 62 330 64 380 L 50 380 Z" fill={p.clothHL} opacity=".25"/>
        <path d="M 184 290 Q 192 330 198 380 L 184 380 Z" fill={p.clothShade} opacity=".6"/>
        {/* lapel highlight */}
        <path d="M 88 260 L 94 280" stroke={p.clothHL} strokeWidth=".6" opacity=".5"/>
        <path d="M 152 260 L 146 280" stroke={p.clothHL} strokeWidth=".6" opacity=".5"/>
      </g>
    );
  }

  function ClothSam({ p }) {
    // Chunky knit beige
    return (
      <g>
        {/* knit body */}
        <path d="M 36 282 Q 46 252 86 248 L 154 248 Q 194 252 204 282 L 212 380 L 28 380 Z" fill={p.clothBase}/>
        {/* turtleneck */}
        <path d="M 96 248 Q 96 230 120 228 Q 144 230 144 248 L 142 256 Q 130 252 120 252 Q 110 252 98 256 Z" fill={p.clothShade}/>
        <path d="M 100 232 Q 120 228 140 232 L 140 244 Q 120 240 100 244 Z" fill={p.clothBase}/>
        {/* knit pattern - cable stitches */}
        {Array.from({length:7}, (_,i)=>{
          const x = 50 + i*22;
          return (
            <g key={i}>
              <path d={`M ${x} 260 Q ${x+5} 280 ${x} 300 Q ${x-5} 320 ${x} 340 Q ${x+5} 360 ${x} 378`}
                    stroke={p.clothShade} strokeWidth="1.2" fill="none" opacity=".55"/>
              <path d={`M ${x+11} 260 Q ${x+16} 280 ${x+11} 300 Q ${x+6} 320 ${x+11} 340 Q ${x+16} 360 ${x+11} 378`}
                    stroke={p.clothHL} strokeWidth=".8" fill="none" opacity=".5"/>
            </g>
          );
        })}
        {/* horizontal knit weave */}
        {Array.from({length:14}, (_,i)=>(
          <rect key={i} x="32" y={258+i*9} width="178" height="1.2" fill={p.clothShade} opacity=".25"/>
        ))}
        {/* sleeve cuff covering hand naturally */}
        <path d="M 32 360 L 28 380 L 56 380 L 56 360 Z" fill={p.clothShade} opacity=".7"/>
        <path d="M 208 360 L 212 380 L 184 380 L 184 360 Z" fill={p.clothShade} opacity=".7"/>
        <path d="M 50 290 L 46 380" stroke={p.clothShade} strokeWidth=".7" opacity=".4" fill="none"/>
        <path d="M 192 290 L 196 380" stroke={p.clothShade} strokeWidth=".7" opacity=".4" fill="none"/>
      </g>
    );
  }

  function ClothYann({ p }) {
    return (
      <g>
        {/* oxford shirt body */}
        <path d="M 42 284 Q 54 256 90 252 L 150 252 Q 186 256 198 284 L 206 380 L 34 380 Z" fill={p.clothBase}/>
        {/* collar */}
        <path d="M 96 252 L 90 248 L 84 268 L 100 280 L 110 268 Z" fill={p.clothBase}/>
        <path d="M 144 252 L 150 248 L 156 268 L 140 280 L 130 268 Z" fill={p.clothBase}/>
        {/* collar shade */}
        <path d="M 96 252 L 100 280 L 110 268 L 110 256 Z" fill={p.clothShade} opacity=".5"/>
        <path d="M 144 252 L 140 280 L 130 268 L 130 256 Z" fill={p.clothShade} opacity=".5"/>
        {/* tie loose */}
        <path d="M 110 268 L 130 268 L 134 286 L 106 286 Z" fill="#3a4a5a"/>
        <path d="M 106 286 L 134 286 L 138 326 L 102 326 Z" fill="#3a4a5a"/>
        <path d="M 102 326 L 138 326 L 134 360 L 106 360 Z" fill="#3a4a5a"/>
        <path d="M 110 268 L 130 268 L 132 274 L 108 274 Z" fill="#1a2a3a"/>
        {/* tie pattern stripes */}
        <path d="M 108 290 L 132 320" stroke="#5a6a7a" strokeWidth="1" opacity=".7"/>
        <path d="M 116 290 L 138 314" stroke="#5a6a7a" strokeWidth="1" opacity=".7"/>
        <path d="M 102 308 L 126 340" stroke="#5a6a7a" strokeWidth="1" opacity=".7"/>
        {/* shirt buttons */}
        <circle cx="120" cy="296" r="1.4" fill="#fff"/>
        <circle cx="120" cy="316" r="1.4" fill="#fff"/>
        <circle cx="120" cy="336" r="1.4" fill="#fff"/>
        <circle cx="120" cy="356" r="1.4" fill="#fff"/>
        {/* sleeves rolled cuff */}
        <path d="M 36 326 L 30 354 L 56 358 L 60 332 Z" fill={p.clothHL}/>
        <path d="M 204 326 L 210 354 L 184 358 L 180 332 Z" fill={p.clothHL}/>
        {/* watch */}
        <rect x="183" y="350" width="14" height="9" rx="2" fill="#3a2818"/>
        <rect x="185" y="352" width="10" height="5" rx="1" fill="#1a1410"/>
        <circle cx="190" cy="354.5" r="1.2" fill={p.clothHL}/>
        {/* highlight */}
        <path d="M 52 290 Q 54 330 56 380 L 46 380 Z" fill={p.clothHL} opacity=".35"/>
        <path d="M 188 290 Q 190 330 194 380 L 184 380 Z" fill={p.clothShade} opacity=".5"/>
        {/* fold */}
        <path d="M 84 290 L 78 380" stroke={p.clothShade} strokeWidth=".7" opacity=".4" fill="none"/>
        <path d="M 156 290 L 162 380" stroke={p.clothShade} strokeWidth=".7" opacity=".4" fill="none"/>
      </g>
    );
  }

  const CLOTHES = {
    'sage-coat': ClothSage,
    'lou-hoodie': ClothLou,
    'mira-apron': ClothMira,
    'diego-hoodie': ClothDiego,
    'tess-blazer': ClothTess,
    'sam-knit': ClothSam,
    'yann-shirt': ClothYann,
  };

  // ─────────────────────────────────────────────────────────
  //  EYE — sclera + iris (4-stop radial) + pupil + lashes
  // ─────────────────────────────────────────────────────────
  function Eye({ p, side, mood, idPrefix }) {
    const x = side === 'L' ? 102 : 138;
    const irisId = `${idPrefix}-iris-${side}`;
    const sclId = `${idPrefix}-scl-${side}`;
    const closed = mood === 'asleep' || mood === 'concentrate-sam';
    return (
      <g>
        {/* under-eye shadow / cerne */}
        <ellipse cx={x} cy="119" rx="9" ry="2.4" fill={p.skinSh} opacity=".18"/>
        {/* sclera */}
        <ellipse cx={x} cy="113" rx="8.5" ry={closed ? 1 : 5.4} fill="#fdf6e8"/>
        {/* sclera inner pink corner */}
        {!closed && (
          <ellipse cx={side === 'L' ? x-6 : x+6} cy="113" rx="2.8" ry="3.2" fill="#f5d4c8" opacity=".5"/>
        )}
        {/* iris with 4-stop gradient (inline radial) */}
        <defs>
          <radialGradient id={irisId} cx="50%" cy="40%" r="60%">
            <stop offset="0%" stopColor={p.eye} stopOpacity="1"/>
            <stop offset="35%" stopColor={mixColor(p.eye, '#ffffff', 0.25)}/>
            <stop offset="78%" stopColor={p.eye}/>
            <stop offset="100%" stopColor={mixColor(p.eye, '#000000', 0.35)}/>
          </radialGradient>
        </defs>
        {!closed && (
          <g style={{ animation: `a10-saccade ${3.4 + p.delaySeed*0.7}s ease-in-out infinite ${p.delaySeed*0.4}s` }}>
            <circle cx={x} cy="113" r="4.4" fill={`url(#${irisId})`}/>
            <circle cx={x} cy="113" r="2" fill="#0a0606"/>
            {/* main highlight up-right */}
            <circle cx={x+1.4} cy="111.6" r="1.2" fill="#ffffff"/>
            <circle cx={x+1.4} cy="111.6" r=".4" fill="#ffffff"/>
            {/* secondary highlight bottom-left blue tint */}
            <circle cx={x-1.6} cy="114.4" r=".7" fill="#a8d0ff" opacity=".7"/>
          </g>
        )}
        {/* upper lashes (4 strokes V pattern) */}
        <path d={`M ${x-7} 108 L ${x-6.5} 105.4`} stroke={p.brow} strokeWidth=".9" strokeLinecap="round"/>
        <path d={`M ${x-3.4} 107.4 L ${x-3} 105`} stroke={p.brow} strokeWidth="1" strokeLinecap="round"/>
        <path d={`M ${x+0.6} 107.2 L ${x+1} 104.8`} stroke={p.brow} strokeWidth="1" strokeLinecap="round"/>
        <path d={`M ${x+4.6} 107.6 L ${x+5} 105.2`} stroke={p.brow} strokeWidth=".9" strokeLinecap="round"/>
        <path d={`M ${x+7} 108 L ${x+6.6} 105.4`} stroke={p.brow} strokeWidth=".8" strokeLinecap="round"/>
        {/* upper lid line */}
        <path d={`M ${x-8} 108.6 Q ${x} 106.4 ${x+8} 108.6`} stroke={p.brow} strokeWidth="1.2" fill="none" strokeLinecap="round"/>
        {/* lower lashes 3 short */}
        <path d={`M ${x-4} 118.6 L ${x-4} 120`} stroke={p.brow} strokeWidth=".7" strokeLinecap="round" opacity=".7"/>
        <path d={`M ${x} 118.8 L ${x} 120.4`} stroke={p.brow} strokeWidth=".7" strokeLinecap="round" opacity=".7"/>
        <path d={`M ${x+4} 118.6 L ${x+4} 120`} stroke={p.brow} strokeWidth=".7" strokeLinecap="round" opacity=".7"/>
        {/* lower lid line */}
        <path d={`M ${x-8} 118 Q ${x} 119.4 ${x+8} 118`} stroke={p.skinSh} strokeWidth=".6" fill="none" opacity=".6"/>
        {/* blink lid */}
        <ellipse cx={x} cy="113" rx="9" ry="6" fill={p.skin}
          style={{ transformOrigin: `${x}px 113px`, animation: `a10-blink-squash ${4 + p.delaySeed * 0.5}s ease-in-out infinite ${p.delaySeed*0.3}s` }}/>
      </g>
    );
  }

  // mix two hex colors
  function mixColor(a, b, t) {
    const ah = parseInt(a.slice(1), 16), bh = parseInt(b.slice(1), 16);
    const ar = (ah>>16)&255, ag=(ah>>8)&255, ab=ah&255;
    const br = (bh>>16)&255, bg=(bh>>8)&255, bb=bh&255;
    const rr = Math.round(ar+(br-ar)*t).toString(16).padStart(2,'0');
    const gg = Math.round(ag+(bg-ag)*t).toString(16).padStart(2,'0');
    const bbh= Math.round(ab+(bb-ab)*t).toString(16).padStart(2,'0');
    return '#'+rr+gg+bbh;
  }

  // ─────────────────────────────────────────────────────────
  //  BROW — Bezier 6-point + 4 hair texture strokes
  // ─────────────────────────────────────────────────────────
  function Brow({ p, side, mood }) {
    const x = side === 'L' ? 102 : 138;
    const flip = side === 'R' ? -1 : 1;
    const furrow = mood === 'frown' || mood === 'concentrate';
    const raise = mood === 'surprise' || mood === 'speak-up';
    const animClass = furrow ? 'a10-brow-furrow' : raise ? 'a10-brow-raise' : '';
    return (
      <g style={{ transformOrigin: `${x}px 99px`, animation: animClass ? `${animClass} ${3 + p.delaySeed*0.4}s ease-in-out infinite ${p.delaySeed*0.5}s` : 'none' }}>
        {/* main brow body */}
        <path d={`M ${x-8} 100 Q ${x-5} 96 ${x-1} 95 Q ${x+3} 95 ${x+6} 96 Q ${x+8} 97 ${x+9} 99 Q ${x+5} 98 ${x} 97.5 Q ${x-4} 98 ${x-8} 100 Z`}
              fill={p.brow}/>
        {/* texture strokes */}
        <path d={`M ${x-6} 98 L ${x-5} 96.5`} stroke={p.hairDark} strokeWidth=".5" strokeLinecap="round"/>
        <path d={`M ${x-3} 97 L ${x-2} 95.4`} stroke={p.hairDark} strokeWidth=".5" strokeLinecap="round"/>
        <path d={`M ${x} 96.6 L ${x+1} 95.2`} stroke={p.hairDark} strokeWidth=".5" strokeLinecap="round"/>
        <path d={`M ${x+3} 96.6 L ${x+4} 95.4`} stroke={p.hairDark} strokeWidth=".5" strokeLinecap="round"/>
        <path d={`M ${x+6} 97 L ${x+7} 95.8`} stroke={p.hairDark} strokeWidth=".5" strokeLinecap="round"/>
        <path d={`M ${x+8} 98 L ${x+8.5} 97`} stroke={p.hairDark} strokeWidth=".4" strokeLinecap="round"/>
      </g>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  NOSE — 6-point path with arête, narines, reflet
  // ─────────────────────────────────────────────────────────
  function Nose({ p }) {
    return (
      <g>
        {/* nose bridge shadow right */}
        <path d="M 122 105 Q 124 118 126 132 Q 124 138 120 140 Q 122 134 121 124 Q 120 114 121 106 Z" fill={p.skinSh} opacity=".4"/>
        {/* left bridge highlight */}
        <path d="M 118 105 Q 117 116 117 130 Q 118 132 119 134" stroke={p.skinHL} strokeWidth="1" fill="none" opacity=".6"/>
        {/* nose tip + base 6-point */}
        <path d="M 116 132 Q 113 138 114 142 Q 117 144 120 144 Q 123 144 126 142 Q 127 138 124 132 Q 122 134 120 134 Q 118 134 116 132 Z"
              fill={p.skin}/>
        <path d="M 116 132 Q 113 138 114 142 L 116 142 Q 116 138 117 134 Z" fill={p.skinHL} opacity=".5"/>
        {/* narines */}
        <ellipse cx="117" cy="141" rx="1.4" ry=".9" fill={p.skinDeep}/>
        <ellipse cx="123" cy="141" rx="1.4" ry=".9" fill={p.skinDeep}/>
        {/* shadow under nose on philtrum */}
        <path d="M 117 144 Q 120 145 123 144 L 122 146 L 118 146 Z" fill={p.skinSh} opacity=".4"/>
      </g>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  MOUTH — upper/lower lip + 4 teeth + cupidon
  // ─────────────────────────────────────────────────────────
  function Mouth({ p, mood }) {
    const showTeeth = mood === 'smile' || mood === 'speak';
    const speak = mood === 'speak';
    return (
      <g>
        {/* cupidon's bow shadow */}
        <path d="M 116 150 Q 118 149 120 150 Q 122 149 124 150 L 123 151 Q 120 150.4 117 151 Z" fill={p.skinSh} opacity=".4"/>
        {/* mouth animated container */}
        <g style={{ transformOrigin: '120px 156px', animation: speak ? 'a10-mouth-speak 0.85s steps(5) infinite' : 'none' }}>
          {/* upper lip M-curve */}
          <path d="M 110 156 Q 114 152 116 154 Q 118 151 120 152 Q 122 151 124 154 Q 126 152 130 156 Q 124 158 120 158 Q 116 158 110 156 Z"
                fill={p.lip}/>
          <path d="M 116 154 Q 120 151.5 124 154 L 124 155.4 Q 120 153 116 155.4 Z" fill={p.lipSh}/>
          {/* lower lip arrondi */}
          <path d="M 110 156 Q 116 162 120 163 Q 124 162 130 156 Q 124 164 120 164.4 Q 116 164 110 156 Z"
                fill={mixColor(p.lip, '#ffffff', 0.18)}/>
          <path d="M 113 158 Q 120 161 127 158" stroke={p.lipSh} strokeWidth=".5" fill="none" opacity=".7"/>
          {/* central highlight */}
          <ellipse cx="120" cy="160" rx="2.6" ry=".7" fill="#fff" opacity=".4"/>
          {/* teeth (4 visible if smile/speak) */}
          {showTeeth && (
            <g>
              <rect x="115" y="155" width="2.2" height="3" rx=".4" fill="#fbf6ec"/>
              <rect x="117.6" y="154.8" width="2.4" height="3.2" rx=".4" fill="#fbf6ec"/>
              <rect x="120.4" y="154.8" width="2.4" height="3.2" rx=".4" fill="#fbf6ec"/>
              <rect x="123.2" y="155" width="2.2" height="3" rx=".4" fill="#fbf6ec"/>
            </g>
          )}
          {/* commissures */}
          <ellipse cx="110" cy="156.5" rx="1" ry=".7" fill={p.lipSh} opacity=".7"/>
          <ellipse cx="130" cy="156.5" rx="1" ry=".7" fill={p.lipSh} opacity=".7"/>
        </g>
        {/* tongue tip — Mira concentration only */}
        {mood === 'concentrate' && (
          <ellipse cx="124" cy="160" rx="1.8" ry="1" fill="#e07060"
            style={{ animation: 'a10-tongue-peek 4s ease-in-out infinite' }}/>
        )}
      </g>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  EAR with hélix / anti-hélix / lobe
  // ─────────────────────────────────────────────────────────
  function Ear({ p, side }) {
    const x = side === 'L' ? 64 : 176;
    const flip = side === 'R' ? -1 : 1;
    return (
      <g>
        <ellipse cx={x} cy="124" rx="6" ry="10" fill={p.skin}/>
        {/* helix */}
        <path d={`M ${x+flip*5} 116 Q ${x+flip*3} 122 ${x+flip*4} 132`} stroke={p.skinSh} strokeWidth="1" fill="none"/>
        {/* anti-helix */}
        <path d={`M ${x+flip*2} 120 Q ${x} 124 ${x+flip*1.5} 128`} stroke={p.skinSh} strokeWidth=".7" fill="none" opacity=".7"/>
        {/* interior shadow triangle */}
        <path d={`M ${x} 122 L ${x+flip*2} 130 L ${x+flip*1} 128 Z`} fill={p.skinDeep} opacity=".5"/>
        {/* lobe */}
        <ellipse cx={x} cy="132" rx="3" ry="2.6" fill={p.skin}/>
        <ellipse cx={x} cy="132.5" rx="2" ry="1.8" fill={p.skinSh} opacity=".4"/>
        {/* edge highlight */}
        <path d={`M ${x-flip*4.5} 116 Q ${x-flip*5} 124 ${x-flip*4} 132`} stroke={p.skinHL} strokeWidth=".5" fill="none" opacity=".7"/>
      </g>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  HEAD assembly (skull + face + ears + hair + neck)
  // ─────────────────────────────────────────────────────────
  function Head({ persona, mood }) {
    const p = P[persona];
    const hair = makeHair(persona);
    const idPrefix = `a10-${persona}`;
    return (
      <g style={{ transformOrigin: '120px 130px', animation: `a10-head-turn ${6 + p.delaySeed * 0.4}s cubic-bezier(.4,0,.2,1) infinite ${p.delaySeed*0.6}s` }}>
        <defs>
          <radialGradient id={`${idPrefix}-skull`} cx="50%" cy="32%" r="68%">
            <stop offset="0%" stopColor={p.skinHL}/>
            <stop offset="40%" stopColor={p.skin}/>
            <stop offset="78%" stopColor={p.skinSh}/>
            <stop offset="100%" stopColor={p.skinDeep}/>
          </radialGradient>
          <linearGradient id={`${idPrefix}-neck`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={p.skin}/>
            <stop offset="100%" stopColor={p.skinSh}/>
          </linearGradient>
        </defs>
        {/* back hair */}
        <path d={hair.back} fill={p.hairDark}/>
        <path d={hair.back} fill={p.hair} opacity=".7"/>
        {/* ears behind head edges */}
        <Ear p={p} side="L"/>
        <Ear p={p} side="R"/>
        {/* skull */}
        <ellipse cx="120" cy="120" rx="58" ry="68" fill={`url(#${idPrefix}-skull)`}/>
        {/* forehead radial soft shade */}
        <ellipse cx="120" cy="92" rx="40" ry="20" fill={p.skinHL} opacity=".3"/>
        {/* temple shadows */}
        <path d="M 64 110 Q 70 120 76 132 Q 70 124 64 116 Z" fill={p.skinSh} opacity=".35"/>
        <path d="M 176 110 Q 170 120 164 132 Q 170 124 176 116 Z" fill={p.skinSh} opacity=".35"/>
        {/* slight forehead line for Sage */}
        {persona === 'sage' && (
          <path d="M 96 88 Q 120 84 144 88" stroke={p.skinSh} strokeWidth=".7" fill="none" opacity=".5"/>
        )}
        {/* jaw V shadow */}
        <path d="M 94 158 Q 120 178 146 158 Q 134 174 120 178 Q 106 174 94 158 Z" fill={p.skinSh} opacity=".25"/>
        {/* chin shadow under lower lip */}
        <path d="M 110 168 Q 120 172 130 168 L 128 174 Q 120 176 112 174 Z" fill={p.skinSh} opacity=".4"/>
        {/* cheeks */}
        <ellipse cx="98" cy="138" rx="6" ry="4" fill={p.cheek} opacity=".35"
          style={{ animation: `a10-cheek-flush ${5 + p.delaySeed*0.3}s ease-in-out infinite ${p.delaySeed*0.5}s` }}/>
        <ellipse cx="142" cy="138" rx="6" ry="4" fill={p.cheek} opacity=".35"
          style={{ animation: `a10-cheek-flush ${5 + p.delaySeed*0.3}s ease-in-out infinite ${p.delaySeed*0.5+0.4}s` }}/>
        {/* eyes */}
        <Eye p={p} side="L" mood={mood} idPrefix={idPrefix}/>
        <Eye p={p} side="R" mood={mood} idPrefix={idPrefix}/>
        {/* brows */}
        <Brow p={p} side="L" mood={mood}/>
        <Brow p={p} side="R" mood={mood}/>
        {/* glasses (Tess, Sam wear them when in pose) */}
        {p.glasses && persona === 'sam' && (
          <g style={{ transformOrigin: '120px 113px', animation: 'a10-glasses-slide 5.7s ease-in-out infinite' }}>
            <ellipse cx="102" cy="113" rx="11" ry="8" fill="none" stroke="#3a2a1a" strokeWidth="1.4"/>
            <ellipse cx="138" cy="113" rx="11" ry="8" fill="none" stroke="#3a2a1a" strokeWidth="1.4"/>
            <line x1="113" y1="113" x2="127" y2="113" stroke="#3a2a1a" strokeWidth="1.4"/>
            <ellipse cx="102" cy="113" rx="9" ry="6.5" fill="#a8d0e8" opacity=".15"/>
            <ellipse cx="138" cy="113" rx="9" ry="6.5" fill="#a8d0e8" opacity=".15"/>
          </g>
        )}
        {/* nose */}
        <Nose p={p}/>
        {/* mouth */}
        <Mouth p={p} mood={mood}/>
        {/* front hair strands */}
        <g style={{ transformOrigin:'120px 110px', animation: `a10-hair-follow ${6 + p.delaySeed*0.4}s cubic-bezier(.4,0,.2,1) infinite ${0.08 + p.delaySeed*0.6}s` }}>
          {hair.strands.map((d, i) => (
            <path key={i} d={d} fill={i%3===0 ? p.hairDark : p.hair} opacity={i%4===0 ? 0.95 : 0.85}/>
          ))}
          {/* hair highlights */}
          <path d="M 88 70 Q 100 60 116 60" stroke={p.hairHL} strokeWidth="1.4" fill="none" opacity=".7"/>
          <path d="M 124 64 Q 140 64 156 76" stroke={p.hairHL} strokeWidth="1.2" fill="none" opacity=".6"/>
          <path d="M 70 96 Q 70 112 76 130" stroke={p.hairHL} strokeWidth="1" fill="none" opacity=".5"/>
        </g>
        {/* neck */}
        <path d="M 102 178 Q 102 198 106 220 L 134 220 Q 138 198 138 178 Z" fill={`url(#${idPrefix}-neck)`}/>
        {/* neck shadow under jaw */}
        <path d="M 102 178 Q 110 188 120 188 Q 130 188 138 178 L 134 196 L 106 196 Z" fill={p.skinSh} opacity=".5"/>
        {/* Adam's apple for men */}
        {p.pomme && (
          <ellipse cx="120" cy="208" rx="2" ry="3" fill={p.skinSh} opacity=".6"/>
        )}
        {/* clavicles */}
        <path d="M 76 224 Q 100 232 120 232 Q 140 232 164 224" stroke={p.skinSh} strokeWidth=".8" fill="none" opacity=".7"/>
        <path d="M 80 230 Q 100 238 120 238" stroke={p.skinSh} strokeWidth=".5" fill="none" opacity=".5"/>
        <path d="M 120 238 Q 140 238 160 230" stroke={p.skinSh} strokeWidth=".5" fill="none" opacity=".5"/>
        {/* jugular notch */}
        <ellipse cx="120" cy="234" rx="2" ry="1.4" fill={p.skinSh} opacity=".5"/>
      </g>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  HAND — 5 fingers with nails + palm shadow
  // ─────────────────────────────────────────────────────────
  function Hand({ p, x, y, scale = 1, side = 'L', state = 'idle' }) {
    const flip = side === 'R' ? -1 : 1;
    return (
      <g transform={`translate(${x} ${y}) scale(${scale * flip} ${scale})`}>
        {/* palm */}
        <path d="M -10 0 Q -12 14 -8 22 Q 0 26 8 22 Q 12 14 10 0 Z" fill={p.skin}/>
        {/* palm shadow */}
        <path d="M -8 4 Q -8 14 -4 20 Q 4 22 8 20 Q 8 12 6 6" fill="none" stroke={p.skinSh} strokeWidth=".7" opacity=".5"/>
        {/* fingers — index, middle, ring, pinky */}
        {[0,1,2,3].map(i => {
          const fx = -8 + i*5.5;
          const fy = state === 'tap' ? -10 - (i===1 || i===2 ? 1 : 0) : -10;
          const cls = state === 'tap' ? `tap-${i}` : '';
          return (
            <g key={i} style={{
              transformOrigin: `${fx}px 0px`,
              animation: state === 'tap' ? `a10-finger-tap 0.9s cubic-bezier(.4,0,.2,1) infinite ${i*0.07}s` : 'none'
            }}>
              <rect x={fx-2} y={fy} width="4" height="12" rx="1.6" fill={p.skin}/>
              <rect x={fx-1.6} y={fy} width="3.2" height="3.2" rx=".8" fill={p.skinHL} opacity=".5"/>
              {/* nail */}
              <ellipse cx={fx} cy={fy+1.2} rx="1.2" ry=".8" fill={mixColor(p.skin,'#ffffff',0.4)}/>
              {/* knuckle */}
              <ellipse cx={fx} cy={fy+5} rx="1.4" ry=".7" fill={p.skinSh} opacity=".4"/>
            </g>
          );
        })}
        {/* thumb */}
        <g transform="translate(-12 4) rotate(-30)">
          <rect x="-2" y="-8" width="4" height="10" rx="1.6" fill={p.skin}/>
          <ellipse cx="0" cy="-7" rx="1.2" ry=".8" fill={mixColor(p.skin,'#ffffff',0.4)}/>
        </g>
      </g>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  BODY — shoulders, arms, hands, clothing
  // ─────────────────────────────────────────────────────────
  function Body({ persona, gesture }) {
    const p = P[persona];
    const Cloth = CLOTHES[p.cloth];
    return (
      <g style={{ transformOrigin: '120px 320px', animation: `a10-breath ${4 + p.delaySeed*0.2}s cubic-bezier(.4,0,.2,1) infinite ${p.delaySeed*0.3}s` }}>
        {/* shoulders gradient base */}
        <path d="M 32 290 Q 60 252 120 248 Q 180 252 208 290 L 220 380 L 20 380 Z" fill={p.skinSh} opacity="0"/>
        <Cloth p={p}/>
        {/* arms — left & right with hand at end */}
        {/* Left arm */}
        <g style={{
          transformOrigin: '56 280px',
          animation: gesture === 'painting' ? 'a10-brush-arc 2.6s cubic-bezier(.4,0,.2,1) infinite' : 'none'
        }}>
          <path d="M 36 286 Q 28 320 32 354 L 50 354 Q 50 320 56 286 Z" fill={p.clothBase}/>
          <path d="M 38 286 Q 32 320 34 348" stroke={p.clothShade} strokeWidth=".7" opacity=".5" fill="none"/>
          {/* cuff variation handled by cloth */}
          <Hand p={p} x={42} y={358} scale={0.85} side="L"
                state={gesture === 'typing' ? 'tap' : 'idle'}/>
        </g>
        {/* Right arm */}
        <g style={{
          transformOrigin: '184px 280px',
          animation: gesture === 'pointing' ? 'a10-pen-trace 4s cubic-bezier(.4,0,.2,1) infinite' :
                     gesture === 'whiteboard' ? 'a10-pen-trace 3.2s cubic-bezier(.4,0,.2,1) infinite' :
                     gesture === 'speaking' ? 'a10-mic-bob 1.6s ease-in-out infinite' : 'none'
          }}>
          <path d="M 184 286 Q 190 320 188 354 L 206 354 Q 212 320 204 286 Z" fill={p.clothBase}/>
          <path d="M 202 286 Q 208 320 204 348" stroke={p.clothShade} strokeWidth=".7" opacity=".5" fill="none"/>
          <Hand p={p} x={196} y={358} scale={0.85} side="R"
                state={gesture === 'typing' ? 'tap' : 'idle'}/>
        </g>
        {/* gesture-specific tools in hand */}
        {gesture === 'painting' && (
          <g style={{ transformOrigin: '46px 366px', animation: 'a10-brush-arc 2.6s cubic-bezier(.4,0,.2,1) infinite' }}>
            <rect x="38" y="356" width="2.4" height="20" fill="#8a5a3a"/>
            <ellipse cx="39" cy="376" rx="3" ry="4" fill="#e85d2a"/>
          </g>
        )}
        {gesture === 'speaking' && (
          <g style={{ transformOrigin: '194px 360px', animation: 'a10-mic-bob 1.6s ease-in-out infinite' }}>
            <rect x="190" y="346" width="6" height="14" rx="3" fill="#1a1a1a"/>
            <circle cx="193" cy="352" r="2.4" fill="#3a3a3a"/>
            <line x1="193" y1="360" x2="193" y2="372" stroke="#1a1a1a" strokeWidth="1.4"/>
          </g>
        )}
        {gesture === 'reading' && (
          <g style={{ transformOrigin: '120px 340px' }}>
            <path d="M 78 320 L 162 320 L 162 372 L 78 372 Z" fill="#f0e8d8"/>
            <path d="M 120 320 L 120 372" stroke="#8a7858" strokeWidth=".8"/>
            <g style={{ transformOrigin: '120px 320px', animation: 'a10-page-flip 6.5s cubic-bezier(.4,0,.2,1) infinite' }}>
              <path d="M 120 320 L 162 320 L 162 372 L 120 372 Z" fill="#f6f0e0"/>
              {Array.from({length:8}, (_,i)=>(
                <line key={i} x1={126} x2="156" y1={332+i*5} y2={332+i*5} stroke="#5a4838" strokeWidth=".4" opacity=".7"/>
              ))}
            </g>
            {Array.from({length:8}, (_,i)=>(
              <line key={i} x1={86} x2="116" y1={332+i*5} y2={332+i*5} stroke="#5a4838" strokeWidth=".4" opacity=".7"/>
            ))}
          </g>
        )}
        {gesture === 'whiteboard' && (
          <g style={{ transformOrigin: '194px 360px', animation: 'a10-pen-trace 3.2s cubic-bezier(.4,0,.2,1) infinite' }}>
            <rect x="192" y="350" width="2.4" height="14" fill="#1a1a1a"/>
            <path d="M 192 364 L 195 366 L 196 364" fill="#1a1a1a"/>
          </g>
        )}
      </g>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  AVATAR — full portrait
  //  Public: persona, mood, gesture, light, w, h
  // ─────────────────────────────────────────────────────────
  function Avatar({ persona = 'sage', mood, gesture, light, w = 240, h = 360, style = {}, className = '' }) {
    const p = P[persona];
    if (!p) return null;
    const m = mood || (
      persona === 'mira' ? 'concentrate' :
      persona === 'lou' ? 'frown' :
      persona === 'diego' ? 'speak' :
      persona === 'tess' ? 'smile' :
      persona === 'sam' ? 'concentrate-sam' :
      persona === 'yann' ? 'frown' :
      persona === 'sage' ? 'smile' : 'neutral'
    );
    const g = gesture || p.gesture;

    // Lighting — direction determines highlight side and tint
    const lightTint = (light?.color) || '#fff5e0';
    const lightDir = light?.dir || 'right';
    const lightIntensity = light?.intensity ?? 0.32;

    return (
      <svg viewBox="0 0 240 380" width={w} height={h} className={className} style={{ overflow:'visible', ...style }}>
        {/* lighting overlay layer (drawn after avatar via mask) — we keep simple: a colored rim path */}
        <defs>
          <linearGradient id={`a10-light-${persona}`} x1={lightDir==='left'?'100%':'0%'} y1="0%" x2={lightDir==='left'?'0%':'100%'} y2="100%">
            <stop offset="0%" stopColor={lightTint} stopOpacity={lightIntensity}/>
            <stop offset="60%" stopColor={lightTint} stopOpacity="0"/>
          </linearGradient>
        </defs>
        <g style={{ animation: `a10-weight-shift ${5 + p.delaySeed*0.2}s cubic-bezier(.4,0,.2,1) infinite ${p.delaySeed*0.3}s` }}>
          <Body persona={persona} gesture={g}/>
          <Head persona={persona} mood={m}/>
        </g>
        {/* directional light overlay */}
        <ellipse cx={lightDir==='left'?60:180} cy="120" rx="80" ry="120" fill={`url(#a10-light-${persona})`} opacity=".75" pointerEvents="none"/>
      </svg>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  AVATAR MINI — head only, simplified, for chips & badges
  // ─────────────────────────────────────────────────────────
  function AvatarMini({ persona = 'sage', w = 56, h = 56, style = {} }) {
    const p = P[persona];
    if (!p) return null;
    const idPrefix = `mini-${persona}`;
    return (
      <svg viewBox="40 40 160 200" width={w} height={h} style={{ overflow:'visible', ...style }}>
        <defs>
          <radialGradient id={`${idPrefix}-skull`} cx="50%" cy="32%" r="68%">
            <stop offset="0%" stopColor={p.skinHL}/>
            <stop offset="50%" stopColor={p.skin}/>
            <stop offset="100%" stopColor={p.skinSh}/>
          </radialGradient>
        </defs>
        <ellipse cx="120" cy="225" rx="58" ry="24" fill={p.clothBase}/>
        <ellipse cx="120" cy="120" rx="58" ry="68" fill={`url(#${idPrefix}-skull)`}/>
        {/* simple hair fringe */}
        <path d={makeHair(persona).back} fill={p.hair}/>
        {/* eyes simple */}
        <ellipse cx="102" cy="113" rx="3" ry="2.2" fill="#fdf6e8"/>
        <ellipse cx="138" cy="113" rx="3" ry="2.2" fill="#fdf6e8"/>
        <circle cx="102" cy="113" r="1.6" fill={p.eye}/>
        <circle cx="138" cy="113" r="1.6" fill={p.eye}/>
        <circle cx="102.5" cy="112.5" r=".5" fill="#fff"/>
        <circle cx="138.5" cy="112.5" r=".5" fill="#fff"/>
        {/* brows simple */}
        <path d="M 95 100 Q 102 96 109 100" stroke={p.brow} strokeWidth="1.6" fill="none" strokeLinecap="round"/>
        <path d="M 131 100 Q 138 96 145 100" stroke={p.brow} strokeWidth="1.6" fill="none" strokeLinecap="round"/>
        {/* nose */}
        <path d="M 117 134 Q 120 142 123 134 Q 122 142 120 142 Q 118 142 117 134 Z" fill={p.skinSh} opacity=".5"/>
        {/* mouth */}
        <path d="M 112 156 Q 120 162 128 156" stroke={p.lipSh} strokeWidth="1.6" fill={p.lip} strokeLinecap="round"/>
      </svg>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  ONOMATOPEE — stylized POW! BOOM! CRACK!
  // ─────────────────────────────────────────────────────────
  function Onomatopee({ text, x = 0, y = 0, color = '#ffd040', stroke = '#1a1410', size = 56, style = {} }) {
    return (
      <div style={{
        position:'absolute', left:x, top:y, fontFamily:'Caveat, "Brush Script MT", cursive',
        fontSize: size, fontWeight:700, color, lineHeight:1,
        WebkitTextStroke: `3px ${stroke}`,
        textShadow: `0 6px 0 ${stroke}, 6px 6px 0 rgba(0,0,0,.25)`,
        animation: 'a10-onomatopee 1.6s cubic-bezier(.4,0,.2,1) infinite',
        transformOrigin: 'center', ...style
      }}>{text}</div>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  FIGHTCLOUD — irregular cloud + N limb-pokes + sparks + smoke
  //  kinds:  pow (8 limbs), boom (6), crack (4)
  // ─────────────────────────────────────────────────────────
  const CLOUD_PATHS = {
    pow: 'M 40 110 Q 20 80 50 60 Q 60 30 100 38 Q 130 10 170 30 Q 220 18 250 50 Q 300 40 330 70 Q 360 90 350 130 Q 370 160 330 180 Q 300 210 250 195 Q 220 220 170 200 Q 130 215 100 195 Q 50 200 30 170 Q 10 140 40 110 Z',
    boom: 'M 30 120 Q 8 90 40 60 Q 60 24 110 36 Q 150 10 200 30 Q 240 8 280 36 Q 330 30 370 60 Q 410 90 390 130 Q 415 165 370 195 Q 340 230 280 210 Q 240 235 200 215 Q 150 240 110 215 Q 70 230 40 200 Q 8 170 30 120 Z',
    crack: 'M 30 100 Q 14 76 40 56 Q 60 28 100 36 Q 130 14 170 32 Q 210 24 250 50 Q 300 38 322 80 Q 340 110 320 145 Q 340 170 300 180 Q 270 200 220 188 Q 180 210 150 195 Q 110 210 80 195 Q 48 200 30 170 Q 12 140 30 100 Z',
  };

  // Limb sprites for each kind
  function limbSprites(kind) {
    if (kind === 'pow') {
      // 3 arms, 2 legs, 1 brush, 1 palette, 1 paint tube = 8
      return [
        { d: <g><rect x="-3" y="-3" width="6" height="36" rx="2" fill="#f0d0a8"/><circle cx="0" cy="-6" r="6" fill="#f0d0a8"/></g>, lx: -120, ly: -60, lr: '-30deg', label:'arm' },
        { d: <g><rect x="-3" y="-3" width="6" height="40" rx="2" fill="#f0d0a8"/><circle cx="0" cy="-6" r="6" fill="#f0d0a8"/></g>, lx: 130, ly: -55, lr: '40deg', label:'arm' },
        { d: <g><rect x="-3" y="-3" width="6" height="34" rx="2" fill="#c8a075"/><circle cx="0" cy="-6" r="6" fill="#c8a075"/></g>, lx: 50, ly: -90, lr: '-10deg', label:'arm' },
        { d: <g><rect x="-4" y="-4" width="8" height="40" rx="3" fill="#1e3a5f"/><rect x="-3" y="36" width="6" height="10" fill="#3a2a18"/></g>, lx: -90, ly: 90, lr: '20deg', label:'leg' },
        { d: <g><rect x="-4" y="-4" width="8" height="44" rx="3" fill="#722f2f"/><rect x="-3" y="40" width="6" height="10" fill="#3a2a18"/></g>, lx: 100, ly: 95, lr: '-25deg', label:'leg' },
        { d: <g><rect x="-1.5" y="-12" width="3" height="32" fill="#8a5a3a"/><ellipse cx="0" cy="-14" rx="3.4" ry="6" fill="#e85d2a"/></g>, lx: -60, ly: -110, lr: '15deg', label:'brush' },
        { d: <g><circle r="14" fill="#f0e8d8" stroke="#8a7858" strokeWidth="1.6"/><circle r="3" cx="-6" cy="-2" fill="#e85d2a"/><circle r="3" cx="4" cy="-3" fill="#3a86ff"/><circle r="3" cx="2" cy="6" fill="#ffd040"/><circle r="3" cx="-5" cy="6" fill="#20a878"/></g>, lx: 110, ly: -100, lr: '0deg', label:'palette' },
        { d: <g><rect x="-3" y="-12" width="6" height="22" rx="1.4" fill="#3a86ff"/><circle cx="0" cy="-14" r="3" fill="#1a4080"/><path d="M 0 14 L -2 18 L 2 18 Z" fill="#e85d2a"/></g>, lx: -110, ly: 50, lr: '-50deg', label:'tube' },
      ];
    }
    if (kind === 'boom') {
      // hammer, wrench, screwdriver, helmeted arm, booted leg, gear = 6
      return [
        { d: <g><rect x="-2" y="-2" width="4" height="34" rx="1" fill="#5a4838"/><rect x="-12" y="-14" width="24" height="14" rx="2" fill="#9a8878"/></g>, lx: 0, ly: -130, lr: '0deg', label:'hammer' },
        { d: <g><rect x="-3" y="0" width="6" height="32" rx="2" fill="#a8a8a8"/><path d="M -10 -8 L -3 -8 L -3 4 L -8 4 L -10 0 Z" fill="#a8a8a8"/><path d="M 10 -8 L 3 -8 L 3 4 L 8 4 L 10 0 Z" fill="#a8a8a8"/></g>, lx: -120, ly: -80, lr: '-30deg', label:'wrench' },
        { d: <g><rect x="-1.6" y="-2" width="3.2" height="30" fill="#a8a8a8"/><rect x="-3.6" y="-12" width="7.2" height="12" rx="2" fill="#e85d2a"/></g>, lx: 130, ly: -75, lr: '25deg', label:'screwdriver' },
        { d: <g><rect x="-3" y="-3" width="6" height="36" rx="2" fill="#c89878"/><path d="M -10 -16 Q 0 -22 10 -16 L 10 -8 L -10 -8 Z" fill="#ffd040"/><rect x="-10" y="-8" width="20" height="3" fill="#3a3a3a"/></g>, lx: -90, ly: -100, lr: '-15deg', label:'arm' },
        { d: <g><rect x="-4" y="-4" width="8" height="32" rx="2" fill="#1e3a5f"/><path d="M -6 28 L 8 28 L 10 36 L -8 36 Z" fill="#3a2a18"/></g>, lx: 90, ly: 110, lr: '-20deg', label:'leg' },
        { d: <g><circle r="14" fill="#7a8898" stroke="#3a4a5a" strokeWidth="1.4"/><circle r="6" fill="#3a4a5a"/>{Array.from({length:8},(_,i)=>{const a=i*Math.PI/4;return <rect key={i} x="-2" y="-19" width="4" height="6" fill="#7a8898" transform={`rotate(${i*45})`}/>})}</g>, lx: -50, ly: 110, lr: '0deg', label:'gear' },
      ];
    }
    // crack
    return [
      { d: <g><rect x="-20" y="-6" width="40" height="14" rx="2" fill="#3a3a3a"/><rect x="-18" y="-4" width="36" height="10" fill="#5a5a5a"/>{Array.from({length:5},(_,i)=>(<rect key={i} x={-15+i*6} y="-2" width="4" height="6" fill="#1a1a1a"/>))}</g>, lx: 0, ly: -120, lr: '-15deg', label:'keyboard' },
      { d: <g><ellipse rx="10" ry="14" fill="#ffffff" stroke="#1a1a1a" strokeWidth="1.4"/><circle r="2" fill="#1a1a1a"/><line y1="14" y2="20" stroke="#1a1a1a" strokeWidth="1.4"/></g>, lx: -110, ly: -50, lr: '-40deg', label:'mouse' },
      { d: <g><rect x="-3" y="-3" width="6" height="40" rx="2" fill="#f5d8b8"/><circle cx="0" cy="-6" r="6" fill="#f5d8b8"/></g>, lx: 120, ly: -60, lr: '40deg', label:'arm' },
      { d: <g><rect x="-12" y="-12" width="24" height="24" rx="1" fill="#ffd040"/><line x1="-9" x2="9" y1="-7" y2="-7" stroke="#5a4838" strokeWidth=".7"/><line x1="-9" x2="9" y1="-2" y2="-2" stroke="#5a4838" strokeWidth=".7"/><line x1="-9" x2="9" y1="3" y2="3" stroke="#5a4838" strokeWidth=".7"/></g>, lx: -90, ly: 80, lr: '20deg', label:'postit' },
    ];
  }

  // FightCloud component
  function FightCloud({ kind = 'pow', x = 0, y = 0, w, h, anticipation = true }) {
    const widths = { pow: 380, boom: 420, crack: 360 };
    const heights = { pow: 220, boom: 240, crack: 200 };
    const W = w || widths[kind], H = h || heights[kind];
    const cloudColor = '#dadada';
    const cloudColorDark = '#a8a8a8';
    const onomatopees = {
      pow: { text: 'POW!', color: '#ffd040', stroke: '#1a1410', size: 64 },
      boom: { text: 'BOOM!', color: '#ff8030', stroke: '#1a0808', size: 72 },
      crack: { text: 'CRACK!', color: '#ff3030', stroke: '#400000', size: 60 },
    };
    const limbs = limbSprites(kind);
    const sparkColor = kind === 'pow' ? '#ff3030' : kind === 'boom' ? '#ff8030' : '#ff5050';
    const onom = onomatopees[kind];
    return (
      <div style={{ position:'absolute', left:x, top:y, width:W, height:H, pointerEvents:'none' }}>
        {/* anticipation flash */}
        <div style={{
          position:'absolute', inset:'-20px', background:'radial-gradient(ellipse at center, #fff 0%, transparent 60%)',
          animation:'a10-flash 1.6s ease-in-out infinite', mixBlendMode:'screen'
        }}/>
        <svg viewBox={`-${W/2} -${H/2} ${W} ${H}`} width={W} height={H}
             style={{ position:'absolute', inset:0, animation: anticipation ? 'a10-cloud-shake 1.6s ease-in-out infinite' : 'none', overflow:'visible' }}>
          {/* speed-lines radiating */}
          {Array.from({length: kind === 'pow' ? 14 : kind === 'boom' ? 12 : 10}, (_,i)=>{
            const a = (i / (kind === 'pow' ? 14 : kind === 'boom' ? 12 : 10)) * Math.PI * 2;
            const r1 = (W/2) * 0.55, r2 = (W/2) * 0.95;
            return (
              <line key={i}
                    x1={Math.cos(a)*r1} y1={Math.sin(a)*r1}
                    x2={Math.cos(a)*r2} y2={Math.sin(a)*r2}
                    stroke="#ffffff" strokeWidth="2.4" strokeLinecap="round"/>
            );
          })}
          {/* cloud body — irregular path */}
          <g transform={`translate(-${W/2} -${H/2}) scale(${W/(kind==='pow'?380:kind==='boom'?420:360)} ${H/(kind==='pow'?220:kind==='boom'?240:200)})`}>
            <path d={CLOUD_PATHS[kind]} fill={cloudColorDark}/>
            <path d={CLOUD_PATHS[kind]} fill={cloudColor} transform="translate(0 -4)"/>
            <path d={CLOUD_PATHS[kind]} fill="#f0f0f0" opacity=".4" transform="translate(0 -10)"/>
          </g>
          {/* sparks */}
          {Array.from({length: kind === 'pow' ? 12 : kind === 'boom' ? 14 : 8}, (_,i) => {
            const a = (i / (kind === 'pow' ? 12 : kind === 'boom' ? 14 : 8)) * Math.PI * 2 + 0.3;
            const r = (W/2) * 0.7;
            const sx = Math.cos(a) * r, sy = Math.sin(a) * r;
            return (
              <g key={i} style={{ transformOrigin: '0 0',
                animation: `a10-spark ${0.9 + (i%4)*0.15}s cubic-bezier(.4,0,.2,1) infinite ${i*0.07}s`,
                ['--sx']: `${sx}px`, ['--sy']: `${sy}px` }}>
                <path d={`M 0 -8 L 2 0 L 0 8 L -2 0 Z`} fill={sparkColor}/>
              </g>
            );
          })}
          {/* smoke (boom + crack) */}
          {(kind === 'boom' || kind === 'crack') && Array.from({length: 5}, (_,i) => (
            <ellipse key={i} cx={(i-2)*22} cy={-H/2 + 10}
                     rx="14" ry="10" fill="#a8a8a8" opacity=".5"
                     style={{ animation: `a10-smoke-rise ${2.2 + (i%3)*0.3}s ease-out infinite ${i*0.4}s`, transformOrigin: 'center' }}/>
          ))}
          {/* limb-pokes */}
          {limbs.map((l, i) => (
            <g key={i} className="limb-poke"
               style={{
                 transformOrigin: '0 0',
                 ['--lx']: `${l.lx}px`, ['--ly']: `${l.ly}px`, ['--lr']: l.lr,
                 animation: `a10-limb-out ${1.6}s cubic-bezier(.4,0,.2,1) infinite ${0.32 + i*0.05}s`,
               }}>
              {l.d}
            </g>
          ))}
        </svg>
        {/* error text overlay for crack */}
        {kind === 'crack' && (
          <div style={{ position:'absolute', left:'62%', top:'10%',
                        fontFamily:'JetBrains Mono, ui-monospace, monospace', fontSize:11, color:'#ff3030',
                        animation:'a10-fade-in 0.4s ease-out 0.5s both' }}>
            <div>{'>>> ERROR'}</div>
            <div>FAIL 1/412</div>
            <div>{'schema_drift'}</div>
          </div>
        )}
        {/* onomatopée */}
        <Onomatopee text={onom.text} x={W/2 - 60} y={-20} color={onom.color} stroke={onom.stroke} size={onom.size}/>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────
  //  EXPORT keyframes once + components on window
  // ─────────────────────────────────────────────────────────
  if (!document.getElementById('a10-keyframes')) {
    const styleEl = document.createElement('style');
    styleEl.id = 'a10-keyframes';
    styleEl.textContent = KEYFRAMES;
    document.head.appendChild(styleEl);
  }

  export { Avatar, AvatarMini, P, FightCloud, Onomatopee, mixColor };
