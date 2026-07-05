/* Cowork — orchestrator hero scene. */
const { useState: useS, useEffect: useE } = React;

function CoworkAgentNode({ x, y, label, role, status, tint, delay }) {
  const colors = {
    running: 'var(--ember-500)',
    done: 'oklch(0.72 0.12 145)',
    queued: 'var(--fg-mute)',
  };
  const c = colors[status];
  return (
    <div style={{
      position: 'absolute', left: `${x}%`, top: `${y}%`,
      transform: 'translate(-50%,-50%)',
      animation: `aurora-fadeup .8s var(--ease-out) ${delay}s both`
    }}>
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--line)',
        borderRadius: 10, padding: '8px 12px', minWidth: 160,
        boxShadow: status === 'running' ? `0 0 24px ${c}33, 0 8px 30px rgba(0,0,0,.4)` : '0 8px 24px rgba(0,0,0,.3)',
        position: 'relative'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <NodeDot active={status !== 'queued'} color={c}/>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-mute)', letterSpacing: '.08em', textTransform: 'uppercase' }}>{role}</span>
        </div>
        <div style={{ fontSize: 13, fontWeight: 500, marginTop: 2 }}>{label}</div>
        {status === 'running' && (
          <div style={{ position: 'absolute', bottom: -1, left: 12, right: 12, height: 2, background: 'var(--line)', borderRadius: 99, overflow: 'hidden' }}>
            <div style={{ height: '100%', background: c, width: '60%', animation: 'aurora-progress 2.4s ease-in-out infinite' }}/>
          </div>
        )}
      </div>
      <style>{`
        @keyframes aurora-fadeup { from { opacity: 0; transform: translate(-50%, -45%) } to { opacity: 1; transform: translate(-50%, -50%) } }
        @keyframes aurora-progress { 0% { transform: translateX(-100%) } 100% { transform: translateX(280%) } }
      `}</style>
    </div>
  );
}

function CoworkConnector({ x1, y1, x2, y2, active }) {
  // x/y in 0..100 (% space). Render in 1000x600 viewBox so paths use real numbers.
  const X1 = x1 * 10, Y1 = y1 * 6;
  const X2 = x2 * 10, Y2 = y2 * 6;
  const MX = (X1 + X2) / 2, MY = (Y1 + Y2) / 2 - 30;
  const id = `g-${X1}-${Y1}-${X2}-${Y2}`;
  return (
    <svg viewBox="0 0 1000 600" preserveAspectRatio="none"
         style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
      <defs>
        <linearGradient id={id} x1={X1} y1={Y1} x2={X2} y2={Y2} gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--line-strong)" stopOpacity="0.3"/>
          <stop offset="100%" stopColor={active ? 'var(--ember-500)' : 'var(--line-strong)'} stopOpacity={active ? 0.95 : 0.5}/>
        </linearGradient>
      </defs>
      <path d={`M ${X1} ${Y1} Q ${MX} ${MY} ${X2} ${Y2}`}
            stroke={`url(#${id})`} strokeWidth="1.4" fill="none"
            strokeDasharray={active ? '0' : '5 5'}/>
      {active && (
        <circle r="3" fill="var(--ember-500)">
          <animateMotion dur="2.6s" repeatCount="indefinite"
            path={`M ${X1} ${Y1} Q ${MX} ${MY} ${X2} ${Y2}`}/>
        </circle>
      )}
    </svg>
  );
}

function CoworkLog() {
  const lines = [
    { t: '14:02:11', a: 'planner', m: 'plan generated · 7 steps · est 4m12', tone: 'fg-dim' },
    { t: '14:02:14', a: 'fetcher', m: 'GET arxiv.org/abs/2401.10515 · 200 · 184kb', tone: 'fg' },
    { t: '14:02:18', a: 'fetcher', m: 'GET semanticscholar.org/api · 200', tone: 'fg' },
    { t: '14:02:23', a: 'reader',  m: 'extracted 12 references · key claim flagged', tone: 'fg' },
    { t: '14:02:31', a: 'critic',  m: '⚠ source freshness: 2 of 12 older than 24mo', tone: 'warn' },
    { t: '14:02:34', a: 'writer',  m: 'drafting synthesis · 412 tokens streaming…', tone: 'fg' },
    { t: '14:02:35', a: 'mind',    m: 'mind-map node added · "diffusion priors"', tone: 'fg-dim' },
  ];
  return (
    <div style={{
      fontFamily: 'var(--font-mono)', fontSize: 11.5, lineHeight: 1.8,
      maxHeight: 200, overflow: 'hidden'
    }}>
      {lines.map((l, i) => (
        <div key={i} style={{
          display: 'grid', gridTemplateColumns: '64px 80px 1fr', gap: 12,
          color: l.tone === 'warn' ? 'var(--ember-400)' : `var(--${l.tone === 'fg' ? 'fg' : 'fg-dim'})`,
          opacity: 1 - i * 0.08
        }}>
          <span style={{ color: 'var(--fg-mute)' }}>{l.t}</span>
          <span style={{ color: 'var(--fg-dim)' }}>[{l.a}]</span>
          <span>{l.m}</span>
        </div>
      ))}
    </div>
  );
}

function CoworkScreen() {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      {/* Hero band: sphere left, mission editorial right */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1.05fr 1fr',
        gap: 0, padding: '40px 48px 24px', position: 'relative',
        height: '58%'
      }}>
        {/* Hero sphere with editorial caption */}
        <div style={{ position: 'relative', minHeight: 420 }}>
          <Eyebrow dot="var(--ember-500)" style={{ position: 'absolute', top: 0, left: 0 }}>
            ◊ Cowork · Orchestrator
          </Eyebrow>

          <div style={{ position: 'absolute', inset: '24px 24px 80px 0' }}>
            <AuroraSphere tint="oklch(0.70 0.150 40)" state="thinking" radius={0.36} glow={1.1}/>
            {window.OrbitRing && <OrbitRing radius={170} count={2} speed={28}/>}
          </div>

          {/* technical labels orbiting the sphere */}
          <div style={{ position: 'absolute', top: 90, right: 36, textAlign: 'right' }}>
            <div className="tech" style={{ marginBottom: 4 }}>state</div>
            <div style={{ fontFamily: 'var(--font-display)', fontStyle: 'italic', fontSize: 26, letterSpacing: '-0.02em' }}>thinking</div>
          </div>
          <div style={{ position: 'absolute', bottom: 110, left: 18 }}>
            <div className="tech" style={{ marginBottom: 4 }}>agents · 4 active</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>planner · fetcher · reader · writer</div>
          </div>

          {/* corner crosshairs frame the sphere as a specimen */}
          <Crosshairs inset={6} size={14}/>
        </div>

        {/* Editorial mission */}
        <div style={{
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          paddingLeft: 32, borderLeft: '1px solid var(--line)', position: 'relative'
        }}>
          <div>
            <Eyebrow style={{ marginBottom: 14 }}>Mission · 0341</Eyebrow>
            <Display size={68} style={{ marginBottom: 20 }}>
              Cartographier la <em style={{ color: 'var(--ember-500)' }}>diffusion</em><br/>
              dans la peinture sumi-e <span style={{ color: 'var(--fg-mute)' }}>—</span>
            </Display>
            <p style={{
              fontFamily: 'var(--font-sans)', fontSize: 15, lineHeight: 1.55,
              color: 'var(--fg-dim)', maxWidth: 480, marginTop: 14
            }}>
              Aurora orchestre quatre agents pour relier les avancées récentes en
              modèles de diffusion à la pratique du sumi-e, et produit un document
              de synthèse, un mind map et trois esquisses de référence.
            </p>
          </div>

          <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
            <Btn variant="primary">Pause mission</Btn>
            <Btn variant="ghost">Voir le plan</Btn>
            <Btn variant="bare">Annuler</Btn>
            <span style={{ flex: 1 }}/>
            <span className="tech" style={{ alignSelf: 'center' }}>ETA 02:18 · 7 étapes · 3 sources</span>
          </div>
        </div>
      </div>

      <div className="hrule" style={{ margin: '0 48px' }}/>

      {/* Lower band: graph + log + metrics */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1.4fr 1fr',
        gap: 24, padding: '24px 48px', height: 'calc(42% - 1px)'
      }}>
        {/* Agent graph */}
        <Panel padded={false} style={{ position: 'relative', overflow: 'hidden', minHeight: 240 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid var(--line)' }}>
            <Eyebrow>Agent graph · live</Eyebrow>
            <div style={{ display: 'flex', gap: 6 }}>
              <Tag>compact</Tag>
              <Tag tint="var(--ember-500)">flow</Tag>
              <Tag>timeline</Tag>
            </div>
          </div>
          <div style={{ position: 'relative', height: 'calc(100% - 50px)' }}>
            <CoworkConnector x1={12} y1={50} x2={36} y2={28} active delay={0}/>
            <CoworkConnector x1={12} y1={50} x2={36} y2={75} active delay={0.4}/>
            <CoworkConnector x1={36} y1={28} x2={64} y2={50} active delay={0.8}/>
            <CoworkConnector x1={36} y1={75} x2={64} y2={50} active delay={1.2}/>
            <CoworkConnector x1={64} y1={50} x2={88} y2={50} active delay={1.6}/>

            <CoworkAgentNode x={12} y={50} role="planner"  label="qwen3:14b · plan"        status="done"    tint="var(--ember-500)" delay={0}/>
            <CoworkAgentNode x={36} y={28} role="fetcher"  label="web · arxiv + scholar"   status="done"    tint="var(--ember-500)" delay={0.1}/>
            <CoworkAgentNode x={36} y={75} role="reader"   label="qwen3-vl · extract"      status="done"    tint="var(--ember-500)" delay={0.2}/>
            <CoworkAgentNode x={64} y={50} role="critic"   label="self-critique loop"      status="running" tint="var(--ember-500)" delay={0.3}/>
            <CoworkAgentNode x={88} y={50} role="writer"   label="streaming synthesis…"    status="queued"  tint="var(--ember-500)" delay={0.4}/>
          </div>
        </Panel>

        {/* Log + metrics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0 }}>
          <Panel raised style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
              <Eyebrow dot="oklch(0.74 0.12 145)">Live · console</Eyebrow>
              <span className="tech">tail · last 7</span>
            </div>
            <CoworkLog/>
          </Panel>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            {[
              { l: 'Tokens', v: '12 481', s: '+412/s' },
              { l: 'Coût',   v: '0,00 €', s: 'local' },
              { l: 'Étapes', v: '4 / 7',  s: 'in flight' },
            ].map((k, i) => (
              <Panel key={i} style={{ padding: 12 }}>
                <div className="tech" style={{ marginBottom: 4 }}>{k.l}</div>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontStyle: 'italic', letterSpacing: '-0.02em' }}>{k.v}</div>
                <div className="tech" style={{ color: 'var(--ember-500)', marginTop: 2 }}>{k.s}</div>
              </Panel>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

window.CoworkScreen = CoworkScreen;
