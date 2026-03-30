from aiohttp.client_middleware_digest_auth import CHALLENGE_FIELDS
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from utils.type_helpers import uint32, int32

class Crypt_TR6R:
    ID = b"TOMB"

    BASE_SAVEGAME_OFFSET_TR6      = 0x293C04
    SAVEGAME_SIZE                 = 0x00A470
    MAX_SAVEGAMES                 = 32
    COMPRESSED_BLOCK_START_OFFSET = 0x00368
    COMPRESSED_BLOCK_SIZE_OFFSET  = 0x00360
    MAX_BUFFER_SIZE               = 0x40000

    class LZW:
        MAX_BITS          = 12
        INIT_BITS         =  9
        MAX_CODE          = (1 << MAX_BITS) - 1
        CLEAR_CODE        = 0x0100
        FIRST_CODE        = 0x0101
        HASH_SIZE         = 0x1400
        CLEAR_TABLE       = (0x00, 0x3C, 0x18, 0x54, 0x30, 0x0C, 0x48, 0x24)
        COMPRESSED_HEADER = b"\x1F\x9D\x8C"

        def __init__(self, cc: CC, max_target_size: int, start_off: int, stop_off: int) -> None:
            self.cc = cc
            assert not self.cc.in_place
            self.max_target_size = max_target_size # make sure we can write max_target_size without exceeding SAVESIZE_MAX before
            self.stop_off = stop_off

            self.source_pos = start_off
            cc.set_ptr(self.source_pos)

            self.target_pos = 0
            self.target_idx = 0
            self.target_buf = bytearray(min(cc.CHUNKSIZE, max_target_size))

            self.bit_buf   = 0
            self.bit_count = 0
            self.bit_total = 8 * 3 # start after header

            self.code_width = self.INIT_BITS
            self.max_code   = (1 << self.code_width) - 1
            self.next_code  = self.FIRST_CODE

            self.block_base = self.bit_total

        async def fill_source(self) -> bool:
            if self.source_pos < self.cc.chunk_end:
                return True
            return bool(await self.cc.read(stop_off=self.stop_off))

        async def read_source(self) -> int:
            if not await self.fill_source():
                return -1
            r_pos = self.source_pos - self.cc.chunk_start
            self.source_pos += 1
            return self.cc.chunk[r_pos]

        async def write_alloc_target(self) -> None:
            del self.target_buf[self.target_idx:]
            await self.cc.w_stream.write(self.target_buf)

        async def alloc_target(self) -> None:
            await self.write_alloc_target()
            self.target_buf = bytearray(min(self.cc.CHUNKSIZE, self.max_target_size))
            self.target_idx = 0

        async def write_target(self, b: int) -> None:
            if self.target_pos >= self.max_target_size:
                raise CryptoError("Invalid save!")
            if self.target_idx == len(self.target_buf):
                await self.alloc_target()
            self.target_buf[self.target_idx] = b
            self.target_idx += 1
            self.target_pos += 1
    class LZW_Decompress(LZW):
        def __init__(self, cc: CC, max_target_size: int, start_off: int, stop_off: int) -> None:
            super().__init__(cc, max_target_size, start_off, stop_off)
            self.table = [(0, 0)] * (self.MAX_CODE + 1) # (prefix, suffix)

        async def decompress(self) -> int:
            for b in self.COMPRESSED_HEADER:
                if await self.read_source() != b:
                    raise CryptoError("Invalid save!")

            # Read the very first code — it is always a literal
            prev_code = await self.read_bits(self.code_width)
            if prev_code == -1:
                return self.target_pos
            # Extremely unlikely for a well-formed stream, but handle it
            if prev_code == self.CLEAR_CODE:
                return self.target_pos

            # Output the first literal
            await self.write_target(prev_code & 0xFF)

            # root char of the previous string
            first_char = prev_code & 0xFF

            while (code := await self.read_bits(self.code_width)) != -1:
                if code == self.CLEAR_CODE:
                    # Reset dictionary and skip padding bits
                    bits_since = self.bit_total - self.block_base
                    idx = (bits_since >> 2) & 7
                    extra_bits = self.CLEAR_TABLE[idx]
                    if not await self.skip_bits(extra_bits):
                        break

                    self.reset_lzw()

                    # Read the first code of the new block
                    prev_code = await self.read_bits(self.code_width)
                    if prev_code == -1:
                        break
                    if prev_code == self.CLEAR_CODE:
                        # Should not happen in a valid stream
                        break

                    await self.write_target(prev_code & 0xFF)
                    first_char = prev_code & 0xFF
                    continue

                # Decode current code
                if code < self.next_code:
                    # Code is already in the table (or is a literal)
                    new_first_char = await self.decode_string(code)
                elif code == self.next_code:
                    # Special case: encoder just added this code; its string is the previous string + its own first character
                    new_first_char = first_char
                    # Temporarily emit the previous string, then append first_char
                    await self.decode_string(prev_code)
                    await self.write_target(first_char)
                else:
                    return self.target_pos

                if code != self.next_code:
                    first_char = new_first_char

                # Add new entry to the string table
                if self.next_code <= self.MAX_CODE:
                    self.table[self.next_code] = (prev_code, first_char)
                    self.next_code += 1

                    # Widen code width when the next code would exceed the current max
                    if self.next_code > self.max_code and self.code_width < self.MAX_BITS:
                        self.code_width += 1
                        self.max_code = (1 << self.code_width) - 1

                prev_code = code

            if self.target_idx != 0:
                await self.write_alloc_target()
            return self.target_pos

        async def decode_string(self, code: int) -> int:
            """
            Decode a code to a byte string and write it into the output buffer.
            Returns the first (root) character of the string.
            """

            # Walk the chain and build the string in reverse on a small stack
            stack = [0] * (self.MAX_CODE + 1)
            top = 0

            while code > 0xFF:
                if top >= len(stack):
                    raise CryptoError("Invalid save!")
                prefix, suffix = self.table[code]
                stack[top] = suffix
                top += 1
                code = prefix
            # code is now the root literal character
            first_char = code & 0xFF
            stack[top] = first_char
            top += 1

            # Write the string forward (reverse the stack)
            for i in range(top - 1, -1, -1):
                await self.write_target(stack[i])
            return first_char

        async def read_bits(self, width: int) -> int:
            while self.bit_count < width:
                r = await self.read_source()
                if r == -1:
                    return -1
                self.bit_buf |= r << self.bit_count
                self.bit_buf &= 0xFF_FF_FF_FF_FF_FF_FF_FF
                self.bit_count += 8
            r = self.bit_buf & ((1 << width) - 1)
            r &= 0xFF_FF_FF_FF
            self.bit_buf >>= width
            self.bit_count -= width
            self.bit_total += width
            return r

        async def skip_bits(self, width: int) -> bool:
            while width > 0:
                chunk = min(width, self.bit_count)
                if chunk == 0:
                    r = await self.read_source()
                    if r == -1:
                        return False
                    self.bit_buf |= r << self.bit_count
                    self.bit_buf &= 0xFF_FF_FF_FF_FF_FF_FF_FF
                    self.bit_count += 8
                    continue
                self.bit_buf >>= chunk
                self.bit_count -= chunk
                self.bit_total += chunk
                width -= chunk
            return True

        def reset_lzw(self) -> None:
            self.code_width = self.INIT_BITS
            self.max_code   = (1 << self.code_width) - 1
            self.next_code  = self.FIRST_CODE
            self.block_base = self.bit_total
    class LZW_Compress(LZW):
        def __init__(self, cc: CC, max_target_size: int, start_off: int, stop_off: int) -> None:
            super().__init__(cc, max_target_size, start_off, stop_off)
            self.dictionary = [0] * self.HASH_SIZE

        async def compress(self) -> int:
            for b in self.COMPRESSED_HEADER:
                await self.write_target(b)

            current_code = await self.read_source()
            while (next_char := await self.read_source()) != -1:
                combined_code = (current_code << 8) | next_char
                combined_code &= 0xFF_FF_FF_FF
                hash_idx = (next_char << 4) ^ current_code
                hash_idx %= self.HASH_SIZE

                found = False
                if hash_idx == 0:
                    step = 1
                else:
                    step = 0x13_FF - hash_idx
                    step &= 0xFF_FF_FF_FF

                while (entry := self.dictionary[hash_idx]) != 0:
                    adjusted = entry + ((entry >> 31) & 0xFF_F)
                    adjusted = int32(adjusted, "little")
                    if (adjusted.value >> 12) == combined_code:
                        current_code = entry & 0xFF_F
                        found = True
                        break

                    # Apply probe arithmetic
                    temp_idx = hash_idx - step
                    if temp_idx < 0:
                        temp_idx += 0x13_FF # wraparound
                    hash_idx = temp_idx

                if not found:
                    await self.write_bits(current_code, self.code_width)

                    if self.next_code > self.max_code and self.code_width < self.MAX_BITS:
                        self.code_width += 1
                        self.max_code = (1 << self.code_width) - 1

                    if self.next_code <= self.MAX_CODE:
                        self.dictionary[hash_idx] = (combined_code << 12) | self.next_code
                        self.dictionary[hash_idx] &= 0xFF_FF_FF_FF
                        self.next_code += 1
                    else:
                        # Dictionary full: emit CLEAR code and then flush extra bits
                        await self.write_bits(self.CLEAR_CODE, self.code_width)
                        # Compute how many bits have been output since the start of this dictionary block
                        bits_since = self.bit_total - self.block_base
                        idx = (bits_since >> 2) & 7
                        extra_bits = self.CLEAR_TABLE[idx]
                        await self.write_bits(0, extra_bits)

                        self.reset_lzw()

                    current_code = next_char

            # Final write
            await self.write_bits(current_code, self.code_width)

            # Flush remaining bits
            if self.bit_count > 0:
                await self.write_target(self.bit_buf & 0xFF)
                self.bit_buf = 0
                self.bit_count = 0

            if self.target_idx != 0:
                await self.write_alloc_target()
            return self.target_pos

        async def write_bits(self, code: int, width: int) -> None:
            self.bit_buf |= code << self.bit_count
            self.bit_buf &= 0xFF_FF_FF_FF_FF_FF_FF_FF
            self.bit_count += width
            self.bit_total += width
            while self.bit_count >= 8:
                await self.write_target(self.bit_buf & 0xFF)
                self.bit_buf >>= 8
                self.bit_count -= 8

        def reset_lzw(self) -> None:
            self.dictionary = [0] * self.HASH_SIZE
            self.code_width = self.INIT_BITS
            self.max_code   = (1 << self.code_width) - 1
            self.next_code  = self.FIRST_CODE

            self.block_base = self.bit_total

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            await cc.copy(0, Crypt_TR6R.BASE_SAVEGAME_OFFSET_TR6)
            for i in range(Crypt_TR6R.MAX_SAVEGAMES):
                off = Crypt_TR6R.BASE_SAVEGAME_OFFSET_TR6 + i * Crypt_TR6R.SAVEGAME_SIZE
                comp_off = off + Crypt_TR6R.COMPRESSED_BLOCK_START_OFFSET
                comp_size_off = off + Crypt_TR6R.COMPRESSED_BLOCK_SIZE_OFFSET
                await cc.copy(off, comp_size_off)

                await cc.r_stream.seek(comp_size_off)
                comp_size = uint32(await cc.r_stream.read(4), "little").value

                await cc.r_stream.seek(comp_off)
                header = await cc.r_stream.read(len(Crypt_TR6R.LZW.COMPRESSED_HEADER))
                await cc.r_stream.seek(off)
                identifier = await cc.r_stream.read(len(Crypt_TR6R.ID))
                if header != Crypt_TR6R.LZW.COMPRESSED_HEADER or identifier != Crypt_TR6R.ID:
                    l = Crypt_TR6R.MAX_BUFFER_SIZE - Crypt_TR6R.COMPRESSED_BLOCK_SIZE_OFFSET
                    if await cc.w_stream.tell() + l > cc.SAVESIZE_MAX:
                        raise CryptoError("Unsupported save!")
                    for i in range(0, l, cc.CHUNKSIZE):
                        b = b"\x00" * (min(cc.CHUNKSIZE, l - i))
                        await cc.w_stream.write(b)
                    continue

                if await cc.w_stream.tell() + Crypt_TR6R.MAX_BUFFER_SIZE + 8 > cc.SAVESIZE_MAX:
                    raise CryptoError("Unsupported save!")
                decomp = Crypt_TR6R.LZW_Decompress(cc, Crypt_TR6R.MAX_BUFFER_SIZE, comp_off, comp_off + comp_size)
                cur = await cc.w_stream.tell()
                await cc.w_stream.write(b"\x00" * 8)
                decomp_size = await decomp.decompress()
                await cc.w_stream.seek(cur)
                await cc.w_stream.write(uint32(decomp_size, "little").as_bytes)

                await cc.w_stream.seek(0, 2)
                n = Crypt_TR6R.MAX_BUFFER_SIZE - decomp_size - 8 - Crypt_TR6R.COMPRESSED_BLOCK_SIZE_OFFSET
                if n > 0:
                    for i in range(0, n, cc.CHUNKSIZE):
                        b = b"\xFF" * (min(cc.CHUNKSIZE, n - i))
                        await cc.w_stream.write(b)

            await cc.copy(Crypt_TR6R.BASE_SAVEGAME_OFFSET_TR6 + Crypt_TR6R.MAX_SAVEGAMES * Crypt_TR6R.SAVEGAME_SIZE, cc.size)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            await cc.copy(0, Crypt_TR6R.BASE_SAVEGAME_OFFSET_TR6)
            for i in range(Crypt_TR6R.MAX_SAVEGAMES):
                off = Crypt_TR6R.BASE_SAVEGAME_OFFSET_TR6 + i * Crypt_TR6R.MAX_BUFFER_SIZE
                decomp_off = off + Crypt_TR6R.COMPRESSED_BLOCK_START_OFFSET
                decomp_size_off = off + Crypt_TR6R.COMPRESSED_BLOCK_SIZE_OFFSET
                await cc.copy(off, decomp_size_off)

                await cc.r_stream.seek(decomp_size_off)
                decomp_size = uint32(await cc.r_stream.read(4), "little").value

                await cc.r_stream.seek(decomp_off)
                buf1 = await cc.r_stream.read(len(Crypt_TR6R.ID))
                await cc.r_stream.seek(off)
                buf2 = await cc.r_stream.read(len(Crypt_TR6R.ID))
                if buf1 != Crypt_TR6R.ID or buf2 != Crypt_TR6R.ID:
                    l = Crypt_TR6R.SAVEGAME_SIZE - Crypt_TR6R.COMPRESSED_BLOCK_SIZE_OFFSET
                    if await cc.w_stream.tell() + l > cc.SAVESIZE_MAX:
                        raise CryptoError("Unsupported save!")
                    for i in range(0, l, cc.CHUNKSIZE):
                        b = b"\x00" * (min(cc.CHUNKSIZE, l - i))
                        await cc.w_stream.write(b)
                    continue

                if await cc.w_stream.tell() + Crypt_TR6R.SAVEGAME_SIZE + 8 > cc.SAVESIZE_MAX:
                    raise CryptoError("Unsupported save!")
                comp = Crypt_TR6R.LZW_Compress(cc, Crypt_TR6R.SAVEGAME_SIZE, decomp_off, decomp_off + decomp_size)
                cur = await cc.w_stream.tell()
                await cc.w_stream.write(b"\x00" * 8)
                comp_size = await comp.compress()
                await cc.w_stream.seek(cur)
                await cc.w_stream.write(uint32(comp_size, "little").as_bytes)

                await cc.w_stream.seek(0, 2)
                n = Crypt_TR6R.SAVEGAME_SIZE - comp_size - 8 - Crypt_TR6R.COMPRESSED_BLOCK_SIZE_OFFSET
                if n > 0:
                    for i in range(0, n, cc.CHUNKSIZE):
                        b = b"\x00" * min(cc.CHUNKSIZE, n - i)
                        await cc.w_stream.write(b)

            await cc.copy(Crypt_TR6R.BASE_SAVEGAME_OFFSET_TR6 + Crypt_TR6R.MAX_SAVEGAMES * Crypt_TR6R.MAX_BUFFER_SIZE, cc.size)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                id_search     = await cc.find(Crypt_TR6R.ID)
                header_search = await cc.find(Crypt_TR6R.LZW.COMPRESSED_HEADER)
            if id_search != -1 and header_search != -1:
                await Crypt_TR6R.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with CC(filepath) as cc:
            id_search     = await cc.find(Crypt_TR6R.ID)
            header_search = await cc.find(Crypt_TR6R.LZW.COMPRESSED_HEADER)
        if id_search != -1 and header_search == -1:
            await Crypt_TR6R.encrypt_file(filepath)

