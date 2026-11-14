/* ============================================================
   AURORA · POLYPHONIE — v3
   Each module has its OWN aesthetic. No unifying system.
   Self-contained, no external dependencies.
   ============================================================ */

/* ============================================================
   I. COWORK — MISSION CONTROL HUD
   Phosphor green on deep teal, radar sweep, callsigns
   ============================================================ */
function CoworkV3() {
  const [t, setT] = React.useState(0);
  React.useEffect(() => {
    let raf;
    const loop = () => { setT(performance.now() / 1000); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);
  const sweep = (t * 60) % 360;
  return (
    <div style={{
      width: '100%', height: '100%', background: '#031a1a', color: '#7df9c4',
      fontFamily: 'JetBrains Mono, monospace', fontSize: 12, padding: 20,
      display: 'grid', gridTemplateColumns: '300px 1fr 280px', gridTemplateRows: '40px 1fr 120px',
      gap: 12, position: 'relative', overflow: 'hidden'
    }}>
      {/* scanlines */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(0,0,0,0.25) 2.5px, transparent 3px)',
        zIndex: 10 }}/>
      {/* CRT vignette */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at center, transparent 50%, #000 110%)', zIndex: 11 }}/>

      {/* top bar */}
      <header style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        borderBottom: '1px solid #15524d', paddingBottom: 6, color: '#7df9c4' }}>
        <span>▣ AURORA / MISSIONCTRL · ORBIT 0341 · COWORK</span>
        <span>UTC {new Date().toISOString().slice(11, 19)} · LIVE</span>
        <span style={{ color: '#ffb938' }}>● ARMED</span>
      </header>

      {/* left: agent roster */}
      <div style={{ border: '1px solid #15524d', padding: 12, fontSize: 11 }}>
        <div style={{ color: '#3eb89b', marginBottom: 10 }}>// AGENT_ROSTER</div>
        {[
          ['CDX-01', 'CODEX', 'LLAMA-70B', 'NOM', '#ffb938'],
          ['PCT-04', 'PICTURA', 'SDXL-1.0', 'GEN', '#7df9c4'],
          ['SCH-02', 'SCHOLA', 'MISTRAL-L', 'RDY', '#3eb89b'],
          ['CST-01', 'CUSTODIA', 'LOCAL', 'HOLD', '#ffb938'],
          ['VOX-03', 'VOX', 'KOKORO', 'IDLE', '#3eb89b'],
        ].map(([id, n, m, s, c]) => (
          <div key={id} style={{ display: 'grid', gridTemplateColumns: '60px 1fr 38px', padding: '6px 0',
            borderBottom: '1px dashed #15524d', alignItems: 'baseline' }}>
            <span style={{ color: '#3eb89b' }}>{id}</span>
            <span><span style={{ color: '#7df9c4' }}>{n}</span> <span style={{ color: '#3eb89b', fontSize: 9 }}>{m}</span></span>
            <span style={{ color: c, textAlign: 'right' }}>{s}</span>
          </div>
        ))}
        <div style={{ marginTop: 14, color: '#3eb89b' }}>// THROUGHPUT</div>
        <div style={{ marginTop: 6 }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
              <span style={{ color: '#3eb89b' }}>T+{i}m</span>
              <span style={{ fontFamily: 'JetBrains Mono' }}>
                {'█'.repeat(Math.max(2, Math.round(8 + Math.sin(t + i) * 6)))}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* center: radar */}
      <div style={{ border: '1px solid #15524d', position: 'relative', overflow: 'hidden' }}>
        <svg viewBox="0 0 400 400" width="100%" height="100%" style={{ display: 'block' }}>
          {[40,80,120,160,200].map(r => <circle key={r} cx="200" cy="200" r={r} fill="none" stroke="#15524d" strokeWidth="1"/>)}
          {[0,30,60,90,120,150].map(a => {
            const ra = a * Math.PI / 180;
            return <line key={a} x1={200 - Math.cos(ra)*200} y1={200 - Math.sin(ra)*200}
              x2={200 + Math.cos(ra)*200} y2={200 + Math.sin(ra)*200} stroke="#15524d" strokeWidth="0.5"/>;
          })}
          {/* sweep */}
          <defs>
            <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#7df9c4" stopOpacity="0.5"/>
              <stop offset="100%" stopColor="#7df9c4" stopOpacity="0"/>
            </linearGradient>
          </defs>
          <path d={`M 200 200 L ${200 + Math.cos(sweep*Math.PI/180)*200} ${200 + Math.sin(sweep*Math.PI/180)*200} A 200 200 0 0 0 ${200 + Math.cos((sweep-40)*Math.PI/180)*200} ${200 + Math.sin((sweep-40)*Math.PI/180)*200} Z`}
            fill="url(#sweep)" opacity="0.6"/>
          {/* blips */}
          {[
            [120, 90, 'CDX-01'], [260, 140, 'PCT-04'], [180, 280, 'SCH-02'], [310, 250, 'CST-01']
          ].map(([x, y, lbl]) => (
            <g key={lbl}>
              <circle cx={x} cy={y} r="4" fill="#ffb938"/>
              <circle cx={x} cy={y} r="10" fill="none" stroke="#ffb938" opacity={0.4 + 0.4*Math.sin(t*3 + x)}/>
              <text x={x + 14} y={y + 4} fontSize="10" fill="#ffb938" fontFamily="JetBrains Mono">{lbl}</text>
            </g>
          ))}
          <circle cx="200" cy="200" r="6" fill="#7df9c4"/>
          <text x="200" y="395" textAnchor="middle" fontSize="9" fill="#3eb89b" fontFamily="JetBrains Mono">RANGE 200KM · BEARING {Math.round(sweep)}°</text>
        </svg>
      </div>

      {/* right: telemetry */}
      <div style={{ border: '1px solid #15524d', padding: 12, fontSize: 11 }}>
        <div style={{ color: '#3eb89b', marginBottom: 10 }}>// TELEMETRY</div>
        {[
          ['VRAM', 22.4, 32, 'GiB'],
          ['CPU', 41, 100, '%'],
          ['NET', 0, 100, 'kb/s', true],
          ['TOK', 47218, 100000, ''],
        ].map(([k, v, max, u, off]) => (
          <div key={k} style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#3eb89b' }}>{k}</span>
              <span style={{ color: off ? '#ffb938' : '#7df9c4' }}>{off ? 'OFFLN' : `${v}${u}`}</span>
            </div>
            <div style={{ height: 8, background: '#0a2a26', marginTop: 4, position: 'relative' }}>
              <div style={{ position: 'absolute', inset: 0, width: `${(v/max)*100}%`, background: off ? '#ffb938' : '#7df9c4', opacity: 0.6 }}/>
            </div>
          </div>
        ))}
        <div style={{ color: '#3eb89b', margin: '14px 0 6px' }}>// MISSION_LOG</div>
        <div style={{ fontSize: 10, lineHeight: 1.6 }}>
          <div>04:21:08 ► CDX recv corpus[47]</div>
          <div>04:21:14 ► PCT gen sketch[12]</div>
          <div>04:21:21 ► SCH propose draft</div>
          <div style={{ color: '#ffb938' }}>04:21:24 ► CST verify clean ✓</div>
          <div style={{ animation: 'blink 1s infinite' }}>04:21:31 ► _</div>
        </div>
      </div>

      {/* bottom: command */}
      <footer style={{ gridColumn: '1 / -1', border: '1px solid #15524d', padding: 10, display: 'grid', gridTemplateColumns: '1fr auto', gap: 12 }}>
        <div>
          <div style={{ color: '#3eb89b', fontSize: 10 }}>&gt; MISSION_BRIEF</div>
          <div style={{ color: '#7df9c4', fontSize: 13, marginTop: 4 }}>
            CARTOGRAPHIE.DIFFUSION_SUMI-E :: 4 AGENTS :: 47 SOURCES :: ETA 00:14:22
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {['ABORT', 'PAUSE', 'EXEC'].map((b, i) => (
            <button key={b} style={{
              background: i === 2 ? '#7df9c4' : 'transparent', color: i === 2 ? '#031a1a' : '#7df9c4',
              border: '1px solid #7df9c4', padding: '8px 18px', fontFamily: 'inherit', fontSize: 11, cursor: 'pointer'
            }}>[{b}]</button>
          ))}
        </div>
      </footer>
      <style>{`@keyframes blink { 50% { opacity: 0 } }`}</style>
    </div>
  );
}

/* ============================================================
   II. CHAT — TYPEWRITER / CARBON COPY
   Onion-skin paper, courier, red corrections, carriage returns
   ============================================================ */
function ChatV3() {
  return (
    <div style={{
      width: '100%', height: '100%', background: '#f0e9d9',
      fontFamily: 'Courier New, Courier, monospace', color: '#1c1614',
      padding: 28, position: 'relative', display: 'flex', flexDirection: 'column',
      backgroundImage: 'repeating-linear-gradient(0deg, transparent 0, transparent 27px, rgba(28,30,80,0.08) 27px, rgba(28,30,80,0.08) 28px)'
    }}>
      {/* paper holes */}
      <div style={{ position: 'absolute', left: 14, top: 0, bottom: 0, width: 24, display: 'flex', flexDirection: 'column', justifyContent: 'space-around', padding: '40px 0' }}>
        {Array.from({ length: 14 }).map((_, i) => (
          <div key={i} style={{ width: 14, height: 14, borderRadius: '50%', background: '#d4cab8', boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.3)' }}/>
        ))}
      </div>
      {/* red margin line */}
      <div style={{ position: 'absolute', left: 80, top: 0, bottom: 0, width: 1, background: '#c44' }}/>

      <div style={{ marginLeft: 70, flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* letterhead */}
        <div style={{ borderBottom: '2px solid #1c1614', paddingBottom: 8, marginBottom: 24, display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontWeight: 700, letterSpacing: '0.3em', fontSize: 14 }}>AURORA — DICTAPHONE</span>
          <span style={{ fontSize: 11 }}>FILE No. 062 / 2026 · CARBON COPY</span>
        </div>

        <div style={{ flex: 1, fontSize: 14, lineHeight: 28, overflow: 'hidden' }}>
          <div style={{ marginBottom: 16 }}>
            <span style={{ background: '#1c1614', color: '#f0e9d9', padding: '0 6px', marginRight: 8, fontWeight: 700 }}>FROM</span>
            LE MAITRE &nbsp;·&nbsp;
            <span style={{ background: '#1c1614', color: '#f0e9d9', padding: '0 6px', margin: '0 8px', fontWeight: 700 }}>TIME</span>
            14:02:17
          </div>
          <p style={{ margin: '0 0 8px', maxWidth: '70ch' }}>
            EXPLIQUE-MOI LA <span style={{ textDecoration: 'underline wavy #c44' }}>DIFFUSION LATENTE</span> EN
          </p>
          <p style={{ margin: '0 0 8px', maxWidth: '70ch' }}>
            EMPRUNTANT LE VOCABULAIRE DE LA PEINTURE SUMI-E.
          </p>

          <div style={{ display: 'flex', alignItems: 'center', margin: '20px 0 12px', gap: 8 }}>
            <span style={{ flex: 1, height: 0, borderTop: '1px dashed #1c1614' }}/>
            <span style={{ fontSize: 10, letterSpacing: '0.3em' }}>RETOUR CHARIOT</span>
            <span style={{ flex: 1, height: 0, borderTop: '1px dashed #1c1614' }}/>
          </div>

          <div style={{ marginBottom: 16 }}>
            <span style={{ background: '#c44', color: '#f0e9d9', padding: '0 6px', marginRight: 8, fontWeight: 700 }}>FROM</span>
            <span style={{ color: '#c44' }}>AURORA</span> &nbsp;·&nbsp;
            <span style={{ background: '#c44', color: '#f0e9d9', padding: '0 6px', margin: '0 8px', fontWeight: 700 }}>MOD</span>
            LLAMA-3.1-70B
          </div>
          <p style={{ margin: '0 0 8px', maxWidth: '70ch', position: 'relative' }}>
            IMAGINEZ QUE L'ENCRE, DEPOSEE SUR LE PAPIER DE RIZ, NE
          </p>
          <p style={{ margin: '0 0 8px', maxWidth: '70ch' }}>
            DECRIT PAS UN TRAIT MAIS UN <span style={{ background: '#fff7a8' }}>CHAMP DE PROBABILITES</span>.
          </p>
          <p style={{ margin: '0 0 8px', maxWidth: '70ch' }}>
            LE MODELE COMMENCE PAR UN NUAGE INFORME — UN PAPIER
          </p>
          <p style={{ margin: '0 0 8px', maxWidth: '70ch', position: 'relative' }}>
            <span style={{ textDecoration: 'line-through' }}>BARBOUILLE</span> <span style={{ position: 'absolute', top: -16, marginLeft: -180, color: '#c44', fontSize: 11, fontStyle: 'italic' }}>↑ corr.</span> MACULE DE BRUIT GAUSSIEN. A CHAQUE PASSE, IL
          </p>
          <p style={{ margin: '0 0 8px', maxWidth: '70ch' }}>
            RETIRE UN PEU DE BRUIT COMME UN BUVARD ABSORBE
          </p>
          <p style={{ margin: '0 0 8px', maxWidth: '70ch' }}>
            L'HUMIDITE, JUSQU'A REVELER LA FORME CACHEE.<span style={{ animation: 'caret 1s steps(2) infinite', marginLeft: 4, fontWeight: 700 }}>█</span>
          </p>

          <div style={{ position: 'absolute', right: 60, top: 100, transform: 'rotate(-8deg)', border: '3px double #c44', padding: '6px 14px', color: '#c44', fontWeight: 700, letterSpacing: '0.2em', fontSize: 12 }}>
            VU PAR LE MAITRE
          </div>
        </div>

        {/* compose */}
        <div style={{ borderTop: '2px solid #1c1614', paddingTop: 12, marginTop: 12, display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <span style={{ background: '#1c1614', color: '#f0e9d9', padding: '0 6px', fontWeight: 700, fontSize: 11 }}>TYPE&gt;</span>
          <span style={{ flex: 1, fontSize: 14, color: '#666' }}>_______________________________________________</span>
          <span style={{ fontSize: 11, letterSpacing: '0.2em' }}>SHIFT+ENTER</span>
        </div>
      </div>
      <style>{`@keyframes caret { 50% { opacity: 0 } }`}</style>
    </div>
  );
}

window.CoworkV3 = CoworkV3;
window.ChatV3 = ChatV3;
