<p align="center">
  <img src="assets/c2gohq-logo.png" width="240" alt="C2Go logo">
</p>

<h1 align="center">C2Go Toolchain</h1>

<p align="center">
  A coordinated C-to-Go compiler, binding generator, and runtime compatibility layer.
</p>

<p align="center">
  <a href="README.zh-CN.md">简体中文</a>
</p>

> **PRE-RELEASE COORDINATION REPOSITORY — NOT READY FOR PRODUCTION USE**
>
> This repository records the intended component set and release process. The
> component remotes and immutable submodule pointers have not been activated,
> so no installable C2Go release is published from this checkout yet.

## What this repository is

`c2go-toolchain` is the canonical release-coordination repository for C2Go. It
will pin one mutually compatible revision of each top-level component, record
the supported Go and C2Go ABI window, run fail-closed release checks, and host
the release notes and downloadable bundles for each coordinated release.

It is intentionally not a monorepo. Component development and history remain
in their own repositories; this repository becomes the source of truth for the
exact combination shipped under a C2Go toolchain version.

## Components

| Component | Planned repository | Mount point | Responsibility | License boundary |
| --- | --- | --- | --- | --- |
| c2go-clang | `c2gohq/c2go-clang` | `components/c2go-clang` | LLVM/Clang-based C2Go frontend, lowering, `c2go-lto`, and Plan 9 assembly emission | `Apache-2.0 WITH LLVM-exception`, plus existing third-party notices |
| c2go-bind | `c2gohq/c2go-bind` | `components/c2go-bind` | Converts C2Go assembly and manifests into Go packages | Original C2Go material: `AGPL-3.0-only` or a separate commercial agreement; third-party portions retain their licenses |
| c2go-libc | `c2gohq/c2go-libc` | `components/c2go-libc` | Runtime C-library compatibility and Go runtime bridges | Mixed work: original C2Go material plus musl and other third-party material under their own terms |

The modified `c2gohq/musl` fork is a nested, commit-pinned dependency owned by
the c2go-libc release. It is not a fourth top-level toolchain component.

## Pipeline

```text
C source
   |
   v
c2go-clang + c2go-lto
   |  Plan 9 assembly + export manifest
   v
c2go-bind
   |  generated Go package
   v
c2go-libc + Go toolchain
   |
   v
Go executable or library
```

## Current state

The repository is deliberately fail-closed:

- `.gitmodules` is not created until all three `c2gohq` component repositories
  exist and the intended commits are reachable;
- [toolchain.lock.json](toolchain.lock.json) uses `null` revisions and tags
  until real immutable values can be recorded;
- the default release verifier must fail while those values are unset; and
- the provisional compatibility window is Go 1.25.x and C2Go ABI epoch 1,
  subject to clean-checkout release validation.

Validate only the scaffold structure with:

```sh
python3 scripts/verify-release.py --structure-only
```

The actual release gate is intentionally stricter:

```sh
python3 scripts/verify-release.py
```

It will not pass until the component remotes, submodule gitlinks, tags,
revisions, recursive dependencies, and clean working trees all agree.

## First release

The first public build should be a release candidate such as
`v0.1.0-rc.1`, not a stable `v0.1.0`. Before that tag, the project must close
the component-level provenance, generated-artifact, musl, `c2go_libc/dl`,
clean-clone, and platform-test blockers documented in the component
repositories.

See [RELEASING.md](RELEASING.md) for the activation and release sequence. Do
not publish `git clone --recursive` installation instructions until the
submodules and the release gate are live.

## Repository layout

```text
.
├── assets/                 Project branding and provenance notes
├── components/             Future pinned top-level submodules
├── scripts/                Fail-closed release validation
├── toolchain.lock.json     Coordinated version and revision manifest
├── RELEASING.md            Release procedure
├── LICENSING*.md           Aggregate and component license boundaries
├── COMMERCIAL-LICENSING*   Commercial intent; not a license grant
└── TRADEMARKS.md           Name and logo policy
```

## Licensing and branding

Original coordination documentation and scripts in this repository are
available under GNU AGPL version 3 only, with alternative commercial terms
available only under a separately executed agreement. Every component and
generated artifact retains its own applicable license boundary; inclusion as a
submodule does not relicense it.

The C2Go name and logo are branding assets and are not licensed as software
under AGPL merely because they are stored here. See [LICENSE](LICENSE),
[LICENSING.md](LICENSING.md), [COMMERCIAL-LICENSING.md](COMMERCIAL-LICENSING.md),
[NOTICE](NOTICE), and [TRADEMARKS.md](TRADEMARKS.md).

GitHub Sponsors may be designated as a payment channel in a separately
executed commercial agreement. A sponsorship payment alone grants no software
or trademark rights.

## Contributing

Code contributions are not accepted until the project adopts an appropriate
contributor agreement preserving commercial-relicensing rights. Bug reports,
release reproducibility findings, and original documentation feedback are
welcome once the public issue tracker is available. See
[CONTRIBUTING.md](CONTRIBUTING.md).
