def run(brackets: str):
    stack = []
    map_brackets = {"(": ")", "[": "]", "{": "}"}

    for bracket in brackets:
        if bracket in map_brackets:
            stack.append(bracket)
        else:
            # G28 ?? - Avoid calculating the length of the list
            if not stack or map_brackets[stack.pop()] != bracket:
                return False
    # G28 ?? - Avoid calculating the length of the list
    return not stack


correct_bracketing_advanced = run