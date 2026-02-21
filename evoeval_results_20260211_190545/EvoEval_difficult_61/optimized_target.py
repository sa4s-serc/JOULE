_OPENING_BRACKETS = {'(', '[', '{'}
_BRACKET_PAIRS = {')': '(', ']': '[', '}': '{'}
def correct_bracketing_advanced(brackets: str):
    stack = []
    for bracket in brackets:
        if (bracket in _OPENING_BRACKETS):
            stack.append(bracket)
        else:
            if ((not stack) or (stack.pop() != _BRACKET_PAIRS[bracket])):
                return False
    return (not stack)