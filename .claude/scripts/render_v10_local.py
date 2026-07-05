"""Serve v10 locally + screenshot via CDP."""
import json, urllib.request, websocket, base64, sys, time, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, socket

ROOT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10'
OUT = os.path.join(ROOT, 'v10_render_local.jpeg')

# 1. find free port
s = socket.socket(); s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]; s.close()

# 2. start http.server in thread serving ROOT
os.chdir(ROOT)
srv = ThreadingHTTPServer(('127.0.0.1', PORT), SimpleHTTPRequestHandler)
t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
url = f'http://127.0.0.1:{PORT}/Aurora_v10.html'
print(f'serving {ROOT} on {url}')

# 3. open new tab in user's Chrome via /json/new
req = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(url, safe=":/")}', method='PUT')
try:
    new_tab = json.load(urllib.request.urlopen(req))
except Exception:
    # fallback: GET
    new_tab = json.load(urllib.request.urlopen(f'http://localhost:9222/json/new?{urllib.parse.quote(url, safe=":/")}'))
print('new tab:', new_tab['id'], new_tab.get('url','')[:80])
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

cmd('Page.enable')
cmd('Page.navigate', {'url': url})
# Wait for load + extra time for fonts/animations
time.sleep(8)

# Set a wide viewport for fullPage capture (the design uses w=1440)
cmd('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
time.sleep(3)

# Capture a screenshot of full content
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':80,'captureBeyondViewport':True})
data = base64.b64decode(shot['data'])
with open(OUT, 'wb') as f: f.write(data)
print(f'screenshot {len(data)} bytes -> {OUT}')

# Cleanup: close the tab
cmd('Page.close')
ws.close()
srv.shutdown()
print('done')
