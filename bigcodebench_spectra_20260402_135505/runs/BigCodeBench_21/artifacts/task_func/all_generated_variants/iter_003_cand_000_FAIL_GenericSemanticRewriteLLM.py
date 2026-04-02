# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=(); expected=dict({'OS': 'Linux', 'Architecture': '64bit', 'Memory Usage': '55.81%'}); actual=dict({'OS': 'Linux', 'Architecture': '64bit', 'Memory Usage': '9.47%'})
# ============================================================

def task_func():
    mem_stats = psutil.virtual_memory()
    total_memory = mem_stats.total
    used_memory = mem_stats.used
    
    return {
        'OS': platform.system(),
        'Architecture': platform.architecture()[0],
        'Memory Usage': f'{used_memory/total_memory*100:.2f}%'
    }