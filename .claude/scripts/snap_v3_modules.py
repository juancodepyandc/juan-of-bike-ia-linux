"""Snap each v3 module to confirm no cream cut + module fills properly."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10'

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

cmd('Page.enable'); cmd('Runtime.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
cmd('Runtime.evaluate', {'expression': '''(()=>{
  try { localStorage.setItem('aurora-ui-skin','aurora_v3'); } catch(_){}
})()'''})
cmd('Page.reload')
time.sleep(8)

# Use the dock buttons by class .aurora-v3-dock-btn
modules = [
    ('conversation','Chat'),('image','Image'),('video','Vidéo'),('code','Code'),
    ('drawing','Dessin'),('3d','3D'),('learning','Academy'),('cyber','Cyber'),
]
for mod_id, label in modules:
    res = cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      const btn = Array.from(document.querySelectorAll('.aurora-v3-dock-btn,button')).find(b=>{{
        const lbl = (b.querySelector('.aurora-v3-dock-label')||b).textContent||'';
        return lbl.trim() === {json.dumps(label)};
      }});
      if (btn) {{ btn.click(); return 'click ' + {json.dumps(label)}; }}
      return 'miss ' + {json.dumps(label)};
    }})()''', 'returnByValue': True})
    print(res.get('result',{}).get('value'))
    time.sleep(2.2)
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':75})
    out_path = os.path.join(OUT, f'v3_{mod_id}_clean.jpeg')
    open(out_path,'wb').write(base64.b64decode(shot['data']))
    print(f'  {out_path}')

cmd('Page.close'); ws.close()
