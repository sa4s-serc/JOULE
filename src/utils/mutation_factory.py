"""
Mutation Result Factory

Centralized factory for creating MutationResult objects with consistent
metadata and automatic mutator name detection. Eliminates duplication
across all mutator implementations.
"""

import inspect
import logging
from typing import TYPE_CHECKING

from src.domain.ir import schema
from src.utils.constants import ConfidenceScores, ErrorMessages

if TYPE_CHECKING:
    from src.application.mutators.base import MutationLayer, MutationResult

logger = logging.getLogger(__name__)


class MutationResultFactory:
    """
    Factory for creating MutationResult objects with consistent metadata.

    Provides automatic mutator name detection, confidence validation,
    and standardized result creation across all mutation layers.
    """

    @staticmethod
    def create_result(
        ir: schema.Module,
        strategy_name: str,
        layer: "MutationLayer",
        mutator_name: str = "",
        confidence: float = 1.0,
        description: str = "",
        auto_detect_mutator: bool = True,
    ) -> "MutationResult":
        """
        Create a MutationResult with proper metadata and validation.

        Args:
            ir: The mutated IR module
            strategy_name: Name of the mutation strategy used
            layer: The mutation layer this result belongs to
            mutator_name: Name of the mutator (auto-detected if empty)
            confidence: Confidence score (0.0 to 1.0)
            description: Human-readable description of the change
            auto_detect_mutator: Whether to auto-detect mutator name

        Returns:
            MutationResult with complete metadata

        Raises:
            ValueError: If confidence is outside valid range
        """
        # Validate confidence score
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(ErrorMessages.INVALID_CONFIDENCE.format(score=confidence))

        # Import here to avoid circular dependency
        from src.application.mutators.base import MutationResult

        # Auto-detect mutator name if not provided
        if not mutator_name and auto_detect_mutator:
            mutator_name = MutationResultFactory._detect_mutator_name()

        # Fallback if detection failed
        if not mutator_name:
            mutator_name = "Unknown"

        # Generate description if not provided
        if not description:
            description = MutationResultFactory._generate_description(
                strategy_name, layer, confidence
            )

        return MutationResult(
            ir=ir,
            strategy_name=strategy_name,
            layer=layer,
            mutator_name=mutator_name,
            confidence=confidence,
            description=description,
        )

    @staticmethod
    def _detect_mutator_name() -> str:
        """
        Automatically detect the mutator class name from the call stack.

        Returns:
            Detected mutator class name or empty string if detection fails
        """
        try:
            # Walk up the call stack to find a mutator class
            frame = inspect.currentframe()

            # Look up to 10 frames up (increased from 5 to handle deeper call stacks)
            for _ in range(10):
                if frame and frame.f_back:
                    frame = frame.f_back

                    # Check if 'self' exists in frame locals
                    if "self" in frame.f_locals:
                        caller_self = frame.f_locals["self"]

                        # Check if it's a mutator class
                        if hasattr(caller_self, "__class__"):
                            class_name = caller_self.__class__.__name__

                            # Verify it's likely a mutator (expanded patterns)
                            if any(
                                pattern in class_name
                                for pattern in [
                                    "Mutator",
                                    "Optimizer",
                                    "Transformer",
                                    "Eliminator",
                                    "Reducer",
                                    "Simplifier",
                                ]
                            ):
                                return class_name

                            # Also check if it's a LayeredMutator subclass
                            try:
                                from src.application.mutators.base import \
                                    LayeredMutator

                                if isinstance(caller_self, LayeredMutator):
                                    return class_name
                            except ImportError:
                                pass
                else:
                    break

        except Exception:
            pass

        return ""

    @staticmethod
    def _generate_description(strategy_name: str, layer: "MutationLayer", confidence: float) -> str:
        """
        Generate a human-readable description for the mutation.

        Args:
            strategy_name: Name of the mutation strategy
            layer: The mutation layer
            confidence: Confidence score

        Returns:
            Generated description string
        """
        # Extract readable parts from strategy name
        readable_strategy = strategy_name.replace("_", " ").replace("Optimization", "optimization")

        # Add confidence indicator
        if confidence >= 0.9:
            confidence_desc = "high confidence"
        elif confidence >= 0.7:
            confidence_desc = "medium confidence"
        elif confidence >= 0.5:
            confidence_desc = "low confidence"
        else:
            confidence_desc = "experimental"

        return f"{layer.value.title()} layer {readable_strategy} ({confidence_desc})"

    @staticmethod
    def create_with_confidence_preset(
        ir: schema.Module,
        strategy_name: str,
        layer: "MutationLayer",
        confidence_preset: str = "medium",
        mutator_name: str = "",
        description: str = "",
    ) -> "MutationResult":
        """
        Create result using predefined confidence presets.

        Args:
            ir: The mutated IR module
            strategy_name: Name of the mutation strategy used
            layer: The mutation layer
            confidence_preset: Preset name (high/medium/low/experimental)
            mutator_name: Name of the mutator (auto-detected if empty)
            description: Human-readable description

        Returns:
            MutationResult with preset confidence score
        """
        confidence_map = {"high": 0.9, "medium": 0.75, "low": 0.6, "experimental": 0.4}

        confidence = confidence_map.get(confidence_preset, 0.75)

        return MutationResultFactory.create_result(
            ir=ir,
            strategy_name=strategy_name,
            layer=layer,
            mutator_name=mutator_name,
            confidence=confidence,
            description=description,
        )

    @staticmethod
    def create_for_strategy(
        ir: schema.Module,
        strategy_name: str,
        layer: "MutationLayer",
        mutator_name: str = "",
        description: str = "",
    ) -> "MutationResult":
        """
        Create result with confidence automatically determined by strategy type.

        Args:
            ir: The mutated IR module
            strategy_name: Name of the mutation strategy used
            layer: The mutation layer
            mutator_name: Name of the mutator (auto-detected if empty)
            description: Human-readable description

        Returns:
            MutationResult with strategy-appropriate confidence
        """
        # Determine confidence based on strategy name patterns
        confidence = MutationResultFactory._get_strategy_confidence(strategy_name)

        return MutationResultFactory.create_result(
            ir=ir,
            strategy_name=strategy_name,
            layer=layer,
            mutator_name=mutator_name,
            confidence=confidence,
            description=description,
        )

    @staticmethod
    def _get_strategy_confidence(strategy_name: str) -> float:
        """
        Determine appropriate confidence score based on strategy name.

        Args:
            strategy_name: Name of the mutation strategy

        Returns:
            Appropriate confidence score
        """
        strategy_lower = strategy_name.lower()

        # High confidence strategies (safe transformations)
        if any(
            pattern in strategy_lower
            for pattern in ["constant", "folding", "deadcode", "builtin", "elimination"]
        ):
            return ConfidenceScores.CONSTANT_FOLDING

        # Medium confidence strategies (structural changes)
        elif any(
            pattern in strategy_lower
            for pattern in ["loop", "comprehension", "optimization", "simplification"]
        ):
            return ConfidenceScores.LOOP_OPTIMIZATION

        # Lower confidence strategies (complex transformations)
        elif any(
            pattern in strategy_lower
            for pattern in ["algorithmic", "semantic", "architectural", "intent"]
        ):
            return ConfidenceScores.LLM_SEMANTIC_CHANGE

        # Default medium confidence
        else:
            return ConfidenceScores.ALGORITHMIC_IMPROVEMENT


# Convenience functions for backward compatibility
def create_mutation_result(
    ir: schema.Module,
    strategy_name: str,
    layer: "MutationLayer",
    mutator_name: str = "",
    confidence: float = 1.0,
    description: str = "",
) -> "MutationResult":
    """
    Convenience function for creating mutation results.

    This maintains backward compatibility while using the factory internally.
    """
    return MutationResultFactory.create_result(
        ir=ir,
        strategy_name=strategy_name,
        layer=layer,
        mutator_name=mutator_name,
        confidence=confidence,
        description=description,
    )


def create_result_for_strategy(
    ir: schema.Module,
    strategy_name: str,
    layer: "MutationLayer",
    mutator_name: str = "",
    description: str = "",
) -> "MutationResult":
    """
    Convenience function for creating results with automatic confidence.
    """
    return MutationResultFactory.create_for_strategy(
        ir=ir,
        strategy_name=strategy_name,
        layer=layer,
        mutator_name=mutator_name,
        description=description,
    )
