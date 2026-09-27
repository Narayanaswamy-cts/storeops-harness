"""Cross-cutting primitives shared by every module.

`core` must never import from `storeops.modules.*` — that one rule is what keeps
the module graph acyclic. See `tests/test_boundaries.py`.
"""
