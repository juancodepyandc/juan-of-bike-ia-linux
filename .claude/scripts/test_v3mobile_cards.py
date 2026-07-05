"""iter5: V3 mobile shell — tap a numbered card → its module mounts fullscreen (slide-in + back arrow)."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'
os.makedirs(OUT, exist_ok=True)

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
cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.clear();localStorage.setItem('aurora-ui-skin','aurora_v3');localStorage.setItem('aurora_build_id_html','v82s-studio5');}catch(_){}})()'''})
cmd('Page.reload'); time.sleep(11)

cover = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const cards = Array.from(document.querySelectorAll('button')).map(b=>(b.textContent||'').replace(/\s+/g,' ').trim()).filter(t=>t.length>2);
  const hasTeam = cards.some(c=>/L.ÉQUIPE|7 personae/i.test(c));
  const numbered = cards.filter(c=>/^(I|II|III|IV|V|VI|VII|VIII)\s*·/.test(c));
  return {hasTeam, numbered: numbered.slice(0,10), total: cards.length};
})()''', 'returnByValue':True}).get('result',{}).get('value',{})
print('V3 cover hasTeam:', cover.get('hasTeam'))
print('numbered cards:', cover.get('numbered'))
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':74})
if shot and 'data' in shot: open(os.path.join(OUT,'v3mobile_cover.jpeg'),'wb').write(base64.b64decode(shot['data']))

# tap Card II (DICTAPHONE → conversation)
tap = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const b=Array.from(document.querySelectorAll('button')).find(b=>/^II\s*·\s*DICTAPHONE/.test((b.textContent||'').replace(/\s+/g,' ').trim()));
  if(b){b.click();return 'tap DICTAPHONE'} return 'miss'
})()''', 'returnByValue':True}).get('result',{}).get('value')
print('tap card II:', tap)
time.sleep(0.4)
anim = cmd('Runtime.evaluate', {'expression': r'''(()=>{const el=document.querySelector('.aurora-mobile-slide-in');return {hasSlide:!!el, anim: el?getComputedStyle(el).animationName:'none'};})()''', 'returnByValue':True}).get('result',{}).get('value',{})
print('slide-in:', anim)
time.sleep(4)
mod = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const text=document.body.innerText;
  const headerHasConv=/conversation/i.test(text.slice(0,120));
  const back=!!Array.from(document.querySelectorAll('button')).find(b=>/^←|retour/i.test((b.textContent||'').trim()));
  const errs=(window.__auroraErrors||[]);
  return {headerHasConv, back, bodyLen:text.length, snippet:text.slice(0,200).replace(/\n/g,' | ')};
})()''', 'returnByValue':True}).get('result',{}).get('value',{})
print('module:', mod)
shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':74})
if shot and 'data' in shot: open(os.path.join(OUT,'v3mobile_card_conv.jpeg'),'wb').write(base64.b64decode(shot['data']))

# back
cmd('Runtime.evaluate', {'expression': r'''(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>/^←|retour/i.test((b.textContent||'').trim()));if(b)b.click()})()'''})
time.sleep(1.5)
back = cmd('Runtime.evaluate', {'expression': r'''(()=>{const cards=Array.from(document.querySelectorAll('button')).filter(b=>/DICTAPHONE|LIGHTBOX|L.ÉQUIPE/i.test(b.textContent||'')).length;return {backToCover: cards>=2};})()''', 'returnByValue':True}).get('result',{}).get('value',{})
print('back to cover:', back)

# console errors
cmd('Runtime.evaluate', {'expression': '1'})  # noop
cmd('Page.close'); ws.close()
print('OK')
