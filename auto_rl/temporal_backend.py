"""Real Wan video diffusion and HY-Motion skeleton generation."""
from pathlib import Path
import os
import sys
import numpy as np
import torch
from .config import ROOT
from .adapters import WeightSubspace
from .backends import local_snapshot, seed_all
from .comfy_backend import ComfyImageBackend, shape_model
from .storage import atomic_json


def temporal_paths(c):
    if c['module']=='video':
        paths={'video':c['video_unet'],'video_clip':c['video_clip'],'video_vae':c['video_vae'],
               'clip':local_snapshot(c['models']['clip'])}
    else:
        root=Path(c['hymotion_root'])
        checkpoint=root/'ckpts/tencent/HY-Motion-1.0'
        if not (checkpoint/'latest.ckpt').is_file():checkpoint=root/'ckpts/HY-Motion-1.0'
        paths={'animation':str(checkpoint/'latest.ckpt'),'motion_config':str(checkpoint/'config.yml'),
               'motion_stats':str(root/'stats'),'motion_assets':str(root/'scripts/gradio/static/assets/dump_wooden'),
               'motion_text':local_snapshot(c['models']['motion_text']),
               'motion_clip':local_snapshot(c['models']['motion_clip'])}
    for name,path in paths.items():
        if not Path(path).exists():raise RuntimeError(f'Poids ou ressources {name} absents : {path}')
    return paths


def video_workflow(c,task,seed,path):
    g=c['generation']
    return {
        '12':{'class_type':'UNETLoader','inputs':{'unet_name':Path(c['video_unet']).name,'weight_dtype':'default'}},
        '11':{'class_type':'CLIPLoaderGGUF','inputs':{'clip_name':Path(c['video_clip']).name,'type':'wan'}},
        '10':{'class_type':'VAELoader','inputs':{'vae_name':Path(c['video_vae']).name}},
        '6':{'class_type':'CLIPTextEncode','inputs':{'clip':['11',0],'text':task['prompt']}},
        '7':{'class_type':'CLIPTextEncode','inputs':{'clip':['11',0],'text':'static image, frozen motion, flicker, deformed, blurry, low quality'}},
        '26':{'class_type':'ModelSamplingSD3','inputs':{'model':['12',0],'shift':g['video_shift']}},
        '5':{'class_type':'Wan22ImageToVideoLatent','inputs':{'vae':['10',0],'width':g['width'],'height':g['height'],'length':g['frames'],'batch_size':1}},
        '3':{'class_type':'KSampler','inputs':{'model':['26',0],'positive':['6',0],'negative':['7',0],'latent_image':['5',0],
              'seed':seed,'steps':g['steps'],'cfg':g['video_cfg'],'sampler_name':'uni_pc','scheduler':'simple','denoise':1.0}},
        '8':{'class_type':'VAEDecodeTiled','inputs':{'samples':['3',0],'vae':['10',0],'tile_size':256,'overlap':64,'temporal_size':16,'temporal_overlap':4}},
        '9':{'class_type':'SaveAnimatedWEBP','inputs':{'images':['8',0],'filename_prefix':'aurora_training/'+Path(path).stem,
              'fps':g['fps'],'lossless':True,'quality':100,'method':'default'}},
    }


class TemporalTasks:
    def prepare_tasks(self,root,check,sandbox=None):
        from .temporal_tasks import build_tasks
        tasks=build_tasks(self.c)
        for task in tasks:
            check();atomic_json(root/(task['id']+'.json'),task)
        return tasks


class VideoBackend(TemporalTasks,ComfyImageBackend):
    suffix='.webp'
    def __init__(self,c,paths):
        self.c={**c,'comfy_unet':c['video_unet'],'comfy_clip':c['video_clip'],'comfy_vae':c['video_vae']}
        self.shape_model=shape_model(paths['video'])
        self.adapter=WeightSubspace(self.shape_model,c['rank'],c['max_layers'],c['seed'])
        self.last_peak_vram_gb=0.;self.check=lambda:None

    def build_workflow(self,task,seed,path):return video_workflow(self.c,task,seed,path)


class AnimationBackend(TemporalTasks):
    suffix='.npz'
    def __init__(self,c,paths):
        self.c=c
        root=Path(c['hymotion_root'])
        sys.path.insert(0,str(root))
        os.environ['USE_HF_MODELS']='1'
        # HY-Motion's Qwen encoder is larger than the remaining VRAM beside
        # the motion DiT. Keep it in host RAM at full precision and transfer
        # only its compact conditioning tensors for each generation. The old
        # forced 4-bit CUDA path was the direct cause of the 15.46 GiB OOM.
        os.environ['AURORA_LLM_DEVICE']='cpu'
        os.environ['AURORA_LLM_4BIT']='0'
        # Bind the encoder to the exact local snapshots fingerprinted in this run.
        from hymotion.network.text_encoders import text_encoder
        text_encoder.LLM_ENCODER_LAYOUT['qwen3']['module_path']=paths['motion_text']
        text_encoder.SENTENCE_EMB_LAYOUT['clipl']['module_path']=paths['motion_clip']
        from hymotion.utils.t2m_runtime import T2MRuntime
        old=os.getcwd()
        try:
            os.chdir(root)
            # Do not let the upstream loader construct Qwen before moving the
            # motion pipeline to CUDA: its temporary 4-bit copy is enough to
            # fill a 16 GiB card and the subsequent `.to(cuda)` then fails.
            # The encoder is built explicitly on CPU below.
            self.runtime=T2MRuntime(config_path=paths['motion_config'],ckpt_name=paths['animation'],
                                    device_ids=[0],skip_text=True,disable_prompt_engineering=True)
        finally:os.chdir(old)
        self.pipe=self.runtime.pipelines[0]
        # T2MRuntime calls pipeline.to(cuda) after constructing the encoder;
        # force every text encoder submodule back to CPU so it cannot silently
        # reoccupy the motion card.
        from hymotion.utils.loaders import load_object
        text_encoder=load_object(self.pipe._text_encoder_module,self.pipe._text_encoder_cfg)
        text_encoder.to('cpu')
        text_encoder.eval().requires_grad_(False)
        self.pipe.text_encoder=text_encoder
        self.pipe.validation_steps=c['generation']['steps']
        self.adapter=WeightSubspace(self.pipe.motion_transformer,c['rank'],c['max_layers'],c['seed'])

    def generate(self,task,seed,path,feedback=None):
        seed_all(seed)
        device=next(self.pipe.motion_transformer.parameters()).device
        with torch.inference_mode():
            # Encode on CPU, then move only the small conditioning tensors to
            # the DiT. This preserves the original model quality while making
            # the peak allocation independent of the 8B text encoder size.
            hidden=self.pipe.encode_text({'text':[task['prompt']]})
            hidden={key:value.to(device, non_blocking=True) for key,value in hidden.items()}
            output=self.pipe.generate(task['prompt'],[seed],task['duration'],
                cfg_scale=self.c['generation']['motion_cfg'],hidden_state_dict=hidden)
            # Upstream WoodenMesh returns body-local joints while vertices and
            # transl are world-space. Rebuild joints with the aligned translation
            # so travel/contacts measure actual movement, not a stationary pelvis.
            device=next(self.pipe.body_model.buffers()).device
            pose={'rot6d':output['rot6d'].to(device),'trans':output['transl'].to(device)}
            body=self.pipe.body_model.forward_batch(pose)
            output['keypoints3d']=(body['keypoints3d']+pose['trans'][:,:,None,:]).cpu()
        arrays={key:value.detach().cpu().numpy() for key,value in output.items() if isinstance(value,torch.Tensor)}
        np.savez_compressed(path,**arrays)
        return str(path)

    def close(self):
        self.adapter.close()
        self.runtime.pipelines.clear()
        del self.pipe,self.runtime
        import gc
        gc.collect();torch.cuda.empty_cache()
