def run(lst):
    if len(lst) < 2:
        return (None, None)

    # No optimization here
    smallest = float('inf')
    second_smallest = float('inf')
    largest = float('-inf')
    second_largest = float('-inf')

    # No optimization here
    for num in lst:
        if num < smallest:
            second_smallest = smallest
            smallest = num
        elif num < second_smallest and num != smallest:
            second_smallest = num

        if num > largest:
            second_largest = largest
            largest = num
        elif num > second_largest and num != largest:
            second_largest = num

    # G4 - Short-circuit
    if second_smallest == float('inf') or second_largest == float('-inf'):
        return (None, None)
    else:
        return (second_smallest, second_largest)


next_smallest_and_largest = run
