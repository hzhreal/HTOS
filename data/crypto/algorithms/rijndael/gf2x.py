from data.crypto.algorithms.rijndael.nat import Nat
from typing import Final, override

# Let $n$ be a nonnegative integer.
# We can write $n$ uniquely in base $2$ as $a_0 + a_1 * 2 + \cdots + a_m * 2$,
# where each $a_0, a_1, \ldots, a_m$ are either $0$ or $1$, and $a_m \neq 0$.
# Now consider the map $a_0 + a_1 * 2 + \cdots + a_m * 2^m \mapsto a_0 + a_1 * x + \cdots + a_m * x^m$.
# This map is a bijection between the set of nonnegative integers and polynomials with binary coefficients.
# We can construct the ring $GF(2)[x]$ of polynomials with binary coefficients by associating the element with a nonnegative integer, a natural number, denoted $Nat$.
# If $f(x)$ is an element of $GF(2)[x]$, then denote the nonnegative integer representation of $f(x)$ as $repr$.
# Since $GF(2)$ is a field, that makes $GF(2)[x]$ an Euclidian domain.
class GF2x:
    def __init__(self, n: Nat) -> None:
        self.repr:   Final[Nat]   = n
        self.degree: Final[int]   = self._get_degree()

    @staticmethod
    def generate_monomial(deg: Nat) -> GF2x:
        # To produce a monomial $x_n$ we can multiply $1$ by $x^n$.
        return GF2x(Nat(1) << deg)

    @staticmethod
    def mul_monomial(monomial: GF2x, other: GF2x) -> GF2x:
        return GF2x(other.repr << Nat(monomial.degree))

    def _get_degree(self) -> int:
        if self.repr == 0:
            return -1
        return int(self.repr).bit_length() - 1

    def __add__(self, other: GF2x, /) -> GF2x:
        # Addition in $GF(2)[x]$ amounts to adding the coefficients of terms with the same degree.
        # Addition of the coefficients amounts to addition in $GF(2)$ which is equivalent to XOR.
        return GF2x(self.repr ^ other.repr)

    def __sub__(self, other: GF2x, /) -> GF2x:
        # Every element is its own inverse.
        # Therefore, $f(x) - g(x) = f(x) + (-(g(x))) = f(x) + g(x)$.
        return self + other

    def __mul__(self, other: GF2x, /) -> GF2x:
        # Let $f(x) = a_0 + \cdots + a_m * x^m$,
        # and let $g(x) = b_0 + \cdots + b_n * x^n$.
        # We want to compute $h(x) = f(x)g(x) = (a_0 + \cdots + a_m * x^m$)(b_0 + \cdots + b_n * x^n)$.
        # If the term $a_i * x^i$ is nonzero, then it is equal to $x^i$.
        # Every product $x^i * (b_j * x^j)$ is equal to either $x^{i + j}$ or $0$.
        # If the product is nonzero we can shift $x^i$ to the left $j$ times.
        # If the product is zero, we can still shift it and the result stays zero.
        # To compute $x^i * g(x)$, we can shift $g(x)$ to the left $i$ times.

        f = self
        g = other
        h = GF2x(Nat(0))

        if f == GF2x(Nat(0)) or g == GF2x(Nat(0)):
            return h

        for i in range(f.degree, -1, -1):
            # Get $x^i$.
            monomial = GF2x.generate_monomial(Nat(i))

            # Is $x^i$ a nonzero term in $f(x)$?
            if f.repr & monomial.repr:
                # Distribute $x^i * g(x)$ in $h$.
                h = h + GF2x.mul_monomial(monomial, g)

        return h

    def __mod__(self, other: GF2x, /) -> GF2x:
        # Let $f(x) = a_0 + \cdots + a_m * x^m$,
        # and let $g(x) = b_0 + \cdots + b_n * x^n$.
        # Since $GF(2)$ is a field, the leading coefficient of every nonzero element in $GF(2)[x]$ is a unit.
        # That is, we can always perform polynomial division in $GF(2)[x]$ as long as the divisor is nonzero.
        # Assume $g(x) \neq 0$, we can write $f(x) = q(x)g(x) + r(x)$ for unique $q(x), r(x)$ with $r(x) = 0$ or $deg r(x) < deg g(x)$.
        # We want to find $r(x)$.
        # If $deg f(x) < deg g(x)$, then $f(x) = 0 * g(x) + f(x)$.

        assert other != GF2x(Nat(0))

        f = self
        g = other

        # This also covers the case $f(x) = 0$.
        if f.degree < g.degree:
            return self

        #      q(x)
        #      ------------------
        # g(x) ) f(x)
        #      ------------------
        #      ...
        #      ------------------
        #      r(x)

        # Start by dividing $a_m * x^m$ by $b_n * x^n$, these are nonzero terms.
        # That is, the division amounts to $x^m$ divided by $x^n$, since $deg f(x) >= deg g(x)$, the result is $x^{m - n}$.
        # Which amounts to the monomial with the degree $m - n$, this is the current rightmost term in $q(x)$, denote this term as $c_q(x)$.

        c_q = GF2x.generate_monomial(Nat(f.degree - g.degree))

        # Now we can compute the remainder.
        r = f - (g * c_q)
        # This is an element of the quotient ring $(GF(2)[x])/(g(x))$.

        # We want the representantive where the degree is strictly less than the degree of $g(x)$.
        # Instead of using $a_m * x^m$ as the dividend, we use the highest degree term in the remainder.
        while r.degree >= g.degree:
            c_q = GF2x.generate_monomial(Nat(r.degree - g.degree))
            r = r - (g * c_q)

        return r

    def __pow__(self, exponent: int, mod: GF2x | None = None, /) -> GF2x:
        # The ring $GF(2)[x]$ can never be a field.
        assert exponent >= 0

        if exponent == 0:
            return GF2x(Nat(1))
        if exponent == 1:
            return self

        # a^5 = a * a * a * a * a
        # f = 1
        # 0: f = f * a = 1 * a = a
        # 1: f = f * a = a * a = a^2
        # 2: f = f * a = a^2 * a = a^3
        # 3: f = f * a = a^3 * a = a^4
        # 4: f = f * a = a^4 * a = a^5

        f = GF2x(Nat(1))
        a = GF2x(self.repr)
        for _ in range(exponent):
            if mod is None:
                f = f * a
            else:
                f = (f * a) % mod
        return f

    @override
    def __hash__(self) -> int:
        return hash(self.repr)

    @override
    def __eq__(self, other: object, /) -> bool:
        if isinstance(other, GF2x):
            return self.repr == other.repr
        return False

    @override
    def __ne__(self, other: object, /) -> bool:
        if isinstance(other, GF2x):
            return self.repr != other.repr
        return False

    @override
    def __repr__(self) -> str:
        terms: list[str] = []
        for i in range(self.degree, -1, -1):
            monomial = GF2x.generate_monomial(Nat(i))
            if self.repr & monomial.repr:
                if i == 0:
                    terms.append("1")
                elif i == 1:
                    terms.append("x")
                else:
                    terms.append(f"x^{{{i}}}")
        if not terms:
            return "0"
        return " + ".join(terms)

# Quotient ring $(GF(2)[x])/(f(x))$.
class GF2x_MOD_f:
    def __init__(self, generator: GF2x, f: GF2x) -> None:
        self.generator: Final[GF2x] = generator
        self.repr:      Final[GF2x] = f % self.generator

    def __add__(self, other: GF2x_MOD_f, /) -> GF2x_MOD_f:
        assert self.generator == other.generator
        return GF2x_MOD_f(self.generator, self.repr + other.repr)

    def __sub__(self, other: GF2x_MOD_f, /) -> GF2x_MOD_f:
        return self + other

    def __mul__(self, other: GF2x_MOD_f, /) -> GF2x_MOD_f:
        assert self.generator == other.generator
        return GF2x_MOD_f(self.generator, self.repr * other.repr)

    def __pow__(self, exponent: int, /) -> GF2x_MOD_f:
        if exponent == 0:
            return GF2x_MOD_f(self.generator, GF2x(Nat(1)))

        f = self.repr
        if exponent < 0:
            assert self != GF2x_MOD_f(self.generator, GF2x(Nat(0)))
            inv = pow(self.repr, 2 ** self.generator.degree - 2, self.generator)
            inv = GF2x_MOD_f(self.generator, inv)
            assert self * inv == GF2x_MOD_f(self.generator, GF2x(Nat(1)))
            f = inv.repr
            exponent = -exponent

        return GF2x_MOD_f(self.generator, pow(f, exponent, self.generator))

    @override
    def __repr__(self) -> str:
        return f"({str(self.repr)}) + ({str(self.generator)})"

    @override
    def __hash__(self) -> int:
        return hash(self.repr)

    @override
    def __eq__(self, other: object, /) -> bool:
        if isinstance(other, GF2x_MOD_f):
            return self.generator == other.generator and self.repr == other.repr
        return False

    @override
    def __ne__(self, other: object, /) -> bool:
        if isinstance(other, GF2x_MOD_f):
            return self.generator != other.generator or self.repr != other.repr
        return False

