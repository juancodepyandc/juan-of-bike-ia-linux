"""iter7 verify: on v3 desktop, the agent scene is click-through (input bar not blocked)."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'
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
cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.clear();localStorage.setItem('aurora-ui-skin','aurora_v3');localStorage.setItem('aurora_build_id_html','v82s-studio7');localStorage.setItem('juan-bike-app-store',JSON.stringify({state:{activeModule:'code'},version:0}));}catch(_){}})()'''})
cmd('Page.reload'); time.sleep(12)
res = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  // does anything in .aurora-v3-scene have pointer-events != none?
  const scene=document.querySelector('.aurora-v3-scene');
  const fig=document.querySelector('.aurora-v3-scene .aurora-scene-figure');
  const figPE = fig? getComputedStyle(fig).pointerEvents : 'no-fig';
  const scenePE = scene? getComputedStyle(scene).pointerEvents : 'no-scene';
  // sample a few points where the avatar visually is — what element is on top?
  const vw=window.innerWidth, vh=window.innerHeight;
  const probes=[];
  for(const [x,y] of [[vw*0.6, vh-120],[vw*0.62, vh-90],[vw*0.58, vh-160]]){
    const el=document.elementFromPoint(x,y);
    probes.push({x:Math.round(x),y:Math.round(y), tag:el?el.tagName:'?', cls: el?(el.className||'').toString().slice(0,40):'?', inScene: !!(el&&el.closest&&el.closest('.aurora-v3-scene'))});
  }
  // find the prompt textarea/input and check it's the topmost at its center
  const ta=document.querySelector('.aurora-v3-module textarea, .aurora-v3-module input[type="text"]');
  let inputReachable=null;
  if(ta){const rr=ta.getBoundingClientRect(); const el=document.elementFromPoint(rr.left+rr.width/2, rr.top+rr.height/2); inputReachable = el===ta || (el&&ta.contains(el)) || (el&&el.contains(ta));}
  return {scenePE, figPE, probes, inputReachable, hasModule: !!document.querySelector('.aurora-v3-module')};
})()''', 'returnByValue':True}).get('result',{}).get('value',{})
print(json.dumps(res, indent=1, ensure_ascii=False))
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':72})
if shot and 'data' in shot: open(os.path.join(OUT,'v3desk_code_clickthrough.jpeg'),'wb').write(base64.b64decode(shot['data']))
cmd('Page.close'); ws.close()
print('OK')
