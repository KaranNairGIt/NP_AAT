from pathlib import Path
import asyncio,pytest,ssl
from cids.config import Settings
from cids.socket_transport import SocketTransport

ROOT=Path(__file__).resolve().parents[1]
CERT=ROOT/"certs"/"localhost.crt"
KEY=ROOT/"certs"/"localhost.key"
pytestmark=pytest.mark.skipif(not (CERT.exists() and KEY.exists()),reason="optional lab TLS certificate has not been generated")

def test_tls_configuration_accepts_generated_lab_certificate():
    Settings(tls=True,certfile=str(CERT),keyfile=str(KEY)).validate()

@pytest.mark.asyncio
async def test_tls_localhost_transport():
    seen=[]; server_ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); server_ctx.load_cert_chain(CERT,KEY)
    client_ctx=ssl.create_default_context(); client_ctx.check_hostname=False; client_ctx.verify_mode=ssl.CERT_NONE
    server=SocketTransport(ssl_context=server_ctx,client_ssl_context=client_ctx); server.allowed_peers={"client"}
    async def handler(peer,raw): seen.append((peer,raw))
    port=await server.start("server",handler,0)
    client=SocketTransport(ssl_context=server_ctx,client_ssl_context=client_ctx)
    await client.send(port,"client",b"tls-lab-message"); await asyncio.sleep(.03); await server.close()
    assert seen==[("client",b"tls-lab-message")]
