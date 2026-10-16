from cids.event_generator import generate
from cids.local_detector import LocalDetector

def test_generation_is_seeded_and_visibility_is_partial():
    a=generate(5); b=generate(5)
    assert [(e.event_id,e.timestamp,e.source_id) for e in a]==[(e.event_id,e.timestamp,e.source_id) for e in b]
    assert len({e.source_id for e in a if e.incident_id=="inc-lowrate"})>1

def test_rate_rule_explains_threshold():
    from cids.models import Event
    d=LocalDetector(threshold=2,window=3)
    e=Event("a",1,"node-0","target","login",{})
    assert not d.observe(e)["decision"]
    e2=Event("b",2,"node-0","target","login",{})
    result=d.observe(e2)
    assert result["decision"] and "threshold 2" in result["explanation"]
