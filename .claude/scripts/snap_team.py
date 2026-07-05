"""Take ONE clean screenshot of the L'équipe page in iPhone emulation."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\mobile_team_clean.jpeg'
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
cmd('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 3, 'mobile': True, 'screenWidth': 390, 'screenHeight': 844})
cmd('Emulation.setTouchEmulationEnabled', {'enabled': True})
cmd('Emulation.setUserAgentOverride', {'userAgent':'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'})
time.sleep(9)

# Tap L'équipe card
r = cmd('Runtime.evaluate', {'expression': r'''(()=>{const b=Array.from(document.querySelectorAll("button")).find(x=>/équipe/i.test(x.textContent||"")); if(b){b.click();return"tapped"} return"missing"})()''', 'returnByValue': True})
print('tap:', r.get('result',{}).get('value'))
time.sleep(4)  # let the suspense + portrait paths render

shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':82,'captureBeyondViewport':True})
data = base64.b64decode(shot['data'])
open(OUT,'wb').write(data)
print(f'wrote {OUT} ({len(data)} bytes)')

audit = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const portraits = Array.from(document.querySelectorAll("button")).filter(b=>/^(Sage|Lou|Mira|Diego|Tess|Sam|Yann)/.test((b.textContent||"").trim()));
  return {portraitCount: portraits.length, svgs: document.querySelectorAll("svg").length, paths: document.querySelectorAll("path").length, hasKeyframes: !!document.getElementById("a10-keyframes"), title: (document.querySelector("h1")||{}).textContent || ""};
})()''', 'returnByValue': True})
print('audit:', json.dumps(audit.get('result',{}).get('value',{}), ensure_ascii=False))

cmd('Page.close')
ws.close()
