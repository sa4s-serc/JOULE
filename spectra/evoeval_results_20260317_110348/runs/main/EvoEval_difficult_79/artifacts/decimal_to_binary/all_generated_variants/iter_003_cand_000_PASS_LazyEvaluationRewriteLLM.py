# ============================================================
# Iteration: 3
# Operator:  LazyEvaluationRewriteLLM
# Status:    PASS
# ============================================================

def decimal_to_binary(decimal, padding_length):
    if not isinstance(decimal, int) or not isinstance(padding_length, int) or decimal < 0 or padding_length < 0:
        return "Invalid Input"

    full_binary_str = bin(decimal)
    if len(full_binary_str) - 2 > padding_length:
        return "Padding length is too small"

    binary = full_binary_str[2:]
    binary = binary.zfill(padding_length)

    return "db" + binary + "db"