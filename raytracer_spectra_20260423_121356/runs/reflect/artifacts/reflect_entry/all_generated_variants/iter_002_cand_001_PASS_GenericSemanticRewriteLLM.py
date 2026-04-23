# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def reflect_entry(vi: float, vj: float, vk: float,
                  ni: float, nj: float, nk: float) -> tuple[float, float, float]:
    dot_val = vi * ni + vj * nj + vk * nk
    scalar_factor = 2 * dot_val
    ri = vi - scalar_factor * ni
    rj = vj - scalar_factor * nj
    rk = vk - scalar_factor * nk
    return (ri, rj, rk)