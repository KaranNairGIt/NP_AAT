import time
class SimulationClock:
    def __init__(self,speedup=100.0): self.speedup=speedup; self._start=time.monotonic()
    def reset(self): self._start=time.monotonic()
    def now(self): return (time.monotonic()-self._start)*self.speedup
    async def sleep(self,seconds):
        import asyncio; await asyncio.sleep(max(0,seconds/self.speedup))
