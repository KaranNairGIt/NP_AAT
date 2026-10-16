from cids.models import Alert
from cids.message_security import sign,Validator

def test_hmac_validation_and_replay():
    keys={"a":b"a"*32,"b":b"b"*32}; alert=Alert(1,"id","ev","a",10,"login","host",3,.8,"rate rule"); sign(alert,keys["a"]); validator=Validator(["a","b"],keys)
    data=alert.unsigned()|{"signature":alert.signature}; assert validator.validate(data.copy(),"a",10).alert_id=="id"
    try: validator.validate(data.copy(),"a",10); assert False
    except ValueError as exc: assert str(exc)=="replay"
    assert validator.peer_rejections[("a","replay")] == 1

def test_freshness_precedes_replay_cache_only_after_hmac():
    keys={"a":b"a"*32}; alert=Alert(1,"old","ev","a",1,"login","host",3,.8,"evidence"); sign(alert,keys["a"]); validator=Validator(["a"],keys,freshness=5)
    try: validator.validate(alert.unsigned()|{"signature":alert.signature},"a",99); assert False
    except ValueError as exc: assert str(exc)=="freshness"
