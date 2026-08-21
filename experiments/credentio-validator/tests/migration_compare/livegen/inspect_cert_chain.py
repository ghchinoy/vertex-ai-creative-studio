#!/usr/bin/env python3
"""inspect_cert_chain.py -- read the ACTUAL C2PA signing certificate chain from a
real signed asset and answer the trust-list coverage question.

Resolves the OPEN Check 2 of ``primary/trustlist-spike.md``: obtain a real
Google-signed asset, read its signing cert chain (leaf issuer, intermediate(s),
ROOT CA, and the EKU ``c2pa-kp-claimSigning`` / 1.3.6.1.5.5.7.3.36), and decide
whether the bundled ``conformance-public`` anchor list already covers the Google
chain or a Google-operated root must be ADDED.

How it works (no product code, no c2patool needed): the C2PA COSE_Sign1 signature
embeds the signer's X.509 chain as an ``x5chain`` header. Those certs are DER
``SEQUENCE`` (0x30 0x82 ...) blobs inside the asset's JUMBF manifest. This script
scans the raw bytes for DER structures the ``cryptography`` library can parse as
X.509 certificates, de-duplicates by fingerprint, orders them into a chain, and
reports each cert's subject / issuer / EKU / basicConstraints, then compares the
chain's top against the bundled conformance anchors.

Usage:
    cd experiments/credentio-validator
    python tests/migration_compare/livegen/inspect_cert_chain.py \
        --asset tests/migration_compare/livegen/assets/gemini_image.png \
        [--anchors trust/c2pa_conformance_anchors.pem] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import ExtendedKeyUsageOID

_HERE = Path(__file__).resolve()
# livegen / migration_compare / tests / credentio-validator
_EXP_DIR = _HERE.parent.parent.parent.parent   # experiments/credentio-validator
DEFAULT_ANCHORS = _EXP_DIR / "trust" / "c2pa_conformance_anchors.pem"

# The C2PA-assigned claim-signing EKU lives under the C2PA Private Enterprise
# Number (PEN 62558): "1.3.6.1.4.1.62558.2.1". Its presence is exactly what
# credentio's stricter cert-profile check looks for -- the c2pa-rs sandbox cert
# lacks it (credentio -> signingCredential.invalid, the D2 divergence), while a
# real Google leaf carries it (credentio -> signingCredential.untrusted, matching
# c2pa-python, so NO D2 on real Google media).
C2PA_CLAIM_SIGNING_EKU = "1.3.6.1.4.1.62558.2.1"

# Friendly names for the EKU OIDs we expect to encounter, for readable output.
_EKU_NAMES = {
    "1.3.6.1.4.1.62558.2.1": "c2pa-kp-claimSigning (C2PA PEN 62558)",
    "1.3.6.1.5.5.7.3.4": "id-kp-emailProtection",
    "1.3.6.1.5.5.7.3.8": "id-kp-timeStamping",
    "1.3.6.1.5.5.7.3.9": "id-kp-OCSPSigning",
    "1.3.6.1.5.5.7.3.36": "id-kp-documentSigning",
}


def _extract_der_certs(blob: bytes) -> list[x509.Certificate]:
    """Scan raw bytes for DER X.509 certs (SEQUENCE, 2-byte length: 0x30 0x82).
    De-duplicate by SHA-256 fingerprint, preserving first-seen order."""
    certs: list[x509.Certificate] = []
    seen: set[bytes] = set()
    i = 0
    n = len(blob)
    while i < n - 4:
        if blob[i] == 0x30 and blob[i + 1] == 0x82:
            length = (blob[i + 2] << 8) | blob[i + 3]
            end = i + 4 + length
            if end <= n:
                try:
                    cert = x509.load_der_x509_certificate(blob[i:end])
                    fp = cert.fingerprint(hashes.SHA256())
                    if fp not in seen:
                        seen.add(fp)
                        certs.append(cert)
                except Exception:  # noqa: BLE001 - not a cert here; keep scanning
                    pass
        i += 1
    return certs


def _name(name: x509.Name) -> str:
    return name.rfc4514_string()


def _eku_oids(cert: x509.Certificate) -> list[str]:
    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        return [oid.dotted_string for oid in eku]
    except x509.ExtensionNotFound:
        return []


def _is_ca(cert: x509.Certificate) -> bool:
    try:
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        return bool(bc.ca)
    except x509.ExtensionNotFound:
        return False


def _cert_summary(cert: x509.Certificate) -> dict:
    subject = _name(cert.subject)
    issuer = _name(cert.issuer)
    eku = _eku_oids(cert)
    return {
        "subject": subject,
        "issuer": issuer,
        "serial_hex": format(cert.serial_number, "x"),
        "is_ca": _is_ca(cert),
        "self_signed": subject == issuer,
        "eku_oids": eku,
        "eku_names": [_EKU_NAMES.get(o, o) for o in eku],
        "has_c2pa_claim_signing_eku": C2PA_CLAIM_SIGNING_EKU in eku,
        "not_before": cert.not_valid_before_utc.isoformat(),
        "not_after": cert.not_valid_after_utc.isoformat(),
        "sha256_fingerprint": cert.fingerprint(hashes.SHA256()).hex(),
    }


def _order_chain(certs: list[x509.Certificate]) -> list[x509.Certificate]:
    """Order leaf -> ... -> top. Leaf = a cert whose subject is no other cert's
    issuer (i.e. nobody is issued by it)."""
    by_subject = {_name(c.subject): c for c in certs}
    issuers = {_name(c.issuer) for c in certs}
    leaves = [c for c in certs if _name(c.subject) not in issuers]
    if not leaves:
        return certs
    chain = [leaves[0]]
    seen = {_name(leaves[0].subject)}
    cur = leaves[0]
    while True:
        iss = _name(cur.issuer)
        if iss in by_subject and iss not in seen and iss != _name(cur.subject):
            cur = by_subject[iss]
            chain.append(cur)
            seen.add(_name(cur.subject))
        else:
            break
    return chain


def _load_anchor_subjects(anchors_pem: Path) -> list[dict]:
    data = anchors_pem.read_bytes()
    out = []
    for cert in x509.load_pem_x509_certificates(data):
        out.append({
            "subject": _name(cert.subject),
            "sha256_fingerprint": cert.fingerprint(hashes.SHA256()).hex(),
            "subject_cn": _cn(cert.subject),
        })
    return out


def _cn(name: x509.Name) -> str:
    try:
        return name.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
    except (IndexError, Exception):  # noqa: BLE001
        return ""


def inspect(asset: Path, anchors: Path) -> dict:
    blob = asset.read_bytes()
    certs = _extract_der_certs(blob)
    if not certs:
        return {"asset": str(asset), "error": "no X.509 certificates found in asset"}

    chain = _order_chain(certs)
    chain_summ = [_cert_summary(c) for c in chain]
    # Any embedded certs not on the ordered chain (e.g. the TSA chain).
    chain_fps = {c["sha256_fingerprint"] for c in chain_summ}
    other = [_cert_summary(c) for c in certs
             if c.fingerprint(hashes.SHA256()).hex() not in chain_fps]

    anchors_list = _load_anchor_subjects(anchors)
    anchor_fps = {a["sha256_fingerprint"] for a in anchors_list}
    anchor_subjects = {a["subject"] for a in anchors_list}

    # Does the chain top (or any chain cert) match an anchor by fingerprint or subject?
    top = chain_summ[-1]
    top_in_anchors_by_fp = top["sha256_fingerprint"] in anchor_fps
    top_issuer_in_anchor_subjects = top["issuer"] in anchor_subjects
    any_chain_cert_in_anchors = any(
        c["sha256_fingerprint"] in anchor_fps for c in chain_summ
    )
    # Is a Google root present in the bundled anchors at all (by CN containing Google)?
    google_anchor = [a for a in anchors_list if "google" in a["subject_cn"].lower()]

    leaf = chain_summ[0]
    covered = top_in_anchors_by_fp or top_issuer_in_anchor_subjects or any_chain_cert_in_anchors

    return {
        "asset": str(asset),
        "n_certs_found": len(certs),
        "chain_len": len(chain),
        "leaf": leaf,
        "chain": chain_summ,
        "other_embedded_certs": other,
        "leaf_has_c2pa_claim_signing_eku": leaf["has_c2pa_claim_signing_eku"],
        "top_of_embedded_chain_is_self_signed_root": chain_summ[-1]["self_signed"],
        "anchors_file": str(anchors),
        "n_anchors": len(anchors_list),
        "google_anchor_present": bool(google_anchor),
        "chain_covered_by_conformance_public": covered,
        "coverage_reason": (
            "a chain cert matches a bundled anchor by fingerprint"
            if any_chain_cert_in_anchors else
            "chain top's issuer subject matches a bundled anchor subject"
            if top_issuer_in_anchor_subjects else
            "NOT covered: no embedded chain cert or its issuer is in the bundled "
            "anchors, and no Google root is present -> a Google root must be ADDED"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset", required=True)
    p.add_argument("--anchors", default=str(DEFAULT_ANCHORS))
    p.add_argument("--json", metavar="PATH")
    args = p.parse_args(argv)

    result = inspect(Path(args.asset), Path(args.anchors))
    print(json.dumps(result, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2))
        print(f"\nwrote JSON: {args.json}", file=sys.stderr)
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
