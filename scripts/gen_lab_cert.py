"""Generate a short-lived self-signed lab cert using cryptography."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
out=Path(__file__).resolve().parents[1]/"certs"; out.mkdir(exist_ok=True)
key=rsa.generate_private_key(public_exponent=65537,key_size=2048); name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"localhost")])
cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=30)).add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"),x509.IPAddress(__import__('ipaddress').ip_address("127.0.0.1"))]),critical=False).sign(key,hashes.SHA256()))
(out/"localhost.key").write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption())); (out/"localhost.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM)); print(f"Wrote lab certificate to {out}")
