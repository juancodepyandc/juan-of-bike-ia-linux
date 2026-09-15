"""Temporal diagnostics. These proxies cannot certify exact action semantics."""
import numpy as np
from .judges import result


class VideoJudge:
    def __init__(self,clip):self.clip=clip

    def score(self,artifact,task):
        import cv2
        from PIL import Image, ImageSequence
        with Image.open(artifact) as im:
            frames=[frame.convert('RGB').copy() for frame in ImageSequence.Iterator(im)]
        if len(frames)!=task['frames']:
            return result(0,{'frames':len(frames)},False,['Séquence tronquée ou image fixe'])
        small=[cv2.cvtColor(np.array(f.resize((160,96))),cv2.COLOR_RGB2GRAY) for f in frames]
        motion=[];warps=[];flicker=[]
        yy,xx=np.mgrid[:96,:160].astype(np.float32)
        for prev,cur in zip(small,small[1:]):
            flow=cv2.calcOpticalFlowFarneback(cur,prev,None,.5,3,15,3,5,1.2,0)
            warped=cv2.remap(prev,xx+flow[:,:,0],yy+flow[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
            motion.append(float(np.linalg.norm(flow,axis=-1).mean()))
            warps.append(float(np.abs(cur.astype(float)-warped).mean()/255))
            flicker.append(abs(float(cur.mean())-float(prev.mean()))/255)
        ids=np.linspace(0,len(frames)-1,8).astype(int)
        scores=self.clip.scores([frames[i] for i in ids],task['prompt'])
        alignment=float(np.mean(scores));moving=float(np.mean(motion));warp=float(np.mean(warps))
        contrast=float(np.mean([f.std()/255 for f in small]))
        valid=contrast>.012 and moving>.01
        score=.65*alignment+.25*max(0,1-warp*8)+.1*min(1,moving/.3)
        return result(score,{'frames':len(frames),'clip_mean':alignment,'flow_pixels_per_frame':moving,
                             'motion_compensated_error':warp,'luminance_change':float(np.mean(flicker)),
                             'contrast':contrast},valid,[] if valid else ['Vidéo uniforme ou sans mouvement mesurable'],
                      ['CLIP et flux optique ne prouvent pas que chaque action demandée est correcte.',
                       'Audit sur séquences courtes, sans audio ni cohérence de long métrage.'])


class AnimationJudge:
    def score(self,artifact,task):
        with np.load(artifact,allow_pickle=False) as data:
            xyz=data['keypoints3d'][0].astype(float)
            rotation=data['rot6d'][0].astype(float)
        if xyz.ndim!=3 or xyz.shape[1] not in {22,52} or xyz.shape[2]!=3 or not np.isfinite(xyz).all() or not np.isfinite(rotation).all():
            return result(0,{},False,['Squelette ou rotations invalides'])
        # WoodenMesh supplies 52 joints including fingers; the body rotations
        # cover the first 22 SMPL joints. Finger joints are not body bones.
        xyz=xyz[:,:22]
        if len(xyz)!=round(task['duration']*30):
            return result(0,{'frames':len(xyz)},False,['Durée de mouvement incorrecte'])
        # SMPL 22-joint hierarchy, metres, Y up, 30 fps (HY-Motion output).
        parents=[-1,0,0,0,1,2,3,4,5,6,7,8,9,9,9,12,13,14,16,17,18,19]
        lengths=np.stack([np.linalg.norm(xyz[:,i]-xyz[:,p],axis=-1) for i,p in enumerate(parents) if p>=0],axis=1)
        bone_cv=float(np.mean(lengths.std(0)/np.maximum(lengths.mean(0),1e-6)))
        velocity=np.diff(xyz,axis=0)*30
        acceleration=np.diff(velocity,axis=0)*30
        jerk=float(np.linalg.norm(np.diff(acceleration,axis=0)*30,axis=-1).mean())
        travel=float(np.linalg.norm(xyz[-1,0,[0,2]]-xyz[0,0,[0,2]]))
        vertical=float(np.ptp(xyz[:,0,1]))
        hands=float(np.linalg.norm(np.diff(xyz[:,[20,21]]-xyz[:,0,None],axis=0),axis=-1).sum(0).mean())
        feet=xyz[:,[7,8,10,11]];contact=feet[:-1,:,1]<.06
        speed=np.linalg.norm(np.diff(feet[:,:,[0,2]],axis=0)*30,axis=-1)
        slide=float(speed[contact].mean()) if contact.any() else 0.0
        action={'travel':min(1,travel/.5),'vertical':min(1,vertical/.25),'hands':min(1,hands/.6)}[task['motion']]
        ground=float(np.maximum(0,-feet[:,:,1]).mean())
        moving=float(np.linalg.norm(velocity,axis=-1).mean())
        valid=bone_cv<.05 and moving>.01 and np.all(lengths.mean(0)>.01)
        score=.35*action+.25/(1+jerk/100)+.2/(1+slide)+.2*max(0,1-bone_cv*20-ground*20)
        return result(score,{'frames':len(xyz),'bone_length_cv':bone_cv,'jerk_m_s3':jerk,
                             'foot_slide_m_s':slide,'root_travel_m':travel,'root_height_range_m':vertical,
                             'hand_travel_m':hands,'action_proxy':action,'ground_penetration_m':ground},valid,
                      [] if valid else ['Squelette déformé ou mouvement absent'],
                      ['Les mesures cinématiques ne certifient ni une chorégraphie exacte ni la qualité du retargeting.'])
