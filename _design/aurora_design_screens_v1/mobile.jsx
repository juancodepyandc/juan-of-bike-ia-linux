/* Mobile Grimoire — distinct design for tablet/mobile shell.
   Editorial portrait layout, sphere as masthead, swipeable module deck. */

function MobileGrimoire() {
  return (
    <div style={{
      width: 390, height: 844, background: 'var(--bg)', color: 'var(--fg)',
      borderRadius: 38, overflow: 'hidden', position: 'relative',
      border: '1px solid var(--line)',
      boxShadow: '0 80px 120px rgba(0,0,0,0.5), inset 0 0 0 6px oklch(0.06 0.01 250)'
    }} className="grain">
      {/* Status bar */}
      <div style={{ height: 44, padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600 }}>
        <span>14:02</span>
        <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ width: 18, height: 10, border: '1px solid var(--fg)', borderRadius: 2, position: 'relative' }}>
            <span style={{ position: 'absolute', inset: 1, background: 'var(--ember-500)', borderRadius: 1, width: '70%' }}/>
          </span>
        </span>
      </div>

      {/* Top — sphere as masthead */}
      <div style={{ position: 'relative', height: 280, margin: '0 18px', overflow: 'hidden', borderRadius: 22, border: '1px solid var(--line)' }}>
        <AuroraSphere tint="oklch(0.65 0.18 40)" state="thinking" radius={0.42} glow={1.3}/>
        <div style={{ position: 'absolute', top: 18, left: 18, right: 18, display: 'flex', justifyContent: 'space-between' }}>
          <Eyebrow dot="var(--ember-500)">Grimoire · session 0341</Eyebrow>
          <span className="tech">offline</span>
        </div>
        <div style={{ position: 'absolute', bottom: 18, left: 18, right: 18 }}>
          <Display size={42}>Bonjour<br/><em style={{ color: 'var(--ember-500)' }}>Juan</em></Display>
          <div className="tech" style={{ marginTop: 6 }}>4 missions · 2 actives · cowork ETA 02:18</div>
        </div>
      </div>

      {/* Module deck */}
      <div style={{ padding: '20px 18px 8px' }}>
        <Eyebrow style={{ marginBottom: 12 }}>Modules</Eyebrow>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {AURORA_MODULES.slice(0, 6).map(m => (
            <div key={m.id} style={{
              padding: 14, border: '1px solid var(--line)', borderRadius: 14,
              background: 'var(--bg-card)', position: 'relative', overflow: 'hidden'
            }}>
              <div style={{ position: 'absolute', top: -20, right: -20, width: 70, height: 70, opacity: 0.6 }}>
                <AuroraSphere tint={m.tint} state="idle" radius={0.4} glow={1}/>
              </div>
              <div style={{
                width: 28, height: 28, borderRadius: 8, background: m.tint,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--ink-1000)',
                marginBottom: 10, boxShadow: `0 0 18px ${m.tint}`
              }}>{m.glyph}</div>
              <div style={{ fontFamily: 'var(--font-display)', fontStyle: 'italic', fontSize: 22, letterSpacing: '-0.01em' }}>{m.label}</div>
              <div className="tech" style={{ marginTop: 4 }}>swipe →</div>
            </div>
          ))}
        </div>
      </div>

      {/* Forge queue */}
      <div style={{ padding: '12px 18px' }}>
        <Panel raised style={{ padding: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <Eyebrow dot="var(--ember-500)">Forge · queue</Eyebrow>
            <span className="tech">3 / 7</span>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} style={{ flex: 1, height: 4, borderRadius: 99, background: i < 3 ? 'var(--ember-500)' : i === 3 ? 'oklch(0.65 0.18 40 / 0.5)' : 'var(--ink-800)' }}/>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--fg-mute)' }}>
            <span>portrait → variations</span><span>ETA 41s</span>
          </div>
        </Panel>
      </div>

      {/* Bottom dock */}
      <div style={{ position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 6, padding: 8, background: 'var(--bg-raised)', border: '1px solid var(--line)', borderRadius: 99, boxShadow: '0 12px 30px rgba(0,0,0,0.5)' }}>
        {['◐', '✺', '◌', '⌘'].map((g, i) => (
          <div key={i} style={{
            width: 44, height: 44, borderRadius: 99,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: i === 1 ? 'var(--ember-500)' : 'transparent',
            color: i === 1 ? 'var(--ink-1000)' : 'var(--fg-dim)',
            fontFamily: 'var(--font-mono)', fontSize: 18,
            boxShadow: i === 1 ? '0 0 24px var(--ember-500)' : 'none'
          }}>{g}</div>
        ))}
      </div>
    </div>
  );
}

window.MobileGrimoire = MobileGrimoire;
