/* AuroraSphere — WebGL2 noise sphere with explicit error checking + canvas fallback. */
const { useEffect, useRef } = React;

const VERT_SRC = [
  '#version 300 es',
  'precision highp float;',
  'in vec2 a_pos;',
  'out vec2 v_uv;',
  'void main() {',
  '  v_uv = a_pos * 0.5 + 0.5;',
  '  gl_Position = vec4(a_pos, 0.0, 1.0);',
  '}'
].join('\n');

const FRAG_SRC = [
  '#version 300 es',
  'precision highp float;',
  'out vec4 fragColor;',
  'uniform float u_time;',
  'uniform vec2 u_res;',
  'uniform vec3 u_tint;',
  'uniform float u_amp;',
  'uniform float u_speed;',
  'uniform float u_radius;',
  'uniform float u_glow;',
  '',
  'vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x, 289.0);}',
  'vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}',
  'float snoise(vec3 v){',
  '  const vec2 C = vec2(1.0/6.0, 1.0/3.0);',
  '  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);',
  '  vec3 i  = floor(v + dot(v, C.yyy));',
  '  vec3 x0 = v - i + dot(i, C.xxx);',
  '  vec3 g = step(x0.yzx, x0.xyz);',
  '  vec3 l = 1.0 - g;',
  '  vec3 i1 = min(g.xyz, l.zxy);',
  '  vec3 i2 = max(g.xyz, l.zxy);',
  '  vec3 x1 = x0 - i1 + C.xxx;',
  '  vec3 x2 = x0 - i2 + C.yyy;',
  '  vec3 x3 = x0 - D.yyy;',
  '  i = mod(i, 289.0);',
  '  vec4 p = permute( permute( permute(',
  '            i.z + vec4(0.0, i1.z, i2.z, 1.0))',
  '          + i.y + vec4(0.0, i1.y, i2.y, 1.0))',
  '          + i.x + vec4(0.0, i1.x, i2.x, 1.0));',
  '  float n_ = 1.0/7.0;',
  '  vec3 ns = n_ * D.wyz - D.xzx;',
  '  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);',
  '  vec4 x_ = floor(j * ns.z);',
  '  vec4 y_ = floor(j - 7.0 * x_);',
  '  vec4 x = x_ * ns.x + ns.yyyy;',
  '  vec4 y = y_ * ns.x + ns.yyyy;',
  '  vec4 h = 1.0 - abs(x) - abs(y);',
  '  vec4 b0 = vec4(x.xy, y.xy);',
  '  vec4 b1 = vec4(x.zw, y.zw);',
  '  vec4 s0 = floor(b0)*2.0 + 1.0;',
  '  vec4 s1 = floor(b1)*2.0 + 1.0;',
  '  vec4 sh = -step(h, vec4(0.0));',
  '  vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;',
  '  vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;',
  '  vec3 p0 = vec3(a0.xy, h.x);',
  '  vec3 p1 = vec3(a0.zw, h.y);',
  '  vec3 p2 = vec3(a1.xy, h.z);',
  '  vec3 p3 = vec3(a1.zw, h.w);',
  '  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));',
  '  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;',
  '  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);',
  '  m = m * m;',
  '  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));',
  '}',
  '',
  'void main() {',
  '  vec2 uv = (gl_FragCoord.xy - 0.5*u_res) / min(u_res.x, u_res.y);',
  '  float r = length(uv);',
  '  float t = u_time * 0.0008 * u_speed;',
  '  float R = u_radius;',
  '  float core = smoothstep(R, R - 0.005, r);',
  '  float halo = smoothstep(R + 0.45 * u_glow, R, r);',
  '  vec3 p = vec3(uv * 2.5, t);',
  '  float n1 = snoise(p);',
  '  float n2 = snoise(p * 1.7 + vec3(n1 * 1.2));',
  '  float n3 = snoise(p * 3.2 + vec3(n2 * 0.8) + 5.0);',
  '  float n  = (n1 * 0.55 + n2 * 0.30 + n3 * 0.15);',
  '  float pulse = 0.5 + 0.5 * sin(u_time * 0.002 * (1.0 + 2.0 * u_amp));',
  '  n += u_amp * 0.35 * pulse;',
  '  float h = sqrt(max(0.0, R*R - r*r));',
  '  vec3 N = normalize(vec3(uv, h));',
  '  vec3 L = normalize(vec3(0.4, 0.6, 0.8));',
  '  float lambert = max(0.0, dot(N, L));',
  '  float rim = pow(1.0 - max(0.0, N.z), 2.5);',
  '  vec3 deep = u_tint * 0.18;',
  '  vec3 mid  = u_tint * 0.65;',
  '  vec3 hot  = mix(u_tint, vec3(1.0), 0.55);',
  '  vec3 col = mix(deep, mid, smoothstep(-0.3, 0.4, n));',
  '  col = mix(col, hot, smoothstep(0.4, 0.95, n + lambert * 0.2));',
  '  col += rim * u_tint * 0.6;',
  '  vec3 outer = u_tint * halo * 0.5 * u_glow;',
  '  vec3 final = col * core + outer;',
  '  float alpha = max(core, halo * 0.85);',
  '  fragColor = vec4(final, alpha);',
  '}'
].join('\n');

function compile(gl, type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    console.error('Shader compile error:', gl.getShaderInfoLog(s));
    console.error(src);
    return null;
  }
  return s;
}

function oklchToRgb(input) {
  if (typeof input === 'string' && input.startsWith('#')) {
    return [parseInt(input.slice(1,3),16)/255, parseInt(input.slice(3,5),16)/255, parseInt(input.slice(5,7),16)/255];
  }
  const m = String(input).match(/oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/);
  if (!m) return [1, 0.5, 0.2];
  const L = parseFloat(m[1]), C = parseFloat(m[2]), H = parseFloat(m[3]) * Math.PI/180;
  const a = C * Math.cos(H), b = C * Math.sin(H);
  const l_ = L + 0.3963377774*a + 0.2158037573*b;
  const m_ = L - 0.1055613458*a - 0.0638541728*b;
  const s_ = L - 0.0894841775*a - 1.2914855480*b;
  const l = l_*l_*l_, mm = m_*m_*m_, s = s_*s_*s_;
  const r =  4.0767416621*l - 3.3077115913*mm + 0.2309699292*s;
  const g = -1.2684380046*l + 2.6097574011*mm - 0.3413193965*s;
  const bl = -0.0041960863*l - 0.7034186147*mm + 1.7076147010*s;
  return [Math.max(0,Math.min(1,r)), Math.max(0,Math.min(1,g)), Math.max(0,Math.min(1,bl))];
}

/* Canvas2D fallback — animated radial noise sphere. Used if WebGL fails. */
function canvas2dFallback(canvas, getTint, getState) {
  const ctx = canvas.getContext('2d');
  let raf, t0 = performance.now();
  function tick() {
    const t = performance.now() - t0;
    const w = canvas.width, h = canvas.height;
    const cx = w / 2, cy = h / 2;
    const R = Math.min(w, h) * 0.34;
    const tint = getTint();
    const state = getState();
    const amp = state === 'voice' ? 0.65 : state === 'thinking' ? 0.45 : state === 'streaming' ? 0.3 : 0.1;
    const pulse = 1 + amp * 0.12 * Math.sin(t * 0.003);

    ctx.clearRect(0, 0, w, h);
    // outer halo
    const halo = ctx.createRadialGradient(cx, cy, R * 0.4, cx, cy, R * 1.7);
    halo.addColorStop(0, `rgba(${tint[0]*255|0},${tint[1]*255|0},${tint[2]*255|0},0.55)`);
    halo.addColorStop(1, `rgba(${tint[0]*255|0},${tint[1]*255|0},${tint[2]*255|0},0)`);
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, w, h);

    // core sphere with internal turbulence approximated by layered radial gradients
    for (let i = 0; i < 4; i++) {
      const ox = Math.cos(t * 0.0008 + i * 1.6) * R * 0.25;
      const oy = Math.sin(t * 0.0011 + i * 2.1) * R * 0.25;
      const grad = ctx.createRadialGradient(cx + ox, cy + oy, 0, cx + ox, cy + oy, R * pulse);
      const inner = `rgba(${(tint[0]*255*1.4)|0},${(tint[1]*255*1.4)|0},${(tint[2]*255*1.4)|0},0.55)`;
      grad.addColorStop(0, inner);
      grad.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.globalCompositeOperation = 'lighter';
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, R * pulse, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalCompositeOperation = 'source-over';
    raf = requestAnimationFrame(tick);
  }
  tick();
  return () => cancelAnimationFrame(raf);
}

function AuroraSphere({
  tint = 'oklch(0.65 0.180 40)',
  state = 'idle',
  radius = 0.34,
  glow = 1.0,
  className = '',
  style = {}
}) {
  const canvasRef = useRef(null);
  const stateRef = useRef({ amp: 0.15, speed: 1, tgtAmp: 0.15, tgtSpeed: 1, tint, state });

  useEffect(() => {
    const targets = ({
      idle:      { amp: 0.10, speed: 0.7 },
      thinking:  { amp: 0.45, speed: 1.6 },
      streaming: { amp: 0.30, speed: 1.2 },
      voice:     { amp: 0.65, speed: 2.4 },
    })[state] || { amp: 0.10, speed: 0.7 };
    stateRef.current.tgtAmp = targets.amp;
    stateRef.current.tgtSpeed = targets.speed;
    stateRef.current.state = state;
    stateRef.current.tint = tint;
  }, [state, tint]);

  useEffect(() => {
    const canvas = canvasRef.current;
    let cleanup = () => {};

    const gl = canvas.getContext('webgl2', { premultipliedAlpha: false, antialias: true });
    if (!gl) {
      cleanup = canvas2dFallback(canvas,
        () => oklchToRgb(stateRef.current.tint),
        () => stateRef.current.state);
      const ro = new ResizeObserver(() => {
        const dpr = Math.min(2, window.devicePixelRatio || 1);
        const r = canvas.getBoundingClientRect();
        canvas.width = Math.max(2, Math.floor(r.width * dpr));
        canvas.height = Math.max(2, Math.floor(r.height * dpr));
      });
      ro.observe(canvas);
      const orig = cleanup;
      cleanup = () => { orig(); ro.disconnect(); };
      return () => cleanup();
    }

    const vs = compile(gl, gl.VERTEX_SHADER, VERT_SRC);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG_SRC);
    if (!vs || !fs) {
      console.warn('Aurora: shader compile failed, using canvas2d fallback');
      cleanup = canvas2dFallback(canvas,
        () => oklchToRgb(stateRef.current.tint),
        () => stateRef.current.state);
      return () => cleanup();
    }

    const prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      console.error('Aurora link error:', gl.getProgramInfoLog(prog));
      cleanup = canvas2dFallback(canvas,
        () => oklchToRgb(stateRef.current.tint),
        () => stateRef.current.state);
      return () => cleanup();
    }
    gl.useProgram(prog);

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(prog, 'a_pos');
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

    const uTime = gl.getUniformLocation(prog, 'u_time');
    const uRes = gl.getUniformLocation(prog, 'u_res');
    const uTint = gl.getUniformLocation(prog, 'u_tint');
    const uAmp = gl.getUniformLocation(prog, 'u_amp');
    const uSpeed = gl.getUniformLocation(prog, 'u_speed');
    const uRadius = gl.getUniformLocation(prog, 'u_radius');
    const uGlow = gl.getUniformLocation(prog, 'u_glow');

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    function resize() {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const r = canvas.getBoundingClientRect();
      canvas.width = Math.max(2, Math.floor(r.width * dpr));
      canvas.height = Math.max(2, Math.floor(r.height * dpr));
      gl.viewport(0, 0, canvas.width, canvas.height);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    let raf, t0 = performance.now();
    function frame() {
      const t = performance.now() - t0;
      const s = stateRef.current;
      s.amp += (s.tgtAmp - s.amp) * 0.04;
      s.speed += (s.tgtSpeed - s.speed) * 0.04;
      const rgb = oklchToRgb(s.tint);
      gl.uniform1f(uTime, t);
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform3f(uTint, rgb[0], rgb[1], rgb[2]);
      gl.uniform1f(uAmp, s.amp);
      gl.uniform1f(uSpeed, s.speed);
      gl.uniform1f(uRadius, radius);
      gl.uniform1f(uGlow, glow);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      raf = requestAnimationFrame(frame);
    }
    frame();

    cleanup = () => { cancelAnimationFrame(raf); ro.disconnect(); };
    return () => cleanup();
  }, [radius, glow]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ display: 'block', width: '100%', height: '100%', ...style }}
    />
  );
}

window.AuroraSphere = AuroraSphere;
window.oklchToRgb = oklchToRgb;
