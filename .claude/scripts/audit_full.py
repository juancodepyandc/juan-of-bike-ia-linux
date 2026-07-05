"""Comprehensive audit: each module × each skin × desktop+mobile = capture + functional probe.

For each (skin, device, module):
  - navigate
  - screenshot
  - check key elements rendered (DOM selectors)
  - attempt one minimal interaction where possible (e.g., type into prompt input)
"""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'
os.makedirs(OUT, exist_ok=True)

MODULES_DESKTOP = ['conversation','image','code','video','drawing','3d','learning','cyber']

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
                if 'error' in r: return {'__err': r['error']}
                return r.get('result',{})
    return ws, cmd

results = {}

# ================ DESKTOP AUDIT ================
for skin in ['aurora_v1', 'aurora_v3']:
    label = f'desktop_{skin}'
    results[label] = {}
    print(f'\n=== {label} ===')
    tab = open_tab(TUNNEL)
    ws, cmd = ws_session(tab)
    cmd('Page.enable'); cmd('Runtime.enable'); cmd('Log.enable')
    cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
    cmd('Runtime.evaluate', {'expression': f'(()=>{{try{{localStorage.setItem("aurora-ui-skin","{skin}");localStorage.removeItem("ft-grimoire-page");}}catch(_){{}}}}'+'})()'})
    cmd('Page.reload'); time.sleep(8)

    for mod in MODULES_DESKTOP:
        # Click module either via sidebar (v1) or dock (v3)
        if skin == 'aurora_v1':
            click_js = (
                f'(()=>{{const links=Array.from(document.querySelectorAll("button,a"));'
                f'const m={{conversation:"Conversation",image:"Image",code:"Code",video:"Vidéo",drawing:"Dessin","3d":"3D",learning:"Academy",cyber:"Cyber"}};'
                f'const t=m["{mod}"];const el=links.find(b=>(b.textContent||"").trim()===t||(b.textContent||"").trim().startsWith(t));'
                f'if(el){{el.click();return"OK "+t}}return"MISS "+t}})()'
            )
        else:
            click_js = (
                f'(()=>{{const m={{conversation:"Chat",image:"Image",code:"Code",video:"Vidéo",drawing:"Dessin","3d":"3D",learning:"Academy",cyber:"Cyber"}};'
                f'const t=m["{mod}"];const btn=Array.from(document.querySelectorAll(".aurora-v3-dock-btn,button")).find(b=>{{const lbl=(b.querySelector(".aurora-v3-dock-label")||b).textContent||"";return lbl.trim()===t}});'
                f'if(btn){{btn.click();return"OK "+t}}return"MISS "+t}})()'
            )
        r = cmd('Runtime.evaluate', {'expression': click_js, 'returnByValue':True})
        print(f'  click {mod}: {r.get("result",{}).get("value","?")}')
        time.sleep(3)
        # Probe rendering
        probe = cmd('Runtime.evaluate', {'expression': r'''(()=>{
          const buttons = document.querySelectorAll('button').length;
          const inputs = document.querySelectorAll('input,textarea,[contenteditable=true]').length;
          const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,[role=heading]')).slice(0,5).map(h=>(h.textContent||'').trim().slice(0,50));
          const text = document.body.innerText.slice(0, 400);
          const errs = (window.__lastErrors || []).slice(0, 3);
          return {buttons, inputs, headings, text, errs};
        })()''', 'returnByValue':True})
        info = probe.get('result',{}).get('value',{})
        results[label][mod] = info
        # Screenshot
        shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':70})
        if shot and 'data' in shot:
            open(os.path.join(OUT, f'{label}_{mod}.jpeg'),'wb').write(base64.b64decode(shot['data']))
        print(f'    btns={info.get("buttons")} inputs={info.get("inputs")} h1={info.get("headings",[])[:2]}')
    cmd('Page.close'); ws.close()

# ================ MOBILE AUDIT ================
for skin in ['aurora_v1', 'aurora_v3']:
    label = f'mobile_{skin}'
    results[label] = {}
    print(f'\n=== {label} ===')
    tab = open_tab(f'{TUNNEL}/?device=mobile')
    ws, cmd = ws_session(tab)
    cmd('Page.enable'); cmd('Runtime.enable')
    cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':3,'mobile':True})
    cmd('Emulation.setTouchEmulationEnabled', {'enabled':True})
    cmd('Runtime.evaluate', {'expression': f'(()=>{{try{{localStorage.setItem("aurora-ui-skin","{skin}");localStorage.removeItem("ft-grimoire-page");}}catch(_){{}}}}'+'})()'})
    cmd('Page.reload'); time.sleep(9)

    # Cover screenshot
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':75})
    if shot and 'data' in shot:
        open(os.path.join(OUT, f'{label}_cover.jpeg'),'wb').write(base64.b64decode(shot['data']))
    cover = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const cards = Array.from(document.querySelectorAll('button')).filter(b=>(b.textContent||'').trim().length>2).slice(0,15).map(b=>(b.textContent||'').replace(/\s+/g,' ').trim().slice(0,40));
      const teamCard = !!Array.from(document.querySelectorAll('button')).find(b=>/équipe|equipe/i.test(b.textContent||''));
      return {cards, teamCard};
    })()''', 'returnByValue':True})
    cinfo = cover.get('result',{}).get('value',{})
    results[label]['_cover'] = cinfo
    print(f'  cover: teamCard={cinfo.get("teamCard")} cards={len(cinfo.get("cards",[]))}')

    # Tap L'équipe
    tap = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const card=Array.from(document.querySelectorAll('button')).find(b=>/équipe/i.test(b.textContent||''));
      if(card){card.click();return 'tap'} return 'miss'
    })()''', 'returnByValue':True})
    print(f'  tap L\'équipe: {tap.get("result",{}).get("value")}')
    time.sleep(3)
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':75})
    if shot and 'data' in shot:
        open(os.path.join(OUT, f'{label}_team.jpeg'),'wb').write(base64.b64decode(shot['data']))
    team = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const personas=Array.from(document.querySelectorAll('button')).filter(b=>/^(Sage|Lou|Mira|Diego|Tess|Sam|Yann)/.test((b.textContent||'').trim())).length;
      return {personas, paths: document.querySelectorAll('path').length, hasKeyframes: !!document.getElementById('a10-keyframes')};
    })()''', 'returnByValue':True})
    tinfo = team.get('result',{}).get('value',{})
    results[label]['_team'] = tinfo
    print(f'  team: personas={tinfo.get("personas")} paths={tinfo.get("paths")} keyframes={tinfo.get("hasKeyframes")}')

    # Tap Sage portrait → conversation
    tap = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const sage=Array.from(document.querySelectorAll('button')).find(b=>/^Sage/.test((b.textContent||'').trim()));
      if(sage){sage.click();return 'tap'} return 'miss'
    })()''', 'returnByValue':True})
    print(f'  tap Sage→conversation: {tap.get("result",{}).get("value")}')
    time.sleep(4)
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':75})
    if shot and 'data' in shot:
        open(os.path.join(OUT, f'{label}_module_conv.jpeg'),'wb').write(base64.b64decode(shot['data']))
    mod_state = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const inputs=document.querySelectorAll('input,textarea,[contenteditable=true]').length;
      const buttons=document.querySelectorAll('button').length;
      const text=document.body.innerText.slice(0,200);
      return {inputs, buttons, text};
    })()''', 'returnByValue':True})
    minfo = mod_state.get('result',{}).get('value',{})
    results[label]['_module_conv'] = minfo
    print(f'  module mounted: btns={minfo.get("buttons")} inputs={minfo.get("inputs")}')
    cmd('Page.close'); ws.close()

# Save results
with open(os.path.join(OUT, '_audit.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f'\nfull audit at {OUT}')
print(f'json: {os.path.join(OUT, "_audit.json")}')
