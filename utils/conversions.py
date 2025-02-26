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