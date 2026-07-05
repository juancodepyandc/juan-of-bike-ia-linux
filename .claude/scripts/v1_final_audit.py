"""V1 desktop audit with corrected selector + screenshots per module."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'

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
            if 'error' in r: return {'__err':r['error']}
            return r.get('result',{})

cmd('Page.enable'); cmd('Runtime.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.setItem('aurora-ui-skin','aurora_v1');localStorage.removeItem('ft-grimoire-page');}catch(_){}})()'''})
cmd('Page.reload'); time.sleep(8)

modules = [
    ('conversation','Conversation⌘1'),('image','Image⌘2'),('code','Code⌘3'),
    ('video','Vidéo⌘4'),('drawing','Dessin⌘5'),('3d','3D⌘6'),
    ('learning','Academy⌘8'),('cyber','Cyber⌘7'),
]

print('=== V1 desktop FINAL audit ===')
results = {}
for mod_id, fragment in modules:
    click = cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      const els=Array.from(document.querySelectorAll('button'));
      const want={json.dumps(fragment)};
      const el=els.find(b=>(b.textContent||'').includes(want));
      if(el){{el.click();return 'OK '+want}}
      return 'MISS '+want;
    }})()''', 'returnByValue':True})
    print(f'  {click.get("result",{}).get("value")}')
    time.sleep(2.5)
    info = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const ls=localStorage.getItem('juan-bike-app-store')||'';
      const m=ls.match(/"activeModule":"([^"]+)"/);
      const text=document.body.innerText;
      const errOverlay=/a bloque/.test(text);
      return {active: m && m[1], bodyLen:text.length, hasErr:errOverlay};
    })()''', 'returnByValue':True})
    val = info.get('result',{}).get('value',{})
    err = ' [CRASH]' if val.get('hasErr') else ''
    print(f'    active={val.get("active")} bodyLen={val.get("bodyLen")}{err}')
    results[mod_id] = val
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':70})
    if shot and 'data' in shot:
        open(os.path.join(OUT, f'v1_desktop_{mod_id}.jpeg'),'wb').write(base64.b64decode(shot['data']))

cmd('Page.close'); ws.close()

print('\nSummary:')
for k,v in results.items():
    err = ' CRASH' if v.get('hasErr') else ''
    print(f'  {k:14} active={v.get("active"):14} bodyLen={v.get("bodyLen")}{err}')
