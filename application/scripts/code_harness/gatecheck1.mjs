import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import { readFileSync } from 'node:fs'
import path from 'node:path'
const noop=()=>{}; const mem=new Map()
globalThis.localStorage={getItem:k=>mem.has(k)?mem.get(k):null,setItem:(k,v)=>mem.set(k,String(v)),removeItem:k=>mem.delete(k),clear:()=>mem.clear(),key:i=>Array.from(mem.keys())[i]??null,get length(){return mem.size}}
globalThis.window={location:{hostname:'localhost',href:'http://localhost/'},addEventListener:noop,removeEventListener:noop,matchMedia:()=>({matches:false,addEventListener:noop})}
globalThis.document={documentElement:{setAttribute:noop,classList:{add:noop,remove:noop}},body:{setAttribute:noop},addEventListener:noop,createElement:()=>({setAttribute:noop,style:{}}),querySelector:()=>null}
register('./hooks.mjs', import.meta.url)
const file = process.argv[2]
const prompt = process.argv.slice(3).join(' ')
const files = [{ name: path.basename(file), path: path.basename(file), content: readFileSync(file,'utf8'), language: 'markup' }]
const { checkGamePlayability } = await import(pathToFileURL(path.resolve('src/services/codeOrchestrator.ts')).href)
const r = checkGamePlayability(files, prompt)
console.log('missing:', JSON.stringify(r.missing), '| ok:', r.ok)
