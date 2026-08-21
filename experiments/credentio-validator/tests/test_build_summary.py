"""Unit tests for adapter.build_summary and multi-manifest aggregation.

Covers review item 3 (build_summary returns the EXACT summarize_c2pa shape and
label strings) and review item 2 (validation_status aggregates across all
manifests, active first). Pure -- no binary required.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from credentio_validator import adapter  # noqa: E402


def _store(validation_status, actions=None, generator="credentio-spike"):
    return {
        "active_manifest": "m1",
        "manifests": {
            "m1": {
                "claim_generator": generator,
                "claim_generator_info": [{"name": generator, "version": "0.1.0"}],
                "label": "m1",
                "assertions": [
                    {"label": "c2pa.actions.v2", "data": {"actions": actions or []}}
                ],
            }
        },
        "validation_status": validation_status,
    }


def test_build_summary_valid_label():
    assert adapter.build_summary(_store([]))["status"] == "Valid"


def test_build_summary_untrusted_label():
    store = _store([{"code": "signingCredential.untrusted"}])
    assert adapter.build_summary(store)["status"] == "Untrusted (Sandbox)"


def test_build_summary_invalid_label_includes_code():
    store = _store([{"code": "signingCredential.invalid"}])
    assert adapter.build_summary(store)["status"] == "Invalid (signingCredential.invalid)"


def test_build_summary_generator_from_info_list():
    assert adapter.build_summary(_store([]))["generator"] == "credentio-spike"


def test_build_summary_action_detail_format():
    actions = [{
        "action": "c2pa.created",
        "description": "made it",
        "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    }]
    summary = adapter.build_summary(_store([], actions=actions))
    assert summary["actions"] == [
        {"label": "c2pa.created", "detail": "c2pa.created: made it (trainedAlgorithmicMedia)"}
    ]


def test_build_summary_has_exact_keys():
    # Shape parity with summarize_c2pa: exactly status/generator/actions.
    assert set(adapter.build_summary(_store([]))) == {"status", "generator", "actions"}


# --- review item 2: multi-manifest validation_status aggregation ---------- #

def _cred_manifest(label, failure_codes):
    return {
        "label": label,
        "claim.v2": {"claim_generator_info": {"name": "g", "version": "1"}},
        "assertions": {},
        "validationResults": {
            "success": [],
            "informational": [],
            "failure": [{"code": c} for c in failure_codes],
        },
    }


def test_validation_status_aggregates_across_manifests():
    crjson = {"manifests": [
        _cred_manifest("active", ["signingCredential.untrusted"]),
        _cred_manifest("ingredient", ["assertion.dataHash.mismatch"]),
    ]}
    store = adapter.to_manifest_store(crjson)
    codes = [s["code"] for s in store["validation_status"]]
    # active manifest's codes come first, then nested/ingredient manifests.
    assert codes == ["signingCredential.untrusted", "assertion.dataHash.mismatch"]
    # A non-untrusted code anywhere makes the overall verdict invalid.
    assert adapter.summarize(store)["status"] == "invalid"


def test_single_manifest_behavior_unchanged():
    crjson = {"manifests": [_cred_manifest("only", ["signingCredential.untrusted"])]}
    store = adapter.to_manifest_store(crjson)
    assert [s["code"] for s in store["validation_status"]] == ["signingCredential.untrusted"]
    assert adapter.summarize(store)["status"] == "untrusted"
