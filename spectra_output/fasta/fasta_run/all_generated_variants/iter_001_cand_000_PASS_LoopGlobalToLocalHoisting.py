# ============================================================
# Iteration: 1
# Operator:  LoopGlobalToLocalHoisting
# Status:    PASS
# ============================================================

from bisect import bisect
from itertools import accumulate, chain, zip_longest
from re import sub
_IM = 139968.0
_IA = 3877.0
_IC = 29573.0
_WIDTH = 60
_ALU = sub('\\s+', '', '\nGGCCGGGCGCGGTGGCTCACGCCTGTAATCCCAGCACTTTGGGAGGCCGAGGCGGGCGGA\nTCACCTGAGGTCAGGAGTTCGAGACCAGCCTGGCCAACATGGTGAAACCCCGTCTCTACT\nAAAAATACAAAAATTAGCCGGGCGTGGTGGCGCGCGCCTGTAATCCCAGCTACTCGGGAG\nGCTGAGGCAGGAGAATCGCTTGAACCCGGGAGGCGGAGGTTGCAGTGAGCCGAGATCGCG\nCCACTGCACTCCAGCCTGGGCGACAGAGCGAGACTCCGTCTCAAAAA')
_IUB = list(zip_longest('acgtBDHKMNRSVWY', (0.27, 0.12, 0.12, 0.27), fillvalue=0.02))
_HOMOSAPIENS = list(zip('acgt', (0.302954942668, 0.1979883004921, 0.1975473066391, 0.3015094502008)))

def _probs_and_table(alphabet):
    probs = tuple(accumulate((p * _IM for (_, p) in alphabet)))
    table = bytearray.maketrans(bytes(chain(range(len(alphabet)), [255])), bytes(chain((ord(c) for (c, _) in alphabet), [10])))
    return (probs, table)

def _write_lines(sequence, n, newline=b'\n', table=None):
    out = bytearray()
    i = 0
    while i + _WIDTH <= n:
        out += sequence[i:i + _WIDTH] + newline
        i += _WIDTH
    if i < n:
        out += sequence[i:n] + newline
    return out.translate(table) if table else bytes(out)

def _lcg_indices(seed, count, probs):
    _local_range = range
    vals = bytearray(count)
    for k in _local_range(count):
        seed = (seed * _IA + _IC) % _IM
        vals[k] = bisect(probs, seed)
    return (vals, seed)

def fasta_run(n):
    result = bytearray()
    alu = bytearray(_ALU, 'utf8')
    while len(alu) < n * 2:
        alu.extend(alu)
    result += b'>ONE Homo sapiens alu\n'
    result += _write_lines(alu, n * 2)
    (probs_iub, tbl_iub) = _probs_and_table(_IUB)
    (vals, seed) = _lcg_indices(42.0, n * 3, probs_iub)
    result += b'>TWO IUB ambiguity codes\n'
    result += _write_lines(vals, len(vals), newline=b'\xff', table=tbl_iub)
    (probs_hs, tbl_hs) = _probs_and_table(_HOMOSAPIENS)
    (vals, seed) = _lcg_indices(seed, n * 5, probs_hs)
    result += b'>THREE Homo sapiens frequency\n'
    result += _write_lines(vals, len(vals), newline=b'\xff', table=tbl_hs)
    return bytes(result)