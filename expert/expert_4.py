def run(numbers):
    sum_weights = 0
    weighted_mean_numerator = 0
    
    for x, w in numbers: # G3 - Combining operations in single loops (instead of 4 we use only 2 loops)
        if w <= 0 or sum_weights >= 1: #G4 - stop the looping when sum_weights is already invalid
            return "Weights must be positive and sum to 1"
        sum_weights += w
        weighted_mean_numerator += x * w
    
    if sum_weights != 1:
        return "Weights must sum to 1"

    weighted_mean = weighted_mean_numerator # Sum weight is 1 (no need to divide)

    wmad_numerator = 0
    deviation_cache = {}

    for x, w in numbers:
        if deviation_cache.get(x) is None: # G18 - Use memoization (kinda)
            deviation_cache[x] = abs(x - weighted_mean) 
        wmad_numerator += w * deviation_cache[x]
    
    return wmad_numerator


weighted_mean_absolute_deviation = run
