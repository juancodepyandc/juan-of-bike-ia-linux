"""Kaggle optimization of a low-rank image adapter from measured PC rewards.

This trains a reward surrogate, then proposes bounded weight coefficients.
Predicted improvement NEVER authorizes deployment: the PC audits actual images.
"""
from pathlib import Path
import json
import time
import torch
from safetensors.torch import load_file,save_file
from safetensors import safe_open
from .storage import atomic_json


def optimize(c,root,out,callback):
    root,out=Path(root),Path(out)
    records=json.loads((root/'observations.json').read_text())
    if len(records)<6:raise ValueError('Six essais mesurés minimum pour le modèle de récompense')
    torch.manual_seed(c['seed'])
    device='cuda' if torch.cuda.is_available() else 'cpu'
    x=torch.tensor([r['vector'] for r in records],dtype=torch.float32,device=device)
    y=torch.tensor([r['reward'] for r in records],dtype=torch.float32,device=device)[:,None]
    if not torch.isfinite(x).all() or not torch.isfinite(y).all():raise ValueError('Mesures non finies')
    center=x.mean(0);scale=x.std(0).clamp_min(.01)
    normalized=(x-center)/scale
    # Regularized linear/quadratic reward fit. Small model, explicit scope.
    features=torch.cat([torch.ones_like(normalized[:,:1]),normalized,normalized.square()],1)
    penalty=torch.eye(features.shape[1],device=device)*.1;penalty[0,0]=1e-6
    weights=torch.linalg.solve(features.T@features+penalty,features.T@y)
    fit_loss=float((features@weights-y).square().mean())
    baseline=x[y[:,0].argmax()]
    if c.get('coordinate_search'):
        proposals=[baseline]
        axes=torch.eye(x.shape[1],device=device)
        for radius in (c['sigma'],c['sigma']*.5,c['sigma']*.25):
            proposals.extend([baseline+axis*sign*radius for axis in axes for sign in (-1,1)])
        point=baseline.clone()
        for _ in range(32):
            z=(point-center)/scale
            gradient=(weights[1:1+x.shape[1],0]+2*z*weights[1+x.shape[1]:,0])/scale
            point=point+c['sigma']*.1*gradient/gradient.norm().clamp_min(1e-8)
            point=point*min(1.,c['trust_radius']/max(float(point.norm()),1e-8))
            proposals.append(point.clone())
        candidates=torch.stack(proposals)
    else:
        candidates=baseline+torch.randn(2048,x.shape[1],device=device)*c['sigma']*.5
        candidates=torch.cat([baseline[None],candidates],0)
    candidates *= (c['trust_radius']/candidates.norm(dim=1).clamp_min(c['trust_radius']))[:,None]
    z=(candidates-center)/scale
    predictions=(torch.cat([torch.ones_like(z[:,:1]),z,z.square()],1)@weights)[:,0]
    # Penalize extrapolation from actually measured coefficient vectors.
    distance=torch.cdist(candidates,x).min(1).values
    choice=(predictions-distance*.1).argmax()
    vector=candidates[choice].cpu()
    tensors=load_file(str(root/'initial.safetensors'))
    with safe_open(str(root/'initial.safetensors'),framework='pt',device='cpu') as f:meta=f.metadata()
    rank=int(meta['rank']);targets=json.loads(meta['targets'])
    if vector.numel()!=rank*len(targets):raise ValueError('Dimension des coefficients incompatible')
    for i in range(len(targets)):tensors[f'{i}.c']=vector[i*rank:(i+1)*rank].contiguous()
    save_file(tensors,str(out/'candidate.safetensors'),metadata=meta)
    metrics={'algorithm':'measured_reward_surrogate_ES','observations':len(records),'fit_mse':fit_loss,
             'proposal_method':'deterministic_coordinates_and_surrogate_gradient' if c.get('coordinate_search') else 'seeded_gaussian',
             'completed_epochs':1,'requested_epochs':1,'training_gpu':torch.cuda.get_device_name(0) if device=='cuda' else 'cpu',
             'predicted_reward':float(predictions[choice]),'note':'Ajustement de récompense et proposition de coefficients. Les essais FLUX sont effectués sur le PC ; le gain prédit n’est pas un gain de qualité démontré.'}
    atomic_json(out/'training_metrics.json',metrics)
    callback({'epoch':1,'loss':fit_loss})
