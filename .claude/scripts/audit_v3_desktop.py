"""iter7 audit: aurora_v3 desktop — screenshot each module, detect 'cut'/black-void layout bugs."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'
os.makedirs(OUT, exist_ok=True)

MODULES = ['conversation','image','code','video','drawing','3d','learning','cyber']
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
cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.clear();localStorage.setItem('aurora-ui-skin','aurora_v3');localStorage.setItem('aurora_build_id_html','v82s-studio7');localStorage.setItem('juan-bike-app-store',JSON.stringify({state:{activeModule:'conversation'},version:0}));}catch(_){}})()'''})
cmd('Page.reload'); time.sleep(11)

for m in MODULES:
    # switch module via app store
    cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      try {{
        // try to find the v3 dock button for this module, else mutate store
        const ev=new CustomEvent('aurora-set-module',{{detail:'{m}'}});window.dispatchEvent(ev);
      }} catch(_){{}}
      // hard fallback: write to localStorage + reload would be too slow; just try store
    }})()'''})
    # Use a more reliable switch: click v3 floating dock if present, else navigate URL
    sw = cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      const labels={{conversation:'chat',image:'image',code:'code',video:'vidéo|video',drawing:'dessin|draw|atelier','3d':'3d|model',learning:'académie|academy|learn',cyber:'cyber'}};
      const rx=new RegExp(labels['{m}'],'i');
      const b=Array.from(document.querySelectorAll('button,a')).find(b=>rx.test((b.textContent||'')+(b.getAttribute('aria-label')||'')+(b.title||'')) && (b.textContent||'').length<24);
      if(b){{b.click();return 'clicked '+(b.textContent||b.getAttribute('aria-label')||'').slice(0,20)}}
      return 'no-btn'
    }})()''', 'returnByValue':True}).get('result',{}).get('value')
    time.sleep(3.5)
    probe = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const vh=window.innerHeight, vw=window.innerWidth;
      // sample column of pixels via elementFromPoint at bottom band
      const samples=[];
      for(let y=vh-8; y>vh-180; y-=24){
        const el=document.elementFromPoint(vw/2,y);
        const cs=el?getComputedStyle(el):null;
        samples.push({y, tag:el?el.tagName:'?', bg: cs?cs.backgroundColor:'?'});
      }
      // distinct bg colors in bottom band
      const bgs=[...new Set(samples.map(s=>s.bg))];
      // does any element fill the viewport height?
      const main=document.querySelector('.aurora-v3-module,[class*="v3"],main,#root>div');
      const r=main?main.getBoundingClientRect():null;
      return {bottomBgs:bgs, bottomSamples:samples.slice(0,4), mainH:r?Math.round(r.height):0, vh, fillsViewport: r? r.height>=vh-4 : false};
    })()''', 'returnByValue':True}).get('result',{}).get('value',{})
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':70})
    if shot and 'data' in shot: open(os.path.join(OUT,f'v3desk_{m}.jpeg'),'wb').write(base64.b64decode(shot['data']))
    print(f'{m:14s} switch={sw} mainH={probe.get("mainH")}/{probe.get("vh")} fills={probe.get("fillsViewport")} bottomBgs={probe.get("bottomBgs")}')
cmd('Page.close'); ws.close()
print('OK')
