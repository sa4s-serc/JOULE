"""
HEDGE - Metrics and Instrumentation

Provides detailed metrics for IR complexity, mutation effectiveness,
and performance profiling.
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from src.domain.ir.schema import Expression, Module, Statement


@dataclass
class IRComplexityMetrics:
    """Metrics describing IR structural complexity."""

    total_nodes: int
    total_statements: int
    total_expressions: int
    max_depth: int
    cyclomatic_complexity: int
    function_count: int
    loop_count: int
    conditional_count: int


class IRMetricsCollector:
    """Collects complexity and structural metrics from IR."""

    def collect(self, module: Module) -> IRComplexityMetrics:
        """
        Analyze IR and collect complexity metrics.

        Args:
            module: The IR module to analyze

        Returns:
            IRComplexityMetrics with structural information
        """
        visitor = MetricsVisitor()
        visitor.visit(module)

        return IRComplexityMetrics(
            total_nodes=visitor.node_count,
            total_statements=visitor.stmt_count,
            total_expressions=visitor.expr_count,
            max_depth=visitor.max_depth,
            cyclomatic_complexity=visitor.cyclomatic,
            function_count=visitor.function_count,
            loop_count=visitor.loop_count,
            conditional_count=visitor.conditional_count,
        )


class MetricsVisitor:
    """Visitor that traverses IR and collects statistics."""

    def __init__(self):
        self.node_count = 0
        self.stmt_count = 0
        self.expr_count = 0
        self.max_depth = 0
        self.cyclomatic = 1  # Base complexity
        self.function_count = 0
        self.loop_count = 0
        self.conditional_count = 0
        self.current_depth = 0

    def visit(self, node, depth=0):
        """Recursively visit IR nodes."""
        if node is None:
            return

        self.node_count += 1
        self.max_depth = max(self.max_depth, depth)

        # Track statement vs expression
        if isinstance(node, Statement):
            self.stmt_count += 1
        elif isinstance(node, Expression):
            self.expr_count += 1

        # Track specific constructs
        from src.domain.ir import schema

        if isinstance(node, schema.FunctionDef):
            self.function_count += 1
        elif isinstance(node, (schema.For, schema.While)):
            self.loop_count += 1
            self.cyclomatic += 1
        elif isinstance(node, schema.If):
            self.conditional_count += 1
            self.cyclomatic += 1

        # Recurse
        if hasattr(node, "__dict__"):
            for value in node.__dict__.values():
                if isinstance(value, list):
                    for item in value:
                        self.visit(item, depth + 1)
                elif hasattr(value, "__dict__"):
                    self.visit(value, depth + 1)


@dataclass
class MutationStatistics:
    """Statistics about mutation effectiveness."""

    total_mutations: int = 0
    successful_mutations: int = 0
    failed_validations: int = 0
    failed_executions: int = 0
    pareto_improvements: int = 0
    cache_hits: int = 0
    proxy_filtered: int = 0  # mutations skipped by EnergyProxyFilter

    # Per-mutator statistics: strategy_name -> {total, valid, improved}
    mutator_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def record_attempt(self, strategy: str):
        if strategy not in self.mutator_stats:
            self.mutator_stats[strategy] = {"total": 0, "valid": 0, "improved": 0}
        self.mutator_stats[strategy]["total"] += 1
        self.total_mutations += 1

    def record_success(self, strategy: str):
        if strategy not in self.mutator_stats:
            self.mutator_stats[strategy] = {"total": 0, "valid": 0, "improved": 0}
        self.mutator_stats[strategy]["valid"] += 1
        self.successful_mutations += 1

    def record_improvement(self, strategy: str):
        if strategy not in self.mutator_stats:
            self.mutator_stats[strategy] = {"total": 0, "valid": 0, "improved": 0}
        self.mutator_stats[strategy]["improved"] += 1
        self.pareto_improvements += 1

    @property
    def success_rate(self) -> float:
        """Percentage of mutations that passed validation."""
        if self.total_mutations == 0:
            return 0.0
        return (self.successful_mutations / self.total_mutations) * 100

    @property
    def improvement_rate(self) -> float:
        """Percentage of successful mutations that improved Pareto front."""
        if self.successful_mutations == 0:
            return 0.0
        return (self.pareto_improvements / self.successful_mutations) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "total_mutations": self.total_mutations,
            "successful_mutations": self.successful_mutations,
            "failed_validations": self.failed_validations,
            "failed_executions": self.failed_executions,
            "pareto_improvements": self.pareto_improvements,
            "cache_hits": self.cache_hits,
            "proxy_filtered": self.proxy_filtered,
            "success_rate": f"{self.success_rate:.2f}%",
            "improvement_rate": f"{self.improvement_rate:.2f}%",
        }
