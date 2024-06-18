import struct
import aiofiles
import zstandard as zstd
from data.crypto.common import CustomCrypto as CC

class Crypt_DI2:
    ZSTD_MAGIC = 0xFD2FB528
    
    # this is a header from a save that will get applied when compressing
    # the header contains metadata such as game version
    # instead of figuring out how to generate one, here is a lazy approach
    # so here is one already from a save
    HEADER_FROM_SAVE = b"\xBF\xF5\x0F\x00\x0A\x00\x03\x00\x01\xD9\x0E\x51\x05\x00\x00\x00\x5A\x73\x74\x64\x00\x6E\x20\x00\x00\x00\x00\x01\x00"

    # a compressed save has multiple chunks of zstd compressed data, we decompress from one magic header to the start of the next
    @staticmethod
    def decompress(data: bytes | bytearray) -> bytearray:
        magic = struct.pack("<I", Crypt_DI2.ZSTD_MAGIC)
        decomp = bytearray()

        pointer = 0
        while True:
            off = data.find(magic, pointer)
            if off == -1:
                break
            pointer = off + len(magic)

            next_off = data.find(magic, pointer)
            if next_off != -1:
                chunk = data[off:next_off]
            else:
                chunk = data[off:]
            
            de_chunk = zstd.decompress(chunk)
            decomp.extend(de_chunk)
        return decomp
    
    # to compress a save we take 64KB (or whats left if not 64KB) of the decompressed data and use zstd
    @staticmethod
    def compress(data: bytes | bytearray) -> bytearray:
        comp = bytearray()
        chunk_size = 64 * 1024

        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            co_chunk = zstd.compress(chunk)
            comp.extend(co_chunk)
        return comp

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = await CC.obtainFiles(folderPath)

        for filePath in files:

            async with aiofiles.open(filePath, "rb") as savegame:
                compressed_data = await savegame.read()

            decompressed_data = Crypt_DI2.decompress(compressed_data)

            async with aiofiles.open(filePath, "wb") as savegame:
                await savegame.write(decompressed_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            decompressed_data = await savegame.read()
        
        compressed_data = Crypt_DI2.compress(decompressed_data)
        compressed_data = Crypt_DI2.HEADER_FROM_SAVE + compressed_data

        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(compressed_data)
    
    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            data = await savegame.read()
        
        start_off = data.find(struct.pack("<I", Crypt_DI2.ZSTD_MAGIC))
        if start_off == -1:
            await Crypt_DI2.encryptFile(fileName)