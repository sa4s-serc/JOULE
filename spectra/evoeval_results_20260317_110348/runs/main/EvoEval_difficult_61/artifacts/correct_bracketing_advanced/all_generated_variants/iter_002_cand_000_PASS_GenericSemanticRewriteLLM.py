# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import collections

def correct_bracketing_advanced(brackets: str):
    stack = collections.deque()
    opening_to_closing = {"(": ")", "[": "]", "{": "}"}
    closing_to_opening = {v: k for k, v in opening_to_closing.items()}

    for char in brackets:
        if char in opening_to_closing:
            stack.append(char)
        else:
            if not stack or closing_to_opening.get(char) != stack.pop():
                return False
    return not stack