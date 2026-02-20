from typing import List, Tuple

def weighted_mean_absolute_deviation(numbers: List[Tuple[float, float]]) -> float:
    """
    Calculate the weighted mean absolute deviation (WMAD) of a list of numbers.

    The input is a list of tuples, where each tuple contains a number and its corresponding weight.
    Weights must be positive and sum to 1.

    :param numbers: A list of tuples, where each tuple contains a number and its weight.
                    For example: [(number1, weight1), (number2, weight2), ...]
    :type numbers: List[Tuple[float, float]]
    :raises TypeError: if the input is not a list of tuples
    :raises TypeError: if the number of weights are not same as the number of elements
    :raises TypeError: if the inputs are not all floats
    :raises ValueError: if any of the weights are non-positive
    :raises ValueError: if the weights do not sum to 1
    :rtype: float
    :return: The weighted mean absolute deviation.
    """

    weight_sum = 0.0
    weighted_sum = 0.0

    # Optimization: Cache global abs lookup
    local_abs = abs

    for x, w in numbers:
        if w <= 0:
            return "Weights must be positive and sum to 1"
        weight_sum += w
        weighted_sum += x * w

    if weight_sum != 1:
        return "Weights must be positive and sum to 1"

    wmad = 0.0
    
    for x, w in numbers:
        wmad += w * local_abs(x - weighted_sum)

    return wmad