# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def decimal_to_binary(decimal, padding_length):
    if not isinstance(decimal, int) or not isinstance(padding_length, int) or decimal < 0 or padding_length < 0:
        return "Invalid Input"

    binary_str = format(decimal, 'b')
    
    if len(binary_str) > padding_length:
        return "Padding length is too small"

    padded_binary = binary_str.zfill(padding_length)

    return f"db{padded_binary}db"