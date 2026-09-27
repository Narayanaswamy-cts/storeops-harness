"""Feature modules.

Boundary rules (enforced by `tests/test_boundaries.py`):

1. A module may import `storeops.core.*` and its own package. Nothing else.
2. Cross-module notification goes over the event bus only — importing
   `storeops.modules.alerts` from another module is banned outright.
3. `staff` is read-only to other modules: the single legal cross-module import
   is `storeops.modules.staff.port`, which exposes no mutating operation.
4. Composition happens in `storeops.main`, the only place allowed to import
   more than one module.
"""
