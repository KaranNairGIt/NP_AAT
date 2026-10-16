class ConsensusEngine:
    def __init__(self, threshold=0.5, min_peer_sources=2):
        self.threshold = threshold
        self.min_peer_sources = min_peer_sources

    def decide(self, key, evidence, now, *, observer_id=None, local_detected=False):
        sources = sorted({alert.sender_id for _, alert, _ in evidence})
        peer_evidence = [item for item in evidence if item[1].sender_id != observer_id]
        peer_sources = sorted({alert.sender_id for _, alert, _ in peer_evidence})
        weight = sum(trust * alert.confidence for _, alert, trust in evidence)
        peer_weight = sum(trust * alert.confidence for _, alert, trust in peer_evidence)
        peer_quorum = peer_weight >= self.threshold and len(peer_sources) >= self.min_peer_sources
        decision = bool(local_detected or peer_quorum)
        if local_detected:
            explanation = f"local detector crossed its threshold; self evidence trust 1.0; peer support {peer_weight:.3f}"
        else:
            explanation = (f"peer weighted support {peer_weight:.3f} against threshold {self.threshold:.3f}; "
                           f"{len(peer_sources)} distinct peer source(s), minimum {self.min_peer_sources}")
        support = weight
        peer_support = peer_weight
        return {"timestamp":now,"target_id":key[0],"event_type":key[1],"is_attack":decision,
                "confidence":min(1,weight/max(1,len(sources))),"weighted_support":support,
                "decision_threshold":self.threshold,"min_peer_sources":self.min_peer_sources,
                "peer_weighted_support":peer_support,"sources":sources,"peer_sources":peer_sources,
                "distinct_peer_sources":len(peer_sources),"explanation":explanation}
