# credentio-validator (SPIKE / PoC)

A **standalone, read/validate-only C2PA validator** built on Google's
[`credentio`](https://mediaprovenance.googlesource.com/credentio) C++ library,
intended to be cross-usable by the main product and other experiments.

> **This is a spike / proof-of-concept, not production code.** It proves the
> path `build credentio -> invoke the CLI -> parse -> normalize -> compare to
> c2pa-python`. It is standalone: it does **not** modify or wire into the main
> product or `experiments/veo-variations`.

## Status

| Phase | Scope | State |
|---|---|---|
| 1 (GATE) | JPEG vertical slice; normalized store **matches c2pa-python** | done |
| 2 | FastAPI service (`POST /validate`, `GET /healthz`) + Dockerfile | done (service smoke-tested; full Docker build not run here) |
| 3 | Drop-in client with HTTP **and** subprocess transports (identical shapes) | done |
| 4 | Video + audio breadth, genuine untrusted-sandbox path, write-up | done |

The GATE (Phase 1):

> The normalized manifest store produced by the adapter **matches c2pa-python's
> manifest store** for that asset.

### What's here

```
credentio_validator/
  runner.py     # subprocess invocation of the credentio c2pa_validate CLI (fail-soft)
  adapter.py    # credentio crJSON -> c2pa-python-shaped manifest store (the real mapping)
                #   + build_summary(): the exact summarize_c2pa-shaped dict
  client.py     # drop-in surface: validate()/summarize(), HTTP or subprocess transport
  service.py    # FastAPI app wrapping runner+adapter (POST /validate, GET /healthz)
  schema.py     # pydantic request/response models
scripts/
  build_credentio.sh      # clone + Bazel-build //tools:c2pa_validate into bin/
  fetch_testdata.sh       # fetch the real signed fixture into testdata/
  demo.py                 # end-to-end: runner->adapter, then diff vs c2pa-python
  gen_av_fixtures.py      # (re)generate signed video/audio fixtures
  gen_untrusted_fixture.py# (re)generate the untrusted-sandbox fixture
tests/                    # pytest: adapter, runner, build_summary, client, service
testdata/
  CA.jpg                  # real public C2PA-signed JPEG (from contentauth/c2pa-rs)
  signed_v2.jpg           # generated v2-claim JPEG (GATE fixture)
  signed_video.mp4        # generated signed video (format breadth)
  signed_audio.m4a        # generated signed audio (format breadth)
  untrusted_sandbox.jpg   # generated: chains to an untrusted root -> untrusted path
trust/                    # bundled C2PA public trust anchors (claim-signer)
bin/                      # built c2pa_validate binary lands here (gitignored; see bin/PROVENANCE.md)
Dockerfile                # multi-stage: builder (Bazel) + slim runtime service
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

## The client (drop-in surface)

`credentio_validator.client` is what a real call site would import. It has two
functions and two transports, and **both transports return identical shapes**:

```python
from credentio_validator import client

# subprocess transport (no service needed): runs the binary in-process
store   = client.validate("path/to/asset.jpg")      # -> manifest_store dict | None
summary = client.summarize("path/to/asset.jpg")     # -> summarize_c2pa-shaped dict

# HTTP transport: same call, pointed at a running service
store   = client.validate("path/to/asset.jpg", base_url="http://localhost:8000")
summary = client.summarize("path/to/asset.jpg", base_url="http://localhost:8000")
```

Transport selection:

1. explicit `base_url=` argument, else
2. the `CREDENTIO_VALIDATOR_URL` environment variable, else
3. subprocess (run the binary directly).

**Drop-in compatibility.** `validate(asset_uri) -> dict | None` matches
`services/c2pa_service.py::C2PAService.read_manifest` (returns the manifest store,
or `None` for no-manifest / any failure). `summarize(asset_uri) -> dict` matches
`experiments/veo-variations/core/c2pa.py::summarize_c2pa`: on success
`{"status", "generator", "actions": [...]}` with the exact labels `"Valid"`,
`"Untrusted (Sandbox)"`, `"Invalid (<code>)"`; on failure
`{"status": "Error", "error_detail": ..., "actions": [], "generator": "Unknown"}`.
Migrating a call site is a config flag, never a call-site change.

## The service

```bash
make install-service      # fastapi, uvicorn, pydantic, requests
make serve                # uvicorn on :8000  (uses ./bin/c2pa_validate)
```

`POST /validate` with `{"asset_uri": "<local path | http(s):// | gs://>", "summarize": false}`:

* a **valid/untrusted/invalid** asset -> `200`, `ok:true`, `manifest_store`, a
  `validation` block (`valid|untrusted|invalid` + codes), and (if requested) a
  `summary`;
* an asset with **no manifest** -> `200`, `ok:true`, `manifest_store:null`,
  `validation.status:"none"` (a *result*, not an error). `"none"` is a
  spike-added value beyond the design vocabulary (`valid | untrusted | invalid`);
  it is inert to callers, which key off `ok` / `manifest_store`
  (`client.validate()` returns `None` for a no-manifest asset);
* a **genuine fault** (binary missing/crash/timeout, bad URI, `gs://` unwired)
  -> `5xx`, `ok:false`, `error` set. The body still follows the response schema,
  so the client maps it to a sentinel.

`GET /healthz` -> `{"ok", "credentio_version"}`.

### Docker

```bash
make docker               # multi-stage: Bazel builder + slim runtime
```

The runtime stage is slim (compiled binary + trust anchors + FastAPI). The
builder stage compiles credentio and is the expensive part (~27 min, large
download); it mirrors `scripts/build_credentio.sh` but was **not** executed in
the spike env -- see `poc/phase234-build-notes.md`.

## Format breadth & the untrusted path

The adapter is format-agnostic -- it normalizes credentio's crJSON regardless of
media type. Beyond `signed_v2.jpg` (JPEG), the suite includes generated
`signed_video.mp4` and `signed_audio.m4a` fixtures, and `untrusted_sandbox.jpg`,
which is signed by a leaf carrying the C2PA claim-signing EKU
(`1.3.6.1.4.1.62558.2.1`) chaining to a self-signed root that is **not** on the
trust list. credentio reports `signingCredential.untrusted`, which the adapter
maps to status `untrusted` / label `"Untrusted (Sandbox)"`. Regenerate with
`python scripts/gen_av_fixtures.py` and `python scripts/gen_untrusted_fixture.py`
(needs ffmpeg + openssl + c2pa-python).

> **Note (multi-manifest validation_status).** c2pa-python's top-level
> `validation_status` is a flat list that can carry codes from the active
> manifest *and* ingredient/nested manifests. The adapter therefore aggregates
> problem codes across **all** manifests (active first). For single-manifest
> assets -- every fixture here -- this is identical to reading only the active
> manifest, so the gate is unaffected.

## Python version

`pyproject.toml` pins `requires-python = ">=3.14"` to match repo convention, but
this spike was actually developed and tested on **Python 3.11.2** (the toolchain
available in the build env), and nothing here uses a 3.12+ feature. To install
under 3.11, relax the pin locally or use `uv pip install --python 3.11`.

## Testing

```bash
python -m pytest -q       # 38 tests
```

Adapter/build_summary/client-selection/service (no-manifest vs fault) tests run
without the binary; end-to-end tests that need `bin/c2pa_validate` skip cleanly
when it is absent.

## Security / not for production

This is a spike. In particular, the service's `POST /validate` will fetch **any**
`http(s)://` `asset_uri` server-side (`service._resolve_to_local`), with no
allowlist, authentication, size cap, or timeout budget beyond the request
timeout. That is a server-side request forgery (SSRF) surface and is
**intentionally out of scope** here (it mirrors the existing
`C2PAService.read_manifest` download pattern). Before any non-local deployment,
this fetch **must** be gated -- an allowlist of hosts/schemes and/or
authentication, plus request-size/time limits -- or restricted to local paths
and pre-fetched assets only. Likewise, `gs://` resolution is unwired and returns
`501` rather than pulling credentials into the spike.

## Fail-soft

Every failure mode of the CLI (missing binary, non-zero exit, timeout,
unparseable output, missing asset) is caught by `runner.run_validate` and
returned as a `RunnerResult(ok=False, error=...)` -- never raised into the
caller. The client and service preserve this: no transport error, HTTP 5xx, or
timeout is ever raised into the caller -- it becomes `None` / the `Error` dict.
This mirrors the fail-soft contract of the existing call sites.
