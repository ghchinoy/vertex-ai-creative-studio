#!/usr/bin/env bash
#
# Build the credentio c2pa_validate CLI from source and copy it into bin/.
#
# PoC / spike build script. This is NOT a production build pipeline -- it clones
# credentio live-at-head (the repo is v0.1.0, unversioned, "breaking changes
# without notice") and builds it with Bazelisk + Clang/libc++. A real deployment
# needs a pinned, reproducible, containerized build (see design.md "Build story").
#
# Toolchain requirements (see phase1-build-notes.md for the exact versions used
# in the spike):
#   - bazelisk (honours credentio's Bazel version; the repo pins none, so the
#     latest stable Bazel is used -- record the resolved version)
#   - clang / clang++ with libc++ (the credentio .bazelrc forces -stdlib=libc++)
#   - git, and network access to mediaprovenance.googlesource.com + Bazel deps
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HERE}/bin"
WORK_DIR="${CREDENTIO_SRC_DIR:-${HOME}/work/credentio}"
CREDENTIO_REPO="https://mediaprovenance.googlesource.com/credentio"

echo ">> credentio source dir: ${WORK_DIR}"
if [[ ! -d "${WORK_DIR}/.git" ]]; then
  echo ">> cloning ${CREDENTIO_REPO}"
  git clone "${CREDENTIO_REPO}" "${WORK_DIR}"
fi

cd "${WORK_DIR}"
echo ">> credentio commit: $(git rev-parse HEAD)"

# credentio's .bazelrc forces clang + libc++. Make sure Bazel uses clang.
export CC="${CC:-clang}"
export CXX="${CXX:-clang++}"

echo ">> bazelisk build -c opt //tools:c2pa_validate"
bazelisk build -c opt //tools:c2pa_validate

mkdir -p "${BIN_DIR}"
cp -f "$(bazelisk cquery --output=files //tools:c2pa_validate 2>/dev/null | tail -1)" \
      "${BIN_DIR}/c2pa_validate" 2>/dev/null \
  || cp -f "${WORK_DIR}/bazel-bin/tools/c2pa_validate" "${BIN_DIR}/c2pa_validate"

chmod +x "${BIN_DIR}/c2pa_validate"
echo ">> installed binary: ${BIN_DIR}/c2pa_validate"
"${BIN_DIR}/c2pa_validate" --help 2>&1 | head -5 || true
