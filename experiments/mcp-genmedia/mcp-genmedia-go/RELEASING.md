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

## Cutting a release

1. Update `VERSION` to the new semver (this is the human-editable single source).
2. Commit the `VERSION` bump (and `CHANGELOG.md`) to `main`.
3. Tag the release, e.g. `git tag v<version> && git push origin v<version>`.
4. goreleaser builds the artifacts, injecting the tag as the version.

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

## Future: release-please (step b)

This VERSION-file + ldflags plumbing is step (a) of the automation plan. It is
intentionally compatible with a later
[release-please](https://github.com/googleapis/release-please) adoption:
release-please will automate bumping the `VERSION` file and maintaining
`CHANGELOG.md` from Conventional Commit messages, then the tag it creates drives
goreleaser exactly as described above.
