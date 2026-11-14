/* ============================================================
   VII. DRAW — ATELIER / SKETCHBOOK PAGE
   Cream paper, pencil, gouache splotches, hand-drawn
   ============================================================ */
function DrawV3() {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: '#faf2e0',
      backgroundImage: `radial-gradient(ellipse at 30% 20%, rgba(180,140,90,0.12), transparent 40%),
                        radial-gradient(ellipse at 70% 80%, rgba(180,140,90,0.08), transparent 40%)`,
      padding: 32, fontFamily: 'Caveat, Bradley Hand, cursive', color: '#2a1f15',
      position: 'relative', display: 'grid', gridTemplateColumns: '1fr 280px', gap: 24
    }}>
      {/* paper edge curl */}
      <div style={{ position: 'absolute', top: 0, right: 0, width: 80, height: 80,
        background: 'linear-gradient(225deg, transparent 50%, rgba(0,0,0,0.08) 50%)' }}/>

      <div>
        <h1 style={{ fontSize: 56, margin: 0, transform: 'rotate(-1deg)' }}>l'atelier</h1>
        <div style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 14, marginTop: -4, color: '#5a4a3a' }}>
          ↳ feuille du jeudi, encre de Chine + lavis
        </div>

        <div style={{ marginTop: 20, position: 'relative', minHeight: 460, border: '1px solid rgba(42,31,21,0.2)', background: 'rgba(255,253,245,0.5)', padding: 24 }}>
          {/* hand-drawn bamboo */}
          <svg viewBox="0 0 500 400" width="100%" height="100%" style={{ display: 'block' }}>
            <g stroke="#2a1f15" strokeLinecap="round" fill="none">
              <path d="M 120 380 Q 130 250 122 90" strokeWidth="14" opacity="0.92"/>
              <path d="M 116 290 Q 119 286 124 290" strokeWidth="3"/>
              <path d="M 116 220 Q 119 216 124 220" strokeWidth="3"/>
              <path d="M 117 150 Q 120 146 125 150" strokeWidth="3"/>
              {/* leaves */}
              <path d="M 122 290 Q 200 295 250 340 Q 220 320 180 320 Q 150 315 122 295" strokeWidth="2.5" opacity="0.85" fill="rgba(42,31,21,0.5)"/>
              <path d="M 124 220 Q 240 220 320 200 Q 280 215 220 215 Q 170 218 124 222" strokeWidth="2.5" opacity="0.85" fill="rgba(42,31,21,0.4)"/>
              <path d="M 125 150 Q 60 130 30 100" strokeWidth="2" opacity="0.8" fill="rgba(42,31,21,0.3)"/>
            </g>
            {/* annotations */}
            <g fontFamily="Caveat, cursive" fontSize="22" fill="#a8231d">
              <text x="280" y="120" transform="rotate(-4 280 120)">↘ + d'eau ici ?</text>
              <text x="320" y="320" transform="rotate(2 320 320)">tronc trop droit</text>
              <text x="40" y="200" transform="rotate(-90 40 200)">racine ↓</text>
            </g>
            {/* arrows */}
            <g stroke="#a8231d" strokeWidth="1.5" fill="none">
              <path d="M 270 130 Q 220 145 175 165 M 175 165 L 185 158 M 175 165 L 175 155" strokeLinecap="round"/>
            </g>
            {/* gouache splotches */}
            <ellipse cx="420" cy="80" rx="22" ry="14" fill="#a8231d" opacity="0.85" transform="rotate(15 420 80)"/>
            <text x="420" y="86" textAnchor="middle" fontFamily="Georgia, serif" fontStyle="italic" fontSize="14" fill="#faf2e0">A.</text>
            <circle cx="450" cy="350" r="8" fill="#3a5a4a" opacity="0.6"/>
            <circle cx="40" cy="370" r="5" fill="#2a1f15" opacity="0.5"/>
          </svg>
        </div>

        <div style={{ marginTop: 16, display: 'flex', gap: 14, alignItems: 'center', fontSize: 22, transform: 'rotate(-0.5deg)' }}>
          <span>aurora suggère :</span>
          <span style={{ borderBottom: '2px solid #a8231d', paddingBottom: 2, color: '#a8231d' }}>épaissir le tronc en bas</span>
          <span style={{ fontSize: 14, color: '#5a4a3a' }}>· accepter (a) · refuser (r)</span>
        </div>
      </div>

      {/* tools margin */}
      <aside style={{ borderLeft: '1px dashed rgba(42,31,21,0.3)', paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 14, fontSize: 18 }}>
        <div style={{ fontSize: 26, transform: 'rotate(-1deg)' }}>boîte à outils</div>

        {/* pencil */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, transform: 'rotate(1deg)' }}>
          <svg width="120" height="20" viewBox="0 0 120 20"><path d="M 0 10 L 10 4 L 95 4 L 95 16 L 10 16 Z" fill="#e8a040" stroke="#2a1f15"/><path d="M 0 10 L 10 4 L 10 16 Z" fill="#2a1f15"/><path d="M 95 4 L 110 4 L 115 10 L 110 16 L 95 16 Z" fill="#d8b890" stroke="#2a1f15"/></svg>
          <span>2B</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, transform: 'rotate(-2deg)' }}>
          <svg width="120" height="20" viewBox="0 0 120 20"><path d="M 0 10 L 10 4 L 95 4 L 95 16 L 10 16 Z" fill="#3a5a4a" stroke="#2a1f15"/><path d="M 0 10 L 10 4 L 10 16 Z" fill="#2a1f15"/></svg>
          <span style={{ textDecoration: 'underline' }}>encre · ★</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, transform: 'rotate(0.5deg)' }}>
          <svg width="100" height="50" viewBox="0 0 100 50"><path d="M 50 5 Q 48 25 35 40 Q 50 45 65 40 Q 52 25 50 5" fill="#2a1f15"/><rect x="46" y="40" width="8" height="8" fill="#5a4a3a"/></svg>
          <span>pinceau</span>
        </div>

        <div style={{ borderTop: '1px dashed rgba(42,31,21,0.3)', paddingTop: 12, marginTop: 4, fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 13, color: '#5a4a3a' }}>
          calques :
          <ol style={{ margin: '8px 0 0', paddingLeft: 20, fontSize: 14, color: '#2a1f15' }}>
            <li>papier</li>
            <li>réserve</li>
            <li><strong>tronc</strong> ←</li>
            <li>feuilles</li>
            <li>sceau</li>
          </ol>
        </div>

        <div style={{ marginTop: 'auto', textAlign: 'center', fontSize: 14, fontFamily: 'Georgia, serif', fontStyle: 'italic', color: '#5a4a3a' }}>
          17:42 · jeudi
        </div>
      </aside>
    </div>
  );
}

/* ============================================================
   VIII. ACADEMY — SPIRAL NOTEBOOK
   Ruled paper, highlighters, doodles, post-its
   ============================================================ */
function AcademyV3() {
  return (
    <div style={{
      width: '100%', height: '100%', display: 'flex',
      background: 'linear-gradient(90deg, #c8b89a 0%, #c8b89a 80px, #fff 80px)',
      fontFamily: 'Patrick Hand, Comic Sans MS, cursive', color: '#1a2840',
      position: 'relative', overflow: 'hidden'
    }}>
      {/* spiral binding */}
      <div style={{ position: 'absolute', left: 30, top: 0, bottom: 0, width: 36, display: 'flex', flexDirection: 'column', justifyContent: 'space-around', padding: '12px 0', zIndex: 2 }}>
        {Array.from({ length: 24 }).map((_, i) => (
          <div key={i} style={{ width: 28, height: 16, border: '3px solid #888', borderRadius: '50%', background: 'transparent', boxShadow: '0 1px 0 rgba(0,0,0,0.2)' }}/>
        ))}
      </div>

      {/* lined paper */}
      <div style={{
        flex: 1, marginLeft: 80, padding: '36px 36px 36px 80px', position: 'relative',
        backgroundImage: `repeating-linear-gradient(0deg, transparent 0 31px, #6c89c4 31px 32px)`,
        borderLeft: '2px solid #d04a4a',
      }}>
        {/* red margin line */}
        <div style={{ position: 'absolute', left: 56, top: 0, bottom: 0, width: 1, background: '#d04a4a' }}/>

        <div style={{ fontSize: 13, color: '#d04a4a', position: 'absolute', top: 8, right: 24, transform: 'rotate(-1deg)' }}>
          jeudi 30 avril ✦
        </div>

        <h1 style={{ fontSize: 44, margin: 0, lineHeight: 1, transform: 'rotate(-0.5deg)' }}>
          le nombre d'or  <span style={{ background: '#fff8a0', padding: '0 8px' }}>φ</span>
        </h1>
        <div style={{ fontSize: 16, color: '#5a6a90', marginTop: 4 }}>↳ première · maths · leçon XII</div>

        <div style={{ marginTop: 24, fontSize: 18, lineHeight: '32px' }}>
          <p style={{ margin: 0 }}>
            <span style={{ background: '#a0e8b8', padding: '0 4px' }}>def.</span> le nombre d'or, noté <em style={{ color: '#a050c8' }}>φ</em>,
            est cette proportion <span style={{ textDecoration: 'underline #d04a4a wavy' }}>par laquelle</span> un
          </p>
          <p style={{ margin: 0 }}>segment se laisse diviser en deux parties dont</p>
          <p style={{ margin: 0 }}>le rapport <em>grande/petite</em> = rapport <em>tout/grande</em>.</p>
          <p style={{ margin: '32px 0 0', fontSize: 26, color: '#a050c8', textAlign: 'center', transform: 'rotate(-0.5deg)' }}>
            φ = (1 + √5) / 2  ≈  1,6180...
          </p>

          <div style={{ marginTop: 32 }}>
            <span style={{ background: '#fff8a0', padding: '0 6px' }}>ex.</span> on retrouve φ dans :
            <ul style={{ margin: '8px 0 0', paddingLeft: 32, fontSize: 18 }}>
              <li>les <span style={{ textDecoration: 'underline' }}>spirales de nautile</span> 🐚</li>
              <li>l'arrangement des fleurs de tournesol</li>
              <li>les façades du Parthénon</li>
            </ul>
          </div>
        </div>

        {/* post-it */}
        <div style={{
          position: 'absolute', top: 200, right: 40, width: 180, height: 180,
          background: '#fff088', padding: 14, transform: 'rotate(4deg)',
          boxShadow: '4px 6px 12px rgba(0,0,0,0.18)', fontSize: 16, lineHeight: 1.4
        }}>
          <strong style={{ color: '#a8231d' }}>aurora :</strong><br/>
          tu as déjà vu φ dans la suite de Fibonacci !<br/>
          1, 1, 2, 3, 5, 8, 13...<br/>
          <span style={{ color: '#5a6a90', fontStyle: 'italic' }}>→ je te fais une carte ?</span>
        </div>

        {/* doodle */}
        <svg width="160" height="120" style={{ position: 'absolute', bottom: 80, right: 60, transform: 'rotate(8deg)' }} viewBox="0 0 160 120">
          <path d="M 80 60 m -50 0 a 50 30 0 1 0 100 0 a 30 18 0 1 0 -60 0 a 18 11 0 1 0 36 0 a 11 7 0 1 0 -22 0" fill="none" stroke="#a050c8" strokeWidth="2"/>
          <text x="80" y="115" textAnchor="middle" fontFamily="Patrick Hand, cursive" fontSize="14" fill="#5a6a90">spirale d'or</text>
        </svg>

        {/* leitner boxes — drawn */}
        <div style={{ position: 'absolute', bottom: 30, left: 90, display: 'flex', gap: 12, transform: 'rotate(-1deg)' }}>
          {['I·3', 'II·7', 'III·12', 'IV·∞'].map((b, i) => (
            <div key={b} style={{
              width: 56, height: 56, border: '2px solid #1a2840',
              background: i === 0 ? '#fff8a0' : i === 3 ? '#a0e8b8' : '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18, transform: `rotate(${(i-1.5)*1.5}deg)`,
              boxShadow: '2px 2px 0 rgba(0,0,0,0.15)'
            }}>{b}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

window.DrawV3 = DrawV3;
window.AcademyV3 = AcademyV3;
