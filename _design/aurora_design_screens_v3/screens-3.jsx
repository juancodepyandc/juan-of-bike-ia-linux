/* ============================================================
   V. VIDEO — STEENBECK FLATBED EDITOR
   Brushed steel, film strip, sprockets, mechanical
   ============================================================ */
function VideoV3() {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'linear-gradient(135deg, #6a6a6a 0%, #4a4a4a 50%, #5a5a5a 100%)',
      backgroundImage: 'repeating-linear-gradient(135deg, transparent 0 2px, rgba(0,0,0,0.04) 2px 3px)',
      padding: 20, display: 'grid', gridTemplateRows: '40px 1fr auto auto', gap: 16,
      fontFamily: 'Helvetica Neue, sans-serif', color: '#1a1a1a'
    }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '2px solid #2a2a2a', paddingBottom: 6 }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'baseline' }}>
          <span style={{ background: '#1a1a1a', color: '#f5f0d8', padding: '3px 10px', fontSize: 11, letterSpacing: '0.3em', fontWeight: 700 }}>STEENBECK</span>
          <span style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 22 }}>Aurora Cinematica</span>
        </div>
        <div style={{ display: 'flex', gap: 8, fontSize: 11 }}>
          <span style={{ background: '#a8231d', color: '#fff', padding: '3px 8px' }}>● REC</span>
          <span style={{ background: '#1a1a1a', color: '#f5f0d8', padding: '3px 8px' }}>00:04 / 00:08</span>
          <span style={{ background: '#1a1a1a', color: '#f5f0d8', padding: '3px 8px' }}>24fps</span>
        </div>
      </header>

      {/* viewer + scope */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 16 }}>
        <div style={{
          background: '#0a0a0a', border: '8px solid #2a2a2a', borderRadius: 4,
          boxShadow: 'inset 0 0 30px rgba(0,0,0,0.8), 0 6px 20px rgba(0,0,0,0.5)',
          position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <svg viewBox="0 0 400 220" width="100%" height="100%" style={{ filter: 'sepia(0.3) contrast(1.1)' }}>
            <defs><radialGradient id="moon" cx="70%" cy="30%"><stop offset="0%" stopColor="#f8e4a0"/><stop offset="100%" stopColor="#1a1410"/></radialGradient></defs>
            <rect width="400" height="220" fill="url(#moon)"/>
            <path d="M 0 180 Q 100 140 200 170 T 400 165 L 400 220 L 0 220 Z" fill="#0a0806"/>
            <path d="M 80 200 L 110 100 L 140 200 Z" fill="#1a1410"/>
            <path d="M 200 195 L 240 110 L 280 195 Z" fill="#1a1410"/>
          </svg>
          <div style={{ position: 'absolute', top: 8, left: 12, color: '#a8231d', fontFamily: 'Courier New, monospace', fontSize: 11, letterSpacing: '0.2em' }}>● REC · A001_C012</div>
          <div style={{ position: 'absolute', bottom: 8, right: 12, color: '#f5f0d8', fontFamily: 'Courier New, monospace', fontSize: 11 }}>TC 01:00:04:08</div>
          {/* film perforations */}
          <div style={{ position: 'absolute', left: -22, top: 8, bottom: 8, width: 14, background: 'repeating-linear-gradient(0deg, #2a2a2a 0 12px, #4a4a4a 12px 18px)' }}/>
          <div style={{ position: 'absolute', right: -22, top: 8, bottom: 8, width: 14, background: 'repeating-linear-gradient(0deg, #2a2a2a 0 12px, #4a4a4a 12px 18px)' }}/>
        </div>

        {/* shot params + waveform/vectorscope */}
        <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: 12 }}>
          <div style={{ background: '#0a0a0a', border: '4px solid #2a2a2a', padding: 12 }}>
            <div style={{ color: '#7df9c4', fontFamily: 'Courier New, monospace', fontSize: 10, letterSpacing: '0.2em' }}>VECTORSCOPE</div>
            <svg viewBox="-50 -50 100 100" width="100%" height="80%">
              <circle r="40" fill="none" stroke="#2a4a3a" strokeWidth="0.5"/>
              <circle r="25" fill="none" stroke="#2a4a3a" strokeWidth="0.5"/>
              {Array.from({ length: 200 }).map((_, i) => {
                const a = Math.random() * Math.PI * 2, r = Math.random() * 30;
                return <circle key={i} cx={Math.cos(a)*r} cy={Math.sin(a)*r} r="0.4" fill="#7df9c4" opacity="0.6"/>;
              })}
            </svg>
          </div>
          <div style={{ background: '#0a0a0a', border: '4px solid #2a2a2a', padding: 12 }}>
            <div style={{ color: '#7df9c4', fontFamily: 'Courier New, monospace', fontSize: 10, letterSpacing: '0.2em' }}>WAVEFORM RGB</div>
            <svg viewBox="0 0 200 60" width="100%" height="80%">
              {['#ff6b6b', '#7df9c4', '#6b9eff'].map((c, j) => (
                <g key={c} opacity="0.7">
                  {Array.from({ length: 80 }).map((_, i) => {
                    const h = 8 + Math.abs(Math.sin(i * 0.3 + j)) * 30;
                    return <rect key={i} x={i * 2.5} y={50 - h} width="1" height={h} fill={c}/>;
                  })}
                </g>
              ))}
            </svg>
          </div>
        </div>
      </div>

      {/* film strip timeline */}
      <div style={{ background: '#1a1a1a', border: '4px solid #2a2a2a', padding: '14px 18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#f5f0d8', fontSize: 10, letterSpacing: '0.2em', marginBottom: 8 }}>
          <span>FILM · 35mm · ROLL #04</span>
          <span>16 PRISES · 1 SÉLECTIONNÉE</span>
        </div>
        <div style={{ display: 'flex', gap: 0, position: 'relative', overflow: 'hidden' }}>
          {Array.from({ length: 16 }).map((_, i) => (
            <div key={i} style={{
              flex: 1, aspectRatio: '4/3', background: i === 4 ? '#3a2a1a' : '#0a0a0a',
              border: i === 4 ? '2px solid #f5d040' : 'none',
              backgroundImage: `radial-gradient(circle at ${30 + i*4}% 50%, rgba(248,228,160,0.3), transparent 50%)`,
              position: 'relative'
            }}>
              <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 6, background: 'repeating-linear-gradient(90deg, #2a2a2a 0 5px, transparent 5px 8px)' }}/>
              <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 6, background: 'repeating-linear-gradient(90deg, #2a2a2a 0 5px, transparent 5px 8px)' }}/>
              <div style={{ position: 'absolute', bottom: 8, left: 4, fontSize: 8, color: '#f5f0d8', fontFamily: 'Courier New, monospace' }}>{String(i+1).padStart(2,'0')}</div>
            </div>
          ))}
        </div>
      </div>

      {/* transport controls */}
      <div style={{ background: '#3a3a3a', border: '1px solid #1a1a1a', padding: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.1)' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {['⏮', '◀◀', '◀', '■', '▶', '▶▶', '⏭'].map((c, i) => (
            <button key={i} style={{ width: 50, height: 36, background: i === 4 ? '#a8231d' : '#1a1a1a', color: '#f5f0d8', border: '1px solid #5a5a5a', fontSize: 14, cursor: 'pointer', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.1)' }}>{c}</button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 18, alignItems: 'center' }}>
          {['SHUTTLE', 'JOG'].map(l => (
            <div key={l} style={{ textAlign: 'center' }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'radial-gradient(circle at 30% 30%, #6a6a6a, #2a2a2a 70%, #0a0a0a)', border: '2px solid #1a1a1a', position: 'relative' }}>
                <div style={{ position: 'absolute', top: 6, left: '50%', width: 4, height: 14, background: '#f5d040', transform: 'translateX(-50%)' }}/>
              </div>
              <div style={{ fontSize: 9, color: '#f5f0d8', letterSpacing: '0.2em', marginTop: 4 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   VI. 3D — CAD BLUEPRINT
   Cyan-on-navy drafting, dimensions, technical drawing
   ============================================================ */
function ThreeV3() {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: '#0c2944',
      backgroundImage: `linear-gradient(rgba(120,200,255,0.07) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(120,200,255,0.07) 1px, transparent 1px),
                        linear-gradient(rgba(120,200,255,0.04) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(120,200,255,0.04) 1px, transparent 1px)`,
      backgroundSize: '80px 80px, 80px 80px, 16px 16px, 16px 16px',
      color: '#cce8ff', fontFamily: 'Courier New, Courier, monospace',
      padding: 24, position: 'relative', display: 'flex', flexDirection: 'column'
    }}>
      {/* title block bottom right */}
      <header style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #4a82b4', paddingBottom: 8 }}>
        <div>
          <div style={{ fontSize: 11, letterSpacing: '0.3em' }}>AURORA · DRAFT DEPT.</div>
          <div style={{ fontSize: 22, marginTop: 4, letterSpacing: '0.05em' }}>VOLUMEN — Hunyuan3D</div>
        </div>
        <div style={{ fontSize: 11, textAlign: 'right' }}>
          <div>SHEET 06 / 10</div>
          <div>SCALE 1:1 · METRIC</div>
          <div>REV. C · 04 / 26</div>
        </div>
      </header>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr', gap: 12, padding: '20px 0' }}>
        {[
          { label: 'FRONT', d: 0 }, { label: 'TOP', d: 1 }, { label: 'SIDE', d: 2 }, { label: 'ISO', d: 3 }
        ].map(v => (
          <div key={v.label} style={{ border: '1px solid #4a82b4', position: 'relative', padding: 14 }}>
            <div style={{ position: 'absolute', top: 6, left: 8, fontSize: 9, letterSpacing: '0.2em', background: '#0c2944', padding: '0 4px' }}>{v.label}</div>
            <svg viewBox="0 0 200 120" width="100%" height="100%">
              {v.d === 3 ? (
                <g>
                  <path d="M 60 70 L 100 50 L 140 70 L 140 100 L 100 120 L 60 100 Z" fill="none" stroke="#7dc8ff" strokeWidth="1"/>
                  <path d="M 60 70 L 100 50 L 100 80 L 60 100 Z" fill="rgba(125,200,255,0.08)" stroke="#7dc8ff" strokeWidth="1"/>
                  <path d="M 100 50 L 140 70 L 140 100 L 100 80 Z" fill="rgba(125,200,255,0.04)" stroke="#7dc8ff" strokeWidth="1"/>
                  <path d="M 60 70 L 100 80 L 140 70" fill="none" stroke="#7dc8ff" strokeWidth="0.5" strokeDasharray="2 2"/>
                </g>
              ) : (
                <g>
                  <rect x={50 + v.d * 4} y={30} width={100 - v.d*4} height={70} fill="none" stroke="#7dc8ff" strokeWidth="1"/>
                  <path d={`M ${50 + v.d * 4} 65 L ${150 - v.d * 4} 65`} stroke="#7dc8ff" strokeWidth="0.5" strokeDasharray="3 3"/>
                  <circle cx="100" cy="65" r={12 - v.d*2} fill="none" stroke="#7dc8ff" strokeWidth="1"/>
                </g>
              )}
              {/* dimensions */}
              <g stroke="#7dc8ff" strokeWidth="0.4" fill="none">
                <line x1="50" y1="20" x2="150" y2="20"/>
                <line x1="50" y1="16" x2="50" y2="24"/>
                <line x1="150" y1="16" x2="150" y2="24"/>
              </g>
              <text x="100" y="14" fontSize="6" fill="#cce8ff" textAnchor="middle">142.0</text>
              <g stroke="#7dc8ff" strokeWidth="0.4" fill="none">
                <line x1="170" y1="30" x2="170" y2="100"/>
                <line x1="166" y1="30" x2="174" y2="30"/>
                <line x1="166" y1="100" x2="174" y2="100"/>
              </g>
              <text x="178" y="68" fontSize="6" fill="#cce8ff">88.5</text>
            </svg>
          </div>
        ))}
      </div>

      {/* parts table */}
      <div style={{ border: '1px solid #4a82b4', fontSize: 11 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '60px 60px 1fr 80px 80px 80px', borderBottom: '1px solid #4a82b4', padding: '6px 10px', letterSpacing: '0.2em', fontSize: 9, color: '#7dc8ff' }}>
          <span>ITEM</span><span>QTY</span><span>DESCRIPTION</span><span>VERTS</span><span>FACES</span><span>STAGE</span>
        </div>
        {[
          ['001', 1, 'CAPTURE — image-source', '—', '—', 'DONE'],
          ['002', 1, 'SILHOUETTE — extraction alpha', '—', '—', 'DONE'],
          ['003', 1, 'VOXELS — résolution 256³', '16M', '—', 'DONE'],
          ['004', 1, 'MESH — marching cubes', '24,614', '12,308', 'ACTIVE'],
          ['005', 1, 'UV — déplié angulaire', '—', '—', 'PENDING'],
          ['006', 1, 'TEXTURES — diffuse/normal/rough', '—', '—', 'PENDING'],
        ].map(row => (
          <div key={row[0]} style={{ display: 'grid', gridTemplateColumns: '60px 60px 1fr 80px 80px 80px', padding: '6px 10px', borderBottom: '1px dashed #2a4a6a' }}>
            {row.map((c, i) => <span key={i} style={{ color: i === 5 && c === 'ACTIVE' ? '#ffd166' : i === 5 && c === 'DONE' ? '#7df9c4' : '#cce8ff' }}>{c}</span>)}
          </div>
        ))}
      </div>
    </div>
  );
}

window.VideoV3 = VideoV3;
window.ThreeV3 = ThreeV3;
