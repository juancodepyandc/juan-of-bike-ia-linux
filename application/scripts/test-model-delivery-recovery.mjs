import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
function load(name,require){const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../src/utils/'+name,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021}}).outputText,{exports,require});return exports}
const parser=load('pythonResult.ts')
const {recoverModelDelivery}=load('recoverModelDelivery.ts',()=>parser)
const id='session-12345678-abcd-1234-1111-222222222222'
const workspace='/workspace',base=workspace+'/output/3d/conversations',directory='topic_'+id.replace('session-','').slice(0,18),runId='juan_bike_123',root=base+'/'+directory+'/'+runId
const files=new Map([[root+'/journal/manifest.json',JSON.stringify({session_id:id})],[root+'/travail/journal/pipeline.log',JSON.stringify({ok:false,error:'pose mismatch',final_mesh:root+'/modele/modele_couleurs.glb'},null,2)],[root+'/modele/modele_couleurs.glb','fixture presence']])
const api={list:async path=>{if(path===base)return[directory];if(path===base+'/'+directory)return[runId,'pbr_alias'];throw Error('unavailable')},text:async path=>{if(!files.has(path))throw Error('missing');return files.get(path)},exists:async path=>files.has(path)}
const result=await recoverModelDelivery(workspace,id,api)
assert.equal(result.mesh,root+'/modele/modele_couleurs.glb');assert.equal(result.engineOk,false);assert.equal(result.error,'pose mismatch')
assert.equal(await recoverModelDelivery(workspace,id.replace('222222222222','333333333333'),api),null,'a matching truncated directory prefix must not bind a different full session')
files.set(root+'/travail/journal/pipeline.log',JSON.stringify({ok:true,final_mesh:'/outside.glb'}));files.set('/outside.glb','external')
assert.equal(await recoverModelDelivery(workspace,id,api),null)
console.log('Actual recovery: exact session identity, failed-result preview, old pretty JSON, aliases and external paths handled without a calculation')
if(process.argv[2]&&process.argv[3]){
 const manifest=JSON.parse(fs.readFileSync(process.argv[3],'utf8'))
 const actual=await recoverModelDelivery(process.argv[2],manifest.session_id,{list:async p=>fs.readdirSync(p),text:async p=>fs.readFileSync(p,'utf8'),exists:async p=>fs.existsSync(p)})
 assert(actual&&fs.existsSync(actual.mesh));console.log('Existing local run recovered without replay; engine verdict:',actual.engineOk)
}
