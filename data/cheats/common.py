from data.crypto.common import CustomCrypto

class QuickCheats(CustomCrypto):
    async def find_off_with_identifier32(self, before_offset: bytes, after_offset: bytes | None, bytes_between: int) -> int:
        """Used to find an offset using values that identify the location (32 bit / 4 byte)."""
        index = 0
        target_offset = -1

        while index < self.size:
            identifier_offset = await self.find(before_offset, index)
            if identifier_offset == -1: 
                break

            if after_offset is not None:
                second_identifier_offset = identifier_offset + bytes_between + 4
                await self.r_stream.seek(second_identifier_offset)
                second_identifier_data = await self.r_stream.read(4)

                if second_identifier_data == after_offset:
                    target_offset = identifier_offset + bytes_between
                    break

                index = identifier_offset + 1

            else:
                target_offset = identifier_offset + bytes_between
                break

        return target_offset
