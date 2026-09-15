/* Media views use the generated files, never simulated model output. */
async function displayArtifact(target,event,urlFor=artifactUrl){
  target.replaceChildren();
  const path=event.artifact||event.name, url=event.url||urlFor(path);
  const viewer=event.viewer?(event.url?event.viewer:urlFor(event.viewer)):null;
  if(event.text!=null || /\.(txt|py)$/.test(path)){
    const pre=document.createElement('pre');pre.textContent=event.text??await (await fetch(url)).text();target.append(pre);
  }else{
    const tag=viewer||path.endsWith('.glb')?'iframe':path.endsWith('.wav')?'audio':path.endsWith('.mp4')?'video':'img';
    const el=document.createElement(tag);el.src=viewer||(tag==='iframe'?url+(url.includes('?')?'&':'?')+'viewer=1':url);el.title='Fichier réellement généré';
    if(tag==='audio'||tag==='video')el.controls=true;
    target.append(el);
  }
  const link=document.createElement('a');link.href=url;link.textContent='Télécharger le fichier généré';link.download='';target.append(link);
}

let sampleRows=[],sampleRun=null,sampleSignature='',sampleLoading=false;
async function loadSamples(){
  const current=selected();if(!current||sampleLoading)return;
  const run=current.latest_run?.run_id;
  if(!run){$('#sampleInfo').textContent='Aucun fichier généré pour ce module.';$('#sampleOutput').replaceChildren();$('#sampleChoice').replaceChildren();$('#diagnosticText').textContent='';return}
  sampleLoading=true;
  try{
    const r=await fetch('/api/training/samples/'+encodeURIComponent(run));if(!r.ok)throw Error('Résultats indisponibles');
    const data=await r.json();if(selected()?.latest_run?.run_id!==run)return;
    const signature=run+JSON.stringify(data.samples.map(s=>[s.name,s.bytes,s.measured]));
    const prior=sampleRun===run?$('#sampleChoice').value:null;
    if(signature!==sampleSignature){
      sampleRows=data.samples;sampleRun=run;sampleSignature=signature;
      $('#sampleChoice').replaceChildren();
      for(const [i,row] of sampleRows.entries()){
        const o=document.createElement('option');o.value=row.name;o.textContent=row.name+(row.judge?' · score '+row.judge.score.toFixed(3):' · jugement en attente');$('#sampleChoice').append(o);
      }
      if(prior&&sampleRows.some(row=>row.name===prior))$('#sampleChoice').value=prior;
      if(sampleRows.length)await showSample();else $('#sampleOutput').replaceChildren();
    }
    $('#sampleInfo').textContent=sampleRows.length+' fichier(s) disponible(s) · '+current.label+' · '+run;
    const d=await fetch('/api/training/diagnostic/'+encodeURIComponent(run));
    if(d.ok){const info=await d.json();$('#diagnosticText').textContent=[info.message,info.last_step?'Dernière étape : '+info.last_step:null,info.log_tail||info.traceback].filter(Boolean).join('\n\n')}
  }catch(e){$('#sampleInfo').textContent=e.message}finally{sampleLoading=false}
}
async function showSample(){const row=sampleRows.find(r=>r.name===$('#sampleChoice').value);if(row)await displayArtifact($('#sampleOutput'),row)}
$('#sampleChoice').onchange=()=>showSample().catch(e=>$('#sampleInfo').textContent=e.message);
const originalShowVersions=showVersions;
showVersions=function(){originalShowVersions();const c=state?.cycle;if(c?.local_generations_planned)$('#telemetry').textContent+=' · PC '+(c.local_generations_done||0)+'/'+c.local_generations_planned;loadSamples()};
$('#trainModule').onchange=showVersions;
setInterval(()=>{if(online)loadSamples()},5000);

function initPreviewModules(){
  if(!state){setTimeout(initPreviewModules,200);return}
  for(const m of state.modules){const o=document.createElement('option');o.value=m.module;o.textContent=m.label;$('#module').append(o)}
  $('#module').value='animation';$('#module').onchange=()=>{$('#referenceLabel').hidden=$('#module').value!=='3d'};
  $('#prompt').value='A person stands and waves with the right hand.';
}
initPreviewModules();
$('#generate').onclick=async()=>{
  const button=$('#generate');button.disabled=true;$('#output').replaceChildren();$('#progress').textContent='Préparation…';
  try{
    const body={module:$('#module').value,prompt:$('#prompt').value};
    if($('#version').value!=='selected')body.use_base=$('#version').value==='base';
    if(body.module==='3d'){
      const file=$('#referenceImage').files[0];if(!file)throw Error('Choisis une image de référence pour la 3D.');
      const form=new FormData();form.append('image',file);
      const response=await fetch('/api/training/reference',{method:'POST',headers:{'X-Aurora-Control':token},body:form});
      const ref=await response.json();if(!response.ok)throw Error(ref.error);body.reference_id=ref.reference_id;
    }
    const response=await fetch('/api/training/media',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!response.ok)throw Error(await response.text());
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',finished=false;
    async function eventLine(line){if(!line.trim())return;const event=JSON.parse(line);if(event.error)throw Error(event.error);if(event.done){finished=true;$('#progress').textContent=event.model+' · '+event.seconds.toFixed(1)+' s';await displayArtifact($('#output'),event)}else if(event.status)$('#progress').textContent=event.status}
    while(!finished){const {done,value}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});let pos;while((pos=buffer.indexOf('\n'))>=0){await eventLine(buffer.slice(0,pos));buffer=buffer.slice(pos+1)}if(done){if(buffer.trim())await eventLine(buffer);if(!finished)throw Error('Connexion interrompue avant la fin');break}}
  }catch(e){$('#progress').textContent=e.message}finally{button.disabled=false}
};
