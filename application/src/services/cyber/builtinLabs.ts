/**
 * builtinLabs — lab(s) cyber STATIQUES, faits main, 100% fonctionnels et
 * autonomes. Sert de filet de sécurité : si le modèle local n'arrive pas à
 * forger un lab IA exploitable (petit modèle, JSON tronqué…), le module Cyber
 * sert quand même un vrai atelier jouable au lieu d'un message d'erreur.
 *
 * Le lab fourni est un mini-CTF crypto en chaîne (Base64 → ROT13 → XOR clé
 * répétée) avec : scénario, panneau Théorie, 3 outils interactifs réels,
 * objectifs auto-validés (postMessage), panneau Solution verrouillé. Le flag
 * est RÉELLEMENT dérivable par la manip — rien n'est codé en dur côté joueur.
 */
import type { Lab } from '../../hooks/useCyberViewLogic'

const CHAIN_LAB_HTML = `<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Atelier — Le message en oignon</title>
<style>
  :root{--bg:#0a0d12;--bg2:#10151c;--fg:#cfe3d6;--mute:#7d8a82;--neon:#5ad17a;--neon2:#2bd1c4;--amber:#e0a14b;--line:#1e2730;--bad:#e0584b}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;padding:14px}
  h1{font-size:18px;margin:0 0 4px;color:#eaf5ee}h2{font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:var(--neon);margin:18px 0 8px}
  .scn{color:var(--mute);font-style:italic;margin:0 0 4px}.warm{display:inline-block;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--amber);border:1px solid #3a2c14;background:#1c1509;border-radius:99px;padding:2px 8px;margin-bottom:8px}
  details{background:var(--bg2);border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:8px 0}summary{cursor:pointer;color:var(--neon2)}
  pre,code{background:#070a0e;border:1px solid var(--line);border-radius:6px}pre{padding:8px;overflow:auto;white-space:pre-wrap;word-break:break-all}code{padding:1px 5px}
  .tool{background:var(--bg2);border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0}.tool .tt{color:#eaf5ee;font-weight:700;margin-bottom:6px}
  textarea,input[type=text]{width:100%;background:#070a0e;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font:inherit}
  textarea{resize:vertical;min-height:42px}input[type=range]{width:100%}
  button{background:#16202a;color:var(--fg);border:1px solid #2a3742;border-radius:6px;padding:5px 12px;cursor:pointer;font:inherit}button:hover{border-color:var(--neon)}
  .out{margin-top:6px}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  .obj{display:flex;gap:8px;align-items:flex-start;padding:5px 0;border-top:1px dashed var(--line)}.obj:first-child{border-top:none}
  .obj .bx{flex:0 0 18px;height:18px;border:1px solid #2a3742;border-radius:4px;text-align:center;line-height:16px;color:#0a0d12}.obj.done .bx{background:var(--neon)}
  .obj.done .tx{color:var(--mute);text-decoration:line-through}.hint{color:var(--mute);font-size:11px}
  #log{background:#070a0e;border:1px solid var(--line);border-radius:6px;padding:8px;min-height:40px;max-height:140px;overflow:auto;font-size:11px;color:var(--mute)}
  .ok{color:var(--neon)}.ko{color:var(--bad)}.k{color:var(--amber)}
</style></head><body>
<div class="warm">Atelier de secours · hors-ligne · 100% jouable</div>
<h1>🧅 Le message en oignon</h1>
<p class="scn">Un coéquipier t'a laissé un blob suspect avant de disparaître. Trois couches de chiffrement amateur l'enveloppent. Épluche-les une par une — le drapeau est au cœur.</p>

<details><summary>📖 Théorie — les 3 couches</summary>
<p><b>1. Base64</b> : un <i>encodage</i> (pas du chiffrement) — 3 octets → 4 caractères dans l'alphabet <code>A-Za-z0-9+/</code>, parfois rembourré par <code>=</code>. Reconnaissable à cet alphabet. <code>atob()</code> le défait.</p>
<p><b>2. César / ROT13</b> : décalage circulaire des lettres. ROT13 = décalage de 13 (involutif : l'appliquer deux fois redonne l'original). Sur des chiffres hexadécimaux, seules les lettres <code>a-f</code> bougent. On casse un César inconnu par essais (26 décalages) ou par analyse de fréquences.</p>
<p><b>3. XOR à clé répétée</b> : chaque octet du message est XOR-é avec un octet de la clé, la clé se répétant en boucle (Vigenère binaire). <code>C = P ⊕ K</code> et, comme XOR est involutif, <code>P = C ⊕ K</code>. Si on connaît (ou devine) la clé, on retrouve tout. Schéma :</p>
<pre>P:  66 6c 61 67 ...
K:  41 55 52 4f 52 41 41 55 ...   (clé "AURORA" en boucle)
C:  P[i] XOR K[i % 6]</pre>
</details>

<h2>① Outil — Base64</h2>
<div class="tool"><div class="tt">Le blob à éplucher (couche 1) :</div>
<pre id="blob"></pre>
<div class="row"><button id="b64dec">atob() → décoder</button><span class="hint">colle le blob ci-dessus si besoin</span></div>
<textarea id="b64in" spellcheck="false"></textarea>
<div class="out">→ <span id="b64out" class="ko">(rien)</span></div></div>

<h2>② Outil — César / ROT13</h2>
<div class="tool"><div class="tt">Décale les lettres (essaie, ou mets 13 pour ROT13) :</div>
<textarea id="rotin" spellcheck="false" placeholder="colle ici la sortie de l'étape ①"></textarea>
<div class="row">décalage : <input type="range" id="rot" min="0" max="25" value="13"><code id="rotv">13</code><button id="rotgo">décaler</button></div>
<div class="out">→ <span id="rotout" class="ko">(rien)</span></div></div>

<h2>③ Outil — XOR à clé répétée</h2>
<div class="tool"><div class="tt">Le hex de l'étape ② XOR-é octet par octet avec ta clé (texte) :</div>
<textarea id="xin" spellcheck="false" placeholder="colle ici le HEX de l'étape ②"></textarea>
<div class="row">clé : <input type="text" id="xkey" placeholder="indice : 6 lettres, ce qui se lève à l'est…" style="max-width:240px"><button id="xgo">XOR</button></div>
<div class="out">→ <span id="xout" class="ko">(rien)</span></div></div>

<h2>🎯 Objectifs</h2>
<div id="objs">
  <div class="obj" data-id="o1"><div class="bx"></div><div><span class="tx">Décoder la couche Base64 (couche 1).</span><div class="hint">L'outil ①. Le résultat ressemble à de l'hex… mais bizarre.</div></div></div>
  <div class="obj" data-id="o2"><div class="bx"></div><div><span class="tx">Casser le César pour obtenir du vrai hexadécimal.</span><div class="hint">L'outil ②. ROT13 est involutif — essaie 13.</div></div></div>
  <div class="obj" data-id="o3"><div class="bx"></div><div><span class="tx">XOR le hex avec la bonne clé → trouver le flag.</span><div class="hint">L'outil ③. La clé est un mot de 6 lettres (cf. l'indice).</div></div></div>
  <div class="obj" data-id="o4"><div class="bx"></div><div><span class="tx">Bonus : soumets le flag complet ici.</span>
    <div class="row" style="margin-top:4px"><input type="text" id="flagin" placeholder="flag{...}" style="max-width:280px"><button id="flagsub">soumettre</button></div></div></div>
</div>

<h2>Journal</h2><div id="log">…</div>

<details><summary>🧩 Solution / write-up (à n'ouvrir qu'en dernier recours)</summary>
<ol>
<li><b>Couche 1 :</b> l'alphabet <code>A-Za-z0-9+/=</code> trahit du Base64. <code>atob(blob)</code> → une chaîne qui <i>ressemble</i> à de l'hex mais contient des lettres au-delà de <code>f</code> : c'est de l'hex décalé.</li>
<li><b>Couche 2 :</b> seules les lettres bougent ⇒ César. ROT13 (décalage 13) redonne un hex propre <code>[0-9a-f]+</code> de longueur paire.</li>
<li><b>Couche 3 :</b> on lit cet hex par paires d'octets, on XOR avec la clé répétée. L'indice « 6 lettres, ce qui se lève à l'est » ⇒ <code>AURORA</code>. <code>P[i] = octet[i] XOR "AURORA"[i % 6]</code> ⇒ <code>flag{...}</code>.</li>
</ol></details>

<script>
(function(){
  // --- crypto utils (vanilla) ---
  function rot13(s){return s.replace(/[a-zA-Z]/g,function(c){var b=c<="Z"?65:97;return String.fromCharCode((c.charCodeAt(0)-b+13)%26+b);});}
  function rotN(s,n){n=((n%26)+26)%26;return s.replace(/[a-zA-Z]/g,function(c){var b=c<="Z"?65:97;return String.fromCharCode((c.charCodeAt(0)-b+n)%26+b);});}
  function strToHex(s){return Array.from(s,function(ch){return ch.charCodeAt(0).toString(16).padStart(2,"0");}).join("");}
  function xorHexWithKey(hex,key){hex=hex.replace(/[^0-9a-fA-F]/g,"");var out="";for(var i=0;i+1<hex.length;i+=2){var b=parseInt(hex.substr(i,2),16);var k=key.charCodeAt((i/2)%key.length);out+=String.fromCharCode(b^k);}return out;}
  // --- le secret (tout calculé côté client : rien n'est codé en dur pour le joueur) ---
  var FLAG="flag{tr0is_couches_b64_rot_xor}";
  var KEY="AURORA";
  var enc=""; for(var i=0;i<FLAG.length;i++){enc+=String.fromCharCode(FLAG.charCodeAt(i)^KEY.charCodeAt(i%KEY.length));}
  var HEX_PROPRE=strToHex(enc);                 // étape 2 attendue : hex propre [0-9a-f], longueur paire
  var HEX_ROT=rot13(HEX_PROPRE);                // étape 1 attendue : ce hex passé en ROT13
  var BLOB=btoa(HEX_ROT);                        // couche 1, montrée au joueur
  document.getElementById("blob").textContent=BLOB;
  document.getElementById("b64in").value=BLOB;

  // --- état / log / validation ---
  var done={};
  function logL(html){var d=document.getElementById("log");d.innerHTML+=("<div>"+html+"</div>");d.scrollTop=d.scrollHeight;}
  function mark(id,flag){if(done[id])return;done[id]=true;var el=document.querySelector('.obj[data-id="'+id+'"]');if(el){el.classList.add("done");el.querySelector(".bx").textContent="✓";}
    try{window.parent.postMessage({type:"lab-flag",objectiveId:id,flag:flag||("done:"+id)},"*");}catch(e){}
    logL('<span class="ok">✓ objectif '+id+' validé'+(flag?(' — <span class="k">'+flag+'</span>'):'')+'</span>');}
  function norm(s){return (s||"").trim();}

  // --- outil 1 : base64 ---
  document.getElementById("b64dec").onclick=function(){
    var v=norm(document.getElementById("b64in").value);var r;
    try{r=atob(v);}catch(e){document.getElementById("b64out").className="ko";document.getElementById("b64out").textContent="Base64 invalide";logL('<span class="ko">atob() a échoué — vérifie le blob</span>');return;}
    document.getElementById("b64out").className="";document.getElementById("b64out").textContent=r;
    document.getElementById("rotin").value=r;
    if(r===HEX_ROT){mark("o1");logL("couche 1 ouverte → ça ressemble à de l'hex mais avec des lettres au-delà de f ⇒ encore décalé.");}
    else logL("décodé, mais ce n'est pas la couche attendue (re-vérifie le blob).");
  };
  // --- outil 2 : césar ---
  var rot=document.getElementById("rot"),rotv=document.getElementById("rotv");
  rot.oninput=function(){rotv.textContent=rot.value;};
  document.getElementById("rotgo").onclick=function(){
    var v=norm(document.getElementById("rotin").value);var r=rotN(v,parseInt(rot.value,10));
    document.getElementById("rotout").className="";document.getElementById("rotout").textContent=r;
    document.getElementById("xin").value=r;
    if(r===HEX_PROPRE){mark("o2");logL("César cassé (décalage "+rot.value+") → hex propre ["+"0-9a-f"+"]+ de longueur paire. Étape suivante : XOR.");}
    else if(/^[0-9a-f]+$/.test(r)&&r.length%2===0){logL("hex propre obtenu mais pas le bon — sûr du texte d'entrée ?");}
    else logL("pas encore de l'hex propre — essaie un autre décalage (13 ?).");
  };
  // --- outil 3 : xor ---
  document.getElementById("xgo").onclick=function(){
    var hex=norm(document.getElementById("xin").value);var key=norm(document.getElementById("xkey").value);
    if(!key){logL('<span class="ko">donne une clé (indice : 6 lettres, lever de soleil…)</span>');return;}
    var r=xorHexWithKey(hex,key);
    document.getElementById("xout").className="";document.getElementById("xout").textContent=r;
    if(r.indexOf("flag{")===0||r===FLAG){mark("o3",FLAG);logL('<span class="ok">🎉 flag récupéré — bravo. Tu peux aussi le soumettre dans le bonus.</span>');document.getElementById("flagin").value=r;}
    else if(/^[0-9a-f]/i.test(key)){logL("la clé est un MOT (lettres), pas du hex.");}
    else logL("clé incorrecte — le résultat est illisible. Relis l'indice.");
  };
  // --- outil 4 : soumission du flag ---
  document.getElementById("flagsub").onclick=function(){
    var v=norm(document.getElementById("flagin").value);
    if(v===FLAG){mark("o4",FLAG);if(!done["o3"])mark("o3",FLAG);logL('<span class="ok">flag confirmé ✔ atelier terminé.</span>');}
    else logL('<span class="ko">ce n\\'est pas le bon flag.</span>');
  };
  logL("Atelier prêt. Commence par l'outil ① (Base64) avec le blob ci-dessus.");
})();
</script>
</body></html>`

/**
 * Renvoie un lab statique jouable pour servir de filet de sécurité quand la
 * forge IA échoue. `kataName` / `discipline` ne servent qu'à habiller le titre.
 */
export function getBuiltinFallbackLab(kataId: string, _kataName?: string, _discipline?: string): Lab {
  return {
    kataId,
    title: 'Le message en oignon — atelier de secours',
    briefing:
      "La forge IA n'a pas abouti cette fois — voici un vrai atelier crypto hors-ligne (Base64 → César/ROT13 → XOR à clé répétée) pour ne pas rester bloqué. Épluche les trois couches, le flag est au cœur. Relance « Démarrer l'atelier » pour retenter un lab IA sur-mesure.",
    objectives: [
      { id: 'o1', text: 'Décoder la couche Base64 (couche 1).', hint: "Outil ①. atob(). Le résultat ressemble à de l'hex… déformé." },
      { id: 'o2', text: 'Casser le César pour obtenir du vrai hexadécimal.', hint: 'Outil ②. ROT13 est involutif — essaie un décalage de 13.' },
      { id: 'o3', text: 'XOR le hex avec la bonne clé → trouver le flag.', hint: "Outil ③. La clé est un mot de 6 lettres (cf. l'indice dans le lab)." },
      { id: 'o4', text: 'Bonus : soumettre le flag complet.', hint: 'Format flag{...}.' },
    ],
    html: CHAIN_LAB_HTML,
  }
}
