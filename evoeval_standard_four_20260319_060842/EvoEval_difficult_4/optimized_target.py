from typing import List, Tuple, Union
def weighted_mean_absolute_deviation(numbers: List[Tuple[(float, float)]]) -> Union[(float, str)]:
    sum_xw = 0.0
    sum_weights = 0.0
    for (x, w) in numbers:
        if (w <= 0):
            return 'Weights must be positive and sum to 1'
        sum_xw += (x * w)
        sum_weights += w
    if (sum_weights != 1.0):
        return 'Weights must be positive and sum to 1'
    weighted_mean = sum_xw
    sum_w_abs_diff = 0.0
    for (x, w) in numbers:
        sum_w_abs_diff += (w * abs((x - weighted_mean)))
    wmad = sum_w_abs_diff
    return wmad