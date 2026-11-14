/* AmbientField — WebGL particle field that drifts behind everything.
   Adds depth + life to every screen without competing with the sphere. */
const { useEffect: useEA, useRef: useRA } = React;

function AmbientField({ tint = 'oklch(0.65 0.18 40)', density = 1, speed = 1 }) {
  const ref = useRA(null);
  useEA(() => {
    const canvas = ref.current;
    const ctx = canvas.getContext('2d');
    let raf, t0 = performance.now();
    const N = Math.floor(80 * density);
    const parts = Array.from({ length: N }, () => ({
      x: Math.random(), y: Math.random(),
      z: Math.random() * 0.7 + 0.3,   // depth: 0.3..1
      r: Math.random() * 1.6 + 0.3,
      vy: (Math.random() * 0.00006 + 0.00002) * speed,
      vx: (Math.random() - 0.5) * 0.00004 * speed,
      ph: Math.random() * Math.PI * 2,
    }));
    const rgb = (window.oklchToRgb || (() => [0.7, 0.5, 0.3]))(tint);
    const R = (rgb[0] * 255) | 0, G = (rgb[1] * 255) | 0, B = (rgb[2] * 255) | 0;

    function resize() {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const r = canvas.getBoundingClientRect();
      canvas.width = Math.max(2, r.width * dpr);
      canvas.height = Math.max(2, r.height * dpr);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    function tick() {
      const t = performance.now() - t0;
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      for (const p of parts) {
        p.y -= p.vy;
        p.x += p.vx + Math.sin(t * 0.0003 + p.ph) * 0.00012;
        if (p.y < -0.05) { p.y = 1.05; p.x = Math.random(); }
        if (p.x < -0.05) p.x = 1.05;
        if (p.x > 1.05) p.x = -0.05;
        const a = 0.18 * p.z + 0.05 * Math.sin(t * 0.001 + p.ph);
        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, p.r * p.z * 1.4, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${R},${G},${B},${Math.max(0, a)})`;
        ctx.fill();
      }
      raf = requestAnimationFrame(tick);
    }
    tick();
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [tint, density, speed]);
  return <canvas ref={ref} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 1 }}/>;
}

/* OrbitRing — concentric thin rings with traveling dot, wraps a sphere for hero scenes. */
function OrbitRing({ radius = 240, dotted = true, speed = 24, count = 1, color = 'var(--line-strong)', dotColor = 'var(--ember-500)' }) {
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
      {Array.from({ length: count }).map((_, i) => {
        const r = radius + i * 28;
        return (
          <div key={i} style={{
            position: 'absolute', width: r * 2, height: r * 2, borderRadius: '50%',
            border: `1px ${dotted ? 'dashed' : 'solid'} ${color}`,
            opacity: 0.35 - i * 0.08,
            animation: `aurora-orbit-${speed} ${speed + i * 6}s linear infinite`
          }}>
            <div style={{
              position: 'absolute', top: -3, left: '50%', transform: 'translateX(-50%)',
              width: 6, height: 6, borderRadius: 99, background: dotColor,
              boxShadow: `0 0 14px ${dotColor}`
            }}/>
          </div>
        );
      })}
      <style>{`@keyframes aurora-orbit-${speed} { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}

/* MegaType — juanmora-style massive editorial title that pushes the layout. */
function MegaType({ children, size = 220, style }) {
  return (
    <h1 style={{
      fontFamily: 'var(--font-display)', fontStyle: 'italic',
      fontWeight: 400, fontSize: size, lineHeight: 0.86,
      letterSpacing: '-0.04em', margin: 0,
      textWrap: 'balance', color: 'var(--fg)',
      ...style
    }}>{children}</h1>
  );
}

/* Vertical rotated label — paradisoinstitute-style edge marker */
function EdgeLabel({ children, side = 'left', style }) {
  return (
    <div style={{
      position: 'absolute', [side]: 14, top: '50%',
      transform: `translateY(-50%) rotate(${side === 'left' ? -90 : 90}deg)`,
      transformOrigin: 'center',
      fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.3em',
      textTransform: 'uppercase', color: 'var(--fg-mute)',
      whiteSpace: 'nowrap', ...style
    }}>{children}</div>
  );
}

Object.assign(window, { AmbientField, OrbitRing, MegaType, EdgeLabel });
