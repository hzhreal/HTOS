import struct
from os.path import basename
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError

class Crypt_JForce:
    SLOTS = {"JFSaveData": 0x0007CB61, "JFReplay": 0x443B294F}

    class JForce(CC):
        FOOTER_LEN = 16
        STRIDE_DIVISOR = 17
        FOLD_ADD = 0xE55D9141
        MASK_X = 0x075BCD15
        MASK_Y = 0x05491333
        MASK_Z = 0x1F123BB5
        MASK_W = 0x159A55E5

        def __init__(self, filepath: str, in_place: bool = True) -> None:
            super().__init__(filepath, in_place)
            self.seed = Crypt_JForce.SLOTS[basename(filepath)]
            self.tag = bytearray(self.FOOTER_LEN)

        async def _encrypt(self) -> None:
            assert self.in_place

            md5 = self.create_ctx_md5()
            await self.checksum(md5, 0, self.size - self.FOOTER_LEN)
            md5_digest_obj = self._get_ctx(md5).obj
            self.tag[:] = md5_digest_obj.digest()
            await self._body_keystream_xor()
            await self._tag_keystream_xor()
            await self.ext_write(self.size - self.FOOTER_LEN, self.tag)

        async def _decrypt(self) -> None:
            assert self.in_place

            self.tag[:] = await self.ext_read(self.size - self.FOOTER_LEN, self.FOOTER_LEN)
            await self._tag_keystream_xor()
            await self.ext_write(self.size - self.FOOTER_LEN, self.tag)
            await self._body_keystream_xor()

        async def _body_keystream_xor(self) -> None:
            w0, w1, w2, w3 = struct.unpack("<4I", self.tag)
            a = ((self.seed ^ w0 ^ w1 ^ w2 ^ w3) + self.FOLD_ADD) & 0xFF_FF_FF_FF
            a_x = a ^ self.MASK_X

            b = self._rol(a, 24) ^ self.MASK_Z
            c = self._rol(a,  8) ^ self.MASK_W
            a = self._rol(a, 16) ^ self.MASK_Y
            while await self.read(stop_off=self.size - self.FOOTER_LEN):
                for i in range(len(self.chunk)):
                    d = b
                    a_x = ((a_x << 11) & 0xFF_FF_FF_FF) ^ a_x
                    e = (a_x >> 8) ^ (a >> 19) ^ a ^ a_x
                    self.chunk[i] ^= e & 0xFF
                    a_x = c
                    b = a
                    c = d
                    a = e
                await self.write()

        async def _tag_keystream_xor(self) -> None:
            a = (self.seed + self.FOLD_ADD) & 0xFF_FF_FF_FF
            b = self._rol(a, 16) ^ self.MASK_Y
            a_x = a ^ self.MASK_X
            c = ((a_x << 11) & 0xFF_FF_FF_FF) ^ a_x
            d = (c >> 8) ^ ((b >> 19)) ^ b ^ c
            self.tag[0] ^= d & 0xFF

            e = self._rol(a,  8) ^ self.MASK_W
            c = self._rol(a, 24) ^ self.MASK_Z
            for i in range(1, self.FOOTER_LEN):
                a = b
                b = d
                e = ((e << 11) & 0xFF_FF_FF_FF) ^ e
                d = (e >> 8) ^ (b >> 19) ^ b ^ e
                self.tag[i] ^= d & 0xFF
                e = c
                c = a

        async def _interleave(self) -> None:
            assert not self.in_place

            self.tag[:] = await self.ext_read(self.size - self.FOOTER_LEN, self.FOOTER_LEN)

            body_len = self.size - self.FOOTER_LEN # no check needed because encrypt passed
            stride = body_len // self.STRIDE_DIVISOR
            keep = body_len - self.FOOTER_LEN * stride

            await self.copy(0, keep)
            out = keep
            cur = keep

            for i in range(self.FOOTER_LEN - 1, -1, -1):
                # we are writing self.size in total, footer already there will be ignored
                await self.w_stream.write(bytes([self.tag[i]]))
                await self.copy(cur, cur + stride)
                out += 1 + stride
                cur += stride
            if out < body_len:
                await self.copy(cur, body_len)

        async def _deinterleave(self) -> None:
            assert not self.in_place

            body_len = self.size - self.FOOTER_LEN
            if body_len < 0:
                raise CryptoError("Invalid save!")
            stride = body_len // self.STRIDE_DIVISOR
            keep = body_len - self.FOOTER_LEN * stride

            await self.copy(0, keep)
            out = keep
            cur = keep

            for i in range(self.FOOTER_LEN - 1, -1, -1):
                self.tag[i] = (await self.ext_read(cur, 1))[0]
                await self.copy(cur + 1, cur + 1 + stride)
                out += stride
                cur += 1 + stride
            if out < body_len:
                await self.copy(out, body_len)
            # body_len has been written to w_stream
            # we can be sure that body_len + FOOTER_LEN <= SAVESIZE_MAX
            await self.w_stream.write(self.tag)

        @staticmethod
        def _rol(u32: int, count: int) -> int:
            """Cyclic left bit shift."""
            return ((u32 << count) | (u32 >> (32 - count))) & 0xFF_FF_FF_FF

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        if not Crypt_JForce.file_check(filepath):
            return

        async with Crypt_JForce.JForce(filepath, in_place=False) as cc:
            await cc._deinterleave()
        async with Crypt_JForce.JForce(filepath) as cc:
            await cc._decrypt()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if not Crypt_JForce.file_check(filepath):
            return

        async with Crypt_JForce.JForce(filepath) as cc:
            await cc._encrypt()
        async with Crypt_JForce.JForce(filepath, in_place=False) as cc:
            await cc._interleave()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_JForce.files_check(files)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if not is_dec:
                await Crypt_JForce.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_JForce.files_check(files)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if is_dec:
                await Crypt_JForce.encrypt_file(filepath)

    @staticmethod
    def file_check(filepath: str) -> bool:
        filename = basename(filepath)
        return filename in Crypt_JForce.SLOTS

    @staticmethod
    def files_check(files: list[str]) -> list[str]:
        valid = []
        for path in files:
            filename = basename(path)
            if filename in Crypt_JForce.SLOTS:
                valid.append(path)
        return valid

