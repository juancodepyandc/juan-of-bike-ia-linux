import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
import ts from 'typescript'
const exports={}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../src/utils/threeDRelation.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports})
const history=[{role:'user',content:'une elfe sans cape'},{role:'assistant',content:'guerrier avec armure'}]
let instruction
const generate=async text=>{instruction=text;return JSON.stringify({continuation:true,reference_edit:false,mesh_edit:'pose'})}
const relation=await exports.resolveThreeDRelation('dans la position assise',history,true,generate)
assert(relation.continuation&&relation.mesh_edit==='pose')
assert(instruction.includes('une elfe sans cape')&&!instruction.includes('guerrier avec armure'))
const independent=await exports.resolveThreeDRelation('un nouveau véhicule',history,true,async()=>'{"continuation":false,"reference_edit":true,"mesh_edit":"motion"}')
assert(!independent.reference_edit&&independent.mesh_edit==='none')
assert.equal(await exports.resolveThreeDRelation('texte',history,true,async()=>'invalid'),null)
assert.equal(await exports.resolveThreeDRelation('texte',[],false,async()=>{throw Error('no history')}),null)
console.log('Relation contract: raw user context, independent project separation, invalid interpretation rejected; model understanding not simulated as proven')
const mixed=[{role:'user',content:'une elfe',threeDContext:'new'},{role:'user',content:'un camion bleu',threeDContext:'new'},{role:'user',content:'ajoute une remorque',threeDContext:'continuation'}]
await exports.resolveThreeDRelation('tourne les roues',mixed,true,async text=>{assert(!text.includes('une elfe'));assert(text.includes('camion bleu'));return '{"continuation":true,"reference_edit":false,"mesh_edit":"motion"}'})
console.log('Persisted subject boundary prevents old project requirements contaminating later follow-ups')
