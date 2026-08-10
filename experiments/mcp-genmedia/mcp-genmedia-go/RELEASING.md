# Releasing the genmedia MCP servers

## Single source of truth for the version

The version for **all** MCP servers in this tree lives in one place:

```
experiments/mcp-genmedia/mcp-genmedia-go/VERSION
```

It contains a bare semver string (e.g. `3.10.0`). This replaces the previous
approach of a per-file `const version = "..."` hand-edited in each of the seven
server entry files — that hand-sync is what caused the `mcp-chirp3-go` version to
drift out of step with the rest.

Each server still exposes a package-level `var version = "dev"` in its `main`
package. The value is **injected at build time** via
`-ldflags "-X main.version=<version>"`; nobody edits the Go source to bump a
version anymore. A bare `go run` / `go build` (no ldflags) leaves it as `"dev"`,
which clearly signals an un-injected local build.

## How the version is derived

| Build path | Version source | Mechanism |
|------------|----------------|-----------|
| **Released artifacts** | the git tag (e.g. `v3.10.0`) | `.goreleaser.yaml` injects `-X main.version={{.Version}}` per build; goreleaser derives `{{.Version}}` from the tag. |
| **Local / CI builds** | the `VERSION` file | `make build` reads `VERSION` and passes `-ldflags "-X main.version=$(cat VERSION)"` for every server. |

For releases the **git tag is the source of truth** — no file edit is required at
release time. The `VERSION` file keeps local and CI builds honest, and it is the
file a future automation step (see below) will bump.

## Cutting a release (automated — release-please)

Releases of the MCP servers are automated with
[release-please](https://github.com/googleapis/release-please), scoped to **this
tree only** (`experiments/mcp-genmedia/mcp-genmedia-go`). It never touches the
core app's version (root `pyproject.toml`, `config/default.py`) — see
[MCP-only isolation](#mcp-only-isolation-important) below.

The normal flow is:

1. **Land Conventional-Commit PRs.** Write MCP changes as Conventional Commits
   (`feat:` → minor, `fix:`/`perf:` → patch, `feat!:` or a `BREAKING CHANGE:`
   footer → major). On squash-merge the **PR title** becomes the commit subject,
   so the PR title must be conventional — the `MCP PR Title (Conventional
   Commits)` check enforces this for PRs that touch this tree.
2. **release-please maintains a standing "release PR."** On every push to `main`
   that touches this tree, the `release-please (MCP genmedia)` workflow opens or
   updates a release PR that bumps `VERSION` and prepends the derived entries to
   `CHANGELOG.md`. It only considers commits under this path.
3. **Merge the release PR** when you want to cut the release (the human gate).
   On merge, release-please creates the tag **`mcp-v<version>`** and a GitHub
   Release with the changelog notes.
4. **goreleaser publishes the binaries.** The `mcp-v*` tag triggers
   `.github/workflows/mcp-release.yml`, which strips the `mcp-` prefix and runs
   goreleaser, injecting `-X main.version={{.Version}}` from the tag.

### Tag format and the goreleaser handoff

release-please emits `mcp-v<version>` (component `mcp` + `-v` + version). This is
deliberate:

* It **matches the existing `mcp-release.yml` trigger** (`tags: ['mcp-v*']`) so
  goreleaser still fires unchanged.
* It is **MCP-specific** and does not collide with a bare, repo-wide `vX.Y.Z`
  that would imply a *core-app* release.

> **Token note.** A tag pushed by release-please with the default `GITHUB_TOKEN`
> will **not** trigger the goreleaser workflow (GitHub's workflow-recursion
> guard). To chain automatically, add a repo/org secret `RELEASE_PLEASE_TOKEN`
> (a PAT or GitHub App token with `contents: write` + `pull-requests: write`).
> Without it, the release PR, tag, and Release are still created, but a
> maintainer must publish the binaries manually (re-push the `mcp-v*` tag or run
> goreleaser).

### MCP-only isolation (important)

This pipeline is **isolated to the MCP servers**. Isolation holds on two
independent layers:

1. `release-please-config.json` declares a **single package** rooted at
   `experiments/mcp-genmedia/mcp-genmedia-go`; release-please only inspects
   commits touching that path and only ever edits that path's `VERSION` +
   `CHANGELOG.md`.
2. The workflow's push trigger is **path-filtered** to the MCP tree, so a push
   that changes only core-app files never even starts release-please.

The core app versions separately via root `pyproject.toml` and
`config/default.py`; release-please does not read, propose, or edit them.

### Manual fallback

If you ever need to cut a release by hand: bump `VERSION`, update `CHANGELOG.md`,
commit to `main`, then `git tag mcp-v<version> && git push origin mcp-v<version>`
— the `mcp-v*` tag drives goreleaser exactly as above.

## Local builds

```sh
cd experiments/mcp-genmedia/mcp-genmedia-go
make build      # builds every server into ./bin with the VERSION injected
make version    # prints the version that will be injected
make vet        # go vet across every server module
```

You can verify injection on any built binary by starting it and reading the
startup log line, e.g.:

```
Starting mcp-veo-go MCP Server (Version: 3.10.0, Transport: stdio)
```

## Automation history

* **Step (a)** — single `VERSION` file + build-time ldflags injection (replaced
  the seven hand-edited `const version` declarations).
* **Step (b)** — release-please adoption (this document's automated flow):
  release-please bumps the `VERSION` file and maintains `CHANGELOG.md` from
  Conventional Commit messages, then the `mcp-v*` tag it creates drives
  goreleaser exactly as described above. Config lives in
  `release-please-config.json` and `.release-please-manifest.json` at the repo
  root (root is release-please's required location for these two files; they are
  configuration only and do not version the core app).
