import aiofiles
import mmh3
from os.path import basename
from data.crypto.common import CryptoError
from utils.type_helpers import uint32

class Crypt_RE7:
    SEED = 0xFF_FF_FF_FF

    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "r+b") as savegame:
            await savegame.seek(0, 2)
            size = await savegame.tell()
            size -= 4
            if size <= 0:
                raise CryptoError(f"File is to small ({basename(fileToEncrypt)})!")

            await savegame.seek(0)
            buf = await savegame.read(size)
            csum = uint32(mmh3.hash(buf, Crypt_RE7.SEED, False), "little")

            await savegame.seek(size)
            await savegame.write(csum.as_bytes)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        await Crypt_RE7.encryptFile(fileName)
