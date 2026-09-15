"""Production HY-Motion launcher, attaching only an audited matching adapter."""
import os
import runpy
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
root=Path(os.environ.get('AURORA_HYMOTION_ROOT',Path.home()/'.local/share/auroraia/external/HY-Motion'))
sys.path.insert(0,str(root))
from hymotion.utils.t2m_runtime import T2MRuntime
from auto_rl.runtime import validated_record,attach_validated

original_load=T2MRuntime.load


def load(self):
    original_load(self)
    from auto_rl.versions import preference
    if preference('animation')=='base':return
    record=validated_record('animation')
    if not record:return
    from auto_rl.temporal_backend import temporal_paths
    expected=Path(temporal_paths(record['config'])['animation']).resolve()
    if Path(self.ckpt_name).resolve()!=expected:
        raise ValueError('Le moteur animation utilise un autre checkpoint que celui de l’audit')
    for pipeline in self.pipelines:
        model=pipeline.motion_transformer
        if not getattr(model,'_aurora_validated_adapter',None):
            attach_validated(model,'animation','tencent/HY-Motion-1.0')


T2MRuntime.load=load
if __name__=='__main__':runpy.run_path(str(root/'local_infer.py'),run_name='__main__')
