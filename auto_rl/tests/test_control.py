import json
import os
from pathlib import Path
import re
import tempfile
import time
import unittest
from unittest.mock import patch
from flask import Flask
from auto_rl import control, versions
from auto_rl.integration import register_routes
from auto_rl.storage import atomic_json, read_json, exclusive_lock


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='aurora-rl-test-')
        self.state=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def record(self, **fields):
        record={'schema':1,'session_id':'test-session','phase':'starting','started_at':time.time(),
                'module':'3d','mode':'once','training_minutes':30,'completed_cycles':0,'history':[]}
        record.update(fields)
        atomic_json(self.state/'control.json',record)
        return record

    def test_start_rejects_duplicate_and_engine_lock(self):
        with patch.object(control,'launch') as launch:
            first=control.start({'module':'3d'},self.state)
            self.assertTrue(first['active'])
            with self.assertRaises(RuntimeError):control.start({'module':'code'},self.state)
            launch.assert_called_once()
        self.record(phase='complete')
        with exclusive_lock(self.state/'cycle.lock'), patch.object(control,'launch') as launch:
            with self.assertRaises(RuntimeError):control.start({},self.state)
            launch.assert_not_called()

    def test_dead_and_recycled_processes_are_not_live(self):
        self.record(phase='running',pid=os.getpid(),process_identity='wrong',heartbeat_at=time.time()-15)
        result=control.snapshot(self.state)
        self.assertFalse(result['active']);self.assertEqual(result['phase'],'interrupted')
        self.assertLess(result['elapsed_seconds'],1)

    def test_controls_do_not_cancel_the_remote_job(self):
        record=self.record()
        command=control.request('stop',state=self.state)
        self.assertEqual(command['session_id'],record['session_id'])
        self.assertFalse(list(self.state.rglob('stop_signal.txt')))
        self.assertTrue(control.snapshot(self.state)['active'])

    def test_old_stop_cannot_stop_a_new_session(self):
        old=self.record();control.request('stop',state=self.state)
        new=self.record(session_id='next',phase='running')
        self.assertTrue(control.apply_boundary(self.state,new))
        self.assertFalse(control.pending(self.state,new))

    def test_invalid_options_never_reach_the_launcher(self):
        with patch.object(control,'launch') as launch:
            for bad in (None,[],{'module':[]},{'module':'unknown'},{'training_minutes':True},
                        {'training_minutes':1800},{'mode':'forever'},{'command':'rm -rf'}):
                with self.assertRaises(ValueError):control.start(bad,self.state)
            launch.assert_not_called()

    def run_fake_worker(self, mode='once', after_poll=None):
        record=self.record(mode=mode)
        jobs=[]
        state=self.state
        class Child:
            def __init__(self,argv,**kwargs):
                self.config=read_json(Path(argv[-1]));self.pid=900000+len(jobs)
                self.returncode=None;self.polls=0;self.index=len(jobs)+1
                jobs.append(self)
            def poll(self):
                self.polls+=1
                if self.polls==1:
                    atomic_json(state/'status.json',{'pid':self.pid,'run_id':f'run-{self.index}',
                                'module':self.config['module'],'phase':'cloud_training'})
                    if after_poll:after_poll(self)
                    return None
                # Simulate durable export BEFORE marking the cycle finished.
                folder=state/'runs'/f'run-{self.index}';folder.mkdir(parents=True,exist_ok=True)
                (folder/'candidate.safetensors').write_bytes(b'saved checkpoint')
                atomic_json(state/'status.json',{'pid':self.pid,'run_id':folder.name,
                            'module':self.config['module'],'phase':'rejected'})
                self.returncode=0
                return 0
        with patch.object(control.subprocess,'Popen',Child),patch.object(control.time,'sleep'), \
             patch('auto_rl.cloud.quota',return_value={'remaining_seconds':7200}), \
             patch.object(control.signal,'signal'):
            result=control.worker(record['session_id'],state)
        self.assertEqual(result,0)
        return jobs,read_json(state/'control.json')

    def test_fixed_cycle_finishes_after_export(self):
        jobs,record=self.run_fake_worker()
        self.assertEqual(len(jobs),1);self.assertEqual(record['phase'],'complete')
        self.assertTrue((self.state/'runs/run-1/candidate.safetensors').exists())

    def test_continuous_survives_rejections_and_stops_at_boundary(self):
        def stop_on_third(child):
            if child.index==3:control.request('stop',state=self.state)
        jobs,record=self.run_fake_worker('continuous',stop_on_third)
        self.assertEqual(len(jobs),3);self.assertEqual(record['phase'],'stopped')
        self.assertEqual(record['completed_cycles'],3)
        self.assertTrue(all(row['outcome']=='rejected' for row in record['history']))
        self.assertTrue((self.state/'runs/run-3/candidate.safetensors').exists())

    def test_switch_waits_for_export_then_runs_selected_module(self):
        def switch(child):
            if child.index==1:
                control.request('switch',{'module':'video','mode':'once','training_minutes':10},self.state)
                self.assertFalse((self.state/'runs/run-1/candidate.safetensors').exists())
            else:self.assertTrue((self.state/'runs/run-1/candidate.safetensors').exists())
        jobs,record=self.run_fake_worker('continuous',switch)
        self.assertEqual([job.config['module'] for job in jobs],['3d','video'])
        self.assertEqual(jobs[1].config['training_budget_seconds'],600)
        self.assertEqual(record['phase'],'complete')
        self.assertNotIn('requested',control.snapshot(self.state))

    def test_quota_wait_remains_stoppable_without_launch(self):
        record=self.record(mode='continuous')
        def sleeping(seconds):
            control.request('stop',state=self.state)
        with patch('auto_rl.cloud.quota',return_value={'remaining_seconds':100}), \
             patch.object(control.time,'sleep',side_effect=sleeping),patch.object(control.subprocess,'Popen') as launch, \
             patch.object(control.signal,'signal'):
            self.assertEqual(control.worker(record['session_id'],self.state),0)
            launch.assert_not_called()
        self.assertEqual(read_json(self.state/'control.json')['phase'],'stopped')

    def test_all_module_profiles_train_instead_of_replaying_old_audits(self):
        for module in control.LABELS:
            c=control.cycle_config({'module':module,'training_minutes':30},1,self.state)
            self.assertNotIn('resume_audit',c)
            self.assertEqual(c['mode'],'auto');self.assertGreaterEqual(c['eval_tasks'],8)
            self.assertFalse(c['fallback_on_quota'])
            self.assertEqual(c['training_budget_seconds'],1800)

    def test_no_rejected_candidate_is_selectable_for_production(self):
        with patch('auto_rl.runtime.validated_record',return_value=None):
            with self.assertRaises(ValueError):versions.select('3d','validated',self.state)
        with self.assertRaises(ValueError):versions.select('3d','candidate',self.state)
        versions.select('3d','base',self.state)
        self.assertEqual(versions.preference('3d',self.state),'base')
        from auto_rl.runtime import catalog
        models=catalog(self.state,include_base=True)
        self.assertEqual(len(models),10)
        self.assertTrue(all(m['selection']=='base' for m in models))

    def test_continuous_partition_never_trains_on_previous_audit_families(self):
        from auto_rl.curriculum import build_tasks
        for module in ('code','conversation','cyber','cowork','learning'):
            training,audit=set(),set()
            for cycle in range(6):
                c=control.cycle_config({'module':module,'training_minutes':30},cycle,self.state)
                tasks=build_tasks(c)
                training.update(t['family'] for t in tasks[:c['train_tasks']])
                audit.update(t['family'] for t in tasks[c['train_tasks']:])
            self.assertFalse(training & audit,module)

    def test_media_curriculum_remains_available_after_queue_items_move(self):
        c=control.cycle_config({'module':'3d','training_minutes':30},0,self.state)
        cache=self.state/'control_curricula'/(c['control_curriculum_key']+'.json')
        atomic_json(cache,[{'id':'preserved-reference','image':'/original/run/tasks/image.png'}])
        next_cycle=control.cycle_config({'module':'3d','training_minutes':30},4,self.state)
        self.assertEqual(next_cycle['prepared_tasks'],str(cache))
        self.assertNotEqual(c['seed'],next_cycle['seed'])

    def test_ui_control_requires_token_and_same_origin(self):
        flask=Flask(__name__)
        with patch('auto_rl.integration.STATE',self.state):
            register_routes(flask,lambda url:{'ok':True})
            client=flask.test_client()
            html=client.get('/api/training/ui').text
            token=re.search("token='([^']+)'",html).group(1)
            self.assertNotEqual(token,'__CONTROL_TOKEN__')
            self.assertEqual(client.post('/api/training/control/start',json={}).status_code,403)
            headers={'X-Aurora-Control':token,'Origin':'https://evil.example'}
            self.assertEqual(client.get('/api/training/ui',headers=headers).status_code,403)
            self.assertEqual(client.post('/api/training/control/start',json={},headers=headers).status_code,403)
            headers['Origin']='http://localhost:1420'
            with patch.object(control,'launch') as launch:
                self.assertEqual(client.post('/api/training/control/start',json={'module':'animation'},headers=headers).status_code,202)
                self.assertEqual(client.post('/api/training/control/start',json={},headers=headers).status_code,409)
                self.assertEqual(client.post('/api/training/control/stop',json={},headers=headers).status_code,202)
                launch.assert_called_once()


if __name__=='__main__':unittest.main()
