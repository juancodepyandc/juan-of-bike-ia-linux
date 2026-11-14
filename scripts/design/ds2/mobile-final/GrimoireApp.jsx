/* global React */
const { useState, useEffect, useRef } = React;

// =========================================================================
// GRIMOIRE — juan of bike IA mobile
// Metaphor: a living spell book. Each page = a module.
// Vertical swipe between pages. Companion orb floats. Ink notifications.
// =========================================================================

const PAGES = [
  { id: 'home',   chapter: 'I · COUVERTURE',  title: 'GRIMOIRE' },
  { id: 'chat',   chapter: 'II · INCANTATIONS', title: 'CHAT' },
  { id: 'forge',  chapter: 'III · INVOCATION', title: 'FORGE' },
  { id: 'create', chapter: 'IV · SORTILÈGES',  title: 'CRÉATION' },
  { id: 'academy',chapter: 'V · ANNALES',      title: 'ACADÉMIE' },
  { id: 'canvas', chapter: 'VI · CARTE',       title: 'CANVAS' },
];

function GrimoireApp() {
  const [pageIdx, setPageIdx] = useState(0);
  const [touchY, setTouchY] = useState(null);
  const [turning, setTurning] = useState(false);
  const [bubble, setBubble] = useState('Bonjour. Glisse vers le haut pour tourner la page.');
  const [notifs, setNotifs] = useState([]);

  // Auto companion lines per page
  useEffect(() => {
    const lines = {
      home: 'Le grimoire te reconnaît. Choisis un sort.',
      chat: 'Parle-moi. Je t\'écoute sur la plume.',
      forge: 'Décris un esprit. Je vais le forger.',
      create: 'Quatre arts. Lequel veux-tu ouvrir ?',
      academy: 'Tes quêtes en cours attendent.',
      canvas: 'Vue complète du royaume.',
    };
    setBubble(lines[PAGES[pageIdx].id]);
    const t = setTimeout(() => setBubble(null), 4000);
    return () => clearTimeout(t);
  }, [pageIdx]);

  // Random notifications
  useEffect(() => {
    const msgs = [
      { seal: '✦', text: 'Caine est prêt dans la Forge.' },
      { seal: '⚡', text: 'Wan2.2 a terminé ton clip.' },
      { seal: '♡', text: 'Lucy a +40 XP en invocation.' },
    ];
    const iv = setInterval(() => {
      const m = msgs[Math.floor(Math.random() * msgs.length)];
      const id = Date.now();
      setNotifs(n => [...n, { ...m, id }]);
      setTimeout(() => setNotifs(n => n.filter(x => x.id !== id)), 3500);
    }, 9000);
    return () => clearInterval(iv);
  }, []);

  const turnTo = (idx) => {
    if (idx < 0 || idx >= PAGES.length) return;
    setTurning(true);
    setPageIdx(idx);
    setTimeout(() => setTurning(false), 700);
  };

  const onTouchStart = (e) => setTouchY(e.touches[0].clientY);
  const onTouchEnd = (e) => {
    if (touchY === null) return;
    const dy = e.changedTouches[0].clientY - touchY;
    if (dy < -50) turnTo(pageIdx + 1);
    else if (dy > 50) turnTo(pageIdx - 1);
    setTouchY(null);
  };
  // mouse fallback
  const [mouseY, setMouseY] = useState(null);
  const onMouseDown = (e) => setMouseY(e.clientY);
  const onMouseUp = (e) => {
    if (mouseY === null) return;
    const dy = e.clientY - mouseY;
    if (dy < -40) turnTo(pageIdx + 1);
    else if (dy > 40) turnTo(pageIdx - 1);
    setMouseY(null);
  };

  const current = PAGES[pageIdx];

  return (
    <div className="g-root"
         onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}
         onMouseDown={onMouseDown} onMouseUp={onMouseUp}>

      {/* top band */}
      <div className="g-topband">
        <span className="chapter">{current.chapter}</span>
        <span className="pagenum">{String(pageIdx+1).padStart(2,'0')} / {String(PAGES.length).padStart(2,'0')}</span>
      </div>

      {/* notifications */}
      <div className="g-notifs">
        {notifs.map(n => (
          <div key={n.id} className="g-notif-scroll">
            <div className="g-notif-seal">{n.seal}</div>
            <span>{n.text}</span>
          </div>
        ))}
      </div>

      {/* flash fx on page turn */}
      <div className={`g-pageturn-fx ${turning ? 'on' : ''}`}/>

      {/* particles */}
      <Particles />

      {/* current page */}
      <div className="g-page" key={current.id} style={{animation: 'g-bubble-in .5s'}}>
        <div className="g-corner g-corner-tl"/>
        <div className="g-corner g-corner-tr"/>
        <div className="g-corner g-corner-bl"/>
        <div className="g-corner g-corner-br"/>

        <div className="g-content">
          {current.id === 'home' && <HomePage onPick={turnTo}/>}
          {current.id === 'chat' && <ChatPage/>}
          {current.id === 'forge' && <ForgePage/>}
          {current.id === 'create' && <CreatePage/>}
          {current.id === 'academy' && <AcademyPage/>}
          {current.id === 'canvas' && <CanvasPage/>}
        </div>
      </div>

      {/* companion */}
      <div className="g-companion">
        {bubble && <div className="g-companion-bubble">{bubble}</div>}
        <div className="g-companion-orb" onClick={() => setBubble('Demande-moi n\'importe quoi.')}>
          <div className="g-companion-face">
            <div className="g-companion-eye l"/>
            <div className="g-companion-eye r"/>
            <div className="g-companion-smile"/>
          </div>
        </div>
      </div>

      {/* bottom spine nav */}
      <div className="g-spine">
        <button className="g-spine-cmd" onClick={() => turnTo(0)}>⌘ CENTRE</button>
        <div className="g-spine-strip">
          {PAGES.map((p, i) => (
            <div key={p.id} className={`g-spine-dot ${i === pageIdx ? 'active' : ''}`}
                 onClick={() => turnTo(i)}/>
          ))}
        </div>
        <div className="g-spine-labels">
          {PAGES.map((p, i) => <span key={p.id} className={i === pageIdx ? 'active' : ''}>{p.title}</span>)}
        </div>
      </div>
    </div>
  );
}

// ==================== PAGES ====================

function HomePage({ onPick }) {
  const modules = [
    { idx: 1, icon: '💬', label: 'Chat',    angle: 0,   hot: true },
    { idx: 2, icon: '🔮', label: 'Forge',   angle: 60 },
    { idx: 3, icon: '✨', label: 'Créer',   angle: 120 },
    { idx: 4, icon: '📖', label: 'Académie',angle: 180 },
    { idx: 5, icon: '🗺',  label: 'Canvas',  angle: 240 },
    { idx: 2, icon: '⚔',  label: 'Quêtes',  angle: 300 },
  ];
  const R = 100;
  return (
    <div className="g-home">
      <h1 className="g-home-hero">JUAN OF BIKE</h1>
      <div className="g-home-sub">grimoire · niveau 12 · 2430 xp</div>

      <div className="g-wheel">
        <div className="g-wheel-ring"/>
        <div className="g-wheel-ring-2"/>
        {modules.map((m, i) => {
          const rad = (m.angle * Math.PI) / 180;
          const x = Math.cos(rad) * R;
          const y = Math.sin(rad) * R;
          return (
            <div key={i} className={`g-petal ${m.hot ? 'hot' : ''}`}
                 style={{ transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))` }}
                 onClick={() => onPick(m.idx)}>
              <span style={{ fontSize: 26 }}>{m.icon}</span>
              <span className="g-petal-label">{m.label}</span>
            </div>
          );
        })}
        <div className="g-seal">
          <svg className="g-seal-star" viewBox="0 0 48 48" fill="currentColor">
            <path d="M24 2 L29 18 L46 18 L32 28 L37 44 L24 34 L11 44 L16 28 L2 18 L19 18 Z"/>
          </svg>
        </div>
      </div>

      <div className="g-home-status">
        <h5>JOURNAL DU JOUR</h5>
        <div className="g-home-status-row"><span>streak</span><b>7 jours</b></div>
        <div className="g-home-status-row"><span>quête active</span><b>Caine v1</b></div>
        <div className="g-home-status-row"><span>prochain pallier</span><b>niv. 13 · 120 xp</b></div>
      </div>
    </div>
  );
}

function ChatPage() {
  const msgs = [
    { who: 'ai', t: 'Te voilà. Que cherchons-nous aujourd\'hui ?' },
    { who: 'user', t: 'Aide-moi à écrire un prompt pour Caine.' },
    { who: 'ai', t: 'Bien. Commençons par ses traits signature : étoile + lune au lieu des yeux, pas de peau, sourire permanent. Tu veux une pose idle ou action ?' },
    { who: 'user', t: 'Idle, portrait 3/4.' },
    { who: 'ai', t: '"caine tadc, portrait 3/4, star eye left yellow, crescent moon eye right orange, permanent grin, jester hat dual horn, monochrome face, theatrical lighting". Je lance ?' },
  ];
  return (
    <>
      <h1 className="g-title">CHAT</h1>
      <div className="g-subtitle">ollama · llama3.1 · streaming</div>
      <div className="g-chat-scroll" style={{ height: 'calc(100% - 70px)' }}>
        {msgs.map((m, i) => (
          <div key={i} className={`g-msg ${m.who}`}>
            {m.who === 'ai' && <span className="glow"/>}
            {m.t}
          </div>
        ))}
      </div>
      <div className="g-chat-input">
        <input placeholder="prononce ton sort…"/>
        <button className="g-chat-send">↗</button>
      </div>
    </>
  );
}

function ForgePage() {
  const [step, setStep] = useState(3);
  const runes = ['✦','☾','✧','⚝','❂','☉','⚘','❖'];
  return (
    <>
      <h1 className="g-title">FORGE</h1>
      <div className="g-subtitle">un prompt · un esprit · tout auto</div>

      <div className="g-forge-circle">
        <div className="g-forge-runes">
          {runes.map((r, i) => {
            const angle = (i / runes.length) * 360;
            return (
              <div key={i} className="g-forge-rune"
                   style={{ transform: `rotate(${angle}deg) translateY(-95px)` }}>
                {r}
              </div>
            );
          })}
        </div>
        {/* Caine silhouette */}
        <svg className="g-forge-char" viewBox="0 0 200 240">
          <ellipse cx="100" cy="110" rx="70" ry="80" fill="#ecdcb0" stroke="#1a0f05" strokeWidth="4"/>
          {/* star eye */}
          <polygon points="68,85 73,98 86,100 76,108 79,122 68,114 57,122 60,108 50,100 63,98"
                   fill="#c9a24b" stroke="#1a0f05" strokeWidth="3"/>
          {/* moon eye */}
          <path d="M 128 75 A 18 18 0 1 0 128 111 A 14 14 0 1 1 128 75 Z"
                fill="#b5241e" stroke="#1a0f05" strokeWidth="3"/>
          {/* grin */}
          <path d="M 70 150 Q 100 175 130 150 Q 100 162 70 150 Z"
                fill="#1a0f05"/>
          <line x1="80" y1="152" x2="80" y2="160" stroke="#ecdcb0" strokeWidth="2"/>
          <line x1="92" y1="154" x2="92" y2="163" stroke="#ecdcb0" strokeWidth="2"/>
          <line x1="108" y1="154" x2="108" y2="163" stroke="#ecdcb0" strokeWidth="2"/>
          <line x1="120" y1="152" x2="120" y2="160" stroke="#ecdcb0" strokeWidth="2"/>
          {/* hat horns */}
          <path d="M 45 55 Q 25 5 30 50 Q 40 55 50 55 Z" fill="#1a0f05"/>
          <path d="M 155 55 Q 175 5 170 50 Q 160 55 150 55 Z" fill="#ecdcb0" stroke="#1a0f05" strokeWidth="3"/>
        </svg>
      </div>

      <div className="g-forge-pipeline">
        <div><span className="plan">03 · plan :</span> rig sur-mesure pour Caine ✓</div>
        <div><span className="gen">04 · gen :</span> flux-dev Q6 · 28/28</div>
        <div><span className="ok">05 · ✓ :</span> 6 variations · score 0.94</div>
        <div><span className="ok">06 · ✓ :</span> 11 calques extraits</div>
      </div>

      <div className="g-forge-prompt">
        <input placeholder="Caine, the amazing digital circus" defaultValue="Caine, tadc"/>
        <button className="g-forge-btn">INVOQUER</button>
      </div>
    </>
  );
}

function CreatePage() {
  const arts = [
    { name: 'Image',  sub: 'flux · 15 styles',      tag: 'S', preview: '142 générées' },
    { name: 'Vidéo',  sub: 'wan2.2 · T2V/I2V',       tag: 'B', preview: '8 clips' },
    { name: 'Code',   sub: 'multi-modèle',            tag: 'A', preview: '12 projets' },
    { name: 'Dessin', sub: 'canvas · sketch2img',    tag: 'B', preview: '37 croquis' },
  ];
  return (
    <>
      <h1 className="g-title">SORTILÈGES</h1>
      <div className="g-subtitle">quatre arts créatifs</div>
      <div className="g-creative-grid">
        {arts.map(a => (
          <div key={a.name} className="g-creative-card">
            <span className="tag">rang {a.tag}</span>
            <h4>{a.name}</h4>
            <p>{a.sub}</p>
            <div className="g-creative-preview">{a.preview}</div>
          </div>
        ))}
      </div>
    </>
  );
}

function AcademyPage() {
  const quests = [
    { t: 'Apprendre FLUX', s: 'module 3/8', r: 'S' },
    { t: 'Crypto · CTF', s: 'défi 14', r: 'S' },
    { t: 'Rigify Blender', s: 'leçon 2/5', r: 'A' },
    { t: 'Leitner du jour', s: '12 cartes', r: 'B' },
  ];
  return (
    <>
      <h1 className="g-title">ANNALES</h1>
      <div className="g-subtitle">tes quêtes en cours</div>
      <div className="g-grimoire-stats">
        <div className="g-stat"><div className="g-stat-val">12</div><div className="g-stat-lbl">niveau</div></div>
        <div className="g-stat"><div className="g-stat-val">2430</div><div className="g-stat-lbl">xp total</div></div>
        <div className="g-stat"><div className="g-stat-val">7j</div><div className="g-stat-lbl">streak</div></div>
        <div className="g-stat"><div className="g-stat-val">94%</div><div className="g-stat-lbl">leitner</div></div>
      </div>
      <div className="g-divider"/>
      {quests.map(q => (
        <div key={q.t} className="g-quest">
          <div>
            <div className="g-quest-t">{q.t}</div>
            <div className="g-quest-s">{q.s}</div>
          </div>
          <div className={`g-quest-rank ${q.r === 'S' ? 's' : ''}`}>{q.r}</div>
        </div>
      ))}
    </>
  );
}

function CanvasPage() {
  return (
    <>
      <h1 className="g-title">CARTE</h1>
      <div className="g-subtitle">tes territoires actifs</div>
      <svg viewBox="0 0 300 400" style={{ width: '100%', height: 'auto', marginTop: 10 }}>
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#3d2a12" strokeWidth="0.8"/>
          </pattern>
        </defs>
        {/* rivers / paths */}
        <path d="M 20 340 Q 80 280 120 240 T 200 120 T 280 40" fill="none" stroke="#3d2a12" strokeWidth="2" strokeDasharray="4 4"/>
        <path d="M 40 50 Q 100 100 150 140 T 260 220" fill="none" stroke="#3d2a12" strokeWidth="2" strokeDasharray="4 4"/>

        {/* territories */}
        <circle cx="70" cy="80" r="38" fill="url(#hatch)" stroke="#1a0f05" strokeWidth="2"/>
        <text x="70" y="85" textAnchor="middle" fontFamily="Bangers" fontSize="14" fill="#1a0f05">CHAT</text>

        <circle cx="220" cy="110" r="32" fill="#b5241e" stroke="#1a0f05" strokeWidth="2" opacity="0.7"/>
        <text x="220" y="115" textAnchor="middle" fontFamily="Bangers" fontSize="12" fill="#ecdcb0">FORGE</text>

        <rect x="40" y="200" width="80" height="60" fill="#c9a24b" stroke="#1a0f05" strokeWidth="2" transform="rotate(-5 80 230)"/>
        <text x="80" y="236" textAnchor="middle" fontFamily="Bangers" fontSize="13" fill="#1a0f05">IMAGE</text>

        <circle cx="200" cy="240" r="28" fill="#ecdcb0" stroke="#1a0f05" strokeWidth="2"/>
        <text x="200" y="245" textAnchor="middle" fontFamily="Bangers" fontSize="11" fill="#1a0f05">CODE</text>

        <polygon points="150,320 190,360 110,360" fill="#6a3b8c" stroke="#1a0f05" strokeWidth="2" opacity="0.8"/>
        <text x="150" y="350" textAnchor="middle" fontFamily="Bangers" fontSize="11" fill="#ecdcb0">CYBER</text>

        {/* compass */}
        <g transform="translate(255, 340)">
          <circle r="22" fill="#ecdcb0" stroke="#1a0f05" strokeWidth="2"/>
          <polygon points="0,-16 4,0 0,14 -4,0" fill="#b5241e" stroke="#1a0f05"/>
          <text x="0" y="-18" textAnchor="middle" fontFamily="Bangers" fontSize="8">N</text>
        </g>
      </svg>
      <div className="g-divider"/>
      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#6b523a', textAlign: 'center' }}>
        DOUBLE-TAP UN TERRITOIRE POUR L'OUVRIR
      </div>
    </>
  );
}

function Particles() {
  const parts = React.useMemo(() => Array.from({ length: 14 }, (_, i) => ({
    left: Math.random() * 100,
    top: 60 + Math.random() * 40,
    delay: Math.random() * 6,
    duration: 4 + Math.random() * 4,
  })), []);
  return (
    <>
      {parts.map((p, i) => (
        <div key={i} className="g-particle"
             style={{
               left: `${p.left}%`, top: `${p.top}%`,
               animationDelay: `${p.delay}s`,
               animationDuration: `${p.duration}s`,
             }}/>
      ))}
    </>
  );
}

window.GrimoireApp = GrimoireApp;
