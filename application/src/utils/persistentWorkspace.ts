import { getBridgeUrl } from './runtime.ts'
import { bridgeFetch } from './bridgeAuth.ts'
import { readUiSkin } from './uiSkin.ts'
import type { ModuleId } from '../types/app.ts'

export async function openPersistentWorkspace(module:ModuleId){
 const settings:Record<string,string>={}
 for(const key of ['aurora.printProfiles.v1','aurora.printProfiles.v1.selected','aurora.engineering-objective.v1.selected']){try{const value=localStorage.getItem(key);if(value!==null)settings[key]=value}catch{}}
 let workspace='model',draft:{goal:string;constraints:string}|undefined
 try{workspace=localStorage.getItem('aurora.3d.workspace')||'model';const d=JSON.parse(localStorage.getItem('aurora.engineering-objective.v1')||'{}');if(typeof d.goal==='string')draft={goal:d.goal,constraints:typeof d.constraints==='string'?d.constraints:''}}catch{}
 const response=await bridgeFetch(getBridgeUrl()+'/api/workspace-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({width:innerWidth,height:innerHeight-150,navigation:{module,workspace,skin:readUiSkin(),draft,settings}})})
 if(!response.ok)throw Error('L’espace du PC est momentanément indisponible. Votre demande n’a pas été relancée.')
 location.assign(getBridgeUrl()+'/workspace')
}
