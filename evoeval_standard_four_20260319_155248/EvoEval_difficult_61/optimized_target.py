BRACKET_MAP = {'(': ')', '[': ']', '{': '}'}
def correct_bracketing_advanced(brackets: str):
    stack = []
    _stack_append = stack.append
    _stack_pop = stack.pop
    for bracket in brackets:
        if (bracket in BRACKET_MAP):
            _stack_append(bracket)
        else:
            if ((not stack) or (BRACKET_MAP[_stack_pop()] != bracket)):
                return False
    return (not stack)