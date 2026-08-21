# bin/ -- the credentio `c2pa_validate` binary

The compiled `c2pa_validate` binary lands here as `bin/c2pa_validate`. It is
**gitignored** (large, platform-specific, and a PoC artifact -- not something to
commit). This file documents its provenance so the binary is reproducible.

## How it was built (spike)

- **Source:** `https://mediaprovenance.googlesource.com/credentio`
- **Target:** `//tools:c2pa_validate`
- **Command:** `bazelisk build -c opt //tools:c2pa_validate`
  (wrapped by `scripts/build_credentio.sh`)
- **Toolchain:** Bazelisk + Clang/LLVM with libc++ (credentio's `.bazelrc`
  forces `-stdlib=libc++`).

See `poc/phase1-build-notes.md` in the design workspace for the exact resolved
Bazel version, Clang version, credentio commit, and build time recorded during
the spike.

## Rebuilding

```bash
./scripts/build_credentio.sh    # or: make build-credentio
```

> PoC only -- production needs a real, pinned, containerized build pipeline
> (credentio is v0.1.0, unversioned, live-at-head, "breaking changes without
> notice").
