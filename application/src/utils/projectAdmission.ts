import { bridgeFetch } from './bridgeAuth.ts'
import { getBridgeUrl } from './runtime.ts'

class AdmissionRejected extends Error{}
type Request={request_id:string;module:string;title:string;model?:string|null}
export async function acquireProject(data:Request,onWaiting:(detail:string)=>void,signal?:AbortSignal){
 const executor=typeof crypto.randomUUID==='function'?crypto.randomUUID():Array.from(crypto.getRandomValues(new Uint8Array(16))).map(n=>n.toString(16).padStart(2,'0')).join('')
 async function api(path:string,payload:unknown,cancellable=true){while(true){if(cancellable)signal?.throwIfAborted();try{const r=await bridgeFetch(getBridgeUrl()+'/api/projects'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();if(!r.ok){if(r.status>=400&&r.status<500&&!(path.endsWith('/finish')&&d.code==='workers_stopping'))throw new AdmissionRejected(d.error||'Admission refusée.');throw Error('PC momentanément injoignable.')}return d}catch(error){if(cancellable)signal?.throwIfAborted();if(error instanceof AdmissionRejected)throw error;onWaiting('Connexion au PC interrompue · même demande conservée, sans relancer le calcul.');await new Promise(r=>setTimeout(r,1500))}}}

 const accepted=await api('/admission',data);const id=accepted.id
 try { while(true){const state=await api('/'+id+'/admission',{executor});if(state.status==='running'&&state.granted)break;if(state.status==='running'){onWaiting('Ce projet travaille déjà sur le PC · aucune seconde exécution.');await new Promise(r=>setTimeout(r,1500));continue}if(state.status!=='queued'){const error=new Error(state.status==='stopped'?'Attente annulée.':'Cette admission est interrompue. Le travail existant doit être vérifié avant reprise.');if(state.status==='stopped')error.name='AbortError';throw error}const blocker=state.scheduling.blockers?.find((b:{status:string})=>b.status==='interrupted');onWaiting(blocker?`Attente bloquée : réservation interrompue « ${blocker.title} » (${blocker.id}). Le PC doit vérifier son arrêt avant de libérer la file.`:`En attente sur le PC · position ${state.scheduling.queue_position} · ${state.scheduling.ahead_count} projet(s) devant · aucun calcul de cette demande n’a commencé.`);await new Promise(r=>setTimeout(r,1500))}
 } catch(error) { if(signal?.aborted){const r=await bridgeFetch(getBridgeUrl()+'/api/projects/'+id+'/cancel',{method:'POST'}).catch(()=>null);if(r?.status===409)await api('/'+id+'/finish',{status:'stopped',executor},false);} throw error }
 let releasePromise:Promise<void>|null=null
 const finish=async(status:'completed'|'failed'|'stopped')=>{if(releasePromise)return releasePromise;clearInterval(timer);signal?.removeEventListener('abort',stop);releasePromise=api('/'+id+'/finish',{status:signal?.aborted?'stopped':status,executor},false).then(()=>undefined);return releasePromise}
 const stop=()=>{void finish('stopped').catch(()=>{onWaiting('Arrêt demandé ; libération de la file non confirmée par le PC.')})}
 let renewing=false;const timer=setInterval(()=>{if(renewing)return;renewing=true;void api('/'+id+'/admission',{executor}).catch(()=>{/* Keep the admission; never start another copy. */}).finally(()=>{renewing=false})},10000)
 signal?.addEventListener('abort',stop,{once:true})
 if(signal?.aborted){await finish('stopped');signal.throwIfAborted()}
 return finish
}
