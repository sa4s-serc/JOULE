from __future__ import annotations

from joule.transformers.base import BaseOperator

from .chained_comparison_fusion import ChainedComparisonFusion
from .concat_list_literal_fusion import ConcatListLiteralFusion
from .constant_condition_elision import ConstantConditionElision
from .container_membership_operator import ContainerMembershipOperator
from .counter_substitution import CounterSubstitution
from .data_structure_substitution import ListToSetMembership
from .defaultdict_substitution import DefaultDictSubstitution
from .dict_get_with_default import DictGetWithDefault
from .dict_keys_membership_elision import DictKeysMembershipElision
from .empty_literal import EmptyLiteralOperator
from .enumerate_substitution import EnumerateSubstitution
from .for_loop_to_comprehension import ForLoopToComprehension
from .fstring_conversion import FStringConversion
from .functools_cache_injection import FunctoolsCacheInjection
from .generator_to_yield_from import GeneratorToYieldFrom
from .heap_n_largest_smallest import HeapNLargestSmallest
from .identity_compare_normalization import IdentityCompareNormalization
from .iterator_substitution import IteratorSubstitution
from .join_list_comp_to_generator import JoinListCompToGenerator
from .list_pop_zero_to_deque import ListPopZeroToDeque
from .local_import_hoisting import LocalImportHoisting
from .loop_global_to_local_hoisting import LoopGlobalToLocalHoisting
from .loop_membership_set_cache import LoopMembershipSetCache
from .map_filter_fusion import MapFilterFusion
from .memoization_addition import MemoizationAddition
from .multiple_assignment_fusion import MultipleAssignmentFusion
from .multiple_or_to_set_membership import MultipleOrToSetMembership
from .not_in_normalization import NotInNormalization
from .reduction_list_comp_to_generator import ReductionListCompToGenerator
from .return_bool_simplification import ReturnBoolSimplification
from .seen_set_for_append_dedup import SeenSetForAppendDedup
from .sorted_to_in_place_sort import SortedToInPlaceSort
from .string_concat_to_join import StringConcatToJoin
from .sum_list_comprehension_operator import SumListComprehensionOperator
from .tuple_unpack_in_loop import TupleUnpackInLoop


__all__ = [
    "ChainedComparisonFusion",
    "ConcatListLiteralFusion",
    "ConstantConditionElision",
    "ContainerMembershipOperator",
    "CounterSubstitution",
    "DefaultDictSubstitution",
    "DictGetWithDefault",
    "DictKeysMembershipElision",
    "EmptyLiteralOperator",
    "EnumerateSubstitution",
    "FStringConversion",
    "ForLoopToComprehension",
    "FunctoolsCacheInjection",
    "GeneratorToYieldFrom",
    "HeapNLargestSmallest",
    "IdentityCompareNormalization",
    "IteratorSubstitution",
    "JoinListCompToGenerator",
    "ListPopZeroToDeque",
    "ListToSetMembership",
    "LocalImportHoisting",
    "LoopGlobalToLocalHoisting",
    "LoopMembershipSetCache",
    "MapFilterFusion",
    "MemoizationAddition",
    "MultipleAssignmentFusion",
    "MultipleOrToSetMembership",
    "NotInNormalization",
    "ReductionListCompToGenerator",
    "ReturnBoolSimplification",
    "SeenSetForAppendDedup",
    "SortedToInPlaceSort",
    "StringConcatToJoin",
    "SumListComprehensionOperator",
    "TupleUnpackInLoop",
    "default_deterministic_operators",
]


def default_deterministic_operators() -> list[BaseOperator]:
    return [
        # Tier L — syntactic rewrites (fast, high-confidence)
        ForLoopToComprehension(),
        MapFilterFusion(),
        IteratorSubstitution(),
        ReductionListCompToGenerator(),
        DictKeysMembershipElision(),
        StringConcatToJoin(),
        SortedToInPlaceSort(),
        LocalImportHoisting(),
        JoinListCompToGenerator(),
        GeneratorToYieldFrom(),
        MultipleOrToSetMembership(),
        EnumerateSubstitution(),
        ListPopZeroToDeque(),
        FStringConversion(),
        MultipleAssignmentFusion(),
        LoopGlobalToLocalHoisting(),
        ReturnBoolSimplification(),
        TupleUnpackInLoop(),
        ChainedComparisonFusion(),
        DictGetWithDefault(),
        IdentityCompareNormalization(),
        ConstantConditionElision(),
        NotInNormalization(),
        ConcatListLiteralFusion(),
        ListToSetMembership(),
        EmptyLiteralOperator(),
        SumListComprehensionOperator(),
        ContainerMembershipOperator(),
        # Tier M — semantic rewrites
        FunctoolsCacheInjection(),
        LoopMembershipSetCache(),
        SeenSetForAppendDedup(),
        DefaultDictSubstitution(),
        CounterSubstitution(),
        HeapNLargestSmallest(),
        # Tier H — algorithmic rewrites
        MemoizationAddition(),
    ]
