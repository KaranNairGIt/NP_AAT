# Explained architecture

## Flow

1. A local seeded generator creates synthetic Event dataclasses and incident ground truth. Events are partially visible by source node.
2. Each node applies a sliding-window rate rule. The explanation includes the event count, source, threshold and time window.
3. Alerts are compact canonical JSON, framed with a four-byte big-endian length, signed with per-run random HMAC-SHA256 secrets, and sent over actual asyncio TCP listeners on 127.0.0.1.
4. Receiver order: frame bounds, UTF-8/JSON, exact schema and ranges, protocol version, configured sender/connection identity, HMAC, simulation-time freshness, then replay cache. Rejections are logged and counted.
5. Correlation groups target/type inside a configurable window and keeps one current contribution per sender. Each observer owns its trust ledger. Only authenticated alerts can change it: corroborated observations raise trust, and a recent target observation with no independent matching activity through the correlation window lowers it by a bounded amount. Invalid signatures and replays are attributed to their channel and never affect the claimed identity's trust.
6. A node's own local detection enters consensus with configurable self-trust (default 1.0). Peers share suspicions at 0.5 of the local threshold by default, with confidence proportional to their local score. Local detections decide immediately for that observer. Peer-only decisions need both weighted support at the decision threshold and at least two distinct peer sources by default.
7. Evaluation uses each labeled incident as one unit, including benign decoys, and scores observations from incident start through incident end plus grace. It compares collaborative, local-only-any, per-node-average local, strict all-node majority, and majority among the nodes that observed the target. Per-node-average metrics are computed by scoring each node first and then averaging each metric across nodes; the accompanying standard deviations are across nodes.
8. Experiment output includes incident latency, message counts/bytes, process CPU/RSS, and threshold sweeps. The sweep evaluates decision thresholds 0.3–0.9 and peer source minima 1–3 over five seeds without selecting a winning configuration.

## Time and repeatability

All peer handshakes complete before the simulation clock is reset and the first incident starts. A peer that cannot be handshaken is logged as unavailable. The clock maps wall monotonic time to simulation time at the configured speedup. Event timestamps, freshness, correlation and incident latency use simulation time. I/O remains real. Python's seeded generator gives identical generated event streams per seed; asyncio scheduling can make delivery/measurement vary slightly. The offline-peer scenario records reachable/offline/reachable topology intervals against simulation time.

## Socket and TLS behavior

Listeners use configurable loopback ports; port 0 asks the OS for an available port. Framing rejects empty and oversized frames, catches truncated reads and malformed UTF-8/JSON without taking down a listener. Sends have timeouts, three attempts with exponential backoff and a bounded in-flight semaphore. Shutdown closes listeners and cancels/awaits active handlers. TLS is opt-in; `scripts/gen_lab_cert.py` creates a short-lived self-signed localhost cert. HMAC remains mandatory. The lab client deliberately disables certificate-chain verification because the certificate is self-signed; use only inside the isolated simulation.

## Security scenarios and limits

Fault injection uses synthetic signed false alerts, duplicate/replay transmissions, stale alerts, invalid signatures, malformed frames, and a temporarily closed peer listener. It never crafts real network attack traffic. Peer identity is a simulation handshake string plus HMAC; this is not an operational PKI. Trust is a bounded illustrative score, not a trained reputation model. Authentication proves who sent a report, not that its contents are true; an insider can still generate a false alert, and two-source quorum only limits single-peer influence. Strict majority over all nodes is structurally disadvantaged when events are only visible to a subset of nodes. The source paste ended during its correlation-window requirement, so the 15-second default and other unspecified experiment details are explicit implementation choices.
