import { register } from 'node:module'; import { pathToFileURL } from 'node:url'; import { readFileSync } from 'node:fs'; import path from 'node:path'
const mem=new Map(); const ls={getItem:(k)=>mem.has(k)?mem.get(k):null,setItem:(k,v)=>mem.set(k,String(v)),removeItem:(k)=>mem.delete(k),clear:()=>mem.clear(),key:(i)=>[...mem.keys()][i]??null,get length(){return mem.size}}; const noop=()=>{}
globalThis.localStorage=ls; globalThis.window={location:{hostname:'localhost',href:'http://localhost/',origin:'http://localhost'},localStorage:ls,addEventListener:noop,removeEventListener:noop,matchMedia:()=>({matches:false,addEventListener:noop,removeEventListener:noop})}; globalThis.document={documentElement:{setAttribute:noop,classList:{add:noop,remove:noop,toggle:noop}},body:{setAttribute:noop},addEventListener:noop,createElement:()=>({setAttribute:noop,style:{},appendChild:noop}),querySelector:()=>null}
register('./hooks.mjs', import.meta.url)
const { checkWebPageIntegrity } = await import(pathToFileURL(path.resolve('src/services/codeOrchestrator.ts')).href)
const D='output/code-tests/fintech_real4'; const files=['index.html','style.css','script.js'].map(n=>({name:n,content:readFileSync(path.join(D,n),'utf8')}))
const r=checkWebPageIntegrity(files,'dashboard fintech graphique tableau triable convertisseur toggle thème')
console.log('  real4 ok =', r.ok); for(const m of r.missing) console.log('   -',m)
