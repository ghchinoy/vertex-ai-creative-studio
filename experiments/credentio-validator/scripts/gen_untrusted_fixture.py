#!/usr/bin/env python3
"""gen_untrusted_fixture.py -- generate the "untrusted (sandbox)" C2PA fixture.

Phase 4: exercises the genuine ``signingCredential.untrusted`` path end to end
(credentio -> adapter -> "Untrusted (Sandbox)" summary label).

To make credentio report *untrusted* rather than *invalid* the signing cert must
satisfy the full C2PA cert profile that credentio enforces
(crypto/default/eku_verifier.cc) yet chain to a root that is NOT on the bundled
public trust list:

  * a self-signed ES256 CA (the "sandbox root", absent from trust/), and
  * a leaf issued by it carrying:
        keyUsage        = critical, digitalSignature
        extendedKeyUsage= critical, 1.3.6.1.4.1.62558.2.1  (c2pa-kp-claimSigning)

With a valid-but-untrusted chain, credentio emits signingCredential.untrusted;
the adapter maps that to status "untrusted" / label "Untrusted (Sandbox)".

Requires openssl + c2pa-python. One-shot generator; not part of the runtime pkg.
"""

import json
import pathlib
import subprocess
import tempfile

import c2pa

TESTDATA = pathlib.Path(__file__).resolve().parent.parent / "testdata"
BASE_IMAGE = TESTDATA / "signed_v2.jpg"  # reused only as a JPEG carrier
DST = TESTDATA / "untrusted_sandbox.jpg"

CLAIM_SIGNING_EKU = "1.3.6.1.4.1.62558.2.1"


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def build_sandbox_chain(tmp: pathlib.Path) -> tuple[str, str]:
    """Mint a self-signed ES256 CA + a C2PA-profile leaf. Returns (chain_pem, leaf_pk8_pem)."""
    ca_key, ca_crt = tmp / "ca.key", tmp / "ca.crt"
    leaf_key, leaf_csr, leaf_crt = tmp / "leaf.key", tmp / "leaf.csr", tmp / "leaf.crt"
    leaf_pk8 = tmp / "leaf_pk8.pem"

    leaf_ext = tmp / "leaf.cnf"
    leaf_ext.write_text(
        "[v3_leaf]\n"
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature\n"
        f"extendedKeyUsage=critical,{CLAIM_SIGNING_EKU}\n"
    )

    # self-signed sandbox CA
    _run(["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(ca_key)])
    _run(["openssl", "req", "-x509", "-new", "-key", str(ca_key), "-sha256", "-days", "3650",
          "-out", str(ca_crt), "-subj", "/CN=credentio-spike-sandbox-CA/O=spike"])
    # leaf issued by the sandbox CA, with the C2PA claim-signing EKU
    _run(["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(leaf_key)])
    _run(["openssl", "req", "-new", "-key", str(leaf_key), "-out", str(leaf_csr),
          "-subj", "/CN=credentio-spike-signer/O=spike"])
    _run(["openssl", "x509", "-req", "-in", str(leaf_csr), "-CA", str(ca_crt), "-CAkey", str(ca_key),
          "-CAcreateserial", "-days", "3650", "-sha256", "-out", str(leaf_crt),
          "-extfile", str(leaf_ext), "-extensions", "v3_leaf"])
    _run(["openssl", "pkcs8", "-topk8", "-nocrypt", "-in", str(leaf_key), "-out", str(leaf_pk8)])

    chain = leaf_crt.read_text() + ca_crt.read_text()
    return chain, leaf_pk8.read_text()


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        chain, key = build_sandbox_chain(pathlib.Path(td))
    signer = c2pa.Signer.from_info(
        c2pa.C2paSignerInfo(alg=b"es256", sign_cert=chain.encode(),
                            private_key=key.encode(), ta_url=None)
    )
    manifest = {
        "claim_generator_info": [{"name": "credentio-spike", "version": "0.1.0"}],
        "title": "credentio spike untrusted-sandbox fixture",
        "format": "image/jpeg",
        "assertions": [{
            "label": "c2pa.actions.v2",
            "data": {"actions": [{
                "action": "c2pa.created",
                "digitalSourceType": (
                    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"),
            }]},
        }],
    }
    if DST.exists():
        DST.unlink()
    c2pa.Builder.from_json(json.dumps(manifest)).sign_file(str(BASE_IMAGE), str(DST), signer)
    print(f"signed -> {DST.name} ({DST.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
