"""Send v11 prompt to Claude Design via CDP — bypass MCP."""
import json, urllib.request, websocket, time, sys

PROMPT = """Aurora V11 — STUDIO RÉALISTE · enfin "incroyable au scroll".

V10 a progressé (40 keyframes, lumière par scène, FightCloud présent) mais les portraits restent trop blob au scale rendu — iris, sourcils, cils, lèvres ne sont pas lisibles à la taille où l'utilisateur les voit. Et Roster XII reste fade. Corrige radicalement.

═══ A. PORTRAITS LISIBLES À LA BONNE TAILLE ═══

ROSTER XII RÉINVENTÉ : 7 portraits ¾ face, AGRANDIS à 380×540px chacun, disposés en grille 4 + 3 (pas 7 mini), fond gradient studio par persona avec rim light. À cette taille, je dois voir DISTINCTEMENT à l'écran :
- 2 yeux ouverts avec sclère blanche + iris coloré (gradient 4 stops visible) + pupille noire + reflet blanc identifiable
- 2 sourcils dessinés en arc avec 4-6 traits courts pour le poil
- Nez avec 2 narines visibles + reflet sur arête + ombre côté
- Bouche avec lèvre sup et inf séparées, dents si sourire (4 dents centrales)
- Oreilles avec hélix visible
- 12-18 mèches de cheveux individuelles
- Joues avec gradient rosé
- Cou avec ombre et clavicules
- Vêtement signature avec plis, col, boutons (Sage manteau ¾ + écharpe / Lou hoodie zip + cordons / Mira tablier taché + bandana / Diego hoodie + casque / Tess blazer + lunettes pendantes / Sam pull mailles + col roulé / Yann oxford + cravate)

Test : si je zoome à 100% sur n'importe quel portrait Roster, je dois reconnaître la personne au visage SEUL sans étiquette.

COWORK ISO : réduis le nombre de stations à 4 visibles bien placées (Lou + Mira + Diego + Sam, Sage marche au centre, Tess + Yann en arrière-plan flou) et rapproche la caméra pour que CHAQUE persona soit affiché à 200×260 minimum, pas 80px. À 200×260, mêmes critères : iris+sourcils+lèvres+cheveux strands lisibles.

═══ B. FIGHTCLOUD VRAIMENT WAOUH ═══

C1 IMAGE diffusion : nuage 600×360 (pas 380×220), occupe 40% de la scène. POW! en Caveat 96px JAUNE avec contour noir 4px + drop-shadow rouge. 8 limb-pokes qui dépassent de 60% du nuage avec speed-lines blanches. Étincelles rouges + jaunes radiales (24 étincelles). Onomatopée OFFSCREEN-style (rotated -8°, sortie franche du cadre du nuage).

C2 3D forge : nuage 640×400. BOOM! en Caveat 110px ORANGE FEU avec contour noir + glow. 6 limb-pokes (marteau XL + clé + tournevis + bras casque + jambe + roue). Sparks oranges en explosion radiale 30 particules. Fumée grise qui monte au-dessus avec 5 cumulus.

C3 CODE test failed : nuage 540×320. CRACK! en Caveat 100px ROUGE SANG avec contour blanc + glow rouge. 4 limb-pokes (clavier en 3 morceaux + souris + bras + post-it). Lignes ASCII >>> ERROR FAIL qui giclent en typo Mono rouge. Fumée grise.

ANTICIPATION : avant chaque limb-poke, le nuage tremble (cloud-shake) 250ms à fréquence 8Hz. Après chaque limb-poke, follow-through 200ms d'amorti.

═══ C. UIs RÉELLEMENT FONCTIONNELLES ═══

CONVERSATION : zone draft chat où les 10 lignes du draft s'écrivent caractère par caractère en streaming (write-stream class avec letter-spacing animation OU stroke-dasharray sur SVG text). Curseur clignotant à la fin. Citation [1] [2] [3] qui POPent (scale 0→1 + opacity) avec 600ms d'écart. Pipeline étape 5 (Compose) avec vraie barre qui progresse 0→87% en 5s puis reset.

CODE : éditeur monospace affiche def run(src, dst):\\n    df = pl.read_database(src)\\n    df = df.with_columns([pl.col("created_at").cast(pl.Datetime), pl.col("price").fill_null(0)])\\n    return df.write_database(dst) — chaque caractère apparaît en stream sur 6s. Terminal en bas affiche "$ pytest -k etl" en stream, puis "FAILED 1/412 schema drift" en rouge, déclenche FightCloud CRACK!, puis "retry · auto-fix · L4 → L5", puis "✓ 412/412 in 4.3s" en vert. Cycle complet 12s avant reset.

3D : score 79 → 84 → 89 → 93 → 97 progresse en 5 paliers de 800ms chacun, chaque palier déclenche une mini particle burst. Wireframe → textured transition à mi-parcours.

VOIX : 28 formant bars avec autocorrélation visible (les bars adjacentes ondulent ensemble selon F0=120Hz simulé), pas chacune indépendante.

═══ D. ANIMATIONS PIXAR INSPECTABLES ═══

À chaque persona dans la scène et le roster :
- breathing : torse oscille ±3px Y + ±2px X drift léger (pas que vertical)
- head-turn : ±5° en arc cubic-bezier(.4,0,.2,1), cheveux follow 80ms après
- blink : paupière scaleY .05 sur 120ms ease-in puis 80ms ease-out, joues squash légèrement
- micro-saccade : pupilles ±1.5px toutes 2-4s
- secondary : pendant Lou typing, sourcils froncés ; pendant Mira brush, langue qui sort coin bouche ; pendant Diego speak, sourcils qui montent à l'accent

DELAYS UNIQUES par persona : style={animationDelay:`${(seed*Math.PI*0.7).toFixed(2)}s`} pour casser le sync robotique.

═══ E. PARITÉ AURORA V1 (rappel obligatoire) ═══

Toutes les chips et fonctionnalités v9/v10 préservées :
- Conversation 6 étapes + score 94 + 3 modèles
- Image FLUX 15 styles + denoise 0.92 + brand 96/100
- Vidéo Wan2.2 + 5 motion presets + MuseTalk + visemes A-Z
- 3D 4 routeurs + 33 motions + rescue 79→97 + Rigify + PBR
- Code 22 langs + L1→L5 + brand-fidelity 96/100 + 16 productShape
- Voix Voxtral + Kokoro + Rhubarb + 28 formants
- Dessin qwen3-vl + denoise 0.88-0.97
- Academy BAC 12 + Anki + LabAssistant + Clarif
- Cyber 9 labs + _safety.py + radar
- Cowork-Connect Chrome ext + 12 connectors + safety_limits

═══ F. FORMAT DE SORTIE ═══

6 fichiers v11 : Aurora_v11.html (boot mission-control gradient violet→cyan + entrée 14 scènes), design-canvas.jsx (conserver), v11/avatars.jsx (PORTRAITS LISIBLES + 40+ keyframes), v11/scenes-1.jsx, v11/scenes-2.jsx, v11/scenes-3.jsx.

H1 = "AURORA V11 — STUDIO RÉALISTE" · sous-titre = "Aurora v1 → v3 swap · 14 scènes · 7 portraits illustration éditoriale lisibles · UIs fonctionnelles streaming · FightCloud × 3 dramatique"

═══ G. AUTO-VETO ═══

Refais avant de me rendre si :
- Roster portrait < 380×540 ou < 4 traits sourcils visibles
- Cowork persona < 200×260 ou faces illisibles
- FightCloud onomatopée < 80px ou nuage < 500px largeur
- Code/Conversation pas de write-stream visible
- Score 79→97 pas de palier visible
- limb-poke total ≠ 18
- Pas d'anticipation cloud-shake avant FightCloud
- Pas de delays animation uniques par persona

GO. Si en doute, GROSSIS plus, dessine plus."""

BASE = 'http://localhost:9222'
tabs = json.load(urllib.request.urlopen(f'{BASE}/json'))
design = next((t for t in tabs if 'claude.ai/design/p/' in t.get('url','')), None)
if not design: print('no design tab'); sys.exit(1)
print('tab:', design['url'][:100])

ws = websocket.create_connection(design['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
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

# Make sure we're on a non-present view of v10
cmd('Page.navigate', {'url': design['url'].split('&present')[0].split('?present')[0]})
time.sleep(3)

# Focus textarea + clear it
cmd('Runtime.enable')
focus = cmd('Runtime.evaluate', {'expression': r'(()=>{const ta=document.querySelector("textarea[placeholder*=\"Describe\"]");if(!ta)return{ok:false};ta.focus();ta.select();return{ok:true,id:ta.id};})()', 'returnByValue': True})
print('focus:', focus.get('result',{}).get('value'))
time.sleep(0.5)

# Use Input.insertText to type (works with React controlled inputs)
# Split into chunks to avoid CDP message size limits
CHUNK = 4000
parts = [PROMPT[i:i+CHUNK] for i in range(0, len(PROMPT), CHUNK)]
print(f'inserting {len(PROMPT)} chars in {len(parts)} chunks')
for i, p in enumerate(parts):
    cmd('Input.insertText', {'text': p})
    time.sleep(0.3)
print('insert done')

# Verify content
val = cmd('Runtime.evaluate', {'expression': r'(()=>{const ta=document.querySelector("textarea[placeholder*=\"Describe\"]");return ta?ta.value.length:-1;})()', 'returnByValue': True})
print('textarea length:', val.get('result',{}).get('value'))

# Click Send
res = cmd('Runtime.evaluate', {'expression': r'(()=>{const b=Array.from(document.querySelectorAll("button")).find(x=>/send/i.test(x.getAttribute("aria-label")||x.textContent||"")&&!x.disabled);if(b){b.click();return{clicked:true};}return{clicked:false};})()', 'returnByValue': True})
print('send:', res.get('result',{}).get('value'))

ws.close()
print('done')
