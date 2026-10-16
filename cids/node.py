"""One simulated IDS observer, its bounded event worker, and localhost listener."""
import asyncio, json, logging, time
from collections import defaultdict
from dataclasses import asdict, replace
from .socket_transport import SocketTransport
from .message_security import Validator, sign
from .models import Alert
from .alert_correlator import AlertCorrelator
from .trust_manager import TrustManager
from .consensus_engine import ConsensusEngine
from .local_detector import LocalDetector
log=logging.getLogger(__name__)

class IDSNode:
    def __init__(self,node_id,peers,keys,settings,clock,feed_sink=None):
        self.event_queue=asyncio.Queue(maxsize=256); self.runner=None; self.id=node_id; self.peers=peers; self.keys=keys; self.settings=settings; self.clock=clock; self.feed_sink=feed_sink; self.unavailable_until={}
        self.detector=LocalDetector(settings.rate_threshold,settings.window_seconds); server_ssl=client_ssl=None
        if settings.tls:
            import ssl
            server_ssl=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); server_ssl.load_cert_chain(settings.certfile,settings.keyfile)
            client_ssl=ssl.create_default_context(); client_ssl.check_hostname=False; client_ssl.verify_mode=ssl.CERT_NONE
        self.transport=SocketTransport(settings.host,settings.max_frame_bytes,timeout=settings.socket_timeout_seconds,ssl_context=server_ssl,client_ssl_context=client_ssl); self.transport.allowed_peers=set(peers)
        self.validator=Validator(peers,keys,settings.freshness_seconds); self.correlator=AlertCorrelator(settings.correlation_window); self.trust=TrustManager(peers); self.consensus=ConsensusEngine(settings.quorum_weight,settings.min_peer_sources)
        self.incoming=[]; self.local=[]; self.local_decisions=[]; self.decisions=[]; self.local_events=defaultdict(list); self.feed=[]; self._time=time; self.trust_audits=set()
    def emit(self,record):
        self.feed.append(record)
        if self.feed_sink is not None:
            try: self.feed_sink.put_nowait(record)
            except Exception: pass
    def _locally_detected(self,target_id,event_type,now):
        return any(d["target_id"]==target_id and d["event_type"]==event_type and 0<=now-d["timestamp"]<=self.settings.correlation_window for d in self.local_decisions)
    async def _audit_authenticated_alert(self,peer,alert,receipt_time,watched_count):
        await self.clock.sleep(self.settings.correlation_window)
        end=self.clock.now()
        observed=[event for event in self.local_events.get((alert.target_id,alert.event_type),[]) if receipt_time<=event.timestamp<=end]
        if not observed:
            self.trust.update(peer,delta=-self.settings.trust_decrease_step,
                reason="authenticated_alert_uncorroborated_while_target_observed",
                simulation_time=end,evidence=f"observer had {watched_count} recent observation(s) on {alert.target_id}; no independent {alert.event_type} observation during the {self.settings.correlation_window:g}s correlation window")
        self.trust_audits.discard(asyncio.current_task())
    async def drain_trust_audits(self):
        if self.trust_audits: await asyncio.gather(*tuple(self.trust_audits),return_exceptions=True)
    async def handle(self,channel_peer,raw):
        try:
            decoded=json.loads(raw.decode("utf-8")); now=self.clock.now(); alert=self.validator.validate(decoded,channel_peer,now)
        except (ValueError,UnicodeDecodeError,json.JSONDecodeError) as exc:
            reason="non_utf8" if isinstance(exc,UnicodeDecodeError) else "invalid_json" if isinstance(exc,json.JSONDecodeError) else str(exc)
            key=(channel_peer,reason); self.transport.rejections[key]=self.transport.rejections.get(key,0)+1
            log.warning("alert rejected channel_peer=%s reason=%s",channel_peer,reason)
            # Failed signature, replay, and other rejected claims do not prove the claimed identity.
            return
        self.incoming.append(alert)
        local=self.local_events.get((alert.target_id,alert.event_type),[])
        corroborating=[event for event in local if max(0,now-self.settings.correlation_window)<=event.timestamp<=now]
        if corroborating:
            self.trust.update(channel_peer,delta=0.05,reason="authenticated_alert_corroborated_by_local_events",simulation_time=now,evidence=f"{len(corroborating)} matching own observation(s) for {alert.target_id}/{alert.event_type}")
        else:
            recent_target=[event for events in self.local_events.values() for event in events if event.target_id==alert.target_id and max(0,now-self.settings.correlation_window)<=event.timestamp<=now]
            if recent_target:
                task=asyncio.create_task(self._audit_authenticated_alert(channel_peer,alert,now,len(recent_target)))
                self.trust_audits.add(task)
        key=self.correlator.add(alert,self.trust.get(channel_peer),now); decision=self.consensus.decide(key,self.correlator.evidence(key),now,observer_id=self.id,local_detected=self._locally_detected(alert.target_id,alert.event_type,now)); self.decisions.append(decision)
        self.emit({"simulation_time":now,"kind":"alert_received","node_id":self.id,"peer_id":channel_peer,"target_id":alert.target_id,"event_type":alert.event_type,"alert_id":alert.alert_id,"decision":decision["is_attack"]})
    async def start(self,port=0): return await self.transport.start(self.id,self.handle,port)
    async def run(self):
        while True:
            event=await self.event_queue.get()
            try:
                if event is None: return
                self.local_events[(event.target_id,event.event_type)].append(event)
                result=self.detector.observe(event)
                if result["decision"]: self.local_decisions.append({"timestamp":event.timestamp,"target_id":event.target_id,"event_type":event.event_type,"is_attack":True,"explanation":result["explanation"]})
                await self.publish(event,result)
            except Exception as exc: log.exception("node event processing failed node=%s: %s",self.id,exc)
            finally: self.event_queue.task_done()
    async def submit(self,event): await self.event_queue.put(event)
    async def stop(self):
        if self.runner and not self.runner.done():
            await self.event_queue.put(None); await self.runner
    async def publish(self,event,result=None):
        result=result or self.detector.observe(event)
        is_suspicion=result["score"]>=self.settings.reporting_threshold and event.event_type in ("login_fail","port_probe")
        if result["decision"] or is_suspicion:
            label="local threshold alert" if result["decision"] else "sub-threshold suspicion"
            confidence=1.0 if result["decision"] else result["score"]
            alert=Alert(1,event.event_id+"-"+self.id,event.event_id,self.id,self.clock.now(),event.event_type,event.target_id,4 if result["decision"] else 2,confidence,f"{label}: {result['explanation']}"[:160]); sign(alert,self.keys[self.id]); self.local.append(alert)
            self.emit({"simulation_time":alert.timestamp,"kind":"alert_sent","node_id":self.id,"peer_id":None,"target_id":alert.target_id,"event_type":alert.event_type,"alert_id":alert.alert_id,"decision":result["decision"]})
            local_detected=self._locally_detected(alert.target_id,alert.event_type,event.timestamp)
            local_evidence=replace(alert,timestamp=event.timestamp) if local_detected else alert
            decision_time=event.timestamp if local_detected else alert.timestamp
            key=self.correlator.add(local_evidence,self.settings.self_trust,decision_time)
            decision=self.consensus.decide(key,self.correlator.evidence(key),decision_time,observer_id=self.id,local_detected=local_detected); self.decisions.append(decision)
            payload=asdict(alert)
            async def deliver(peer,port):
                if peer==self.id: return
                if self._time.monotonic()<self.unavailable_until.get(peer,0):
                    self.transport.failed_sends+=1; return
                try: await self.transport.send(port,self.id,payload)
                except (OSError,TimeoutError,ValueError): self.unavailable_until[peer]=self._time.monotonic()+1.0; self.transport.failed_sends+=1
            await asyncio.gather(*(deliver(peer,port) for peer,port in self.peers.items()))
        return result
    async def close(self): await self.transport.close()
