from __future__ import annotations

from joule.models import Tier

from .reduction_list_comp_to_generator import ReductionListCompToGenerator


class SumListComprehensionOperator(ReductionListCompToGenerator):
    name = "sum_generator"
    tier = Tier.L
