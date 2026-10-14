import fs from 'node:fs'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import ts from 'typescript'
const source=fs.readFileSync(new URL('../src/services/threeDIntent.ts',import.meta.url),'utf8')
const parsed=ts.createSourceFile('intent.ts',source,ts.ScriptTarget.Latest,true)
const fn=parsed.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='verify3DMeshFidelity')
const code=ts.transpileModule(fn.getText(parsed).replace(/^export /,''),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
let calls=0
const sandbox={ollamaChat:async()=>{calls++;return {message:{content:JSON.stringify({score:99,passed:true,missingDetails:['requested pose differs'],artifacts:[],suggestions:[]})}}}}
vm.runInNewContext(code,sandbox)
const options={prompt:'Full figure, requested pose, without the specified accessory',intent:{referencePromptAdditions:[],subjectKind:'character'},model:'controlled',referenceImageBase64:'reference'}
assert.equal((await sandbox.verify3DMeshFidelity({...options,meshScreenshotBase64:''})).passed,false)
assert.equal(calls,0,'the reference must never be evaluated as the mesh')
assert.equal((await sandbox.verify3DMeshFidelity({...options,meshScreenshotBase64:'actual mesh render'})).passed,false,'99/100 cannot override a missing requirement')
const binarySource=fs.readFileSync(new URL('../src/utils/binaryBase64.ts',import.meta.url),'utf8')
const exp={};vm.runInNewContext(ts.transpileModule(binarySource,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports:exp,Uint8Array,btoa})
const image=Uint8Array.from({length:2000000},(_,i)=>i%251)
assert.equal(exp.binaryBase64(image),Buffer.from(image).toString('base64'))
console.log('Fidelity: no reference-as-mesh, missing requirements cannot pass, 2 MB images encode without stack overflow')
const compound=fs.readFileSync(new URL('../src/services/compoundScene.ts',import.meta.url),'utf8')
const sceneExports={}
vm.runInNewContext(ts.transpileModule(compound,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports:sceneExports})
const contract=sceneExports.buildCompoundSceneContract('robot sans moteur mais avec vapeur et néons','',{isolated:true})
assert(!contract.includes('moteur'),'an excluded keyword must not become required geometry')
assert(!contract.includes('not as separate animated geometry'),'requested props must not become merely surface styling')
console.log('Scene expansion: excluded objects stay excluded; requested scene geometry is retained')
const contextSource=fs.readFileSync(new URL('../src/utils/threeDConversationContext.ts',import.meta.url),'utf8')
const contextExports={};vm.runInNewContext(ts.transpileModule(contextSource,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports:contextExports})
const history=[{role:'user',content:'elfe entièrement visible, assise, sans cape'},{role:'assistant',content:'a dressed warrior with cape'},{role:'user',content:'elfe couleur bleue'}]
const retained=contextExports.retainThreeDRequirements('elfe sans couronne',history)
assert.equal(retained.length,2)
const request=contextExports.composeThreeDRequirements('elfe sans couronne',retained)
assert(request.includes('entièrement visible, assise, sans cape'))
assert(!request.includes('dressed warrior'))
assert(request.endsWith('elfe sans couronne'))
assert.equal(contextExports.retainThreeDRequirements('chat bleu',history).length,0)
console.log('Same-subject requirements survive short edits; assistant guesses and unrelated subjects do not contaminate the request')
