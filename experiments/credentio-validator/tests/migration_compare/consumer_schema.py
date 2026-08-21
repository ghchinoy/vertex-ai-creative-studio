"""consumer_schema.py -- projection + diff + the explicit pass/fail rule.

THE HEART OF THE TEST. Both validators emit a c2pa-python-shaped ``manifest_store``
dict (credentio via ``adapter.to_manifest_store``; c2pa-python natively via
``c2pa.Reader(path).json()``). This module projects each store down to exactly the
fields the product's real call sites consume, diffs the two projections, and
decides PASS/FAIL under a rule that is explicit in code.

The consumer schema (only what the product actually reads):
  * ``has_active_manifest``            -- there is an active manifest id
  * ``active_manifest_present_in_map`` -- that id resolves in ``manifests``
  * ``generator_info``  -- list of ``{name, version}`` from claim_generator_info
                           (the Lit viewer + ``summarize_c2pa`` read generator name;
                           we compare name AND version). Implementation-private
                           markers such as c2pa-python's ``org.contentauth.c2pa_rs``
                           are intentionally dropped -- the product never reads them.
  * ``actions``         -- the c2pa.actions / c2pa.actions.v2 action list, each
                           ``{action, digitalSourceType}`` (``summarize_c2pa`` and
                           the Lit ``content_credentials`` web component key off this)
  * ``validation_status_is_list`` -- the SHAPE the product iterates; we compare the
                           shape, not the raw codes (independent validators
                           legitimately differ on verdict wording -- see below).

WHY NOT COMPARE RAW VERDICT STRINGS: credentio is an independent, stricter
implementation of the C2PA 2.2 certificate profile. On the c2pa-rs test cert it
returns ``signingCredential.invalid`` where c2pa-python returns
``signingCredential.untrusted`` (spike finding #3). Both are structurally a list
of ``{code, ...}``; the product iterates the list shape. Comparing raw strings
would report a false failure on what is a documented, expected difference.

THE PASS/FAIL RULE (explicit):
  A surface PASSES when every consumer-schema field that the product consumes is
  EQUAL across the two validators, after removing any field difference fully
  explained by a DOCUMENTED expected-divergence. It FAILS when a consumed field
  differs in a way NOT explained by a documented expected-divergence.

  Documented expected-divergences (from spike-result.md; each is detected and
  reported explicitly, never silently swallowed):
    D1 EXTRA_RAW_ASSERTIONS  -- credentio carries the full raw assertion store
       (c2pa.hash.*, thumbnails) that c2pa-python filters/relocates. Outside the
       consumed fields (we only project c2pa.actions*), so it never changes the
       verdict; reported for transparency.
    D2 STRICTER_VERDICT      -- credentio emits signingCredential.invalid where
       c2pa-python emits signingCredential.untrusted. In validation_status CODES,
       which are outside the consumed fields (we compare list SHAPE only);
       reported for transparency.
    D3 V1_CLAIM_UNSUPPORTED  -- on a legacy v1-claim asset credentio reports
       com.google.unsupportedSpecVersion and drops claim-generator info/actions.
       This DOES land in consumed fields (generator_info/actions), so consumed-field
       differences are reclassified as this expected-divergence rather than a fail
       -- with the actual dropped values shown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

UNTRUSTED_CODE = "signingCredential.untrusted"
INVALID_CODE = "signingCredential.invalid"
V1_UNSUPPORTED_CODE = "com.google.unsupportedSpecVersion"


# --------------------------------------------------------------------------- #
# projection
# --------------------------------------------------------------------------- #
def _active_manifest(store: dict) -> dict:
    return store.get("manifests", {}).get(store.get("active_manifest"), {}) or {}


def _generator_info(manifest: dict) -> list[dict]:
    """Project claim_generator_info to just {name, version} -- the fields the
    consumers read. Drops implementation-private extras (e.g. c2pa-python's
    org.contentauth.c2pa_rs marker) the product never looks at."""
    out = []
    for entry in manifest.get("claim_generator_info", []) or []:
        out.append({"name": entry.get("name"), "version": entry.get("version")})
    return out


# The action-assertion labels the product consumes. Exact-set membership (rather
# than an ``"c2pa.actions" in label`` substring test) so that, if a manifest ever
# carried both blocks, their action lists are not silently concatenated (review O3).
_ACTION_LABELS = frozenset({"c2pa.actions", "c2pa.actions.v2"})


def _actions(manifest: dict) -> list[dict]:
    """Project the c2pa.actions* assertion to {action, digitalSourceType}."""
    out = []
    for a in manifest.get("assertions", []) or []:
        if (a.get("label") or "") in _ACTION_LABELS:
            for act in a.get("data", {}).get("actions", []) or []:
                out.append({
                    "action": act.get("action"),
                    "digitalSourceType": act.get("digitalSourceType"),
                })
    return out


def project(store: dict) -> dict:
    """Project a manifest_store onto the consumer schema the product reads."""
    am = _active_manifest(store)
    return {
        "has_active_manifest": bool(store.get("active_manifest")),
        "active_manifest_present_in_map": store.get("active_manifest")
        in (store.get("manifests") or {}),
        "generator_info": _generator_info(am),
        "actions": _actions(am),
        "validation_status_is_list": isinstance(store.get("validation_status"), list),
    }


def assertion_labels(store: dict) -> list[str]:
    return sorted(
        (a.get("label") or "") for a in _active_manifest(store).get("assertions", []) or []
    )


def codes(store: dict) -> list[str]:
    # Guard against a non-list validation_status: a malformed/degraded store must
    # yield a clean shape mismatch downstream, not an AttributeError that crashes
    # the whole run (review O2). project() already treats a non-list as a shape diff.
    vs = store.get("validation_status")
    if not isinstance(vs, list):
        return []
    return [s.get("code") for s in vs if isinstance(s, dict)]


# --------------------------------------------------------------------------- #
# diff
# --------------------------------------------------------------------------- #
def diff(ref_proj: dict, cred_proj: dict) -> list[str]:
    """Field-level diff of two consumer-schema projections.

    ``ref_proj`` is the c2pa-python (incumbent) side; ``cred_proj`` is credentio.
    Returns a list of human-readable difference strings (empty == identical).
    """
    out: list[str] = []
    for key in sorted(set(ref_proj) | set(cred_proj)):
        rv = ref_proj.get(key)
        cv = cred_proj.get(key)
        if rv != cv:
            out.append(f"{key}: c2pa-python={rv!r}  !=  credentio={cv!r}")
    return out


# --------------------------------------------------------------------------- #
# expected-divergence detection + pass/fail
# --------------------------------------------------------------------------- #
@dataclass
class Divergence:
    code: str            # D1/D2/D3 tag
    title: str
    detail: str


@dataclass
class SurfaceResult:
    passed: bool
    ref_projection: dict
    cred_projection: dict
    consumer_diffs: list[str]                    # unexplained consumed-field diffs (empty on PASS)
    divergences: list[Divergence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # non-failing signals (e.g. O1)
    ref_codes: list[str] = field(default_factory=list)
    cred_codes: list[str] = field(default_factory=list)
    ref_labels: list[str] = field(default_factory=list)
    cred_labels: list[str] = field(default_factory=list)


def _detect_divergences(ref_store: dict, cred_store: dict) -> list[Divergence]:
    divs: list[Divergence] = []

    ref_labels = assertion_labels(ref_store)
    cred_labels = assertion_labels(cred_store)
    extra = sorted(set(cred_labels) - set(ref_labels))
    if extra:
        divs.append(Divergence(
            "D1", "EXTRA_RAW_ASSERTIONS",
            f"credentio surfaces raw assertions c2pa-python filters/relocates: "
            f"{extra}. Outside the consumed fields (only c2pa.actions* is read); "
            f"does not change the verdict.",
        ))

    ref_codes = codes(ref_store)
    cred_codes = codes(cred_store)
    if ref_codes != cred_codes:
        # Stricter-verdict swap: same count, invalid where the other is untrusted.
        swap = (
            len(ref_codes) == len(cred_codes)
            and set(ref_codes) <= {UNTRUSTED_CODE, INVALID_CODE}
            and set(cred_codes) <= {UNTRUSTED_CODE, INVALID_CODE}
            and INVALID_CODE in cred_codes
        )
        if swap:
            divs.append(Divergence(
                "D2", "STRICTER_VERDICT",
                f"credentio={cred_codes} vs c2pa-python={ref_codes}: credentio "
                f"applies stricter C2PA 2.2 cert-profile checks "
                f"(EKU c2pa-kp-claimSigning). Both are a list of {{code,...}}; the "
                f"product iterates the list shape, not the raw code.",
            ))

    if V1_UNSUPPORTED_CODE in cred_codes:
        divs.append(Divergence(
            "D3", "V1_CLAIM_UNSUPPORTED",
            f"credentio reports {V1_UNSUPPORTED_CODE} on this legacy v1-claim asset "
            f"and drops claim-generator info/actions. A known upstream gap "
            f"(spike finding #4) -- consumed-field differences here are attributed "
            f"to this expected-divergence, not counted as a failure.",
        ))
    return divs


def _is_v1_gap(divs: list[Divergence]) -> bool:
    return any(d.code == "D3" for d in divs)


def compare(ref_store: dict, cred_store: dict) -> SurfaceResult:
    """Compare two manifest stores on the consumer schema and decide PASS/FAIL."""
    ref_proj = project(ref_store)
    cred_proj = project(cred_store)
    raw_diffs = diff(ref_proj, cred_proj)
    divs = _detect_divergences(ref_store, cred_store)

    # Reclassify: when the v1-claim gap (D3) is present, the ONLY documented
    # behavior is that credentio *drops* generator_info/actions (projects to an
    # empty value). We therefore skip a generator_info/actions diff ONLY when
    # credentio's projected value is actually empty -- i.e. the documented drop.
    # A NON-EMPTY value that diverges (e.g. a forged generator) is still a real
    # FAIL, so the D3 safeguard cannot silently swallow a wrong value (review R1).
    unexplained: list[str] = []
    for d in raw_diffs:
        field_name = d.split(":", 1)[0]
        if (
            _is_v1_gap(divs)
            and field_name in ("generator_info", "actions")
            and not cred_proj.get(field_name)   # only the documented drop-to-empty
        ):
            continue
        unexplained.append(d)

    # O1: shape-only validation_status means a credentio that silently stopped
    # validating (empty validation_status) would still match on the consumed
    # fields. Surface that as a non-failing WARNING when the incumbent DID report
    # codes but credentio reported none -- so a degraded validator is visible
    # rather than scoring a clean pass under the "credentio adds validation" claim.
    warnings: list[str] = []
    ref_codes = codes(ref_store)
    cred_codes = codes(cred_store)
    if ref_codes and not cred_codes:
        warnings.append(
            f"credentio validation_status is EMPTY while c2pa-python reports "
            f"{ref_codes} -- credentio may not have validated this asset. "
            f"(Consumed fields still compare on list SHAPE, so this does not fail "
            f"the surface, but it is surfaced here.)"
        )

    return SurfaceResult(
        passed=(len(unexplained) == 0),
        ref_projection=ref_proj,
        cred_projection=cred_proj,
        consumer_diffs=unexplained,
        divergences=divs,
        warnings=warnings,
        ref_codes=ref_codes,
        cred_codes=cred_codes,
        ref_labels=assertion_labels(ref_store),
        cred_labels=assertion_labels(cred_store),
    )
