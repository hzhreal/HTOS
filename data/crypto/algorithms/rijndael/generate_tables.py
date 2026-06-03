import sys
from os.path import dirname as dn
rootdir = dn(dn(dn(dn(dn(__file__)))))
sys.path.append(rootdir)

from data.crypto.algorithms.rijndael.writer import Writer
from data.crypto.algorithms.rijndael.nat import Nat
from data.crypto.algorithms.rijndael.gf2x import GF2x, GF2x_MOD_f

def main(path: str) -> None:
    writer = Writer(path)

    # x^8 + x^4 + x^3 + x + 1
    g = GF2x(Nat(0b100011011))

    # https://en.wikipedia.org/wiki/Rijndael_S-box
    sbox = [0] * 256
    for a in range(256):
        b = GF2x_MOD_f(g, GF2x(Nat(a)))
        # take the inverse
        if b != GF2x_MOD_f(g, GF2x(Nat(0))):
            b = b ** -1
        # apply transformation
        b = b.repr.repr.n
        s = b ^ \
            circular_left_shift(b, 1) ^ \
            circular_left_shift(b, 2) ^ \
            circular_left_shift(b, 3) ^ \
            circular_left_shift(b, 4) ^ \
            0x63
        sbox[a] = s
    writer.write("S", sbox)

    sbox_inv = [0] * 256
    for s in range(256):
        # apply transformation
        b = circular_left_shift(s, 1) ^ \
            circular_left_shift(s, 3) ^ \
            circular_left_shift(s, 6) ^ \
            0x05
        # take the inverse
        if b != 0:
            b = (GF2x_MOD_f(g, GF2x(Nat(b))) ** -1).repr.repr.n
        sbox_inv[s] = b
    writer.write("Si", sbox_inv)

    # https://en.wikipedia.org/wiki/AES_key_schedule
    rcon = [0] * 30
    x = GF2x_MOD_f(g, GF2x(Nat(0b10)))
    for i in range(1, 30, 1):
        rc_i = (x ** (i - 1)).repr.repr.n
        rcon[i] = construct_word((rc_i, 0, 0, 0))
    writer.write("Rcon", rcon, 6, 8)

    # https://csrc.nist.gov/csrc/media/projects/cryptographic-standards-and-guidelines/documents/aes-development/rijndael-ammended.pdf#%5B%7B%22num%22%3A52%2C%22gen%22%3A0%7D%2C%7B%22name%22%3A%22FitH%22%7D%2C549%5D
    t0 = [0] * 256
    t1 = [0] * 256
    t2 = [0] * 256
    t3 = [0] * 256
    x_ = GF2x_MOD_f(g, GF2x(Nat(0x03))) # x + 1
    for a in range(256):
        S_a = GF2x_MOD_f(g, GF2x(Nat(sbox[a])))
        w = (
            (S_a * x ).repr.repr.n,
             S_a      .repr.repr.n,
             S_a      .repr.repr.n,
            (S_a * x_).repr.repr.n
        )
        t0[a] = construct_word(
            w
        )
        t1[a] = construct_word(
            rot_byte(w, 1)
        )
        t2[a] = construct_word(
            rot_byte(w, 2)
        )
        t3[a] = construct_word(
            rot_byte(w, 3)
        )
    writer.write("T0", t0, 8, 8)
    writer.write("T1", t1, 8, 8)
    writer.write("T2", t2, 8, 8)
    writer.write("T3", t3, 8, 8)

    # tables for the inverse cipher, similar to the previous t-tables
    # the multiplication polynomial for InvMixColumn is given by
    # d(x) = '0B' x^3 + '0D' x^2 + '09' x + '0E' in GF(2^8)[x]/((M(x))
    # we just swap out the MixColumns polynomial with the InverseMixColumns polynomial
    # and generate the tables in the same way
    # https://csrc.nist.gov/csrc/media/projects/cryptographic-standards-and-guidelines/documents/aes-development/rijndael-ammended.pdf#%5B%7B%22num%22%3A19%2C%22gen%22%3A0%7D%2C%7B%22name%22%3A%22FitH%22%7D%2C492%5D
    # 0E 0B 0D 09
    # 09 0E 0B 0D
    # 0D 09 0E 0B
    # 0B 0D 09 0E
    # then T4[a] = (Si[a] * 0E, Si[a] * 09, Si[a] * 0D, Si[a] * 0B) etc
    t4 = [0] * 256
    t5 = [0] * 256
    t6 = [0] * 256
    t7 = [0] * 256
    d_0 = GF2x_MOD_f(g, GF2x(Nat(0x0E)))
    d_1 = GF2x_MOD_f(g, GF2x(Nat(0x09)))
    d_2 = GF2x_MOD_f(g, GF2x(Nat(0x0D)))
    d_3 = GF2x_MOD_f(g, GF2x(Nat(0x0B)))
    for a in range(256):
        Si_a = GF2x_MOD_f(g, GF2x(Nat(sbox_inv[a])))
        w = (
            (Si_a * d_0).repr.repr.n,
            (Si_a * d_1).repr.repr.n,
            (Si_a * d_2).repr.repr.n,
            (Si_a * d_3).repr.repr.n
        )
        t4[a] = construct_word(
            w
        )
        t5[a] = construct_word(
            rot_byte(w, 1)
        )
        t6[a] = construct_word(
            rot_byte(w, 2)
        )
        t7[a] = construct_word(
            rot_byte(w, 3)
        )
    writer.write("T4", t4, 8, 8)
    writer.write("T5", t5, 8, 8)
    writer.write("T6", t6, 8, 8)
    writer.write("T7", t7, 8, 8)

    # InvMixColumn tables
    # recall the polynomial d(x) = '0B' x^3 + '0D' x^2 + '09' x + '0E' in GF(2^8)[x]/(M(x))
    #
    # suppose we have a state column
    # a_0
    # a_1
    # a_2
    # a_3
    #
    # the product of the state column (as a polynomial) and d(x)
    # is b(x) = b_3 x^3 + b_2 x^2 + b_1 x + b_0
    # where
    # b_0 = '0E' * a_0 + '0B' * a_1 + '0D' * a_2 + '09' * a_3
    # b_1 = '09' * a_0 + '0E' * a_1 + '0B' * a_2 + '0D' * a_3
    # b_2 = '0D' * a_0 + '09' * a_1 + '0E' * a_2 + '0B' * a_3
    # b_3 = '0B' * a_0 + '0D' * a_1 + '09' * a_2 + '0E' * a_3
    #
    # we can define tables U_i for each column, e.g.
    # U0[a] = ('0E' * a, '09' * a, '0D' * a, '0B' * a)
    #
    # then consider
    # U0[a_0] ^ U1[a_1] ^ U2[a_2] ^ U3[a_3] =
    # ('0E' * a_0, '09' * a_0, '0D' * a_0, '0B' * a_0) ^
    # ('0B' * a_1, '0E' * a_1, '09' * a_1, '0D' * a_1) ^
    # ('0D' * a_2, '0B' * a_2, '0E' * a_2, '09' * a_2) ^
    # ('09' * a_3, '0D' * a_3, '0B' * a_3, '0E' * a_3)
    # we can interpret this as
    # (
    # '0E' * a_0 + '0B' * a_1 + '0D' * a_2 + '09' * a_3,
    # '09' * a_0 + '0E' * a_1 + '0B' * a_2 + '0D' * a_3,
    # '0D' * a_0 + '09' * a_1 + '0E' * a_2 + '0B' * a_3,
    # '0B' * a_0 + '0D' * a_1 + '09' * a_2 + '0E' * a_3
    # )
    # this is exactly b(x) computed with respect to the state order
    # its the same for a round key
    u0 = [0] * 256
    u1 = [0] * 256
    u2 = [0] * 256
    u3 = [0] * 256
    for a in range(256):
        a_ = GF2x_MOD_f(g, GF2x(Nat(a)))
        w = (
            (a_ * d_0).repr.repr.n,
            (a_ * d_1).repr.repr.n,
            (a_ * d_2).repr.repr.n,
            (a_ * d_3).repr.repr.n
        )
        u0[a] = construct_word(
            w
        )
        u1[a] = construct_word(
            rot_byte(w, 1)
        )
        u2[a] = construct_word(
            rot_byte(w, 2)
        )
        u3[a] = construct_word(
            rot_byte(w, 3)
        )
    writer.write("U0", u0, 8, 8)
    writer.write("U1", u1, 8, 8)
    writer.write("U2", u2, 8, 8)
    writer.write("U3", u3, 8, 8)

    writer.close()

def circular_left_shift(b: int, n: int) -> int:
    # let b = (b_7, ..., b_0) be a byte
    # for n = 1, return (b_6, ..., b_0, b_7)

    for _ in range(n):
        b = ( \
             ((b & 0b01000000) << 1) | \
             ((b & 0b00100000) << 1) | \
             ((b & 0b00010000) << 1) | \
             ((b & 0b00001000) << 1) | \
             ((b & 0b00000100) << 1) | \
             ((b & 0b00000010) << 1) | \
             ((b & 0b00000001) << 1) | \
             (b >> 7) \
            )

    return b

def rot_byte(w: tuple[int, int, int, int], n: int) -> tuple[int, int, int, int]:
    # (a, b, c, d) |-> (d, a, b, c)
    for _ in range(n):
        a = w[0]
        b = w[1]
        c = w[2]
        d = w[3]
        w = (d, a, b, c)
    return w

def construct_word(w: tuple[int, int, int, int]) -> int:
    # let w = (a, b, c, d) be a tuple of bytes
    # return the 32 bit word abcd
    return (w[0] << 24) | (w[1] << 16) | (w[2] << 8) | (w[3] << 0)

if __name__ == "__main__":
    import os
    # tables.py in same directory as this file
    path = os.path.join(os.path.dirname(__file__), "tables.py")
    main(path)

