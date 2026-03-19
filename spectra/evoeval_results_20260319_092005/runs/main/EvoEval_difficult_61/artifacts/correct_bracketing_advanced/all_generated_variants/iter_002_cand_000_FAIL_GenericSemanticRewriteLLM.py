# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=('a',)
# ============================================================

def correct_bracketing_advanced(brackets: str):
    stack = []
    for bracket in brackets:
        if bracket == '(':
            stack.append('(')
        elif bracket == '[':
            stack.append('[')
        elif bracket == '{':
            stack.append('{')
        elif bracket == ')':
            if not stack or stack.pop() != '(':
                return False
        elif bracket == ']':
            if not stack or stack.pop() != '[':
                return False
        elif bracket == '}':
            if not stack or stack.pop() != '{':
                return False
    return not stack