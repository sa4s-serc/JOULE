def run(n: int, startSequence: list, p: int):
    if n < 3:
        return startSequence[n]

    seq1, seq2, seq3 = startSequence

    for i in range(3, n + 1):
        next_value = seq1 + seq2 + seq3 # G1/G2
        if next_value > p:
            return 'Limit Exceeded'
        seq1, seq2, seq3 = seq2, seq3, next_value # Discarding the previous value in the list of 3

    return seq3 # Returning the n (last) value of the list


customFibFib = run