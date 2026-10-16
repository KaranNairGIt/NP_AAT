from cids.metrics import classification
def test_metrics():
    assert classification([1,0,1],[1,0,0])["fn"]==1
