"""Test v3 mobile shell → tap card → MobileGrimoire team page."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
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
cmd('Page.enable'); cmd('Runtime.enable'); cmd('Network.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':3,'mobile':True})
cmd('Emulation.setTouchEmulationEnabled', {'enabled':True})

# Force aurora_v3 skin + ft-grimoire-page=1 to reproduce user state
cmd('Runtime.evaluate', {'expression': r'''(()=>{
  try {
    localStorage.setItem('aurora-ui-skin','aurora_v3');
    localStorage.setItem('ft-grimoire-page','1');
  } catch(_){}
  return 'set';
})()'''})
cmd('Page.reload')
time.sleep(8)

# Snap cover (v3)
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':80})
open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\v3_cover.jpeg','wb').write(base64.b64decode(shot['data']))

# Tap any v3 card to trigger setLive(true) → MobileGrimoire
tap = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const card = Array.from(document.querySelectorAll('button')).find(b=>/MISSION CTRL|DICTAPHONE|STUDIO|CODEX|polyphonie/i.test(b.textContent||''));
  if (card) { card.click(); return 'tapped: ' + (card.textContent||'').slice(0,30); }
  return 'no card';
})()''', 'returnByValue': True})
print('TAP:', tap.get('result',{}).get('value'))

# Wait long enough for chunk + render
for i in range(15):
    time.sleep(1)
    state = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const fb = Array.from(document.querySelectorAll('*')).find(e=>(e.textContent||'').match(/POLYPHONIE · LOAD|L'équipe se réveille|chargement/i));
      const grim = !!document.querySelector('.g-root');
      const team = !!document.querySelector('h1') && /L'équipe/i.test(document.body.innerText);
      const personas = Array.from(document.querySelectorAll('button')).filter(b=>/^(Sage|Lou|Mira|Diego|Tess|Sam|Yann)/.test((b.textContent||'').trim())).length;
      return {grim, team, personas, fbVisible: !!fb && fb.offsetHeight>0, snippet: (fb? (fb.textContent||'').slice(0,60):'')};
    })()''', 'returnByValue': True})
    v = state.get('result',{}).get('value',{})
    print(f't+{i+1}s: grim={v.get("grim")} team={v.get("team")} personas={v.get("personas")} fb=[{v.get("snippet")}]')
    if v.get('personas',0) >= 7: break

# Final shot
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':82})
open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\v3_after_tap.jpeg','wb').write(base64.b64decode(shot['data']))
print('done')
cmd('Page.close'); ws.close()
