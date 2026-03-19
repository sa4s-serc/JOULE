def decimal_to_binary(decimal, padding_length):
    if not (isinstance(decimal, int) and decimal >= 0 and
            isinstance(padding_length, int) and padding_length >= 0):
        return "Invalid Input"

    binary_representation = bin(decimal)[2:]

    if len(binary_representation) > padding_length:
        return "Padding length is too small"

    return f"db{binary_representation.zfill(padding_length)}db"