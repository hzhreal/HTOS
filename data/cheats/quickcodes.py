import aiofiles
import numpy as np
import re
import struct
from struct import unpack, pack

np.seterr(all="ignore") # no need for any warnings

# Example
# 80010008 EA372703
# 00140000 00000000
# 180000E8 0000270F

QC_RE = re.compile(r"^([0-9a-fA-F]){8} ([0-9a-fA-F]){8}$")

class QuickCodesError(Exception):
    """Exception raised for errors relating to quick codes."""
    def __init__(self, message: str) -> None:
        self.message = message

class QuickCodes:
    """Functions to handle Save Wizard quick codes."""
    def __init__(self, filePath: str, codes: str) -> None:
        self.filePath = filePath
        self.codes = codes
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
        s = search[:length]

        for i in range(start, size - length + 1):
            if data[i:i + length] == s:
                if k == count:
                    return i
                k += 1
        return -1

    @staticmethod
    def reverse_search_data(data: bytearray | bytes, size: int, start: int, search: bytearray | bytes, length: int, count: int) -> int:
        k = 1
        s = search[:length]
        
        for i in range(start, -1, -1):
            if (i + length <= size) and (data[i:i + length] == s) and (k == count):
                return i
            elif (i + length <= size) and (data[i:i + length] == s):
                k += 1
        return -1
    
    @staticmethod
    def validate_code(line: str) -> bool:
        return bool(QC_RE.fullmatch(line))

    async def read_file(self) -> None:
        async with aiofiles.open(self.filePath, "rb") as savegame:
            self.data.extend(await savegame.read())

    async def write_file(self) -> None:
        async with aiofiles.open(self.filePath, "wb") as savegame:
            await savegame.write(self.data)

    async def apply_code(self) -> None:
        pointer = end_pointer = np.int_(0)
        ptr_value = np.uint32(0)

        await self.read_file()

        line_index = 0
        while line_index < len(self.lines):
            line = self.lines[line_index]
        
            try:
                match line[0]:
                    case "0" | "1" | "2":
                        #	8-bit write
    			        #	0TXXXXXX 000000YY
                        #   16-bit write
    				    #   1TXXXXXX 0000YYYY
                        #   32-bit write
                        #   2TXXXXXX YYYYYYYY
                        #   X= Address/Offset
                        #   Y= Value to write
                        #   T=Address/Offset type (0 = Normal / 8 = Offset From Pointer)
                        bytes_ = np.uint8(1 << (ord(line[0]) - 0x30))

                        tmp6 = line[2:8]
                        off = np.intc(int(tmp6, 16))
                        if line[1] == "8":
                            off += pointer

                        tmp8 = line[9:17]
                        val = np.uint32(int(tmp8, 16))
                        val = pack("<I", val)

                        self.data[off:off + bytes_] = val[(4 - bytes_):(4 - bytes_) + bytes_]

                    case "3":
                        #	Increase / Decrease Write
                        #	Increases or Decreases a specified amount of data from a specific Address
                        #	This does not add/remove Bytes into the save, it just adjusts the value of the Bytes already in it
                        #	For the 8 Byte Value Type, it will write 4 Bytes of data but will continue to write the bytes afterwards if it cannot write any more.
                        #	3BYYYYYY XXXXXXXX
                        #	B = Byte Value & Offset Type
                        #	0 = Add 1 Byte  (000000XX)
                        #	1 = Add 2 Bytes (0000XXXX)
                        #	2 = Add 4 Bytes
                        #	3 = Add 8 Bytes
                        #	4 = Sub 1 Byte  (000000XX)
                        #	5 = Sub 2 Bytes (0000XXXX)
                        #	6 = Sub 4 Bytes
                        #	7 = Sub 8 Bytes
                        #	8 = Offset from Pointer; Add 1 Byte  (000000XX)
                        #	9 = Offset from Pointer; Add 2 Bytes (0000XXXX)
                        #	A = Offset from Pointer; Add 4 Bytes
                        #	B = Offset from Pointer; Add 8 Bytes
                        #	C = Offset from Pointer; Sub 1 Byte  (000000XX)
                        #	D = Offset from Pointer; Sub 2 Bytes (0000XXXX)
                        #	E = Offset from Pointer; Sub 4 Bytes
                        #	F = Offset from Pointer; Sub 8 Bytes
                        #	Y = Address
                        #	X = Bytes to Add/Sub
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
                                wv8 = np.uint8(self.data[write])
                                wv8 += (val & 0x000000FF)

                                self.data[write] = wv8
                            
                            case "1" | "9":
                                wv16 = np.uint16(unpack("<H", self.data[write:write + 2])[0])
                                wv16 += (val & 0x0000FFFF)
                                wv16 = pack("<H", wv32)
                                
                                self.data[write:write + 2] = wv16
                            
                            case "2" | "A":
                                wv32 = np.uint32(unpack("<I", self.data[write:write + 4])[0])
                                wv32 += val
                                wv32 = pack("<I" , wv32)

                                self.data[write:write + 4] = wv32

                            case "3" | "B":
                                wv64 = np.uint64(unpack("<Q", self.data[write:write + 8])[0])
                                wv64 += val
                                wv64 = pack("<Q", wv64)

                                self.data[write:write + 8] = wv64

                            case "4" | "C":
                                wv8 = np.uint8(self.data[write])
                                wv8 -= (val & 0x000000FF)

                                self.data[write] = wv8

                            case "5" | "D":
                                wv16 = np.uint16(unpack("<H", self.data[write:write + 2])[0])
                                wv16 -= (val & 0x0000FFFF)
                                wv16 = pack("<H", wv16)

                                self.data[write:write + 2] = wv16
                            
                            case "6" | "E":
                                wv32 = np.uint32(unpack("<I", self.data[write:write + 4])[0])
                                wv32 -= val
                                wv32 = pack("<I", wv32)

                                self.data[write:write + 4] = wv32
                            
                            case "7" | "F":
                                wv64 = np.uint64(unpack("<Q", self.data[write:write + 8])[0])
                                wv64 -= val
                                wv64 = pack("<Q", wv64)

                                self.data[write:write + 8] = wv64
                            
                    case "4":
                        #	multi write
                        #	4TXXXXXX YYYYYYYY
                        #	4NNNWWWW VVVVVVVV | NNNNWWWW VVVVVVVV
                        #	X= Address/Offset
                        #	Y= Value to write (Starting)
                        #	N=Times to Write
                        #	W=Increase Address By
                        #	V=Increase Value By
                        #	T=Address/Offset type
                        #	Normal/Pointer
                        #	0 / 8 & 4 / C = 8bit
                        #	1 / 9 & 5 / D = 16bit
                        #	2 / A & 6 / E = 32bit
                        t = line[1]

                        tmp6 = line[2:8]
                        off = np.intc(int(tmp6, 16))
                        if t in ["8", "9", "A", "C", "D", "E"]:
                            off += pointer
                        
                        tmp8 = line[9:17]
                        val = np.uint32(int(tmp8, 16))

                        line = self.lines[line_index + 1]
                        line_index += 1
                        
                        if t in ["4", "5", "6", "C", "D", "E"]:
                            # NNNNWWWW VVVVVVVV
                            tmp4 = line[:4]
                            n = np.intc(int(tmp4, 16))
                        else:
                            # 4NNNWWWW VVVVVVVV
                            tmp3 = line[1:4]
                            n = np.intc(int(tmp3, 16))

                        tmp4 = line[4:8]
                        incoff = np.intc(int(tmp4, 16))

                        tmp8 = line[9:17]
                        incval = np.uint32(int(tmp8, 16))

                        for i in range(n):
                            write = off + (incoff * i)

                            match t:
                                case "0" | "8" | "4" | "C":
                                    wv8 = np.uint8(val)

                                    self.data[write] = wv8
                                
                                case "1" | "9" | "5" | "D":
                                    wv16 = np.uint16(val)
                                    wv16 = pack("<H", wv16)

                                    self.data[write:write + 2] = wv16
                                
                                case "2" | "A" | "6" | "E":
                                    wv32 = val
                                    wv32 = pack("<I", wv32)

                                    self.data[write:write + 4] = wv32
                            
                            val += incval

                    case "5":
                        #	copy bytes
                        #	5TXXXXXX ZZZZZZZZ
                        #	5TYYYYYY 00000000
                        #	  XXXXXX = Offset to copy from
                        #	  YYYYYY = Offset to copy to
                        #	         ZZZZZZZZ = Number of bytes to copy
                        #	 T = Bit Size
                        #	 0 = From start of the data
                        #	 8 = From found from a search
                        tmp6 = line[2:8]
                        off_src = np.intc(int(tmp6, 16))

                        tmp8 = line[9:17]
                        val = np.uint32(int(tmp8, 16))

                        src = off_src

                        if line[1] == "8":
                            src += pointer

                        line = self.lines[line_index + 1]
                        line_index += 1

                        tmp6 = line[2:8]
                        off_dst = np.intc(int(tmp6, 16))

                        dst = off_dst
                        
                        if line[1] == "8":
                            dst += pointer

                        self.data[dst:dst + val] = self.data[src:src + val]
                    
                    case "6":
                        #	special mega code
                        #	6TWX0Y0Z VVVVVVVV <- Code Type 6
                        #	6 = Type 6: Pointer codes
                        #	T = Data size of VVVVVVVV: 0:8bit, 1:16bit, 2:32bit, search-> 8:8bit, 9:16bit, A:32bit
                        #	W = operator:
                        #	      0X = Read "address" from file (X = 0:none, 1:add, 2:multiply)
                        #	      1X = Move pointer from obtained address ?? (X = 0:add, 1:substract, 2:multiply)
                        #	      2X = Move pointer ?? (X = 0:add, 1:substract, 2:multiply)
                        #	      4X = Write value: X=0 at read address, X=1 at pointer address
                        #	Y = flag relative to read add (very tricky to understand; 0=absolute, 1=pointer)
                        #	Z = flag relative to current pointer (very tricky to understand)
                        #	V = Data
                        t = line[1]
                        w = line[2]
                        x = line[3]
                        y = line[5]
                        z = line[7]

                        tmp8 = line[9:17]
                        val = np.uint32(int(tmp8, 16))

                        write = 0
                        off = 0

                        if t in ["8", "9", "A"]:
                            off += pointer

                        match w:
                            case "0":
                                # 0X = Read "address" from file (X = 0:none, 1:add, 2:multiply)
                                if x == "1":
                                    val += ptr_value 
                                write += (val + off)
                            
                                if y == "1":
                                    pointer = np.int_(val)
                                
                                match t:
                                    case "0" | "8":
                                        # Data size = 8 bits
						                # 000000VV
                                        ptr_value = np.uint32(self.data[write])

                                    case "1" | "9":
                                        # Data size = 16 bits
						                # 0000VVVV
                                        wv16 = unpack("<H", self.data[write:write + 2])[0]
                                        ptr_value = np.uint32(wv16)
                                    
                                    case "2" | "A":
                                        # Data size = 32 bits
						                # VVVVVVVV
                                        wv32 = unpack("<I", self.data[write:write + 4])[0]
                                        ptr_value = np.uint32(wv32)

                            case "1":
                                # 1X = Move pointer from obtained address ?? (X = 0:add, 1:substract, 2:multiply)
                                match x:
                                    case "0":
                                        ptr_value += val
                                    
                                    case "1":
                                        ptr_value -= val
                                    
                                    case "2":
                                        ptr_value *= val
                                
                                if z == "1":
                                    ptr_value += pointer
                                pointer = np.intc(ptr_value)
                            
                            case "2":
                                # 2X = Move pointer ?? (X = 0:add, 1:substract, 2:multiply)
                                match x:
                                    case "0":
                                        pointer += val
                                    
                                    case "1":
                                        pointer -= val
                                    
                                    case "2":
                                        pointer *= val
                                    
                                if y == "1":
                                    ptr_value = np.uint32(pointer)
                            
                            case "4":
                                # 4X = Write value: X=0 at read address, X=1 at pointer address
                                write += pointer

                                match t:
                                    case "0" | "8":
                                        wv8 = np.uint8(val)
                        
                                        self.data[write] = wv8
                                    
                                    case "1" | "9":
                                        wv16 = np.uint16(val)
                                        wv16 = pack("<H", wv16)

                                        self.data[write:write + 2] = wv16

                                    case "2" | "A":
                                        wv32 = val
                                        wv32 = pack("<I", wv32)

                                        self.data[write:write + 4] = wv32
                    
                    case "7":
                        #	Writes Bytes up to a specified Maximum/Minimum to a specific Address
                        #	This code is the same as a standard write code however it will only write the bytes if the current value at the address is no more or no less than X.
                        #	For example, you can use a no less than value to make sure the address has more than X but will take no effect if it already has more than the value on the save.
                        #	7BYYYYYY XXXXXXXX
                        #	B = Byte Value & Offset Type
                        #	0 = No Less Than: 1 Byte  (000000XX)
                        #	1 = No Less Than: 2 Bytes (0000XXXX)
                        #	2 = No Less Than: 4 Bytes
                        #	4 = No More Than: 1 Byte  (000000XX)
                        #	5 = No More Than: 2 Bytes (0000XXXX)
                        #	6 = No More Than: 4 Bytes
                        #	8 = Offset from Pointer; No Less Than: 1 Byte  (000000XX)
                        #	9 = Offset from Pointer; No Less Than: 2 Bytes (0000XXXX)
                        #	A = Offset from Pointer; No Less Than: 4 Bytes
                        #	C = Offset from Pointer; No More Than: 1 Byte  (000000XX)
                        #	D = Offset from Pointer; No More Than: 2 Bytes (0000XXXX)
                        #	E = Offset from Pointer; No More Than: 4 Bytes
                        #	Y = Address
                        #	X = Bytes to Write
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
                                wv8 = np.uint8(self.data[write])
                                if val > wv8: wv8 = val

                                self.data[write] = wv8

                            case "1" | "9":
                                val &= 0x0000FFFF
                                wv16 = np.uint16(self.data[write:write + 2])
                                if val > wv16: wv16 = val
                                wv16 = pack("<H", wv16)

                                self.data[write:write + 2] = wv16
                            
                            case "2" | "A":
                                wv32 = np.uint32(self.data[write:write + 4])
                                if val > wv32: wv32 = val
                                wv32 = pack("<I", wv32)

                                self.data[write:write + 4] = wv32
                            
                            case "4" | "C":
                                val &= 0x000000FF
                                wv8 = np.uint8(self.data[write])
                                if val < wv8: wv8 = val

                                self.data[write] = wv8

                            case "5" | "D":
                                val &= 0x0000FFFF
                                wv16 = np.uint16(self.data[write:write + 2])
                                if val < wv16: wv16 = val
                                wv16 = pack("<H", wv16)

                                self.data[write:write + 2] = wv16

                            case "6" | "E":
                                wv32 = np.uint32(self.data[write:write + 4])
                                if val < wv32: wv32 = val
                                wv32 = pack("<I", wv32)

                                self.data[write:write + 4] = wv32

                    case "8":
                        #	Search Type
                        #	8TZZXXXX YYYYYYYY
                        #	T= Address/Offset type (0 = Normal / 8 = Offset From Pointer)
                        #	Z= Amount of times to find before Write
                        #	X= Amount of data to Match
                        #	Y= Seach For (note can be extended for more just continue it like YYYYYYYY YYYYYYYY under it)
                        #	Once u have your Search type done then place one of the standard code types under it with setting T to the Pointer type
                        t = line[1]

                        tmp3 = line[2:4]
                        cnt = np.intc(int(tmp3, 16))

                        tmp4 = line[4:8]
                        length = np.intc(int(tmp4, 16))

                        tmp8 = line[9:17]
                        val = np.uint32(int(tmp8, 16))

                        find = bytearray((length + 3) & ~3)

                        if not cnt: cnt = np.intc(1)

                        find[:4] = pack(">I", val)

                        for i in range(4, length, 8):
                            line = self.lines[line_index + 1]
                            line_index += 1

                            tmp8 = line[:8]
                            val = np.uint32(int(tmp8, 16))

                            find[i:i + 4] = pack(">I", val)

                            tmp8 = line[9:17]
                            val = np.uint32(int(tmp8, 16))

                            if i + 4 < length:
                                find[(i + 4):(i + 4) + 4] = pack(">I", val)

                        pointer = np.int_(self.search_data(self.data, len(self.data), pointer if t == "8" else 0, find, length, cnt))

                        if pointer < 0:
                            while line_index < len(self.lines):
                                line_index += 1

                                while (line and ((line[0] not in ["8", "B", "C"]) or line[1] == "8")):
                                    if line_index >= len(self.lines):
                                        break
                                    
                                    line = self.lines[line_index]
                                    line_index += 1
                            pointer = np.int_(0)

                    case "9":
                        #	Pointer Manipulator (Set/Move Pointer)
                        #	Adjusts the Pointer Offset using numerous Operators
                        #	9Y000000 XXXXXXXX
                        #	Y = Operator
                        #	0 = Set Pointer to Big Endian value at XXXXXXXX
                        #	1 = Set Pointer to Little Endian value at XXXXXXXX
                        #	2 = Add X to Pointer
                        #	3 = Sub X to Pointer
                        #	4 = Set Pointer to the end of file and subtract X
                        #	5 = Set Pointer to X
                        #	D = Set End Address = to X
                        #	E = Set End Address From Pointer + X
                        #	X = Value to set / change
                        #	---
                        #	Move pointer to offset in address XXXXXXXXX (CONFIRMED CODE)
                        #	90000000 XXXXXXXX
                        #	---
                        #	Step Forward Code (CONFIRMED CODE)
                        #	92000000 XXXXXXXX
                        #	---
                        #	Step Back Code (CONFIRMED CODE)
                        #	93000000 XXXXXXXX
                        #	---
                        #	Step Back From End of File Code (CONFIRMED CODE)
                        #	94000000 XXXXXXXX
                        tmp8 = line[9:17]
                        off = np.uint32(int(tmp8, 16))

                        match line[1]:
                            case "0":
                                val = np.uint32(unpack(">I", self.data[off:off + 4])[0])
                                pointer = np.int_(val)
                            
                            case "1":
                                val = np.uint32(unpack("<I", self.data[off:off + 4])[0])
                                pointer = np.int_(val)
                            
                            case "2":
                                pointer += off
                            
                            case "3":
                                pointer -= off
                            
                            case "4": 
                                pointer = np.int_(len(self.data) - off)
                            
                            case "5":
                                pointer = np.int_(off)

                            case "D":
                                end_pointer = np.int_(off)

                            case "E":
                                end_pointer = np.int_(pointer + off)

                    case "A":
                        #	Multi-write
                        #	ATxxxxxx yyyyyyyy  (xxxxxx = address, yyyyyyyy = size)
                        #	zzzzzzzz zzzzzzzz  <-data to write at address
                        #	T= Address/Offset type (0 = Normal / 8 = Offset From Pointer)
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
                            val = pack(">I", val)

                            write[i:i + 4] = val

                            tmp8 = line[9:17]
                            val = np.uint32(int(tmp8, 16))
                            val = pack(">I", val)

                            if (i + 4) < size:
                                write[(i + 4):(i + 4) + 4] = val
                        
                        self.data[off:off + size] = write[:size] 

                    case "B":
                        #	Backward Byte Search (Set Pointer)
                        #	Searches Backwards for a specified Value and saves the Value's Address as the Pointer Offset
                        #	Will start from the end of the save file, but can be changed using a previous Pointer Offset
                        #	BTCCYYYY XXXXXXXX
                        #	*Other Code Here, Use Specific Offset Type*
                        #	T = Offset Type
                        #	0 = Default
                        #	8 = Offset from Pointer
                        #	C = Amount of Times to Find until Pointer Set
                        #	Y = Amount of Bytes to Search
                        #	1 = 1 Byte
                        #	2 = 2 Bytes
                        #	and so on...
                        #	X = Bytes to Search, use Multiple Lines if Needed
                        t = line[1]

                        tmp3 = line[2:4] 
                        cnt = np.intc(int(tmp3, 16))

                        tmp4 = line[4:8]
                        length = np.intc(int(tmp4, 16))

                        tmp8 = line[9:17]
                        val = np.uint32(int(tmp8, 16))
                        val = pack(">I", val)

                        find = bytearray((length + 3) & ~3)
                        if not cnt: cnt = np.intc(1)
                        if not end_pointer: end_pointer = np.int_(len(self.data) - 1)

                        find[:4] = val

                        for i in range(4, length, 8):
                            line = self.lines[line_index + 1]
                            line_index += 1

                            tmp8 = line[:8]
                            val = np.uint32(int(tmp8, 16))
                            val = pack(">I", val)

                            find[i:i + 4] = val

                            tmp8 = line[9:17]
                            val = np.uint32(int(tmp8, 16))
                            val = pack(">I", val)

                            if (i + 4) < length:
                                find[(i + 4):(i + 4) + 4] = val

                        pointer = np.int_(self.reverse_search_data(self.data, len(self.data), pointer if t == "8" else end_pointer, find, length, cnt))
                        
                        if pointer < 0:
                            while line_index < len(self.lines):
                                line_index += 1

                                while (line and ((line[0] not in ["8", "B", "C"]) or line[1] == "8")):
                                    if line_index >= len(self.lines):
                                        break
                                    
                                    line = self.lines[line_index]
                                    line_index += 1
                            pointer = np.int_(0)
                    
                    case "C":
                        #	Address Byte Search (Set Pointer)
                        #	Searches for a Value from a specified Address and saves the new Value's Address as the Pointer Offset
                        #	Rather than searching for Bytes already given such as code types 8 and B, this code will instead search using the bytes at a specific Address
                        #	CBFFYYYY XXXXXXXX
                        #	*Other Code Here, Use Specific Offset Type*
                        #	B = Offset Type
                        #	0 = Search Forwards from Address Given
                        #	4 = Search from 0x0 to Address Given
                        #	8 = Offset from Pointer; Search Forwards from Address Given
                        #	C = Offset from Pointer; Search from 0x0 to Address Given
                        #	F = Amount of Times to Find until Pointer Set
                        #	Y = Amount of Bytes to Search from Address
                        #	1 = 1 Byte
                        #	2 = 2 Bytes
                        #	and so on...
                        #	X = Address of Bytes to Search with
                        t = line[1]

                        tmp3 = line[2:4]
                        cnt = np.intc(int(tmp3, 16))

                        tmp4 = line[4:8]
                        length = np.intc(int(tmp4, 16))

                        tmp8 = line[9:17]
                        addr = np.uint32(int(tmp8, 16))

                        if t in ["8", "C"]:
                            addr += pointer

                        find = self.data[addr:]

                        if not cnt: cnt = np.intc(1)

                        if t in ["4", "C"]:
                            pointer = np.int_(self.search_data(self.data, addr + length, 0, find, length, cnt))
                        else:
                            pointer = np.int_(self.search_data(self.data, len(self.data), addr + length, find, length, cnt))

                        if pointer < 0:
                            while line_index < len(self.lines):
                                line_index += 1

                                while (line and ((line[0] not in ["8", "B", "C"]) or line[1] == "8")):
                                    if line_index >= len(self.lines):
                                        break
                                    
                                    line = self.lines[line_index]
                                    line_index += 1
                            pointer = np.int_(0)

                    case "D":
                        #	2 Byte Test Commands (Code Skipper)
                        #	Test a specific Address using an Operation; skips the following code lines if Operation fails
                        #	DBYYYYYY CCZDXXXX
                        #	B = Offset Type
                        #	0 = Normal
                        #	8 = Offset from Pointer
                        #	Y = Address to test
                        #	C = Lines of code to skip if test fails
                        #	Z = Value data type
                        #	0 = 16-bit
                        #	1 = 8-bit
                        #	D = Test Operation
                        #	0 = Equal
                        #	1 = Not Equal
                        #	2 = Greater Than (Value at the Address is greater than the tested value)
                        #	3 = Less Than (Value at the Address is less than the tested value)
				        #	X = Value to test
                        t = line[1]
                        op = line[12]
                        bit = line[11]

                        tmp6 = line[2:8]
                        off = np.intc(int(tmp6, 16))
                        if t == "8":
                            off += pointer

                        tmp3 = line[9:11]
                        l = np.intc(int(tmp3, 16))

                        tmp4 = line[13:17]
                        val = np.intc(int(tmp4, 16))

                        src = unpack("<H", self.data[off:off + 2])[0]

                        if bit == "1":
                            val &= 0xFF
                            src = self.data[off]
                        
                        match op:
                            case "0":
                                off = np.intc((src == val))

                            case "1":
                                off = np.intc((src != val))

                            case "2":
                                off = np.intc((src > val))
                            
                            case "3":
                                off = np.intc((src < val))

                            case _:
                                off = np.intc(1)
                        
                        if not off:
                            while l > 0:
                                l -= 1
                                line = self.lines[line_index + 1]
                                line_index += 1
            # except NotImplementedError:
            #     raise QuickCodesError("A code-type you entered has not yet been implemented!")
            except (ValueError, IOError, IndexError, struct.error):
                raise QuickCodesError("Invalid code!")

            line_index += 1
        
        await self.write_file()
