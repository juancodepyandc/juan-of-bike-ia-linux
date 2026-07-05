"""Find what is rendering the orange ? orb at bottom-left of mobile shell."""
import json, urllib.request, urllib.parse, websocket, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
TARGET = f'{TUNNEL}/?device=mobile'
req_url = f'http://localhost:9222/json/new?{urllib.parse.quote(TARGET, safe=":/?=&")}'
req = urllib.request.Request(req_url, method='PUT')
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
cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':3,'mobile':True})
cmd('Emulation.setTouchEmulationEnabled', {'enabled':True})
cmd('Emulation.setUserAgentOverride', {'userAgent':'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'})
time.sleep(8)

r = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  // Look for any fixed/absolute positioned element near bottom-left
  const els = Array.from(document.querySelectorAll('*'));
  const candidates = [];
  for (const el of els) {
    const cs = getComputedStyle(el);
    if ((cs.position === 'fixed' || cs.position === 'absolute')) {
      const r = el.getBoundingClientRect();
      // bottom-left zone of mobile viewport (390x844)
      if (r.left < 80 && r.bottom > 740 && r.width > 30 && r.width < 100 && r.height > 30 && r.height < 100) {
        candidates.push({
          tag: el.tagName.toLowerCase(),
          cls: el.className && el.className.toString ? el.className.toString().slice(0,80) : '',
          id: el.id||'',
          text: (el.textContent||'').slice(0,40),
          rect: {l:Math.round(r.left), t:Math.round(r.top), w:Math.round(r.width), h:Math.round(r.height)},
          bg: cs.backgroundColor.slice(0,30),
          z: cs.zIndex,
        });
      }
    }
  }
  return candidates.slice(0, 10);
})()''', 'returnByValue': True})
print(json.dumps(r.get('result',{}).get('value', []), ensure_ascii=False, indent=2))
cmd('Page.close'); ws.close()
