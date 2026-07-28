# Releasing C2Go Toolchain

[简体中文](RELEASING.zh-CN.md)

This procedure is fail-closed. A locally prepared checkout, an unpushed commit,
or a passing component-only test is not release evidence.

## 1. Publish the component repositories

Create and populate these controlled repositories first:

- `https://github.com/c2gohq/c2go_clang.git`
- `https://github.com/c2gohq/c2go_bind.git`
- `https://github.com/c2gohq/c2go_libc.git`
- `https://github.com/c2gohq/musl.git`

The c2go-clang fork must not use the upstream LLVM repository as its push
target. Preserve upstream history and all LLVM notices.

Before adding submodules, verify that every release commit is reachable from
its public remote and that c2go-libc pins the intended musl commit as its own
nested submodule.

## 2. Initialize the top-level submodules

The submodules are already registered in `.gitmodules`. From a fresh checkout:

```sh
git submodule sync --recursive
git submodule update --init --recursive
```

Check out reviewed, immutable commits in each component. Never point a release
at a moving branch name.

## 3. Close component release blockers

At minimum, verify from clean recursive clones:

1. c2go-clang builds the coordinated compiler and passes the selected Clang,
   LLVM, C2Go, and cross-repository tests.
2. c2go-bind passes tests, race tests, vet, build, and cross-repository LIT.
3. c2go-libc contains or no longer requires `c2go_libc/dl`, has a real musl
   submodule, ships or reproducibly generates every promised target artifact,
   and passes the reviewed platform matrix.
4. All Apple/FreeBSD/XNU/MinGW/musl/Go/PureGo and other provenance boundaries,
   notices, and complete-source obligations are closed.
5. The commercial licensor, contributor agreement, and public contact/payment
   process are legally ready without changing third-party rights.

## 4. Lock the release

Use one coordinated version, normally the same tag in all three top-level
components. The first public candidate should be `v0.1.0-rc.1`.

Update [toolchain.lock.json](toolchain.lock.json):

- set `release.version`, `release.status`, and `release.published_at`;
- set every component and nested dependency to its full commit hash and tag;
- update the Go version window and C2Go ABI epoch only from verified evidence;
- commit the resulting submodule gitlinks and lock file together.

## 5. Run the release gate

From a clean recursive clone of this repository:

```sh
git submodule update --init --recursive
python3 scripts/verify-release.py
```

Then run the documented component build/test matrix. Preserve machine-readable
logs with the release evidence.

After pushing the reviewed commits (but before creating tags), run the
`Release C2Go toolchain` workflow manually with the candidate version. This is
an unsigned dry run: it exercises the same four native build jobs and complete
source packaging without creating a GitHub Release.

## 6. Build release artifacts

A Git archive of this repository does not include submodule contents. Build a
complete release source bundle that contains or fetches, in a
license-compliant and reproducible way, every exact component and nested
dependency used to build shipped artifacts.

For every binary/source bundle, publish:

- filename, platform, architecture, and toolchain version;
- SHA-256 checksum;
- exact component and nested-dependency revisions;
- applicable license and third-party notice bundle;
- reproducible build instructions and required bootstrap tools; and
- SBOM/provenance data when available.

The checked-in workflow currently uses Ubuntu 22.04 for both Linux
architectures, Windows Server 2022 for Windows amd64, and macOS 14 arm64 with
`CMAKE_OSX_DEPLOYMENT_TARGET=11.0`. It emits unsigned deterministic archives,
the complete recursive source bundle, checksum sidecars, and `SHA256SUMS`.
Signing, Apple notarization, and Windows Authenticode are deliberately not
configured until the corresponding credentials and policy are available.

## 7. Tag and publish

Tag reviewed component commits first. Then tag the c2go-toolchain commit whose
gitlinks and lock file reference those exact commits. Pushing that tag builds
the assets and creates a GitHub Release draft using the repository's automatic
`GITHUB_TOKEN`; no personal access token is required. Inspect the artifacts,
rendered notices, checksums, and installation smoke tests, then publish the
draft manually.

Do not move or replace a published tag. Corrections receive a new candidate or
patch version.
