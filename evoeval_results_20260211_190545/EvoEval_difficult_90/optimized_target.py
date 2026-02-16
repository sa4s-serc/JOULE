def next_smallest_and_largest(lst):
    unique_sorted_nums = sorted(set(lst))
    if (len(unique_sorted_nums) < 3):
        return (None, None)
    return (unique_sorted_nums[1], unique_sorted_nums[-2])