import asyncio
from dataclasses import replace
import sys
from unittest.mock import AsyncMock

from agi_core.process_progress import EngineProgress
from agi_core.mission_agent import AutonomousMissionAgent


def test_fragmented_progress_is_bounded_rate_limited_and_keeps_latest_stage():
    progress=EngineProgress(interval_seconds=1.,line_chars=64)
    assert progress.feed('irrelevant noise'*1000,now=0) is None
    assert len(progress.line)<=64
    progress.feed('\nPROG',now=0)
    assert progress.feed('RESS:geometry:10%\n',now=0)=='PROGRESS:geometry:10%'
    assert progress.feed('PROGRESS:texture:20%\n',now=.1) is None
    assert progress.feed('PROGRESS:texture:90%\n',now=.2) is None
    assert progress.feed('',now=1)=='PROGRESS:texture:90%'
    assert progress.feed('PROGRESS:texture:90%\n',now=2) is None
    assert progress.feed('PROGRESS:delivery:complete',now=2,final=True)=='PROGRESS:delivery:complete'


def test_actual_process_keeps_progress_after_bounded_diagnostic_output(tmp_path):
    agent=AutonomousMissionAgent('mis_progress','Inspect actual process progress',str(tmp_path),'fixture')
    agent.state['plan']=['Run controlled process'];agent.policy=replace(agent.policy,output_chars=64)
    agent._emit=AsyncMock()
    async def save():pass
    agent._save=save
    command=[sys.executable,'-u','-c',r'print("x"*200+"\nPROGRESS:geometry:actual stage",flush=True)']
    asyncio.run(agent._run_process(command))
    output=[call.args[1] for call in agent._emit.await_args_list if call.args[0]=='command_output']
    assert any(item.get('kind')=='engine_progress' and 'actual stage' in item['content'] for item in output)
    assert len(agent.state['process_observations'][-1]['result']['output'])<=64
    assert agent.state['process_observations'][-1]['result']['status']=='completed'
