import struct
from data.crypto.common import CustomCrypto as CC
from utils.constants import SW4_TITLEID, SW4_2_TITLEID, SW_SOS_TITLEID, SW4_E_TITLEID

class Crypt_SW:
    SW4_SUPPORTED_VERS = (0x18d2, 0x1cf5, 0x2118)
    # offset of first slot
    SW4_SLOT0 = 0
    SW4_SLOT_SIZE = -1
    SW4_NSLOTS = 1
    @staticmethod
    def sw4_get_regions(_: int) -> tuple[ tuple[ tuple[int, int], ... ], tuple[int, ...] ]:
        # start offset, length from offset
        SW4_SUM_REGIONS = (
            (0x8, 0xA0),
            (0xAC, 0x840),
            (0x8EC, 0x32A),
            (0xC1A, 0x6CBC),
            (0x85FE, 0x77F34),
            (0x78D6, 0xD28)
        )
        SW4_WRITE_OFFS = (
            0x4,
            0xA8,
            0xC16,
            0x80532
        )
        return SW4_SUM_REGIONS, SW4_WRITE_OFFS
    @staticmethod
    def sw4_mix(s: list[int]) -> list[int]:
        M = 0x7F_FF_FF_FF
        sm = [
            s[0] & M,
            s[1] & M,
            s[3] & M,
            s[4] & M
        ]
        s = [
            ( (sm[0] + sm[2]        ) * sm[1] + s[5] ) & 0xFF_FF_FF_FF,
            ( (sm[1] + sm[2] + sm[3]) * sm[0]        ) & 0xFF_FF_FF_FF,
            sum(s[:4])                                 & 0xFF_FF_FF_FF
        ]
        s.append( sum(s) & 0xFF_FF_FF_FF )
        s = map(lambda s: struct.pack("<I", s & M), s)
        return list(s)

    SW4_2_SUPPORTED_VERS = (0x31A4,) # 0x2D81 unsupported
    SW4_2_SLOT0 = 0
    SW4_2_SLOT_SIZE = -1
    SW4_2_NSLOTS = 1
    @staticmethod
    def sw4_2_get_regions(_: int) -> tuple[ tuple[ tuple[int, int], ... ], tuple[int, ...] ]:
        SW4_2_SUM_REGIONS = (
            (0x8, 0xA0),
            (0xAC, 0x960),
            (0xA0C, 0x642),
            (0x1052, 0xBBE4),
            (0xD92E, 0x77F40),
            (0xCC36, 0xCB8),
            (0xD8EE, 0x40)
        )
        SW4_2_WRITE_OFFS = (
            0x4,
            0xA8,
            0x104E,
            0x8586E
        )
        return SW4_2_SUM_REGIONS, SW4_2_WRITE_OFFS
    @staticmethod
    def sw4_2_mix(s: list[int]) -> list[int]:
        M = 0x7F_FF_FF_FF
        sm = [
            s[0] & M,
            s[1] & M,
            s[3] & M,
            s[4] & M
        ]
        s = [
            ( (sm[0] + sm[2]        ) * sm[1] + s[5] + s[6] ) & 0xFF_FF_FF_FF,
            ( (sm[1] + sm[2] + sm[3]) * sm[0]               ) & 0xFF_FF_FF_FF,
            sum(s[:4])                                        & 0xFF_FF_FF_FF
        ]
        s.append( sum(s) & 0xFF_FF_FF_FF )
        s = map(lambda s: struct.pack("<I", s & M), s)
        return list(s)

    SW_SOS_SUPPORTED_VERS = (0x846, 0x423)
    SW_SOS_SLOT0 = 0x1000
    SW_SOS_SLOT_SIZE = 0x28A000
    SW_SOS_NSLOTS = 4
    @staticmethod
    def sw_sos_get_regions(_: int) -> tuple[ tuple[ tuple[int, int], ... ], tuple[int, ...] ]:
        SW_SOS_SUM_REGIONS = (
            (0x8, 0xA4),
            (0xB0, 0x770),
            (0x820, 0x7980),
            (0x81A4, 0x4D0),
            (0xD5BC, 0x10144),
            (0x1D700, 0x7F734),
            (0x9CE34, 0x4374C),
            (0xE0580, 0x4374C),
            (0x123CCC, 0x4374C),
            (0x167418, 0x4374C),
            (0x1AAB64, 0x4374C),
            (0x1EE2B0, 0x4374C),
            (0x2319FC, 0x4374C)
        )
        SW_SOS_WRITE_OFFS = (
            0x4,
            0xAC,
            0x81A0,
            0x8674,
            0x275148,
            0x2752FC
        )
        return SW_SOS_SUM_REGIONS, SW_SOS_WRITE_OFFS
    @staticmethod
    def sw_sos_mix(s: list[int]) -> list[int]:
        M = 0x7F_FF_FF_FF
        sm = [
            s[0] & M,
            s[1] & M,
            s[4] & M,
            s[5] & M,
            sum(s[6:12]) & M
        ]
        s = [
            ( (sm[0] + sm[2]                        ) * sm[1] ) & 0xFF_FF_FF_FF,
            ( (sm[1] + sm[2] + sm[ 3]               ) * sm[0] ) & 0xFF_FF_FF_FF,
            ( (sm[0] + sm[1] + sm[ 2] + s[2]        )         ) & 0xFF_FF_FF_FF,
            ( (sm[0] + sm[1] + sm[ 2] + s[2] + s[ 3])         ) & 0xFF_FF_FF_FF,
            ( (sm[4]                  + s[0] + s[12])         ) & 0xFF_FF_FF_FF
        ]
        s.append( sum(s) & 0xFF_FF_FF_FF )
        s = map(lambda s: struct.pack("<I", s & M), s)
        return list(s)

    SW4_E_SUPPORTED_VERS = (0x4A76, 0x4653, 0x4230, 0x3E0D, 0x35C7)
    SW4_E_SLOT0 = 0
    SW4_E_SLOT_SIZE = -1
    SW4_E_NSLOTS = 1
    @staticmethod
    def sw4_e_get_regions(ver: int) -> tuple[ tuple[ tuple[int, int], ... ], tuple[int, ...] ]:
        SZ = 0x3CB6F
        VERS = {
            0x4A76: (0x31384, SZ * 5),
            0x4653: (0x31384, SZ * 5),
            0x4230: (0x31384, (SZ - 4) * 3),
            0x3E0D: (0x30B14, SZ * 5 + 0xAF96B),
            0x35C7: (0x31384, SZ * 5 - 20),
        }
        x, y = VERS[ver]
        SW4_E_SUM_REGIONS = (
            (0x8, 0xA0),
            (0xAC, 0xA78),
            (0xB24, 0x7DC),
            (0x1328, x),
            (0x1328 + x, y),
            (0x1328 + x + y, 0x257BB4)
        )
        SW4_E_WRITE_OFFS = (
            0x4,
            0xA8,
            0x1300,
            0x1328 + x + y + 0x257BB4
        )
        return SW4_E_SUM_REGIONS, SW4_E_WRITE_OFFS
    @staticmethod
    def sw4_e_mix(s: list[int]) -> list[int]:
        M = 0x7F_FF_FF_FF
        sm = [
            s[0] & M,
            s[1] & M,
            s[3] & M,
            s[5] & M
        ]
        s = [
            ( (sm[0] + sm[2]        ) * sm[1] + s[4] ) & 0xFF_FF_FF_FF,
            ( (sm[1] + sm[2] + sm[3]) * sm[0]        ) & 0xFF_FF_FF_FF,
            sum(s[:4])                                 & 0xFF_FF_FF_FF
        ]
        s.append( sum(s) & 0xFF_FF_FF_FF )
        s = map(lambda s: struct.pack("<I", s & M), s)
        return list(s)

    MAP = {}
    for t in SW4_TITLEID:
        MAP[t] = (
            SW4_SUPPORTED_VERS,
            SW4_SLOT0, SW4_SLOT_SIZE, SW4_NSLOTS,
            sw4_get_regions, sw4_mix
        )
    for t in SW4_2_TITLEID:
        MAP[t] = (
            SW4_2_SUPPORTED_VERS,
            SW4_2_SLOT0, SW4_2_SLOT_SIZE, SW4_2_NSLOTS,
            sw4_2_get_regions, sw4_2_mix
        )
    for t in SW_SOS_TITLEID:
        MAP[t] = (
            SW_SOS_SUPPORTED_VERS,
            SW_SOS_SLOT0, SW_SOS_SLOT_SIZE, SW_SOS_NSLOTS,
            sw_sos_get_regions, sw_sos_mix
        )
    for t in SW4_E_TITLEID:
        MAP[t] = (
            SW4_E_SUPPORTED_VERS,
            SW4_E_SLOT0, SW4_E_SLOT_SIZE, SW4_E_NSLOTS,
            sw4_e_get_regions, sw4_e_mix
        )

    @staticmethod
    async def sums(cc: CC, base: int, x: tuple[ tuple[int, int], ... ] ) -> list[int]:
        ss = []
        for off, l in x:
            s = 0
            off += base
            cc.set_ptr(off)
            while await cc.read(stop_off=off + l):
                s = (s + sum(cc.chunk)) & 0xFF_FF_FF_FF
            ss.append(s)
        return ss

    @staticmethod
    async def encrypt_file(filepath: str, title_id: str) -> None:
        assert title_id in Crypt_SW.MAP
        vers, slot0, slot_size, nslots, get_regions, mix = Crypt_SW.MAP[title_id]

        async with CC(filepath) as cc:
            for i in range(nslots):
                base = slot0 + slot_size * i
                ver = struct.unpack("<I", await cc.ext_read(base, 4))[0]
                if ver not in vers:
                    continue

                regions, write_offs = get_regions(ver)
                s = await Crypt_SW.sums(cc, base, regions)
                s = mix(s)
                for off, w in zip(write_offs, s):
                    await cc.ext_write(base + off, w)

    @staticmethod
    async def check_enc_ps(folderpath: str, title_id: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            await Crypt_SW.encrypt_file(filepath, title_id)

