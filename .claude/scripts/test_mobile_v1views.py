"""iter9: mobile V1 module views — tap dock/card → module → check the useful content is on-screen
(no horizontal overflow burying the real UI), screenshot each."""
import json, urllib.request, urllib.parse, websocket, base64, sys, time, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
TUNNEL = open(r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\tunnel_url.txt', encoding='utf-8-sig').read().strip()
OUT = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\full_audit'
os.makedirs(OUT, exist_ok=True)
BUILD='v82s-studio10'

# We open the V1 mobile shell and tap module cards in the deck. The deck cards
# are buttons whose text starts with a glyph then the label. We also have the
# bottom dock with [L'équipe, Chat, Image, Code, Académie].
MODS = [('Chat','conversation','/dictaphone|conversation|copilote|balance ton défi/i'),
        ('Image','image','/style wheel|imago|flux|denoise|planche/i'),
        ('Code','code','/orchestrateur|before|after|streaming|aurora\\.codex|modèles actifs/i'),
        ('Académie','learning','/parcours|quiz|académie|academy|leçon|bac/i')]

r = urllib.request.Request(f'http://localhost:9222/json/new?{urllib.parse.quote(TUNNEL+"/?device=mobile", safe=":/?=&")}', method='PUT')
new_tab = json.load(urllib.request.urlopen(r))
ws = websocket.create_connection(new_tab['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
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
cmd('Runtime.evaluate', {'expression': f'''(()=>{{try{{localStorage.clear();localStorage.setItem('aurora-ui-skin','aurora_v1');localStorage.setItem('aurora_build_id_html','{BUILD}');}}catch(_){{}}}}'''+'})()'})
cmd('Page.reload'); time.sleep(11)

for label, modid, rx in MODS:
    # back to cover first
    cmd('Runtime.evaluate', {'expression': r'''(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>/^←|retour/i.test((b.textContent||'').trim()));if(b)b.click();})()'''})
    time.sleep(1.2)
    # tap dock button
    tapped = cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      const b=Array.from(document.querySelectorAll('button[aria-label]')).find(b=>b.getAttribute('aria-label')==={json.dumps(label)});
      if(b){{b.click();return 'tap'}} return 'miss'
    }})()''', 'returnByValue':True}).get('result',{}).get('value')
    time.sleep(4)
    probe = cmd('Runtime.evaluate', {'expression': f'''(()=>{{
      const scroller=document.scrollingElement||document.documentElement;
      const hOver = (document.documentElement.scrollWidth - document.documentElement.clientWidth) > 4;
      const txt=document.body.innerText;
      const hasUsefulUI = ({rx}).test(txt);
      // is there an obvious column-grid root still showing 2+ cols? measure first .aurora-v1-cols
      const colsEl=document.querySelector('.aurora-v1-cols');
      let gtc='n/a'; if(colsEl){{gtc=getComputedStyle(colsEl).gridTemplateColumns;}}
      // a text input/textarea reachable?
      const ta=document.querySelector('textarea, input[type="text"]');
      let inputOk=null; if(ta){{const rr=ta.getBoundingClientRect(); inputOk = rr.width>120 && rr.left>=-4 && rr.right<=window.innerWidth+4;}}
      return {{hOver, hasUsefulUI, gridTemplateColumns:gtc, inputOk, bodyLen:txt.length}};
    }})()''', 'returnByValue':True}).get('result',{}).get('value',{})
    shot = cmd('Page.captureScreenshot', {'format':'jpeg','quality':70})
    if shot and 'data' in shot: open(os.path.join(OUT,f'mobv1_{modid}.jpeg'),'wb').write(base64.b64decode(shot['data']))
    print(f'{label:10s} tap={tapped} hOverflow={probe.get("hOver")} usefulUI={probe.get("hasUsefulUI")} cols={probe.get("gridTemplateColumns")} inputOk={probe.get("inputOk")} bodyLen={probe.get("bodyLen")}')
cmd('Page.close'); ws.close()
print('OK')
