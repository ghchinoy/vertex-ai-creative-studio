#!/usr/bin/env bash
#
# Fetch the real, public C2PA-signed JPEG fixture used by the Phase 1 demo.
#
# CA.jpg is a genuine C2PA-signed image from the contentauth/c2pa-rs test suite
# (signed by the c2pa-rs "make_test_images" sandbox signer -- its cert does NOT
# chain to any public trust list, so validators report signingCredential.untrusted;
# that is the expected "untrusted (sandbox)" success path, not an error).
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${HERE}/testdata/CA.jpg"
URL="https://raw.githubusercontent.com/contentauth/c2pa-rs/main/sdk/tests/fixtures/CA.jpg"

echo ">> fetching ${URL}"
curl -fsSL -o "${DEST}" "${URL}"
echo ">> wrote ${DEST} ($(wc -c < "${DEST}") bytes)"
