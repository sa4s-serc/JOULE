def clamp_number(number: float, minimum: float, maximum: float) -> float:
    return minimum if number < minimum else (maximum if number > maximum else number)