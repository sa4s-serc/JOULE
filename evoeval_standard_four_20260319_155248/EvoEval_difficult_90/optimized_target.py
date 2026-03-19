def next_smallest_and_largest(lst):
    _inf = float('inf')
    _neg_inf = float('-inf')
    if (len(lst) < 2):
        return (None, None)
    smallest = _inf
    second_smallest = _inf
    largest = _neg_inf
    second_largest = _neg_inf
    for num in lst:
        if (num < smallest):
            second_smallest = smallest
            smallest = num
        else:
            if ((num < second_smallest) and (num != smallest)):
                second_smallest = num
        if (num > largest):
            second_largest = largest
            largest = num
        else:
            if ((num > second_largest) and (num != largest)):
                second_largest = num
    if (second_smallest == _inf):
        second_smallest = None
    if (second_largest == _neg_inf):
        second_largest = None
    return (second_smallest, second_largest)