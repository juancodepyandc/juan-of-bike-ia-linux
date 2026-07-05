/*!
 * Aurora Embed — widget de chat à coller dans n'importe quel site.
 * Parle à ton IA locale Aurora via le tunnel, authentifié par une clé d'API.
 *
 * Usage (le plus simple) — colle ça avant </body> :
 *   <script src="https://TON-TUNNEL/aurora-embed.js"
 *           data-aurora-url="https://TON-TUNNEL"
 *           data-aurora-key="aur_XXXXXXXX"></script>
 *
 * Ou en JS :
 *   AuroraEmbed.init({ url:'https://TON-TUNNEL', key:'aur_XXXX', title:'Assistant', accent:'#d97757' })
 *
 * API exposée : AuroraEmbed.init(opts), AuroraEmbed.open(), AuroraEmbed.close(),
 *               AuroraEmbed.ask(text), AuroraEmbed.generate3D(prompt, onUpdate).
 *
 * 3D : tape « /3d <description> » dans le chat (ou AuroraEmbed.generate3D) →
 * le widget lance le pipeline (FLUX → Hunyuan3D → auto-rescue), affiche le
 * temps écoulé, et te renvoie l'URL du .glb une fois le rendu validé. À toi
 * de l'afficher dans ton viewer (the widget ne fait pas le rendu 3D lui-même).
 */
(function () {
  'use strict';
  if (window.AuroraEmbed && window.AuroraEmbed.__mounted) return;

  var S = {}; // state: url, key, title, accent, open, mounted, history
  var els = {};

  function css(str) { var s = document.createElement('style'); s.textContent = str; document.head.appendChild(s); }
  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) { if (k === 'style') e.style.cssText = attrs[k]; else e.setAttribute(k, attrs[k]); }
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function mountUI() {
    if (S.mounted) return;
    S.mounted = true;
    var ac = S.accent || '#d97757';
    css(
      '.aef{position:fixed;right:18px;bottom:18px;z-index:2147483000;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}' +
      '.aef-bub{width:56px;height:56px;border-radius:50%;background:' + ac + ';color:#fff;border:none;cursor:pointer;box-shadow:0 8px 28px rgba(0,0,0,.28);font-size:24px;display:flex;align-items:center;justify-content:center;transition:transform .15s}' +
      '.aef-bub:hover{transform:scale(1.06)}' +
      '.aef-panel{position:fixed;right:18px;bottom:84px;width:min(380px,calc(100vw - 28px));height:min(560px,calc(100vh - 110px));background:#15110f;color:#f3ede4;border:1px solid rgba(255,255,255,.10);border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.45);display:flex;flex-direction:column;overflow:hidden}' +
      '.aef-hd{padding:12px 14px;display:flex;align-items:center;gap:10px;border-bottom:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03)}' +
      '.aef-dot{width:8px;height:8px;border-radius:50%;background:#3ddc84;box-shadow:0 0 10px #3ddc84}' +
      '.aef-dot.off{background:#e0533f;box-shadow:0 0 10px #e0533f}' +
      '.aef-ti{font-weight:600;font-size:14px;flex:1}.aef-sub{font-size:10px;opacity:.6;font-family:ui-monospace,monospace}' +
      '.aef-x{background:none;border:none;color:#aaa;cursor:pointer;font-size:18px;line-height:1}' +
      '.aef-body{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;scroll-behavior:smooth}' +
      '.aef-msg{max-width:84%;padding:9px 12px;border-radius:13px;font-size:14px;line-height:1.5;white-space:pre-wrap;word-break:break-word}' +
      '.aef-msg.u{align-self:flex-end;background:' + ac + ';color:#fff;border-bottom-right-radius:4px}' +
      '.aef-msg.a{align-self:flex-start;background:rgba(255,255,255,.06);border-bottom-left-radius:4px}' +
      '.aef-msg.sys{align-self:center;font-size:11px;opacity:.65;font-family:ui-monospace,monospace;background:none;text-align:center}' +
      '.aef-msg.a a{color:' + ac + '}' +
      '.aef-foot{padding:10px;border-top:1px solid rgba(255,255,255,.08);display:flex;gap:8px;align-items:flex-end;background:rgba(255,255,255,.02)}' +
      '.aef-in{flex:1;resize:none;max-height:110px;min-height:38px;padding:9px 11px;border-radius:10px;border:1px solid rgba(255,255,255,.12);background:#0c0a09;color:#f3ede4;font:inherit;font-size:14px;outline:none}' +
      '.aef-in:focus{border-color:' + ac + '}' +
      '.aef-send{border:none;border-radius:10px;background:' + ac + ';color:#fff;cursor:pointer;padding:0 14px;height:38px;font-weight:600;font-size:13px}' +
      '.aef-send:disabled{opacity:.5;cursor:default}' +
      '.aef-typ{align-self:flex-start;display:flex;gap:4px;padding:10px 12px}.aef-typ i{width:6px;height:6px;border-radius:50%;background:#bbb;animation:aefb 1.1s infinite}.aef-typ i:nth-child(2){animation-delay:.15s}.aef-typ i:nth-child(3){animation-delay:.3s}@keyframes aefb{0%,60%,100%{opacity:.3;transform:translateY(0)}30%{opacity:1;transform:translateY(-3px)}}' +
      '@media(prefers-color-scheme:light){.aef-panel{background:#fbf7f0;color:#1c1614;border-color:rgba(0,0,0,.10)}.aef-hd{background:rgba(0,0,0,.02);border-color:rgba(0,0,0,.07)}.aef-msg.a{background:rgba(0,0,0,.05)}.aef-foot{background:rgba(0,0,0,.02);border-color:rgba(0,0,0,.07)}.aef-in{background:#fff;color:#1c1614;border-color:rgba(0,0,0,.12)}.aef-x{color:#888}}'
    );
    els.root = el('div', { 'class': 'aef' });
    els.bub = el('button', { 'class': 'aef-bub', 'aria-label': 'Ouvrir ' + (S.title || 'Aurora') }, '✦');
    els.bub.onclick = function () { S.open ? closePanel() : openPanel(); };
    els.root.appendChild(els.bub);
    document.body.appendChild(els.root);
  }

  function buildPanel() {
    if (els.panel) return;
    els.panel = el('div', { 'class': 'aef-panel', role: 'dialog', 'aria-label': S.title || 'Aurora' });
    var hd = el('div', { 'class': 'aef-hd' });
    els.dot = el('span', { 'class': 'aef-dot off' });
    var titleWrap = el('div', { style: 'flex:1' });
    titleWrap.appendChild(el('div', { 'class': 'aef-ti' }, esc(S.title || 'Assistant Aurora')));
    els.sub = el('div', { 'class': 'aef-sub' }, 'connexion…');
    titleWrap.appendChild(els.sub);
    var x = el('button', { 'class': 'aef-x', 'aria-label': 'Fermer' }, '✕'); x.onclick = closePanel;
    hd.appendChild(els.dot); hd.appendChild(titleWrap); hd.appendChild(x);
    els.body = el('div', { 'class': 'aef-body' });
    els.foot = el('div', { 'class': 'aef-foot' });
    els.in = el('textarea', { 'class': 'aef-in', placeholder: 'Pose ta question… (ou « /3d <description> »)', rows: '1' });
    els.in.addEventListener('input', function () { els.in.style.height = '38px'; els.in.style.height = Math.min(110, els.in.scrollHeight) + 'px'; });
    els.in.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSend(); } });
    els.send = el('button', { 'class': 'aef-send' }, 'Envoyer'); els.send.onclick = doSend;
    els.foot.appendChild(els.in); els.foot.appendChild(els.send);
    els.panel.appendChild(hd); els.panel.appendChild(els.body); els.panel.appendChild(els.foot);
    els.root.appendChild(els.panel);
    addMsg('sys', S.title ? ('« ' + S.title + ' » — IA locale Aurora') : 'IA locale Aurora');
    pingHealth();
  }

  function addMsg(kind, text) {
    var m = el('div', { 'class': 'aef-msg ' + kind });
    if (kind === 'a') {
      // markdown très léger : **gras**, `code`, liens
      var h = esc(text).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/(https?:\/\/[^\s)]+)(?![^<]*>)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
      m.innerHTML = h;
    } else { m.textContent = text; }
    els.body.appendChild(m);
    els.body.scrollTop = els.body.scrollHeight;
    return m;
  }
  function typing(on) {
    if (on) { if (els.typ) return; els.typ = el('div', { 'class': 'aef-typ' }, '<i></i><i></i><i></i>'); els.body.appendChild(els.typ); els.body.scrollTop = els.body.scrollHeight; }
    else { if (els.typ) { els.typ.remove(); els.typ = null; } }
  }
  function setHealth(ok, txt) { if (els.dot) els.dot.className = 'aef-dot' + (ok ? '' : ' off'); if (els.sub) els.sub.textContent = txt; }

  function api(path, opts) {
    opts = opts || {};
    return fetch(S.url.replace(/\/+$/, '') + path, {
      method: opts.method || 'GET',
      headers: Object.assign({ 'Authorization': 'Bearer ' + S.key }, opts.body ? { 'Content-Type': 'application/json' } : {}),
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then(function (r) { return r.json().then(function (j) { return { status: r.status, ok: r.ok, json: j }; }).catch(function () { return { status: r.status, ok: r.ok, json: {} }; }); });
  }

  function pingHealth() {
    api('/api/ext/ping').then(function (r) {
      if (r.ok && r.json.ok) setHealth(true, 'en ligne · ' + (r.json.model || 'modèle local'));
      else setHealth(false, (r.json && r.json.error) || 'hors ligne');
    }).catch(function () { setHealth(false, 'hors ligne'); });
  }

  function doSend() {
    var txt = (els.in.value || '').trim();
    if (!txt) return;
    els.in.value = ''; els.in.style.height = '38px';
    var m3 = txt.match(/^\/3d\s+([\s\S]+)/i);
    if (m3) { addMsg('u', txt); return generate3D(m3[1].trim()); }
    addMsg('u', txt);
    S.history.push({ role: 'user', content: txt });
    els.send.disabled = true; typing(true);
    api('/api/ext/chat', { method: 'POST', body: { messages: S.history.slice(-20) } }).then(function (r) {
      typing(false); els.send.disabled = false;
      if (r.ok && r.json.reply) { addMsg('a', r.json.reply); S.history.push({ role: 'assistant', content: r.json.reply }); }
      else { addMsg('sys', '⚠ ' + ((r.json && r.json.error) || ('erreur ' + r.status))); }
      pingHealth();
    }).catch(function (e) { typing(false); els.send.disabled = false; addMsg('sys', '⚠ ' + e); });
  }

  function generate3D(prompt, onUpdate) {
    if (!prompt) return;
    var pm = addMsg('a', '◇ Génération 3D lancée — pipeline FLUX → Hunyuan3D → rescue. Ça prend plusieurs minutes (priorité au rendu, pas à la vitesse)…');
    api('/api/ext/3d/generate', { method: 'POST', body: { prompt: prompt } }).then(function (r) {
      if (!r.ok || !r.json.job_id) { pm.textContent = '⚠ ' + ((r.json && r.json.error) || ('erreur ' + r.status)); return; }
      var jid = r.json.job_id, t0 = Date.now();
      (function poll() {
        api('/api/ext/3d/status/' + jid).then(function (s) {
          var j = s.json || {};
          var el2 = j.elapsed_s != null ? j.elapsed_s : ((Date.now() - t0) / 1000).toFixed(1);
          if (onUpdate) try { onUpdate(j); } catch (_) {}
          if (j.state === 'done') {
            var url = S.url.replace(/\/+$/, '') + j.glb_url;
            pm.innerHTML = '◇ GLB prêt en ' + el2 + 's' + (j.score != null ? ' · score ' + j.score : '') + ' :<br><a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(url) + '</a><br><span style="opacity:.6;font-size:12px">→ charge-le dans le viewer de ton site</span>';
            window.dispatchEvent(new CustomEvent('aurora-embed:3d-ready', { detail: { url: url, audit: j.audit, prompt: prompt } }));
          } else if (j.state === 'failed') {
            pm.textContent = '⚠ rendu rejeté : ' + (j.error || 'échec') + (j.glb_url ? ' — GLB brut: ' + S.url.replace(/\/+$/, '') + j.glb_url : '');
          } else {
            pm.textContent = '◇ ' + (j.step || 'en cours') + '… ' + el2 + 's' + (j.attempts > 1 ? ' (passe ' + j.attempts + ')' : '');
            setTimeout(poll, 5000);
          }
        }).catch(function () { setTimeout(poll, 6000); });
      })();
    }).catch(function (e) { pm.textContent = '⚠ ' + e; });
  }

  function openPanel() { buildPanel(); els.panel.style.display = 'flex'; S.open = true; els.bub.textContent = '✕'; setTimeout(function () { els.in && els.in.focus(); }, 50); }
  function closePanel() { if (els.panel) els.panel.style.display = 'none'; S.open = false; els.bub.textContent = '✦'; }

  function init(opts) {
    opts = opts || {};
    S.url = (opts.url || S.url || '').replace(/\/+$/, '');
    S.key = opts.key || S.key || '';
    S.title = opts.title || S.title || 'Assistant';
    S.accent = opts.accent || S.accent || '#d97757';
    S.history = S.history || [];
    if (!S.url || !S.key) { console.warn('[AuroraEmbed] url et key requis (data-aurora-url / data-aurora-key)'); return window.AuroraEmbed; }
    mountUI();
    return window.AuroraEmbed;
  }

  window.AuroraEmbed = {
    __mounted: true,
    init: init,
    open: openPanel, close: closePanel,
    ask: function (t) { buildPanel(); openPanel(); els.in.value = t; doSend(); },
    generate3D: generate3D,
  };

  // Auto-init depuis l'attribut du <script> qui nous a chargés.
  try {
    var cur = document.currentScript || (function () { var ss = document.getElementsByTagName('script'); return ss[ss.length - 1]; })();
    if (cur && cur.getAttribute('data-aurora-url') && cur.getAttribute('data-aurora-key')) {
      init({
        url: cur.getAttribute('data-aurora-url'),
        key: cur.getAttribute('data-aurora-key'),
        title: cur.getAttribute('data-aurora-title') || undefined,
        accent: cur.getAttribute('data-aurora-accent') || undefined,
      });
    }
  } catch (_) {}
})();
