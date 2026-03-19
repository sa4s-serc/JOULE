def add_elements(list1: list, list2: list, index: int):
    len1 = len(list1)
    len2 = len(list2)
    if -len1 <= index < len1 and -len2 <= index < len2:
        result = list1[index] + list2[index]
        return (result, False)
    else:
        return (None, True)