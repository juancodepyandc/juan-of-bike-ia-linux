"""Audit each skin (manga / aurora_v1 / aurora_v3) on desktop viewport.
Capture screenshot + console errors + DOM body for each.
"""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10'
os.makedirs(OUT, exist_ok=True)

SKINS = ['aurora_v1', 'aurora_v3']  # manga not in allow-list

def open_tab(url):
    r = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(url, safe=":/?=&")}', method='PUT')
    return json.load(urllib.request.urlopen(r))

def session(ws):
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
    return cmd

results = {}
for skin in SKINS:
    tab = open_tab(TUNNEL)
    ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
    cmd = session(ws)
    cmd('Page.enable'); cmd('Runtime.enable'); cmd('Log.enable')
    # Desktop viewport
    cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
    cmd('Emulation.clearDeviceMetricsOverride') if False else None  # keep override
    cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      try {{ localStorage.setItem('aurora-ui-skin','{skin}'); localStorage.removeItem('ft-grimoire-page'); }} catch(_){{}}
      return 'set {skin}';
    }})()'''})
    cmd('Page.reload')
    time.sleep(9)

    # Listen briefly
    seen = []
    ws.settimeout(0.05)
    end = time.time()+1.5
    while time.time()<end:
        try:
            m = ws.recv()
            d = json.loads(m)
            method = d.get('method','')
            if method in ('Runtime.consoleAPICalled','Runtime.exceptionThrown','Log.entryAdded'):
                seen.append(d)
        except websocket.WebSocketTimeoutException:
            time.sleep(0.05)
    ws.settimeout(None)

    state = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const skin = document.documentElement.getAttribute('data-ui-skin');
      const buildId = localStorage.getItem('aurora_build_id_html');
      const bodyText = document.body.innerText.slice(0, 600);
      const buttons = Array.from(document.querySelectorAll('button')).slice(0, 25).map(b=>(b.textContent||'').replace(/\s+/g,' ').trim().slice(0,40));
      const hasSidebar = !!document.querySelector('[class*=sidebar],[class*=Sidebar]');
      const hasModuleNav = !!document.querySelector('[class*=module-nav],[class*=ModuleNav]');
      const visibleH1 = Array.from(document.querySelectorAll('h1')).map(h=>h.textContent.trim()).slice(0,5);
      return {skin, buildId, bodyText, buttons, hasSidebar, hasModuleNav, visibleH1, bodyLen: document.body.innerText.length};
    })()''', 'returnByValue': True})
    val = state.get('result',{}).get('value',{})

    # Console errors
    errors = []
    for m in seen:
        method = m['method']
        p = m.get('params',{})
        if method == 'Runtime.consoleAPICalled' and p.get('type') == 'error':
            args = ' '.join((a.get('value') or a.get('description','?'))[:200] if isinstance(a, dict) else str(a) for a in (p.get('args') or []))
            errors.append(f'[error] {args[:300]}')
        elif method == 'Runtime.exceptionThrown':
            ex = p.get('exceptionDetails',{})
            errors.append(f'[EXC] {ex.get("text","")} {ex.get("exception",{}).get("description","")[:200]}')
        elif method == 'Log.entryAdded':
            e = p.get('entry',{})
            if e.get('level') == 'error':
                errors.append(f'[log-err] {e.get("text","")[:300]}')

    # Screenshot
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':80})
    out_path = os.path.join(OUT, f'desktop_{skin}.jpeg')
    open(out_path,'wb').write(base64.b64decode(shot['data']))

    results[skin] = {'state': val, 'errors': errors, 'shot': out_path}
    print(f'\n=== SKIN {skin} ===')
    print('build:', val.get('buildId'))
    print('h1:', val.get('visibleH1'))
    print('body len:', val.get('bodyLen'))
    print('snippet:', (val.get('bodyText','') or '')[:200].replace('\n',' | '))
    print(f'errors: {len(errors)}')
    for e in errors[:8]: print(' ',e)
    print(f'shot: {out_path}')

    cmd('Page.close'); ws.close()

print('\n=== SUMMARY ===')
for s, r in results.items():
    print(f'{s}: bodyLen={r["state"].get("bodyLen")} errors={len(r["errors"])}')
