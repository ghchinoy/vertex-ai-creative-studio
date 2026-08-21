"""Unit tests for adapter.py -- the credentio crJSON -> c2pa-python mapping.

These use static crJSON samples shaped exactly like real ``c2pa_validate``
output (captured during Phase 1), so they run without the binary.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from credentio_validator import adapter  # noqa: E402

# A v2-claim crJSON, shaped like real c2pa_validate --output_format=crjson.
CRJSON_V2 = {
    "@context": ["https://c2pa.org/crjson/crJSON.schema.json"],
    "manifests": [
        {
            "label": "urn:c2pa:abc",
            "isUpdateManifest": False,
            "isCompressedManifest": False,
            "claim.v2": {
                "claim_generator_info": {"name": "credentio-spike", "version": "0.1.0"},
                "instanceID": "xmp.iid:1",
            },
            "assertions": {
                "c2pa.actions.v2": {
                    "actions": [
                        {"action": "c2pa.created",
                         "digitalSourceType": "http://cv.iptc.org/x/trainedAlgorithmicMedia"},
                        {"action": "c2pa.color_adjustments",
                         "parameters": {"name": "brightnesscontrast"}},
                    ]
                },
                "c2pa.hash.data": {"alg": "sha256"},
            },
            "validationResults": {
                "success": [{"code": "claimSignature.validated"}],
                "informational": [],
                "failure": [
                    {"code": "signingCredential.untrusted",
                     "url": "self#jumbf=/c2pa/urn:c2pa:abc/c2pa.signature",
                     "explanation": "signing certificate untrusted"}
                ],
                "validationTime": "2026-08-21T00:00:00+00:00",
            },
        }
    ],
    "jsonGenerator": {"name": "Google C2PA Toolkit", "version": "0.0.1"},
}


def test_active_manifest_is_first():
    store = adapter.to_manifest_store(CRJSON_V2)
    assert store["active_manifest"] == "urn:c2pa:abc"
    assert set(store["manifests"]) == {"urn:c2pa:abc"}


def test_assertions_object_becomes_list_of_label_data():
    store = adapter.to_manifest_store(CRJSON_V2)
    assertions = store["manifests"]["urn:c2pa:abc"]["assertions"]
    assert isinstance(assertions, list)
    labels = {a["label"] for a in assertions}
    assert "c2pa.actions.v2" in labels
    actions = next(a for a in assertions if a["label"] == "c2pa.actions.v2")["data"]["actions"]
    assert actions[0]["action"] == "c2pa.created"
    assert actions[0]["digitalSourceType"].endswith("trainedAlgorithmicMedia")


def test_claim_generator_info_becomes_list():
    store = adapter.to_manifest_store(CRJSON_V2)
    man = store["manifests"]["urn:c2pa:abc"]
    assert man["claim_generator_info"] == [{"name": "credentio-spike", "version": "0.1.0"}]
    assert man["claim_generator"] == "credentio-spike/0.1.0"


def test_validation_status_flattens_problem_codes():
    store = adapter.to_manifest_store(CRJSON_V2)
    codes = [s["code"] for s in store["validation_status"]]
    # success codes are NOT surfaced (matches c2pa-python's validation_status).
    assert codes == ["signingCredential.untrusted"]


def test_summarize_untrusted():
    store = adapter.to_manifest_store(CRJSON_V2)
    assert adapter.summarize(store) == {
        "status": "untrusted",
        "codes": ["signingCredential.untrusted"],
    }


def test_summarize_valid_when_no_codes():
    store = {"validation_status": []}
    assert adapter.summarize(store)["status"] == "valid"


def test_summarize_invalid_on_other_code():
    store = {"validation_status": [{"code": "signingCredential.invalid"}]}
    assert adapter.summarize(store)["status"] == "invalid"


def test_empty_crjson_is_safe():
    store = adapter.to_manifest_store({})
    assert store == {"active_manifest": None, "manifests": {}, "validation_status": []}
