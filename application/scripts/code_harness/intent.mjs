// Dump the deterministic intent classification for a prompt (no LLM).
import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import path from 'node:path'

const mem = new Map()
const ls = { getItem:(k)=>mem.has(k)?mem.get(k):null, setItem:(k,v)=>mem.set(k,String(v)), removeItem:(k)=>mem.delete(k), clear:()=>mem.clear(), key:(i)=>Array.from(mem.keys())[i]??null, get length(){return mem.size} }
const noop = () => {}
globalThis.localStorage = ls
globalThis.window = { location:{hostname:'localhost',href:'http://localhost/',origin:'http://localhost'}, localStorage:ls, addEventListener:noop, removeEventListener:noop, matchMedia:()=>({matches:false,addEventListener:noop,removeEventListener:noop}) }
globalThis.document = { documentElement:{setAttribute:noop,classList:{add:noop,remove:noop,toggle:noop}}, body:{setAttribute:noop}, addEventListener:noop, createElement:()=>({setAttribute:noop,style:{},appendChild:noop}), querySelector:()=>null }
register('./hooks.mjs', import.meta.url)

const prompt = process.argv.slice(2).join(' ').trim()
const ci = await import(pathToFileURL(path.resolve('src/services/codeIntent.ts')).href)

// Find the public classify function
const fnName = ['classifyCodeIntent','detectCodeIntent','analyzeCodeIntent','buildCodeIntent','classifyIntent']
  .find((n) => typeof ci[n] === 'function')
console.log('intent fn:', fnName, '| exports:', Object.keys(ci).filter(k=>typeof ci[k]==='function').join(', '))
if (fnName) {
  const intent = ci[fnName](prompt)
  console.log(JSON.stringify({
    projectType: intent.projectType,
    complexity: intent.complexity,
    language: intent.language,
    languages: intent.languages,
    frameworks: intent.frameworks,
    features: intent.features,
    needsArchitecturePlanning: intent.needsArchitecturePlanning,
    estimatedFileCount: intent.estimatedFileCount,
    previewType: intent.previewType,
    isGame: intent.isGame,
    gameKind: intent.gameKind,
    knownGame: intent.knownGame ? intent.knownGame.canonical : null,
    subject: intent.assetPlan?.subject,
    researchQueries: intent.assetPlan?.researchQueries?.slice(0,3),
  }, null, 2))
}
