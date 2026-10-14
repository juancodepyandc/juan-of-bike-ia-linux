import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import {createRequire} from 'node:module'
import {webcrypto} from 'node:crypto'
const require=createRequire(import.meta.url)
const data=new Map()
globalThis.localStorage={getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)}
function load(path,imports){const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL(path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021}}).outputText,{exports,require:imports,crypto:webcrypto,Date,Math,console});return exports}
const middleware=require('zustand/middleware')
const storage=middleware.createJSONStorage(()=>globalThis.localStorage)
const title=load('../src/utils/titleInference.ts',require)
const {useModuleHistoryStore:store}=load('../src/stores/moduleHistoryStore.ts',name=>name.includes('titleInference')?title:name==='zustand/middleware'?{...middleware,persist:(creator,options)=>middleware.persist(creator,{...options,storage})}:require(name))
const message={role:'assistant',content:'preserved',timestamp:1}
const session=(id,module,messages)=>({id,module,title:id,messages,createdAt:1,updatedAt:1})
store.setState({sessions:[session('cancelled','3d',[]),session('retained','3d',[message]),session('image','image',[message])],activeSessionId:{'3d':'cancelled',image:'image'},histories:{'3d':[{...message,content:'stale'}],image:[message]}})
store.getState().deleteSession('cancelled')
assert.equal(store.getState().activeSessionId['3d'],'retained')
assert.deepEqual(store.getState().histories['3d'],[message])
assert.equal(store.getState().sessions.find(s=>s.id==='image').messages[0].content,'preserved')
store.getState().deleteSession('retained')
assert.equal(store.getState().getActiveSession('3d').messages.length,0)
assert.equal(store.getState().histories['3d'].length,0)
assert.equal(JSON.parse(data.get('aurora-module-history')).state.histories['3d'].length,0)
console.log('Actual history store: deleted session and legacy cache agree; other conversations survive')
