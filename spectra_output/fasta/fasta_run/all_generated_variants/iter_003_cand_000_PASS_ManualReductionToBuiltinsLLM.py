# ============================================================
# Iteration: 3
# Operator:  ManualReductionToBuiltinsLLM
# Status:    PASS
# ============================================================

from bisect import bisect
from itertools import accumulate, chain, zip_longest
from re import sub


_IM = 139968.0
_IA = 3877.0
_IC = 29573.0
_WIDTH = 60

_ALU = sub(r'\s+', '', """
GGCCGGGCGCGGTGGCTCACGCCTGTAATCCCAGCACTTTGGGAGGCCGAGGCGGGCGGA
TCACCTGAGGTCAGGAGTTCGAGACCAGCCTGGCCAACATGGTGAAACCCCGTCTCTACT
AAAAATACAAAAATTAGCCGGGCGTGGTGGCGCGCGCCTGTAATCCCAGCTACTCGGGAG
GCTGAGGCAGGAGAATCGCTTGAACCCGGGAGGCGGAGGTTGCAGTGAGCCGAGATCGCG
CCACTGCACTCCAGCCTGGGCGACAGAGCGAGACTCCGTCTCAAAAA""")

_IUB = list(zip_longest('acgtBDHKMNRSVWY', (.27, .12, .12, .27), fillvalue=.02))

_HOMOSAPIENS = list(zip('acgt', (0.3029549426680, 0.1979883004921,
                                  0.1975473066391, 0.3015094502008)))


def _probs_and_table(alphabet):
    probs = tuple(accumulate(p * _IM for _, p in alphabet))
    table = bytearray.maketrans(
        bytes(chain(range(len(alphabet)), [255])),
        bytes(chain((ord(c) for c, _ in alphabet), [10])))
    return probs, table


def _write_lines(sequence, n, newline=b'\n', table=None):
    out = bytearray(b''.join(
        sequence[i:min(i + _WIDTH, n)] + newline
        for i in range(0, n, _WIDTH)
    ))
    return out.translate(table) if table else bytes(out)


def _lcg_indices(seed, count, probs):
    vals = bytearray(count)
    for k in range(count):
        seed = (seed * _IA + _IC) % _IM
        vals[k] = bisect(probs, seed)
    return vals, seed


def fasta_run(n):
    # Section ONE: copy from ALU repeat.
    alu = bytearray(_ALU, 'utf8')
    while len(alu) < n * 2:
        alu.extend(alu)

    # Section TWO: IUB ambiguity codes (random selection).
    probs_iub, tbl_iub = _probs_and_table(_IUB)
    vals_iub, seed = _lcg_indices(42.0, n * 3, probs_iub)

    # Section THREE: Homo sapiens frequency (seed continues from TWO).
    probs_hs, tbl_hs = _probs_and_table(_HOMOSAPIENS)
    vals_hs, seed = _lcg_indices(seed, n * 5, probs_hs)

    parts = [
        b'>ONE Homo sapiens alu\n',
        _write_lines(alu, n * 2),
        b'>TWO IUB ambiguity codes\n',
        _write_lines(vals_iub, len(vals_iub), newline=b'\xff', table=tbl_iub),
        b'>THREE Homo sapiens frequency\n',
        _write_lines(vals_hs, len(vals_hs), newline=b'\xff', table=tbl_hs)
    ]

    return bytes(b''.join(parts))