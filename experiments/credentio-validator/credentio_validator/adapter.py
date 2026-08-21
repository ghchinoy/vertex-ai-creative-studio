"""adapter.py -- normalize credentio crJSON into a c2pa-python-shaped store.

This is the one real correctness task of the spike. credentio's native crJSON
(produced by ``ConvertToCrJson`` in utils/crjson.cc) is NOT the same shape as
``c2pa-python``'s manifest JSON, so this module maps it onto the manifest-store
shape the existing consumers already parse (``services/c2pa_service.py`` returns
it raw to the Lit viewer; ``experiments/veo-variations/core/c2pa.py``'s
``summarize_c2pa`` walks it).

Target schema (only the fields the current code reads -- see design.md):

    manifest_store = {
      "active_manifest": "<id>",
      "manifests": {
        "<id>": {
          "claim_generator": "<str>",
          "claim_generator_info": [ { "name": "<str>", "version": "<str>" } ],
          "assertions": [
            { "label": "c2pa.actions.v2",
              "data": { "actions": [ { "action": "<str>", ... } ] } }
          ],
          "label": "<id>",
        }
      },
      "validation_status": [ { "code": "signingCredential.untrusted", ... } ]
    }

Key shape differences bridged here (derived from real CLI output + crjson.cc):
  * credentio ``manifests`` is an ARRAY (active = element 0, from reverse box
    iteration); c2pa-python ``manifests`` is a MAP keyed by manifest label, plus
    a top-level ``active_manifest`` id.
  * credentio ``assertions`` is an OBJECT keyed by label; c2pa-python
    ``assertions`` is an ARRAY of ``{"label", "data"}``.
  * credentio ``claim_generator_info`` is a single object under ``claim.v2``;
    c2pa-python uses a LIST and also exposes a flattened ``claim_generator``
    string. (For legacy v1-claim assets credentio emits no ``claim.v2`` block,
    so the generator fields are best-effort/empty -- a documented limitation.)
  * credentio ``validationResults`` splits codes into success/informational/
    failure arrays; c2pa-python's flat ``validation_status`` lists the non-success
    (problem) codes. We map credentio failures+informational into it.
"""

from __future__ import annotations

# credentio buckets that represent a non-success validation code, i.e. the ones
# c2pa-python surfaces in its flat ``validation_status`` list.
_PROBLEM_BUCKETS = ("failure", "informational")

_UNTRUSTED_CODE = "signingCredential.untrusted"


def _validation_status_from_manifest(cred_manifest: dict) -> list[dict]:
    """Flatten a credentio manifest's validationResults problem codes to a list.

    Returns entries shaped like c2pa-python's ``validation_status`` items:
    ``{"code", "url"?, "explanation"?}``.
    """
    out: list[dict] = []
    vr = cred_manifest.get("validationResults") or {}
    for bucket in _PROBLEM_BUCKETS:
        for entry in vr.get(bucket, []) or []:
            item = {"code": entry.get("code")}
            if entry.get("url"):
                item["url"] = entry["url"]
            if entry.get("explanation"):
                item["explanation"] = entry["explanation"]
            out.append(item)
    return out


def _assertions_to_list(cred_assertions: dict) -> list[dict]:
    """credentio assertions object {label: data} -> [{"label", "data"}]."""
    result: list[dict] = []
    if not isinstance(cred_assertions, dict):
        return result
    for label, data in cred_assertions.items():
        result.append({"label": label, "data": data})
    return result


def _generator_fields(cred_manifest: dict) -> tuple[str | None, list[dict]]:
    """Derive (claim_generator string, claim_generator_info list).

    credentio stores a single ``claim_generator_info`` object under
    ``claim.v2``. c2pa-python uses a list and a flattened UA-style string.
    """
    claim = cred_manifest.get("claim.v2") or {}
    info = claim.get("claim_generator_info")
    if not info:
        return None, []
    info_list = info if isinstance(info, list) else [info]
    # Flatten to a c2pa-python-style "name/version name/version" string.
    parts = []
    for entry in info_list:
        name = entry.get("name")
        if not name:
            continue
        version = entry.get("version")
        parts.append(f"{name}/{version}" if version else name)
    claim_generator = " ".join(parts) if parts else None
    return claim_generator, info_list


def to_manifest_store(crjson: dict) -> dict:
    """Normalize credentio crJSON into a c2pa-python-shaped manifest store."""
    cred_manifests = crjson.get("manifests", []) or []

    manifests: dict[str, dict] = {}
    validation_status: list[dict] = []
    active_manifest: str | None = None

    for idx, cred_manifest in enumerate(cred_manifests):
        label = cred_manifest.get("label", "") or f"__manifest_{idx}"
        if idx == 0:
            # credentio emits the active manifest first (see crjson.cc).
            active_manifest = label

        claim_generator, claim_generator_info = _generator_fields(cred_manifest)
        target_manifest: dict = {
            "claim_generator": claim_generator,
            "claim_generator_info": claim_generator_info,
            "assertions": _assertions_to_list(cred_manifest.get("assertions", {})),
            "label": label,
        }
        manifests[label] = target_manifest

        # Multi-manifest behavior (resolves review item 2): c2pa-python's
        # top-level validation_status is a FLAT list that can carry codes from
        # the active manifest AND nested/ingredient manifests. We therefore
        # aggregate problem codes across ALL manifests, active first, rather than
        # only the active one. For the single-manifest case this is identical to
        # the Phase 1 behavior (and to how summarize_c2pa reads one list), so the
        # gate and existing tests are unaffected.
        validation_status.extend(_validation_status_from_manifest(cred_manifest))

    store: dict = {
        "active_manifest": active_manifest,
        "manifests": manifests,
        "validation_status": validation_status,
    }
    return store


def summarize(manifest_store: dict) -> dict:
    """Compute the validation summary the same way ``summarize_c2pa`` does.

    Returns ``{"status": "valid"|"untrusted"|"invalid", "codes": [...]}``:
      * no codes                         -> valid
      * all codes signingCredential.untrusted -> untrusted (sandbox)
      * otherwise                        -> invalid
    """
    codes = [s.get("code") for s in manifest_store.get("validation_status", []) or []]
    if not codes:
        status = "valid"
    elif all(c == _UNTRUSTED_CODE for c in codes):
        status = "untrusted"
    else:
        status = "invalid"
    return {"status": status, "codes": codes}


def build_summary(manifest_store: dict) -> dict:
    """Build the EXACT ``summarize_c2pa``-shaped dict on a success path.

    Mirrors ``experiments/veo-variations/core/c2pa.py::summarize_c2pa`` byte for
    byte in its output shape and status label strings -- ``"Valid"``,
    ``"Untrusted (Sandbox)"``, ``"Invalid (<code>)"`` -- so it is a true drop-in
    (resolves review item 3). The failure-path dict
    (``{"status": "Error", "error_detail": ..., "actions": [], "generator":
    "Unknown"}``) is produced by ``client.summarize`` when there is no manifest
    store to summarize.

    Actions are formatted identically: ``{"label": <action>, "detail":
    "<action>: <description> (<ds_name>)"}`` where ``<ds_name>`` is the last path
    segment of ``digitalSourceType``.
    """
    validation_status = manifest_store.get("validation_status", []) or []
    status_label = "Valid"
    if validation_status:
        codes = [s.get("code") for s in validation_status]
        if all(c == _UNTRUSTED_CODE for c in codes):
            status_label = "Untrusted (Sandbox)"
        else:
            status_label = f"Invalid ({codes[0]})"

    active_manifest_id = manifest_store.get("active_manifest")
    active_manifest = manifest_store.get("manifests", {}).get(active_manifest_id, {}) or {}

    generator = "Unknown"
    gen_info = active_manifest.get("claim_generator_info", [])
    if gen_info and isinstance(gen_info, list):
        generator = gen_info[0].get("name", "Unknown")
    elif active_manifest.get("claim_generator"):
        generator = active_manifest.get("claim_generator")

    summary = {"status": status_label, "generator": generator, "actions": []}

    for assertion in active_manifest.get("assertions", []) or []:
        label = assertion.get("label", "")
        if "c2pa.actions" in label:
            for action in assertion.get("data", {}).get("actions", []) or []:
                action_name = action.get("action", "unknown action")
                description = action.get("description", "")
                ds_type = action.get("digitalSourceType", "")
                detail = f"{action_name}: {description}"
                if ds_type:
                    ds_name = ds_type.split("/")[-1] if "/" in ds_type else ds_type
                    detail += f" ({ds_name})"
                summary["actions"].append({"label": action_name, "detail": detail})

    return summary
