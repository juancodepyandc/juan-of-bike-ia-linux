"""Inspect V1 desktop sidebar DOM structure to find correct module-switch selector."""
import json, urllib.request, urllib.parse, websocket, sys, time, io
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

cmd('Page.enable'); cmd('Runtime.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.setItem('aurora-ui-skin','aurora_v1');}catch(_){}})()'''})
cmd('Page.reload'); time.sleep(8)

info = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  // Enumerate every clickable in the left sidebar
  const sidebar = document.querySelector('[class*=sidebar],[class*=Sidebar],aside,nav') || document.body;
  const clickables = Array.from(sidebar.querySelectorAll('button, a, [role=button], [role=tab], li, [data-module]'));
  const filtered = clickables.filter(el=>{const t=(el.textContent||'').trim();return t && t.length<60}).slice(0, 30);
  return filtered.map(el=>({
    tag: el.tagName.toLowerCase(),
    text: (el.textContent||'').replace(/\s+/g,' ').trim().slice(0,60),
    cls: (el.className && el.className.toString) ? el.className.toString().slice(0,80) : '',
    dataModule: el.getAttribute('data-module')||'',
    aria: el.getAttribute('aria-label')||'',
    role: el.getAttribute('role')||'',
    href: el.getAttribute('href')||'',
  }));
})()''', 'returnByValue':True})
items = info.get('result',{}).get('value',[])
for i,el in enumerate(items[:25]):
    print(f'{i:2d} {el["tag"]:6} text={el["text"][:40]!r:40} cls={el["cls"][:40]!r} data-module={el["dataModule"]!r}')
cmd('Page.close'); ws.close()
