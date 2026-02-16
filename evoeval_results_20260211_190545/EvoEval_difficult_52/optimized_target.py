def below_above_threshold(l: list, t1: int, t2: int, s: str):
    violating_index = None
    if (s == 'below'):
        violating_index = next((i for (i, num) in enumerate(l) if (num >= t1)), None)
    else:
        if (s == 'above'):
            violating_index = next((i for (i, num) in enumerate(l) if (num <= t2)), None)
        else:
            return -1
    if (violating_index is None):
        return True
    else:
        return violating_index