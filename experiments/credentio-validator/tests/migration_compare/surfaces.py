"""surfaces.py -- the five media surfaces under test.

Each surface names: the product's real generation + C2PA-consumption path, the
media type, the asset used (a representative signed fixture vs a live-cheap
generation) and WHY, and -- for Lyria -- a special comparison strategy.

WHY FIXTURES (stated once, per-surface below too): live generation of every
surface needs GCP project credentials, per-model API enablement (Veo/Omni/Lyria
are allow-listed EAP models), and real spend. The standing cost policy prefers
cheap validation over costly live generation, and this harness proves a
*comparison methodology*, not a generation pipeline. Each surface therefore uses
the real, signed representative fixture shipped with the validator spike
(``testdata/``), which carries a genuine C2PA v2 manifest signed with the c2pa-rs
sandbox cert -- the same manifest shape the product reads at runtime. Where a
cheap live path were trivially available it would be used; none is, in this
container (no GCP creds / EAP access). This is stated, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Surface:
    key: str
    title: str
    media_type: str
    fixture: str                # filename under testdata/
    path_used: str              # "representative fixture" | "live-cheap generation"
    generation_path: str        # product code pointer for real generation
    consumption_path: str       # product code pointer for C2PA read at runtime
    rationale: str              # why this path/fixture
    special: str = ""           # non-empty for Lyria's special comparison


SURFACES: list[Surface] = [
    Surface(
        key="gemini_image",
        title="Gemini Image",
        media_type="image (JPEG)",
        fixture="signed_v2.jpg",
        path_used="representative fixture",
        generation_path="pages/gemini_image_generation.py -> services/c2pa_service.py",
        consumption_path="services/c2pa_service.py::C2PAService.read_manifest "
                         "-> c2pa.Reader(path).json() (fail-soft dict|None)",
        rationale="Image is the load-bearing Content Credentials surface. Live "
                  "generation needs Vertex/GCP creds + image-model access absent "
                  "here; signed_v2.jpg is a real ES256-signed v2-claim JPEG "
                  "carrying the exact manifest shape read_manifest returns.",
    ),
    Surface(
        key="veo",
        title="Veo",
        media_type="video (MP4)",
        fixture="signed_video.mp4",
        path_used="representative fixture",
        generation_path="experiments/veo-variations (Veo generation)",
        consumption_path="experiments/veo-variations/core/c2pa.py::get_c2pa_manifest / "
                         "summarize_c2pa -> c2pa.Reader(video_path).json()",
        rationale="Video surface. Live Veo generation is a paid EAP model needing "
                  "GCP project config absent here; signed_video.mp4 is a real "
                  "C2PA-signed MP4 (BMFF hash) matching what summarize_c2pa reads.",
    ),
    Surface(
        key="omni",
        title="Gemini Omni",
        media_type="video (MP4)",
        fixture="signed_video.mp4",
        path_used="representative fixture",
        generation_path="models/omni.py::generate_omni_video "
                        "(EAP Gemini Omni Flash Interactions API -> video/mp4 in GCS)",
        consumption_path="Omni video is rendered through the same content_credentials "
                         "viewer path as other media; no dedicated c2pa.Reader call in "
                         "models/omni.py (identified by grep: media type is video/mp4).",
        rationale="Grep of models/omni.py + config/omni_models.py shows Omni Flash "
                  "emits video/mp4 (see _save_video_to_gcs, mime_type 'video/mp4'). "
                  "So Omni is a VIDEO surface; it reuses the video fixture. Live "
                  "Omni is an enterprise EAP model (genai.Client(enterprise=True), "
                  "OMNI_PROJECT_ID) unavailable here.",
    ),
    Surface(
        key="lyria",
        title="Lyria",
        media_type="audio (WAV/M4A)",
        fixture="signed_audio.m4a",
        path_used="representative fixture",
        generation_path="models/lyria.py (~181-214): Lyria API response; the "
                        "'content_credentials' output's data is captured as c2pa_data "
                        "and PASSED THROUGH; the audio itself is stored as .wav in GCS.",
        consumption_path="NONE via c2pa-python. models/lyria.py never calls c2pa.Reader "
                         "-- the pre-formed credential blob is handed straight to the "
                         "Lit content_credentials viewer (state/lyria_state.py, "
                         "pages/lyria.py:287-291).",
        rationale="Audio surface. Live Lyria is a paid EAP model needing GCP config "
                  "absent here; signed_audio.m4a is a real C2PA-signed audio asset.",
        special="LYRIA SPECIAL COMPARISON. Today Lyria performs NO validation: it "
                "trusts a pre-formed credential blob from the API and renders it. "
                "credentio's migration value is that it can independently VALIDATE "
                "the signed audio bytes. So the comparison is: (baseline) what the "
                "pass-through path would surface for the asset -- obtained here by "
                "reading the signed audio's embedded manifest with c2pa.Reader, "
                "since the Lyria API embeds a real manifest and the app does no read "
                "of its own -- vs (candidate) credentio validating the SAME signed "
                "audio bytes. The consumer-schema fields (generator, actions) must "
                "agree; credentio additionally produces a real validation_status the "
                "pass-through never had -- reported as an ADDED capability, not a diff.",
    ),
    Surface(
        key="gemini_tts",
        title="Gemini TTS",
        media_type="audio (LINEAR16/WAV)",
        fixture="signed_audio.m4a",
        path_used="representative fixture",
        generation_path="models/gemini_tts.py::synthesize_speech "
                        "(texttospeech, AudioEncoding.LINEAR16 -> raw audio bytes)",
        consumption_path="No dedicated c2pa.Reader call in models/gemini_tts.py "
                         "(grep: returns raw LINEAR16 bytes); audio provenance would "
                         "be read via the same c2pa.Reader path as other audio.",
        rationale="Audio surface. Live Gemini TTS needs GCP TTS creds absent here; "
                  "signed_audio.m4a is a real C2PA-signed audio asset standing in "
                  "for a signed TTS output.",
    ),
]
