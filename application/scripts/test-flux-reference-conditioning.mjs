import fs from 'node:fs'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import ts from 'typescript'
const source=fs.readFileSync(new URL('../src/utils/fluxWorkflow.ts',import.meta.url),'utf8')
const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
const exports={}
vm.runInNewContext(code,{exports,require:path=>path.includes('models')?{IMAGE_CLIP_MODEL:'clip',IMAGE_T5_MODEL:'t5',IMAGE_UNET_MODEL:'model.gguf',IMAGE_VAE_MODEL:'vae'}:{hasHumanRemovalTarget:()=>false}})
const options={prompt:'Keep subject identity, change the requested pose and remove the specified accessory',width:1024,height:1024,steps:20,filenamePrefix:'test'}
const plain=exports.createFlux2Workflow(options)
assert.equal(plain['55'],undefined)
const edited=exports.createFlux2Workflow({...options,referenceImageFilename:'folder/reference.png'})
assert.equal(edited['55'].class_type,'LoadImage')
assert.equal(edited['55'].inputs.image,'reference.png')
assert.equal(edited['56'].class_type,'VAEEncode')
assert.equal(edited['57'].class_type,'ReferenceLatent')
assert.equal(edited['58'].class_type,'ReferenceLatent')
assert.equal(edited['26'].inputs.positive[0],'57')
assert.equal(edited['26'].inputs.negative[0],'58')
assert.equal(edited['6'].inputs.text,options.prompt)
console.log('Real FLUX graph: requested edits retain image conditioning on both branches; text generation remains available')

const windows=exports.createFlux2Workflow({...options,referenceImageFilename:String.raw`C:\folder\reference.png`})
assert.equal(windows['55'].inputs.image,'reference.png')
