import asyncio,json,struct,pytest
from cids.socket_transport import SocketTransport

@pytest.mark.asyncio
async def test_tcp_framed_delivery():
    seen=[]; srv=SocketTransport(); srv.allowed_peers={"client"}
    async def handler(peer,raw): seen.append(json.loads(raw))
    port=await srv.start("server",handler,0)
    cli=SocketTransport(); await cli.send(port,"client",{"hello":"world"}); await asyncio.sleep(.03); await srv.close()
    assert seen==[{"hello":"world"}] and cli.tx_frames==1

@pytest.mark.asyncio
async def test_empty_oversized_and_truncated_frames_are_rejected():
    srv=SocketTransport(max_frame=1024); srv.allowed_peers={"client"}
    async def handler(peer,raw): pass
    port=await srv.start("server",handler,0)
    async def raw_frame(size,payload):
        reader,writer=await asyncio.open_connection("127.0.0.1",port); writer.write(b"client\n"); await writer.drain(); await reader.readline(); writer.write(struct.pack("!I",size)+payload); await writer.drain(); writer.close(); await writer.wait_closed()
    await raw_frame(0,b""); await raw_frame(1025,b""); await raw_frame(5,b"{}")
    await asyncio.sleep(.03); await srv.close()
    assert srv.rejections[("client","empty_frame")]==1
    assert srv.rejections[("client","oversized_frame")]==1
    assert srv.rejections[("client","truncated")]==1
