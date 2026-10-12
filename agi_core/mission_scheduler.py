"""FIFO durable admission: a queued mission holds no execution lease or model slot."""
import asyncio


async def schedule_queue(store,missions,capacity,execute,wake,*,interval=1):
    while True:
        pending=await asyncio.to_thread(store.queued)
        available=capacity-sum(not task.done() for task in missions.values())
        for item in pending[:max(0,available)]:
            mid=item['id']
            if mid not in missions or missions[mid].done():
                missions[mid]=asyncio.create_task(execute({'mission_id':mid,**item['payload']}))
        wake.clear()
        try:await asyncio.wait_for(wake.wait(),timeout=interval)
        except asyncio.TimeoutError:pass
