import asyncio
import time

from ui.controller import RunController


def test_page_rerun_polls_do_not_restart_or_drop_a_running_job():
    controller=RunController(); calls=[]
    async def job(stop_event,feed_sink):
        calls.append("started")
        await asyncio.sleep(.03)
        feed_sink.put_nowait({"kind":"alert_sent"})
        return {"seed":7}
    try:
        assert controller.start("single",job)
        run_id=controller.run_number
        for _ in range(4):
            controller.poll()
            assert controller.run_number==run_id
            time.sleep(.005)
        deadline=time.monotonic()+1
        while controller.poll()=="Running" and time.monotonic()<deadline: time.sleep(.005)
        assert controller.status=="Finished"
        assert calls==["started"] and controller.result=={"seed":7}
        assert controller.feed_history==[{"kind":"alert_sent"}]
    finally:
        controller.close()
