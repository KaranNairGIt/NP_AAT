from dataclasses import dataclass, field
import secrets

@dataclass
class Settings:
    # Four fixed observers keep the lab small enough to demonstrate and explain.
    # ``node_count`` remains an internal constructor argument for isolated unit tests,
    # but neither the CLI nor dashboard exposes it as a user setting.
    node_count:int=4; base_port:int=0; host:str="127.0.0.1"; seed:int=7; speedup:float=100.0
    rate_threshold:int=6; window_seconds:float=10.0; freshness_seconds:float=60.0
    correlation_window:float=15.0; quorum_weight:float=0.5; min_peer_sources:int=2; self_trust:float=1.0
    reporting_threshold:float=0.5; trust_decrease_step:float=0.1; grace_period_seconds:float=5.0
    duration_seconds:float=120.0; max_frame_bytes:int=65536; socket_timeout_seconds:float=0.1
    tls:bool=False; certfile:str="certs/localhost.crt"; keyfile:str="certs/localhost.key"
    node_secrets:dict=field(default_factory=dict)
    def validate(self):
        if not 2 <= self.node_count <= 10: raise ValueError("node_count must be 2..10")
        if self.host != "127.0.0.1": raise ValueError("host must remain 127.0.0.1 for the isolated lab")
        if not 0 <= self.base_port <= 65535-self.node_count+1: raise ValueError("base_port out of range")
        if self.speedup <= 0 or self.rate_threshold < 1: raise ValueError("speedup and rate_threshold must be positive")
        if self.min_peer_sources < 1 or self.min_peer_sources > self.node_count: raise ValueError("min_peer_sources must be between 1 and node_count")
        if not 0 <= self.self_trust <= 1 or not 0 < self.reporting_threshold <= 1: raise ValueError("self_trust must be 0..1 and reporting_threshold must be 0..1")
        if not 0 < self.trust_decrease_step <= 1 or not 0 < self.quorum_weight <= 1: raise ValueError("trust decrease and decision threshold must be in (0,1]")
        if self.correlation_window <= 0 or self.grace_period_seconds < 0 or self.duration_seconds <= 0: raise ValueError("windows and duration must be positive (grace may be zero)")
        if not 1024 <= self.max_frame_bytes <= 1048576: raise ValueError("max_frame_bytes must be 1 KiB..1 MiB")
        if not 0.05 <= self.socket_timeout_seconds <= 10: raise ValueError("socket timeout must be 0.05..10 seconds")
        if self.tls:
            import os
            if not (os.path.isfile(self.certfile) and os.path.isfile(self.keyfile)):
                raise FileNotFoundError("TLS requested but lab certificate/key missing; run python scripts/gen_lab_cert.py")
        return self
    def secrets(self):
        if not self.node_secrets: self.node_secrets={f"node-{i}":secrets.token_bytes(32) for i in range(self.node_count)}
        return self.node_secrets
