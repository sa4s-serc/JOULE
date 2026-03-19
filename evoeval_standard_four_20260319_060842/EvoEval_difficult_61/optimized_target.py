from collections import deque
_DEFAULT_BRACKET_RULES = {'(': ')', '[': ']', '{': '}'}
def correct_bracketing_advanced(brackets: str):
    stack = deque()
    bracket_map = _DEFAULT_BRACKET_RULES
    _stack_append = stack.append
    _stack_pop = stack.pop
    for bracket in brackets:
        if (bracket in bracket_map):
            _stack_append(bracket)
        else:
            try:
                last_open = _stack_pop()
            except IndexError:
                return False
            if (bracket_map[last_open] != bracket):
                return False
    return (not stack)