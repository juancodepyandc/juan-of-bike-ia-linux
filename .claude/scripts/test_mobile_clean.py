"""Clean test: wipe ALL localStorage, navigate fresh, screenshot the true cover."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'

for skin in ['aurora_v1','aurora_v3']:
    print(f'\n=== mobile {skin} CLEAN ===')
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
    # WIPE all localStorage + set only the skin
    cmd('Runtime.evaluate', {'expression': f'''(()=>{{try{{
      localStorage.clear();
      localStorage.setItem('aurora-ui-skin','{skin}');
      localStorage.setItem('aurora_build_id_html','v82s-studio');
    }}catch(_){{}}}}'''+'})()'})
    cmd('Page.reload'); time.sleep(10)
    state = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const skin=document.documentElement.getAttribute('data-ui-skin');
      const isGrimoire=!!document.querySelector('.g-root');
      const cards=Array.from(document.querySelectorAll('button')).filter(b=>(b.textContent||'').replace(/\s+/g,' ').trim().length>2).slice(0,15).map(b=>(b.textContent||'').replace(/\s+/g,' ').trim().slice(0,28));
      const hasSphere=!!document.querySelector('canvas');
      const headerText=Array.from(document.querySelectorAll('h1,div')).slice(0,5).map(e=>(e.textContent||'').trim().slice(0,30)).filter(t=>t);
      return {skin, isGrimoire, cardCount:cards.length, cards, hasSphere, bodyLen:document.body.innerText.length, snippet:document.body.innerText.slice(0,200).replace(/\n/g,' | ')};
    })()''', 'returnByValue':True}).get('result',{}).get('value',{})
    print(f'  skin={state.get("skin")} grimoire={state.get("isGrimoire")} cards={state.get("cardCount")} sphere={state.get("hasSphere")}')
    print(f'  cards: {state.get("cards",[])[:10]}')
    print(f'  snippet: {state.get("snippet","")[:160]}')
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':78})
    if shot and 'data' in shot:
        open(os.path.join(OUT, f'mobile_{skin}_TRUE_cover.jpeg'),'wb').write(base64.b64decode(shot['data']))
    cmd('Page.close'); ws.close()
