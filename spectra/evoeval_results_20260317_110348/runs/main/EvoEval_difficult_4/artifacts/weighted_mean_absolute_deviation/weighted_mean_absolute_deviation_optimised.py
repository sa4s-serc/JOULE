from typing import List, Tuple


def weighted_mean_absolute_deviation(numbers: List[Tuple[float, float]]) -> float:
    total_weight = 0.0
    weighted_sum = 0.0
    
    for x, w in numbers:
        if w <= 0:
            return "Weights must be positive and sum to 1"
        total_weight += w
        weighted_sum += x * w

    if total_weight != 1:
        return "Weights must be positive and sum to 1"

    weighted_mean = weighted_sum 

    wmad = 0.0
    for x, w in numbers:
        wmad += w * abs(x - weighted_mean)

    return wmad