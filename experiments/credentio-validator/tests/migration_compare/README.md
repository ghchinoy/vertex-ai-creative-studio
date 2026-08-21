# migration_compare — 5-surface generate-and-compare C2PA test harness

A real, runnable harness that cross-validates the incumbent **`c2pa-python`**
(`c2pa.Reader`) against the candidate **credentio** CLI (via the spike's
`credentio_validator` client) across the five media surfaces this product exposes,
comparing them on the **consumer schema** the product's real call sites read —
not on raw verdict strings.

It exists to answer one question with evidence: *if we ran credentio alongside
`c2pa-python` as a cross-validator (the spike's recommended first step), would the
fields the product actually consumes agree, surface by surface?*

## The five surfaces

| Surface | Media type | Product generation path | C2PA consumption path |
|---|---|---|---|
| Gemini Image | image (JPEG) | `pages/gemini_image_generation.py` | `services/c2pa_service.py::read_manifest` → `c2pa.Reader` |
| Veo | video (MP4) | `experiments/veo-variations` | `experiments/veo-variations/core/c2pa.py::summarize_c2pa` → `c2pa.Reader` |
| Gemini Omni | video (MP4) | `models/omni.py::generate_omni_video` | same content-credentials viewer path (video/mp4) |
| Lyria | audio (WAV/M4A) | `models/lyria.py` (~181-214) | **none via c2pa-python** — pre-formed blob passed through (see special case) |
| Gemini TTS | audio (LINEAR16/WAV) | `models/gemini_tts.py::synthesize_speech` | via the shared `c2pa.Reader` audio path |

Each surface uses a **representative signed fixture** from `../../testdata/` (real
C2PA v2 manifests). Live generation of every surface needs GCP project
credentials, per-model EAP access, and real spend — unavailable in the harness
container and against the standing cost policy — so fixtures are used and this is
stated per surface in the output. See `surfaces.py` for the exact rationale.

### Lyria is special

Today Lyria performs **no validation**: `models/lyria.py` captures a pre-formed
`content_credentials` blob from the Lyria API and hands it straight to the viewer
(no `c2pa.Reader`). credentio's migration value is that it can **independently
validate the signed audio bytes**. The harness therefore compares the pass-through
baseline (obtained by reading the signed audio's embedded manifest, since the API
embeds a real manifest and the app reads none of its own) against credentio
validating the same bytes — and reports that credentio *adds* a real
`validation_status` the current path never had.

## The comparison (consumer schema)

Both validators emit a `c2pa-python`-shaped `manifest_store`. `consumer_schema.py`
projects each to exactly the fields the product consumes:

- `has_active_manifest`, `active_manifest_present_in_map`
- `generator_info`: `[{name, version}]`
- `actions`: the `c2pa.actions[.v2]` list, each `{action, digitalSourceType}`
- `validation_status_is_list` (shape — not the raw codes)

**Pass/fail rule (explicit in code):** a surface PASSES when every consumed field
is equal across the two validators, *after removing differences fully explained by
a documented expected-divergence*; it FAILS when a consumed field differs
unexpectedly. Documented expected-divergences (from `spike-result.md`), each
detected and printed, never silently swallowed:

- **D1 EXTRA_RAW_ASSERTIONS** — credentio carries raw assertions (`c2pa.hash.*`,
  thumbnails) `c2pa-python` filters. Outside consumed fields.
- **D2 STRICTER_VERDICT** — credentio `signingCredential.invalid` where
  `c2pa-python` says `signingCredential.untrusted`. In codes (outside consumed
  fields — we compare list shape).
- **D3 V1_CLAIM_UNSUPPORTED** — on a legacy v1-claim asset credentio reports
  `com.google.unsupportedSpecVersion` and drops generator/actions. This *does*
  land in consumed fields, so the diff is reclassified as this expected-divergence
  (with the dropped values shown), not a failure.

## How to run

Prerequisites:
- `bin/c2pa_validate` present in `experiments/credentio-validator/bin/` — copy the
  spike's pre-built x86_64 binary, or run `scripts/build_credentio.sh` (~27 min).
- libc++ runtime for the binary. On Debian/Ubuntu:
  `apt-get install -y libc++1-14 libc++abi1-14 libunwind-14`.
- `c2pa-python==0.37.7` (the product's pin).

```bash
cd experiments/credentio-validator
pip install .              # pulls c2pa-python (a base dep); or: pip install c2pa-python==0.37.7
python -m tests.migration_compare.run_migration_compare
# optional machine-readable report:
python -m tests.migration_compare.run_migration_compare --json results.json
# one surface only:
python -m tests.migration_compare.run_migration_compare --only lyria
```

Exit code is 0 iff all five surfaces PASS.

Unit tests for the pass/fail rule (identical → PASS, unexpected divergence →
FAIL, D1/D2/D3 handling):

```bash
pytest tests/migration_compare/test_consumer_schema.py
```

## Files

- `consumer_schema.py` — projection, diff, expected-divergence detection, pass/fail rule.
- `surfaces.py` — the five surface descriptors (media type, fixture, path, rationale).
- `run_migration_compare.py` — the runner (validates with both, projects, diffs, reports).
- `test_consumer_schema.py` — unit tests for the comparison core.
