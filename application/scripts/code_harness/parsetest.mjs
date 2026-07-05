import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import path from 'node:path'
const noop=()=>{}; const mem=new Map()
globalThis.localStorage={getItem:k=>mem.has(k)?mem.get(k):null,setItem:(k,v)=>mem.set(k,String(v)),removeItem:k=>mem.delete(k),clear:()=>mem.clear(),key:i=>Array.from(mem.keys())[i]??null,get length(){return mem.size}}
globalThis.window={location:{hostname:'localhost',href:'http://localhost/'},addEventListener:noop,removeEventListener:noop,matchMedia:()=>({matches:false,addEventListener:noop})}
globalThis.document={documentElement:{setAttribute:noop,classList:{add:noop,remove:noop}},body:{setAttribute:noop},addEventListener:noop,createElement:()=>({setAttribute:noop,style:{}}),querySelector:()=>null}
register('./hooks.mjs', import.meta.url)

const sample = [
  '--- FICHIER: index.html ---',
  '```html',
  '<!DOCTYPE html><html><body><canvas id="c"></canvas><script src="game.js"></script></body></html>',
  '```',
  '--- FICHIER: game.js ---',
  '```js',
  "const ctx = document.getElementById('c').getContext('2d');",
  'function gameLoop(){ requestAnimationFrame(gameLoop); }',
  'gameLoop();',
  '```',
  '',
  '```css',
  '/* Add any additional styles here */',
  '```',
  '```bash',
  '#!/usr/bin/env bash',
  'set -e',
  '```',
  '--- FICHIER: style.css ---',
  '```css',
  'body { margin: 0; }',
  '```',
].join('\n')

const { parseCodeFiles } = await import(pathToFileURL(path.resolve('src/services/codeOrchestrator.ts')).href)
const files = parseCodeFiles(sample)
for (const f of files) {
  const hasFence = /```/.test(f.content)
  console.log(`--- ${f.name} (${f.content.length}c) fence_leak=${hasFence ? 'YES ***BUG***' : 'no'}`)
  if (hasFence) console.log(JSON.stringify(f.content))
}
console.log('files:', files.map(f=>f.name).join(', '))
