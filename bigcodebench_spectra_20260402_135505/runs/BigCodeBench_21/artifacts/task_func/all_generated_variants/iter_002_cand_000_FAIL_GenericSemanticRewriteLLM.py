# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=(); expected=dict({'OS': 'Linux', 'Architecture': '64bit', 'Memory Usage': '55.81%'}); actual=dict({'OS': 'Linux', 'Architecture': '64bit', 'Memory Usage': '9.44%'})
# ============================================================

def task_func():
    mem_info = psutil.virtual_memory()
    return {
        'OS': platform.system(),
        'Architecture': platform.architecture()[0],
        'Memory Usage': f'{mem_info.used / mem_info.total * 100:.2f}%'
    }