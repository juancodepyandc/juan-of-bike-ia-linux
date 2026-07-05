"""Test mobile flow on both skins: cover (no overlapping CTA) → tap module card → slide-in fullscreen."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'

for skin in ['aurora_v1','aurora_v3']:
    print(f'\n=== mobile {skin} ===')
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
    cmd('Runtime.evaluate', {'expression': f'(()=>{{try{{localStorage.setItem("aurora-ui-skin","{skin}");localStorage.removeItem("ft-grimoire-page");}}catch(_){{}}}}'+'})()'})
    cmd('Page.reload'); time.sleep(9)
    # cover
    cover = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const overlapCTA = !!Array.from(document.querySelectorAll('button')).find(b=>/ouvrir le grimoire/i.test(b.textContent||''));
      const cards = Array.from(document.querySelectorAll('button')).filter(b=>(b.textContent||'').trim().length>2).slice(0,12).map(b=>(b.textContent||'').replace(/\s+/g,' ').trim().slice(0,30));
      return {overlapCTA, cardCount: cards.length, hasTeam: cards.some(c=>/équipe|equipe/i.test(c))};
    })()''', 'returnByValue':True}).get('result',{}).get('value',{})
    print(f'  cover: overlappingCTA_removed={not cover.get("overlapCTA")} cards={cover.get("cardCount")} hasTeam={cover.get("hasTeam")}')
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':75})
    if shot and 'data' in shot:
        open(os.path.join(OUT, f'mobile_{skin}_cover_clean.jpeg'),'wb').write(base64.b64decode(shot['data']))
    # tap Image card
    tap = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const card=Array.from(document.querySelectorAll('button')).find(b=>/^◐\s*Image|Image\s*tap|Image$/.test((b.textContent||'').replace(/\s+/g,' ').trim()) || (b.textContent||'').replace(/\s+/g,' ').trim().startsWith('◐ Image') || /Image/.test(b.textContent||'') && (b.textContent||'').length<20);
      if(card){card.click();return 'tap '+(card.textContent||'').slice(0,20)} return 'miss'
    })()''', 'returnByValue':True}).get('result',{}).get('value')
    print(f'  tap Image: {tap}')
    time.sleep(0.5)  # catch the slide-in mid-anim
    has_anim = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const el = document.querySelector('.aurora-mobile-slide-in');
      const cs = el ? getComputedStyle(el) : null;
      return {hasSlideClass: !!el, animationName: cs?cs.animationName:'none'};
    })()''', 'returnByValue':True}).get('result',{}).get('value',{})
    print(f'  slide-in: {has_anim}')
    time.sleep(3)
    mod = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const text=document.body.innerText;
      const moduleMounted=/imago|planche|flux|prompt|denoise|image/i.test(text.slice(0,400));
      const backBtn=!!Array.from(document.querySelectorAll('button')).find(b=>/^←|retour/i.test((b.textContent||'').trim()));
      return {moduleMounted, backBtn, bodyLen:text.length};
    })()''', 'returnByValue':True}).get('result',{}).get('value',{})
    print(f'  module: mounted={mod.get("moduleMounted")} backBtn={mod.get("backBtn")} bodyLen={mod.get("bodyLen")}')
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':75})
    if shot and 'data' in shot:
        open(os.path.join(OUT, f'mobile_{skin}_module_image.jpeg'),'wb').write(base64.b64decode(shot['data']))
    # back
    cmd('Runtime.evaluate', {'expression': r'''(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>/^←|retour/i.test((b.textContent||'').trim()));if(b)b.click()})()'''})
    time.sleep(1.5)
    back_ok = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const cards=Array.from(document.querySelectorAll('button')).filter(b=>/équipe|chat|image|code/i.test(b.textContent||'')).length;
      return {backToCover: cards>=3};
    })()''', 'returnByValue':True}).get('result',{}).get('value',{})
    print(f'  back: backToCover={back_ok.get("backToCover")}')
    cmd('Page.close'); ws.close()
