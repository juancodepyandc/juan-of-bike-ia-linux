"""Smoke-test: open tunnel in Chrome via CDP, emulate iPhone, navigate to L'ÉQUIPE
page (mobile grimoire 'team' page), screenshot, audit DOM."""
import json, urllib.request, websocket, base64, sys, time, urllib.parse, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT_HOME = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\mobile_home.jpeg'
OUT_TEAM = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\mobile_team.jpeg'

print(f'tunnel: {TUNNEL}')

# Open new tab via /json/new (PUT required by recent Chrome).
# Force mobile shell with `?device=mobile` query (handled by utils/device.ts).
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
            if 'error' in r: print(f'ERR {m}:', r['error']); return None
            return r.get('result',{})

cmd('Page.enable')
cmd('Runtime.enable')
cmd('Network.enable')
cmd('Network.clearBrowserCache')
# iPhone 13 Pro emulation
cmd('Emulation.setDeviceMetricsOverride', {
    'width': 390, 'height': 844, 'deviceScaleFactor': 3,
    'mobile': True, 'screenWidth': 390, 'screenHeight': 844
})
cmd('Emulation.setTouchEmulationEnabled', {'enabled': True})
cmd('Emulation.setUserAgentOverride', {'userAgent':
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'})

# Wait for app to mount
time.sleep(9)
# v82: we need data-ui-skin set via localStorage to manga to get MobileGrimoire mounted.
# Or we accept aurora_v1 default (set by inline boot script) and the app may render an
# AuroraV1MobileShell instead of MobileGrimoire. Let's see what's currently rendered.
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':82,'captureBeyondViewport':False})
if shot: open(OUT_HOME,'wb').write(base64.b64decode(shot['data'])); print(f'home shot: {OUT_HOME}')

# Inspect what's on screen — find the grimoire spine nav or page nav
inspect = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const skin = document.documentElement.getAttribute('data-ui-skin');
  const teamCard = Array.from(document.querySelectorAll('button')).find(b=>/équipe|equipe/i.test(b.textContent||''));
  const allCards = Array.from(document.querySelectorAll('button')).filter(b=>/Chat|Image|Académie|Code|Vidéo|Dessin|3D|Cyber|équipe/i.test(b.textContent||'')).map(b=>(b.textContent||'').replace(/\s+/g,' ').trim().slice(0,30));
  return {skin, hasTeamCard: !!teamCard, cards: allCards, bodyLen: document.body.innerText.length};
})()''', 'returnByValue': True})
print('inspect cover:', json.dumps(inspect.get('result',{}).get('value',{}), ensure_ascii=False, indent=2))

# Tap the L'équipe card
tapped = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const teamBtn = Array.from(document.querySelectorAll('button')).find(b=>/équipe|equipe/i.test(b.textContent||''));
  if (teamBtn) { teamBtn.click(); return {tapped:true}; }
  return {tapped:false};
})()''', 'returnByValue': True})
print('tap team:', tapped.get('result',{}).get('value'))
time.sleep(3)

shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':82,'captureBeyondViewport':False})
if shot: open(OUT_TEAM,'wb').write(base64.b64decode(shot['data'])); print(f'team shot: {OUT_TEAM}')

audit = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const personaBtns = Array.from(document.querySelectorAll('button')).filter(b=>/^(Sage|Lou|Mira|Diego|Tess|Sam|Yann)/.test((b.textContent||'').trim()));
  const svgs = document.querySelectorAll('svg').length;
  const paths = document.querySelectorAll('path').length;
  const hasKeyframes = !!document.getElementById('a10-keyframes');
  const headerH1 = (document.querySelector('h1')||{}).textContent || '';
  return {headerH1, personaBtns: personaBtns.length,
          personaLabels: personaBtns.map(b=>(b.textContent||'').replace(/\s+/g,' ').trim().slice(0,40)),
          svgs, paths, hasKeyframes};
})()''', 'returnByValue': True})
print('team audit:', json.dumps(audit.get('result',{}).get('value',{}), ensure_ascii=False, indent=2))

# If aurora_v1 skin is active, MobileGrimoire isn't shown. Switch to manga.
cmd('Runtime.evaluate', {'expression': r'''(()=>{
  try { localStorage.setItem('aurora-ui-skin','manga'); } catch(_){}
  document.documentElement.setAttribute('data-ui-skin','manga');
  return 'switched to manga skin, reloading...';
})()'''})
time.sleep(0.5)
cmd('Page.reload')
time.sleep(8)

inspect2 = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const skin = document.documentElement.getAttribute('data-ui-skin');
  const isMobileGrimoire = !!document.querySelector('.g-root');
  const chapters = Array.from(document.querySelectorAll('.chapter')).map(e=>e.textContent.trim());
  return {skin, isMobileGrimoire, chapters};
})()''', 'returnByValue': True})
print('after reload:', json.dumps(inspect2.get('result',{}).get('value',{}), ensure_ascii=False))

# Snap home
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':82,'captureBeyondViewport':False})
if shot: open(OUT_HOME,'wb').write(base64.b64decode(shot['data'])); print(f'home reload: {OUT_HOME}')

# Force navigation to team page by setting localStorage + reloading
cmd('Runtime.evaluate', {'expression': r'''(()=>{
  try { localStorage.setItem('ft-grimoire-page','1'); } catch(_){}
  return 'set ft-grimoire-page=1';
})()'''})
time.sleep(0.3)
cmd('Page.reload')
time.sleep(7)

# Wait for team page render — give SVG time to inject keyframes + animate
time.sleep(2)

shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':82,'captureBeyondViewport':False})
if shot: open(OUT_TEAM,'wb').write(base64.b64decode(shot['data'])); print(f'team shot: {OUT_TEAM}')

audit = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const personas = Array.from(document.querySelectorAll('button')).filter(b=>/Sage|Lou|Mira|Diego|Tess|Sam|Yann/.test(b.textContent||''));
  const svgs = document.querySelectorAll('svg').length;
  const paths = document.querySelectorAll('path').length;
  const hasKeyframes = !!document.getElementById('a10-keyframes');
  const chapter = (document.querySelector('.chapter')||{}).textContent || '';
  const visible = Array.from(document.querySelectorAll('h1')).map(h=>h.textContent.trim());
  return {chapter, personas: personas.length, svgs, paths, hasKeyframes, visibleH1: visible};
})()''', 'returnByValue': True})
print('team audit:', json.dumps(audit.get('result',{}).get('value',{}), ensure_ascii=False, indent=2))

# Cleanup tab
cmd('Page.close')
ws.close()
print('done')
