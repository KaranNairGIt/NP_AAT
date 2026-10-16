import asyncio,json,struct,logging,ssl
log=logging.getLogger(__name__)
class SocketTransport:
    def __init__(self,host="127.0.0.1",max_frame=65536,timeout=2,ssl_context=None,client_ssl_context=None): self.host=host; self.max_frame=max_frame; self.timeout=timeout; self.ssl=ssl_context; self.client_ssl=client_ssl_context or ssl_context; self.server=None; self.port=0; self.handlers={}; self.queues={}; self.tasks=[]; self.allowed_peers=set(); self.send_slots=asyncio.Semaphore(32); self.rejections={}; self.connection_tasks=set(); self.tx_frames=0; self.tx_bytes=0; self.tx_alerts=0; self.rx_frames=0; self.rx_bytes=0; self.failed_sends=0
    async def start(self,node_id,handler,port=0):
        self.handlers[node_id]=handler
        async def accept(reader,writer):
            task=asyncio.current_task(); self.connection_tasks.add(task)
            try:
                peerraw=await asyncio.wait_for(reader.readline(),self.timeout)
                if not peerraw.endswith(b"\n") or len(peerraw)>128: raise ValueError("handshake")
                peer=peerraw.decode("utf-8").strip()
                if peer not in self.allowed_peers or peer==node_id: raise ValueError("handshake")
                writer.write((node_id+"\n").encode()); await writer.drain()
                while True:
                    header=await asyncio.wait_for(reader.readexactly(4),self.timeout); size=struct.unpack("!I",header)[0]
                    self.rx_frames+=1; self.rx_bytes+=4
                    if size==0: raise ValueError("empty_frame")
                    if size>self.max_frame: raise ValueError("oversized_frame")
                    raw=await asyncio.wait_for(reader.readexactly(size),self.timeout); self.rx_bytes+=size; await handler(peer,raw)
            except (asyncio.IncompleteReadError,asyncio.TimeoutError,ValueError,UnicodeDecodeError,json.JSONDecodeError) as e:
                if isinstance(e,asyncio.IncompleteReadError) and not e.partial: return
                if isinstance(e,asyncio.IncompleteReadError): code="truncated"
                elif isinstance(e,asyncio.TimeoutError): code="timeout"
                elif isinstance(e,UnicodeDecodeError): code="non_utf8_handshake"
                elif isinstance(e,ValueError): code=str(e) or "invalid_frame"
                else: code="invalid_frame"
                key=(peer if "peer" in locals() else "unknown",code); self.rejections[key]=self.rejections.get(key,0)+1
                log.warning("connection rejected node=%s peer=%s reason=%s",node_id,key[0],code)
            finally:
                writer.close()
                try: await writer.wait_closed()
                except OSError: pass
                self.connection_tasks.discard(task)
        self.server=await asyncio.start_server(accept,self.host,port,ssl=self.ssl); self.port=self.server.sockets[0].getsockname()[1]; return self.port
    async def send(self,port,sender_id,payload):
        raw=payload if isinstance(payload,bytes) else json.dumps(payload,separators=(",",":")).encode()
        if not raw or len(raw)>self.max_frame: raise ValueError("frame_size")
        async with self.send_slots:
            for attempt in range(3):
                writer=None
                try:
                    reader,writer=await asyncio.wait_for(asyncio.open_connection(self.host,port,ssl=self.client_ssl),self.timeout)
                    writer.write((sender_id+"\n").encode()); await writer.drain(); await asyncio.wait_for(reader.readline(),self.timeout)
                    writer.write(struct.pack("!I",len(raw))+raw); await writer.drain(); writer.close(); await writer.wait_closed(); self.tx_frames+=1; self.tx_bytes+=len(raw)+4
                    if isinstance(payload,dict) and "alert_id" in payload: self.tx_alerts+=1
                    return
                except (OSError,asyncio.TimeoutError):
                    if writer is not None: writer.close()
                    if attempt==2:
                        self.failed_sends+=1
                        raise
                    await asyncio.sleep(.05*(2**attempt))
    async def send_frame(self,port,sender_id,raw,declared_size=None):
        size=len(raw) if declared_size is None else declared_size
        writer=None
        try:
            reader,writer=await asyncio.wait_for(asyncio.open_connection(self.host,port,ssl=self.client_ssl),self.timeout)
            writer.write((sender_id+"\n").encode()); await writer.drain(); await asyncio.wait_for(reader.readline(),self.timeout)
            writer.write(struct.pack("!I",size)+raw); await writer.drain()
            self.tx_frames+=1; self.tx_bytes+=4+len(raw)
        finally:
            if writer is not None:
                writer.close()
                try: await writer.wait_closed()
                except OSError: pass
    async def warmup(self,port,sender_id,expected_peer):
        reader,writer=await asyncio.wait_for(asyncio.open_connection(self.host,port,ssl=self.client_ssl),self.timeout)
        try:
            writer.write((sender_id+"\n").encode()); await writer.drain()
            response=await asyncio.wait_for(reader.readline(),self.timeout)
            if response != (expected_peer+"\n").encode(): raise ConnectionError("peer handshake identity mismatch")
            return True
        finally:
            writer.close()
            try: await writer.wait_closed()
            except OSError: pass
    async def close(self):
        if self.server: self.server.close(); await self.server.wait_closed()
        active=tuple(self.connection_tasks)
        for task in active: task.cancel()
        if active: await asyncio.gather(*active,return_exceptions=True)
        for task in self.tasks: task.cancel()
        if self.tasks: await asyncio.gather(*self.tasks,return_exceptions=True)
