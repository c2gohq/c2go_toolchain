# C2Go Toolchain SDK @C2GO_VERSION@

[简体中文](README.zh-CN.md)

This archive is the ready-to-use, native C2Go SDK for one host platform. It
contains installed tools, C2Go C headers, Clang runtime resources, and the
license records required for redistribution. It does not contain project
checkouts, tests, build scripts, or C/Go source trees; the exact corresponding
source is published as the separate `-source` release asset.

> **Release candidate:** this SDK is for evaluation and compatibility testing.
> It is unsigned and is not yet a production release.

## Layout

```text
.
├── bin/                         c2go-clang, c2go-lto, and c2go-bind
├── include/                     c2go-libc public C headers
├── lib/clang/<version>/         Clang resources, including c2go.h
├── licenses/                    component and third-party license records
├── BUILD-INFO.json              target, versions, revisions, and checksums
├── toolchain.lock.json          coordinated source snapshot
└── LICENSE, NOTICE, ...         toolchain licensing documents
```

The SDK is relocatable. Keep `bin/`, `include/`, and `lib/` under the same
directory. In `-fc2go` mode, the packaged `c2go-clang` finds `include/` and its own
resource directory automatically; do not add a host libc include directory.

## Requirements

- Go 1.25.x (Go 1.26 and later are outside this release's ABI window).
- The archive matching the host OS and architecture.
- A Go module that pins `github.com/c2gohq/c2go_libc` to the same coordinated
  version, `@C2GO_VERSION@`.

The Go runtime package is intentionally obtained as a versioned Go module. A
precompiled Go package archive is not portable across Go versions, build
settings, or dependency build IDs.

## Quick start

Add the SDK tools to `PATH`:

```sh
export C2GO_HOME=/absolute/path/to/c2go-toolchain-@C2GO_VERSION@-<target>
export PATH="$C2GO_HOME/bin:$PATH"
```

Choose the target triple matching the archive:

| Archive target | C2Go target triple |
| --- | --- |
| `linux-amd64` | `x86_64-unknown-linux-goabi` |
| `linux-arm64` | `aarch64-unknown-linux-goabi` |
| `windows-amd64` | `x86_64-pc-windows-goabi` |
| `macos-arm64` | `aarch64-apple-darwin` |

Create a Go module and pin the matched runtime:

```sh
go mod init example.com/demo
go get github.com/c2gohq/c2go_libc@@C2GO_VERSION@
```

For this `input.c`:

```c
#include <stdint.h>
#include <c2go.h>

c2go_extern int add(int a, int b) { return a + b; }
```

compile and bind it as a Go package (replace `$C2GO_TARGET` with the matching
triple from the table):

```sh
export C2GO_TARGET=aarch64-apple-darwin

c2go-clang --target="$C2GO_TARGET" \
  -fc2go \
  -fc2go-package=example.com/demo/translated \
  -O2 \
  -fc2go-emit-plan9-asm=translated.s \
  -fc2go-emit-manifest=translated.json \
  -c -o translated.o input.c

mkdir -p translated
c2go-bind \
  --out=translated \
  --sidecar=translated.json \
  translated.s

go test ./...
```

`c2go-bind` writes the generated `.go`/`.s` package files and their generated
licensing records into `translated/`.

## Verification and macOS quarantine

Verify the release checksum before extraction. The combined release file can
be checked with:

```sh
sha256sum --check SHA256SUMS
```

The macOS archive is not notarized. A browser download may attach Gatekeeper's
quarantine attribute. After verifying the checksum, if macOS blocks the tools,
remove quarantine only from the extracted SDK directory:

```sh
xattr -dr com.apple.quarantine "$C2GO_HOME"
```

See `BUILD-INFO.json` and `toolchain.lock.json` for the exact component
revisions. License terms are in the root documents and `licenses/`; preserve
them when redistributing the SDK or generated support code.
