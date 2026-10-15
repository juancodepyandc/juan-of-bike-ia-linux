import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
import ts from 'typescript'
const exports={}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../src/utils/threeDEditPlan.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports})
const pose={continuation:true,reference_edit:false,mesh_edit:'pose',source_rig:'humanoid'}
assert.equal(exports.planThreeDEdit(true,pose,false,false).articulate,false,'static pose must never require a skin')
assert.equal(exports.planThreeDEdit(true,pose,false,false).reconstructFromSource,true)
assert.equal(exports.planThreeDEdit(true,pose,true,false).articulate,true)
assert.equal(exports.sourceRig({subjectKind:'character'},pose),'humanoid','a posture does not change original anatomy')
for(const edit of ['scene','texture','style','geometry']){
 const mixed={...pose,reference_edit:true,mesh_edit:'none'}
 assert.equal(exports.planThreeDEdit(true,mixed,false,false).reconstructFromSource,true,edit)
 assert.equal(exports.planThreeDEdit(true,mixed,true,false).reconstructFromSource,true,edit+' with later animation')
}
assert.equal(exports.planThreeDEdit(true,{...pose,continuation:false},false,false).continuation,false)
const root='/workspace/output/3d/conversations/adult/juan_bike_123'
const context=await exports.readThreeDSourceContext(root+'/modele/modele_couleurs.glb',async path=>{
 if(path.endsWith('/journal/manifest.json'))return JSON.stringify({source_subject_kind:'character',rig_subject:'humanoid',subject_description:'personnage adulte vêtu',prompt:'à quatre pattes'})
 throw Error('missing')
})
assert.equal(context.subjectKind,'character');assert.equal(context.description,'personnage adulte vêtu');assert.equal(context.rigSubject,'humanoid')
const parsed=ts.createSourceFile('ModelView.tsx',fs.readFileSync(new URL('../src/views/ModelView.tsx',import.meta.url),'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
const declarations=parsed.statements.filter(n=>ts.isFunctionDeclaration(n)&&['_meshRank','findSessionAssets'].includes(n.name?.text)).map(n=>n.getText(parsed).replace(/^export /,''))
const sandbox={}
vm.runInNewContext(ts.transpileModule(declarations.join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText,sandbox)
const assets=sandbox.findSessionAssets({messages:[{images:['/old_RIGGED.glb']},{images:['/new_static.glb','/new_reference.png']}]})
assert.equal(assets.meshPath,'/new_static.glb');assert.equal(assets.referencePath,'/new_reference.png')
console.log('Edit routing: static posture without skin, movement opt-in, scene/texture revisions, source anatomy and newest delivered version')
