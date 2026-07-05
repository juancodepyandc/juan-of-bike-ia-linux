"""Capture console errors when V3 Cyber crashes."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
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

cmd('Page.enable'); cmd('Runtime.enable'); cmd('Log.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.setItem('aurora-ui-skin','aurora_v3');}catch(_){}})()'''})
cmd('Page.reload'); time.sleep(8)

# Switch to cyber via dock
cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const btn=Array.from(document.querySelectorAll('.aurora-v3-dock-btn,button')).find(b=>{const lbl=(b.querySelector('.aurora-v3-dock-label')||b).textContent||'';return lbl.trim()==='Cyber'});
  if(btn){btn.click();return 'tap'} return 'miss'
})()'''})

# Listen for 4s for errors
seen = []
ws.settimeout(0.05)
end = time.time()+4
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

print('errors / exceptions captured:')
for d in seen:
    method = d['method']
    p = d.get('params',{})
    if method == 'Runtime.exceptionThrown':
        ex = p.get('exceptionDetails',{})
        print(f'\n[EXCEPTION] {ex.get("text","")}')
        print(f'  description: {ex.get("exception",{}).get("description","")[:600]}')
        print(f'  url: {ex.get("url","")}')
    elif method == 'Runtime.consoleAPICalled' and p.get('type') in ('error','warning'):
        args = ' '.join((a.get('value') or a.get('description','?'))[:300] if isinstance(a, dict) else str(a) for a in (p.get('args') or []))
        print(f'\n[{p.get("type")}] {args[:600]}')
    elif method == 'Log.entryAdded':
        e = p.get('entry',{})
        if e.get('level') in ('error','warning'):
            print(f'\n[{e.get("level")}] {e.get("text","")[:500]} @ {e.get("url","")}')

cmd('Page.close'); ws.close()
