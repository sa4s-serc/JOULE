from typing import List, Tuple
def weighted_mean_absolute_deviation(numbers: List[Tuple[(float, float)]]) -> float:
    weights = [w for (x, w) in numbers]
    sum_of_weights = sum(weights)
    if (any(((w <= 0) for w in weights)) or (sum_of_weights != 1)):
        return 'Weights must be positive and sum to 1'
    weighted_mean = sum(((x * w) for (x, w) in numbers))
    wmad = (sum(((w * abs((x - weighted_mean))) for (x, w) in numbers)) / sum_of_weights)
    return wmad