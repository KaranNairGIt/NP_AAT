class ConsensusEngine:
    def __init__(self, threshold=0.5, min_peer_sources=2):
        self.threshold = threshold
        self.min_peer_sources = min_peer_sources

    def decide(self, key, evidence, now, *, observer_id=None, local_detected=False):
        sources = sorted({alert.sender_id for _, alert, _ in evidence})
        peer_evidence = [item for item in evidence if item[1].sender_id != observer_id]
        peer_sources = sorted({alert.sender_id for _, alert, _ in peer_evidence})
        # Deliberately simple rule for the demonstration: a local threshold hit
        # wins, otherwise two different authenticated peers must agree.  Trust
        # weights are not operational inputs to this decision.
        peer_quorum = len(peer_sources) >= self.min_peer_sources
        decision = bool(local_detected or peer_quorum)
        if local_detected:
            explanation = "local detector crossed its threshold"
        else:
            explanation = (f"{len(peer_sources)} distinct authenticated peer report(s); "
                           f"minimum {self.min_peer_sources}")
        support = len(sources)
        peer_support = len(peer_sources)
        return {"timestamp":now,"target_id":key[0],"event_type":key[1],"is_attack":decision,
                "confidence":min(1,support/max(1,self.min_peer_sources)),"weighted_support":support,
                "decision_threshold":self.min_peer_sources,"min_peer_sources":self.min_peer_sources,
                "peer_weighted_support":peer_support,"sources":sources,"peer_sources":peer_sources,
                "distinct_peer_sources":len(peer_sources),"explanation":explanation}
