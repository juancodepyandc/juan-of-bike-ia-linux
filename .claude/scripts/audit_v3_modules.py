"""Audit each module under aurora_v3 desktop — capture what breaks."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10'

MODULES = ['conversation','image','code','video','drawing','3d','learning','cyber']

req = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(TUNNEL, safe=":/")}', method='PUT')
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

cmd('Page.enable'); cmd('Runtime.enable'); cmd('Log.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
cmd('Runtime.evaluate', {'expression': '''(()=>{
  try { localStorage.setItem('aurora-ui-skin','aurora_v3'); } catch(_){}
})()'''})
cmd('Page.reload')
time.sleep(8)

for mod in MODULES:
    cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      // Click dock button to switch module
      const btns = Array.from(document.querySelectorAll('.aurora-v3-dock-btn,button'));
      const wanted = btns.find(b=>{{const t=(b.textContent||'').toLowerCase();return t.includes('{mod[0:4]}')||t.includes('{mod}')}});
      if (wanted) {{ wanted.click(); return 'clicked-{mod}'; }}
      return 'no-button-{mod}';
    }})()'''})
    time.sleep(2.5)
    state = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const am = (window.__APP_STORE && window.__APP_STORE.getState) ? window.__APP_STORE.getState().activeModule : null;
      const ls = localStorage.getItem('juan-bike-app-store') || '';
      const m = ls.match(/"activeModule":"(\w+)"/);
      const ramp = (document.querySelector('.aurora-v3-module')||{}).getBoundingClientRect ? (document.querySelector('.aurora-v3-module')).getBoundingClientRect() : null;
      const scene = (document.querySelector('.aurora-v3-scene')||{}).getBoundingClientRect ? (document.querySelector('.aurora-v3-scene')).getBoundingClientRect() : null;
      return {activeModule: m && m[1], moduleRect: ramp && {h: Math.round(ramp.height), w: Math.round(ramp.width)}, sceneRect: scene && {h: Math.round(scene.height), w: Math.round(scene.width)}, bodyLen: document.body.innerText.length};
    })()''', 'returnByValue': True})
    val = state.get('result',{}).get('value',{})
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':75})
    out_path = os.path.join(OUT, f'v3_{mod}.jpeg')
    open(out_path,'wb').write(base64.b64decode(shot['data']))
    print(f'{mod:12} active={val.get("activeModule")} module={val.get("moduleRect")} scene={val.get("sceneRect")} body={val.get("bodyLen")}')

cmd('Page.close'); ws.close()
