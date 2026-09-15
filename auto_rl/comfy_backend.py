"""Real FLUX.2 GGUF inference with portable low-rank weight corrections.

Only tensor SHAPES are read from GGUF locally. ComfyUI owns inference and loads
standard LoRA tensors; the pretrained GGUF is never rewritten.
"""
from __future__ import annotations
import json
import sys
import time
import uuid
from pathlib import Path
import torch
from safetensors.torch import save_file
from .config import ROOT
from .adapters import WeightSubspace
from .storage import digest, file_hash

COMFY=ROOT/'modele/comfyui'


def tensor_shapes(path):
    if str(path).endswith('.safetensors'):
        from safetensors import safe_open
        with safe_open(str(path),framework='pt',device='cpu') as f:
            result=[]
            for name in f.keys():
                if name.startswith('blocks.') and name.endswith('.self_attn.o.weight'):
                    shape=f.get_slice(name).get_shape()
                    if len(shape)==2:result.append((name[:-7],shape[1],shape[0]))
        if not result:raise ValueError('Aucune projection Wan compatible dans ces poids')
        return sorted(result,key=lambda row:int(row[0].split('.')[1]))
    from gguf import GGUFReader
    reader=GGUFReader(str(path))
    result=[(t.name[:-7],int(t.shape[0]),int(t.shape[1])) for t in reader.tensors
            if t.name.endswith('.img_attn.proj.weight') and len(t.shape)==2 and t.name.startswith('double_blocks.')]
    if not result:raise ValueError('Aucune projection FLUX.2 compatible dans ce GGUF')
    return result


def shape_model(path):
    model=torch.nn.Module()
    for name,inputs,outputs in tensor_shapes(path):
        parent=model
        parts=name.split('.')
        for part in parts[:-1]:
            if not hasattr(parent,part):parent.add_module(part,torch.nn.Module())
            parent=getattr(parent,part)
        parent.add_module(parts[-1],torch.nn.Linear(inputs,outputs,bias=False,device='meta'))
    return model


def export_comfy_lora(adapter,path):
    tensors={}
    for entry in adapter.layers:
        name='diffusion_model.'+entry['name']
        tensors[name+'.lora_down.weight']=entry['a'].float().contiguous()
        tensors[name+'.lora_up.weight']=(entry['b']*entry['c'][None,:]).float().contiguous()
        # Comfy uses alpha/rank. Our B diag(c) A has scale exactly 1.
        tensors[name+'.alpha']=torch.tensor(float(adapter.rank))
    tmp=Path(path).with_suffix('.'+uuid.uuid4().hex+'.tmp.safetensors')
    save_file(tensors,str(tmp),metadata={'format':'pt','source':'Aurora low-rank weight adapter'})
    tmp.replace(path)


class ComfyImageBackend:
    suffix='.png'
    def __init__(self,c,paths):
        self.c=c
        self.shape_model=shape_model(paths['image'])
        self.adapter=WeightSubspace(self.shape_model,c['rank'],c['max_layers'],c['seed'])
        self.last_peak_vram_gb=0.0
        self.check=lambda:None

    def generate(self,task,seed,path,feedback=None):
        sys.path.insert(0,str(ROOT/'application/python-services'))
        from flux_reference_synth import build_workflow,post_prompt,output_path_from_history,fetch_to
        import urllib.request
        import subprocess
        g=self.c['generation']
        workflow=(self.build_workflow(task,seed,path) if hasattr(self,'build_workflow') else
                  build_workflow(task['prompt'],width=g['width'],height=g['height'],steps=g['steps'],seed=seed,filename_prefix='aurora_training/'+Path(path).stem,trained_adapter=False))
        workflow['12']['inputs']['unet_name'] = Path(self.c['comfy_unet']).name
        workflow['11']['inputs']['clip_name'] = Path(self.c['comfy_clip']).name
        workflow['10']['inputs']['vae_name'] = Path(self.c['comfy_vae']).name
        lora=None
        if self.adapter.enabled and bool(self.adapter.vector().abs().max()):
            folder=COMFY/'models/loras/aurora_training';folder.mkdir(parents=True,exist_ok=True)
            key=digest({'vector':self.adapter.vector().tolist(),'seed':self.adapter.seed,'targets':[e['name'] for e in self.adapter.layers]})
            lora=folder/(key+'.safetensors')
            export_comfy_lora(self.adapter,lora)
            workflow['90']={'class_type':'LoraLoaderModelOnly','inputs':{'model':['12',0],'lora_name':'aurora_training/'+lora.name,'strength_model':1.0}}
            workflow['26']['inputs']['model']=['90',0]
        job=post_prompt(workflow)
        deadline=time.monotonic()+1800
        self.last_peak_vram_gb=0.0
        try:
            while time.monotonic()<deadline:
                self.check()
                with urllib.request.urlopen('http://127.0.0.1:8188/history/'+job,timeout=15) as response:
                    history=json.load(response).get(job,{})
                usage=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
                if usage.returncode==0:
                    self.last_peak_vram_gb=max(self.last_peak_vram_gb,float(usage.stdout.splitlines()[0])/1024)
                status=history.get('status',{})
                if status.get('status_str')=='error':raise RuntimeError('ComfyUI : '+json.dumps(status.get('messages',[]))[-2000:])
                if status.get('completed'):
                    url=output_path_from_history(history)
                    fetch_to(url,Path(path));return str(path)
                time.sleep(2)
            raise RuntimeError('Délai de génération ComfyUI dépassé')
        except BaseException:
            # Interrupt only this job if it is actually running, otherwise remove
            # its pending queue entry without touching another user's generation.
            try:
                with urllib.request.urlopen('http://127.0.0.1:8188/queue',timeout=5) as response:q=json.load(response)
                if any(item[1]==job for item in q.get('queue_running',[])):
                    req=urllib.request.Request('http://127.0.0.1:8188/interrupt',data=b'{}',headers={'Content-Type':'application/json'})
                else:
                    req=urllib.request.Request('http://127.0.0.1:8188/queue',data=json.dumps({'delete':[job]}).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=5):pass
            except (OSError,ValueError,IndexError):pass
            raise
        finally:
            # Unique filenames invalidate Comfy's cached LoRA weights each time.
            if lora:lora.unlink(missing_ok=True)

    def close(self):
        self.adapter.close()
        from .resources import release_idle_comfy
        release_idle_comfy()
