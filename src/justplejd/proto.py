import hashlib
import binascii
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

def encrypt_decrypt(crypto_key: str, mac_addr: str, data: bytearray):
    key = binascii.a2b_hex(crypto_key.replace("-", ""))
    addr = binascii.a2b_hex(mac_addr.replace("-", "").replace(":", ""))[::-1]

    buf = addr + addr + addr[:4]

    ct = Cipher(algorithms.AES(bytearray(key)), modes.ECB(), backend=default_backend())
    ct = ct.encryptor()
    ct = ct.update(buf)

    output = b""
    for i, d in enumerate(data):
        output += struct.pack("B", d ^ ct[i % 16])
    return output

def encode_payloads(crypto_key: str, mac_addr: str, payloads: list[str]):
    return map(lambda payload: encrypt_decrypt(crypto_key, mac_addr, binascii.a2b_hex(payload.replace(" ", ""))),
               payloads)

def create_auth_response(challenge: bytes, crypto_key: str) -> bytes:
    key = binascii.a2b_hex(crypto_key.replace("-", ""))
    k = int.from_bytes(key, "big")
    c = int.from_bytes(challenge, "big")
    intermediate = hashlib.sha256((k ^ c).to_bytes(16, "big")).digest()
    part1 = intermediate[:16]
    part2 = intermediate[16:]
    return bytearray([(a ^ b) for (a, b) in zip(part1, part2)])

def extract_mac_address(manufacturer_data: bytes) -> str:
    if not manufacturer_data or len(manufacturer_data) < 10:
        return None  # Not enough data

    mac_reversed = manufacturer_data[4:10]
    mac = ':'.join(f'{b:02X}' for b in reversed(mac_reversed))
    return mac