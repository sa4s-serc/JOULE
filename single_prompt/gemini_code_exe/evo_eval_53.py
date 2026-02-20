def add_elements(list1: list, list2: list, index: int):
    try:
        return (list1[index] + list2[index], False)
    except IndexError:
        return (None, True)