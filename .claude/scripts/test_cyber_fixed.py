"""Verify Cyber no longer crashes on V1 + V3 desktop after TDZ fix."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'

for skin, dock_label in [('aurora_v1','Cyber⌘7'), ('aurora_v3','Cyber')]:
    print(f'\n=== {skin} ===')
    r = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(TUNNEL, safe=":/")}', method='PUT')
    new_tab = json.load(urllib.request.urlopen(r))
    ws = websocket.create_connection(new_tab['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
    mid=[0]
    def cmd(m,p=None):
        mid[0]+=1
        msg={'id':mid[0],'method':m}
        if p is not None: msg['params']=p
        ws.send(json.dumps(msg))
        while True:
            rr=json.loads(ws.recv())
            if rr.get('id')==mid[0]:
                if 'error' in rr: return {'__err':rr['error']}
                return rr.get('result',{})
    cmd('Page.enable'); cmd('Runtime.enable')
    cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
    cmd('Runtime.evaluate', {'expression': f'(()=>{{try{{localStorage.setItem("aurora-ui-skin","{skin}");localStorage.removeItem("ft-grimoire-page");}}catch(_){{}}}}'+'})()'})
    cmd('Page.reload'); time.sleep(8)
    # click cyber
    if skin == 'aurora_v1':
        click_js = f'(()=>{{const els=Array.from(document.querySelectorAll("button"));const el=els.find(b=>(b.textContent||"").includes({json.dumps(dock_label)}));if(el){{el.click();return"OK"}}return"MISS"}})()'
    else:
        click_js = f'(()=>{{const btn=Array.from(document.querySelectorAll(".aurora-v3-dock-btn,button")).find(b=>{{const lbl=(b.querySelector(".aurora-v3-dock-label")||b).textContent||"";return lbl.trim()==={json.dumps(dock_label)}}});if(btn){{btn.click();return"OK"}}return"MISS"}})()'
    print('  click:', cmd('Runtime.evaluate', {'expression':click_js,'returnByValue':True}).get('result',{}).get('value'))
    # listen for errors 3s
    seen = []
    ws.settimeout(0.05)
    end = time.time()+3
    while time.time()<end:
        try:
            m = ws.recv()
            d = json.loads(m)
            if d.get('method') in ('Runtime.exceptionThrown','Runtime.consoleAPICalled'):
                p = d.get('params',{})
                if d['method']=='Runtime.exceptionThrown':
                    ex = p.get('exceptionDetails',{})
                    seen.append(f"EXC: {ex.get('text','')} {ex.get('exception',{}).get('description','')[:200]}")
                elif p.get('type')=='error':
                    args = ' '.join((a.get('value') or a.get('description','?'))[:200] if isinstance(a,dict) else str(a) for a in (p.get('args') or []))
                    seen.append(f"err: {args[:200]}")
        except websocket.WebSocketTimeoutException:
            time.sleep(0.05)
    ws.settimeout(None)
    state = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const text=document.body.innerText;
      const crashed=/a bloque|crashed/.test(text);
      const hasKatas=/kata|dojo|ceinture|owasp|stage \d/i.test(text);
      return {crashed, hasKatas, bodyLen:text.length, snippet:text.slice(0,200).replace(/\n/g,' | ')};
    })()''', 'returnByValue':True}).get('result',{}).get('value',{})
    print(f'  crashed={state.get("crashed")} hasKatas={state.get("hasKatas")} bodyLen={state.get("bodyLen")}')
    print(f'  errors captured: {len(seen)}')
    for e in seen[:3]: print(f'    {e}')
    print(f'  snippet: {state.get("snippet")[:160]}')
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':75})
    if shot and 'data' in shot:
        open(os.path.join(OUT, f'cyber_fixed_{skin}.jpeg'),'wb').write(base64.b64decode(shot['data']))
    cmd('Page.close'); ws.close()
