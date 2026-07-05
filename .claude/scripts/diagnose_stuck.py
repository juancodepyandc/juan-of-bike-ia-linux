"""Capture live state + console errors of the app on tunnel."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\stuck.jpeg'
TARGET = f'{TUNNEL}/?device=mobile'

req_url = f'http://localhost:9222/json/new?{urllib.parse.quote(TARGET, safe=":/?=&")}'
req = urllib.request.Request(req_url, method='PUT')
new_tab = json.load(urllib.request.urlopen(req))
ws = websocket.create_connection(new_tab['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
mid=[0]
def cmd(m,p=None):
    mid[0]+=1
    msg={'id':mid[0],'method':m}
    if p is not None: msg['params']=p
    ws.send(json.dumps(msg))
    while True:
        r=json.loads(ws.recv())
        if r.get('id')==mid[0]:
            if 'error' in r: raise RuntimeError(r['error'])
            return r.get('result',{})

cmd('Page.enable'); cmd('Runtime.enable'); cmd('Log.enable'); cmd('Network.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':3,'mobile':True})
cmd('Emulation.setTouchEmulationEnabled', {'enabled':True})
cmd('Emulation.setUserAgentOverride', {'userAgent':'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'})

# Buffer console messages
console_msgs = []
def listen_console():
    pass

# Wait for app load
time.sleep(8)

# Listen for console + log messages briefly
ws.settimeout(0.05)
seen = []
end = time.time()+2
while time.time()<end:
    try:
        m = ws.recv()
        if not m: continue
        d = json.loads(m)
        if d.get('method') in ('Runtime.consoleAPICalled', 'Log.entryAdded', 'Runtime.exceptionThrown'):
            seen.append({'method': d['method'], 'data': d.get('params',{})})
    except websocket.WebSocketTimeoutException:
        time.sleep(0.05)
ws.settimeout(None)

# Inspect current state
state = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const url = location.href;
  const skin = document.documentElement.getAttribute('data-ui-skin');
  const ls = {};
  try { for (let i=0;i<localStorage.length;i++){const k=localStorage.key(i); ls[k]=localStorage.getItem(k).slice(0,80)} } catch(e){}
  const overlays = Array.from(document.querySelectorAll('[role="dialog"], .overlay, [class*=spinner], [class*=loading]')).map(e=>({tag:e.tagName,cls:(e.className||'').toString().slice(0,80),text:(e.textContent||'').slice(0,60)}));
  const bodyTop = document.body.innerText.slice(0, 500);
  const isStuck = /chargement|loading|réveille|grimoire s'ouvre/i.test(bodyTop);
  const moduleViewMounted = !!document.querySelector('[data-module],[class*=module-view]');
  return {url, skin, ls, overlays, bodyTopChars: bodyTop.length, snippet: bodyTop.slice(0, 220), isStuck, moduleViewMounted};
})()''', 'returnByValue': True})
print('STATE:', json.dumps(state.get('result',{}).get('value',{}), ensure_ascii=False, indent=2))

print('\nCONSOLE MESSAGES:')
for m in seen[-20:]:
    method = m['method']
    p = m['data']
    if method == 'Runtime.consoleAPICalled':
        args = ' '.join((a.get('value') or a.get('description','?'))[:120] if isinstance(a, dict) else str(a) for a in (p.get('args') or []))
        print(f'  [{p.get("type","log")}] {args[:200]}')
    elif method == 'Log.entryAdded':
        e = p.get('entry',{})
        print(f'  [{e.get("level","log")}] {e.get("text","")[:200]} @ {e.get("url","")}')
    elif method == 'Runtime.exceptionThrown':
        ex = p.get('exceptionDetails',{})
        print(f'  [EXCEPTION] {ex.get("text","")} {ex.get("exception",{}).get("description","")[:300]}')

# Capture screenshot
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':82,'captureBeyondViewport':False})
data = base64.b64decode(shot['data'])
open(OUT,'wb').write(data)
print(f'\nshot: {OUT} ({len(data)} bytes)')

cmd('Page.close'); ws.close()
