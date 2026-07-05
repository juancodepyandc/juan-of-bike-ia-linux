/* AppShell — global desktop chrome. Sidebar, top bar, command bar, ambient bg. */

function AmbientBackdrop({ tint = 'var(--aura-cowork)' }) {
  return (
    <div style={{
      position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', zIndex: 0
    }}>
      {/* gradient wash */}
      <div style={{
        position: 'absolute', inset: '-20%',
        background: `radial-gradient(ellipse 60% 40% at 78% 12%, ${tint}, transparent 55%),
                     radial-gradient(ellipse 50% 30% at 12% 88%, var(--ember-700), transparent 60%)`,
        opacity: 0.35,
        filter: 'blur(40px)',
      }}/>
      {/* particle field */}
      {window.AmbientField && <AmbientField tint={tint} density={0.8}/>}
      {/* faint horizon line */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: '50%',
        height: 1, background: 'var(--line-soft)', opacity: 0.5
      }}/>
      {/* technical grid */}
      <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, opacity: 0.06 }}>
        <defs>
          <pattern id="agrid" width="80" height="80" patternUnits="userSpaceOnUse">
            <path d="M 80 0 L 0 0 0 80" fill="none" stroke="var(--fg)" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#agrid)"/>
      </svg>
    </div>
  );
}

function TopBar({ moduleLabel, moduleId, tint, breadcrumbs = [] }) {
  return (
    <div style={{
      height: 56, padding: '0 22px',
      display: 'flex', alignItems: 'center', gap: 18,
      borderBottom: '1px solid var(--line)',
      background: 'color-mix(in oklch, var(--bg) 78%, transparent)',
      backdropFilter: 'blur(12px)',
      position: 'relative', zIndex: 5
    }}>
      {/* logotype */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <span style={{
          width: 22, height: 22, borderRadius: 99, flexShrink: 0,
          background: `radial-gradient(circle at 30% 30%, var(--ember-200), var(--ember-600))`,
          boxShadow: '0 0 18px var(--ember-500)'
        }}/>
        <span style={{
          fontFamily: 'var(--font-display)', fontStyle: 'italic',
          fontSize: 22, letterSpacing: '-0.02em', lineHeight: 1
        }}>Aurora</span>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-mute)',
          letterSpacing: '0.1em', textTransform: 'uppercase',
          border: '1px solid var(--line)', padding: '2px 6px', borderRadius: 3,
          whiteSpace: 'nowrap'
        }}>v2.4 · LOCAL</span>
      </div>

      <span style={{ width: 1, height: 22, background: 'var(--line)', flexShrink: 0 }}/>

      {/* breadcrumb */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        fontFamily: 'var(--font-mono)', fontSize: 12,
        whiteSpace: 'nowrap', minWidth: 0, overflow: 'hidden'
      }}>
        <span style={{ color: 'var(--fg-mute)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{moduleId} /</span>
        <span style={{ color: 'var(--fg)' }}>{moduleLabel}</span>
        {breadcrumbs.map((b, i) => (
          <React.Fragment key={i}>
            <span style={{ color: 'var(--fg-mute)' }}>/</span>
            <span style={{ color: i === breadcrumbs.length - 1 ? 'var(--fg)' : 'var(--fg-dim)' }}>{b}</span>
          </React.Fragment>
        ))}
      </div>

      <div style={{ flex: 1 }}/>

      {/* status cluster */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-dim)' }}>
        <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <PulseDot color="oklch(0.74 0.13 145)" size={6}/> ollama:qwen3-vl
        </span>
        <span>ctx 14.2k / 32k</span>
        <span>vram 19.3 / 24 gb</span>
      </div>

      <Btn size="sm" variant="ghost">⌘K</Btn>
      <Btn size="sm" variant="ghost">⌘,</Btn>
    </div>
  );
}

function Sidebar({ activeId = 'cowork' }) {
  return (
    <div style={{
      width: 232, padding: '20px 14px',
      borderRight: '1px solid var(--line)',
      background: 'color-mix(in oklch, var(--bg-raised) 50%, transparent)',
      display: 'flex', flexDirection: 'column', gap: 4,
      position: 'relative', zIndex: 5
    }}>
      <Eyebrow style={{ padding: '0 12px 8px' }}>Modules</Eyebrow>
      {AURORA_MODULES.map(m => (
        <SideItem key={m.id} {...m} active={m.id === activeId}/>
      ))}
      <div style={{ flex: 1 }}/>
      <Eyebrow style={{ padding: '14px 12px 6px' }}>Session</Eyebrow>
      <div style={{
        padding: 12, border: '1px solid var(--line)', borderRadius: 10,
        display: 'flex', gap: 10, alignItems: 'center'
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 99,
          background: 'radial-gradient(circle at 30% 30%, var(--ember-200), var(--ember-700))',
        }}/>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Juan · solo</div>
          <div style={{ fontSize: 10, color: 'var(--fg-mute)', fontFamily: 'var(--font-mono)' }}>session 0341 · 4h12</div>
        </div>
      </div>
    </div>
  );
}

function AppShell({ activeId, moduleLabel, tint, children, breadcrumbs }) {
  const mod = AURORA_MODULES.find(m => m.id === activeId);
  return (
    <div style={{
      width: '100%', minHeight: '100vh', height: '100vh',
      background: 'var(--bg)', color: 'var(--fg)',
      display: 'flex', flexDirection: 'column', position: 'relative',
      overflow: 'hidden'
    }} className="grain">
      <AmbientBackdrop tint={tint || mod?.tint}/>
      <TopBar moduleId={mod?.id?.toUpperCase()} moduleLabel={moduleLabel || mod?.label} tint={tint || mod?.tint} breadcrumbs={breadcrumbs}/>
      <div style={{ display: 'flex', flex: 1, minHeight: 0, position: 'relative', zIndex: 2 }}>
        <Sidebar activeId={activeId}/>
        <main style={{ flex: 1, minWidth: 0, position: 'relative', overflow: 'hidden' }}>
          {children}
        </main>
      </div>
    </div>
  );
}

Object.assign(window, { AppShell, AmbientBackdrop, TopBar, Sidebar });
