/* ============================================================
   III. VOICE — STUDIO MIXER / TAPE REELS
   Black mat, brass knobs, VU needles, magnetic tape
   ============================================================ */
function VoiceV3() {
  const [t, setT] = React.useState(0);
  React.useEffect(() => {
    let raf;
    const loop = () => { setT(performance.now() / 1000); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);
  const needle = -45 + Math.sin(t * 4) * 20 + 30;

  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'linear-gradient(180deg, #1a1a1a 0%, #0d0d0d 100%)',
      color: '#e8d8a8', fontFamily: 'Helvetica Neue, Arial, sans-serif',
      padding: 24, display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: 'auto 1fr auto', gap: 18
    }}>
      {/* brand plate */}
      <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        borderBottom: '2px solid #5a4a2a', paddingBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
          <span style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 32, color: '#e8d8a8' }}>Aurora</span>
          <span style={{ fontSize: 11, letterSpacing: '0.4em', color: '#8a7a4a' }}>STUDIO · MK III · VOX</span>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          {['REC', 'PLAY', 'PAUSE', 'STOP'].map((b, i) => (
            <button key={b} style={{
              width: 60, height: 32, background: i === 0 ? '#a8231d' : '#2a2a2a',
              border: '1px solid #444', color: '#fff', fontSize: 10, letterSpacing: '0.2em', cursor: 'pointer',
              boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.1), 0 2px 4px rgba(0,0,0,0.5)'
            }}>{b}</button>
          ))}
        </div>
      </div>

      {/* tape reels */}
      <div style={{ background: '#161616', border: '1px solid #2a2a2a', padding: 24, display: 'flex', justifyContent: 'space-around', alignItems: 'center', position: 'relative' }}>
        {[0, 1].map(i => (
          <div key={i} style={{ position: 'relative' }}>
            <div style={{
              width: 140, height: 140, borderRadius: '50%',
              background: 'radial-gradient(circle, #2a2418 0%, #1a1611 60%, #0a0808 100%)',
              border: '2px solid #5a4a2a',
              transform: `rotate(${t * 80 * (i ? -1 : 1)}deg)`,
              boxShadow: 'inset 0 0 20px rgba(0,0,0,0.8), 0 4px 16px rgba(0,0,0,0.6)'
            }}>
              {[0, 60, 120].map(a => (
                <div key={a} style={{
                  position: 'absolute', top: '50%', left: '50%',
                  width: 60, height: 4, background: '#5a4a2a',
                  transform: `translate(-50%, -50%) rotate(${a}deg)`,
                  borderRadius: 2
                }}/>
              ))}
              <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: 28, height: 28, borderRadius: '50%', background: '#0a0808', border: '1px solid #5a4a2a' }}/>
            </div>
            <div style={{ textAlign: 'center', marginTop: 8, fontSize: 10, letterSpacing: '0.3em', color: '#8a7a4a' }}>
              {i === 0 ? 'SOURCE' : 'TAKE-UP'}
            </div>
          </div>
        ))}
        {/* tape between reels */}
        <div style={{ position: 'absolute', left: '20%', right: '20%', top: '52%', height: 3, background: '#3a2f1a', boxShadow: '0 1px 0 #1a1611' }}/>
      </div>

      {/* VU meter + waveforms */}
      <div style={{ background: '#161616', border: '1px solid #2a2a2a', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* VU */}
        <div style={{ background: '#f0d890', border: '4px solid #1a1a1a', borderRadius: 6, padding: 10, position: 'relative', height: 100 }}>
          <svg viewBox="-100 -20 200 110" width="100%" height="100%">
            {/* arc */}
            <path d="M -80 80 A 80 80 0 0 1 80 80" fill="none" stroke="#1c1410" strokeWidth="0.6"/>
            {Array.from({ length: 11 }).map((_, i) => {
              const a = -90 + i * 18;
              const r = a * Math.PI / 180;
              const x1 = Math.sin(r) * 70, y1 = 80 - Math.cos(r) * 70;
              const x2 = Math.sin(r) * 80, y2 = 80 - Math.cos(r) * 80;
              return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={i > 7 ? '#a8231d' : '#1c1410'} strokeWidth={i % 5 === 0 ? 1.5 : 0.7}/>;
            })}
            {[-20, -10, -5, 0, '+3'].map((v, i) => {
              const a = -90 + i * 24 + 12;
              const r = a * Math.PI / 180;
              return <text key={v} x={Math.sin(r) * 56} y={80 - Math.cos(r) * 56 + 3} fontSize="6" fill={i > 3 ? '#a8231d' : '#1c1410'} textAnchor="middle">{v}</text>;
            })}
            <text x="0" y="14" textAnchor="middle" fontSize="7" fill="#1c1410" fontFamily="Georgia, serif" fontStyle="italic">VU</text>
            <line x1="0" y1="80" x2={Math.sin(needle*Math.PI/180)*72} y2={80 - Math.cos(needle*Math.PI/180)*72} stroke="#a8231d" strokeWidth="1.5"/>
            <circle cx="0" cy="80" r="3" fill="#1c1410"/>
          </svg>
        </div>
        <div style={{ fontSize: 10, letterSpacing: '0.3em', color: '#8a7a4a' }}>WAVEFORM · INPUT</div>
        <svg width="100%" height="40" viewBox="0 0 400 40">
          {Array.from({ length: 100 }).map((_, i) => {
            const h = 4 + Math.abs(Math.sin(i * 0.5 + t * 3)) * 16 + Math.random() * 4;
            return <rect key={i} x={i * 4} y={20 - h/2} width="2" height={h} fill="#e8d8a8" opacity={0.85}/>;
          })}
        </svg>
        <div style={{ fontSize: 10, letterSpacing: '0.3em', color: '#8a7a4a' }}>WAVEFORM · AURORA OUTPUT</div>
        <svg width="100%" height="40" viewBox="0 0 400 40">
          {Array.from({ length: 100 }).map((_, i) => {
            const h = 2 + Math.abs(Math.cos(i * 0.4 + t * 2)) * 12;
            return <rect key={i} x={i * 4} y={20 - h/2} width="2" height={h} fill="#a8231d" opacity={0.7}/>;
          })}
        </svg>
      </div>

      {/* knobs row */}
      <div style={{ gridColumn: '1 / -1', background: '#161616', border: '1px solid #2a2a2a', padding: 18, display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 8, alignItems: 'center' }}>
        {[
          ['GAIN', 64, '#e8d8a8'], ['HI', 40, '#e8d8a8'], ['MID', 50, '#e8d8a8'], ['LO', 70, '#e8d8a8'],
          ['REVERB', 25, '#e8d8a8'], ['SPEED', 50, '#e8d8a8'], ['PITCH', 50, '#e8d8a8'], ['VOL', 80, '#a8231d'],
        ].map(([label, val, color]) => {
          const angle = -135 + (val / 100) * 270;
          return (
            <div key={label} style={{ textAlign: 'center' }}>
              <div style={{
                width: 52, height: 52, margin: '0 auto', borderRadius: '50%',
                background: 'radial-gradient(circle at 30% 30%, #4a4a4a, #1a1a1a 60%, #0a0a0a)',
                border: '1px solid #5a4a2a', position: 'relative',
                boxShadow: 'inset 0 2px 4px rgba(255,255,255,0.05), 0 2px 6px rgba(0,0,0,0.6)'
              }}>
                <div style={{
                  position: 'absolute', left: '50%', top: '50%',
                  width: 2, height: 18, background: color,
                  transformOrigin: '50% 100%',
                  transform: `translate(-50%, -100%) rotate(${angle}deg)`
                }}/>
              </div>
              <div style={{ fontSize: 9, letterSpacing: '0.25em', color: '#8a7a4a', marginTop: 6 }}>{label}</div>
              <div style={{ fontSize: 10, color: '#e8d8a8', fontFamily: 'Georgia, serif' }}>{val}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ============================================================
   IV. IMAGE — POLAROID LIGHTBOX / CONTACT SHEET
   Cork board, washi tape, polaroids, sharpie
   ============================================================ */
function ImageV3() {
  const cards = [
    { rot: -3, x: 4, y: 4, prompt: 'Bambou souple sous la pluie, sumi-e' },
    { rot: 2, x: 26, y: 6, prompt: 'Grue pliée en équilibre, plume sèche' },
    { rot: -1, x: 50, y: 3, prompt: 'Mont Fuji à l\'aube, lithographie' },
    { rot: 4, x: 72, y: 8, prompt: 'Cascade et pin tordu, encre lavée' },
    { rot: -4, x: 6, y: 38, prompt: 'Carpes koï dans l\'étang noir' },
    { rot: 1, x: 28, y: 42, prompt: 'Pivoine ouverte, sanguine' },
    { rot: 3, x: 50, y: 40, prompt: 'Lanterne en papier, soir' },
    { rot: -2, x: 72, y: 44, prompt: 'Cerisier en fleurs, eau-forte' },
  ];
  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      background: '#b8956b',
      backgroundImage: `radial-gradient(circle at 25% 30%, rgba(0,0,0,0.18) 0.5px, transparent 1px),
                        radial-gradient(circle at 75% 60%, rgba(255,255,255,0.1) 0.5px, transparent 1px),
                        radial-gradient(circle at 40% 80%, rgba(0,0,0,0.14) 0.5px, transparent 1px)`,
      backgroundSize: '7px 7px, 11px 11px, 9px 9px',
      fontFamily: 'Georgia, serif'
    }}>
      {/* sharpie label top */}
      <div style={{ position: 'absolute', top: 24, left: 32, transform: 'rotate(-2deg)', fontFamily: 'Permanent Marker, Marker Felt, cursive', fontSize: 36, color: '#1a1410', textShadow: '0 1px 0 rgba(255,255,255,0.2)' }}>
        Aurora · Imago — planches d'essai
      </div>
      <div style={{ position: 'absolute', top: 78, left: 36, fontStyle: 'italic', fontSize: 14, color: '#3a2a1a' }}>
        FLUX 1.dev · seed 0xA3F1 · γ 7.5 — sélection du matin
      </div>

      {/* polaroids */}
      {cards.map((c, i) => (
        <div key={i} style={{
          position: 'absolute', left: `${c.x}%`, top: `${c.y + 18}%`,
          width: 200, padding: '10px 10px 38px', background: '#fbf6e8',
          boxShadow: '0 8px 22px rgba(0,0,0,0.35), 0 1px 0 rgba(0,0,0,0.1)',
          transform: `rotate(${c.rot}deg)`,
          border: '1px solid rgba(0,0,0,0.05)'
        }}>
          {/* washi tape */}
          <div style={{
            position: 'absolute', top: -14, left: '50%', transform: 'translateX(-50%) rotate(2deg)',
            width: 70, height: 26,
            background: i % 3 === 0 ? 'rgba(232,167,167,0.85)' : i % 3 === 1 ? 'rgba(167,200,232,0.85)' : 'rgba(220,232,167,0.85)',
            backgroundImage: 'repeating-linear-gradient(45deg, rgba(255,255,255,0.3) 0 4px, transparent 4px 8px)',
            boxShadow: '0 2px 4px rgba(0,0,0,0.15)'
          }}/>
          {/* image */}
          <div style={{
            aspectRatio: '1', background: '#1a1410',
            backgroundImage: `radial-gradient(circle at 40% 60%, rgba(255,255,255,0.04), transparent 50%),
                              radial-gradient(circle at ${30 + i*10}% ${50}%, rgba(255,250,240,0.5) 1%, transparent 30%)`,
            position: 'relative', overflow: 'hidden'
          }}>
            <svg viewBox="0 0 200 200" width="100%" height="100%">
              <path d={`M ${30 + i*5} 180 Q ${40 + i*4} 100 ${35 + i*4} 30`} stroke="#f0e8d0" strokeWidth={6} fill="none" opacity="0.85"/>
              <path d={`M ${30 + i*5} 130 L ${100} ${130 + i*2}`} stroke="#f0e8d0" strokeWidth={2} fill="none"/>
              <path d={`M ${30 + i*5} 80 L ${110} ${80 + i*2}`} stroke="#f0e8d0" strokeWidth={2} fill="none"/>
            </svg>
          </div>
          <div style={{ position: 'absolute', bottom: 8, left: 14, right: 14, fontFamily: 'Permanent Marker, Marker Felt, cursive', fontSize: 11, color: '#1a1410', lineHeight: 1.2 }}>
            {c.prompt}
          </div>
          <div style={{ position: 'absolute', bottom: 8, right: 14, fontSize: 9, color: '#8a6a4a' }}>
            #{String(i + 1).padStart(2, '0')}
          </div>
        </div>
      ))}

      {/* push pin */}
      <div style={{ position: 'absolute', top: 22, right: 40, width: 16, height: 16, borderRadius: '50%', background: 'radial-gradient(circle at 30% 30%, #ff9a8a, #c44a3a 60%, #6a1a14)', boxShadow: '0 3px 6px rgba(0,0,0,0.4)' }}/>

      {/* compose */}
      <div style={{ position: 'absolute', bottom: 24, left: 32, right: 32, background: '#1a1410', color: '#fbf6e8', padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 16, transform: 'rotate(-0.5deg)', boxShadow: '0 6px 18px rgba(0,0,0,0.4)' }}>
          <span style={{ fontFamily: 'Permanent Marker, Marker Felt, cursive', fontSize: 16 }}>✏  prompt :</span>
          <span style={{ flex: 1, fontStyle: 'italic', opacity: 0.7 }}>« décris la prochaine prise… »</span>
          <button style={{ background: '#fbf6e8', color: '#1a1410', border: 'none', padding: '8px 18px', fontFamily: 'Permanent Marker, Marker Felt, cursive', fontSize: 14, cursor: 'pointer' }}>TIRER 4</button>
      </div>
    </div>
  );
}

window.VoiceV3 = VoiceV3;
window.ImageV3 = ImageV3;
