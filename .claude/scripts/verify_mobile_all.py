"""iter11: comprehensive mobile sweep — V1 shell, tap every module card in the deck,
confirm no horizontal overflow + useful UI rendered. Both skins."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'
BUILD='v82s-studio10'

def sweep(skin):
    print(f'\n=== mobile {skin} ===')
    r = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(TUNNEL+"/?device=mobile", safe=":/?=&")}', method='PUT')
    nt = json.load(urllib.request.urlopen(r))
    ws = websocket.create_connection(nt['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
    mid=[0]
    def cmd(m,p=None):
        mid[0]+=1; msg={'id':mid[0],'method':m}
        if p is not None: msg['params']=p
        ws.send(json.dumps(msg))
        while True:
            rr=json.loads(ws.recv())
            if rr.get('id')==mid[0]: return rr.get('result',{}) if 'error' not in rr else {'__err':rr['error']}
    cmd('Page.enable'); cmd('Runtime.enable')
    cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':2,'mobile':True})
    cmd('Emulation.setTouchEmulationEnabled', {'enabled':True})
    cmd('Runtime.evaluate', {'expression': f'(()=>{{try{{localStorage.clear();localStorage.setItem("aurora-ui-skin","{skin}");localStorage.setItem("aurora_build_id_html","{BUILD}");}}catch(_){{}}}})()'})
    cmd('Page.reload'); time.sleep(11)
    # enumerate module entry buttons (deck cards / numbered cards)
    entries = cmd('Runtime.evaluate', {'expression': r'''(()=>{
      const bs=Array.from(document.querySelectorAll('button'));
      // filter to ones whose text mentions a module name and are reasonably short
      const names=['chat','conversation','image','code','dessin','draw','atelier','3d','vidéo','video','académie','academy','cyber','dictaphone','codex','lightbox','blueprint','mission','studio'];
      const seen=new Set(); const out=[];
      for(const b of bs){const t=(b.textContent||'').replace(/\s+/g,' ').trim(); const lt=t.toLowerCase();
        if(t.length<3||t.length>40) continue;
        const hit=names.find(n=>lt.includes(n)); if(!hit) continue;
        if(seen.has(hit)) continue; seen.add(hit); out.push({label:t.slice(0,30), key:hit});
        if(out.length>=12) break;
      }
      return out;
    })()''', 'returnByValue':True}).get('result',{}).get('value',[])
    print(f'  entries found: {[e["key"] for e in entries]}')
    results=[]
    for e in entries:
        # back to cover
        cmd('Runtime.evaluate', {'expression': r'''(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>/^←|retour/i.test((b.textContent||'').trim()));if(b)b.click();})()'''})
        time.sleep(1.0)
        clicked = cmd('Runtime.evaluate', {'expression': f'''(()=>{{
          const bs=Array.from(document.querySelectorAll('button'));
          const b=bs.find(b=>(b.textContent||'').replace(/\\s+/g,' ').trim().slice(0,30)==={json.dumps(e["label"])});
          if(b){{b.click();return 1}}
          // fallback by key
          const b2=bs.find(b=>(b.textContent||'').toLowerCase().includes({json.dumps(e["key"])})&&(b.textContent||'').length<40);
          if(b2){{b2.click();return 2}} return 0;
        }})()''', 'returnByValue':True}).get('result',{}).get('value')
        time.sleep(3.5)
        probe = cmd('Runtime.evaluate', {'expression': r'''(()=>{
          const hOver=(document.documentElement.scrollWidth-document.documentElement.clientWidth)>6;
          const t=document.body.innerText; const len=t.length;
          const back=!!Array.from(document.querySelectorAll('button')).find(b=>/^←|retour/i.test((b.textContent||'').trim()));
          // any element wider than viewport+8?
          let wideEl=null; const all=document.querySelectorAll('*');
          for(let i=0;i<all.length;i++){const rr=all[i].getBoundingClientRect(); if(rr.width>window.innerWidth+12 && rr.height>20){wideEl=(all[i].className||all[i].tagName||'').toString().slice(0,30);break;}}
          return {hOver, len, back, wideEl};
        })()''', 'returnByValue':True}).get('result',{}).get('value',{})
        ok = (clicked and probe.get('len',0)>120 and not probe.get('hOver'))
        results.append((e['key'], clicked, ok, probe))
        print(f"  {e['key']:14s} click={clicked} hOver={probe.get('hOver')} back={probe.get('back')} len={probe.get('len')} wideEl={probe.get('wideEl')} {'OK' if ok else 'CHECK'}")
    cmd('Page.close'); ws.close()
    return results

sweep('aurora_v1')
sweep('aurora_v3')
print('\nDONE')
