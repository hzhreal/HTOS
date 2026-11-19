import sys
from os.path import dirname as dn
rootdir = dn(dn(dn(dn(dn(__file__)))))
sys.path.append(rootdir)

import hashlib
from data.crypto.algorithms.md5.md5 import MD5

BIG_NUMBER = 10_000

if __name__ == "__main__":
    m = {
        b"The quick brown fox jumps over the lazy dog": bytes.fromhex("9E107D9D372BB6826BD81D3542A419D6"),
        b"The quick brown fox jumps over the lazy dog.": bytes.fromhex("E4D909C290D0FB1CA068FFADDF22CBD0"),
        b"": bytes.fromhex("D41D8CD98F00B204E9800998ECF8427E"),
    }
    for preimage, digest in m.items():
        h = MD5(data=preimage).digest()
        assert h == digest, f"got {h.hex()}, expected {digest.hex()}"

    preimage = b"HTOS IS COOL!" * BIG_NUMBER
    digest = hashlib.md5(preimage).digest()
    md5 = MD5()
    for b in preimage:
        md5.update(bytes([b]))
    h = md5.digest()
    assert h == digest, f"got {h.hex()}, expected {digest.hex()}"

