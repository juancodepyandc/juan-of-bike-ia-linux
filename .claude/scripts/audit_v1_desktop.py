"""iter8: aurora_v1 desktop — screenshot a few modules, check layout (no cut/void), sidebar switching works."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'
os.makedirs(OUT, exist_ok=True)
BUILD='v82s-studio9'
MODULES = [('conversation','Conversation⌘1'),('image','Image'),('code','Code'),('learning','Académie'),('3d','3D'),('cyber','Cyber'),('drawing','Dessin'),('video','Vidéo')]
r = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(TUNNEL+"/", safe=":/?=&")}', method='PUT')
new_tab = json.load(urllib.request.urlopen(r))
ws = websocket.create_connection(new_tab['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
mid=[0]
def cmd(m,p=None):
    mid[0]+=1; msg={'id':mid[0],'method':m}
    if p is not None: msg['params']=p
    ws.send(json.dumps(msg))
    while True:
        rr=json.loads(ws.recv())
        if rr.get('id')==mid[0]: return rr.get('result',{}) if 'error' not in rr else {'__err':rr['error']}
cmd('Page.enable'); cmd('Runtime.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':1440,'height':900,'deviceScaleFactor':1,'mobile':False})
cmd('Runtime.evaluate', {'expression': f'''(()=>{{try{{localStorage.clear();localStorage.setItem('aurora-ui-skin','aurora_v1');localStorage.setItem('aurora_build_id_html','{BUILD}');}}catch(_){{}}}}'''+'})()'})
cmd('Page.reload'); time.sleep(11)
for mid_id, label in MODULES:
    sw = cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      const b=Array.from(document.querySelectorAll('button')).find(b=>(b.textContent||'').replace(/\\s+/g,'').includes({json.dumps(label.replace(' ',''))}));
      if(b){{b.click();return 'clicked'}} return 'miss'
    }})()''', 'returnByValue':True}).get('result',{}).get('value')
    time.sleep(3.2)
    probe = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const vh=window.innerHeight, vw=window.innerWidth;
      // bottom band sample
      const bgs=new Set(); for(let y=vh-6;y>vh-120;y-=20){const el=document.elementFromPoint(vw/2,y);if(el)bgs.add(getComputedStyle(el).backgroundColor);}
      // pure black void check
      const blackVoid = [...bgs].some(c=>c==='rgb(0, 0, 0)'||c==='rgba(0, 0, 0, 1)');
      const errs=(window.__auroraErr||[]).slice(0,3);
      const bodyLen=document.body.innerText.length;
      return {bottomBgs:[...bgs], blackVoid, bodyLen};
    })()''', 'returnByValue':True}).get('result',{}).get('value',{})
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':68})
    if shot and 'data' in shot: open(os.path.join(OUT,f'v1desk_{mid_id}.jpeg'),'wb').write(base64.b64decode(shot['data']))
    print(f'{mid_id:14s} sw={sw} bodyLen={probe.get("bodyLen")} blackVoid={probe.get("blackVoid")} bottomBgs={probe.get("bottomBgs")}')
cmd('Page.close'); ws.close()
print('OK')
