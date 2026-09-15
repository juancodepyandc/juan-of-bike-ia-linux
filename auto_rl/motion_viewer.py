"""Small standalone browser viewer for judged world-space skeleton sequences."""
import json
from pathlib import Path
import numpy as np


def write_viewer(artifact):
    artifact=Path(artifact)
    with np.load(artifact,allow_pickle=False) as data:xyz=data['keypoints3d'][0,:,:22].round(5).tolist()
    if not xyz or not np.isfinite(np.asarray(xyz)).all():raise ValueError('Mouvement vide ou non fini')
    page='''<!doctype html><meta charset="utf-8"><title>Aurora · Mouvement</title>
<style>body{margin:0;background:#101723;color:#edf4ff;font:14px system-ui}canvas{width:100%;height:360px;touch-action:none}nav{display:flex;gap:10px;padding:10px}input{flex:1}button{cursor:pointer}</style>
<p style="margin:10px">Squelette du mouvement généré · glisser pour tourner · repère au sol</p><canvas width="600" height="360" aria-label="Mouvement réel du squelette"></canvas><nav><button>Pause</button><input type="range" min="0" step="1" value="0"><span></span></nav>
<script>const frames=DATA,parents=[-1,0,0,0,1,2,3,4,5,6,7,8,9,9,9,12,13,14,16,17,18,19];
const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d'),slider=document.querySelector('input'),button=document.querySelector('button');
slider.max=frames.length-1;let playing=true,index=0,last=0,yaw=.6,drag=null;canvas.onpointerdown=e=>{drag=e.clientX;canvas.setPointerCapture(e.pointerId)};canvas.onpointerup=()=>drag=null;canvas.onpointermove=e=>{if(drag!==null){yaw+=(e.clientX-drag)*.01;drag=e.clientX;draw()}};
const flat=frames.flat(),min=[0,1,2].map(k=>Math.min(...flat.map(p=>p[k]))),max=[0,1,2].map(k=>Math.max(...flat.map(p=>p[k]))),center=min.map((v,k)=>(v+max[k])/2),scale=260/Math.max(1,...max.map((v,k)=>v-min[k]));
function point(p){const x=p[0]-center[0],y=p[1]-center[1],z=p[2]-center[2];return [300+(x*Math.cos(yaw)+z*Math.sin(yaw))*scale,170-y*scale+z*.12*scale]}
function draw(){ctx.clearRect(0,0,600,360);const f=frames[index];ctx.lineWidth=1;ctx.strokeStyle='#3c5263';for(let g=-4;g<=4;g++){for(const [a,b] of [[[g,0,-4],[g,0,4]],[[-4,0,g],[4,0,g]]]){ctx.beginPath();ctx.moveTo(...point(a));ctx.lineTo(...point(b));ctx.stroke()}}ctx.lineWidth=9;ctx.lineCap='round';
f.forEach((p,j)=>{const a=point(p);ctx.fillStyle='#71dbce';ctx.beginPath();ctx.arc(...a,j===15?10:4,0,7);ctx.fill();if(parents[j]>=0){const b=point(f[parents[j]]);ctx.strokeStyle=j%2?'#71dbce':'#9dadff';ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke()}});
slider.value=index;document.querySelector('span').textContent=(index/30).toFixed(2)+' / '+((frames.length-1)/30).toFixed(2)+' s';canvas.dataset.frame=String(index);}
button.onclick=()=>{playing=!playing;button.textContent=playing?'Pause':'Lire'};slider.oninput=()=>{index=Number(slider.value);playing=false;button.textContent='Lire';draw()};
function tick(t){if(playing&&t-last>1000/30){index=(index+1)%frames.length;last=t;draw()}requestAnimationFrame(tick)}draw();requestAnimationFrame(tick);</script>'''
    target=artifact.with_suffix('.motion.html');target.write_text(page.replace('DATA',json.dumps(xyz)))
    return target
