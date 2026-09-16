"""
Self-test for the No Man's Sky save crypto helpers in data/crypto/nms_crypt.py.

Runs without a Discord token, network access or PS4, using only project
dependencies.  Run from the repository root:

    uv run python tools/nms_crypt_selftest.py [savedataNN.hg]

Passing a save file adds a report for that file (is the payload valid UTF-8
JSON, and does the key mapping change or preserve the bytes).

Exits with code 1 when any check fails.
"""

import asyncio
import os
import sys
import tempfile

import orjson
from dotenv import load_dotenv

load_dotenv()

# utils/constants.py reads its configuration from the environment when it is
# imported.  The crypto helpers do not use these values, so fill in placeholders
# when the caller has no .env file.
for name, value in (
    ("IP", "127.0.0.1"),
    ("FTP_PORT", "21"),
    ("CECIE_PORT", "755"),
    ("MOUNT_PATH", "/mnt/ps4"),
    ("UPLOAD_PATH", "."),
    ("STORED_SAVES_FOLDER_PATH", "STORED_SAVES"),
):
    if not os.environ.get(name):
        os.environ[name] = value

rootdir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(rootdir)
from data.crypto.exceptions import CryptoError
from data.crypto.nms_crypt import Crypt_NMS

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        suffix = f": {detail}" if detail else ""
        print(f"FAIL  {name}{suffix}")


def build_deep_payload() -> dict:
    # Mirrors the depth-11 Cosmos path:
    # BaseContext.PlayerStateData.SquadronPilots[].ShipResource.ProceduralTexture.
    # Samplers[].Options[].Palette
    deepest = {"RVl": {"Value": 1}}
    payload = {"?=t": [deepest]}
    payload = {"bnT": [payload]}
    payload = {"<d2": payload}
    payload = {":dY": payload}
    payload = {"S5O": [payload]}
    payload = {"6f=": payload}
    payload = {"vLc": payload}
    return {"F2P": 4735, "8>q": "PS4|Final", **payload}


async def lz4_round_trip(payload: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "savedata99.hg")
        with open(path, "wb") as f:
            f.write(payload)

        async with Crypt_NMS.NMS(path) as cc:
            await cc.compress()

        with open(path, "rb") as f:
            compressed = f.read()
        check("compress writes LZ4 blocks", Crypt_NMS.LZ4_MAGIC in compressed)

        async with Crypt_NMS.NMS(path) as cc:
            await cc.decompress()

        with open(path, "rb") as f:
            return f.read()


def check_real_file(path: str) -> None:
    with open(path, "rb") as f:
        data = f.read()
    payload = data.rstrip(b"\x00")
    parsed = Crypt_NMS.try_load_json(payload)
    name = os.path.basename(path)

    if parsed is None:
        check(f"{name} is obfuscated non-UTF-8 JSON", Crypt_NMS.is_obfuscated(payload))
        result = Crypt_NMS.deobfuscate(data)
        check(f"{name} payload kept byte-for-byte", result == payload)
    else:
        result = Crypt_NMS.deobfuscate(data)
        check(f"{name} keys mapped", result != payload)


def run_checks() -> None:
    obfuscated = b'{"F2P":4735,"8>q":"PS4|Final","XTp":"Main","b2n":"dummy"}'
    account = b'{"F2P":4098,"8>q":"PS4|Final","B89":{"32m":false}}'
    human = b'{"Version":4735,"Platform":"PS4|Final"}'
    invalid_obfuscated = b'{"F2P":4735,"8>q":"PS4|Final","b2n":"^\x80\x80"}'
    invalid_human = b'{"Version":4735,"b2n":"^\x80\x80"}'

    check("is_obfuscated(save)", Crypt_NMS.is_obfuscated(obfuscated))
    check("is_obfuscated(account)", Crypt_NMS.is_obfuscated(account))
    check("is_obfuscated(human) is False", not Crypt_NMS.is_obfuscated(human))

    check("try_load_json(valid)", Crypt_NMS.try_load_json(obfuscated) is not None)
    check("try_load_json(invalid) is None", Crypt_NMS.try_load_json(invalid_obfuscated) is None)

    check(
        "deobfuscate keeps obfuscated non-UTF-8 payload",
        Crypt_NMS.deobfuscate(invalid_obfuscated + b"\x00") == invalid_obfuscated,
    )
    check(
        "obfuscate keeps obfuscated non-UTF-8 payload",
        Crypt_NMS.obfuscate(invalid_obfuscated + b"\x00") == invalid_obfuscated,
    )

    for func, label in ((Crypt_NMS.deobfuscate, "deobfuscate"), (Crypt_NMS.obfuscate, "obfuscate")):
        try:
            func(invalid_human)
            check(f"{label} rejects human-readable non-UTF-8 payload", False, "no error raised")
        except CryptoError:
            check(f"{label} rejects human-readable non-UTF-8 payload", True)

    mapped = Crypt_NMS.deobfuscate(obfuscated)
    check("deobfuscate maps keys", b'"Version":4735' in mapped)

    reverse_mapped = Crypt_NMS.obfuscate(mapped)
    check(
        "obfuscate reverses the mapping",
        orjson.loads(reverse_mapped) == orjson.loads(obfuscated),
    )

    deep = orjson.dumps(build_deep_payload())
    try:
        Crypt_NMS.deobfuscate(deep)
        check("deobfuscate maps depth-11 payload", True)
    except CryptoError as exc:
        check("deobfuscate maps depth-11 payload", False, exc.message)

    payload = b'{"F2P":4735,"vLc":{"6f=":{"S5O":[{"val":"' + b"x" * 4096 + b'"}]}}}'
    try:
        result = asyncio.run(lz4_round_trip(payload))
        check("LZ4 round trip is byte-identical", result == payload)
    except Exception as exc:
        check("LZ4 round trip is byte-identical", False, repr(exc))


def main() -> None:
    run_checks()
    if len(sys.argv) - 1 >= 1:
        check_real_file(sys.argv[1])
    print()
    print(f"{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
