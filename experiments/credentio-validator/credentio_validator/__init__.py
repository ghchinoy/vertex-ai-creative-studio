"""credentio-validator: a standalone read/validate-only C2PA validator (spike).

Surface:
  - runner.run_validate(...)  -> invoke the credentio c2pa_validate CLI (fail-soft)
  - adapter.to_manifest_store(...) -> normalize credentio crJSON into the
    c2pa-python-shaped manifest store the existing consumers already parse.
  - adapter.build_summary(...) -> the exact summarize_c2pa-shaped dict.
  - client.validate(...) / client.summarize(...) -> the drop-in call surface,
    selecting the HTTP or subprocess transport (both return identical shapes).

The FastAPI service lives in ``credentio_validator.service`` (imported lazily so
this package stays importable without fastapi installed).
"""

from . import adapter, client, runner

__all__ = ["runner", "adapter", "client"]
