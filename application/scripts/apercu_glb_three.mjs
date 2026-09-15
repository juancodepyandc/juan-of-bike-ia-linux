#!/usr/bin/env node
/**
 * Rend un GLB dans le VRAI three.js (headless, meme version que ModelView) et
 * ecrit une capture PNG + la liste des materiaux tels que three.js les voit.
 *
 * Pourquoi ce banc existe: Blender ne dit PAS ce que ModelView affiche.
 *  - Cycles trace les rayons: il montre un liquide enferme derriere du verre,
 *    donc il MASQUE les defauts propres a un rasteriseur.
 *  - EEVEE trace en espace ecran: il ne voit jamais un objet entierement
 *    couvert par une paroi refractive, donc il declare invisible ce que
 *    three.js, lui, affiche tres bien (three.js exclut les objets transmissifs
 *    de sa cible de transmission, si bien que le verre n'y occulte rien).
 * Les deux mentent, dans des directions opposees. Seul three.js fait foi.
 *
 * Usage: node apercu_glb_three.mjs <modele.glb> <sortie.png> [azimut_deg]
 */
import { chromium } from 'playwright';
import { mkdtemp, cp, writeFile, rm } from 'node:fs/promises';
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, extname, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const [glb, sortie, azStr] = process.argv.slice(2);
if (!glb || !sortie) { console.error('usage: apercu_glb_three.mjs <glb> <png> [azimut]'); process.exit(2); }
const az = Number(azStr || 0) * Math.PI / 180;
const RACINE = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const THREE_DIR = join(RACINE, 'node_modules', 'three');

const dir = await mkdtemp(join(tmpdir(), 'apercu-three-'));
// three 0.183 eclate son build en plusieurs fichiers (three.core.js) et
// GLTFLoader importe ../utils/* en relatif: il faut reproduire l'arborescence.
await cp(join(THREE_DIR, 'build'), dir, { recursive: true });
for (const rel of ['loaders/GLTFLoader.js', 'utils/BufferGeometryUtils.js',
                   'utils/SkeletonUtils.js', 'environments/RoomEnvironment.js']) {
  await cp(join(THREE_DIR, 'examples/jsm', rel), join(dir, 'jsm', rel), { recursive: true });
}
await cp(resolve(glb), join(dir, 'model.glb'));
await writeFile(join(dir, 'index.html'), page(az));

const serveur = createServer(async (req, res) => {
  try {
    const f = join(dir, decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '') || 'index.html');
    const buf = await readFile(f);
    const t = { '.js': 'text/javascript', '.html': 'text/html', '.glb': 'model/gltf-binary' }[extname(f)] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': t }); res.end(buf);
  } catch { res.writeHead(404); res.end('non trouve'); }
});
await new Promise(r => serveur.listen(0, '127.0.0.1', r));
const port = serveur.address().port;

const nav = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader',
  '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-dev-shm-usage', '--no-sandbox'] });
const p = await nav.newPage({ viewport: { width: 900, height: 900 } });
p.on('pageerror', e => console.error('[erreur page]', String(e).slice(0, 300)));
await p.goto(`http://127.0.0.1:${port}/index.html`, { waitUntil: 'load', timeout: 120000 });
let etat = 'inconnu';
try { await p.waitForFunction("window.__etat==='pret'", { timeout: 900000 }); etat = 'pret'; }
catch { etat = await p.evaluate('window.__etat'); }
const mats = await p.evaluate('window.__mats') || [];
console.log('etat:', etat);
console.log('MATERIAUX VUS PAR THREE.JS:');
for (const m of mats) console.log(' ', JSON.stringify(m));
await p.screenshot({ path: resolve(sortie) });
console.log('capture:', resolve(sortie));
await nav.close(); serveur.close(); await rm(dir, { recursive: true, force: true });

function page(az) { return `<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:#c9cbd0}canvas{display:block}</style></head><body>
<script>window.__etat='demarrage';window.onerror=(m)=>{window.__etat='erreur:'+m};</script>
<script type="importmap">{"imports":{"three":"./three.module.js","three/addons/":"./jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from './jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from './jsm/environments/RoomEnvironment.js';
window.__etat='modules_ok';
function demarrer(){
  const r=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
  r.setSize(900,900); r.setPixelRatio(1);
  r.toneMapping=THREE.ACESFilmicToneMapping; r.outputColorSpace=THREE.SRGBColorSpace;
  document.body.appendChild(r.domElement);
  const sc=new THREE.Scene(); sc.background=new THREE.Color(0xc9cbd0);
  sc.environment=new THREE.PMREMGenerator(r).fromScene(new RoomEnvironment(),0.04).texture;
  const cam=new THREE.PerspectiveCamera(28,1,0.01,100);
  const k=new THREE.DirectionalLight(0xffffff,2.2); k.position.set(2,2.4,3); sc.add(k);
  const f2=new THREE.DirectionalLight(0xffffff,1.0); f2.position.set(-3,1.2,1.5); sc.add(f2);
  sc.add(new THREE.AmbientLight(0xffffff,0.5));
  window.__etat='chargement';
  new GLTFLoader().load('./model.glb',(g)=>{
    sc.add(g.scene);
    const b=new THREE.Box3().setFromObject(g.scene);
    const c=b.getCenter(new THREE.Vector3()), s=b.getSize(new THREE.Vector3());
    const d=Math.max(s.x,s.y,s.z), A=${az};
    cam.position.set(c.x+d*3.4*Math.sin(A), c.y+d*0.03, c.z+d*3.4*Math.cos(A)); cam.lookAt(c);
    const ms=[]; g.scene.traverse(n=>{ if(n.isMesh){
      (Array.isArray(n.material)?n.material:[n.material]).forEach(m=>ms.push({
        nom:m.name,type:m.type,transmission:m.transmission??0,ior:m.ior??null,
        thickness:m.thickness??null,metalness:m.metalness??null,roughness:m.roughness??null,
        side:m.side,couleur:m.color?m.color.getHexString():null,aMap:!!m.map,
        tris:n.geometry.index?n.geometry.index.count/3:0})); }});
    window.__mats=ms;
    let i=0;(function bcl(){ r.render(sc,cam); if(++i<12) requestAnimationFrame(bcl); else window.__etat='pret'; })();
  },undefined,(e)=>{ window.__etat='erreur_glb:'+e; });
}
try{ demarrer(); }catch(e){ window.__etat='exception:'+e; }
</script></body></html>`; }
