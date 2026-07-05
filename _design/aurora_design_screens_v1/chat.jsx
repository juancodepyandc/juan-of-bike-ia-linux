/* Conversation — chat with reactive Aurora avatar. */

function ChatBubble({ who, children, attachments, streaming }) {
  const isAurora = who === 'aurora';
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '40px 1fr', gap: 14,
      padding: '14px 0', borderTop: '1px solid var(--line-soft)',
      animation: 'aurora-fadein .6s var(--ease-out)'
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 99,
        background: isAurora
          ? 'radial-gradient(circle at 30% 30%, var(--ember-200), var(--ember-700))'
          : 'var(--ink-800)',
        border: '1px solid var(--line)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
        color: isAurora ? 'var(--ink-1000)' : 'var(--fg-dim)'
      }}>{isAurora ? '✺' : 'J'}</div>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', marginBottom: 4 }}>
          <span style={{ fontWeight: 600, fontSize: 13 }}>{isAurora ? 'Aurora' : 'Juan'}</span>
          <span className="tech">{isAurora ? 'qwen3-vl · 14b' : '14:02'}</span>
          {streaming && <span className="tech" style={{ color: 'var(--ember-500)' }}>● streaming</span>}
        </div>
        <div style={{ fontSize: 14.5, lineHeight: 1.6, color: 'var(--fg)' }}>
          {children}
          {streaming && <span style={{
            display: 'inline-block', width: 7, height: 16, marginLeft: 4,
            verticalAlign: 'text-bottom', background: 'var(--ember-500)',
            animation: 'aurora-blink .9s steps(2) infinite'
          }}/>}
        </div>
        {attachments && (
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            {attachments.map((a, i) => (
              <div key={i} style={{
                width: 96, aspectRatio: '4/3',
                background: `repeating-linear-gradient(135deg, var(--ink-800), var(--ink-800) 6px, transparent 6px, transparent 12px), var(--bg-card)`,
                border: '1px solid var(--line)', borderRadius: 6,
                display: 'flex', alignItems: 'flex-end', padding: 6,
                fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--fg-mute)',
                letterSpacing: '0.06em', textTransform: 'uppercase'
              }}>{a}</div>
            ))}
          </div>
        )}
      </div>
      <style>{`
        @keyframes aurora-fadein { from { opacity: 0; transform: translateY(4px) } to { opacity: 1; transform: translateY(0) } }
        @keyframes aurora-blink { 50% { opacity: 0 } }
      `}</style>
    </div>
  );
}

function ChatScreen() {
  const [voiceMode, setVoice] = React.useState(false);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '420px 1fr', height: '100%' }}>
      {/* Left rail — sphere + state */}
      <div style={{
        position: 'relative', borderRight: '1px solid var(--line)',
        display: 'flex', flexDirection: 'column'
      }}>
        <div style={{ padding: '20px 24px 0', display: 'flex', justifyContent: 'space-between' }}>
          <Eyebrow dot="oklch(0.72 0.12 200)">Conversation</Eyebrow>
          <Tag>session 0341</Tag>
        </div>
        <div style={{ flex: 1, position: 'relative' }}>
          <div style={{ position: 'absolute', inset: '20px 28px 0' }}>
            <AuroraSphere
              tint="oklch(0.72 0.120 200)"
              state={voiceMode ? 'voice' : 'streaming'}
              radius={0.42} glow={1.2}
            />
            {window.OrbitRing && <OrbitRing radius={140} count={1} speed={36} dotColor="oklch(0.72 0.120 200)"/>}
          </div>
          <Crosshairs inset={20} size={14}/>

          <div style={{ position: 'absolute', bottom: 24, left: 24, right: 24 }}>
            <Display size={48} style={{ marginBottom: 12 }}>
              {voiceMode ? "J'écoute…" : 'Aurora pense'}
            </Display>
            <div className="tech" style={{ marginBottom: 14 }}>
              {voiceMode
                ? 'voice live · whisper.cpp · cam off'
                : 'streaming · 412 tok/s · ctx 14.2k'}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Btn size="sm" variant={voiceMode ? 'primary' : 'ghost'} onClick={() => setVoice(v => !v)}>
                ◌ Voice live
              </Btn>
              <Btn size="sm" variant="ghost">📎 Attach</Btn>
              <Btn size="sm" variant="ghost">🎥 Caméra</Btn>
              <Btn size="sm" variant="ghost">⚙ Modèles</Btn>
            </div>
          </div>
        </div>
      </div>

      {/* Right — transcript */}
      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div style={{
          padding: '18px 32px', borderBottom: '1px solid var(--line)',
          display: 'flex', alignItems: 'baseline', gap: 16
        }}>
          <Display size={36}>Diffusion en sumi-e</Display>
          <span style={{ flex: 1 }}/>
          <span className="tech">17 tours · 14.2k ctx · 0,00 €</span>
          <Btn size="sm" variant="ghost">Export PDF</Btn>
          <Btn size="sm" variant="ghost">Bifurquer</Btn>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 32px 32px' }}>
          <ChatBubble who="user">
            J'ai trois esquisses au fusain et un pdf d'article. Tu peux relier
            ce que dit l'article aux gestes que je vois dans mes croquis ?
          </ChatBubble>
          <ChatBubble who="user" attachments={['esquisse-01.png', 'esquisse-02.png', 'arxiv-2401.pdf']}>
            Voilà les fichiers.
          </ChatBubble>
          <ChatBubble who="aurora">
            <p style={{ margin: '0 0 10px' }}>
              Trois liens forts ressortent. <em style={{ fontFamily: 'var(--font-display)', color: 'var(--ember-500)' }}>D'abord</em>,
              le passage en p.4 sur la « propagation guidée » résonne avec ton geste
              sur l'esquisse 02 — la trace centrale joue le rôle d'un drift conditionné.
            </p>
            <ul style={{ margin: '8px 0 12px', paddingLeft: 18, color: 'var(--fg-dim)', fontSize: 14 }}>
              <li>esquisse 01 → score-matching, faible bruit</li>
              <li>esquisse 02 → guidance forte, trajectoire courbe</li>
              <li>esquisse 03 → step-skip, rendu lacunaire</li>
            </ul>
          </ChatBubble>
          <ChatBubble who="aurora" streaming>
            Je peux générer un mind map qui place chaque geste sur un axe
            « bruit / guidance », et préparer trois variantes
          </ChatBubble>
        </div>

        {/* Composer */}
        <div style={{
          padding: 18, borderTop: '1px solid var(--line)',
          background: 'var(--bg-raised)'
        }}>
          <div style={{
            border: '1px solid var(--line-strong)', borderRadius: 14, padding: 14,
            background: 'var(--bg-card)',
            boxShadow: '0 0 0 4px var(--accent-soft)'
          }}>
            <div style={{ fontSize: 14, color: 'var(--fg-dim)', minHeight: 40 }}>
              Écris à Aurora — joins images, fichiers, écran. ⌘↵ pour envoyer.
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
              <Btn size="sm" variant="bare">＋ Fichier</Btn>
              <Btn size="sm" variant="bare">@ Module</Btn>
              <Btn size="sm" variant="bare">/ Commande</Btn>
              <span style={{ flex: 1 }}/>
              <Tag>qwen3-vl · 14b</Tag>
              <Btn size="sm" variant="primary">Envoyer ↵</Btn>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.ChatScreen = ChatScreen;
