/* ============================================================
   IX. CODE — Y2K AMBER CRT
   Phosphor amber, scanlines, ASCII headers, BBS energy
   ============================================================ */
function CodeV3() {
  return (
    <div style={{
      width: '100%', height: '100%', background: '#0a0500', color: '#ffb947',
      fontFamily: 'IBM Plex Mono, JetBrains Mono, Courier New, monospace', fontSize: 13,
      padding: 24, position: 'relative', overflow: 'hidden',
      display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20
    }}>
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 10,
        background: 'repeating-linear-gradient(0deg, transparent 0 2px, rgba(0,0,0,0.35) 2.5px, transparent 3px)' }}/>
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 11,
        background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.7) 110%)' }}/>

      <div style={{ gridColumn: '1 / -1', borderBottom: '1px solid #5a3a14', paddingBottom: 6, fontSize: 11, display: 'flex', justifyContent: 'space-between' }}>
        <span>╔══ AURORA.CODEX ══ TERM/3 ══ AMBER ══</span>
        <span>USR:MASTER  MEM:24576K  9600 BAUD</span>
      </div>

      {[
        { name: 'LLAMA70B', cur: true },
        { name: 'MISTRAL.L', cur: false }
      ].map((m, mi) => (
        <div key={m.name} style={{ border: '1px solid #5a3a14', padding: 14, position: 'relative', background: 'rgba(255,185,71,0.02)' }}>
          <div style={{ fontSize: 10, marginBottom: 8, color: m.cur ? '#ffb947' : '#a87a3a' }}>
            {`> MODEL: ${m.name} ${m.cur ? '[★ ACTIVE]' : '[compare]'}`}
          </div>
          <pre style={{ margin: 0, lineHeight: 1.55, color: '#ffb947', whiteSpace: 'pre-wrap' }}>
{`#!/usr/bin/env python
"""diffuse the bamboo"""
import torch
from aurora import unet, sched

def diffuse(img, steps=50):
    x = torch.randn_like(img)
    for t in reversed(range(steps)):
        ${mi === 0 ? 'eps = unet(x, t)' : 'eps = model(x, t, ctx)'}
        ${mi === 0 ? 'x = sched.step(eps,t,x)' : 'x = sched.prev(eps,t,x)'}
    return ${mi === 0 ? 'decode(x)' : 'x.cpu()'}

# main
img = load("bamboo.png")
out = diffuse(img)
save(out, "out.png")  ${mi === 0 ? '# OK' : '# CHECK'}`}
          </pre>
          <div style={{ marginTop: 10, fontSize: 10, display: 'flex', justifyContent: 'space-between', borderTop: '1px dashed #5a3a14', paddingTop: 8 }}>
            <span>TOK {mi === 0 ? '142' : '128'}</span>
            <span>LAT {mi === 0 ? '0.31s' : '0.42s'}</span>
            <span style={{ color: mi === 0 ? '#7df9c4' : '#c44' }}>{mi === 0 ? 'PASS ✓' : 'WARN'}</span>
          </div>
        </div>
      ))}

      <div style={{ gridColumn: '1 / -1', border: '1px solid #5a3a14', padding: 14, fontSize: 12 }}>
        <div style={{ fontSize: 10, color: '#a87a3a', marginBottom: 6 }}>{'> DIFF.HUNK [merged]'}</div>
        <pre style={{ margin: 0, lineHeight: 1.55 }}>
{`@@ -3,5 +3,7 @@ def diffuse(img, steps=50):
-    x = torch.zeros_like(img)
+    x = torch.randn_like(img)            `}<span style={{color:'#7df9c4'}}>{`# noise init`}</span>{`
     for t in reversed(range(steps)):
         eps = unet(x, t)
+        eps = guidance(eps, gamma=7.5)   `}<span style={{color:'#7df9c4'}}>{`# CFG`}</span>{`
         x = sched.step(eps, t, x)`}
        </pre>
      </div>

      <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 14, fontSize: 11 }}>
        <span>{'>_ '}<span style={{ animation: 'blink 1s steps(2) infinite' }}>█</span></span>
        <span style={{ color: '#a87a3a' }}>F1 HELP · F2 ACCEPT · F3 REJECT · F4 NEXT · ESC EXIT</span>
      </div>
      <style>{`@keyframes blink { 50% { opacity: 0 } }`}</style>
    </div>
  );
}

/* ============================================================
   X. CYBER — TACTICAL WAR ROOM
   Red on black, coordinates, threat board, alerts
   ============================================================ */
function CyberV3() {
  const [t, setT] = React.useState(0);
  React.useEffect(() => { let r; const l = () => { setT(performance.now()/1000); r = requestAnimationFrame(l); }; r = requestAnimationFrame(l); return () => cancelAnimationFrame(r); }, []);
  return (
    <div style={{
      width: '100%', height: '100%', background: '#0a0204',
      color: '#ff4a4a', fontFamily: 'Space Mono, JetBrains Mono, monospace', fontSize: 12,
      padding: 18, display: 'grid', gridTemplateColumns: '260px 1fr 280px', gridTemplateRows: '36px 1fr 100px', gap: 12,
      position: 'relative', overflow: 'hidden'
    }}>
      {/* alert bar */}
      <header style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: '#400808', border: '1px solid #ff4a4a', padding: '6px 14px', letterSpacing: '0.3em' }}>
        <span style={{ animation: 'pulse 1.2s ease-in-out infinite' }}>◢ DEFCON 3 ◣  KATA · MR. ROBOT  ◢ ARMED ◣</span>
        <span style={{ color: '#ffb947' }}>{new Date().toISOString().slice(11, 19)}Z</span>
      </header>

      {/* threat list */}
      <aside style={{ border: '1px solid #5a1414', padding: 10 }}>
        <div style={{ color: '#ff8080', fontSize: 10, letterSpacing: '0.2em', marginBottom: 8 }}>// THREAT.MATRIX</div>
        {[
          ['MD5', 'cracked', 'CRIT'],
          ['SHA1', 'weak', 'HIGH'],
          ['BCRYPT', 'safe', 'OK'],
          ['ARGON2', 'safe', 'OK'],
          ['PLAIN', 'leaked', 'CRIT'],
        ].map(([k, s, lvl]) => (
          <div key={k} style={{ display: 'grid', gridTemplateColumns: '70px 1fr 50px', padding: '5px 0', borderBottom: '1px dashed #5a1414', fontSize: 11 }}>
            <span style={{ color: '#ff8080' }}>{k}</span>
            <span style={{ color: '#cc8c8c', fontStyle: 'italic' }}>{s}</span>
            <span style={{ color: lvl === 'OK' ? '#7df9c4' : lvl === 'HIGH' ? '#ffb947' : '#ff4a4a', textAlign: 'right' }}>{lvl}</span>
          </div>
        ))}
        <div style={{ marginTop: 14, color: '#ff8080', fontSize: 10, letterSpacing: '0.2em' }}>// CORPUS</div>
        <div style={{ fontSize: 10, color: '#cc8c8c', marginTop: 6, lineHeight: 1.6 }}>
          rockyou.txt · 14 344 391<br/>
          common-passwd · 1M<br/>
          aurora.heur · custom
        </div>
      </aside>

      {/* main: terminal kata */}
      <main style={{ border: '1px solid #5a1414', padding: 14, background: '#1a0408', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div style={{ color: '#ff8080', fontSize: 10, letterSpacing: '0.2em', marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
          <span>// DOJO.SESSION · 0xKATA-04</span>
          <span style={{ color: '#ffb947' }}>SCORE 8420 · STREAK 12</span>
        </div>
        <pre style={{ margin: 0, fontSize: 12, lineHeight: 1.7, color: '#ff8080', flex: 1 }}>
{`master@aurora:~$ aurora dojo --kata robot
┌── target hash :: a1b2c3d4e5f6...0341
├── ${'▓'.repeat(Math.round(20 + Math.sin(t*2)*5))}${'░'.repeat(Math.max(0, 20 - Math.round(20 + Math.sin(t*2)*5)))} 64%
├── corpus     :: rockyou.txt [INDEXED]
├── strategy   :: heuristic + dictionary
├── attempts   :: 421,338 / s
└── eta        :: 00:00:14`}
        </pre>
        <div style={{ marginTop: 'auto', fontSize: 12, color: '#7df9c4' }}>
          → CRACKED · "mrR0b0t!" · 0.42s<span style={{ animation: 'blink 1s steps(2) infinite' }}>█</span>
        </div>
        <div style={{ marginTop: 10, padding: 10, background: '#0a0204', border: '1px dashed #5a1414', color: '#ffb947', fontStyle: 'italic', fontSize: 12, lineHeight: 1.5 }}>
          ⚠ leçon — un MD5 fond sous une rainbow table. salez vos formules, allongez vos passages, préférez Argon2id.
        </div>
      </main>

      {/* leaderboard / ops */}
      <aside style={{ border: '1px solid #5a1414', padding: 10 }}>
        <div style={{ color: '#ff8080', fontSize: 10, letterSpacing: '0.2em', marginBottom: 8 }}>// LEADERBOARD</div>
        {[
          ['01', 'MASTER', 'XII°', '#ff4a4a'],
          ['02', 'AURORA', 'IX°', '#ffb947'],
          ['03', 'COGITO', 'VII°', '#cc8c8c'],
          ['04', 'LAMBDA', 'V°', '#cc8c8c'],
          ['05', 'OBLIVION', 'III°', '#cc8c8c'],
        ].map(([n, who, xp, c]) => (
          <div key={n} style={{ display: 'grid', gridTemplateColumns: '24px 1fr 40px', padding: '6px 0', borderBottom: '1px dashed #5a1414' }}>
            <span style={{ color: c }}>{n}</span>
            <span style={{ color: c }}>{who}</span>
            <span style={{ color: c, textAlign: 'right' }}>{xp}</span>
          </div>
        ))}
        <div style={{ marginTop: 14, color: '#ff8080', fontSize: 10, letterSpacing: '0.2em' }}>// OPS</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 6 }}>
          {['ARM', 'ABORT', 'NEXT', 'HINT'].map(b => (
            <button key={b} style={{ background: 'transparent', border: '1px solid #ff4a4a', color: '#ff4a4a', padding: '8px 0', fontFamily: 'inherit', fontSize: 10, letterSpacing: '0.2em', cursor: 'pointer' }}>[{b}]</button>
          ))}
        </div>
      </aside>

      {/* bottom: log */}
      <footer style={{ gridColumn: '1 / -1', border: '1px solid #5a1414', padding: '8px 14px', fontSize: 10, color: '#cc8c8c', overflow: 'hidden' }}>
        <div style={{ color: '#ff8080', letterSpacing: '0.2em', marginBottom: 4 }}>// SECURE.LOG</div>
        <div>14:02:01 ► sandbox spawned · pid 0x4421 · isolated</div>
        <div>14:02:03 ► no network egress · all ops local · ✓</div>
        <div>14:02:14 ► hash table loaded · 14M entries · 220MiB</div>
        <div style={{ color: '#7df9c4' }}>14:02:14 ► kata RESOLVED · sealed in grimoire</div>
      </footer>

      <style>{`@keyframes pulse { 50% { opacity: 0.5 } } @keyframes blink { 50% { opacity: 0 } }`}</style>
    </div>
  );
}

/* ============================================================
   MOBILE V3 — RICOCHET
   Stacked cards with extreme variety per module preview
   ============================================================ */
function MobileV3() {
  return (
    <div style={{
      width: 380, height: 800, background: '#0a0a0a', color: '#fff',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      fontFamily: 'Helvetica Neue, Arial, sans-serif', position: 'relative'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '14px 20px 6px', fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: '#999' }}>
        <span>14:02</span>
        <span>AURORA · POLY</span>
        <span>87%</span>
      </div>
      <div style={{ padding: '8px 20px 14px' }}>
        <div style={{ fontSize: 11, letterSpacing: '0.3em', color: '#888' }}>10 IDENTITÉS</div>
        <div style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 32, marginTop: 2 }}>polyphonie</div>
      </div>

      <div style={{ flex: 1, padding: '0 20px 20px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* card 1 — radar */}
        <div style={{ borderRadius: 0, border: '1px solid #15524d', background: '#031a1a', padding: 14, color: '#7df9c4', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>
          <div style={{ letterSpacing: '0.2em' }}>I · MISSION CTRL</div>
          <svg viewBox="0 0 200 80" width="100%" height="50"><circle cx="100" cy="40" r="34" fill="none" stroke="#15524d"/><circle cx="100" cy="40" r="2" fill="#7df9c4"/><circle cx="130" cy="30" r="2" fill="#ffb938"/><line x1="100" y1="40" x2="140" y2="20" stroke="#7df9c4" strokeOpacity="0.5"/></svg>
          <div style={{ color: '#3eb89b' }}>4 agents · ETA 14m</div>
        </div>

        {/* card 2 — typewriter */}
        <div style={{ background: '#f0e9d9', color: '#1c1614', padding: 14, fontFamily: 'Courier New, monospace', fontSize: 11, lineHeight: 1.6, border: '2px solid #1c1614' }}>
          <div style={{ letterSpacing: '0.2em', borderBottom: '1px solid', paddingBottom: 4, marginBottom: 6 }}>II · DICTAPHONE</div>
          <div>EXPLIQUE-MOI LA <span style={{ background: '#fff7a8' }}>DIFFUSION</span></div>
          <div>EN VOCABULAIRE SUMI-E.<span style={{ animation: 'caret 1s steps(2) infinite' }}>█</span></div>
        </div>

        {/* card 3 — studio */}
        <div style={{ background: '#1a1a1a', color: '#e8d8a8', padding: 14, border: '1px solid #5a4a2a' }}>
          <div style={{ fontSize: 11, letterSpacing: '0.2em', color: '#8a7a4a' }}>III · STUDIO</div>
          <div style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 22, marginTop: 4 }}>vox</div>
          <svg width="100%" height="30" viewBox="0 0 300 30">
            {Array.from({ length: 60 }).map((_, i) => {
              const h = 4 + Math.abs(Math.sin(i * 0.5)) * 14;
              return <rect key={i} x={i * 5} y={15 - h/2} width="2" height={h} fill="#a8231d"/>;
            })}
          </svg>
        </div>

        {/* card 4 — polaroid */}
        <div style={{ background: '#b8956b', padding: 14, position: 'relative', minHeight: 140 }}>
          <div style={{ fontSize: 11, letterSpacing: '0.2em', fontFamily: 'JetBrains Mono, monospace', color: '#1a1410' }}>IV · LIGHTBOX</div>
          <div style={{ position: 'absolute', top: 30, left: 20, width: 90, padding: '6px 6px 18px', background: '#fbf6e8', transform: 'rotate(-4deg)', boxShadow: '0 4px 8px rgba(0,0,0,0.3)' }}>
            <div style={{ aspectRatio: '1', background: '#1a1410' }}/>
            <div style={{ fontFamily: 'Permanent Marker, cursive', fontSize: 9, marginTop: 2, color: '#1a1410' }}>bambou</div>
          </div>
          <div style={{ position: 'absolute', top: 36, left: 130, width: 90, padding: '6px 6px 18px', background: '#fbf6e8', transform: 'rotate(3deg)', boxShadow: '0 4px 8px rgba(0,0,0,0.3)' }}>
            <div style={{ aspectRatio: '1', background: '#2a1f15' }}/>
            <div style={{ fontFamily: 'Permanent Marker, cursive', fontSize: 9, marginTop: 2, color: '#1a1410' }}>grue</div>
          </div>
        </div>

        {/* card 5 — blueprint */}
        <div style={{ background: '#0c2944', color: '#cce8ff', padding: 14, fontFamily: 'Courier New, monospace', fontSize: 11,
          backgroundImage: 'linear-gradient(rgba(120,200,255,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(120,200,255,0.07) 1px, transparent 1px)',
          backgroundSize: '20px 20px' }}>
          <div style={{ letterSpacing: '0.2em' }}>VI · BLUEPRINT</div>
          <svg viewBox="0 0 200 60" width="100%" height="40">
            <rect x="60" y="10" width="80" height="40" fill="none" stroke="#7dc8ff"/>
            <line x1="60" y1="50" x2="140" y2="10" stroke="#7dc8ff" strokeDasharray="2 2"/>
          </svg>
          <div>verts 24,614 · faces 12,308</div>
        </div>

        {/* card 6 — sketchbook */}
        <div style={{ background: '#faf2e0', color: '#2a1f15', padding: 14, fontFamily: 'Caveat, cursive', fontSize: 18, transform: 'rotate(-0.5deg)' }}>
          <div style={{ fontSize: 11, letterSpacing: '0.2em', fontFamily: 'JetBrains Mono, monospace' }}>VII · L'ATELIER</div>
          <div style={{ fontSize: 24 }}>aurora suggère :</div>
          <span style={{ color: '#a8231d', borderBottom: '2px solid #a8231d' }}>épaissir le tronc</span>
        </div>
      </div>
      <style>{`@keyframes caret { 50% { opacity: 0 } }`}</style>
    </div>
  );
}

window.CodeV3 = CodeV3;
window.CyberV3 = CyberV3;
window.MobileV3 = MobileV3;
