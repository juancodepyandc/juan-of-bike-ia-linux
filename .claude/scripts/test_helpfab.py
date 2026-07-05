"""iter6: HelpFab hidden on mobile, present on desktop."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'

def run(device, w, h, mobile):
    url = TUNNEL + ('/?device=mobile' if device=='mobile' else '/')
    r = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(url, safe=":/?=&")}', method='PUT')
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
    cmd('Emulation.setDeviceMetricsOverride', {'width':w,'height':h,'deviceScaleFactor':2,'mobile':mobile})
    if mobile: cmd('Emulation.setTouchEmulationEnabled', {'enabled':True})
    cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.clear();localStorage.setItem('aurora-ui-skin','aurora_v1');localStorage.setItem('aurora_build_id_html','v82s-studio6');}catch(_){}})()'''})
    cmd('Page.reload'); time.sleep(10)
    res = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const fab=Array.from(document.querySelectorAll('button')).find(b=>(b.getAttribute('aria-label')||'')==='Aide clavier');
      const errs=Array.from(document.querySelectorAll('button')).length;
      return {hasHelpFab: !!fab, btnCount: errs, dataDevice: document.documentElement.getAttribute('data-device')};
    })()''', 'returnByValue':True}).get('result',{}).get('value',{})
    print(f'{device}: hasHelpFab={res.get("hasHelpFab")} dataDevice={res.get("dataDevice")} btns={res.get("btnCount")}')
    cmd('Page.close'); ws.close()
    return res

run('mobile', 390, 844, True)
run('desktop', 1440, 900, False)
print('OK')
