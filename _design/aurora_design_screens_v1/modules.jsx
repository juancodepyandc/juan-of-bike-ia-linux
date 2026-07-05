/* Compact module screens — built efficiently for design canvas display.
   Each one is a hero scene (sphere + editorial layout + module-specific UI). */

/* ============== ACADEMY ============== */
function AcademyScreen() {
  return (
    <div style={{ position: 'relative', height: '100%', display: 'grid', gridTemplateColumns: '1fr 1.1fr', gap: 0 }}>
      <div style={{ padding: '40px 36px', display: 'flex', flexDirection: 'column', gap: 18, borderRight: '1px solid var(--line)' }}>
        <Eyebrow dot="oklch(0.74 0.11 90)">Academy · BAC STI2D · Session 2026</Eyebrow>
        <Display size={76}>Diffusion<br/><em style={{ color: 'var(--ember-500)' }}>thermique</em></Display>
        <p style={{ fontSize: 14.5, lineHeight: 1.55, color: 'var(--fg-dim)', maxWidth: 480 }}>
          Cours · 12 fiches · 4 exos générés · 1 quiz Leitner · révision dans 2h41.
          Calibré sur Métropole 2024, 2023, et Polynésie 2024.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Tag tint="oklch(0.74 0.11 90)">Physique-Chimie</Tag>
          <Tag>STI2D · Tle</Tag>
          <Tag>Coef. 16</Tag>
          <Tag>Niveau 4 / 5</Tag>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 12 }}>
          {[['Cours', '12'], ['Fiches', '8'], ['Exos', '4'], ['Quiz', '37']].map(([l, v]) => (
            <Panel key={l} style={{ padding: 12 }}>
              <div className="tech">{l}</div>
              <div style={{ fontFamily: 'var(--font-display)', fontStyle: 'italic', fontSize: 26, letterSpacing: '-0.02em' }}>{v}</div>
            </Panel>
          ))}
        </div>
        <div style={{ flex: 1 }}/>
        <Panel raised style={{ padding: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
            <Eyebrow>Leitner · prochaine révision</Eyebrow>
            <span className="tech">2h41</span>
          </div>
          <div style={{ height: 6, borderRadius: 99, background: 'var(--ink-800)', overflow: 'hidden' }}>
            <div style={{ width: '64%', height: '100%', background: 'linear-gradient(90deg, var(--ember-500), oklch(0.74 0.11 90))' }}/>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--fg-mute)' }}>
            <span>boîte 1 · 7</span><span>2 · 12</span><span>3 · 9</span><span>4 · 5</span><span>5 · 4</span>
          </div>
        </Panel>
      </div>

      <div style={{ position: 'relative', padding: 36 }}>
        <div style={{ position: 'absolute', inset: '36px 36px 220px' }}>
          <AuroraSphere tint="oklch(0.74 0.11 90)" state="thinking" radius={0.32}/>
        </div>
        <Crosshairs inset={36} size={14}/>
        <div style={{ position: 'absolute', bottom: 36, left: 36, right: 36 }}>
          <Panel raised style={{ padding: 18 }}>
            <Eyebrow style={{ marginBottom: 10 }}>Exam blanc · live</Eyebrow>
            <div style={{ fontFamily: 'var(--font-display)', fontStyle: 'italic', fontSize: 20, letterSpacing: '-0.01em', marginBottom: 10 }}>
              « Un mur en parpaings de 18 cm sépare un local chauffé à 19°C… »
            </div>
            <div style={{ display: 'flex', gap: 8, fontSize: 12 }}>
              <Btn size="sm" variant="primary">Indice 1 / 3</Btn>
              <Btn size="sm" variant="ghost">Voir corrigé</Btn>
              <Btn size="sm" variant="bare">Sauter</Btn>
              <span style={{ flex: 1 }}/>
              <span className="tech" style={{ alignSelf: 'center' }}>14:23 / 18:00</span>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

/* ============== IMAGE — FLUX wheel ============== */
function ImageScreen() {
  const styles = ['Sumi-e', 'Renaissance', 'Cyberpunk', 'Watercolor', 'Editorial', 'Brutalist', 'Polaroid', 'Manga', '3D render', 'Cinéma 35mm', 'Pencil', 'Vintage'];
  return (
    <div style={{ position: 'relative', height: '100%', padding: '32px 40px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
        <Eyebrow dot="oklch(0.70 0.14 320)">Image · FLUX dev</Eyebrow>
        <span style={{ flex: 1 }}/>
        <Tag tint="oklch(0.70 0.14 320)">flux1-dev-fp8</Tag>
        <Tag>1024² · 28 steps</Tag>
        <Tag>seed 0341</Tag>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr 320px', gap: 20, flex: 1, minHeight: 0 }}>
        {/* Wheel */}
        <Panel padded={false} style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--line)' }}>
            <Eyebrow>Style wheel</Eyebrow>
          </div>
          <div style={{ position: 'relative', height: 'calc(100% - 50px)' }}>
            <div style={{ position: 'absolute', inset: 20 }}>
              <AuroraSphere tint="oklch(0.70 0.14 320)" state="streaming" radius={0.28}/>
            </div>
            {styles.map((s, i) => {
              const angle = (i / styles.length) * 360;
              const rad = angle * Math.PI / 180;
              return (
                <div key={s} style={{
                  position: 'absolute', left: '50%', top: '50%',
                  transform: `translate(-50%,-50%) rotate(${angle}deg) translateY(-42%) rotate(${-angle}deg)`,
                }}>
                  <span style={{
                    fontFamily: 'var(--font-display)', fontStyle: 'italic',
                    fontSize: i === 0 ? 24 : 14,
                    color: i === 0 ? 'var(--ember-500)' : 'var(--fg-dim)',
                    letterSpacing: '-0.01em', whiteSpace: 'nowrap',
                  }}>{s}</span>
                </div>
              );
            })}
          </div>
        </Panel>

        {/* Canvas */}
        <Panel padded={false} style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between' }}>
            <Eyebrow>Canvas · 1024 × 1024</Eyebrow>
            <span className="tech">step 19 / 28 · 0.6s/it</span>
          </div>
          <div style={{ flex: 1, padding: 18, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Specimen label="variant 01" ratio="1/1" tint="oklch(0.30 0.05 320)"/>
            <Specimen label="variant 02 · streaming" ratio="1/1" tint="oklch(0.30 0.05 320)"/>
            <Specimen label="variant 03" ratio="1/1" tint="oklch(0.30 0.05 320)"/>
            <Specimen label="variant 04" ratio="1/1" tint="oklch(0.30 0.05 320)"/>
          </div>
        </Panel>

        {/* Prompt */}
        <Panel raised>
          <Eyebrow style={{ marginBottom: 10 }}>Prompt</Eyebrow>
          <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--fg)', minHeight: 120 }}>
            une grue cendrée traversant un paysage de <em style={{ color: 'var(--ember-500)' }}>encre lavis</em>, papier washi, brume du matin, cinematic lighting
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12 }}>
            <Tag>+ negative</Tag><Tag>+ ref</Tag><Tag>+ inpaint</Tag>
          </div>
          <div className="hrule" style={{ margin: '14px 0' }}/>
          <Eyebrow style={{ marginBottom: 8 }}>Réglages</Eyebrow>
          {[['Guidance', '4.5'], ['Steps', '28'], ['Sampler', 'euler·a']].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 12, padding: '6px 0', borderBottom: '1px dashed var(--line-soft)' }}>
              <span style={{ color: 'var(--fg-dim)' }}>{k}</span><span>{v}</span>
            </div>
          ))}
          <Btn variant="primary" style={{ width: '100%', marginTop: 16, justifyContent: 'center' }}>Générer · ⌘↵</Btn>
        </Panel>
      </div>
    </div>
  );
}

/* ============== VIDEO — Wan2.2 cinema ============== */
function VideoScreen() {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 1, position: 'relative', background: 'oklch(0.06 0.01 250)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {/* "projector" beam */}
        <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 50% 35% at 50% 50%, oklch(0.68 0.13 260 / 0.18), transparent 70%)' }}/>
        <div style={{
          width: '70%', aspectRatio: '16/9',
          border: '1px solid var(--line-strong)', position: 'relative',
          background: `repeating-linear-gradient(90deg, oklch(0.16 0.02 260), oklch(0.16 0.02 260) 14px, oklch(0.20 0.03 260) 14px, oklch(0.20 0.03 260) 28px)`,
          boxShadow: '0 0 80px oklch(0.68 0.13 260 / 0.25)'
        }}>
          <div style={{ position: 'absolute', top: 14, left: 14, display: 'flex', gap: 6 }}>
            <Tag tint="var(--ember-500)">REC</Tag>
            <Tag>04 / 12</Tag>
          </div>
          <div style={{ position: 'absolute', bottom: 14, right: 14 }}>
            <span className="tech">wan2.2-i2v-14B · 720p · 16fps</span>
          </div>
          <Crosshairs inset={6} size={16}/>
        </div>
      </div>

      {/* Editorial title under */}
      <div style={{ padding: '28px 40px 16px', display: 'flex', alignItems: 'flex-end', gap: 24, borderTop: '1px solid var(--line)' }}>
        <div style={{ flex: 1 }}>
          <Eyebrow dot="oklch(0.68 0.13 260)" style={{ marginBottom: 6 }}>Vidéo · Wan2.2 · Projecteur</Eyebrow>
          <Display size={64}>L'aurore<br/>sur la <em style={{ color: 'var(--ember-500)' }}>baie</em></Display>
        </div>
        <Btn variant="ghost">⏮︎</Btn>
        <Btn variant="primary" size="lg">⏵</Btn>
        <Btn variant="ghost">⏭︎</Btn>
        <span style={{ flex: 1 }}/>
        <span className="tech">00:04 / 00:12 · render 38%</span>
      </div>

      {/* Timeline */}
      <div style={{ padding: '0 40px 24px' }}>
        <div style={{ height: 60, border: '1px solid var(--line)', borderRadius: 8, position: 'relative', background: 'var(--bg-raised)', overflow: 'hidden' }}>
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} style={{ position: 'absolute', left: `${i * 8.33}%`, top: 0, bottom: 0, width: '8.33%', borderRight: '1px solid var(--line-soft)', background: i === 4 ? 'oklch(0.68 0.13 260 / 0.25)' : 'transparent' }}>
              <span style={{ position: 'absolute', top: 4, left: 4, fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--fg-mute)' }}>{String(i+1).padStart(2,'0')}</span>
            </div>
          ))}
          <div style={{ position: 'absolute', left: '34%', top: 0, bottom: 0, width: 2, background: 'var(--ember-500)', boxShadow: '0 0 12px var(--ember-500)' }}/>
        </div>
      </div>
    </div>
  );
}

/* ============== CODE ============== */
function CodeScreen() {
  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateColumns: '260px 1fr 1fr', gap: 0 }}>
      <div style={{ padding: '24px 18px', borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Eyebrow dot="oklch(0.72 0.12 145)">Code · Multi-modèle</Eyebrow>
        <div style={{ marginTop: 6 }}>
          {['App.tsx', 'router.ts', 'auth/', 'api/diffusion.ts', 'lib/utils.ts', 'theme.css', 'README.md'].map((f, i) => (
            <div key={f} style={{
              padding: '6px 10px', borderRadius: 6, fontSize: 12,
              fontFamily: 'var(--font-mono)', color: i === 3 ? 'var(--fg)' : 'var(--fg-dim)',
              background: i === 3 ? 'var(--ink-800)' : 'transparent', display: 'flex', gap: 8
            }}>
              <span style={{ color: 'var(--fg-mute)' }}>{i === 3 ? '◆' : '·'}</span>{f}
            </div>
          ))}
        </div>
        <div style={{ flex: 1 }}/>
        <Panel style={{ padding: 12 }}>
          <Eyebrow style={{ marginBottom: 8 }}>Modèles actifs</Eyebrow>
          {[['qwen3:14b', 'plan'], ['deepseek-coder:33b', 'edit'], ['llama3.2:3b', 'fix']].map(([m, r]) => (
            <div key={m} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11, padding: '4px 0' }}>
              <span>{m}</span><span style={{ color: 'oklch(0.72 0.12 145)' }}>{r}</span>
            </div>
          ))}
        </Panel>
      </div>

      <div style={{ borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '14px 22px', borderBottom: '1px solid var(--line)' }}>
          <Eyebrow>api/diffusion.ts · before</Eyebrow>
        </div>
        <pre style={{ flex: 1, padding: '18px 22px', margin: 0, fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.7, color: 'var(--fg-dim)', overflow: 'auto' }}>
{`export async function diffuse(
  prompt: string,
  steps = 28,
`}<span style={{ background: 'oklch(0.55 0.18 25 / 0.2)', display: 'block', padding: '0 22px', margin: '0 -22px' }}>{`  // TODO: validate guidance range
  guidance: number,`}</span>{`
) {
  const res = await fetch('/api/flux', {
    method: 'POST',
    body: JSON.stringify({ prompt, steps }),
  });
  return res.json();
}`}
        </pre>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '14px 22px', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between' }}>
          <Eyebrow dot="oklch(0.72 0.12 145)">after · streaming</Eyebrow>
          <span className="tech">+18 −4 · 0.4s</span>
        </div>
        <pre style={{ flex: 1, padding: '18px 22px', margin: 0, fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.7, color: 'var(--fg)', overflow: 'auto' }}>
{`export async function diffuse(
  prompt: string,
  steps = 28,
`}<span style={{ background: 'oklch(0.72 0.12 145 / 0.18)', display: 'block', padding: '0 22px', margin: '0 -22px' }}>{`  guidance: number = 4.5,
) {
  if (guidance < 1 || guidance > 20) {
    throw new RangeError('guidance ∈ [1, 20]');
  }`}</span>{`
  const res = await fetch('/api/flux', {
    method: 'POST',
    body: JSON.stringify({ prompt, steps, guidance }),
  });
  return res.json();
}`}
        </pre>
        <div style={{ padding: 14, borderTop: '1px solid var(--line)', display: 'flex', gap: 8 }}>
          <Btn size="sm" variant="primary">Accepter ⌘↵</Btn>
          <Btn size="sm" variant="ghost">Réviser</Btn>
          <Btn size="sm" variant="bare">Annuler</Btn>
        </div>
      </div>
    </div>
  );
}

/* ============== DESSIN — sumi-e ============== */
function DrawScreen() {
  return (
    <div data-theme="paper" style={{ height: '100%', background: 'var(--paper)', color: 'var(--ink-1000)', position: 'relative', display: 'flex' }}>
      <div style={{ width: 280, padding: '32px 24px', borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Eyebrow style={{ color: 'var(--ink-700)' }}>墨 Dessin · Sumi-e</Eyebrow>
        <Display size={56} style={{ color: 'var(--ink-1000)' }}>Encre<br/><em>vivante</em></Display>
        <p style={{ fontSize: 13.5, lineHeight: 1.55, color: 'var(--ink-700)' }}>
          Tablette + ML — Aurora suit la pression et le geste, propose
          des continuations dans le style sumi-e ou sketch2img.
        </p>
        <div className="hrule" style={{ background: 'var(--line)' }}/>
        <Eyebrow style={{ color: 'var(--ink-700)' }}>Pinceaux</Eyebrow>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {['筆 #6', '筆 #12', '渇筆', 'sketch', 'lavis'].map((b, i) => (
            <span key={b} style={{
              padding: '6px 10px', border: `1px solid ${i === 0 ? 'var(--ink-1000)' : 'var(--line)'}`,
              borderRadius: 4, fontSize: 12, fontFamily: 'var(--font-mono)',
              background: i === 0 ? 'var(--ink-1000)' : 'transparent',
              color: i === 0 ? 'var(--paper)' : 'var(--ink-1000)'
            }}>{b}</span>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {/* Paper canvas */}
        <div style={{ position: 'absolute', inset: 40, background: 'oklch(0.99 0.005 85)', border: '1px solid var(--ink-200)', boxShadow: '0 30px 80px rgba(0,0,0,0.08)' }}>
          {/* hand-stroke abstract via filter */}
          <svg width="100%" height="100%" viewBox="0 0 800 500" preserveAspectRatio="xMidYMid meet">
            <path d="M 120 320 C 220 260, 280 360, 380 240 S 540 280, 660 200" stroke="oklch(0.10 0.01 250)" strokeWidth="14" fill="none" strokeLinecap="round" opacity="0.86"/>
            <path d="M 360 240 C 380 200, 420 160, 460 180 S 520 240, 540 230" stroke="oklch(0.18 0.01 250)" strokeWidth="6" fill="none" strokeLinecap="round" opacity="0.7"/>
            <circle cx="600" cy="160" r="10" fill="oklch(0.55 0.18 25)" opacity="0.85"/>
            <text x="612" y="166" fontFamily="JetBrains Mono" fontSize="10" fill="oklch(0.40 0.01 80)">落款 · 0341</text>
          </svg>
          <Crosshairs inset={6} size={12} color="var(--ink-300)"/>
        </div>

        {/* AI suggestion floater */}
        <div style={{ position: 'absolute', right: 60, top: 60, width: 220 }}>
          <Panel style={{ background: 'var(--paper-2)', border: '1px solid var(--line-strong)', padding: 12 }}>
            <Eyebrow dot="var(--ember-500)" style={{ color: 'var(--ink-700)' }}>Aurora propose</Eyebrow>
            <Specimen label="continuation" ratio="4/3" tint="var(--ink-300)" style={{ marginTop: 10 }}/>
            <Btn size="sm" variant="primary" style={{ width: '100%', marginTop: 10, justifyContent: 'center' }}>Appliquer</Btn>
          </Panel>
        </div>
      </div>
    </div>
  );
}

/* ============== 3D ============== */
function ThreeDScreen() {
  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateColumns: '1fr 320px' }}>
      <div style={{ position: 'relative', borderRight: '1px solid var(--line)' }}>
        {/* Stage with wireframe object placeholder */}
        <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(ellipse 50% 40% at 50% 60%, oklch(0.74 0.13 60 / 0.15), transparent 70%)` }}/>
        <div style={{ position: 'absolute', inset: '15% 20%' }}>
          <AuroraSphere tint="oklch(0.74 0.13 60)" state="streaming" radius={0.42} glow={1.4}/>
        </div>
        {/* wireframe overlay */}
        <svg width="100%" height="100%" viewBox="0 0 600 400" style={{ position: 'absolute', inset: 0, opacity: 0.5 }}>
          <g stroke="oklch(0.74 0.13 60)" fill="none" strokeWidth="0.6">
            <path d="M 200 240 L 300 180 L 400 240 L 300 300 Z"/>
            <path d="M 200 240 L 300 280 L 400 240"/>
            <path d="M 300 180 L 300 280"/>
            <path d="M 200 240 L 220 220 L 380 220 L 400 240"/>
          </g>
        </svg>

        <div style={{ position: 'absolute', top: 24, left: 32 }}>
          <Eyebrow dot="oklch(0.74 0.13 60)" style={{ marginBottom: 10 }}>3D · Hunyuan3D · DreamGaussian</Eyebrow>
          <Display size={62}>Grue<br/><em style={{ color: 'var(--ember-500)' }}>en vol</em></Display>
        </div>

        {/* viewport corners */}
        <div style={{ position: 'absolute', bottom: 24, left: 32, display: 'flex', gap: 16, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-mute)' }}>
          <span>front · 0°</span><span>top · 90°</span><span>right · 0°</span>
        </div>
        <div style={{ position: 'absolute', bottom: 24, right: 32 }}>
          <span className="tech">12 482 verts · 8 196 tris · 24mb</span>
        </div>
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Eyebrow>Pipeline</Eyebrow>
        {[
          ['intent', 'done'], ['traits', 'done'], ['portrait', 'done'],
          ['variations', 'done'], ['segmentation', 'running'], ['rig', 'queued'],
          ['assemblage', 'queued'], ['publish', 'queued'],
        ].map(([s, st], i) => (
          <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px dashed var(--line-soft)' }}>
            <span style={{ width: 22, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-mute)' }}>{String(i+1).padStart(2,'0')}</span>
            <span style={{ flex: 1, fontSize: 13, color: st === 'queued' ? 'var(--fg-mute)' : 'var(--fg)' }}>{s}</span>
            <NodeDot active={st !== 'queued'} color={st === 'running' ? 'var(--ember-500)' : 'oklch(0.72 0.12 145)'}/>
          </div>
        ))}
        <Btn variant="primary" style={{ marginTop: 12, justifyContent: 'center' }}>Exporter .glb</Btn>
      </div>
    </div>
  );
}

/* ============== VOICE ============== */
function VoiceScreen() {
  return (
    <div style={{ height: '100%', position: 'relative', display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 1, position: 'relative' }}>
        <div style={{ position: 'absolute', inset: '6% 25%' }}>
          <AuroraSphere tint="oklch(0.72 0.14 350)" state="voice" radius={0.46} glow={1.4}/>
        </div>

        {/* live captions */}
        <div style={{ position: 'absolute', bottom: '12%', left: '50%', transform: 'translateX(-50%)', maxWidth: 720, textAlign: 'center' }}>
          <Eyebrow dot="oklch(0.72 0.14 350)" style={{ marginBottom: 14, justifyContent: 'center' }}>Voice live · whisper.cpp · cam on</Eyebrow>
          <p style={{ fontFamily: 'var(--font-display)', fontStyle: 'italic', fontSize: 36, lineHeight: 1.2, letterSpacing: '-0.015em', color: 'var(--fg)', margin: 0 }}>
            « Je vois ton croquis — la <span style={{ color: 'var(--ember-500)' }}>trace centrale</span> ressemble à une diffusion guidée. On en parle&nbsp;? »
          </p>
        </div>

        {/* waveform side panels */}
        <div style={{ position: 'absolute', left: 40, top: '50%', transform: 'translateY(-50%)', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Eyebrow style={{ marginBottom: 8 }}>You · in</Eyebrow>
          {Array.from({ length: 24 }).map((_, i) => (
            <div key={i} style={{ width: 80 + Math.sin(i * 0.5) * 30, height: 3, background: 'var(--fg-dim)', opacity: 0.4 + (i % 5) * 0.12, borderRadius: 99 }}/>
          ))}
        </div>
        <div style={{ position: 'absolute', right: 40, top: '50%', transform: 'translateY(-50%)', display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-end' }}>
          <Eyebrow style={{ marginBottom: 8 }}>Aurora · out</Eyebrow>
          {Array.from({ length: 24 }).map((_, i) => (
            <div key={i} style={{ width: 60 + Math.cos(i * 0.7) * 40, height: 3, background: 'oklch(0.72 0.14 350)', opacity: 0.5 + (i % 4) * 0.14, borderRadius: 99 }}/>
          ))}
        </div>
      </div>

      <div style={{ padding: '20px 40px', borderTop: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 14 }}>
        <Btn variant="ghost">🎥 Caméra</Btn>
        <Btn variant="ghost">🔇 Mute</Btn>
        <Btn variant="ghost">⚙ Voice</Btn>
        <span style={{ flex: 1 }}/>
        <span className="tech">02:14 actif · 412 turns · latence 312ms</span>
        <Btn variant="primary">Terminer</Btn>
      </div>
    </div>
  );
}

/* ============== CYBER ============== */
function CyberScreen() {
  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 0 }}>
      <div style={{ padding: '36px 32px', borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 18, position: 'relative' }}>
        <Eyebrow dot="oklch(0.70 0.13 130)">※ Cyber · Dojo · Kata 0341</Eyebrow>
        <Display size={64}>SQL<br/><em style={{ color: 'var(--ember-500)' }}>injection</em></Display>
        <p style={{ fontSize: 14.5, lineHeight: 1.55, color: 'var(--fg-dim)', maxWidth: 420 }}>
          Lab 4 · authentification cassée. Ton objectif&nbsp;: récupérer le flag
          <code style={{ fontFamily: 'var(--font-mono)', color: 'oklch(0.70 0.13 130)' }}> AURORA{'{'}…{'}'} </code>
          en exploitant la requête de login. Sans payload connu.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Tag tint="oklch(0.70 0.13 130)">Web · auth</Tag>
          <Tag>★★★☆☆</Tag>
          <Tag>4 hints</Tag>
          <Tag>OWASP A03</Tag>
        </div>
        <div style={{ flex: 1 }}/>
        <Panel raised style={{ padding: 14 }}>
          <Eyebrow style={{ marginBottom: 8 }}>Leaderboard · solo</Eyebrow>
          {[['01', 'kata 0339', '★★★★☆', '4m12'], ['02', 'kata 0340', '★★★☆☆', '7m02'], ['03', 'kata 0341', '—', 'live']].map(([n, k, s, t]) => (
            <div key={n} style={{ display: 'grid', gridTemplateColumns: '24px 1fr auto auto', gap: 10, fontFamily: 'var(--font-mono)', fontSize: 12, padding: '5px 0', color: t === 'live' ? 'var(--fg)' : 'var(--fg-dim)' }}>
              <span style={{ color: 'var(--fg-mute)' }}>{n}</span><span>{k}</span><span>{s}</span><span style={{ color: t === 'live' ? 'var(--ember-500)' : 'var(--fg-dim)' }}>{t}</span>
            </div>
          ))}
        </Panel>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, padding: 24, fontFamily: 'var(--font-mono)', fontSize: 12.5, lineHeight: 1.7, background: 'oklch(0.06 0.01 250)', overflow: 'auto', color: 'var(--fg-dim)' }}>
          <div style={{ color: 'oklch(0.70 0.13 130)' }}>$ aurora kata start 0341</div>
          <div>→ lab spawn · http://127.0.0.1:8341 · target ready</div>
          <div>→ checklist: 1. enum  2. inject  3. exfil  4. flag</div>
          <div style={{ marginTop: 14, color: 'var(--fg-mute)' }}># probe login form</div>
          <div>$ curl -X POST :8341/login -d "u=admin&p=test"</div>
          <div>← 401 · invalid credentials</div>
          <div style={{ marginTop: 14, color: 'var(--fg-mute)' }}># try classic payload</div>
          <div style={{ color: 'var(--fg)' }}>$ curl -X POST :8341/login -d "u=admin'--&p="</div>
          <div style={{ color: 'oklch(0.70 0.13 130)' }}>← 200 · welcome admin · token=eyJhb…</div>
          <div style={{ marginTop: 14, color: 'var(--ember-500)' }}>✓ flag captured: AURORA{`{tautology_via_quote}`}</div>
          <div style={{ marginTop: 14 }}><span style={{ color: 'oklch(0.70 0.13 130)' }}>$ </span><span style={{ borderRight: '8px solid var(--ember-500)', animation: 'aurora-blink 1s steps(2) infinite' }}>&nbsp;</span></div>
        </div>
        <div style={{ padding: 14, borderTop: '1px solid var(--line)', display: 'flex', gap: 8 }}>
          <Btn size="sm" variant="primary">Valider flag · ⌘↵</Btn>
          <Btn size="sm" variant="ghost">Hint 2 / 4</Btn>
          <Btn size="sm" variant="ghost">Reset lab</Btn>
          <span style={{ flex: 1 }}/>
          <span className="tech" style={{ alignSelf: 'center' }}>HUD · score 840 · streak 3</span>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  AcademyScreen, ImageScreen, VideoScreen, CodeScreen, DrawScreen, ThreeDScreen, VoiceScreen, CyberScreen
});
