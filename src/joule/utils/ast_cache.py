"""Shared AST parse cache for joule internals.

Both the smell tagger and the surrogate feature extractor need to call
``ast.parse()`` on the same source strings.  Without coordination they
parse the same source multiple times per candidate evaluation, which adds
measurable overhead for large functions.

This module provides a lightweight, process-wide LRU cache keyed on the
SHA-256 hash of the source string.  Callers should use
``get_parsed_tree()`` instead of calling ``ast.parse()`` directly.

Thread safety: ``functools.lru_cache`` uses a simple lock internally, so
concurrent readers are safe.  Parse results are immutable AST trees, so
sharing them across threads does not require additional synchronisation.
"""

from __future__ import annotations

import ast
import functools
import hashlib

# Maximum number of distinct source strings to keep parsed in memory.
# Each entry holds a full AST tree, which is typically a few hundred KB
# for a large function.  512 entries ≈ a few hundred MB worst-case.
_CACHE_MAXSIZE = 512


@functools.lru_cache(maxsize=_CACHE_MAXSIZE)
def _cached_parse(source_hash: str, source: str) -> ast.Module | None:  # noqa: ARG001
    """Parse *source* and return the AST, or ``None`` on ``SyntaxError``.

    The *source_hash* argument is only used as a cache key; it is not
    passed to ``ast.parse()``.  Using the hash as the primary key avoids
    storing large source strings twice in the LRU cache.
    """
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def source_hash(source: str) -> str:
    """Return the SHA-256 hex digest of *source*."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def get_parsed_tree(source: str) -> tuple[ast.Module | None, list[ast.AST]]:
    """Return ``(tree, nodes)`` for *source*, using the process-wide cache.

    *tree* is ``None`` when *source* has a syntax error, in which case
    *nodes* is an empty list.  Callers should guard against ``None``
    before inspecting the tree.

    Example::

        tree, nodes = get_parsed_tree(source)
        if tree is None:
            return frozenset()
        loops = [n for n in nodes if isinstance(n, ast.For)]
    """
    sh = source_hash(source)
    tree = _cached_parse(sh, source)
    if tree is None:
        return None, []
    return tree, list(ast.walk(tree))


def cache_info() -> functools.lru_cache.cache_info:  # type: ignore[type-arg]
    """Expose the underlying LRU cache statistics (for diagnostics)."""
    return _cached_parse.cache_info()


def cache_clear() -> None:
    """Invalidate the parse cache (useful in tests)."""
    _cached_parse.cache_clear()
