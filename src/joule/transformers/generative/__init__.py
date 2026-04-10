from __future__ import annotations

from joule.transformers.base import BaseOperator

from .algorithm_complexity_reduction import AlgorithmComplexityReduction
from .bisect_substitution_llm import BisectSubstitutionLLM
from .caching_wrapper import CachingWrapper
from .concurrent_map_delegate_llm import ConcurrentMapDelegateLLM
from .dict_double_hash_elimination_llm import DictDoubleHashEliminationLLM
from .early_exit_optimization import EarlyExitOptimization
from .generator_chain_fusion import GeneratorChainFusion
from .generative_llm_operator import GenerativeLLMOperator
from .generic_semantic_rewrite_llm import GenericSemanticRewriteLLM
from .itertools_delegate_llm import ItertoolsDelegateLLM
from .lazy_evaluation_rewrite_llm import LazyEvaluationRewriteLLM
from .llm_base import LLMTransformationOperator
from .loop_invariant_hoisting_llm import LoopInvariantHoistingLLM
from .loop_membership_indexing_llm import LoopMembershipIndexingLLM
from .manual_reduction_to_builtins_llm import ManualReductionToBuiltinsLLM
from .math_to_bitwise_llm import MathToBitwiseLLM
from .naive_search_to_indexed import NaiveSearchToIndexed
from .recursion_to_dynamic_programming import RecursionToDynamicProgramming
from .regex_precompilation_llm import RegexPrecompilationLLM
from .seen_set_deduplication_llm import SeenSetDeduplicationLLM
from .slots_delegate_llm import SlotsDelegateLLM
from .string_build_buffer_llm import StringBuildBufferLLM
from .try_except_fast_path_llm import TryExceptFastPathLLM
from .vectorization_delegate import VectorizationDelegate


__all__ = [
    "AlgorithmComplexityReduction",
    "BisectSubstitutionLLM",
    "CachingWrapper",
    "ConcurrentMapDelegateLLM",
    "DictDoubleHashEliminationLLM",
    "EarlyExitOptimization",
    "GeneratorChainFusion",
    "GenerativeLLMOperator",
    "GenericSemanticRewriteLLM",
    "ItertoolsDelegateLLM",
    "LLMTransformationOperator",
    "LazyEvaluationRewriteLLM",
    "LoopInvariantHoistingLLM",
    "LoopMembershipIndexingLLM",
    "ManualReductionToBuiltinsLLM",
    "MathToBitwiseLLM",
    "NaiveSearchToIndexed",
    "RecursionToDynamicProgramming",
    "RegexPrecompilationLLM",
    "SeenSetDeduplicationLLM",
    "SlotsDelegateLLM",
    "StringBuildBufferLLM",
    "TryExceptFastPathLLM",
    "VectorizationDelegate",
    "default_llm_operators",
    "escape_llm_operators",
]


def default_llm_operators(model: str) -> list[BaseOperator]:
    return [
        GeneratorChainFusion(model),
        EarlyExitOptimization(model),
        CachingWrapper(model),
        ManualReductionToBuiltinsLLM(model),
        LoopInvariantHoistingLLM(model),
        ItertoolsDelegateLLM(model),
        MathToBitwiseLLM(model),
        LazyEvaluationRewriteLLM(model),
        RegexPrecompilationLLM(model),
        DictDoubleHashEliminationLLM(model),
        TryExceptFastPathLLM(model),
        SlotsDelegateLLM(model),
        ConcurrentMapDelegateLLM(model),
        BisectSubstitutionLLM(model),
        StringBuildBufferLLM(model),
        RecursionToDynamicProgramming(model),
        NaiveSearchToIndexed(model),
        VectorizationDelegate(model),
        AlgorithmComplexityReduction(model),
        LoopMembershipIndexingLLM(model),
        SeenSetDeduplicationLLM(model),
        GenerativeLLMOperator(model),
    ]


def escape_llm_operators(model: str) -> list[BaseOperator]:
    return [GenericSemanticRewriteLLM(model)]
