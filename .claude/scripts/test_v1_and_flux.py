"""V1 desktop re-audit (sidebar selectors fixed) + Real FLUX prompt test."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'
os.makedirs(OUT, exist_ok=True)

def open_tab(url):
    r = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(url, safe=":/?=&")}', method='PUT')
    return json.load(urllib.request.urlopen(r))

def ws_session(tab):
    ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
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
    return ws, cmd

# === V1 DESKTOP RE-AUDIT (substring match) ===
print('=== V1 DESKTOP RE-AUDIT ===')
tab = open_tab(TUNNEL)
ws, cmd = ws_session(tab)
cmd('Page.enable'); cmd('Runtime.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.setItem('aurora-ui-skin','aurora_v1');localStorage.removeItem('ft-grimoire-page');}catch(_){}})()'''})
cmd('Page.reload'); time.sleep(8)

modules = [
    ('conversation', 'Conversation'),('image','Image'),('code','Code'),
    ('video','Vidéo'),('drawing','Dessin'),('3d','3D'),
    ('learning','Academy'),('cyber','Cyber'),
]
v1_results = {}
for mod_id, label in modules:
    click = cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      const links=Array.from(document.querySelectorAll('button,a,nav *'));
      const want={json.dumps(label)};
      const el=links.find(b=>{{const t=(b.textContent||'').trim();return t===want||t.includes(want+' ')||t.endsWith(want)||t.startsWith(want)}});
      if(el){{el.click();return 'click '+want+': '+(el.textContent||'').slice(0,30)}}
      return 'miss '+want;
    }})()''', 'returnByValue':True})
    print(f'  {click.get("result",{}).get("value")}')
    time.sleep(2.5)
    info = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const ls=localStorage.getItem('juan-bike-app-store')||'';
      const m=ls.match(/"activeModule":"([^"]+)"/);
      const text=document.body.innerText;
      const errOverlay=/a bloque|Cyber a bloque|crashed/.test(text);
      return {active: m && m[1], bodyLen: text.length, hasErr: errOverlay,
              h1: Array.from(document.querySelectorAll('h1')).slice(0,3).map(h=>h.textContent.trim().slice(0,40))};
    })()''', 'returnByValue':True})
    v1_results[mod_id] = info.get('result',{}).get('value',{})
    val = v1_results[mod_id]
    err = ' [CRASH]' if val.get('hasErr') else ''
    print(f'    active={val.get("active")} bodyLen={val.get("bodyLen")}{err} h1={val.get("h1")[:1]}')
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':70})
    if shot and 'data' in shot:
        open(os.path.join(OUT, f'v1_desktop_{mod_id}.jpeg'),'wb').write(base64.b64decode(shot['data']))

cmd('Page.close'); ws.close()

# === FLUX TEST ===
print('\n=== FLUX REAL PROMPT TEST (V3 Image module) ===')
tab = open_tab(TUNNEL)
ws, cmd = ws_session(tab)
cmd('Page.enable'); cmd('Runtime.enable'); cmd('Network.enable'); cmd('Log.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.setItem('aurora-ui-skin','aurora_v3');localStorage.removeItem('ft-grimoire-page');}catch(_){}})()'''})
cmd('Page.reload'); time.sleep(8)
# Click Image
cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const btn=Array.from(document.querySelectorAll('.aurora-v3-dock-btn,button')).find(b=>{const lbl=(b.querySelector('.aurora-v3-dock-label')||b).textContent||'';return lbl.trim()==='Image'});
  if(btn) btn.click();
})()'''})
time.sleep(3)
# Find prompt input
focus = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const ta=Array.from(document.querySelectorAll('textarea,input[type=text]')).find(el=>{const ph=(el.getAttribute('placeholder')||'').toLowerCase();return /décris|prompt|prochaine|prise|prompt:/.test(ph) || el.tagName==='TEXTAREA'});
  if(ta){ta.focus();return {ph:ta.getAttribute('placeholder'),tag:ta.tagName}}
  return {missing:true};
})()''', 'returnByValue':True})
print('input:', focus.get('result',{}).get('value'))

# Simple FLUX prompt
cmd('Input.insertText', {'text':'a calm zen garden with a stone lantern at dusk, sumi-e style'})
time.sleep(0.5)
clicked = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const buttons=Array.from(document.querySelectorAll('button'));
  const tirer=buttons.find(b=>/tirer|générer|generate|envoyer|valider|go/i.test(b.textContent||'') && !b.disabled);
  if(tirer){tirer.click();return {clicked:true,text:(tirer.textContent||'').slice(0,30)}}
  return {clicked:false,btns: buttons.slice(0,8).map(b=>(b.textContent||'').slice(0,20))};
})()''', 'returnByValue':True})
print('click TIRER:', clicked.get('result',{}).get('value'))

# Listen for /api/web/image network calls + console errors for 30s
print('waiting up to 60s for FLUX response...')
seen_api = []
seen_err = []
ws.settimeout(0.05)
end = time.time()+60
while time.time()<end:
    try:
        m = ws.recv()
        d = json.loads(m)
        method = d.get('method','')
        if method == 'Network.requestWillBeSent':
            url = d.get('params',{}).get('request',{}).get('url','')
            if '/api/web/image' in url or '/proxy/comfy' in url or 'comfyui' in url.lower():
                seen_api.append({'phase':'request','url':url[:120]})
        elif method == 'Network.responseReceived':
            url = d.get('params',{}).get('response',{}).get('url','')
            status = d.get('params',{}).get('response',{}).get('status')
            if '/api/web/image' in url or '/proxy/comfy' in url or 'comfyui' in url.lower():
                seen_api.append({'phase':'response','status':status,'url':url[:120]})
        elif method == 'Runtime.consoleAPICalled' and d.get('params',{}).get('type')=='error':
            args = ' '.join((a.get('value') or a.get('description','?'))[:200] if isinstance(a,dict) else str(a) for a in (d.get('params',{}).get('args') or []))
            seen_err.append(args[:300])
        elif method == 'Runtime.exceptionThrown':
            ex = d.get('params',{}).get('exceptionDetails',{})
            seen_err.append(f"EXC {ex.get('text','')} {ex.get('exception',{}).get('description','')[:200]}")
    except websocket.WebSocketTimeoutException:
        time.sleep(0.05)
ws.settimeout(None)

print(f'\nAPI calls: {len(seen_api)}')
for a in seen_api[:8]: print('  ',a)
print(f'\nErrors: {len(seen_err)}')
for e in seen_err[:5]: print('  ',e)

shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':75})
open(os.path.join(OUT,'flux_after_prompt.jpeg'),'wb').write(base64.b64decode(shot['data']))
print(f'\nshot: {os.path.join(OUT,"flux_after_prompt.jpeg")}')
cmd('Page.close'); ws.close()
