"""Fetch Aurora v10 files from Claude Design via CDP over the user's running Chrome."""
import json, time, urllib.request, websocket, sys, os, base64

BASE = 'http://localhost:9222'
PROJECT = '019e08a9-fa5b-7b07-a99b-4c1959f1f99d'
SERVE_BASE = f'https://{PROJECT}.claudeusercontent.com/v1/design/projects/{PROJECT}/serve'
FILES = ['Aurora_v10.html', 'design-canvas.jsx', 'v10/avatars.jsx', 'v10/scenes-1.jsx', 'v10/scenes-2.jsx', 'v10/scenes-3.jsx']
OUT_DIR = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10'

# 1. Find the design tab
tabs = json.load(urllib.request.urlopen(f'{BASE}/json'))
design = next((t for t in tabs if 'Aurora_v10' in t.get('url','')), None)
if not design:
    design = next((t for t in tabs if 'claude.ai/design' in t.get('url','')), None)
if not design:
    print('NO DESIGN TAB'); sys.exit(1)
print(f'tab: {design["url"]}')
ws_url = design['webSocketDebuggerUrl']

# 2. Open WS, send commands
ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
mid = [0]
def send(method, params=None):
    mid[0] += 1
    msg = {'id': mid[0], 'method': method}
    if params is not None: msg['params'] = params
    ws.send(json.dumps(msg))
    while True:
        resp = json.loads(ws.recv())
        if resp.get('id') == mid[0]:
            if 'error' in resp: raise RuntimeError(resp['error'])
            return resp.get('result', {})

send('Runtime.enable')

# 3. Navigate to design page with file=Aurora_v10.html and present=1 to trigger iframe + token
send('Page.enable')

# 4. Trick: do an in-page fetch using the current cookies. Run JS that reads
# __Host-omelette-preview from the standalone domain via a hidden iframe or by
# postMessage-trick. Simpler: navigate the design page's iframe directly via JS,
# wait for the cookie to be set, then fetch each file from JS using the cookie.
JS_FETCH = r'''
(async () => {
  const PROJECT = '%s';
  const FILES = %s;
  const SERVE = `https://${PROJECT}.claudeusercontent.com/v1/design/projects/${PROJECT}/serve`;

  // Find the standalone iframe (it has the cookie set via postMessage from parent)
  let iframe = Array.from(document.querySelectorAll('iframe')).find(f => /claudeusercontent\.com/.test(f.src||''));
  if (!iframe) {
    // Click "Present" to load it
    const btn = Array.from(document.querySelectorAll('button')).find(b => /^present\b/i.test((b.textContent||'').trim()));
    if (btn) btn.click();
    await new Promise(r => setTimeout(r, 4000));
    iframe = Array.from(document.querySelectorAll('iframe')).find(f => /claudeusercontent\.com\/v1\/design/.test(f.src||''));
  }
  if (!iframe) return {error: 'no iframe with serve URL'};

  // Wait for load
  for (let i=0;i<20;i++){
    try { if (iframe.contentWindow && iframe.contentDocument && iframe.contentDocument.readyState === 'complete') break; } catch(e){}
    await new Promise(r => setTimeout(r, 500));
  }

  // Read cookie from inside iframe (cross-origin throws; instead reuse postMessage to get cookie)
  // Simplest: call a fetch from inside iframe via postMessage RPC. But cross-origin DOM access blocked.
  // Workaround: extract the iframe.src token (?t=...) by reading the bootstrap response or cookies.
  // The cookie __Host-omelette-preview is set on the claudeusercontent.com domain — same as iframe.
  // A fetch from THIS top page won't have those cookies. So we must inject a fetch INSIDE the iframe.
  // Trick: claudeusercontent.com pages enable window.claude.complete + window.omelette.writeFile;
  // we postMessage('omelette-eval-rpc') if the host bootstrap supports it.
  // Looking at the bootstrap code earlier, there's a 'message' handler that handles `__om_eval` —
  // any iframe registered handlers for J.__om_eval. Let's call it.
  const out = {};
  for (const path of FILES) {
    const url = `${SERVE}/${path}`;
    // Try via iframe.contentWindow.postMessage to invoke __om_eval that runs fetch inside iframe
    const id = `f_${Math.random().toString(36).slice(2,9)}`;
    const code = `(async()=>{const r=await fetch(${JSON.stringify(url)},{credentials:'include'});return {ok:r.ok,status:r.status,text:await r.text()};})()`;
    const result = await new Promise(resolve => {
      const handler = (e) => {
        if (e.data && e.data.__om_eval_r && e.data.id === id) {
          window.removeEventListener('message', handler);
          resolve({ok: e.data.ok, v: e.data.v, e: e.data.e});
        }
      };
      window.addEventListener('message', handler);
      iframe.contentWindow.postMessage({__om_eval: 1, id, code}, '*');
      setTimeout(() => { window.removeEventListener('message', handler); resolve({timeout: true}); }, 8000);
    });
    if (result.timeout) { out[path] = {error: 'timeout'}; continue; }
    try {
      const parsed = JSON.parse(result.v);
      out[path] = {ok: parsed.ok, status: parsed.status, len: (parsed.text||'').length, text_b64: btoa(unescape(encodeURIComponent(parsed.text||'')))};
    } catch (e) {
      out[path] = {raw_error: result.e || result.v};
    }
  }
  return out;
})()
''' % (PROJECT, json.dumps(FILES))

print('running in-page fetch...')
res = send('Runtime.evaluate', {'expression': JS_FETCH, 'awaitPromise': True, 'returnByValue': True})
val = res.get('result', {}).get('value')
if not val:
    print('NO RESULT'); print(res); sys.exit(2)

print('files received:')
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, 'v10'), exist_ok=True)
for path, info in val.items():
    if 'text_b64' in info:
        data = base64.b64decode(info['text_b64'])
        out_path = os.path.join(OUT_DIR, path.replace('/', os.sep))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f: f.write(data)
        print(f'  OK {path:40s} {len(data)} bytes -> {out_path}')
    else:
        print(f'  ERR {path}: {info}')

ws.close()
print('done')
