"""
Constants and Configuration Values for HEDGE

Centralized location for all magic numbers, strings, and configuration defaults
to improve maintainability and reduce duplication.
"""

from typing import FrozenSet


# === MUTATION CONFIDENCE SCORES ===
class ConfidenceScores:
    """Standard confidence scores for different mutation types."""

    # High confidence (safe transformations)
    CONSTANT_FOLDING = 0.95
    DEAD_CODE_ELIMINATION = 0.90
    BUILTIN_UTILIZATION = 0.85

    # Medium confidence (structural changes)
    LOOP_OPTIMIZATION = 0.80
    COMPREHENSION_OPTIMIZATION = 0.75
    ALGORITHMIC_IMPROVEMENT = 0.70

    # Lower confidence (complex transformations)
    LLM_SEMANTIC_CHANGE = 0.65
    ARCHITECTURAL_REFACTOR = 0.60
    EXPERIMENTAL_OPTIMIZATION = 0.50

    # Minimum acceptable confidence
    MIN_ACCEPTABLE = 0.30


# === RESOURCE LIMITS ===
class ResourceLimits:
    """Resource limits for performance and safety."""

    # Memory limits (MB)
    MAX_MEMORY_USAGE_MB = 2048
    MAX_IR_SIZE_MB = 100

    # Concurrency limits
    MAX_WORKERS = 8
    MAX_CONCURRENT_MUTATIONS = 8

    # Timeout limits (seconds)
    LAYER_TIMEOUT_SECONDS = 30.0
    MUTATION_TIMEOUT_SECONDS = 10.0
    LLM_REQUEST_TIMEOUT_SECONDS = 60.0

    # Batch sizes
    LLM_BATCH_SIZE = 5
    MUTATION_BATCH_SIZE = 10


# === MUTATION LIMITS ===
class MutationLimits:
    """Limits for mutation generation and selection."""

    # Variant limits
    MAX_VARIANTS_PER_LAYER = 5
    MAX_TOTAL_VARIANTS = 20
    MAX_ARCHIVE_SIZE = 50

    # Generation limits
    MAX_GENERATIONS = 10
    DEFAULT_POPULATION_SIZE = 5

    # Retry limits
    MAX_PARSE_RETRIES = 3
    MAX_LLM_RETRIES = 3
    MAX_REPAIR_ATTEMPTS = 2

    # Pruning thresholds
    EARLY_PRUNING_THRESHOLD = 0.3
    DIVERSITY_THRESHOLD = 0.1


# === STANDARD LIBRARY WHITELIST ===
STDLIB_WHITELIST: FrozenSet[str] = frozenset(
    {
        # Core modules
        "math",
        "itertools",
        "functools",
        "collections",
        "heapq",
        "bisect",
        "typing",
        "random",
        "time",
        "datetime",
        "re",
        "sys",
        "os",
        "copy",
        # Data processing
        "statistics",
        "operator",
        "string",
        "json",
        "uuid",
        "pathlib",
        "decimal",
        "fractions",
        "numbers",
        "cmath",
        "array",
        # Language features
        "enum",
        "dataclasses",
        "abc",
        "contextlib",
        "io",
        "struct",
        "codecs",
        # Additional safe modules
        "warnings",
        "logging",
        "inspect",
        "types",
        "weakref",
        "gc",
        "pickle",
        "base64",
        "hashlib",
        "hmac",
        "secrets",
        "tempfile",
    }
)


# === OPTIMIZATION STRATEGIES ===
class OptimizationStrategies:
    """Names for optimization strategies (for consistency)."""

    # Semantic layer
    ALGORITHMIC_INTENT_COMPLEXITY = "AlgorithmicIntent_ComplexityReduction"
    ALGORITHMIC_INTENT_PATTERN = "AlgorithmicIntent_PatternRecognition"
    ALGORITHMIC_INTENT_ARCHITECTURE = "AlgorithmicIntent_ArchitecturalImprovement"
    PROGRAM_INTENT_LOGIC = "ProgramIntent_LogicSimplification"
    PROGRAM_INTENT_FLOW = "ProgramIntent_FlowOptimization"
    PROGRAM_INTENT_PURPOSE = "ProgramIntent_PurposeAlignment"

    # Algorithmic layer
    COMPLEXITY_NESTED_LOOP = "Complexity_NestedLoopReduction"
    COMPLEXITY_SORTING = "Complexity_SortingOptimization"
    COMPLEXITY_DUPLICATE_WORK = "Complexity_DuplicateWorkElimination"
    COMPLEXITY_MATHEMATICAL = "Complexity_MathematicalOptimization"

    # Syntactic layer
    IDIOM_COMPREHENSION = "Idiom_ComprehensionOptimization"
    IDIOM_BUILTIN = "Idiom_BuiltinUtilization"
    IDIOM_ITERATOR = "Idiom_IteratorOptimization"
    IDIOM_CONTEXT_MANAGER = "Idiom_ContextManagerUsage"
    PATTERN_LOOP = "Pattern_LoopOptimization"
    PATTERN_CONDITIONAL = "Pattern_ConditionalSimplification"
    PATTERN_FUNCTION_COMPOSITION = "Pattern_FunctionComposition"
    PATTERN_ERROR_HANDLING = "Pattern_ErrorHandling"

    # Micro layer
    CONSTANT_FOLDING = "Constant_Folding"
    CONSTANT_PROPAGATION = "Constant_Propagation"
    CONSTANT_BOOLEAN = "Constant_BooleanSimplification"
    CONSTANT_ARITHMETIC = "Constant_ArithmeticSimplification"
    DEAD_CODE_UNREACHABLE = "DeadCode_UnreachableElimination"
    DEAD_CODE_UNUSED_VAR = "DeadCode_UnusedVariableElimination"
    DEAD_CODE_PURE_EXPR = "DeadCode_PureExpressionElimination"
    DEAD_CODE_EMPTY_BLOCK = "DeadCode_EmptyBlockElimination"
    LOOP_UNROLLING = "Loop_SmallUnrolling"
    LOOP_STRENGTH_REDUCTION = "Loop_StrengthReduction"
    LOOP_INVARIANT_MOTION = "Loop_InvariantMotion"
    LOOP_BOUNDS_OPTIMIZATION = "Loop_BoundsOptimization"


# === CONFIGURATION PROFILES ===
class ConfigurationProfiles:
    """Predefined configuration profiles to reduce complexity."""

    MICRO = {
        "max_variants_per_layer": 2,
        "max_total_variants": 5,
        "enable_parallel_mutations": False,
        "enable_intelligent_selection": False,
        "enable_batch_llm": False,
        "generations": 3,
        "population_size": 3,
    }

    BASIC = {
        "max_variants_per_layer": 3,
        "max_total_variants": 10,
        "enable_parallel_mutations": False,
        "enable_intelligent_selection": True,
        "enable_batch_llm": True,
        "generations": 5,
        "population_size": 4,
    }

    STANDARD = {
        "max_variants_per_layer": 5,
        "max_total_variants": 20,
        "enable_parallel_mutations": True,
        "enable_intelligent_selection": True,
        "enable_batch_llm": True,
        "generations": 10,
        "population_size": 5,
    }

    ADVANCED = {
        "max_variants_per_layer": 8,
        "max_total_variants": 30,
        "enable_parallel_mutations": True,
        "enable_intelligent_selection": True,
        "enable_batch_llm": True,
        "generations": 15,
        "population_size": 8,
    }

    AGGRESSIVE = {
        "max_variants_per_layer": 12,
        "max_total_variants": 50,
        "enable_parallel_mutations": True,
        "enable_intelligent_selection": True,
        "enable_batch_llm": True,
        "generations": 25,
        "population_size": 12,
    }


# === ERROR MESSAGES ===
class ErrorMessages:
    """Standardized error messages."""

    MUTATION_FAILED = "Mutation failed in {mutator_name}: {error}"
    PARSE_FAILED = "Failed to parse code after {attempts} attempts: {error}"
    IMPORT_REJECTED = "Mutation rejected: unauthorized import '{import_name}'"
    TIMEOUT_EXCEEDED = "Operation timed out after {timeout}s"
    MEMORY_EXCEEDED = "Memory usage exceeded {limit}MB"
    INVALID_CONFIDENCE = "Confidence score {score} is outside valid range [0.0, 1.0]"


# === LOG MESSAGES ===
class LogMessages:
    """Standardized log messages for consistency."""

    ORCHESTRATION_START = "Starting orchestration with {layer_count} layers"
    LAYER_COMPLETE = "Layer {layer} completed: {variant_count} variants, {success_rate:.2%} success rate, {time:.2f}s"
    MUTATION_ATTEMPT = "Attempting {strategy} mutation with {mutator}"
    CACHE_HIT = "LLM cache hit for prompt hash {hash}"
    PRUNING_APPLIED = "Pruned {pruned_count} variants, keeping top {kept_count}"
