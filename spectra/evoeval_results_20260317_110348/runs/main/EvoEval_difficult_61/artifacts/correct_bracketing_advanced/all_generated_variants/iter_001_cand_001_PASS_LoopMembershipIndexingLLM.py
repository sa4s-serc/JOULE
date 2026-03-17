# ============================================================
# Iteration: 1
# Operator:  LoopMembershipIndexingLLM
# Status:    PASS
# ============================================================

def correct_bracketing_advanced(brackets: str):
    stack = []
    bracket_map = {"(": ")", "[": "]", "{": "}"}
    opening_brackets = set(bracket_map.keys())

    for bracket in brackets:
        if bracket in opening_brackets:
            stack.append(bracket)
        elif len(stack) == 0 or bracket_map[stack.pop()] != bracket:
            return False

    return len(stack) == 0