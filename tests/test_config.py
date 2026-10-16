import pytest
from cids.config import Settings

def test_node_count_and_loopback_are_enforced():
    assert Settings(node_count=4).validate().host=="127.0.0.1"
    with pytest.raises(ValueError): Settings(node_count=11).validate()
    with pytest.raises(ValueError): Settings(host="0.0.0.0").validate()
