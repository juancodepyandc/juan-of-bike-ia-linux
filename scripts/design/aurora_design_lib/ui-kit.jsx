/* Aurora UI primitives — shared across all module mocks. */
const { useState: useStateK, useEffect: useEffectK, useRef: useRefK } = React;

/* ------------ Eyebrow / Tech label ------------ */
function Eyebrow({ children, dot, style }) {
  return (
    <span style={{
      fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.14em',
      textTransform: 'uppercase', color: 'var(--fg-mute)',
      display: 'inline-flex', alignItems: 'center', gap: 8, ...style
    }}>
      {dot && <span style={{ width: 6, height: 6, borderRadius: 99, background: dot, boxShadow: `0 0 12px ${dot}` }}/>}
      {children}
    </span>
  );
}

/* ------------ Editorial display heading ------------ */
function Display({ children, size = 96, italic = true, weight = 400, style }) {
  return (
    <h1 style={{
      fontFamily: 'var(--font-display)',
      fontStyle: italic ? 'italic' : 'normal',
      fontWeight: weight, fontSize: size, lineHeight: 0.92,
      letterSpacing: '-0.025em', margin: 0, color: 'var(--fg)',
      textWrap: 'balance', ...style
    }}>{children}</h1>
  );
}

/* ------------ Button ------------ */
function Btn({ children, variant = 'ghost', size = 'md', icon, style, ...rest }) {
  const sizes = {
    sm: { padding: '6px 10px', fontSize: 12, height: 28 },
    md: { padding: '9px 14px', fontSize: 13, height: 36 },
    lg: { padding: '12px 18px', fontSize: 14, height: 44 },
  }[size];
  const variants = {
    primary: { background: 'var(--ember-500)', color: 'var(--ink-1000)', border: '1px solid var(--ember-500)' },
    ghost:   { background: 'transparent', color: 'var(--fg)', border: '1px solid var(--line)' },
    solid:   { background: 'var(--ink-800)', color: 'var(--fg)', border: '1px solid var(--line)' },
    bare:    { background: 'transparent', color: 'var(--fg-dim)', border: '1px solid transparent' },
  }[variant];
  return (
    <button {...rest} style={{
      ...sizes, ...variants,
      borderRadius: 999, fontFamily: 'var(--font-sans)', fontWeight: 500,
      letterSpacing: '-0.005em', cursor: 'pointer', display: 'inline-flex',
      alignItems: 'center', gap: 8, transition: 'all .25s var(--ease-out)',
      whiteSpace: 'nowrap', ...style
    }}>
      {icon}{children}
    </button>
  );
}

/* ------------ Card / panel ------------ */
function Panel({ children, style, padded = true, bordered = true, raised = false }) {
  return (
    <div style={{
      background: raised ? 'var(--bg-card)' : 'var(--bg-raised)',
      border: bordered ? '1px solid var(--line)' : 'none',
      borderRadius: 14, padding: padded ? 18 : 0,
      position: 'relative', ...style
    }}>{children}</div>
  );
}

/* ------------ Tag / chip ------------ */
function Tag({ children, tint, style }) {
  return (
    <span style={{
      fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.06em',
      textTransform: 'uppercase', color: tint || 'var(--fg-dim)',
      border: `1px solid ${tint ? tint : 'var(--line)'}`,
      padding: '3px 8px', borderRadius: 4, display: 'inline-block', ...style
    }}>{children}</span>
  );
}

/* ------------ Marquee / ticker ------------ */
function Ticker({ items, speed = 30, style }) {
  return (
    <div style={{
      overflow: 'hidden', whiteSpace: 'nowrap', position: 'relative',
      borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)',
      padding: '12px 0', ...style
    }}>
      <div style={{
        display: 'inline-block',
        animation: `aurora-marquee ${speed}s linear infinite`,
      }}>
        {[...items, ...items].map((t, i) => (
          <span key={i} style={{
            fontFamily: 'var(--font-display)', fontStyle: 'italic',
            fontSize: 28, padding: '0 24px', color: 'var(--fg-dim)',
            letterSpacing: '-0.02em',
          }}>
            {t} <span style={{ color: 'var(--ember-500)', margin: '0 6px' }}>✦</span>
          </span>
        ))}
      </div>
      <style>{`@keyframes aurora-marquee { from { transform: translateX(0) } to { transform: translateX(-50%) } }`}</style>
    </div>
  );
}

/* ------------ Editorial frame line numbers (juanmora-esque) ------------ */
function LineMarks({ count = 12, style }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
      ...style
    }}>
      {Array.from({ length: count }).map((_, i) => (
        <span key={i} style={{
          fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-mute)',
          letterSpacing: '0.08em', opacity: i % 3 === 0 ? 1 : 0.4
        }}>
          {String(i).padStart(3, '0')}
        </span>
      ))}
    </div>
  );
}

/* ------------ Animated glyph: rotating bracket ------------ */
function Spinner({ size = 14, color = 'var(--fg-dim)' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ animation: 'aurora-spin 2s linear infinite' }}>
      <path d="M3 12 a9 9 0 0 1 18 0" stroke={color} strokeWidth="1.8" fill="none" strokeLinecap="round"/>
      <style>{`@keyframes aurora-spin { to { transform: rotate(360deg) } }`}</style>
    </svg>
  );
}

/* ------------ Connector node (used in cowork orchestrator) ------------ */
function NodeDot({ active, size = 10, color = 'var(--ember-500)' }) {
  return (
    <span style={{
      display: 'inline-block', width: size, height: size, borderRadius: 99,
      background: active ? color : 'transparent',
      border: `1px solid ${active ? color : 'var(--line-strong)'}`,
      boxShadow: active ? `0 0 14px ${color}` : 'none',
      transition: 'all .3s var(--ease-out)'
    }}/>
  );
}

/* ------------ Crosshair corners decorator ------------ */
function Crosshairs({ inset = 8, size = 10, color = 'var(--line-strong)' }) {
  const corner = (pos) => ({
    position: 'absolute', width: size, height: size, ...pos
  });
  const stroke = `1px solid ${color}`;
  return (
    <>
      <span style={{ ...corner({ top: inset, left: inset }), borderTop: stroke, borderLeft: stroke }}/>
      <span style={{ ...corner({ top: inset, right: inset }), borderTop: stroke, borderRight: stroke }}/>
      <span style={{ ...corner({ bottom: inset, left: inset }), borderBottom: stroke, borderLeft: stroke }}/>
      <span style={{ ...corner({ bottom: inset, right: inset }), borderBottom: stroke, borderRight: stroke }}/>
    </>
  );
}

/* ------------ Specimen — image placeholder w/ caption (no AI slop SVG) */
function Specimen({ label, ratio = '4 / 3', tint = 'var(--ink-800)', style }) {
  return (
    <div style={{
      aspectRatio: ratio,
      background: `repeating-linear-gradient(135deg, ${tint}, ${tint} 8px, transparent 8px, transparent 16px), var(--bg-raised)`,
      border: '1px solid var(--line)',
      borderRadius: 10,
      position: 'relative',
      overflow: 'hidden',
      ...style
    }}>
      <span style={{
        position: 'absolute', bottom: 8, left: 10,
        fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.08em',
        textTransform: 'uppercase', color: 'var(--fg-mute)',
        background: 'var(--bg)', padding: '2px 6px', borderRadius: 3
      }}>{label}</span>
    </div>
  );
}

/* ------------ Sidebar nav item (used in app shell) ------------ */
function SideItem({ label, glyph, active, tint, kbd }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '9px 12px', borderRadius: 8, cursor: 'pointer',
      background: active ? 'var(--ink-800)' : 'transparent',
      border: active ? '1px solid var(--line)' : '1px solid transparent',
      color: active ? 'var(--fg)' : 'var(--fg-dim)',
      transition: 'all .2s var(--ease-out)',
      position: 'relative'
    }}>
      <span style={{
        width: 22, height: 22, borderRadius: 6,
        background: active ? tint : 'var(--ink-800)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
        color: active ? 'var(--ink-1000)' : 'var(--fg-dim)',
        boxShadow: active ? `0 0 18px ${tint}` : 'none'
      }}>{glyph}</span>
      <span style={{ fontSize: 13, fontWeight: 500, letterSpacing: '-0.005em', flex: 1 }}>{label}</span>
      {kbd && <span style={{
        fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-mute)',
        border: '1px solid var(--line)', padding: '1px 5px', borderRadius: 4
      }}>{kbd}</span>}
    </div>
  );
}

/* ------------ Pulse dot ------------ */
function PulseDot({ color = 'var(--ember-500)', size = 8 }) {
  return (
    <span style={{ position: 'relative', display: 'inline-block', width: size, height: size }}>
      <span style={{
        position: 'absolute', inset: 0, borderRadius: 99, background: color,
        animation: 'aurora-pulse 1.6s ease-out infinite'
      }}/>
      <span style={{
        position: 'absolute', inset: 0, borderRadius: 99, background: color,
      }}/>
      <style>{`@keyframes aurora-pulse {
        0% { transform: scale(1); opacity: 0.6 }
        100% { transform: scale(2.6); opacity: 0 }
      }`}</style>
    </span>
  );
}

/* ------------ Module list — config used everywhere ------------ */
const AURORA_MODULES = [
  { id: 'cowork',  label: 'Cowork',       glyph: '✺', tint: 'var(--aura-cowork)',  kbd: '⌘1' },
  { id: 'chat',    label: 'Conversation', glyph: '◐', tint: 'var(--aura-chat)',    kbd: '⌘2' },
  { id: 'academy', label: 'Academy',      glyph: '∎', tint: 'var(--aura-academy)', kbd: '⌘3' },
  { id: 'image',   label: 'Image',        glyph: '◉', tint: 'var(--aura-image)',   kbd: '⌘4' },
  { id: 'video',   label: 'Vidéo',        glyph: '▷', tint: 'var(--aura-video)',   kbd: '⌘5' },
  { id: 'code',    label: 'Code',         glyph: '⌘', tint: 'var(--aura-code)',    kbd: '⌘6' },
  { id: 'draw',    label: 'Dessin',       glyph: '墨', tint: 'var(--aura-draw)',    kbd: '⌘7' },
  { id: 'tdd',     label: '3D',           glyph: '◇', tint: 'var(--aura-3d)',      kbd: '⌘8' },
  { id: 'voice',   label: 'Voice',        glyph: '◌', tint: 'var(--aura-voice)',   kbd: '⌘9' },
  { id: 'cyber',   label: 'Cyber',        glyph: '※', tint: 'var(--aura-cyber)',   kbd: '⌘0' },
];

Object.assign(window, {
  Eyebrow, Display, Btn, Panel, Tag, Ticker, LineMarks, Spinner,
  NodeDot, Crosshairs, Specimen, SideItem, PulseDot, AURORA_MODULES,
});
