# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import collections

def correct_bracketing_advanced(brackets: str):
    stack = collections.deque()
    open_to_close = {"(": ")", "[": "]", "{": "}"}
    close_to_open = {")": "(", "]": "[", "}": "{"}

    for char in brackets:
        if char in open_to_close:
            stack.append(char)
        elif char in close_to_open:
            if not stack or stack.pop() != close_to_open[char]:
                return False
        else:
            return False

    return not stack