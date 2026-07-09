from __future__ import annotations

from importlib import import_module
import json
import os
from textwrap import dedent
from typing import Any, cast

from joule.models import SearchContext, TargetSpec, Tier, TransformationResult, normalize_tier, tier_descriptor


class LLMUnavailableError(RuntimeError):
    pass


# Tier-specific Python optimization heuristics
_TIER_HEURISTICS: dict[str, str] = {
    "L": dedent("""\
        Tier L (syntactic) heuristics — make only local structural changes:
        - Replace `for`-loop accumulations with list/set/dict comprehensions.
        - Replace `x in d.keys()` with `x in d`.
        - Use f-strings instead of `%` or `.format()` string formatting.
        - Replace `sorted(x)[0]` with `min(x)` or `sorted(x)[-1]` with `max(x)`.
        - Use `enumerate()` instead of `range(len(...))`.
        - Replace manual `+=` string accumulation inside loops with `str.join()`.
        - Prefer generator expressions over list comprehensions inside `sum/any/all/min/max`."""),
    "M": dedent("""\
        Tier M (semantic) heuristics — broader semantic rewrites preserving exact behaviour:
        - Replace `defaultdict` boilerplate with direct `collections.defaultdict` usage.
        - Replace `d.get(k, default)` try-except or `if k in d` guards.
        - Use `collections.Counter` for frequency tallying instead of manual dicts.
        - Replace O(n) membership tests on lists with `set` lookups pre-built outside the loop.
        - Cache repeated attribute lookups (`obj.attr`) in a local variable inside a loop.
        - Replace `re.search/match(pattern, ...)` inside a loop with a pre-compiled `re.compile()`.
        - Substitute `heapq.nlargest/nsmallest` for repeated sorting to find top-N elements."""),
    "H": dedent("""\
        Tier H (algorithmic) heuristics — strong restructuring and algorithmic changes:
        - Convert recursive algorithms with overlapping subproblems to dynamic programming.
        - Replace naive O(n²) nested loops with hash-map or bisect-based O(n log n) solutions.
        - Use `itertools` (chain, groupby, islice, product) to eliminate explicit loop overhead.
        - Replace list accumulation + sort with a single `heapq` heap for top-K queries.
        - Use `bisect` module for searching in sorted containers instead of linear scan.
        - Introduce `functools.lru_cache` / `@functools.cache` on pure expensive sub-functions.
        - Replace CPU-bound loops over independent items with `concurrent.futures.ThreadPoolExecutor.map`."""),
}

# Smell-category context hints
_SMELL_HINTS: dict[str, str] = {
    "C1": "Redundant computation detected — look for repeated calculations that can be hoisted or cached.",
    "C2": "Unnecessary call overhead detected — consider inlining or reducing function call nesting.",
    "C3": "Inefficient iteration detected — look for loop rewrites, comprehensions, or `map`/`filter`.",
    "C4": "Inefficient control flow detected — simplify branching, remove bare except, use short-circuit evaluation.",
    "C5": "Suboptimal data structure detected — consider `set`, `dict`, `deque`, or `Counter` where appropriate.",
    "C6": "Unnecessary memory allocation detected — avoid creating containers inside loops, use generators.",
    "C7": "Suboptimal algorithm detected — look for algorithmic complexity improvements (e.g., O(n²) → O(n log n)).",
    "C8": "Missing reuse detected — cache repeated work (memoization, pre-compilation, loop-invariant hoisting).",
    "C9": "I/O access detected — consider buffering, lazy loading, or reducing read/write frequency.",
    "C10": "Underused language primitives — prefer built-in `sum`, `min`, `max`, `any`, `all`, `map`, `zip` over manual loops.",
    "C11": "Concurrency opportunity detected — consider parallelising independent iterations with `ThreadPoolExecutor`.",
    "C12": "Hardware locality issue — avoid strided or non-sequential memory access patterns.",
}


def _build_system_prompt() -> str:
    return dedent("""\
        You are an expert Python performance engineer specialising in energy efficiency, latency, and memory optimisation.
        Your task is to rewrite a Python function to improve its performance.

        STRICT RULES:
        1. Preserve exact functional behaviour — the rewritten function MUST produce identical outputs for all valid inputs.
        2. Do NOT introduce `eval`, `exec`, `compile`, global state, external subprocesses, or filesystem access.
        3. Do NOT add relative imports or wildcard imports.
        4. The rewritten function must appear as the sole function definition in your output module.
        5. You may add import statements at the top level; prefer stdlib over third-party.
        6. Do NOT add property decorators, `global`, or `nonlocal` statements.
        7. Output ONLY valid JSON — no markdown fences, no prose outside the JSON.

        OUTPUT FORMAT (strict JSON object):
        {
          "candidate_source": "<complete Python source including imports and function definition>",
          "reasoning": "<concise explanation of the optimisation applied>",
          "dependencies": ["<module names added, if any>"],
          "proposal_rank": <integer 0-100, lower is better>,
          "feature_hints": {"<key>": <float>}
        }""").strip()


def _build_user_prompt(
    target: TargetSpec,
    context: SearchContext | None,
    *,
    operator_name: str,
    objective: str,
    tier_value: Tier,
    prior_error: str | None = None,
    attempt: int = 0,
) -> str:
    parts: list[str] = []

    # Operator identity
    parts.append(dedent(f"""\
        OPERATOR: {operator_name}
        TIER: {tier_value.value} ({tier_descriptor(tier_value)})
        OBJECTIVE: {objective}"""))

    # Tier-specific guidance
    heuristics = _TIER_HEURISTICS.get(tier_value.value, "")
    if heuristics:
        parts.append(f"TIER GUIDANCE:\n{heuristics}")

    # Smell-category hints from context
    smell_tags: frozenset[str] = frozenset()
    if context is not None:
        raw_smells = context.search_metadata.get("smell_tags")
        if isinstance(raw_smells, (list, set, frozenset)):
            smell_tags = frozenset(str(s) for s in raw_smells)
    if smell_tags:
        smell_hints = [_SMELL_HINTS[tag] for tag in sorted(smell_tags) if tag in _SMELL_HINTS]
        if smell_hints:
            parts.append("DETECTED CODE SMELLS (prioritise addressing these):\n" + "\n".join(f"  - {h}" for h in smell_hints))

    # Search context
    if context is not None:
        rejection_note = ""
        if context.rejection_history:
            rejection_note = f"\nPrior rejection reasons (DO NOT repeat these patterns): {', '.join(context.rejection_history)}"
        parts.append(dedent(f"""\
            SEARCH CONTEXT:
              Parent candidate id: {context.parent_id}
              Applied by operator: {context.parent_operator_name}
              Generation depth: {context.generation_depth}
              Search phase: {context.phase.value}{rejection_note}"""))

    # Prior error feedback on retry
    if prior_error and attempt > 0:
        parts.append(dedent(f"""\
            PREVIOUS ATTEMPT FAILED (attempt {attempt}):
            {prior_error}
            Fix the issue above. Do NOT return the same code as the original."""))

    # Source code
    parts.append(f"SOURCE TO OPTIMISE:\n{target.source}")

    return "\n\n".join(parts)


class LLMClient:
    # Maximum number of retry attempts when LLM output fails validation.
    MAX_RETRIES: int = 2
    # Temperature schedule: index 0 = first attempt, index 1 = first retry, etc.
    TEMPERATURE_SCHEDULE: tuple[float, ...] = (0.0, 0.2, 0.4)

    def __init__(self, model: str) -> None:
        self.model = model

    def generate_transformation(
        self,
        target: TargetSpec,
        context: SearchContext | None = None,
        *,
        operator_name: str = "llm_generative",
        objective: str = "Generate an optimization candidate.",
        operator_tier: Tier | str = Tier.M,
    ) -> TransformationResult:
        tier_value = normalize_tier(operator_tier)
        fake_response = os.getenv("JOULE_FAKE_LLM_RESPONSE")
        if fake_response:
            payload = json.loads(fake_response)
            if isinstance(payload, dict) and operator_name in payload and isinstance(payload[operator_name], dict):
                payload = payload[operator_name]
            return TransformationResult(
                operator_name=operator_name,
                candidate_source=payload.get("candidate_source", target.source),
                reasoning=payload.get("reasoning", "LLM-generated optimization"),
                dependencies=payload.get("dependencies", []),
                operator_family="llm",
                operator_tier=tier_value,
                proposal_rank=int(payload.get("proposal_rank", 0)),
                feature_hints=payload.get("feature_hints", {}),
                metadata={
                    "source": "fake-env",
                    "operator_tier": tier_value.value,
                    "operator_tier_descriptor": tier_descriptor(tier_value),
                    "objective": objective,
                    "context": context.to_record() if context else {},
                },
            )
        if not self.model:
            raise LLMUnavailableError("No LLM model configured. Set [tool.joule].llm_model or JOULE_LLM_MODEL.")
        try:
            completion = cast(Any, import_module("litellm")).completion
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise LLMUnavailableError("litellm is not installed; set JOULE_FAKE_LLM_RESPONSE for tests.") from exc

        system_prompt = _build_system_prompt()
        prior_error: str | None = None
        last_exc: Exception | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            temperature = self.TEMPERATURE_SCHEDULE[min(attempt, len(self.TEMPERATURE_SCHEDULE) - 1)]
            user_prompt = _build_user_prompt(
                target,
                context,
                operator_name=operator_name,
                objective=objective,
                tier_value=tier_value,
                prior_error=prior_error,
                attempt=attempt,
            )
            try:
                response = completion(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content
                payload = json.loads(content)
            except json.JSONDecodeError as exc:
                prior_error = f"Response was not valid JSON: {exc}"
                last_exc = exc
                continue
            except Exception as exc:
                # Non-JSON errors (network, API) should propagate immediately.
                raise RuntimeError(f"LLM API call failed: {exc}") from exc

            candidate_source = payload.get("candidate_source", "")
            if not candidate_source or not candidate_source.strip():
                prior_error = "candidate_source was empty. Provide a complete, optimised Python function."
                last_exc = ValueError(prior_error)
                continue

            # Light structural check: verify it parses before returning.
            try:
                import ast as _ast
                _ast.parse(candidate_source)
            except SyntaxError as exc:
                prior_error = f"candidate_source has a syntax error: {exc.msg} (line {exc.lineno}). Fix the syntax and try again."
                last_exc = exc
                continue

            # Success — return the result.
            return TransformationResult(
                operator_name=operator_name,
                candidate_source=candidate_source,
                reasoning=payload.get("reasoning", "LLM-generated optimization"),
                dependencies=payload.get("dependencies", []),
                operator_family="llm",
                operator_tier=tier_value,
                proposal_rank=int(payload.get("proposal_rank", 0)),
                feature_hints=payload.get("feature_hints", {}),
                metadata={
                    "model": self.model,
                    "objective": objective,
                    "operator_tier": tier_value.value,
                    "operator_tier_descriptor": tier_descriptor(tier_value),
                    "context": context.to_record() if context else {},
                    "llm_attempts": attempt + 1,
                    "llm_temperature": temperature,
                },
            )

        # All retries exhausted — raise the last error.
        raise last_exc or ValueError("LLM generation failed after all retries.")
