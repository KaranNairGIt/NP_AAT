"""Per-observer trust state with bounded score and timestamped reasons."""
from .models import TrustState

class TrustManager:
    def __init__(self,peers): self.states={peer:TrustState() for peer in peers}
    def get(self,peer): return self.states[peer].score
    def update(self,peer,*,delta,reason,simulation_time,evidence=None):
        state=self.states[peer]; before=state.score
        state.score=max(0.0,min(1.0,before+delta))
        state.history.append({"simulation_time":float(simulation_time),"from":before,"to":state.score,"delta":state.score-before,"reason":reason,"evidence":evidence or ""})
        state.history[:]=state.history[-1000:]
        return state.score
