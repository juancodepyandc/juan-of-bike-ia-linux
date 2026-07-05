"""iter12: v3 desktop — agent scene is BACK with live v10 SVG avatars. Screenshot each module,
confirm: figure rendered (svg with a10-* keyframes), scene is click-through, no horizontal overflow,
module input still reachable."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'
BUILD='v82s-studio11'
MODULES = ['conversation','image','code','video','drawing','3d','learning','cyber']
r = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(TUNNEL+"/", safe=":/?=&")}', method='PUT')
nt = json.load(urllib.request.urlopen(r))
ws = websocket.create_connection(nt['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
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
cmd('Runtime.evaluate', {'expression': f'(()=>{{try{{localStorage.clear();localStorage.setItem("aurora-ui-skin","aurora_v3");localStorage.setItem("aurora_build_id_html","{BUILD}");localStorage.setItem("juan-bike-app-store",JSON.stringify({{state:{{activeModule:"conversation"}},version:0}}));}}catch(_){{}}}})()'})
cmd('Page.reload'); time.sleep(12)
# global checks first
g = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const kf=document.getElementById('a10-keyframes');
  const sceneEl=document.querySelector('.aurora-v3-scene');
  const figEl=document.querySelector('.aurora-v3-scene .aurora-scene-figure svg');
  return {hasKeyframes: !!kf, hasScene: !!sceneEl, scenePE: sceneEl?getComputedStyle(sceneEl).pointerEvents:'?', hasFigSvg: !!figEl, figSvgChildCount: figEl?figEl.children.length:0};
})()''', 'returnByValue':True}).get('result',{}).get('value',{})
print('GLOBAL:', g)
for m in MODULES:
    sw = cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      const labels={{conversation:'chat',image:'image',code:'code',video:'vidéo|video',drawing:'dessin|draw|atelier','3d':'3d|model',learning:'académie|academy|learn',cyber:'cyber'}};
      const rx=new RegExp(labels['{m}'],'i');
      const b=Array.from(document.querySelectorAll('button,a')).find(b=>rx.test((b.textContent||'')+(b.getAttribute('aria-label')||'')+(b.title||'')) && (b.textContent||'').length<24);
      if(b){{b.click();return 'clicked'}}return 'no-btn'
    }})()''', 'returnByValue':True}).get('result',{}).get('value')
    time.sleep(3.2)
    probe = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const hOver=(document.documentElement.scrollWidth-document.documentElement.clientWidth)>4;
      const figSvg=document.querySelector('.aurora-v3-scene .aurora-scene-figure svg');
      let figRect=null; if(figSvg){const rr=figSvg.getBoundingClientRect(); figRect={w:Math.round(rr.width),h:Math.round(rr.height),top:Math.round(rr.top),bottom:Math.round(rr.bottom)};}
      const ta=document.querySelector('.aurora-v3-module textarea, .aurora-v3-module input[type="text"]');
      let inputOk=null; if(ta){const rr=ta.getBoundingClientRect(); const el=document.elementFromPoint(rr.left+rr.width/2, rr.top+rr.height/2); inputOk=(el===ta||(el&&ta.contains(el))||(el&&el.contains(ta)));}
      // does the scene figure overlap the dock? dock top:
      const dock=document.querySelector('.aurora-v3-dock'); let dockTop=null; if(dock){dockTop=Math.round(dock.getBoundingClientRect().top);}
      return {hOver, figRect, inputOk, dockTop, figAboveDock: (figRect&&dockTop)? figRect.bottom<=dockTop+8 : null};
    })()''', 'returnByValue':True}).get('result',{}).get('value',{})
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':70})
    if shot and 'data' in shot: open(os.path.join(OUT,f'v3desk_scene_{m}.jpeg'),'wb').write(base64.b64decode(shot['data']))
    print(f'{m:14s} sw={sw} hOver={probe.get("hOver")} fig={probe.get("figRect")} inputOk={probe.get("inputOk")} dockTop={probe.get("dockTop")} figAboveDock={probe.get("figAboveDock")}')
cmd('Page.close'); ws.close()
print('OK')
