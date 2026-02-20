def next_smallest_and_largest(lst):
    if len(lst) < 2:
        return (None, None)

    inf = float('inf')
    ninf = float('-inf')
    min1 = min2 = inf
    max1 = max2 = ninf

    for num in lst:
        if num < min2:
            if num < min1:
                min2 = min1
                min1 = num
            elif num > min1:
                min2 = num
        
        if num > max2:
            if num > max1:
                max2 = max1
                max1 = num
            elif num < max1:
                max2 = num

    return (min2 if min2 != inf else None, max2 if max2 != ninf else None)