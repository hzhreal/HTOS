import math

def mb_to_bytes(n: int) -> int:
    return n << 20

def gb_to_bytes(n: int) -> int:
    return n << 30

def saveblocks_to_bytes(blocks: int) -> int:
    return blocks << 15

def bytes_to_mb(n: int) -> int:
    return n >> 20

def mb_to_saveblocks(n: int) -> int:
    return n << 5

def round_half_up(c: float) -> int:
    if c == 0.0:
        return 0

    negative = c < 0
    c = abs(c)

    if c - math.floor(c) < 0.5:
        n = math.floor(c)
    else:
        n = math.ceil(c)

    if negative:
        return -n
    return n

def hours_to_seconds(n: int) -> int:
    return n * 3600

def minutes_to_seconds(n: int) -> int:
    return n * 60
