import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import { readFileSync } from 'node:fs'
import path from 'node:path'
const mem = new Map()
const ls = { getItem:(k)=>mem.has(k)?mem.get(k):null, setItem:(k,v)=>mem.set(k,String(v)), removeItem:(k)=>mem.delete(k), clear:()=>mem.clear(), key:(i)=>Array.from(mem.keys())[i]??null, get length(){return mem.size} }
const noop=()=>{}
globalThis.localStorage=ls
globalThis.window={location:{hostname:'localhost',href:'http://localhost/',origin:'http://localhost'},localStorage:ls,addEventListener:noop,removeEventListener:noop,matchMedia:()=>({matches:false,addEventListener:noop,removeEventListener:noop})}
globalThis.document={documentElement:{setAttribute:noop,classList:{add:noop,remove:noop,toggle:noop}},body:{setAttribute:noop},addEventListener:noop,createElement:()=>({setAttribute:noop,style:{},appendChild:noop}),querySelector:()=>null}
register('./hooks.mjs', import.meta.url)
const { checkWebPageIntegrity } = await import(pathToFileURL(path.resolve('src/services/codeOrchestrator.ts')).href)
const prompt = 'dashboard fintech temps réel, graphique live setInterval, tableau triable filtrable, convertisseur, toggle thème'

// CASE 1: the actual broken page (index.html refs script.js which is absent)
const D='output/code-tests/fintech_real'
const broken=[{name:'index.html',content:readFileSync(path.join(D,'index.html'),'utf8')},{name:'style.css',content:readFileSync(path.join(D,'style.css'),'utf8')}]
const r1=checkWebPageIntegrity(broken,prompt)
console.log('CASE1 broken page  -> ok=%s missing=%j', r1.ok, r1.missing)

// CASE 2: healthy page — inline script with getContext + populated tbody + real logic
const good=[{name:'index.html',content:`<!doctype html><html><head><link href="style.css" rel="stylesheet"></head>
<body><canvas id="c"></canvas><table><tbody id="t"></tbody></table>
<script>const ctx=document.getElementById('c').getContext('2d');function draw(){ctx.fillRect(0,0,10,10);}setInterval(draw,1000);document.getElementById('t').innerHTML='<tr><td>AAPL</td></tr>';</script></body></html>`},{name:'style.css',content:'body{color:#fff}'}]
const r2=checkWebPageIntegrity(good,prompt)
console.log('CASE2 healthy page -> ok=%s missing=%j', r2.ok, r2.missing)

// CASE 3: static landing with no interactivity demanded, no JS -> should pass
const r3=checkWebPageIntegrity([{name:'index.html',content:'<!doctype html><html><body><h1>Hello</h1><p>Static.</p></body></html>'}],'une page vitrine simple statique')
console.log('CASE3 static landing-> ok=%s missing=%j', r3.ok, r3.missing)
