import type { FxModule } from './mascots.tsx'

export type SceneDraw = (ctx: CanvasRenderingContext2D, W: number, H: number, now: number, prog: number, accent: string) => void

export type FxScene = {
  phases: string[]
  says: string[]
  create: () => SceneDraw
}

function glow(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, core = 'rgba(255,255,255,.95)') {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r)
  g.addColorStop(0, core)
  g.addColorStop(0.35, color)
  g.addColorStop(1, 'transparent')
  ctx.fillStyle = g
  ctx.beginPath()
  ctx.arc(x, y, r, 0, 6.2832)
  ctx.fill()
}

function rgba(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`
}

const conversation: FxScene = {
  phases: ['Analyse', 'Plan', 'Brouillon', 'Vérification', 'Raffinage', 'Livraison'],
  says: ['Je décortique ta question…', 'Je structure ma pensée…', 'J\'écris, je relis…', 'Je peaufine chaque mot…'],
  create: () => {
    type Node = { x: number; y: number; vx: number; vy: number; r: number; ph: number; far: boolean; thr: number }
    const WORDS = ['analyse', 'contexte', 'nuance', 'structure', 'preuve', 'clarté', 'synthèse', 'logique', 'intention', 'style']
    let nodes: Node[] = []
    const pulses: { a: number; b: number; p: number; s: number }[] = []
    const words: { w: string; x: number; y: number; life: number; drift: number }[] = []
    return (ctx, W, H, now, prog, accent) => {
      if (!nodes.length) {
        for (let i = 0; i < 74; i++) {
          const far = i < 26
          nodes.push({
            x: Math.random() * W, y: Math.random() * H * 0.86,
            vx: (Math.random() - 0.5) * (far ? 0.12 : 0.3), vy: (Math.random() - 0.5) * (far ? 0.09 : 0.24),
            r: far ? 0.9 + Math.random() : 1.5 + Math.random() * 2.4, ph: Math.random() * 6.28, far,
            thr: (i * 0.618034) % 1,
          })
        }
      }
      const breath = 0.5 + 0.5 * Math.sin(now * 0.0012)
      const g = ctx.createRadialGradient(W / 2, H * 0.42, 0, W / 2, H * 0.42, W * 0.42)
      g.addColorStop(0, rgba(accent, 0.13 + 0.08 * breath))
      g.addColorStop(1, 'transparent')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, W, H)
      for (let ring = 0; ring < 2; ring++) {
        ctx.strokeStyle = rgba(accent, 0.1 - ring * 0.04)
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.arc(W / 2, H * 0.42, (Math.min(W, H) * 0.24 + ring * 34) * (1 + 0.03 * Math.sin(now * 0.0016 + ring)), 0, 6.2832)
        ctx.stroke()
      }
      const gate = 0.12 + 0.88 * Math.min(1, Math.max(0, prog))
      const fade = (n: Node) => Math.min(1, Math.max(0, (gate - n.thr) / 0.07))
      const LINK = Math.min(W, H) * (0.15 + 0.11 * Math.min(1, Math.max(0, prog)))
      const near = nodes.filter((n) => !n.far && n.thr <= gate)
      ctx.lineWidth = 1
      for (let a = 0; a < near.length; a++) {
        for (let b = a + 1; b < near.length; b++) {
          const A = near[a], B = near[b]
          const dx = A.x - B.x, dy = A.y - B.y
          const d = Math.sqrt(dx * dx + dy * dy)
          if (d < LINK) {
            const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2 - d * 0.14
            ctx.strokeStyle = rgba(accent, (1 - d / LINK) * 0.36 * Math.min(fade(A), fade(B)))
            ctx.beginPath()
            ctx.moveTo(A.x, A.y)
            ctx.quadraticCurveTo(mx, my, B.x, B.y)
            ctx.stroke()
            if (Math.random() < 0.004 && pulses.length < 34) pulses.push({ a: nodes.indexOf(A), b: nodes.indexOf(B), p: 0, s: 0.013 + Math.random() * 0.02 })
          }
        }
      }
      ctx.globalCompositeOperation = 'lighter'
      for (let p = pulses.length - 1; p >= 0; p--) {
        const pu = pulses[p]
        pu.p += pu.s
        if (pu.p >= 1) { pulses.splice(p, 1); continue }
        const A = nodes[pu.a], B = nodes[pu.b]
        const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2 - Math.hypot(A.x - B.x, A.y - B.y) * 0.14
        const u = pu.p, v = 1 - u
        const x = v * v * A.x + 2 * v * u * mx + u * u * B.x
        const y = v * v * A.y + 2 * v * u * my + u * u * B.y
        glow(ctx, x, y, 9, rgba(accent, 0.75))
      }
      for (const nd of nodes) {
        nd.x += nd.vx; nd.y += nd.vy
        if (nd.x < -8) nd.x = W + 8
        if (nd.x > W + 8) nd.x = -8
        if (nd.y < -8) nd.y = H * 0.86 + 8
        if (nd.y > H * 0.86 + 8) nd.y = -8
        const f = fade(nd)
        if (f <= 0) continue
        const tw = 0.5 + 0.5 * Math.sin(now * 0.002 + nd.ph)
        glow(ctx, nd.x, nd.y, nd.r * (nd.far ? 3 : 4.6), rgba(accent, (nd.far ? 0.3 : 0.55) * tw * f), nd.far ? rgba(accent, 0.6 * tw * f) : undefined)
      }
      const crys = Math.min(1, Math.max(0, (prog - 0.82) / 0.18))
      if (crys > 0) {
        const ccx = W / 2, ccy = H * 0.42
        ctx.lineWidth = 1
        ctx.strokeStyle = rgba(accent, 0.2 * crys)
        for (let i = 0; i < near.length; i += 2) {
          const nd = near[i]
          ctx.beginPath()
          ctx.moveTo(nd.x, nd.y)
          ctx.lineTo(ccx + (nd.x - ccx) * 0.14, ccy + (nd.y - ccy) * 0.14)
          ctx.stroke()
        }
        const rot = now * 0.0012
        const cR = (10 + 24 * crys) * (1 + 0.05 * Math.sin(now * 0.006))
        for (let h = 0; h < 2; h++) {
          ctx.strokeStyle = h ? `rgba(255,255,255,${0.5 * crys})` : rgba(accent, 0.8 * crys)
          ctx.lineWidth = h ? 1 : 1.8
          ctx.beginPath()
          for (let k = 0; k <= 6; k++) {
            const a = (h ? -rot : rot) + (k / 6) * 6.2832
            const rr = cR * (h ? 0.62 : 1)
            const x = ccx + Math.cos(a) * rr, y = ccy + Math.sin(a) * rr
            if (k === 0) ctx.moveTo(x, y)
            else ctx.lineTo(x, y)
          }
          ctx.closePath()
          ctx.stroke()
        }
        glow(ctx, ccx, ccy, cR * 3, rgba(accent, 0.55 * crys), `rgba(255,255,255,${0.85 * crys})`)
      }
      if (Math.random() < 0.032 && words.length < 8) {
        words.push({ w: WORDS[Math.floor(Math.random() * WORDS.length)], x: W * 0.12 + Math.random() * W * 0.76, y: H * 0.8, life: 1, drift: (Math.random() - 0.5) * 0.35 })
      }
      ctx.textAlign = 'center'
      for (let i = words.length - 1; i >= 0; i--) {
        const wd = words[i]
        wd.y -= 0.6; wd.x += wd.drift; wd.life -= 0.0065
        if (wd.life <= 0) { words.splice(i, 1); continue }
        ctx.font = `300 ${13 + 10 * (1 - wd.life)}px Georgia, serif`
        ctx.fillStyle = `rgba(216,206,255,${wd.life * 0.6})`
        ctx.fillText(wd.w, wd.x, wd.y)
      }
      ctx.globalCompositeOperation = 'source-over'
    }
  },
}

const image: FxScene = {
  phases: ['Analyse du prompt', 'Référence visuelle', 'Diffusion FLUX', 'Édition Kontext', 'Finalisation'],
  says: ['Je capture la lumière…', 'Chaque pixel compte…', 'Les couleurs cristallisent…', 'Dernier coup de prisme…'],
  create: () => {
    const SP = ['#F43F5E', '#F59E0B', '#FDE047', '#A3E635', '#22D3EE', '#8B5CF6', '#F472B6']
    const G = 12
    type Cell = { gx: number; gy: number; a: number; h: string }
    const cells: Cell[] = []
    for (let gy = 0; gy < G; gy++) for (let gx = 0; gx < G; gx++) cells.push({ gx, gy, a: 0, h: SP[(gx * 3 + gy * 5) % SP.length] })
    const parts: { x: number; y: number; tx: number; ty: number; ax: number; ay: number; p: number; s: number; c: string; cell: Cell }[] = []
    return (ctx, W, H, now, prog, accent) => {
      const px = W * 0.26, py = H * 0.44, pr = 32
      const mx = W * 0.68, my = H * 0.44
      const msz = Math.min(H * 0.64, W * 0.3), cell = msz / G
      ctx.globalCompositeOperation = 'lighter'
      for (let r = 0; r < 5; r++) {
        const ang = now * 0.0003 + (r * 6.2832) / 5
        const rg = ctx.createLinearGradient(px, py, px + Math.cos(ang) * W * 0.3, py + Math.sin(ang) * W * 0.3)
        rg.addColorStop(0, 'rgba(255,255,255,.06)')
        rg.addColorStop(1, 'transparent')
        ctx.strokeStyle = rg
        ctx.lineWidth = 26
        ctx.beginPath()
        ctx.moveTo(px, py)
        ctx.lineTo(px + Math.cos(ang) * W * 0.3, py + Math.sin(ang) * W * 0.3)
        ctx.stroke()
      }
      const flick = 0.75 + 0.25 * Math.sin(now * 0.02)
      const beam = ctx.createLinearGradient(0, py, px, py)
      beam.addColorStop(0, 'transparent')
      beam.addColorStop(1, `rgba(255,255,255,${0.55 * flick})`)
      ctx.strokeStyle = beam
      ctx.lineWidth = 3
      ctx.beginPath()
      ctx.moveTo(-10, py + Math.sin(now * 0.003) * 5)
      ctx.lineTo(px - pr * 0.6, py)
      ctx.stroke()
      for (let s = 0; s < SP.length; s++) {
        const ang = (s - (SP.length - 1) / 2) * 0.15
        const ex = px + Math.cos(ang) * W * 0.26, ey = py + Math.sin(ang) * W * 0.26
        const fan = ctx.createLinearGradient(px, py, ex, ey)
        fan.addColorStop(0, SP[s] + 'CC')
        fan.addColorStop(1, SP[s] + '00')
        ctx.strokeStyle = fan
        ctx.lineWidth = 5 + 2 * Math.sin(now * 0.004 + s)
        ctx.beginPath()
        ctx.moveTo(px, py)
        ctx.lineTo(ex, ey)
        ctx.stroke()
        if (Math.random() < 0.6 && parts.length < 340) {
          const cutoffRank = prog * cells.length
          const frontier = cells.filter((c2) => {
            const rank = (G - 1 - c2.gy) * G + c2.gx
            return rank >= cutoffRank - G && rank <= cutoffRank + G * 2
          })
          const cb = frontier.length ? frontier[Math.floor(Math.random() * frontier.length)] : cells[Math.floor(Math.random() * cells.length)]
          parts.push({
            x: px, y: py, ax: ex, ay: ey,
            tx: mx - msz / 2 + (cb.gx + 0.5) * cell, ty: my - msz / 2 + (cb.gy + 0.5) * cell,
            p: 0, s: 0.009 + Math.random() * 0.016, c: SP[s], cell: cb,
          })
        }
      }
      ctx.globalCompositeOperation = 'source-over'
      ctx.beginPath()
      ctx.moveTo(px, py - pr)
      ctx.lineTo(px + pr * 0.9, py + pr * 0.7)
      ctx.lineTo(px - pr * 0.9, py + pr * 0.7)
      ctx.closePath()
      const pg = ctx.createLinearGradient(px - pr, py - pr, px + pr, py + pr)
      pg.addColorStop(0, 'rgba(255,255,255,.2)')
      pg.addColorStop(1, rgba(accent, 0.12))
      ctx.fillStyle = pg
      ctx.fill()
      ctx.strokeStyle = 'rgba(255,255,255,.55)'
      ctx.lineWidth = 1.2
      ctx.stroke()
      ctx.globalCompositeOperation = 'lighter'
      for (let p = parts.length - 1; p >= 0; p--) {
        const pt = parts[p]
        pt.p += pt.s
        if (pt.p >= 1) { parts.splice(p, 1); continue }
        const u = pt.p, v = 1 - u
        const x = v * v * pt.x + 2 * v * u * pt.ax + u * u * pt.tx
        const y = v * v * pt.y + 2 * v * u * pt.ay + u * u * pt.ty
        glow(ctx, x, y, 5.5, pt.c + 'EE')
      }
      ctx.globalCompositeOperation = 'source-over'
      const cutoff = prog * cells.length
      for (const ce of cells) {
        const rank = (G - 1 - ce.gy) * G + ce.gx
        const target = rank < cutoff ? 1 : rank < cutoff + G ? 0.18 : 0
        ce.a += (target - ce.a) * 0.09
        if (ce.a <= 0.01) continue
        ctx.globalAlpha = ce.a * (0.6 + 0.18 * Math.sin(now * 0.002 + ce.gx + ce.gy))
        ctx.fillStyle = ce.h
        ctx.fillRect(mx - msz / 2 + ce.gx * cell + 1, my - msz / 2 + ce.gy * cell + 1, cell - 2, cell - 2)
      }
      ctx.globalAlpha = 1
      const fillY = my + msz / 2 - msz * Math.min(1, cutoff / cells.length)
      const fg = ctx.createLinearGradient(0, fillY - 10, 0, fillY + 10)
      fg.addColorStop(0, 'transparent')
      fg.addColorStop(0.5, 'rgba(255,255,255,.35)')
      fg.addColorStop(1, 'transparent')
      ctx.fillStyle = fg
      ctx.fillRect(mx - msz / 2, fillY - 10, msz, 20)
      ctx.strokeStyle = 'rgba(255,255,255,.3)'
      ctx.lineWidth = 1.5
      ctx.strokeRect(mx - msz / 2 - 5, my - msz / 2 - 5, msz + 10, msz + 10)
      const bx0 = mx - msz / 2 - 5, by0 = my - msz / 2 - 5, bs = msz + 10
      const per = bs * 4 * Math.min(1, Math.max(0, prog))
      if (per > 0) {
        const cor: [number, number][] = [[bx0, by0], [bx0 + bs, by0], [bx0 + bs, by0 + bs], [bx0, by0 + bs], [bx0, by0]]
        ctx.strokeStyle = rgba(accent, 0.95)
        ctx.lineWidth = 2.6
        ctx.shadowColor = accent
        ctx.shadowBlur = 9
        ctx.beginPath()
        ctx.moveTo(bx0, by0)
        let left = per
        let hx2 = bx0, hy2 = by0
        for (let c2 = 0; c2 < 4 && left > 0; c2++) {
          const seg = Math.min(left, bs)
          hx2 = cor[c2][0] + ((cor[c2 + 1][0] - cor[c2][0]) * seg) / bs
          hy2 = cor[c2][1] + ((cor[c2 + 1][1] - cor[c2][1]) * seg) / bs
          ctx.lineTo(hx2, hy2)
          left -= seg
        }
        ctx.stroke()
        ctx.shadowBlur = 0
        if (prog < 1) {
          ctx.globalCompositeOperation = 'lighter'
          glow(ctx, hx2, hy2, 11, rgba(accent, 0.85))
          ctx.globalCompositeOperation = 'source-over'
        }
      }
      if (prog > 0.95) {
        const halo = Math.min(1, (prog - 0.95) / 0.05) * (0.75 + 0.25 * Math.sin(now * 0.008))
        ctx.globalCompositeOperation = 'lighter'
        glow(ctx, mx, my, msz * 0.85, rgba(accent, 0.35 * halo), `rgba(255,255,255,${0.3 * halo})`)
        ctx.globalCompositeOperation = 'source-over'
      }
      const sweep = ((now * 0.00045) % 1.4) - 0.2
      const sx0 = mx - msz / 2 + msz * sweep
      const sg = ctx.createLinearGradient(sx0 - 22, 0, sx0 + 22, 0)
      sg.addColorStop(0, 'transparent')
      sg.addColorStop(0.5, 'rgba(255,255,255,.16)')
      sg.addColorStop(1, 'transparent')
      ctx.fillStyle = sg
      ctx.fillRect(mx - msz / 2, my - msz / 2, msz, msz)
    }
  },
}

const code: FxScene = {
  phases: ['Intention', 'Architecture', 'Recherche', 'Génération', 'Sandbox', 'Correction', 'Livraison'],
  says: ['J\'analyse ton besoin…', 'Je pose les fondations…', 'J\'écris chaque fichier…', 'Je compile, je corrige…', 'C\'est du solide.'],
  create: () => {
    const GL = '{}[]()<>=>;:+*/&|!?#$%λΔΦ01'.split('')
    type Col = { x: number; y: number; s: number; seed: number }
    let cols: Col[] = []
    let colsW = 0
    type Trace = { x0: number; y0: number; x1: number; y1: number; x2: number; y2: number; p: number; s: number }
    const traces: Trace[] = []
    const sparks: { x: number; y: number; vx: number; vy: number; life: number }[] = []
    return (ctx, W, H, now, prog, accent) => {
      if (!cols.length || colsW !== W) {
        colsW = W
        cols = []
        for (let x = 8; x < W; x += 17) cols.push({ x, y: Math.random() * H, s: 0.6 + Math.random() * 1.9, seed: Math.floor(Math.random() * 99) })
      }
      ctx.font = '11px Consolas, monospace'
      for (const col of cols) {
        col.y += col.s
        if (col.y > H + 20) { col.y = -20; col.seed = Math.floor(Math.random() * 99) }
        for (let k = 0; k < 8; k++) {
          const gy = col.y - k * 13
          if (gy < -12 || gy > H) continue
          ctx.fillStyle = rgba(accent, Math.max(0, (k === 0 ? 0.85 : 0.5 - k * 0.06) * 0.42))
          ctx.fillText(GL[(col.seed + k * 7 + Math.floor(now * 0.004 * col.s)) % GL.length], col.x, gy)
        }
      }
      if (traces.length < 7 && Math.random() < 0.05) {
        const y0 = H * (0.15 + Math.random() * 0.7)
        const x1 = W * (0.2 + Math.random() * 0.6)
        traces.push({ x0: -10, y0, x1, y1: y0, x2: x1, y2: y0 + (Math.random() < 0.5 ? -1 : 1) * H * 0.28, p: 0, s: 0.004 + Math.random() * 0.007 })
      }
      ctx.lineWidth = 1
      for (let t = traces.length - 1; t >= 0; t--) {
        const tr = traces[t]
        tr.p += tr.s
        if (tr.p >= 1.25) { traces.splice(t, 1); continue }
        const p1 = Math.min(1, tr.p * 2), p2 = Math.max(0, Math.min(1, tr.p * 2 - 1))
        ctx.strokeStyle = rgba(accent, 0.16)
        ctx.beginPath()
        ctx.moveTo(tr.x0, tr.y0)
        ctx.lineTo(tr.x0 + (tr.x1 - tr.x0) * p1, tr.y0)
        if (p2 > 0) ctx.lineTo(tr.x1, tr.y1 + (tr.y2 - tr.y1) * p2)
        ctx.stroke()
        const hx = p2 > 0 ? tr.x1 : tr.x0 + (tr.x1 - tr.x0) * p1
        const hy = p2 > 0 ? tr.y1 + (tr.y2 - tr.y1) * p2 : tr.y0
        ctx.globalCompositeOperation = 'lighter'
        glow(ctx, hx, hy, 6, rgba(accent, 0.7))
        ctx.globalCompositeOperation = 'source-over'
      }
      const LN = 14, lnH = Math.min(11, (H * 0.36) / LN), gx0 = W * 0.06, gy0 = H * 0.6
      const written = Math.min(1, Math.max(0, prog)) * LN
      for (let l = 0; l < LN; l++) {
        const frac = Math.max(0, Math.min(1, written - l))
        if (frac <= 0) break
        const lw = W * 0.21 * (0.4 + 0.6 * Math.abs(Math.sin(l * 12.9898 + 4.1)))
        const ind = l % 4 === 1 || l % 4 === 2 ? 13 : 0
        ctx.fillStyle = rgba(accent, frac >= 1 ? 0.28 : 0.6)
        ctx.beginPath()
        ctx.roundRect(gx0 + ind, gy0 + l * lnH, Math.max(2.5, lw * frac), 5, 2.5)
        ctx.fill()
        if (frac < 1) {
          ctx.globalCompositeOperation = 'lighter'
          const carA = 0.55 + 0.45 * Math.sin(now * 0.012)
          glow(ctx, gx0 + ind + lw * frac, gy0 + l * lnH + 2.5, 7, rgba(accent, 0.8 * carA))
          ctx.globalCompositeOperation = 'source-over'
        }
      }
      const NP = 7, nx0 = W * 0.09, nx1 = W * 0.91, ny = H * 0.42
      const pi = Math.min(NP - 1, Math.floor(prog * NP)), ip = (prog * NP) % 1
      ctx.lineWidth = 2
      for (let n = 0; n < NP; n++) {
        const x = nx0 + ((nx1 - nx0) * n) / (NP - 1)
        const xn = nx0 + ((nx1 - nx0) * Math.min(NP - 1, n + 1)) / (NP - 1)
        const done = n < pi, cur = n === pi
        if (n < NP - 1) {
          const sf = done ? 1 : cur ? ip : 0
          ctx.strokeStyle = 'rgba(255,255,255,.1)'
          ctx.beginPath()
          ctx.moveTo(x + 11, ny)
          ctx.lineTo(xn - 11, ny)
          ctx.stroke()
          if (sf > 0) {
            ctx.strokeStyle = rgba(accent, 0.95)
            ctx.shadowColor = accent
            ctx.shadowBlur = 10
            ctx.beginPath()
            ctx.moveTo(x + 11, ny)
            ctx.lineTo(x + 11 + (xn - x - 22) * sf, ny)
            ctx.stroke()
            ctx.shadowBlur = 0
          }
        }
        const R = cur ? 9 + 2 * Math.sin(now * 0.008) : 7
        if (done || cur) {
          ctx.globalCompositeOperation = 'lighter'
          glow(ctx, x, ny, R * 2.9, rgba(accent, cur ? 0.55 : 0.3))
          ctx.globalCompositeOperation = 'source-over'
        }
        ctx.beginPath()
        ctx.arc(x, ny, R, 0, 6.2832)
        ctx.fillStyle = done ? rgba(accent, 0.9) : 'rgba(14,26,38,.9)'
        ctx.fill()
        ctx.strokeStyle = done || cur ? accent : 'rgba(255,255,255,.18)'
        ctx.stroke()
        if (cur) {
          const oa = now * 0.005
          ctx.strokeStyle = 'rgba(230,250,255,.85)'
          ctx.beginPath()
          ctx.arc(x, ny, R + 6, oa, oa + 1.8)
          ctx.stroke()
          if (Math.random() < 0.3 && sparks.length < 46) {
            sparks.push({ x, y: ny, vx: (Math.random() - 0.5) * 2.6, vy: -1 - Math.random() * 2, life: 1 })
          }
        }
      }
      ctx.globalCompositeOperation = 'lighter'
      for (let s = sparks.length - 1; s >= 0; s--) {
        const sp = sparks[s]
        sp.x += sp.vx; sp.y += sp.vy; sp.vy += 0.07; sp.life -= 0.022
        if (sp.life <= 0) { sparks.splice(s, 1); continue }
        ctx.fillStyle = rgba(accent, sp.life * 0.9)
        ctx.fillRect(sp.x, sp.y, 2, 2)
      }
      const spd = (now * 0.00025) % 1
      glow(ctx, nx0 + (nx1 - nx0) * spd, ny, 11, rgba(accent, 0.85))
      ctx.globalCompositeOperation = 'source-over'
    }
  },
}

const video: FxScene = {
  phases: ['Scénario', 'Keyframes FLUX', 'Segments I2V', 'Lipsync', 'Assemblage', 'Encodage'],
  says: ['Silence plateau…', 'Action !', 'Je cale chaque lèvre…', 'Le montage prend forme…'],
  create: () => {
    const motes: { u: number; v: number; s: number; ph: number }[] = []
    for (let i = 0; i < 110; i++) motes.push({ u: Math.random(), v: Math.random(), s: 0.3 + Math.random() * 0.9, ph: Math.random() * 6.28 })
    return (ctx, W, H, now, prog, accent) => {
      const lx = W * 0.12, ly = H * 0.3
      ctx.fillStyle = 'rgba(255,255,255,.07)'
      ctx.strokeStyle = 'rgba(255,255,255,.18)'
      ctx.lineWidth = 1
      ctx.beginPath(); ctx.arc(lx - 15, ly - 14, 12, 0, 6.2832); ctx.fill(); ctx.stroke()
      ctx.beginPath(); ctx.arc(lx - 28, ly + 8, 12, 0, 6.2832); ctx.fill(); ctx.stroke()
      const spin = now * 0.004
      for (let b = 0; b < 3; b++) {
        ctx.strokeStyle = rgba(accent, 0.55)
        ctx.beginPath(); ctx.arc(lx - 15, ly - 14, 7.5, spin + b * 2.09, spin + b * 2.09 + 0.9); ctx.stroke()
        ctx.beginPath(); ctx.arc(lx - 28, ly + 8, 7.5, -spin + b * 2.09, -spin + b * 2.09 + 0.9); ctx.stroke()
      }
      ctx.fillStyle = 'rgba(20,26,40,.95)'
      ctx.strokeStyle = 'rgba(255,255,255,.25)'
      ctx.beginPath(); ctx.roundRect(lx - 11, ly - 8, 24, 17, 4); ctx.fill(); ctx.stroke()
      const fl = 0.8 + 0.2 * Math.sin(now * 0.05) * Math.sin(now * 0.013)
      const scx = W * 0.72, scw = W * 0.34, sch = scw * 0.5625, scy = ly - sch / 2 + 8
      ctx.globalCompositeOperation = 'lighter'
      const bm = ctx.createLinearGradient(lx, ly, scx, ly)
      bm.addColorStop(0, `rgba(253,230,138,${0.38 * fl})`)
      bm.addColorStop(1, 'rgba(245,158,11,.03)')
      ctx.fillStyle = bm
      ctx.beginPath()
      ctx.moveTo(lx + 13, ly - 2)
      ctx.lineTo(scx - scw / 2, scy)
      ctx.lineTo(scx - scw / 2, scy + sch)
      ctx.lineTo(lx + 13, ly + 8)
      ctx.closePath()
      ctx.fill()
      for (const mo of motes) {
        mo.u += 0.0012 * mo.s
        if (mo.u > 1) mo.u = 0
        const mxp = lx + 13 + (scx - scw / 2 - lx - 13) * mo.u
        const half = 4 + (sch / 2) * mo.u
        const myp = ly + 3 + Math.sin(mo.ph + now * 0.001 * mo.s) * half * mo.v * 0.9
        ctx.fillStyle = `rgba(253,230,138,${0.5 * (1 - mo.u) * fl})`
        ctx.beginPath(); ctx.arc(mxp, myp, 0.9 + mo.s, 0, 6.2832); ctx.fill()
      }
      ctx.globalCompositeOperation = 'source-over'
      ctx.fillStyle = 'rgba(8,12,22,.92)'
      ctx.strokeStyle = 'rgba(255,255,255,.28)'
      ctx.lineWidth = 1.5
      ctx.beginPath(); ctx.roundRect(scx - scw / 2, scy, scw, sch, 8); ctx.fill(); ctx.stroke()
      ctx.save()
      ctx.beginPath(); ctx.roundRect(scx - scw / 2 + 3, scy + 3, scw - 6, sch - 6, 6); ctx.clip()
      const revealH = (sch - 6) * Math.min(1, Math.max(0, prog))
      ctx.save()
      ctx.beginPath(); ctx.rect(scx - scw / 2 + 3, scy + 3, scw - 6, revealH); ctx.clip()
      for (let band = 0; band < 5; band++) {
        const by = scy + 4 + band * ((sch - 8) / 5)
        const hueShift = Math.sin(now * 0.001 + band * 1.7)
        ctx.fillStyle = rgba(accent, 0.1 + 0.1 * Math.abs(hueShift))
        ctx.fillRect(scx - scw / 2 + 3 + Math.sin(now * 0.002 + band) * 6, by, scw - 6, (sch - 8) / 5 - 2)
      }
      glow(ctx, scx + Math.sin(now * 0.0016) * scw * 0.2, scy + sch * 0.4, sch * 0.5, `rgba(253,230,138,${0.16 * fl})`, `rgba(253,230,138,${0.3 * fl})`)
      ctx.fillStyle = `rgba(255,255,255,${0.05 + 0.04 * Math.sin(now * 0.06)})`
      ctx.fillRect(scx - scw / 2, scy + ((now * 0.05) % sch), scw, 1.6)
      ctx.restore()
      if (revealH < sch - 6) {
        ctx.fillStyle = `rgba(253,230,138,${0.55 * fl})`
        ctx.fillRect(scx - scw / 2 + 3, scy + 2 + revealH, scw - 6, 2)
      }
      ctx.restore()
      const fy = H * 0.7, fh = 42, NF = 10
      ctx.fillStyle = 'rgba(10,15,30,.85)'
      ctx.fillRect(0, fy, W, fh)
      const fill = Math.min(1, Math.max(0, prog)) * NF
      for (let f = 0; f < NF; f++) {
        const fx = f * (W / NF), fw = W / NF - 8
        const frac = Math.max(0, Math.min(1, fill - f))
        const lit = frac >= 1
        ctx.fillStyle = 'rgba(255,255,255,.05)'
        ctx.strokeStyle = lit ? 'rgba(253,230,138,.8)' : 'rgba(255,255,255,.14)'
        ctx.lineWidth = 1
        ctx.beginPath(); ctx.roundRect(fx + 4, fy + 7, fw, fh - 14, 3); ctx.fill(); ctx.stroke()
        if (frac > 0) {
          ctx.save()
          ctx.beginPath(); ctx.roundRect(fx + 4, fy + 7, fw, fh - 14, 3); ctx.clip()
          ctx.fillStyle = rgba(accent, 0.32 + 0.18 * Math.sin(now * 0.006 + f))
          ctx.fillRect(fx + 4, fy + 7, fw * frac, fh - 14)
          ctx.restore()
        }
        if (lit) {
          ctx.fillStyle = 'rgba(253,230,138,.9)'
          ctx.font = '9px Consolas, monospace'
          ctx.fillText(`KF${f + 1}`, fx + 9, fy + fh / 2 + 3)
        }
        ctx.fillStyle = 'rgba(230,234,245,.25)'
        for (let h = 0; h < 4; h++) {
          ctx.fillRect(fx + 8 + h * (fw / 4), fy + 1.5, 5, 3)
          ctx.fillRect(fx + 8 + h * (fw / 4), fy + fh - 4.5, 5, 3)
        }
      }
      if (fill > 0 && fill < NF) {
        ctx.globalCompositeOperation = 'lighter'
        glow(ctx, (fill / NF) * W, fy + fh / 2, 13, 'rgba(253,230,138,.8)')
        ctx.globalCompositeOperation = 'source-over'
      }
    }
  },
}

const drawing: FxScene = {
  phases: ['Analyse du croquis', 'Vision', 'Composition', 'Rendu FLUX', 'Révélation'],
  says: ['Je lis ton geste…', 'L\'encre prend vie…', 'Dernier coup de pinceau…'],
  create: () => {
    type Stroke = { pts: [number, number][]; w: number; c?: string }
    let strokes: Stroke[] = []
    let sizedW = 0
    const splash: { x: number; y: number; vx: number; vy: number; life: number; r: number; c: string }[] = []
    const drips: { x: number; y: number; len: number; max: number; c: string }[] = []
    return (ctx, W, H, now, prog, accent) => {
      if (!strokes.length || sizedW !== W) {
        sizedW = W
        const cx = W * 0.5, cy = H * 0.44, R = Math.min(W, H) * 0.27
        const arc = (r: number, a0: number, a1: number): [number, number][] => {
          const p: [number, number][] = []
          for (let a = a0; a <= a1; a += 0.07) p.push([cx + Math.cos(a) * r + Math.sin(a * 3) * 2.5, cy + Math.sin(a) * r + Math.cos(a * 2.3) * 2.5])
          return p
        }
        strokes = [
          { pts: arc(R, -1.4, 3.6), w: 10 },
          { pts: arc(R * 0.985, 3.75, 4.55), w: 6 },
          { pts: [[cx - R * 1.55, cy + R * 0.78], [cx - R * 1.1, cy + R * 0.2], [cx - R * 0.62, cy - R * 0.52], [cx - R * 0.32, cy - R * 0.05], [cx - R * 0.1, cy + R * 0.38]], w: 7 },
          { pts: [[cx + R * 0.72, cy + R * 0.82], [cx + R * 0.9, cy + R * 0.42], [cx + R * 0.97, cy + R * 0.12], [cx + R * 0.86, cy - R * 0.14], [cx + R * 0.8, cy - R * 0.38]], w: 4, c: '#FDE047' },
          { pts: [[cx + R * 0.95, cy + R * 0.82], [cx + R * 1.2, cy + R * 0.36], [cx + R * 1.28, cy - R * 0.06]], w: 3, c: '#FDE047' },
        ]
      }
      const vg = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.2, W / 2, H / 2, Math.max(W, H) * 0.65)
      vg.addColorStop(0, 'rgba(236,252,203,.035)')
      vg.addColorStop(1, 'transparent')
      ctx.fillStyle = vg
      ctx.fillRect(0, 0, W, H)
      let total = 0
      for (const s of strokes) total += s.pts.length
      const target = Math.round(total * Math.min(1, Math.max(0, prog)))
      let count = 0
      let tip: [number, number] | null = null
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      for (const st of strokes) {
        const n = st.pts.length
        const upto = Math.max(0, Math.min(n, target - count))
        count += n
        if (upto < 2) continue
        const col = st.c ?? accent
        for (let p = 1; p < upto; p++) {
          const u = p / n
          ctx.strokeStyle = rgba(col, 0.5 + 0.32 * Math.sin(u * 3.14))
          ctx.lineWidth = st.w * (0.45 + 0.65 * Math.sin(u * 3.14))
          ctx.beginPath()
          ctx.moveTo(st.pts[p - 1][0], st.pts[p - 1][1])
          ctx.lineTo(st.pts[p][0], st.pts[p][1])
          ctx.stroke()
        }
        if (upto < n) { tip = st.pts[upto - 1]; break }
        tip = st.pts[n - 1]
      }
      if (tip) {
        if (Math.random() < 0.5 && splash.length < 70) {
          splash.push({ x: tip[0], y: tip[1], vx: (Math.random() - 0.5) * 2.6, vy: (Math.random() - 0.5) * 2.6 - 0.4, life: 1, r: 0.8 + Math.random() * 2.2, c: accent })
        }
        if (Math.random() < 0.012 && drips.length < 5) drips.push({ x: tip[0], y: tip[1], len: 0, max: 14 + Math.random() * 22, c: accent })
        ctx.globalCompositeOperation = 'lighter'
        glow(ctx, tip[0], tip[1], 30, rgba(accent, 0.5), 'rgba(246,255,230,.95)')
        ctx.strokeStyle = 'rgba(230,234,245,.6)'
        ctx.lineWidth = 2.6
        ctx.beginPath()
        ctx.moveTo(tip[0] + 7, tip[1] - 9)
        ctx.lineTo(tip[0] + 34, tip[1] - 46)
        ctx.stroke()
        ctx.strokeStyle = rgba(accent, 0.75)
        ctx.lineWidth = 5
        ctx.beginPath()
        ctx.moveTo(tip[0] + 2, tip[1] - 2)
        ctx.lineTo(tip[0] + 10, tip[1] - 12)
        ctx.stroke()
        ctx.globalCompositeOperation = 'source-over'
      }
      for (let d = drips.length - 1; d >= 0; d--) {
        const dr = drips[d]
        dr.len += 0.18
        if (dr.len > dr.max) { drips.splice(d, 1); continue }
        ctx.strokeStyle = rgba(dr.c, 0.5 * (1 - dr.len / dr.max))
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(dr.x, dr.y)
        ctx.lineTo(dr.x, dr.y + dr.len)
        ctx.stroke()
      }
      ctx.globalCompositeOperation = 'lighter'
      for (let s = splash.length - 1; s >= 0; s--) {
        const sp = splash[s]
        sp.x += sp.vx; sp.y += sp.vy; sp.vy += 0.04; sp.life -= 0.024
        if (sp.life <= 0) { splash.splice(s, 1); continue }
        ctx.fillStyle = rgba(sp.c, sp.life * 0.8)
        ctx.beginPath(); ctx.arc(sp.x, sp.y, sp.r * sp.life, 0, 6.2832); ctx.fill()
      }
      ctx.globalCompositeOperation = 'source-over'
    }
  },
}

function buildIco() {
  const PHI = (1 + Math.sqrt(5)) / 2
  let V: number[][] = [[-1, PHI, 0], [1, PHI, 0], [-1, -PHI, 0], [1, -PHI, 0], [0, -1, PHI], [0, 1, PHI], [0, -1, -PHI], [0, 1, -PHI], [PHI, 0, -1], [PHI, 0, 1], [-PHI, 0, -1], [-PHI, 0, 1]]
  const F0 = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]]
  const norm = (v: number[]) => { const l = Math.hypot(v[0], v[1], v[2]); return [v[0] / l, v[1] / l, v[2] / l] }
  V = V.map(norm)
  const mid: Record<string, number> = {}
  const V2 = V.slice()
  const F: number[][] = []
  const m = (a: number, b: number) => {
    const k = a < b ? `${a}_${b}` : `${b}_${a}`
    if (mid[k] !== undefined) return mid[k]
    V2.push(norm([(V2[a][0] + V2[b][0]) / 2, (V2[a][1] + V2[b][1]) / 2, (V2[a][2] + V2[b][2]) / 2]))
    mid[k] = V2.length - 1
    return mid[k]
  }
  for (const f of F0) {
    const a = m(f[0], f[1]), b = m(f[1], f[2]), c = m(f[2], f[0])
    F.push([f[0], a, c], [f[1], b, a], [f[2], c, b], [a, b, c])
  }
  const es: Record<string, boolean> = {}
  const E: number[][] = []
  for (const f of F) {
    for (const e of [[f[0], f[1]], [f[1], f[2]], [f[2], f[0]]]) {
      const k = `${Math.min(e[0], e[1])}_${Math.max(e[0], e[1])}`
      if (!es[k]) { es[k] = true; E.push(e) }
    }
  }
  return { V: V2, F, E }
}

const threeD: FxScene = {
  phases: ['Analyse', 'Référence photo', 'Sculpture 3D', 'Matériaux & zones', 'Animation', 'Finalisation'],
  says: ['Je choisis la meilleure photo…', 'Je sculpte en géométrie native…', 'Je pose les matières par zones…', 'Modèle prêt.'],
  create: () => {
    const GEO = buildIco()
    let lastVerts = 0
    const vsparks: { x: number; y: number; life: number }[] = []
    return (ctx, W, H, now, prog, accent) => {
      const cx = W / 2, cy = H * 0.42, R = Math.min(W, H) * 0.27
      ctx.strokeStyle = rgba(accent, 0.1)
      ctx.lineWidth = 1
      for (let i = 0; i <= 9; i++) {
        const u = i / 9
        ctx.beginPath()
        ctx.moveTo(cx - W * 0.36 * (1 - u * 0.5), H * 0.72 + u * H * 0.2)
        ctx.lineTo(cx + W * 0.36 * (1 - u * 0.5), H * 0.72 + u * H * 0.2)
        ctx.stroke()
      }
      for (let i = -4; i <= 4; i++) {
        ctx.beginPath()
        ctx.moveTo(cx + i * W * 0.08, H * 0.72)
        ctx.lineTo(cx + i * W * 0.17, H * 0.92)
        ctx.stroke()
      }
      const ay = now * 0.0006, ax = 0.45 + 0.18 * Math.sin(now * 0.0003)
      const cY = Math.cos(ay), sY = Math.sin(ay), cX = Math.cos(ax), sX = Math.sin(ax)
      const P: number[][] = []
      for (let i = 0; i < GEO.V.length; i++) {
        const v = GEO.V[i]
        const pu = 1 + 0.03 * Math.sin(now * 0.002 + i)
        const x = v[0] * pu, y = v[1] * pu, z = v[2] * pu
        const x1 = x * cY + z * sY, z1 = -x * sY + z * cY
        const y1 = y * cX - z1 * sX, z2 = y * sX + z1 * cX
        const pp = 2.6 / (2.6 + z2)
        P.push([cx + x1 * R * pp, cy + y1 * R * pp, z2, pp])
      }
      const vProg = Math.min(1, Math.max(0, prog) * 2)
      const eProg = Math.max(0, Math.min(1, (prog - 0.25) / 0.5))
      const fProg = Math.max(0, Math.min(1, (prog - 0.55) / 0.45))
      const vertsOn = Math.floor(GEO.V.length * vProg)
      if (vertsOn > lastVerts && lastVerts > 0) {
        const p = P[vertsOn - 1]
        vsparks.push({ x: p[0], y: p[1], life: 1 })
      }
      lastVerts = vertsOn
      const order: number[] = []
      for (let f = 0; f < Math.floor(GEO.F.length * fProg); f++) order.push(f)
      order.sort((a, b) => (P[GEO.F[b][0]][2] + P[GEO.F[b][1]][2] + P[GEO.F[b][2]][2]) - (P[GEO.F[a][0]][2] + P[GEO.F[a][1]][2] + P[GEO.F[a][2]][2]))
      for (const o of order) {
        const fc = GEO.F[o]
        const za = (P[fc[0]][2] + P[fc[1]][2] + P[fc[2]][2]) / 3
        ctx.fillStyle = rgba(accent, Math.max(0.06, (0.5 - za * 0.35) * (0.34 + 0.42 * fProg)))
        ctx.beginPath()
        ctx.moveTo(P[fc[0]][0], P[fc[0]][1])
        ctx.lineTo(P[fc[1]][0], P[fc[1]][1])
        ctx.lineTo(P[fc[2]][0], P[fc[2]][1])
        ctx.closePath()
        ctx.fill()
      }
      ctx.lineWidth = 1
      for (let e = 0; e < Math.floor(GEO.E.length * eProg); e++) {
        const ed = GEO.E[e]
        const A = P[ed[0]], B = P[ed[1]]
        const dep = 1 - ((A[2] + B[2]) / 2 + 1) / 2
        ctx.strokeStyle = rgba(accent, 0.1 + 0.42 * dep)
        ctx.beginPath()
        ctx.moveTo(A[0], A[1])
        ctx.lineTo(B[0], B[1])
        ctx.stroke()
      }
      ctx.globalCompositeOperation = 'lighter'
      for (let s = 0; s < vertsOn; s++) {
        const p = P[s]
        glow(ctx, p[0], p[1], (1.5 * p[3]) * 3.2, rgba(accent, 0.42))
      }
      for (let i = vsparks.length - 1; i >= 0; i--) {
        const vs = vsparks[i]
        vs.life -= 0.03
        if (vs.life <= 0) { vsparks.splice(i, 1); continue }
        ctx.strokeStyle = rgba(accent, vs.life * 0.8)
        ctx.lineWidth = 1.4
        ctx.beginPath()
        ctx.arc(vs.x, vs.y, (1 - vs.life) * 20 + 3, 0, 6.2832)
        ctx.stroke()
      }
      if (prog > 0.5) {
        const sy = cy - R + ((now * 0.06) % (R * 2))
        const sg = ctx.createLinearGradient(0, sy - 8, 0, sy + 8)
        sg.addColorStop(0, 'transparent')
        sg.addColorStop(0.5, 'rgba(219,234,254,.32)')
        sg.addColorStop(1, 'transparent')
        ctx.fillStyle = sg
        ctx.fillRect(cx - R * 1.25, sy - 8, R * 2.5, 16)
      }
      if (prog > 0.96) {
        const done2 = Math.min(1, (prog - 0.96) / 0.04)
        glow(ctx, cx, cy, R * (1.5 + 0.6 * done2), rgba(accent, 0.45 * done2 * (0.7 + 0.3 * Math.sin(now * 0.014))), `rgba(255,255,255,${0.5 * done2})`)
      }
      ctx.globalCompositeOperation = 'source-over'
    }
  },
}

const learning: FxScene = {
  phases: ['Synthèse', 'Fiches', 'Cartes', 'Exercices', 'Examen'],
  says: ['Je lis tout le chapitre…', 'Je distille l\'essentiel…', 'Tes fiches se remplissent…', '+XP en approche.'],
  create: () => {
    const SY = ['∑', 'π', '√', '∆', '∫', 'θ', '∞', 'ƒ', '≈', 'α', 'β', 'λ']
    const orb: { sym: string; a: number; rx: number; ry: number; s: number; size: number; ph: number }[] = []
    for (let i = 0; i < 16; i++) {
      orb.push({ sym: SY[i % SY.length], a: Math.random() * 6.28, rx: 72 + Math.random() * 95, ry: 26 + Math.random() * 36, s: (0.0004 + Math.random() * 0.0007) * (Math.random() < 0.5 ? -1 : 1), size: 12 + Math.random() * 12, ph: Math.random() * 6.28 })
    }
    const orbs: { x: number; y: number; p: number; s: number }[] = []
    const flips: { x: number; y: number; vx: number; vy: number; rot: number; vr: number; life: number }[] = []
    return (ctx, W, H, now, prog, accent) => {
      const cx = W / 2, cy = H * 0.44, bw = 82, bh = 54
      const flap = Math.sin(now * 0.0035)
      glow(ctx, cx, cy, 160, rgba(accent, 0.16), rgba(accent, 0.22))
      ctx.strokeStyle = 'rgba(255,255,255,.35)'
      ctx.lineWidth = 1.4
      ctx.fillStyle = 'rgba(236,253,245,.09)'
      ctx.beginPath()
      ctx.moveTo(cx, cy - bh * 0.32)
      ctx.quadraticCurveTo(cx - bw * 0.55, cy - bh * 0.72, cx - bw, cy - bh * 0.3)
      ctx.lineTo(cx - bw, cy + bh * 0.55)
      ctx.quadraticCurveTo(cx - bw * 0.5, cy + bh * 0.9, cx, cy + bh * 0.62)
      ctx.closePath(); ctx.fill(); ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(cx, cy - bh * 0.32)
      ctx.quadraticCurveTo(cx + bw * 0.55, cy - bh * 0.72, cx + bw, cy - bh * 0.3)
      ctx.lineTo(cx + bw, cy + bh * 0.55)
      ctx.quadraticCurveTo(cx + bw * 0.5, cy + bh * 0.9, cx, cy + bh * 0.62)
      ctx.closePath(); ctx.fill(); ctx.stroke()
      const fx = cx + flap * bw * 0.92
      ctx.strokeStyle = rgba(accent, 0.85)
      ctx.fillStyle = rgba(accent, 0.13)
      ctx.beginPath()
      ctx.moveTo(cx, cy - bh * 0.32)
      ctx.quadraticCurveTo((cx + fx) / 2, cy - bh * (0.9 + 0.25 * Math.abs(flap)), fx, cy - bh * 0.28)
      ctx.lineTo(fx, cy + bh * 0.5)
      ctx.quadraticCurveTo((cx + fx) / 2, cy + bh * 0.8, cx, cy + bh * 0.62)
      ctx.closePath(); ctx.fill(); ctx.stroke()
      if (Math.abs(flap) > 0.97 && flips.length < 12) {
        for (let i = 0; i < 3; i++) flips.push({ x: fx, y: cy - bh * 0.2, vx: (Math.random() - 0.5) * 1.6, vy: -0.6 - Math.random() * 1.2, rot: Math.random() * 6.28, vr: (Math.random() - 0.5) * 0.2, life: 1 })
      }
      for (let i = flips.length - 1; i >= 0; i--) {
        const fl = flips[i]
        fl.x += fl.vx; fl.y += fl.vy; fl.rot += fl.vr; fl.life -= 0.014
        if (fl.life <= 0) { flips.splice(i, 1); continue }
        ctx.save()
        ctx.translate(fl.x, fl.y)
        ctx.rotate(fl.rot)
        ctx.fillStyle = `rgba(236,253,245,${fl.life * 0.5})`
        ctx.fillRect(-4, -2.6, 8, 5.2)
        ctx.restore()
      }
      ctx.strokeStyle = 'rgba(230,234,245,.22)'
      ctx.lineWidth = 1
      for (let l = 0; l < 4; l++) {
        const lyy = cy - bh * 0.08 + l * 10
        ctx.beginPath(); ctx.moveTo(cx - bw * 0.8, lyy); ctx.lineTo(cx - bw * 0.2, lyy + 3); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(cx + bw * 0.2, lyy + 3); ctx.lineTo(cx + bw * 0.8, lyy); ctx.stroke()
      }
      const PAGES = 12
      const pgW = Math.min(52, W * 0.12), pgH = 7
      const pxc = W * 0.13, pyb = H * 0.8
      const donePg = Math.floor(Math.min(1, Math.max(0, prog)) * PAGES)
      const fracPg = Math.min(1, Math.max(0, prog)) * PAGES - donePg
      for (let pg = 0; pg < donePg; pg++) {
        const wob = Math.sin(pg * 2.4) * 3
        ctx.fillStyle = `rgba(236,253,245,${0.3 + 0.028 * pg})`
        ctx.strokeStyle = rgba(accent, 0.55)
        ctx.lineWidth = 1
        ctx.beginPath(); ctx.roundRect(pxc - pgW / 2 + wob, pyb - pg * (pgH + 1.6), pgW, pgH, 2); ctx.fill(); ctx.stroke()
      }
      if (donePg < PAGES && fracPg > 0) {
        const syT = pyb - donePg * (pgH + 1.6)
        const sx2 = cx + (pxc - cx) * fracPg
        const sy2 = cy + (syT - cy) * fracPg
        ctx.fillStyle = `rgba(236,253,245,${0.25 + 0.45 * fracPg})`
        ctx.strokeStyle = rgba(accent, 0.4)
        ctx.lineWidth = 1
        ctx.beginPath(); ctx.roundRect(sx2 - pgW / 2, sy2, pgW, pgH, 2); ctx.fill(); ctx.stroke()
      }
      if (donePg > 0) {
        ctx.globalCompositeOperation = 'lighter'
        glow(ctx, pxc, pyb - (donePg - 1) * (pgH + 1.6) + 3, 16, rgba(accent, 0.3))
        ctx.globalCompositeOperation = 'source-over'
      }
      ctx.textAlign = 'center'
      const pos: [number, number][] = []
      for (const ob of orb) {
        ob.a += ob.s * 16
        const ox = cx + Math.cos(ob.a) * ob.rx
        const oy = cy - 28 + Math.sin(ob.a) * ob.ry
        pos.push([ox, oy])
        const front = Math.sin(ob.a) > 0 ? 1 : 0.45
        const tw = 0.6 + 0.4 * Math.sin(now * 0.002 + ob.ph)
        ctx.font = `${ob.size * (front === 1 ? 1 : 0.82)}px Georgia, serif`
        ctx.shadowColor = accent
        ctx.shadowBlur = 12 * tw * front
        ctx.fillStyle = `rgba(209,250,229,${0.85 * front * tw})`
        ctx.fillText(ob.sym, ox, oy)
        ctx.shadowBlur = 0
        if (Math.random() < 0.0015 + 0.012 * Math.min(1, Math.max(0, prog)) && orbs.length < 3 + Math.floor(Math.min(1, Math.max(0, prog)) * 9)) orbs.push({ x: ox, y: oy, p: 0, s: 0.014 + Math.random() * 0.012 })
      }
      ctx.strokeStyle = rgba(accent, 0.12 + 0.08 * Math.sin(now * 0.001))
      ctx.lineWidth = 1
      for (let i = 0; i < pos.length - 1; i += 3) {
        ctx.beginPath()
        ctx.moveTo(pos[i][0], pos[i][1])
        ctx.lineTo(pos[i + 1][0], pos[i + 1][1])
        ctx.stroke()
      }
      ctx.globalCompositeOperation = 'lighter'
      const tx = W - 90, ty = H - 70
      for (let b = orbs.length - 1; b >= 0; b--) {
        const ob = orbs[b]
        ob.p += ob.s
        if (ob.p >= 1) { orbs.splice(b, 1); continue }
        const u = ob.p, v = 1 - u
        const mx = (ob.x + tx) / 2 + 40 * Math.sin(u * 3.14)
        const x = v * v * ob.x + 2 * v * u * mx + u * u * tx
        const y = v * v * ob.y + 2 * v * u * (ob.y - 30) + u * u * ty
        glow(ctx, x, y, 9, 'rgba(253,224,71,.6)', 'rgba(254,249,195,.95)')
      }
      ctx.globalCompositeOperation = 'source-over'
    }
  },
}

const cyber: FxScene = {
  phases: ['Forge du lab', 'Déploiement', 'Scan', 'Analyse', 'Validation'],
  says: ['Périmètre sécurisé…', 'Je scanne chaque port…', 'Défi calibré pour toi.'],
  create: () => {
    const HX = '0123456789ABCDEF'
    const row = () => Array.from({ length: 5 }, () => HX[Math.floor(Math.random() * 16)] + HX[Math.floor(Math.random() * 16)]).join(' ')
    const rows: { y: number; txt: string; hot: boolean }[] = []
    for (let r = 0; r < 16; r++) rows.push({ y: r * 15, txt: row(), hot: Math.random() < 0.18 })
    const blips: { a: number; r: number; life: number }[] = []
    const ports: { p: number; open: boolean }[] = []
    for (let i = 0; i < 9; i++) ports.push({ p: 20 + Math.floor(Math.random() * 8000), open: Math.random() < 0.35 })
    let glitchT = 0
    return (ctx, W, H, now, prog, accent) => {
      ctx.font = '10px Consolas, monospace'
      for (const rw of rows) {
        rw.y += 0.5
        if (rw.y > H * 0.86) { rw.y = -12; rw.txt = row(); rw.hot = Math.random() < 0.18 }
        if (Math.random() < 0.02) rw.txt = row()
        ctx.fillStyle = rw.hot ? 'rgba(253,164,175,.6)' : rgba(accent, 0.28)
        ctx.fillText(rw.txt, 16, rw.y)
      }
      ctx.textAlign = 'right'
      for (let i = 0; i < ports.length; i++) {
        const pr = ports[i]
        const scanned = i < Math.floor(ports.length * Math.min(1, Math.max(0, prog)))
        ctx.fillStyle = scanned ? (pr.open ? 'rgba(74,222,128,.75)' : rgba(accent, 0.55)) : 'rgba(255,255,255,.18)'
        ctx.fillText(`:${pr.p} ${scanned ? (pr.open ? 'OPEN' : 'closed') : '···'}`, W - 16, 22 + i * 15)
      }
      ctx.textAlign = 'left'
      const cx = W * 0.5, cy = H * 0.42, R = Math.min(W, H) * 0.27
      ctx.strokeStyle = rgba(accent, 0.25)
      ctx.lineWidth = 1
      for (let c = 1; c <= 3; c++) { ctx.beginPath(); ctx.arc(cx, cy, (R * c) / 3, 0, 6.2832); ctx.stroke() }
      ctx.beginPath(); ctx.moveTo(cx - R, cy); ctx.lineTo(cx + R, cy); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy + R); ctx.stroke()
      const sweep = now * 0.0016
      for (let w = 0; w < 30; w++) {
        ctx.strokeStyle = rgba(accent, 0.5 * (1 - w / 30))
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.lineTo(cx + Math.cos(sweep - w * 0.02) * R, cy + Math.sin(sweep - w * 0.02) * R)
        ctx.stroke()
      }
      if (Math.random() < 0.03 && blips.length < 8) blips.push({ a: sweep % 6.2832, r: R * (0.25 + Math.random() * 0.7), life: 1 })
      ctx.globalCompositeOperation = 'lighter'
      for (let b = blips.length - 1; b >= 0; b--) {
        const bl = blips[b]
        bl.life -= 0.007
        if (bl.life <= 0) { blips.splice(b, 1); continue }
        const bx = cx + Math.cos(bl.a) * bl.r, by = cy + Math.sin(bl.a) * bl.r
        glow(ctx, bx, by, 10, rgba(accent, bl.life * 0.8), `rgba(255,228,230,${bl.life})`)
        ctx.strokeStyle = rgba(accent, bl.life * 0.5)
        ctx.beginPath(); ctx.arc(bx, by, (1 - bl.life) * 24 + 4, 0, 6.2832); ctx.stroke()
      }
      ctx.globalCompositeOperation = 'source-over'
      const lx = W * 0.85, ly = H * 0.38, SEG = 8
      const unl = Math.floor(SEG * Math.min(1, Math.max(0, prog)))
      ctx.strokeStyle = unl >= SEG ? 'rgba(74,222,128,.9)' : 'rgba(255,255,255,.4)'
      ctx.lineWidth = 4
      ctx.beginPath(); ctx.arc(lx, ly - 16 + (unl >= SEG ? -6 : 0), 14, 3.14, 0); ctx.stroke()
      ctx.fillStyle = 'rgba(20,26,40,.9)'
      ctx.strokeStyle = 'rgba(255,255,255,.25)'
      ctx.lineWidth = 1.4
      ctx.beginPath(); ctx.roundRect(lx - 20, ly - 14, 40, 44, 6); ctx.fill(); ctx.stroke()
      for (let s = 0; s < SEG; s++) {
        const on = s < unl
        ctx.fillStyle = on ? 'rgba(74,222,128,.85)' : rgba(accent, 0.5)
        if (on) { ctx.shadowColor = '#4ADE80'; ctx.shadowBlur = 6 }
        ctx.fillRect(lx - 13, ly - 9 + s * 4.6, 26, 2.6)
        ctx.shadowBlur = 0
      }
      const segF = SEG * Math.min(1, Math.max(0, prog)) - unl
      if (unl < SEG && segF > 0) {
        ctx.fillStyle = 'rgba(74,222,128,.5)'
        ctx.fillRect(lx - 13, ly - 9 + unl * 4.6, 26 * segF, 2.6)
      }
      if (unl >= SEG) {
        ctx.globalCompositeOperation = 'lighter'
        glow(ctx, lx, ly + 8, 44, 'rgba(74,222,128,.45)', 'rgba(220,255,235,.85)')
        ctx.globalCompositeOperation = 'source-over'
      }
      if (now > glitchT) {
        glitchT = now + 1400 + Math.random() * 2600
      }
      if (now < glitchT - 1300) {
        for (let g = 0; g < 3; g++) {
          const gy = Math.random() * H
          ctx.fillStyle = rgba(accent, 0.1 + Math.random() * 0.12)
          ctx.fillRect(Math.random() * 14 - 7, gy, W, 2 + Math.random() * 3)
        }
      }
      ctx.fillStyle = 'rgba(0,0,0,.13)'
      for (let y = 0; y < H; y += 4) ctx.fillRect(0, y, W, 1.4)
    }
  },
}

const voice: FxScene = {
  phases: ['Écoute', 'Transcription', 'Réflexion', 'Synthèse vocale', 'Lipsync'],
  says: ['Je t\'écoute…', 'Chaque mot compte…', 'Ma voix se forme…'],
  create: () => {
    const BARS = 110
    const hist: number[] = []
    const amp = (i: number, t: number) => {
      const f = i / BARS
      return Math.abs(Math.sin(t * 0.0021 + f * 9) * 0.5 + Math.sin(t * 0.0037 + f * 23 + 1.7) * 0.3 + Math.sin(t * 0.0013 + f * 5 - 0.6) * 0.35 + Math.sin(t * 0.006 + f * 40) * 0.12) * (1 - f * 0.32)
    }
    return (ctx, W, H, now, prog, accent) => {
      const cx = W / 2, cy = H * 0.42, R0 = Math.min(W, H) * 0.15
      for (let ring = 0; ring < 3; ring++) {
        ctx.strokeStyle = rgba(accent, 0.15 - ring * 0.04)
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.arc(cx, cy, R0 * 1.9 + ring * 17 + 7 * Math.sin(now * 0.0016 + ring * 1.2), 0, 6.2832)
        ctx.stroke()
      }
      ctx.globalCompositeOperation = 'lighter'
      for (let i = 0; i < BARS; i++) {
        const a = (i / BARS) * 6.2832 - 1.5708
        const m = amp(i, now)
        const len = R0 * 0.24 + m * R0 * 1.3
        const x1 = cx + Math.cos(a) * (R0 + len), y1 = cy + Math.sin(a) * (R0 + len)
        const x2 = cx + Math.cos(a) * (R0 - len * 0.3), y2 = cy + Math.sin(a) * (R0 - len * 0.3)
        const lg = ctx.createLinearGradient(x2, y2, x1, y1)
        lg.addColorStop(0, rgba(accent, 0.85))
        lg.addColorStop(1, rgba(accent, 0.05))
        ctx.strokeStyle = lg
        ctx.lineWidth = 2.3
        ctx.beginPath(); ctx.moveTo(x2, y2); ctx.lineTo(x1, y1); ctx.stroke()
        if (m > 0.6) glow(ctx, x1, y1, 5, rgba(accent, 0.7))
      }
      const lv = amp(4, now) * 0.6 + amp(12, now) * 0.4
      ctx.beginPath()
      for (let b = 0; b <= 42; b++) {
        const ab = (b / 42) * 6.2832
        const rb = R0 * (0.6 + 0.2 * lv) * (1 + 0.09 * Math.sin(ab * 3 + now * 0.002) + 0.06 * Math.sin(ab * 5 - now * 0.0016))
        const xb = cx + Math.cos(ab) * rb, yb = cy + Math.sin(ab) * rb
        if (b === 0) ctx.moveTo(xb, yb)
        else ctx.lineTo(xb, yb)
      }
      ctx.closePath()
      const core = ctx.createRadialGradient(cx - R0 * 0.15, cy - R0 * 0.2, 0, cx, cy, R0)
      core.addColorStop(0, `rgba(235,255,250,${0.8 + 0.2 * lv})`)
      core.addColorStop(0.5, rgba(accent, 0.5))
      core.addColorStop(1, rgba(accent, 0.06))
      ctx.fillStyle = core
      ctx.fill()
      const ringR = R0 * 2.12
      const pa = -1.5708 + 6.2832 * Math.min(1, Math.max(0, prog))
      ctx.strokeStyle = 'rgba(255,255,255,.1)'
      ctx.lineWidth = 3.4
      ctx.beginPath(); ctx.arc(cx, cy, ringR, 0, 6.2832); ctx.stroke()
      ctx.strokeStyle = rgba(accent, 0.85)
      ctx.shadowColor = accent
      ctx.shadowBlur = 12
      ctx.beginPath(); ctx.arc(cx, cy, ringR, -1.5708, pa); ctx.stroke()
      ctx.shadowBlur = 0
      glow(ctx, cx + Math.cos(pa) * ringR, cy + Math.sin(pa) * ringR, 9, rgba(accent, 0.9))
      hist.push(lv)
      if (hist.length > 130) hist.shift()
      const hy = H * 0.85
      ctx.beginPath()
      for (let i = 0; i < hist.length; i++) {
        const x = W * 0.08 + (i / 130) * W * 0.84
        const y = hy - hist[i] * 26
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.strokeStyle = rgba(accent, 0.55)
      ctx.lineWidth = 1.6
      ctx.stroke()
      ctx.beginPath()
      for (let i = 0; i < hist.length; i++) {
        const x = W * 0.08 + (i / 130) * W * 0.84
        const y = hy + hist[i] * 26
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.strokeStyle = rgba(accent, 0.25)
      ctx.stroke()
      ctx.globalCompositeOperation = 'source-over'
    }
  },
}

const cowork: FxScene = {
  phases: ['Plan', 'Navigation', 'Extraction', 'Synthèse', 'Audit'],
  says: ['Je repère les bonnes pages…', 'J\'extrais l\'essentiel…', 'Ta synthèse arrive…'],
  create: () => {
    type Win = { x: number; y: number; w: number; h: number; tag: string; hue: string }
    let wins: Win[] = []
    let sizedW = 0
    const cur = { x: 60, y: 60, tx: 60, ty: 60 }
    let target = 0, lastHop = 0, clickT = -1
    const frags: { x: number; y: number; tx: number; ty: number; p: number; s: number; hue: string }[] = []
    const rip: { x: number; y: number; r: number; life: number }[] = []
    const trail: { x: number; y: number; life: number }[] = []
    return (ctx, W, H, now, prog, accent) => {
      if (!wins.length || sizedW !== W) {
        sizedW = W
        const ww = Math.min(160, W * 0.25), wh = 88
        wins = [
          { x: W * 0.07, y: H * 0.1, w: ww, h: wh, tag: 'linkedin…', hue: '#38BDF8' },
          { x: W * 0.36, y: H * 0.32, w: ww, h: wh, tag: 'github…', hue: '#A78BFA' },
          { x: W * 0.07, y: H * 0.54, w: ww, h: wh, tag: 'gmail…', hue: '#F472B6' },
        ]
      }
      if (now - lastHop > 2100) {
        lastHop = now
        target = (target + 1) % wins.length
        const wt = wins[target]
        cur.tx = wt.x + 20 + Math.random() * (wt.w - 40)
        cur.ty = wt.y + 26 + Math.random() * (wt.h - 36)
        clickT = now + 850
      }
      cur.x += (cur.tx - cur.x) * 0.07
      cur.y += (cur.ty - cur.y) * 0.07
      if (Math.random() < 0.5) trail.push({ x: cur.x, y: cur.y, life: 1 })
      const bx = W * 0.78, by = H * 0.32
      if (clickT > 0 && now > clickT) {
        clickT = -1
        rip.push({ x: cur.x, y: cur.y, r: 2, life: 1 })
        frags.push({ x: cur.x, y: cur.y, tx: bx, ty: by, p: 0, s: 0.016, hue: wins[target].hue })
      }
      const checks = Math.floor(Math.min(1, Math.max(0, prog)) * wins.length)
      for (let w = 0; w < wins.length; w++) {
        const win = wins[w]
        const act = w === target
        const lift = act ? 3 * Math.sin(now * 0.004) : 0
        ctx.fillStyle = act ? 'rgba(26,32,54,.96)' : 'rgba(18,23,40,.9)'
        ctx.strokeStyle = act ? win.hue : 'rgba(255,255,255,.14)'
        ctx.lineWidth = act ? 1.6 : 1
        if (act) { ctx.shadowColor = win.hue; ctx.shadowBlur = 16 }
        ctx.beginPath(); ctx.roundRect(win.x, win.y - lift, win.w, win.h, 8); ctx.fill(); ctx.stroke()
        ctx.shadowBlur = 0
        ctx.fillStyle = 'rgba(255,255,255,.07)'
        ctx.beginPath(); ctx.roundRect(win.x, win.y - lift, win.w, 15, [8, 8, 0, 0]); ctx.fill()
        ctx.fillStyle = 'rgba(230,234,245,.5)'
        ctx.font = '8px Consolas, monospace'
        ctx.fillText(win.tag, win.x + 10, win.y + 10 - lift)
        if (w < checks) {
          const kx = win.x + win.w - 13, ky = win.y + 8 - lift
          ctx.strokeStyle = 'rgba(74,222,128,.95)'
          ctx.lineWidth = 2
          ctx.shadowColor = '#4ADE80'
          ctx.shadowBlur = 7
          ctx.beginPath()
          ctx.moveTo(kx - 4, ky)
          ctx.lineTo(kx - 1, ky + 3)
          ctx.lineTo(kx + 4, ky - 3)
          ctx.stroke()
          ctx.shadowBlur = 0
        }
        for (let l = 0; l < 4; l++) {
          const lyy = win.y + 26 + l * 14 - lift
          const near = act && Math.abs(cur.y - lyy) < 9 && cur.x > win.x && cur.x < win.x + win.w
          ctx.fillStyle = near ? win.hue + 'AA' : 'rgba(230,234,245,.15)'
          if (near) { ctx.shadowColor = win.hue; ctx.shadowBlur = 8 }
          ctx.beginPath(); ctx.roundRect(win.x + 11, lyy, win.w * 0.72 - (l % 2) * 16, 5, 2.5); ctx.fill()
          ctx.shadowBlur = 0
        }
      }
      const bw = Math.min(118, W * 0.17)
      ctx.strokeStyle = rgba(accent, 0.7)
      ctx.setLineDash([5, 4])
      ctx.lineWidth = 1.4
      ctx.beginPath(); ctx.roundRect(bx - bw / 2, by - 24, bw, 122, 10); ctx.stroke()
      ctx.setLineDash([])
      ctx.fillStyle = 'rgba(199,210,254,.75)'
      ctx.font = '9px Consolas, monospace'
      ctx.textAlign = 'center'
      ctx.fillText('SYNTHÈSE', bx, by - 8)
      ctx.textAlign = 'left'
      const stk = Math.floor(Math.min(1, Math.max(0, prog)) * 7)
      for (let s = 0; s < stk; s++) {
        ctx.fillStyle = rgba(accent, 0.5 - s * 0.04)
        ctx.beginPath(); ctx.roundRect(bx - bw / 2 + 10, by + 2 + s * 11, bw - 20, 7, 3); ctx.fill()
      }
      const stkF = Math.min(1, Math.max(0, prog)) * 7 - stk
      if (stk < 7 && stkF > 0) {
        ctx.fillStyle = rgba(accent, 0.35)
        ctx.beginPath(); ctx.roundRect(bx - bw / 2 + 10, by + 2 + stk * 11, Math.max(3, (bw - 20) * stkF), 7, 3); ctx.fill()
      }
      ctx.globalCompositeOperation = 'lighter'
      for (let t = trail.length - 1; t >= 0; t--) {
        const tr = trail[t]
        tr.life -= 0.03
        if (tr.life <= 0) { trail.splice(t, 1); continue }
        ctx.fillStyle = rgba(accent, tr.life * 0.25)
        ctx.beginPath(); ctx.arc(tr.x, tr.y, 3 * tr.life, 0, 6.2832); ctx.fill()
      }
      for (let f = frags.length - 1; f >= 0; f--) {
        const fr = frags[f]
        fr.p += fr.s
        if (fr.p >= 1) { frags.splice(f, 1); continue }
        const u = fr.p, v = 1 - u
        const mx = (fr.x + fr.tx) / 2, my = Math.min(fr.y, fr.ty) - 46
        const x = v * v * fr.x + 2 * v * u * mx + u * u * fr.tx
        const y = v * v * fr.y + 2 * v * u * my + u * u * fr.ty
        ctx.fillStyle = fr.hue + 'CC'
        ctx.shadowColor = fr.hue
        ctx.shadowBlur = 10
        ctx.beginPath(); ctx.roundRect(x - 9, y - 3, 18, 6, 3); ctx.fill()
        ctx.shadowBlur = 0
      }
      for (let r = rip.length - 1; r >= 0; r--) {
        const ri = rip[r]
        ri.r += 1.1
        ri.life -= 0.03
        if (ri.life <= 0) { rip.splice(r, 1); continue }
        ctx.strokeStyle = `rgba(199,210,254,${ri.life})`
        ctx.lineWidth = 1.6
        ctx.beginPath(); ctx.arc(ri.x, ri.y, ri.r, 0, 6.2832); ctx.stroke()
      }
      glow(ctx, cur.x, cur.y, 18, rgba(accent, 0.6), 'rgba(224,231,255,.9)')
      ctx.globalCompositeOperation = 'source-over'
      ctx.fillStyle = '#E0E7FF'
      ctx.strokeStyle = 'rgba(30,27,75,.9)'
      ctx.lineWidth = 1.2
      ctx.beginPath()
      ctx.moveTo(cur.x, cur.y)
      ctx.lineTo(cur.x, cur.y + 13)
      ctx.lineTo(cur.x + 3.6, cur.y + 9.6)
      ctx.lineTo(cur.x + 8.4, cur.y + 15)
      ctx.lineTo(cur.x + 10.4, cur.y + 13)
      ctx.lineTo(cur.x + 5.8, cur.y + 8)
      ctx.lineTo(cur.x + 10, cur.y + 7)
      ctx.closePath()
      ctx.fill()
      ctx.stroke()
    }
  },
}

export const FX_SCENES: Record<FxModule, FxScene> = {
  conversation,
  image,
  code,
  video,
  drawing,
  '3d': threeD,
  learning,
  cyber,
  voice,
  cowork,
}
