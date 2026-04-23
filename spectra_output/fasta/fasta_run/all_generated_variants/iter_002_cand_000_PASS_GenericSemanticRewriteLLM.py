# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

from bisect import bisect
from itertools import accumulate, chain, zip_longest
from re import sub


_IM = 139968.0
_IA = 3877.0
_IC = 29573.0
_WIDTH = 60

_ALU_STR = sub(r'\s+', '', """
GGCCGGGCGCGGTGGCTCACGCCTGTAATCCCAGCACTTTGGGAGGCCGAGGCGGGCGGA
TCACCTGAGGTCAGGAGTTCGAGACCAGCCTGGCCAACATGGTGAAACCCCGTCTCTACT
AAAAATACAAAAATTAGCCGGGCGTGGTGGCGCGCGCCTGTAATCCCAGCTACTCGGGAG
GCTGAGGCAGGAGAATCGCTTGAACCCGGGAGGCGGAGGTTGCAGTGAGCCGAGATCGCG
CCACTGCACTCCAGCCTGGGCGACAGAGCGAGACTCCGTCTCAAAAA""")

_ALU_BYTEARRAY = bytearray(_ALU_STR, 'utf8')

_IUB_ALPHABET = list(zip_longest('acgtBDHKMNRSVWY', (.27, .12, .12, .27), fillvalue=.02))

_HOMOSAPIENS_ALPHABET = list(zip('acgt', (0.3029549426680, 0.1979883004921,
                                  0.1975473066391, 0.3015094502008)))


def _probs_and_table(alphabet):
    probs = tuple(accumulate(p * _IM for _, p in alphabet))
    table = bytearray.maketrans(
        bytes(chain(range(len(alphabet)), [255])),
        bytes(chain((ord(c) for c, _ in alphabet), [10])))
    return probs, table

_PROBS_IUB, _TBL_IUB = _probs_and_table(_IUB_ALPHABET)
_PROBS_HS, _TBL_HS = _probs_and_table(_HOMOSAPIENS_ALPHABET)


def _write_lines(sequence, n, newline=b'\n', table=None):
    segments = []
    for i in range(0, n, _WIDTH):
        segments.append(sequence[i:min(i + _WIDTH, n)])
        segments.append(newline)
    
    out = b''.join(segments)
    return out.translate(table) if table else out


def _lcg_indices(seed, count, probs):
    vals = bytearray(count)
    for k in range(count):
        seed = (seed * _IA + _IC) % _IM
        vals[k] = bisect(probs, seed)
    return vals, seed


def fasta_run(n):
    parts = []

    alu_copy = bytearray(_ALU_BYTEARRAY)
    while len(alu_copy) < n * 2:
        alu_copy.extend(alu_copy)
    parts.append(b'>ONE Homo sapiens alu\n')
    parts.append(_write_lines(alu_copy, n * 2))

    vals_iub, seed = _lcg_indices(42.0, n * 3, _PROBS_IUB)
    parts.append(b'>TWO IUB ambiguity codes\n')
    parts.append(_write_lines(vals_iub, len(vals_iub), newline=b'\xff', table=_TBL_IUB))

    vals_hs, seed = _lcg_indices(seed, n * 5, _PROBS_HS)
    parts.append(b'>THREE Homo sapiens frequency\n')
    parts.append(_write_lines(vals_hs, len(vals_hs), newline=b'\xff', table=_TBL_HS))

    return b''.join(parts)