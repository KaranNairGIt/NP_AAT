"""Session-owned run controller; jobs continue while Streamlit reruns or navigates."""
import asyncio
import queue
import threading
from concurrent.futures import ThreadPoolExecutor


class RunController:
    def __init__(self):
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="cids-simulation")
        self.status="Idle"; self.error=None; self.future=None; self.stop_event=None; self.feed_queue=queue.Queue()
        self.feed_history=[]; self.result=None; self.result_kind=None; self.run_number=0

    def start(self,kind,job_factory):
        if self.status=="Running": return False
        self.stop_event=threading.Event(); self.feed_queue=queue.Queue(); self.error=None
        event=self.stop_event; sink=self.feed_queue
        self.status="Running"; self.result_kind=kind; self.run_number+=1
        self.future=self.executor.submit(lambda:asyncio.run(job_factory(event,sink)))
        return True

    def stop(self):
        if self.status=="Running" and self.stop_event is not None: self.stop_event.set(); return True
        return False

    def poll(self):
        while True:
            try: self.feed_history.append(self.feed_queue.get_nowait())
            except queue.Empty: break
        if len(self.feed_history)>1000: self.feed_history=self.feed_history[-1000:]
        if self.status=="Running" and self.future is not None and self.future.done():
            try:
                self.result=self.future.result(); self.status="Finished"
            except Exception as exc:
                self.error=f"{type(exc).__name__}: {exc}"; self.status="Error"
        return self.status

    def close(self):
        self.executor.shutdown(wait=True,cancel_futures=True)
