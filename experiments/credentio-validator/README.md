# credentio-validator (SPIKE / PoC)

A **standalone, read/validate-only C2PA validator** built on Google's
[`credentio`](https://mediaprovenance.googlesource.com/credentio) C++ library,
intended to be cross-usable by the main product and other experiments.

> **This is a spike / proof-of-concept, not production code.** It proves the
> path `build credentio -> invoke the CLI -> parse -> normalize -> compare to
> c2pa-python`. It is standalone: it does **not** modify or wire into the main
> product or `experiments/veo-variations`.

## Status: Phase 1 (GATE) only

Phase 1 builds the vertical slice end-to-end for **one format (JPEG)** against
**one real C2PA-signed fixture**, and proves the gate:

> The normalized manifest store produced by the adapter **matches c2pa-python's
> manifest store** for that asset.

Phases 2-4 (FastAPI service, transport-switching client, multi-format breadth,
write-up) are intentionally **not** built yet -- see `poc/design.md`.

### What's here (Phase 1 subset)

```
credentio_validator/
  __init__.py
  runner.py     # subprocess invocation of the credentio c2pa_validate CLI (fail-soft)
  adapter.py    # credentio crJSON -> c2pa-python-shaped manifest store (the real mapping)
scripts/
  build_credentio.sh   # clone + Bazel-build //tools:c2pa_validate into bin/
  fetch_testdata.sh    # fetch the real signed fixture into testdata/
  demo.py              # end-to-end: runner->adapter, then diff vs c2pa-python
testdata/CA.jpg        # real public C2PA-signed JPEG (from contentauth/c2pa-rs)
trust/                 # bundled C2PA public trust anchors (claim-signer)
bin/                   # built c2pa_validate binary lands here (gitignored; see bin/PROVENANCE.md)
```

## Build & run

```bash
# 1. Build the credentio CLI from source (needs bazelisk + clang + libc++).
make build-credentio          # -> bin/c2pa_validate

# 2. Fetch the signed fixture (already committed; re-fetch if needed).
make testdata

# 3. Install the demo-compare dependency (c2pa-python) and run the demo.
make install
make demo
```

`make demo` runs the credentio path, prints the normalized manifest store, then
reads the same asset with `c2pa-python` and prints the shape diff. Exit code 0
means the gate passes.

## The CLI contract (pinned)

`c2pa_validate` flags (from `tools/asset_validator_main.cc`):

| flag | meaning |
|---|---|
| `--asset=<path>` | asset to validate (**required**) |
| `--claim_signer_trust=<pem>` | claim-signer trust anchors (omit => trust checks skipped) |
| `--tsa_trust=<pem>` | timestamp-authority trust anchors |
| `--output_format=crjson\|txtpb` | output format (default `crjson`) |

We pass the bundled C2PA public trust anchors as `--claim_signer_trust`. Because
the fixture is signed by a sandbox signer that chains to no public trust list,
the validator reports `signingCredential.untrusted` -- the expected
**"untrusted (sandbox)"** success path, not an error.

## Trust anchors

`trust/c2pa_conformance_anchors.pem` is the C2PA public trust list
(`https://contentcredentials.org/trust/anchors.pem`). PoC choice; a production
deployment must decide its authoritative trust source deliberately.

## Fail-soft

Every failure mode of the CLI (missing binary, non-zero exit, timeout,
unparseable output, missing asset) is caught by `runner.run_validate` and
returned as a `RunnerResult(ok=False, error=...)` -- never raised into the
caller. This mirrors the fail-soft contract of the existing call sites.
