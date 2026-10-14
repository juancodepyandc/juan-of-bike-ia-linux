import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import {MeshStandardMaterial,MeshPhysicalMaterial,Texture,DoubleSide} from 'three'
const exports={}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../src/utils/materialChannels.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021}}).outputText,{exports})
const texture=new Texture()
const source=new MeshStandardMaterial({vertexColors:true,map:texture,roughnessMap:texture,metalnessMap:texture,normalMap:texture,emissiveMap:texture,alphaTest:.3,side:DoubleSide})
const upgraded=new MeshPhysicalMaterial(exports.materialChannels(source))
assert.equal(upgraded.vertexColors,true)
for(const key of ['map','normalMap','roughnessMap','metalnessMap','emissiveMap','alphaTest','side'])assert.equal(upgraded[key],source[key])
assert.equal(new MeshPhysicalMaterial(exports.materialChannels(new MeshStandardMaterial(),true)).vertexColors,true)
console.log('Actual Three.js materials: physical shading retains vertex colors and authored texture channels')
