# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import numpy as np

def task_func(l1, l2, THRESHOLD = 0.5):
    arr1 = np.array(l1, dtype=float)
    arr2 = np.array(l2, dtype=float)

    if not arr1.size and not arr2.size:
        combined_np = np.array([], dtype=float)
    else:
        max_len = max(arr1.size, arr2.size)
        padded_arr1 = np.pad(arr1, (0, max_len - arr1.size), mode='constant', constant_values=np.nan)
        padded_arr2 = np.pad(arr2, (0, max_len - arr2.size), mode='constant', constant_values=np.nan)

        stacked = np.stack((padded_arr1, padded_arr2))
        interleaved = stacked.flatten(order='F')
        combined_np = interleaved[~np.isnan(interleaved)]

    differences = np.abs(combined_np - THRESHOLD)
    closest_index = np.argmin(differences)
    return combined_np[closest_index]