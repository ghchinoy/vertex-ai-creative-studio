"""credentio-validator: a standalone read/validate-only C2PA validator (spike).

Phase 1 (GATE) surface:
  - runner.run_validate(...)  -> invoke the credentio c2pa_validate CLI (fail-soft)
  - adapter.to_manifest_store(...) -> normalize credentio crJSON into the
    c2pa-python-shaped manifest store the existing consumers already parse.

The FastAPI service, the transport-switching client, and multi-format breadth
are Phases 2-4 and are intentionally NOT part of this package yet.
"""

from . import adapter, runner

__all__ = ["runner", "adapter"]
