"""Test the redesigned mobile dock: tap a dock button → module fullscreen slide-in."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'

r = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(TUNNEL+"/?device=mobile", safe=":/?=&")}', method='PUT')
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
cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':3,'mobile':True})
cmd('Emulation.setTouchEmulationEnabled', {'enabled':True})
cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.removeItem('juan-bike-app-store');localStorage.setItem('aurora-ui-skin','aurora_v1');localStorage.setItem('aurora_build_id_html','v82s-studio');}catch(_){}})()'''})
cmd('Page.reload'); time.sleep(10)

# Check dock buttons
dock = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  // dock buttons have aria-label / title set
  const dockBtns = Array.from(document.querySelectorAll('button[aria-label]')).filter(b=>['L\'équipe','Chat','Image','Code','Académie'].includes(b.getAttribute('aria-label'))).map(b=>b.getAttribute('aria-label'));
  return {dockLabels: dockBtns, overlapCTA: !!Array.from(document.querySelectorAll('button')).find(b=>/ouvrir le grimoire/i.test(b.textContent||''))};
})()''', 'returnByValue':True}).get('result',{}).get('value',{})
print('dock buttons:', dock.get('dockLabels'))
print('overlap CTA removed:', not dock.get('overlapCTA'))
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':78})
if shot and 'data' in shot:
    open(os.path.join(OUT,'mobile_dock_cover.jpeg'),'wb').write(base64.b64decode(shot['data']))

# Tap "Chat" dock button → conversation module fullscreen
tap = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const b=Array.from(document.querySelectorAll('button[aria-label="Chat"]'))[0];
  if(b){b.click();return 'tap Chat'} return 'miss Chat'
})()''', 'returnByValue':True}).get('result',{}).get('value')
print('tap dock Chat:', tap)
time.sleep(0.4)
anim = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const el=document.querySelector('.aurora-mobile-slide-in');
  return {hasSlide: !!el, anim: el?getComputedStyle(el).animationName:'none'};
})()''', 'returnByValue':True}).get('result',{}).get('value',{})
print('slide-in:', anim)
time.sleep(3)
mod = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const text=document.body.innerText;
  const isConv=/dictaphone|conversation|message|aurora.*time|pipeline/i.test(text.slice(0,500));
  const back=!!Array.from(document.querySelectorAll('button')).find(b=>/^←|retour/i.test((b.textContent||'').trim()));
  return {isConv, back, bodyLen:text.length};
})()''', 'returnByValue':True}).get('result',{}).get('value',{})
print('module:', mod)
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':78})
if shot and 'data' in shot:
    open(os.path.join(OUT,'mobile_dock_chat.jpeg'),'wb').write(base64.b64decode(shot['data']))
cmd('Page.close'); ws.close()
