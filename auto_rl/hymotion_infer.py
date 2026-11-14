"""Production HY-Motion launcher, attaching only an audited matching adapter."""
import os
import runpy
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
root=Path(os.environ.get('AURORA_HYMOTION_ROOT',Path.home()/'.local/share/auroraia/external/HY-Motion'))
sys.path.insert(0,str(root))
from auto_rl.backends import local_snapshot
from hymotion.network.text_encoders import text_encoder
try:
    text_encoder.LLM_ENCODER_LAYOUT['qwen3']['module_path']=local_snapshot('Qwen/Qwen3-8B')
    text_encoder.SENTENCE_EMB_LAYOUT['clipl']['module_path']=local_snapshot('openai/clip-vit-large-patch14')
except Exception:
    pass
from hymotion.utils.t2m_runtime import T2MRuntime
from auto_rl.runtime import validated_record,attach_validated

original_load=T2MRuntime.load


def load(self):
    orig_skip = getattr(self, 'skip_text', False)
    if os.environ.get('AURORA_LLM_DEVICE', 'cpu').lower() == 'cpu':
        self.skip_text = True
    original_load(self)
    self.skip_text = orig_skip
    if not orig_skip and os.environ.get('AURORA_LLM_DEVICE', 'cpu').lower() == 'cpu':
        from hymotion.utils.loaders import load_object
        for pipeline in self.pipelines:
            if not getattr(pipeline, 'uncondition_mode', False) and not hasattr(pipeline, 'text_encoder'):
                te = load_object(pipeline._text_encoder_module, pipeline._text_encoder_cfg)
                te.to('cpu')
                te.eval().requires_grad_(False)
                pipeline.text_encoder = te
                orig_encode = pipeline.encode_text
                def _encode_to_dit_device(text_dict, _orig=orig_encode, _pipe=pipeline):
                    out = _orig(text_dict)
                    dev = next(_pipe.motion_transformer.parameters()).device
                    return {k: (v.to(dev, non_blocking=True) if hasattr(v, 'to') else v) for k, v in out.items()}
                pipeline.encode_text = _encode_to_dit_device

    from auto_rl.versions import preference
    if preference('animation')=='base' or os.environ.get('AURORA_ANIMATION_VARIANT','').lower()=='base':
        print('>>> [Aurora Animation] Variante active : BASE INTOUCHABLE (tencent/HY-Motion-1.0)', flush=True)
        return
    record=validated_record('animation')
    if not record:return
    from auto_rl.temporal_backend import temporal_paths
    expected=Path(temporal_paths(record['config'])['animation']).resolve()
    if Path(self.ckpt_name).resolve()!=expected:
        raise ValueError('Le moteur animation utilise un autre checkpoint que celui de l’audit')
    for pipeline in self.pipelines:
        model=pipeline.motion_transformer
        if not getattr(model,'_aurora_validated_adapter',None):
            att=attach_validated(model,'animation','tencent/HY-Motion-1.0')
            if att:
                print(f">>> [Aurora Animation] Variante active : RENFORCÉ ({att.get('name')})", flush=True)


T2MRuntime.load=load
if __name__=='__main__':runpy.run_path(str(root/'local_infer.py'),run_name='__main__')


