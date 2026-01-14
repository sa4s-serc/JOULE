
def search_element(elements, target):
    """
    Inefficient linear search.
    O(n) complexity.
    HEDGE should optimize this to use 'in' or suggest binary search if sorted.
    """
    found = False
    for i in range(len(elements)):
        if elements[i] == target:
            found = True
            break
            
    # Redundant transformation
    if found:
        return True
    else:
        return False

def contains_all(collection, targets):
    """
    Multiple linear searches.
    """
    results = []
    for t in targets:
        results.append(search_element(collection, t))
    return results
