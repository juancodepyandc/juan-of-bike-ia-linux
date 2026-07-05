"""Capture full-page screenshot of v10 standalone via CDP."""
import json, urllib.request, websocket, base64, sys, time

BASE = 'http://localhost:9222'
PROJECT = '019e08a9-fa5b-7b07-a99b-4c1959f1f99d'
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\v10_render.jpeg'

tabs = json.load(urllib.request.urlopen(f'{BASE}/json'))
design = next((t for t in tabs if 'Aurora_v10' in t.get('url','')), None) or next((t for t in tabs if 'claude.ai/design' in t.get('url','')), None)
if not design: print('no tab'); sys.exit(1)
ws = websocket.create_connection(design['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
mid=[0]
def s(m,p=None):
    mid[0]+=1
    msg={'id':mid[0],'method':m}
    if p is not None: msg['params']=p
    ws.send(json.dumps(msg))
    while True:
        r=json.loads(ws.recv())
        if r.get('id')==mid[0]:
            if 'error' in r: raise RuntimeError(r['error'])
            return r.get('result',{})

# Find iframe with v10
JS_FRAME = r'''(() => {
  const f = Array.from(document.querySelectorAll('iframe')).find(x => /claudeusercontent\.com\/v1\/design\/projects.*serve\/Aurora_v10/.test(x.src||''));
  if (!f) {
    const present = Array.from(document.querySelectorAll('button')).find(b => /^present\b/i.test((b.textContent||'').trim()));
    if (present) present.click();
    return {needWait: true};
  }
  return {src: f.src, hasFrame: true};
})()'''

r = s('Runtime.evaluate', {'expression': JS_FRAME, 'returnByValue': True})
v = r.get('result',{}).get('value',{})
if v.get('needWait'):
    time.sleep(5)

# Now find frame target via Page.getFrameTree
ft = s('Page.getFrameTree')
def walk(node, out):
    out.append(node['frame'])
    for c in node.get('childFrames', []) or []: walk(c, out)
frames=[]; walk(ft['frameTree'], frames)
target = next((f for f in frames if 'serve/Aurora_v10' in (f.get('url','') or '')), None)
if not target:
    target = next((f for f in frames if 'claudeusercontent.com' in (f.get('url','') or '') and 'serve' in f.get('url','')), None)
if not target:
    print('no v10 frame; available:', [f.get('url','')[:120] for f in frames])
    sys.exit(2)
print('target frame:', target['url'][:120])

# Capture screenshot of full doc — top page only since cross-frame capture is tricky.
# Instead: navigate top page to standalone v10 url with cookies. Get cookies from main browser.
# Workaround: use Page.captureScreenshot at top level and rely on fullPage clip.
# Better: switch to that frame's session via Target.attachToTarget if it has its own target.
sess = s('Target.attachToTarget', {'targetId': target['id'], 'flatten': True}) if target.get('targetId') else None
print('sess:', sess)

# Capture full page from main page
shot = s('Page.captureScreenshot', {'format':'jpeg','quality':80,'captureBeyondViewport':True})
data = base64.b64decode(shot['data'])
with open(OUT, 'wb') as f: f.write(data)
print(f'screenshot {len(data)} bytes -> {OUT}')
ws.close()
