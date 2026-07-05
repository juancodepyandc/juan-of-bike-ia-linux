import { register } from 'node:module'; import { pathToFileURL } from 'node:url'; import path from 'node:path'
const mem=new Map(); const ls={getItem:(k)=>mem.has(k)?mem.get(k):null,setItem:(k,v)=>mem.set(k,String(v)),removeItem:(k)=>mem.delete(k),clear:()=>mem.clear(),key:(i)=>[...mem.keys()][i]??null,get length(){return mem.size}}; const noop=()=>{}
globalThis.localStorage=ls; globalThis.window={location:{hostname:'localhost',href:'http://localhost/',origin:'http://localhost'},localStorage:ls,addEventListener:noop,removeEventListener:noop,matchMedia:()=>({matches:false,addEventListener:noop,removeEventListener:noop})}; globalThis.document={documentElement:{setAttribute:noop,classList:{add:noop,remove:noop,toggle:noop}},body:{setAttribute:noop},addEventListener:noop,createElement:()=>({setAttribute:noop,style:{},appendChild:noop}),querySelector:()=>null}
register('./hooks.mjs', import.meta.url)
const ci = await import(pathToFileURL(path.resolve('src/services/codeIntent.ts')).href)
const sp = await import(pathToFileURL(path.resolve('src/services/codeSystemPrompts.ts')).href)
const intent = ci.classifyCodeIntent('Crée un dashboard fintech une seule page, tableau triable, ouvrable dans un navigateur')
const p = sp.buildCodeurSystemPrompt(intent)
console.log('  projectType =', intent.projectType)
console.log('  has CONTRAT D INTERACTIVITE =', p.includes('CONTRAT D INTERACTIVITE'))
console.log('  has mutate-then-render rule =', /RE-RENDRE le DOM|repeindre/.test(p))
// non-visual must NOT include it
const cli = ci.classifyCodeIntent('un script python qui parse un CSV')
console.log('  python CLI excludes contract =', !sp.buildCodeurSystemPrompt(cli).includes('CONTRAT D INTERACTIVITE'))
