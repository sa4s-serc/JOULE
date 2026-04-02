# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=(); expected=dict({'OS': 'Linux', 'Architecture': '64bit', 'Memory Usage': '55.81%'}); actual=dict({'OS': 'Linux', 'Architecture': '64bit', 'Memory Usage': '9.40%'})
# ============================================================

import psutil
import platform

def task_func():
    os_name = platform.system()
    architecture_info = platform.architecture()
    mem_stats = psutil.virtual_memory()

    architecture = architecture_info[0]
    total_memory = mem_stats.total
    used_memory = mem_stats.used

    memory_usage_percentage = (used_memory / total_memory) * 100
    memory_usage_str = f'{memory_usage_percentage:.2f}%'

    return {
        'OS': os_name,
        'Architecture': architecture,
        'Memory Usage': memory_usage_str
    }