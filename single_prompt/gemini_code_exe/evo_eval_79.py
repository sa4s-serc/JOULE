def decimal_to_binary(decimal, padding_length):
    if not isinstance(decimal, int) or not isinstance(padding_length, int) or decimal < 0 or padding_length < 0:
        return "Invalid Input"

    if (decimal.bit_length() or 1) > padding_length:
        return "Padding length is too small"

    return f"db{decimal:0{padding_length}b}db"