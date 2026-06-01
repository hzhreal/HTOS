from typing import Final, override

class Nat:
    MIN: int = 0
    def __init__(self, n: int) -> None:
        self.check(n)
        self.n: Final[int] = n

    @staticmethod
    def check(n: int) -> None:
        assert n >= Nat.MIN

    def __int__(self) -> int:
        return self.n

    def __add__(self, other: Nat, /) -> Nat:
        return Nat(self.n + other.n)

    def __sub__(self, other: Nat, /) -> Nat:
        k = self.n - other.n
        self.check(k)
        return Nat(k)

    def __xor__(self, other: Nat, /) -> Nat:
        return Nat(self.n ^ other.n)

    def __and__(self, other: Nat, /) -> Nat:
        return Nat(self.n & other.n)

    def __or__(self, other: Nat, /) -> Nat:
        return Nat(self.n | other.n)

    def __rshift__(self, other: Nat, /) -> Nat:
        return Nat(self.n >> other.n)

    def __lshift__(self, other: Nat, /) -> Nat:
        return Nat(self.n << other.n)

    def __bool__(self) -> bool:
        return self.n != 0

    @override
    def __repr__(self) -> str:
        return str(self.n)

    @override
    def __hash__(self) -> int:
        return hash(self.n)

    @override
    def __eq__(self, other: object, /) -> bool:
        if isinstance(other, Nat):
            return self.n == other.n
        if isinstance(other, int):
            return self.n == other
        return False

    @override
    def __ne__(self, other: object, /) -> bool:
        if isinstance(other, Nat):
            return self.n != other.n
        if isinstance(other, int):
            return self.n != other
        return False

