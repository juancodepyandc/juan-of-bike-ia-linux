"""Snap v3 cover → tap L'équipe card → studio roster (no MobileGrimoire detour)."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
TARGET = f'{TUNNEL}/?device=mobile'
req = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(TARGET, safe=":/?=&")}', method='PUT')
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
cmd('Page.enable'); cmd('Runtime.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':3,'mobile':True})
cmd('Emulation.setTouchEmulationEnabled', {'enabled':True})

# Force aurora_v3 + reset grimoire page; auto-purge will trigger because BUILD_ID changed
cmd('Runtime.evaluate', {'expression': r'''(()=>{
  try {
    localStorage.setItem('aurora-ui-skin','aurora_v3');
    localStorage.removeItem('ft-grimoire-page');
  } catch(_){}
  return 'set';
})()'''})
cmd('Page.reload')
time.sleep(10)

# v3 cover screenshot
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':82})
open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\v3_cover_with_team.jpeg','wb').write(base64.b64decode(shot['data']))
print('cover snapped')

# Tap L'équipe
tap = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const card = Array.from(document.querySelectorAll('button')).find(b=>/L.ÉQUIPE|L.équipe|7 personae/i.test(b.textContent||''));
  if (card) { card.click(); return 'TAP team'; }
  return 'no team card';
})()''', 'returnByValue': True})
print('tap result:', tap.get('result',{}).get('value'))
time.sleep(4)

# Snap roster
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':82,'captureBeyondViewport':True})
open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\v3_team.jpeg','wb').write(base64.b64decode(shot['data']))
print('team snapped')

audit = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  return {personas: Array.from(document.querySelectorAll('button')).filter(b=>/^(Sage|Lou|Mira|Diego|Tess|Sam|Yann)/.test((b.textContent||'').trim())).length,
          paths: document.querySelectorAll('path').length,
          title: (document.querySelector('h1')||{}).textContent || '',
          buildId: localStorage.getItem('aurora_build_id_html')};
})()''', 'returnByValue': True})
print('audit:', json.dumps(audit.get('result',{}).get('value',{}), ensure_ascii=False))

cmd('Page.close'); ws.close()
