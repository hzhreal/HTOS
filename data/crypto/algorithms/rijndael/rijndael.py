from tables import S, Si, Rcon, T0, T1, T2, T3, T4, T5, T6, T7, U0, U1, U2, U3

class Rijndael:
    MODE_ECB = 1
    MODE_CBC = 2
    MODE_CTR = 3

    # keysize and blocksize extension
    # https://csrc.nist.gov/csrc/media/projects/cryptographic-standards-and-guidelines/documents/aes-development/rijndael-ammended.pdf#%5B%7B%22num%22%3A127%2C%22gen%22%3A0%7D%2C%7B%22name%22%3A%22FitH%22%7D%2C727%5D
    @staticmethod
    def is_valid_keysize(n: int) -> bool:
        return n & 3 == 0
    @staticmethod
    def is_valid_blocksize(n: int) -> bool:
        return n in (16, 20, 24, 28, 32)

    def __init__(
        self,
        key: bytes | bytearray,
        mode: int,
        block_size: int,
        iv: bytes | bytearray | None = None,
        S: list[int] = S,
        Si: list[int] = Si,
        Rcon: list[int] = Rcon,
        T0: list[int] = T0,
        T1: list[int] = T1,
        T2: list[int] = T2,
        T3: list[int] = T3,
        T4: list[int] = T4,
        T5: list[int] = T5,
        T6: list[int] = T6,
        T7: list[int] = T7,
        U0: list[int] = U0,
        U1: list[int] = U1,
        U2: list[int] = U2,
        U3: list[int] = U3
    ) -> None:
        assert len(S) == 256
        assert len(Si) == 256
        assert len(Rcon) == 30
        assert len(T0) == 256
        assert len(T1) == 256
        assert len(T2) == 256
        assert len(T3) == 256
        assert len(T4) == 256
        assert len(T5) == 256
        assert len(T6) == 256
        assert len(T7) == 256
        assert len(U0) == 256
        assert len(U1) == 256
        assert len(U2) == 256
        assert len(U3) == 256

        kl = len(key)
        if not self.is_valid_keysize(kl):
            raise ValueError("Invalid key size!")
        if not self.is_valid_blocksize(block_size):
            raise ValueError("Invalid block size!")

        match mode:
            case self.MODE_ECB:
                self.encrypt = self.cipher_ecb
                self.decrypt = self.invcipher_ecb
            case self.MODE_CBC:
                assert iv is not None
                if len(iv) != block_size:
                    raise ValueError("IV must be the same size as the block size!")
                self.C_i = iv # C_0; keeping a seperate one for decrypt and encrypt is irrelevant for the data.crypto module
                self.encrypt = self.cipher_cbc
                self.decrypt = self.invcipher_cbc
            case self.MODE_CTR:
                assert iv is not None
                if len(iv) != block_size:
                    raise ValueError("IV must be the same size as the block size!")
                self.ctr = bytearray(iv)
                self.ks = list()
                self.encrypt = self.cipher_ctr
                self.decrypt = self.invcipher_ctr
            case _:
                assert 0
        self.is_streaming = mode == self.MODE_CTR

        Nk = kl // 4 # key columns
        Nb = block_size // 4 # state columns
        Nr = max(Nk, Nb) + 6 # number of rounds
        # for MixColumns
        C1 = {
            4: 1, 5: 1, 6: 1, 7: 1, 8: 1
        }[Nb]
        C2 = {
            4: 2, 5: 2, 6: 2, 7: 2, 8: 3
        }[Nb]
        C3 = {
            4: 3, 5: 3, 6: 3, 7: 4, 8: 4
        }[Nb]

        # key expansion
        # https://csrc.nist.gov/csrc/media/projects/cryptographic-standards-and-guidelines/documents/aes-development/rijndael-ammended.pdf#%5B%7B%22num%22%3A43%2C%22gen%22%3A0%7D%2C%7B%22name%22%3A%22FitH%22%7D%2C561%5D
        W = [0] * (Nb * (Nr + 1))
        for i in range(Nk):
            W[i] = (key[4 * i] << 24) | (key[4 * i + 1] << 16) | (key[4 * i + 2] << 8) | key[4 * i + 3]
        if Nk <= 6:
            for i in range(Nk, Nb * (Nr + 1), 1):
                temp = W[i - 1]
                if i % Nk == 0:
                    # let temp = (a, b, c, d)
                    # then RotByte(temp) = (b, c, d, a)
                    # and SubByte(RotByte(temp)) = (S[b], S[c], S[d], S[a])
                    # we shift b from 15...23 to 0...7
                    # we shift c from 7...15 to 0...7
                    temp = ( \
                            (S[(temp >> 16) & 0xFF] << 24) | \
                            (S[(temp >>  8) & 0xFF] << 16) | \
                            (S[(temp      ) & 0xFF] <<  8) | \
                            (S[(temp >> 24)       ]      )
                           ) ^ Rcon[i // Nk]
                W[i] = W[i - Nk] ^ temp
        else:
            for i in range(Nk, Nb * (Nr + 1), 1):
                temp = W[i - 1]
                if i % Nk == 0:
                    temp = ( \
                            (S[(temp >> 16) & 0xFF] << 24) | \
                            (S[(temp >>  8) & 0xFF] << 16) | \
                            (S[(temp      ) & 0xFF] <<  8) | \
                            (S[(temp >> 24)       ]      )
                           ) ^ Rcon[i // Nk]
                elif i % Nk == 4:
                    temp = ( \
                            (S[(temp >> 24)       ] << 24) | \
                            (S[(temp >> 16) & 0xFF] << 16) | \
                            (S[(temp >>  8) & 0xFF] <<  8) | \
                            (S[(temp      ) & 0xFF]      )
                           )
                W[i] = W[i - Nk] ^ temp

        # key expansion for the inverse cipher
        # https://csrc.nist.gov/csrc/media/projects/cryptographic-standards-and-guidelines/documents/aes-development/rijndael-ammended.pdf#%5B%7B%22num%22%3A61%2C%22gen%22%3A0%7D%2C%7B%22name%22%3A%22FitH%22%7D%2C537%5D
        # apply InvMixColumns to all round keys except first and last
        W_ = W[:]
        for i in range(1, Nr, 1):
            for j in range(Nb):
                a = W_[Nb * i + j]
                W_[Nb * i + j] = U0[(a >> 24)       ] ^ \
                                 U1[(a >> 16) & 0xFF] ^ \
                                 U2[(a >>  8) & 0xFF] ^ \
                                 U3[(a      ) & 0xFF]

        self.bl = block_size
        self.Nk = Nk
        self.Nb = Nb
        self.Nr = Nr
        self.S = S
        self.Si = Si
        # self.Rcon = Rcon
        self.T0 = T0
        self.T1 = T1
        self.T2 = T2
        self.T3 = T3
        self.T4 = T4
        self.T5 = T5
        self.T6 = T6
        self.T7 = T7
        self.U0 = U0
        self.U1 = U1
        self.U2 = U2
        self.U3 = U3
        self.C1 = C1
        self.C2 = C2
        self.C3 = C3
        self.W = W
        self.W_ = W_

    def cipher(self, a: bytearray, p: int) -> None:
        W  = self.W
        S  = self.S
        T0 = self.T0
        T1 = self.T1
        T2 = self.T2
        T3 = self.T3
        C1 = self.C1
        C2 = self.C2
        C3 = self.C3
        Nb = self.Nb
        Nr = self.Nr

        state  = [0] * Nb
        state_ = [0] * Nb
        # prepare state
        for i in range(Nb):
            state[i] = (a[(p + 4 * i)    ] << 24) | \
                       (a[(p + 4 * i) + 1] << 16) | \
                       (a[(p + 4 * i) + 2] <<  8) | \
                       (a[(p + 4 * i) + 3]      )

        # add round key 0
        for i in range(Nb):
            state[i] ^= W[i]

        # rounds
        # https://csrc.nist.gov/csrc/media/projects/cryptographic-standards-and-guidelines/documents/aes-development/rijndael-ammended.pdf#%5B%7B%22num%22%3A52%2C%22gen%22%3A0%7D%2C%7B%22name%22%3A%22FitH%22%7D%2C517%5D
        for r in range(1, Nr, 1):
            # round transformation using T-tables
            # https://csrc.nist.gov/csrc/media/projects/cryptographic-standards-and-guidelines/documents/aes-development/rijndael-ammended.pdf#%5B%7B%22num%22%3A52%2C%22gen%22%3A0%7D%2C%7B%22name%22%3A%22FitH%22%7D%2C517%5D
            # not sure why the column index in the paper is j - C_i
            for j in range(Nb):
                e_j = (T0[(state[(j     )     ] >> 24)       ]) ^ \
                      (T1[(state[(j + C1) % Nb] >> 16) & 0xFF]) ^ \
                      (T2[(state[(j + C2) % Nb] >>  8) & 0xFF]) ^ \
                      (T3[(state[(j + C3) % Nb]      ) & 0xFF]) ^ \
                       W[Nb * r + j]
                state_[j] = e_j
            state, state_ = state_, state
        # final round
        for j in range(Nb):
            c_j = (S[(state[(j     )     ] >> 24)       ] << 24) | \
                  (S[(state[(j + C1) % Nb] >> 16) & 0xFF] << 16) | \
                  (S[(state[(j + C2) % Nb] >>  8) & 0xFF] <<  8) | \
                  (S[(state[(j + C3) % Nb]      ) & 0xFF]      )
            state_[j] = c_j ^ W[Nb * Nr + j]
        state, state_ = state_, state

        # modify plaintext in place
        for i in range(Nb):
            a[(p + 4 * i)    ] = (state[i] >> 24)
            a[(p + 4 * i) + 1] = (state[i] >> 16) & 0xFF
            a[(p + 4 * i) + 2] = (state[i] >>  8) & 0xFF
            a[(p + 4 * i) + 3] = (state[i]      ) & 0xFF

    def invcipher(self, a: bytearray, p: int) -> None:
        # https://csrc.nist.gov/csrc/media/projects/cryptographic-standards-and-guidelines/documents/aes-development/rijndael-ammended.pdf#%5B%7B%22num%22%3A64%2C%22gen%22%3A0%7D%2C%7B%22name%22%3A%22FitH%22%7D%2C537%5D

        W_ = self.W_
        Si = self.Si
        T4 = self.T4
        T5 = self.T5
        T6 = self.T6
        T7 = self.T7
        C1 = self.C1
        C2 = self.C2
        C3 = self.C3
        Nb = self.Nb
        Nr = self.Nr

        state  = [0] * Nb
        state_ = [0] * Nb
        # prepare state
        for i in range(Nb):
            state[i] = (a[(p + 4 * i)    ] << 24) | \
                       (a[(p + 4 * i) + 1] << 16) | \
                       (a[(p + 4 * i) + 2] <<  8) | \
                       (a[(p + 4 * i) + 3]      )

        # add round key Nr
        for i in range(Nb):
            state[i] ^= W_[Nb * Nr + i]

        # rounds
        for r in range(Nr - 1, 0, -1):
            # round transformation using T-tables
            for j in range(Nb):
                e_j = (T4[(state[(j          )     ] >> 24)       ]) ^ \
                      (T5[(state[(j + Nb - C1) % Nb] >> 16) & 0xFF]) ^ \
                      (T6[(state[(j + Nb - C2) % Nb] >>  8) & 0xFF]) ^ \
                      (T7[(state[(j + Nb - C3) % Nb]      ) & 0xFF]) ^ \
                       W_[Nb * r + j]
                state_[j] = e_j
            state, state_ = state_, state
        # final round
        for j in range(Nb):
            c_j = (Si[(state[(j          )     ] >> 24)       ] << 24) | \
                  (Si[(state[(j + Nb - C1) % Nb] >> 16) & 0xFF] << 16) | \
                  (Si[(state[(j + Nb - C2) % Nb] >>  8) & 0xFF] <<  8) | \
                  (Si[(state[(j + Nb - C3) % Nb]      ) & 0xFF]      )
            state_[j] = c_j ^ W_[j]
        state, state_ = state_, state

        # modify plaintext in place
        for i in range(Nb):
            a[(p + 4 * i)    ] = (state[i] >> 24)
            a[(p + 4 * i) + 1] = (state[i] >> 16) & 0xFF
            a[(p + 4 * i) + 2] = (state[i] >>  8) & 0xFF
            a[(p + 4 * i) + 3] = (state[i]      ) & 0xFF

    def cipher_ecb(self, plaintext: bytearray, _: bytearray) -> None:
        assert len(plaintext) % self.bl == 0

        c = self.cipher
        for i in range(0, len(plaintext), self.bl):
            c(plaintext, i)

    def invcipher_ecb(self, ciphertext: bytearray, _: bytearray) -> None:
        assert len(ciphertext) % self.bl == 0

        ic = self.invcipher
        for i in range(0, len(ciphertext), self.bl):
            ic(ciphertext, i)

    def cipher_cbc(self, plaintext: bytearray, _: bytearray) -> None:
        bl = self.bl
        assert len(plaintext) % bl == 0

        c = self.cipher
        for i in range(0, len(plaintext), bl):
            # C_i = c(P_i ^ C_{i-1})
            for j in range(bl):
                plaintext[i + j] ^= self.C_i[j]
            c(plaintext, i)
            self.C_i = plaintext[i:i + bl]

    def invcipher_cbc(self, ciphertext: bytearray, _: bytearray) -> None:
        bl = self.bl
        assert len(ciphertext) % bl == 0

        ic = self.invcipher
        for i in range(0, len(ciphertext), bl):
            # P_i = ic(C_i) ^ C_{i-i}
            C_i = ciphertext[i:i + bl]
            ic(ciphertext, i)
            for j in range(bl):
                ciphertext[i + j] ^= self.C_i[j]
            self.C_i = C_i

    def cipher_ctr(self, plaintext: bytearray, _: bytearray) -> None:
        size = len(plaintext)
        c = self.cipher
        ctr = self.ctr
        ks = self.ks
        bl = self.bl

        # fill keystream with enough bytes for the whole chunk
        while len(ks) < size:
            ctr_ = ctr[:]
            c(ctr_, 0)
            ks.extend(ctr_)
            # increment counter
            for i in range(bl - 1, -1, -1):
                b = ctr[i]
                b += 1
                b &= 0xFF
                ctr[i] = b
                if ctr[i] != 0:
                    break

        for i in range(size):
            plaintext[i] ^= ks[i]
        del ks[:size]

    def invcipher_ctr(self, ciphertext: bytearray, _: bytearray) -> None:
        self.cipher_ctr(ciphertext, _)

