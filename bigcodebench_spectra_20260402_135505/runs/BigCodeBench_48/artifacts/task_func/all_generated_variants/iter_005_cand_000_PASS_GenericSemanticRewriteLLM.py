# ============================================================
# Iteration: 5
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import time
from datetime import datetime
import random
import matplotlib.pyplot as plt

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


import random as _rng_seed; _rng_seed.seed(42)


def task_func(n, output_path=None):
    current_unix_time = int(time.time())
    
    raw_timestamps = [random.randint(0, current_unix_time) for _ in range(n)]
    
    formatted_timestamps = [datetime.utcfromtimestamp(ts).strftime(DATE_FORMAT) for ts in raw_timestamps]

    plt.hist([datetime.utcfromtimestamp(ts) for ts in raw_timestamps])

    if output_path:
        plt.savefig(output_path)
    else:
        plt.show()
    return formatted_timestamps