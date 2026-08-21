"""Unit tests for the consumer-schema comparison core + pass/fail rule.

These prove the pass/fail machinery is real: identical consumed fields PASS, an
unexpected consumed-field divergence FAILS, and each documented expected-divergence
(D1 extra raw assertions, D2 stricter verdict, D3 v1-claim gap) is detected and
handled per the rule in consumer_schema.py -- D1/D2 never fail (outside consumed
fields), D3 reclassifies the consumed-field diff it causes rather than failing.

Run:  pytest tests/migration_compare/test_consumer_schema.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import consumer_schema as cs  # noqa: E402


def _store(*, active="urn:x", gen=("credentio-spike", "0.1.0"),
           actions=(("c2pa.created", "http://.../trainedAlgorithmicMedia"),),
           codes=("signingCredential.untrusted",),
           extra_labels=()):
    assertions = [{
        "label": "c2pa.actions.v2",
        "data": {"actions": [{"action": a, "digitalSourceType": d} for a, d in actions]},
    }]
    for lbl in extra_labels:
        assertions.append({"label": lbl, "data": {}})
    manifest = {"assertions": assertions}
    if gen is not None:
        manifest["claim_generator_info"] = [{"name": gen[0], "version": gen[1]}]
    return {
        "active_manifest": active,
        "manifests": {active: manifest},
        "validation_status": [{"code": c} for c in codes],
    }


def test_identical_consumed_fields_pass():
    ref = _store()
    cred = _store()
    res = cs.compare(ref, cred)
    assert res.passed
    assert res.consumer_diffs == []


def test_d2_stricter_verdict_is_expected_not_fail():
    # c2pa-python untrusted vs credentio invalid: consumed fields identical.
    ref = _store(codes=("signingCredential.untrusted",))
    cred = _store(codes=("signingCredential.invalid",))
    res = cs.compare(ref, cred)
    assert res.passed
    assert any(d.code == "D2" for d in res.divergences)


def test_d1_extra_raw_assertions_is_expected_not_fail():
    ref = _store()
    cred = _store(extra_labels=("c2pa.hash.data", "c2pa.thumbnail.claim"))
    res = cs.compare(ref, cred)
    assert res.passed
    assert any(d.code == "D1" for d in res.divergences)


def test_d3_v1_gap_reclassifies_consumed_diff():
    # credentio drops generator+actions AND reports the v1 code.
    ref = _store()
    cred = _store(gen=None, actions=(), codes=("com.google.unsupportedSpecVersion",))
    res = cs.compare(ref, cred)
    assert res.passed, res.consumer_diffs          # generator/actions diff -> D3, not fail
    assert any(d.code == "D3" for d in res.divergences)


def test_d3_does_not_swallow_nonempty_forged_generator():
    # R1 regression: v1 code present BUT credentio reports a NON-EMPTY divergent
    # generator (a forged value, not the documented drop-to-empty). This must FAIL
    # -- the D3 reclassification only excuses the drop-to-empty behavior.
    ref = _store(gen=("credentio-spike", "0.1.0"))
    cred = _store(gen=("evil-forged", "9.9.9"),
                  codes=("com.google.unsupportedSpecVersion",))
    res = cs.compare(ref, cred)
    assert not res.passed, "forged non-empty generator on a v1 asset must FAIL"
    assert any("generator_info" in d for d in res.consumer_diffs)
    assert any(d.code == "D3" for d in res.divergences)  # D3 still reported


def test_d3_does_not_swallow_nonempty_divergent_actions():
    # R1 regression, actions variant: v1 code present but credentio reports a
    # non-empty divergent action list -> FAIL (not the documented drop).
    ref = _store(actions=(("c2pa.created", "http://.../trainedAlgorithmicMedia"),))
    cred = _store(actions=(("c2pa.edited", "http://.../compositeWithTrainedAlgorithmicMedia"),),
                  codes=("com.google.unsupportedSpecVersion",))
    res = cs.compare(ref, cred)
    assert not res.passed
    assert any("actions" in d for d in res.consumer_diffs)


def test_o1_empty_credentio_validation_status_warns():
    # O1: credentio validation_status empty while incumbent reports codes ->
    # non-failing WARNING (consumed fields still match on shape, so it PASSES).
    ref = _store(codes=("signingCredential.untrusted",))
    cred = _store(codes=())
    res = cs.compare(ref, cred)
    assert res.passed                                # shape-only comparison
    assert res.warnings and "EMPTY" in res.warnings[0]


def test_codes_tolerates_non_list_validation_status():
    # O2: a malformed (non-list) validation_status must not raise; compare() must
    # return a clean result (shape mismatch surfaced), never crash.
    ref = _store()
    cred = _store()
    cred["validation_status"] = {"unexpected": "dict"}   # malformed
    res = cs.compare(ref, cred)                            # must not raise
    assert not res.passed
    assert any("validation_status_is_list" in d for d in res.consumer_diffs)


def test_unexpected_action_divergence_fails():
    ref = _store(actions=(("c2pa.created", "http://.../trainedAlgorithmicMedia"),))
    cred = _store(actions=(("c2pa.edited", "http://.../trainedAlgorithmicMedia"),))
    res = cs.compare(ref, cred)
    assert not res.passed
    assert any("actions" in d for d in res.consumer_diffs)


def test_unexpected_generator_divergence_fails():
    ref = _store(gen=("credentio-spike", "0.1.0"))
    cred = _store(gen=("something-else", "9.9.9"))
    res = cs.compare(ref, cred)
    assert not res.passed
    assert any("generator_info" in d for d in res.consumer_diffs)
