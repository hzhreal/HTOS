from dataclasses import dataclass
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from utils.constants import LOH_TRAILS_CS4_TITLEID, LOH_TRAILS_DAYBREAK_TITLEID, LOH_TRAILS_ZERO_AZURE
from utils.type_helpers import uint32

class Crypt_LoHTrails:
    class Decompression_LoHTrails:
        def __init__(self, cc: CC) -> None:
            self.cc = cc
            assert not self.cc.in_place

            self.clear()

        def clear(self) -> None:
            self.source_position = 12
            self.target_position = 0
            self.target_buf = bytearray()
            self.target_buf_start = 0
            self.target_buf_end = 0
            self.target_size = 0
            self.buf = bytearray()

        async def fill_source(self) -> None:
            if self.source_position >= self.cc.chunk_end or self.source_position == 12:
                await self.cc.read()

        async def read_source(self) -> int:
            if self.source_position >= self.cc.size:
                raise CryptoError("Invalid save!")
            await self.fill_source()

            r_pos = self.source_position - self.cc.chunk_start
            self.source_position += 1
            return self.cc.chunk[r_pos]

        async def write_alloc_target(self) -> None:
            await self.cc.w_stream.seek(self.target_buf_start)
            await self.cc.w_stream.write(self.target_buf)

        async def alloc_target(self) -> None:
            if self.target_buf:
                await self.write_alloc_target()
            self.target_buf_start = await self.cc.w_stream.tell()
            alloc_len = min(self.cc.CHUNKSIZE, self.target_size - self.target_buf_end)
            self.target_buf = bytearray(alloc_len)
            self.target_buf_end = self.target_buf_start + alloc_len

        async def write_target(self, b: int) -> None:
            if self.target_position > self.target_size:
                raise CryptoError("Unsupported save!")
            if self.target_position >= self.target_buf_end or not self.target_buf:
                await self.alloc_target()

            w_pos = self.target_position - self.target_buf_start
            self.target_buf[w_pos] = b
            self.target_position += 1

            self.buf.append(b)
            if len(self.buf) > 0xFF:
                self.buf.pop(0)

        async def copy_target(self, src_off: int, n: int) -> None:
            if self.target_position < src_off:
                raise CryptoError("Invalid save!")
            if self.target_position + n > self.target_size:
                raise CryptoError("Unsupported save!")
            if self.target_position >= self.target_buf_end:
                await self.alloc_target()

            for _ in range(n):
                src_pos = self.target_position - src_off

                if src_pos >= self.target_buf_start:
                    r_pos = src_pos - self.target_buf_start
                    b = self.target_buf[r_pos]
                else:
                    r_pos = len(self.buf) - src_off
                    b = self.buf[r_pos]

                await self.write_target(b)

        async def decompress(self) -> None:
            await self.cc.r_stream.seek(0)
            self.target_size = uint32(await self.cc.r_stream.read(4), "little").value
            source_size      = uint32(await self.cc.r_stream.read(4), "little").value
            backref_byte     = uint32(await self.cc.r_stream.read(4), "little").value
            self.cc.set_ptr(self.source_position)

            if self.target_size > self.cc.SAVESIZE_MAX:
                raise CryptoError("Unsupported save!")
            if source_size - 12 > self.cc.size:
                raise CryptoError("Invalid save!")

            while self.source_position < source_size:
                source_byte = await self.read_source()

                if source_byte == backref_byte:
                    backref_offset = await self.read_source()
                    if backref_offset == backref_byte:
                        await self.write_target(backref_byte)
                    else:
                        if backref_byte < backref_offset:
                            backref_offset -= 1
                        if backref_offset == 0:
                            raise CryptoError("Invalid save!")

                        backref_length = await self.read_source()
                        if backref_length > 0:
                            await self.copy_target(backref_offset, backref_length)
                else:
                    await self.write_target(source_byte)

            if self.target_size != self.target_position:
                raise CryptoError("Invalid save!")
            await self.write_alloc_target()

            self.clear()

    class Compression_LoHTrails:
        @dataclass
        class Backref:
            position: int
            length: int
        MAX_BACKREF_LENGTH = 32
        MAX_BACKREF_OFFSET = 32

        def __init__(self, cc: CC) -> None:
            self.cc = cc
            assert not self.cc.in_place

            self.clear()

        def clear(self) -> None:
            self.count_per_byte = [0] * 256
            self.backref_byte = 0
            self.max_bound = -1

            self.source_position = 0
            self.target_position = 0
            self.target_buf = bytearray()
            self.target_buf_start = 0
            self.target_buf_end = -1
            self.buf = bytearray(self.MAX_BACKREF_OFFSET + self.MAX_BACKREF_LENGTH)

        async def fill_source(self) -> None:
            if self.source_position >= self.cc.chunk_end or self.source_position == 0:
                await self.cc.read()

        async def read_source(self) -> int:
            if self.source_position >= self.cc.size:
                raise CryptoError("Invalid save!")
            await self.fill_source()

            r_pos = self.source_position - self.cc.chunk_start
            self.source_position += 1
            return self.cc.chunk[r_pos]

        async def write_alloc_target(self) -> None:
            size = await self.cc.w_stream.seek(self.target_buf_start)
            if size + len(self.target_buf) > self.target_position:
                del self.target_buf[self.target_position - self.target_buf_start:]
                self.target_buf_end = self.target_buf_start + len(self.target_buf)
            await self.cc.w_stream.write(self.target_buf)

        async def alloc_target(self) -> None:
            if self.target_buf:
                await self.write_alloc_target()
            self.target_buf_start = await self.cc.w_stream.tell()
            alloc_len = self.cc.CHUNKSIZE
            self.target_buf = bytearray(alloc_len)
            self.target_buf_end = self.target_buf_start + alloc_len

        async def write_target(self, b: int) -> None:
            if self.target_position > self.cc.SAVESIZE_MAX:
                raise CryptoError("Unsupported save!")
            if self.target_position >= self.target_buf_end or not self.target_buf:
                await self.alloc_target()

            w_pos = self.target_position - self.target_buf_start
            self.target_buf[w_pos] = b
            self.target_position += 1

        async def compress(self) -> None:
            await self.calculate_byte_counts()
            self.cc.set_ptr(0)
            self.cc.chunk = None
            self.get_least_used_byte()

            # prepare header
            for _ in range(12):
                await self.write_target(0)

            while self.source_position < self.cc.size:
                best_backref = await self.find_best_backref()

                if best_backref.length <= 1:
                    byte = await self.read_source()
                    if byte == self.backref_byte:
                        await self.write_target(byte)
                        await self.write_target(byte)
                    else:
                        await self.write_target(byte)
                    continue

                if best_backref.length >= 4:
                    await self.write_target(self.backref_byte)
                    offset = self.source_position - best_backref.position
                    if self.backref_byte <= offset:
                        offset += 1
                    await self.write_target(offset & 0xFF)
                    await self.write_target(best_backref.length & 0xFF)
                    # increment source_position
                    for _ in range(best_backref.length):
                        await self.read_source()
                    continue

                # Backref of 2 or 3 bytes - write as literal (as per original implementation)
                byte = await self.read_source()
                if byte == self.backref_byte:
                    await self.write_target(byte)
                    await self.write_target(byte)
                else:
                    await self.write_target(byte)
            await self.write_alloc_target()

            # write header
            uncompressed_length = uint32(self.cc.size,         "little").as_bytes
            compressed_length   = uint32(self.target_position, "little").as_bytes
            backref_byte        = uint32(self.backref_byte,    "little").as_bytes
            await self.cc.w_stream.seek(0)
            await self.cc.w_stream.write(uncompressed_length + compressed_length + backref_byte)

            self.clear()

        async def calculate_byte_counts(self) -> None:
            self.cc.set_ptr(0)
            while await self.cc.read():
                for b in self.cc.chunk:
                    self.count_per_byte[b] += 1

        def get_least_used_byte(self) -> None:
            for i in range(1, 256):
                if self.count_per_byte[i] < self.count_per_byte[self.backref_byte]:
                    self.backref_byte = i

        async def find_best_backref(self) -> Backref:
            best_backref = self.Backref(0, 0)

            if self.source_position == 0:
                return best_backref # no backref possible

            # Calculate search range
            first_possible_backref_position = (
                0 if self.source_position < self.MAX_BACKREF_OFFSET
                else self.source_position - self.MAX_BACKREF_OFFSET
            )
            last_possible_backref_position = self.source_position - 1
            current_backref_test = last_possible_backref_position

            r_len = self.source_position - first_possible_backref_position
            if first_possible_backref_position >= self.cc.chunk_start and first_possible_backref_position + r_len <= self.cc.chunk_end:
                r_pos = first_possible_backref_position - self.cc.chunk_start
                self.buf[:r_len] = self.cc.chunk[r_pos:r_pos + r_len]
            else:
                await self.cc.r_stream.seek(first_possible_backref_position)
                self.buf[:r_len] = await self.cc.r_stream.read(r_len)

            if self.source_position >= self.cc.chunk_start and self.source_position + self.MAX_BACKREF_LENGTH <= self.cc.chunk_end:
                c_pos = self.source_position - self.cc.chunk_start
                self.buf[r_len:] = self.cc.chunk[c_pos:c_pos + self.MAX_BACKREF_LENGTH]
            else:
                await self.cc.r_stream.seek(self.source_position)
                self.buf[r_len:] = await self.cc.r_stream.read(self.MAX_BACKREF_LENGTH)

            while True:
                # Count how many bytes we can match from this position
                count = 0
                local_max_backref_length = self.source_position - current_backref_test
                allowed_backref_length = min(
                    local_max_backref_length,
                    self.cc.size - self.source_position
                )

                for i in range(allowed_backref_length):
                    b_pos = current_backref_test - first_possible_backref_position + i
                    f_pos = self.source_position - first_possible_backref_position + i
                    if self.buf[b_pos] == self.buf[f_pos]:
                        count += 1
                    else:
                        break

                if count > best_backref.length:
                    best_backref.position = current_backref_test
                    best_backref.length = count

                if count == self.MAX_BACKREF_LENGTH:
                    break

                if current_backref_test == first_possible_backref_position:
                    break

                current_backref_test -= 1

            return best_backref

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            decomp = Crypt_LoHTrails.Decompression_LoHTrails(cc)
            await decomp.decompress()

    @staticmethod
    async def encrypt_file(filepath: str, title_id: str) -> None:
        async with CC(filepath) as cc:
            if title_id in LOH_TRAILS_DAYBREAK_TITLEID:
                seed = cc.size - 12
                crc32 = cc.create_ctx_crc32_any(0x4C11DB7, cc.reverse_32_bits(seed), True, True, 0, uint32(cc.size - 12, "little", const=True))
                await cc.checksum(crc32, start_off=12, end_off=cc.size)
                await cc.write_checksum(crc32, 8)
            elif title_id in LOH_TRAILS_ZERO_AZURE:
                file_size_max_pos = cc.size - 1
                file_savedata_checksum = uint32(0, "little")
                file_size_checksum = uint32(-1 * (((file_size_max_pos - 0x08) // 0x04) + 0x01), "little")
                while await cc.read(stop_off=cc.size - 8):
                    cc.bytes_to_u32array("little")
                    file_savedata_checksum.value += sum(u32.value for u32 in cc.chunk)
                file_size_checksum.value -= file_savedata_checksum.value
                await cc.w_stream.seek(cc.size - 8)
                await cc.w_stream.write(file_savedata_checksum.as_bytes)
                await cc.w_stream.seek(cc.size - 4)
                await cc.w_stream.write(file_size_checksum.as_bytes)
            else:
                # LOH_TRAILS_CS4_TITLEID
                seed = cc.size - 0x10
                crc32 = cc.create_ctx_crc32_any(0x04C11DB7, cc.reverse_32_bits(seed), True, True, 0, uint32(seed, "little", const=True))
                await cc.checksum(crc32, start_off=0x10, end_off=cc.size)
                await cc.write_checksum(crc32, 12)

        if title_id in LOH_TRAILS_CS4_TITLEID:
            async with CC(filepath, in_place=False) as cc:
                comp = Crypt_LoHTrails.Compression_LoHTrails(cc)
                await comp.compress()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if not is_dec:
                await Crypt_LoHTrails.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(filepath: str, title_id: str) -> None:
        if title_id in LOH_TRAILS_CS4_TITLEID:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if is_dec:
                await Crypt_LoHTrails.encrypt_file(filepath, title_id)
        else:
            await Crypt_LoHTrails.encrypt_file(filepath, title_id)
