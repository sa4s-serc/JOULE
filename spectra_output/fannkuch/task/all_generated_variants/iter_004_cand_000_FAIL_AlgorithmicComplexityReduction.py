# ============================================================
# Iteration: 4
# Operator:  AlgorithmicComplexityReduction
# Status:    FAIL
# Reason:    Function not found in compiled source
# ============================================================

from math import factorial
from itertools import islice


class FenwickTree:
    def __init__(self, size):
        self.tree = [0] * (size + 1)
        self.size = size
        for i in range(1, size + 1):
            self.update(i, 1)

    def update(self, idx, delta):
        while idx <= self.size:
            self.tree[idx] += delta
            idx += idx & (-idx)

    def query(self, idx):
        s = 0
        while idx > 0:
            s += self.tree[idx]
            idx -= idx & (-idx)
        return s

    def find_kth(self, k):
        low = 1
        high = self.size
        ans = -1
        while low <= high:
            mid = (low + high) // 2
            if self.query(mid) >= k:
                ans = mid
                high = mid - 1
            else:
                low = mid + 1
        return ans - 1


def permutations(n, start, size):
    factorials = [1] * (n + 1)
    for i in range(1, n + 1):
        factorials[i] = factorials[i-1] * i

    p = bytearray(n)
    count = byte