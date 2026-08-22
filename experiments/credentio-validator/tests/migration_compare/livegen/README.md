# livegen — real live-generation drivers + real-asset comparison

Follow-up to the fixture-driven `migration_compare` harness. Where that harness
proves the **comparison methodology** on representative signed fixtures, these
scripts obtain **real, live-generated Google assets** and run the *same*
consumer-schema comparison and a signing-cert-chain inspection on them. This
resolves two open items:

- **comparison-test-result.md** — per-surface: does the *real* asset carry a C2PA
  manifest, and do both validators agree on the consumer schema?
- **trustlist-spike.md Check 2** — read a real Google signing cert chain and
  decide whether `conformance-public` already covers Google or a Google root must
  be added.

> Note: there is no `generate_omni.py` — the Gemini Omni surface was deliberately
> not generated. See `primary/comparison-test-result.md` Addendum A.1.5 for why
> (enterprise Interactions-API-only path + redundant video media type; EM NO-GO).

## Cost discipline

Every paid model was FREE-probed before spend, but the probe lives in two places
depending on the surface:

- **TTS and Lyria** gate the paid call **in-driver**: `generate_gemini_tts.py`
  and `generate_lyria.py` each run a `free_probe()` (TTS `voices:list`; Lyria an
  empty-`instances` predict that 400s iff the model resolves and is authorized)
  and refuse to spend if it fails.
- **Image and Veo** call the paid API **directly** in these drivers; they were
  probed **manually, out-of-band** first via the committed probe scripts
  `test/nano_banana_2_lite_probe.py` (image model resolution) and
  `test/veo_feature_probe.py` (Veo feature/region resolution). The drivers here
  do not re-run that probe inline.

Each surface is generated **exactly once**, cheapest variant, smallest/shortest,
single sample. No product C2PA code is modified — these are
test/analysis/generation-script files only.

## Scripts

| Script | What it does |
|---|---|
| `generate_gemini_image.py` | One image via Vertex `generate_content` (mirrors `test/c2pa/validate_c2pa.py`); model `gemini-2.5-flash-image` (product default `gemini-3-pro-image` is 404 on `ghchinoy-genai-sa` — documented substitution). |
| `generate_gemini_tts.py` | One short LINEAR16 utterance (mirrors `models/gemini_tts.py::synthesize_speech`); cheapest model `gemini-2.5-flash-lite-preview-tts`, via TTS REST. |
| `generate_lyria.py` | One `lyria-002` sample (mirrors `models/lyria.py` predict path), `sampleCount=1`, via Vertex predict REST. |
| `generate_veo.py` | One `veo-3.1-lite-generate-001` clip (mirrors `models/veo.py`), 4s / 720p / 1 video / audio off, generated exactly once, via google-genai (inline bytes, no GCS). |
| `compare_real_asset.py` | Runs BOTH validators on a real asset and diffs on the consumer schema, reusing `consumer_schema.compare` UNCHANGED. Reports NO_MANIFEST as a valid finding. |
| `inspect_cert_chain.py` | Extracts the embedded x5chain, reports leaf/intermediate/root + EKU, and compares the chain against `trust/c2pa_conformance_anchors.pem`. |

The generation drivers replicate the product's request shape but use REST /
`google-genai` directly rather than importing the product modules — the same
transport-agnostic pattern the harness already uses (it calls `c2pa.Reader`
directly rather than importing `services/c2pa_service.py`), so the test tree does
not drag in the product's heavy deps.

## Reproduce

```bash
cd experiments/credentio-validator
export PROJECT_ID=ghchinoy-genai-sa LOCATION=us-central1 GOOGLE_CLOUD_PROJECT=ghchinoy-genai-sa
# needs: c2pa-python==0.37.7, google-genai, cryptography; credentio bin/ + libc++
python tests/migration_compare/livegen/generate_gemini_image.py --out tests/migration_compare/livegen/assets/gemini_image.png
python tests/migration_compare/livegen/compare_real_asset.py --asset tests/migration_compare/livegen/assets/gemini_image.png --title "Gemini Image" --json tests/migration_compare/livegen/gemini_image_result.json
python tests/migration_compare/livegen/inspect_cert_chain.py --asset tests/migration_compare/livegen/assets/gemini_image.png --json tests/migration_compare/livegen/gemini_image_certchain.json
```

## Assets

`assets/gemini_image.png`, `assets/gemini_tts.wav` and `assets/veo.mp4` are
committed (small). `assets/lyria.wav` (~6 MB) is gitignored and mirrored to the
durability mirror under `primary/artifact/...` — its only evidentiary content
("no C2PA manifest") is fully captured in `lyria_result.json`.
