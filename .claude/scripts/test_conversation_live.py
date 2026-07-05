"""Send a real prompt to conversation V3 desktop, see if Aurora responds."""
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

cmd('Page.enable'); cmd('Runtime.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':820,'deviceScaleFactor':1,'mobile':False})
cmd('Runtime.evaluate', {'expression': '''(()=>{try{localStorage.setItem('aurora-ui-skin','aurora_v3');localStorage.removeItem('ft-grimoire-page');}catch(_){}})()'''})
cmd('Page.reload'); time.sleep(8)

# Make sure we're on chat
cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const btn=Array.from(document.querySelectorAll('.aurora-v3-dock-btn,button')).find(b=>{const lbl=(b.querySelector('.aurora-v3-dock-label')||b).textContent||'';return lbl.trim()==='Chat'});
  if(btn) btn.click();
})()'''})
time.sleep(3)

# Find the chat input
focus = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const ta = Array.from(document.querySelectorAll('textarea,[contenteditable=true],input[type=text]')).find(el=>{const ph=(el.getAttribute('placeholder')||'').toLowerCase();const aria=(el.getAttribute('aria-label')||'').toLowerCase();return /dictez|message|prompt|question|écris|envoyer|chat|aurora/.test(ph+aria) || el.tagName==='TEXTAREA'});
  if(ta){ta.focus(); return {tag: ta.tagName, ph: ta.getAttribute('placeholder'), foundLen: ta.value?.length || 0};}
  return {missing: true};
})()''', 'returnByValue':True})
print('input focus:', focus.get('result',{}).get('value'))

# Type a real prompt
cmd('Input.insertText', {'text': 'Salut, dis bonjour en français en 5 mots.'})
time.sleep(0.5)

# Find and click Send
clicked = cmd('Runtime.evaluate', {'expression': r'''(()=>{
  const buttons=Array.from(document.querySelectorAll('button'));
  const send=buttons.find(b=>/envoyer|send|submit/i.test(b.getAttribute('aria-label')||b.textContent||'') && !b.disabled);
  if(send){send.click();return {clicked:true,text:(send.textContent||'').slice(0,30)}}
  return {clicked:false};
})()''', 'returnByValue':True})
print('send:', clicked.get('result',{}).get('value'))

# Wait + check for response
print('waiting for response (30s max)...')
for i in range(30):
    time.sleep(1)
    state = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const text = document.body.innerText;
      const hasGreeting = /bonjour|salut|hello|coucou/i.test(text.slice(-1000));
      const hasStreaming = /streaming|en cours|...|chargement|loading|génère/i.test(text.slice(-500));
      return {len: text.length, last400: text.slice(-400), hasGreeting, hasStreaming};
    })()''', 'returnByValue':True})
    v = state.get('result',{}).get('value',{})
    if v.get('hasGreeting'):
        print(f't+{i+1}s: GREETING DETECTED in tail!')
        print('last400:', v.get('last400'))
        break
    if i in (5, 15, 25):
        print(f't+{i+1}s: len={v.get("len")} streaming={v.get("hasStreaming")}')

shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':75})
out=r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit\conv_response.jpeg'
open(out,'wb').write(base64.b64decode(shot['data']))
print(f'shot: {out}')
cmd('Page.close'); ws.close()
