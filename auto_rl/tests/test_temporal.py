import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from flask import Flask
from auto_rl.config import defaults,validate,LABELS
from auto_rl.temporal_tasks import build_tasks
from auto_rl.temporal_judges import AnimationJudge,VideoJudge
from auto_rl.learning_curriculum import build_tasks as learning_tasks
from auto_rl.judges import ConversationJudge
from auto_rl.integration import register_routes


class TemporalTests(unittest.TestCase):
    def test_ten_modules_with_disjoint_learning_and_temporal_audits(self):
        self.assertEqual(len(LABELS),10)
        for module in ('learning','video','animation'):
            c=defaults(module);c.update(mode='auto',eval_tasks=8)
            validate(c)
            tasks=learning_tasks(c) if module=='learning' else build_tasks(c)
            self.assertFalse({t['family'] for t in tasks[:c['train_tasks']]} & {t['family'] for t in tasks[c['train_tasks']:]})

    def test_educational_oracles_are_scored_and_wrong_answers_fail(self):
        c=defaults('learning');c.update(train_tasks=10,eval_tasks=8)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'response.txt'
            for task in learning_tasks(c):
                p.write_text(json.dumps(task['expected_json']))
                self.assertEqual(ConversationJudge().score(p,task)['score'],1)
                p.write_text('{"answers":[null,null,null]}')
                self.assertEqual(ConversationJudge().score(p,task)['score'],0)

    def test_still_image_is_not_a_video(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'still.webp';Image.new('RGB',(128,128),'blue').save(p)
            self.assertFalse(VideoJudge(None).score(p,{'frames':33})['valid'])

    def test_skeleton_world_translation_and_static_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'motion.npz'
            xyz=np.zeros((1,90,52,3));xyz[:,:,:,1]=np.arange(52)*.1
            xyz[:,:,:,0]=np.linspace(0,2,90)[None,:,None]
            np.savez(p,keypoints3d=xyz,rot6d=np.ones((1,90,22,6)))
            task={'duration':3,'motion':'travel'}
            score=AnimationJudge().score(p,task)
            self.assertTrue(score['valid']);self.assertAlmostEqual(score['metrics']['root_travel_m'],2)
            xyz[:,:,:,0]=0;np.savez(p,keypoints3d=xyz,rot6d=np.ones((1,90,22,6)))
            self.assertFalse(AnimationJudge().score(p,task)['valid'])
            xyz[0,0,0,0]=np.nan;np.savez(p,keypoints3d=xyz,rot6d=np.ones((1,90,22,6)))
            self.assertFalse(AnimationJudge().score(p,task)['valid'])

    def test_media_ui_and_file_boundary(self):
        app=Flask(__name__);urls=[]
        register_routes(app,lambda url:urls.append(url) or {'ok':True})
        client=app.test_client()
        with client.get('/api/training/ui') as response:self.assertEqual(response.status_code,200)
        self.assertEqual(client.get('/api/training/artifact/../../config.py').status_code,404)
        self.assertEqual(client.post('/api/training/media',json={}).status_code,200)
        self.assertEqual(urls,['http://127.0.0.1:11435/api/media/generate'])
        with patch('auto_rl.integration.validated_record',return_value=None):
            self.assertEqual(len(client.get('/api/training/status').json['modules']),10)

    def test_temporal_bounds_reject_silent_clamping(self):
        c=defaults('video');c['generation']['frames']=32
        with self.assertRaises(ValueError):validate(c)
        c=defaults('animation');c['generation']['duration']=20
        with self.assertRaises(ValueError):validate(c)


if __name__=='__main__':unittest.main()
