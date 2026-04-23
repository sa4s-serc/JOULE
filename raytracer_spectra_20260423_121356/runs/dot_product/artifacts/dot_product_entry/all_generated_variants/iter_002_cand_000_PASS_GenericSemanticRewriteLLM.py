# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def dot_product_entry(ui: float, uj: float, uk: float,
                      vi: float, vj: float, vk: float) -> float:
    return ui * vi + uj * vj + uk * vk