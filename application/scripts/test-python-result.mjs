import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
const exports={}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../src/utils/pythonResult.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021}}).outputText,{exports})
const parse=exports.parsePythonResult
const result={ok:true,final_mesh:'/run/modele/modele_couleurs.glb',livraison:{modele_couleurs:'/run/modele/modele_couleurs.glb'},audit:[{ok:false,reason:'escaped "quote" and { braces }'}]}
assert.equal(JSON.stringify(parse('PROGRESS:export:mesh ready\n'+JSON.stringify(result,null,2)+'\nPROGRESS:done')),JSON.stringify(result))
assert.equal(parse(JSON.stringify(result)+'\n{"progress":100}').final_mesh,result.final_mesh)
const failed={ok:false,error:'quality rejected',final_mesh:result.final_mesh,mesh_produced:true}
assert.equal(parse(JSON.stringify(result)+'\n'+JSON.stringify(failed,null,2)).ok,false)
assert.equal(parse('0\nnull\nfalse\n[]'),null)
assert.equal(parse('{ broken }\n'+JSON.stringify(result)).ok,true)
console.log('Actual parser: pretty and compact JSON, delivered paths, nested audits and failed mesh outcomes survive logs')
const referenceSource=fs.readFileSync(new URL('../src/services/referenceVisualResearch.ts',import.meta.url),'utf8')
const tree=ts.createSourceFile('reference.ts',referenceSource,ts.ScriptTarget.Latest,true)
const functionNode=tree.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='canUseVisualReference')
const scope={}
vm.runInNewContext(ts.transpileModule(functionNode.getText(tree).replace('export ',''),{compilerOptions:{target:ts.ScriptTarget.ES2021}}).outputText,scope)
const assessment={usable:true,exactEnough:true,pixelated:false,cluttered:false,wrongSubject:false,score:99}
assert.equal(scope.canUseVisualReference(assessment,84),true)
for(const key of ['wrongSubject','pixelated','cluttered','unrequestedText','obscured','requestMismatch'])assert.equal(scope.canUseVisualReference({...assessment,[key]:true},84,true),false)
assert.equal(scope.canUseVisualReference(null,84),false)
console.log('Actual reference gate: metadata cannot override visible text, blur, outfit/pose mismatches or a negative vision assessment')
