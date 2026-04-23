# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def cross_product_entry(ui: float, uj: float, uk: float,
                        vi: float, vj: float, vk: float) -> tuple:
    return (uj * vk - vj * uk,
            vi * uk - ui * vk,
            ui * vj - vi * uj)