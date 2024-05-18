import aiofiles
import struct
import re
import numpy as np
from typing import Literal

# Example
# 80010008 EA372703
# 00140000 00000000
# 180000E8 0000270F

class QuickCodesError(Exception):
    """Exception raised for errors relating to quick codes."""
    def __init__(self, message: str) -> None:
        self.message = message

class QuickCodes:
    """Functions to handle Save Wizard quick codes."""
    def __init__(self, filePath: str, codes: str, endianness: Literal["little", "big"]) -> None:
        self.filePath = filePath
        self.codes = codes
        self.endianness = endianness
        self.data = bytearray()

        parts = self.codes.split()
        try: 
            self.lines = [f"{parts[i]} {parts[i + 1]}" for i in range(0, len(parts), 2)]
        except IndexError: 
            raise QuickCodesError("Invalid code!")

        for line in self.lines:
            if not self.validate_code(line):
                raise QuickCodesError(f"Invalid code: {line}!")

    @staticmethod
    def search_data(data: bytearray | bytes, size: int, start: int, search: bytearray | bytes, length: int, count: int) -> int:
        k = 1

        for i in range(start, size - length + 1):
            if data[i:i + length] == search:
                if k == count:
                    return i
                k += 1
        return -1

    @staticmethod
    def reverse_search_data(data: bytearray | bytes, size: int, start: int, search: bytearray | bytes, length: int, count: int) -> int:
        k = 1
        
        for i in range(start, -1, -1):
            if (i + length <= size) and (data[i:i + length] == search) and (k == count):
                return i
            elif (i + length <= size) and (data[i:i + length] == search):
                k += 1
        return -1
    
    @staticmethod
    def validate_code(line: str) -> bool:
        return bool(re.match(r"^([0-9a-fA-F]){8} ([0-9a-fA-F]){8}$", line))

    async def read_file(self) -> None:
        async with aiofiles.open(self.filePath, "rb") as savegame:
            self.data.extend(await savegame.read())

    async def write_file(self) -> None:
        async with aiofiles.open(self.filePath, "wb") as savegame:
            await savegame.write(self.data)

    async def apply_code(self) -> None:
        fmt_s = "<" if self.endianness == "little" else ">"
        pointer = end_pointer = np.int_(0)
        ptr_value = np.uint32(0)

        await self.read_file()

        line_index = 0
        while line_index + 1 < len(self.lines):
            line = self.lines[line_index]
        
            try:
                match line[0]:
                    case "0" | "1" | "2":
                        bytes_ = np.uint8(1 << (int(line[0], 16) - 0x30))

                        tmp6 = line[2:8]
                        off = np.intc(int(tmp6, 16))
                        if line[1] == "8":
                            off += pointer

                        tmp8 = line[8:16]
                        val = np.uint32(int(tmp8, 16))
                        val += (4 - bytes_)
                        val = struct.pack(fmt_s + "I", val)

                        self.data[off:off + bytes_] = val

                    case "3":
                        t = line[1]

                        tmp6 = line[2:8]
                        off = np.intc(int(tmp6, 16))
                        if t in ["8", "9", "A", "C", "D", "E"]:
                            off += pointer
                        
                        tmp8 = line[8:16]
                        val = np.uint32(int(tmp8, 16))

                        write = off

                        match t:
                            case "0" | "8":
                                wv8 = np.uint8(write)
                                wv8 += (val & 0x000000FF)

                                self.data[write] = wv8
                            
                            case "1" | "9":
                                wv16 = np.uint16(write)
                                wv16 += (val & 0x0000FFFF)
                                wv16 = struct.pack(fmt_s + "H", wv32)
                                
                                self.data[write:write + 2] = wv16
                            
                            case "2" | "A":
                                wv32 = np.uint32(write)
                                wv32 += (val & 0xFFFFFFFF)
                                wv32 = struct.pack(fmt_s + "I" , wv32)

                                self.data[write:write + 4] = wv32

                            case "3" | "8":
                                # Not Implemented! Add-Wrote 8 bytes (%08X) to 0x%X", val, off
                                raise NotImplementedError

                            case "4" | "C":
                                wv8 = np.uint8(write)
                                wv8 -= (val & 0x000000FF)

                                self.data[write] = wv8

                            case "6" | "E":
                                wv32 = np.uint32(write)
                                wv32 -= (val & 0xFFFFFFFF)
                                wv32 = struct.pack(fmt_s + "I", wv32)

                                self.data[write:write + 4] = wv32
                            
                            case "7" | "F":
                                # Not Implemented! Sub-Write 8 bytes (%08X) to 0x%X", val, off
                                raise NotImplementedError
                            
                    case "4":
                        off = np.intc(int(line[2:8], 16))
                        t = line[1]
                        if t in ["8", "9", "A"]:
                            off += pointer

                        val = np.uint32(int(line[9:17], 16))

                        line = self.lines[line_index + 1]
                        line_index += 1

                        n = np.intc(int(line[1:4], 16))
                        incoff = np.intc(int(line[4:8], 16))
                        incval = np.uint32(int(line[9:17], 16))

                        for i in range(n):
                            write = off + (incoff * i)

                            match t:
                                case "0" | "8":
                                    wv8 = np.uint8(val)

                                    self.data[write] = wv8
                                
                                case "1" | "9":
                                    wv16 = np.uint16(val)
                                    wv16 = struct.pack(fmt_s + "H", wv16)

                                    self.data[write:write + 2] = wv16
                                
                                case "2" | "A":
                                    wv32 = np.uint32(val)
                                    wv32 = struct.pack(fmt_s + "I", wv32)

                                    self.data[write:write + 4] = wv32
                            
                            val += incval

                    case "5":
                        off_src = np.intc(int(line[2:8], 16))
                        val = np.uint32(int(line[9:17], 16))
                        src = 0

                        if line[1] == "8":
                            src += off_src

                        line = self.lines[line_index + 1]
                        line_index += 1

                        off_dst = np.intc(int(line[2:8], 16))
                        dst = 0
                        
                        if line[i] == "8":
                            dst += off_dst

                        self.data[dst:dst + val] = self.data[src:src + val]
                    
                    case "6":
                        t = line[1]
                        w = line[2]
                        x = line[3]
                        y = line[5]
                        z = line[7]

                        tmp8 = line[9:17]

                        val = np.uint32(struct.unpack(fmt_s + "I", bytes.fromhex(tmp8))[0])

                        write = 0
                        off = 0

                        if t in ["8", "9", "A"]:
                            off += pointer

                        match w:
                            case "0":
                                if x == "1":
                                    val += ptr_value 
                                write += (val + off)
                            
                                if y == "1":
                                    pointer = val
                                
                                match t:
                                    case "0" | "8":
                                        ptr_value = np.uint8(write)

                                    case "1" | "9":
                                        wv16 = np.uint16(write)
                                        ptr_value = wv16
                                    
                                    case "2" | "A":
                                        wv32 = np.uint32(write)
                                        ptr_value = wv32

                            case "1":
                                match x:
                                    case "0":
                                        ptr_value += val
                                    
                                    case "1":
                                        ptr_value -= val
                                    
                                    case "2":
                                        ptr_value *= val
                                
                                if z == "1":
                                    ptr_value += pointer
                                pointer = ptr_value
                            
                            case "2":
                                match x:
                                    case "0":
                                        pointer += val
                                    
                                    case "1":
                                        pointer -= val
                                    
                                    case "2":
                                        pointer *= val
                                    
                                if y == "1":
                                    ptr_value = pointer
                            
                            case "4":
                                write += pointer

                                match t:
                                    case "0" | "8":
                                        wv8 = val & 0xFF
                        
                                        self.data[write] = wv8
                                    
                                    case "1" | "9":
                                        wv16 = val & 0xFFFF
                                        wv16 = struct.pack(fmt_s + "H", wv16)

                                        self.data[write:write + 2] = wv16

                                    case "2" | "A":
                                        wv32 = val
                                        wv32 = struct.pack(fmt_s + "I", wv32)

                                        self.data[write:write + 4] = wv32
                    
                    case "7":
                        t = line[1]
                        tmp6 = line[2:8]
                        off = np.intc(int(tmp6, 16))

                        if t in ["8", "9", "A", "C", "D", "E"]:
                            off += pointer

                        tmp8 = line[9:17]
                        val = np.uint32(int(tmp8, 16))

                        write = off

                        match t:
                            case "0" | "8":
                                val &= 0x000000FF
                                wv8 = np.uint8(write)
                                if val > wv8: wv8 = val

                                self.data[write] = wv8

                            case "1" | "9":
                                val &= 0x0000FFFF
                                wv16 = np.uint16(write)
                                if val > wv16: wv16 = val
                                wv16 = struct.pack(fmt_s + "H", wv16)

                                self.data[write:write + 2] = wv16
                            
                            case "2" | "A":
                                wv32 = np.uint32(write)
                                if val > wv32: wv32 = val
                                wv32 = struct.pack(fmt_s + "I", wv32)

                                self.data[write:write + 4] = wv32
                            
                            case "4" | "C":
                                val &= 0x000000FF
                                wv8 = np.uint8(write)
                                if val < wv8: wv8 = val

                                self.data[write] = wv8

                            case "5" | "D":
                                val &= 0x0000FFFF
                                wv16 = np.uint16(write)
                                if val < wv16: wv16 = val
                                wv16 = struct.pack(fmt_s + "H", wv16)

                                self.data[write:write + 2] = wv16

                            case "6" | "E":
                                wv32 = np.uint32(write)
                                if val < wv32: wv32 = val
                                wv32 = struct.pack(fmt_s + "I", wv32)

                                self.data[write:write + 4] = wv32

                    case "8":
                        t = line[1]

                        tmp3 = line[2:4]
                        cnt = np.intc(int(tmp3, 16))

                        tmp4 = line[4:8]
                        length = np.intc(int(tmp4, 16))

                        tmp8 = line[9:17]
                        val = np.uint32(int(tmp8, 16))

                        find = bytearray((length + 3) & ~3)

                        if not cnt: cnt = 1

                        find[:4] = struct.pack(fmt_s + "I", val)

                        for i in range(4, length, 8):
                            line = self.lines[line_index + 1]
                            line_index += 1

                            tmp8 = line[:8]
                            val = int(tmp8, 16)

                            find[i:i + 4] = struct.pack(fmt_s + "I", val)

                            tmp8 = line[9:17]
                            val = int(tmp8, 16)

                            if i + 4 < length:
                                find[i + 4:i + 8] = struct.pack(fmt_s + "I", val)

                        pointer = self.search_data(self.data, len(self.data), pointer if t == "8" else 0, find, length, cnt)

                        if pointer < 0:
                            while line_index < len(self.lines):
                                line_index += 1

                                while (line and ((line[0] not in ["8", "B", "C"]) or line[1] == "8")):
                                    if line_index >= len(self.lines):
                                        break
                                    
                                    line = self.lines[line_index]
                                    line_index += 1
                            pointer = 0

                    case "9":
                        tmp8 = line[9:17]
                        off = np.uint32(int(tmp8, 16))

                        match line[1]:
                            case "0":
                                val = np.uint32(off)
                                val = struct.pack(">I", val)
                                val = struct.unpack(">I", val)[0]

                                pointer = val
                            
                            case "1":
                                val = np.uint32(off)
                                val = struct.pack("<I", val)
                                val = struct.unpack("<I", val)[0]

                                pointer = val
                            
                            case "2":
                                pointer += off
                            
                            case "3":
                                pointer -= off
                            
                            case "4": 
                                pointer = len(self.data) - off
                            
                            case "5":
                                pointer = off

                            case "D":
                                end_pointer = off

                            case "E":
                                end_pointer = pointer + off

                    case "A":
                        t = line[1]
                        tmp6 = line[2:8]

                        off = np.intc(int(tmp6, 16))
                        if t == "8":
                            off += pointer

                        tmp8 = line[9:17]
                        size = np.uint32(int(tmp8, 16))

                        write = bytearray((size + 3) & ~3)

                        for i in range(0, size, 8):
                            line = self.lines[line_index + 1]
                            line_index += 1

                            tmp8 = line[:8]
                            val = np.uint32(int(tmp8, 16))
                            val = struct.pack(">I", val)

                            write[i:i + 4] = val

                            tmp8 = line[9:17]
                            val = np.uint32(int(tmp8, 16))
                            val = struct.pack(">I", val)

                            if (i + 4) < size:
                                write[i + 4:(i + 4) + 4] = val
                        
                        self.data[off:off + size] = write[:size] 

                    case "B":
                        tmp3 = line[2:4] 
                        cnt = np.intc(int(tmp3, 16))

                        tmp4 = line[4:8]
                        length = np.intc(int(tmp4, 16))

                        tmp8 = line[9:17]
                        val = np.uint32(int(tmp8, 16))
                        val = struct.pack(">I", val)

                        find = bytearray((length +3 ) & ~3)
                        if not cnt: cnt = 1
                        if not end_pointer: end_pointer = len(self.data) - 1

                        find[:4] = val

                        for i in range(4, length, 8):
                            line = self.lines[line_index + 1]
                            line_index += 1

                            tmp8 = line[:8]
                            val = np.uint32(int(tmp8, 16))
                            val = struct.pack(">I", val)

                            find[i:i + 4] = val

                            tmp8 = line[9:17]
                            val = np.uint32(int(tmp8, 16))
                            val = struct.pack(">I", val)

                            if (i + 4) < length:
                                find[i + 4:(i + 4) + 4] = val

                        pointer = self.reverse_search_data(self.data, len(self.data), pointer if t == "8" else end_pointer, find, length, cnt)
                        
                        if pointer < 0:
                            while line_index < len(self.lines):
                                line_index += 1

                                while (line and ((line[0] not in ["8", "B", "C"]) or line[1] == "8")):
                                    if line_index >= len(self.lines):
                                        break
                                    
                                    line = self.lines[line_index]
                                    line_index += 1
                            pointer = 0
                    
                    case "C":
                        t = line[1]

                        tmp3 = line[2:4]
                        cnt = np.intc(int(tmp3, 16))

                        tmp4 = line[4:8]
                        length = np.intc(int(tmp4, 16))

                        tmp8 = line[9:17]
                        addr = np.uint32(int(tmp8, 16))

                        if t in ["8", "C"]:
                            addr += pointer

                        find = bytearray(struct.pack(fmt_s + "I", addr))

                        if t in ["4", "C"]:
                            pointer = self.search_data(self.data, addr + length, 0, find, length, cnt)
                        else:
                            pointer = self.search_data(self.data, len(self.data), addr + length, find, length, cnt)

                        if pointer < 0:
                            while line_index < len(self.lines):
                                line_index += 1

                                while (line and ((line[0] not in ["8", "B", "C"]) or line[1] == "8")):
                                    if line_index >= len(self.lines):
                                        break
                                    
                                    line = self.lines[line_index]
                                    line_index += 1
                            pointer = 0

                    case "D":
                        t = line[1]
                        op = line[12]
                        bit = line[11]

                        tmp6 = line[2:8]
                        off = np.intc(int(tmp6, 16))
                        if t == "8":
                            off += pointer

                        tmp3 = line[9:11]
                        l = int(tmp3, 16)

                        tmp4 = line[13:17]
                        val = np.intc(int(tmp4, 16))

                        src = np.uint16(off)

                        if bit == "1":
                            val &= 0xFF
                            src = np.uint8(self.data[off])
                        
                        match op:
                            case "0":
                                off = (src == val)

                            case "1":
                                off = (src != val)

                            case "2":
                                off = (src > val)
                            
                            case "3":
                                off = (src < val)

                            case _:
                                off = 1
                        
                        if not off:
                            while l > 0:
                                l -= 1
                                line = self.lines[line_index + 1]
                                line_index += 1
            except NotImplementedError:
                raise QuickCodesError("A code-type you entered has not yet been implemented!")
            except (ValueError, IOError, IndexError):
                raise QuickCodesError("Invalid code!")

            line_index += 1
        
        await self.write_file()
