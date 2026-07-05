import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
const noop=()=>{}; const mem=new Map()
globalThis.localStorage={getItem:k=>mem.has(k)?mem.get(k):null,setItem:(k,v)=>mem.set(k,String(v)),removeItem:k=>mem.delete(k),clear:()=>mem.clear(),key:i=>Array.from(mem.keys())[i]??null,get length(){return mem.size}}
globalThis.window={location:{hostname:'localhost',href:'http://localhost/'},addEventListener:noop,removeEventListener:noop,matchMedia:()=>({matches:false,addEventListener:noop})}
globalThis.document={documentElement:{setAttribute:noop,classList:{add:noop,remove:noop}},body:{setAttribute:noop},addEventListener:noop,createElement:()=>({setAttribute:noop,style:{}}),querySelector:()=>null}
register('./hooks.mjs', import.meta.url)
const dir = path.resolve(process.argv[2])
const prompt = process.argv.slice(3).join(' ')
function walk(b,r=''){const o=[];for(const n of readdirSync(path.join(b,r))){const rr=r?`${r}/${n}`:n;const f=path.join(b,rr);statSync(f).isDirectory()?o.push(...walk(b,rr)):o.push(rr)}return o}
const files = walk(dir).filter(r=>/\.(html?|m?[jt]sx?|css)$/i.test(r)).map(r=>({name:r,path:r,content:readFileSync(path.join(dir,r),'utf8'),language:'text'}))
const { checkGamePlayability } = await import(pathToFileURL(path.resolve('src/services/codeOrchestrator.ts')).href)
console.log(JSON.stringify(checkGamePlayability(files, prompt), null, 2))
