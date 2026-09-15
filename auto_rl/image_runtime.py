"""Connect an audited image adapter to compatible production ComfyUI graphs."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from .config import ROOT
from .runtime import validated_record


def apply_validated_workflow(workflow, module="image"):
    if not isinstance(workflow, dict):
        raise ValueError('Le workflow ComfyUI doit être un objet')
    if module not in {'image','video'}:raise ValueError('Module ComfyUI inconnu')
    from .versions import preference
    if preference(module)=='base':
        graph=deepcopy(workflow)
        # A previously decorated graph can be resubmitted after choosing base.
        # Remove only Aurora's own adapters and restore their exact input links.
        for key,node in list(graph.items()):
            if not str(key).startswith(f'aurora_trained_{module}_'):continue
            inputs=node.get('inputs',{})
            if node.get('class_type')!='LoraLoaderModelOnly' or not str(inputs.get('lora_name','')).startswith('aurora_validated/'):
                raise ValueError('Nœud réservé Aurora incompatible')
            for other in graph.values():
                if isinstance(other,dict) and other.get('inputs',{}).get('model')==[key,0]:
                    other['inputs']['model']=deepcopy(inputs['model'])
            del graph[key]
        return graph
    record = validated_record(module)
    if not record:
        return workflow
    config = record['config']
    if config.get('trainer') != 'surrogate_es':
        raise ValueError('Cet adaptateur image ne cible pas le backend GGUF')
    model_name = Path(config['video_unet'] if module=='video' else config['comfy_unet']).name
    loaders = [key for key, node in workflow.items()
               if isinstance(node, dict) and node.get('class_type') in {'UnetLoaderGGUF', 'UNETLoader'}
               and node.get('inputs', {}).get('unet_name') == model_name]
    if not loaders:
        return workflow
    from safetensors import safe_open
    from safetensors.torch import load_file
    from .comfy_backend import export_comfy_lora
    tensors = load_file(record['adapter'])
    with safe_open(record['adapter'], framework='pt', device='cpu') as f:
        meta = f.metadata()
    if meta.get('kind') != 'aurora-weight-subspace-v1':
        raise ValueError('Format de poids image incompatible')
    targets = json.loads(meta['targets'])
    adapter = SimpleNamespace(rank=int(meta['rank']), layers=[
        {'name': name, **{k: tensors[f'{i}.{k}'] for k in ('a', 'b', 'c')}}
        for i, name in enumerate(targets)])
    folder = ROOT / 'modele/comfyui/models/loras/aurora_validated'
    folder.mkdir(parents=True, exist_ok=True)
    filename = record['sha256'] + '.safetensors'
    export_comfy_lora(adapter, folder / filename)
    graph = deepcopy(workflow)
    for loader in loaders:
        key = f'aurora_trained_{module}_{loader}'
        if key in graph:
            node = graph[key]
            if (node.get('class_type') != 'LoraLoaderModelOnly'
                    or node.get('inputs', {}).get('model') != [loader, 0]):
                raise ValueError('Identifiant de nœud réservé à l’adaptateur Aurora')
        for other_key, node in graph.items():
            if other_key != key and isinstance(node, dict) and node.get('inputs', {}).get('model') == [loader, 0]:
                node['inputs']['model'] = [key, 0]
        graph[key] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {
            'model': [loader, 0], 'lora_name': 'aurora_validated/' + filename, 'strength_model': 1.0}}
    return graph
