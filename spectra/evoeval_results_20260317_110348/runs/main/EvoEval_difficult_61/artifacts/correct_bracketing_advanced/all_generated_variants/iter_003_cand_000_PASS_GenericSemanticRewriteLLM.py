# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def correct_bracketing_advanced(brackets: str):
    stack = []
    opening_to_closing = {"(": ")", "[": "]", "{": "}"}
    closing_to_opening = {v: k for k, v in opening_to_closing.items()}

    for char in brackets:
        if char in opening_to_closing:
            stack.append(char)
        else:  # Must be a closing bracket, assuming valid input characters
            if not stack or stack.pop() != closing_to_opening[char]:
                return False

    return not stack