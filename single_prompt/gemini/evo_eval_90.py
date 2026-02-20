def next_smallest_and_largest(lst):
    if len(lst) < 2:
        return (None, None)

    inf = float('inf')
    neg_inf = float('-inf')
    s1 = s2 = inf
    l1 = l2 = neg_inf

    for num in lst:
        if num < s2:
            if num < s1:
                s2 = s1
                s1 = num
            elif num != s1:
                s2 = num
        
        if num > l2:
            if num > l1:
                l2 = l1
                l1 = num
            elif num != l1:
                l2 = num

    return (s2 if s2 != inf else None, l2 if l2 != neg_inf else None)