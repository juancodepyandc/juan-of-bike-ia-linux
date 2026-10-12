import asyncio
from agi_core.mission_store import MissionStore
from agi_core.mission_scheduler import schedule_queue


async def _fifo(tmp_path):
    store=MissionStore(tmp_path/'queue.sqlite3');payload={'request':'Compute a project','model':'fixture'}
    jobs=[store.create(payload,str(i),queued=True)[0] for i in range(3)]
    store=MissionStore(store.path);active={};started=[];release=asyncio.Event();wake=asyncio.Event()
    async def execute(payload):
        mid=payload['mission_id'];assert store.claim(mid,mid);started.append(mid)
        await release.wait();store.append(mid,{'type':'mission_complete','result':'controlled computation'});active.pop(mid,None)
    scheduler=asyncio.create_task(schedule_queue(store,active,1,execute,wake,interval=.01))
    try:
        for _ in range(100):
            if started:break
            await asyncio.sleep(.01)
        assert started==[jobs[0]['id']]
        waiting=store.get(jobs[1]['id']);assert waiting['status']=='queued' and waiting['owner'] is None and waiting['started_at'] is None
        assert store.scheduling(waiting['id'])['queue_position']==1
        assert store.scheduling(waiting['id'])['wait_seconds'] is None
        # Explicit cancellation of queued work never runs its callback.
        store.append(jobs[2]['id'],{'type':'mission_complete','stopped':True,'result':'cancelled before execution'})
        release.set()
        for _ in range(100):
            if store.get(jobs[1]['id'])['status']=='completed':break
            await asyncio.sleep(.01)
        assert started==[j['id'] for j in jobs[:2]]
    finally:
        scheduler.cancel();await asyncio.gather(scheduler,*active.values(),return_exceptions=True)


def test_estimate_requires_real_comparable_completed_times(tmp_path):
    store=MissionStore(tmp_path/'queue.sqlite3');payload={'request':'Work','model':'fixture','project_kind':'engineering'}
    current=store.create(payload,queued=True)[0]
    assert store.scheduling(current['id'])['estimated_duration_seconds'] is None
    for duration in [10,20,30]:
        item=store.create(payload)[0];assert store.claim(item['id'],item['id'])
        store.append(item['id'],{'type':'mission_complete','result':'measured'})
        with store.connect(write=True) as db:db.execute('UPDATE missions SET started_at=100,finished=? WHERE id=?',(100+duration,item['id']))
    estimate=store.scheduling(current['id'])
    assert estimate['estimated_duration_seconds']==20 and estimate['estimate_sample_count']==3
    assert store.get(current['id'])['status']=='queued'


def test_fifo_queue_survives_reopening_and_one_slot(tmp_path):
    asyncio.run(_fifo(tmp_path))
