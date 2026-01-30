from data.crypto.common import CustomCrypto

class Converter(CustomCrypto):
    # When converting we have to move PSIN or RSAV header to the start bytes
    # GTA V:
        # PS4 is 0x114
        # PC is 0x108
    # RDR 2:
        # PS4 is 0x120
        # PC is 0x110
    async def push_bytes(self, src_off: int, dst_off: int) -> None:
        assert not self.in_place

        # read from 0 to src_off and write
        await self.r_stream.seek(0)
        await self.w_stream.seek(0, 2)
        for _ in range(int(src_off / self.CHUNKSIZE)):
            chunk = await self.r_stream.read(self.CHUNKSIZE)
            await self.w_stream.write(chunk)
        last_chunk = await self.r_stream.read(src_off % self.CHUNKSIZE)
        await self.w_stream.write(last_chunk)

        # read from source off and write at dst_off
        # if there are bytes in between they will be zero filled
        await self.r_stream.seek(src_off)
        await self.w_stream.seek(dst_off)
        while True:
            chunk = await self.r_stream.read(self.CHUNKSIZE)
            if not chunk:
                break
            await self.w_stream.write(chunk)

