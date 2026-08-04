# C2Go Toolchain SDK @C2GO_VERSION@

[English](README.md)

本压缩包是对应宿主平台可直接使用的 C2Go SDK，包含已安装的工具、C2Go C
头文件、Clang 运行资源和再分发所需的授权记录。包内不包含项目 checkout、测试、
构建脚本或 C/Go 源码树；精确的完整对应源码通过独立的 `-source` release 资产发布。

> **候选版本：**本 SDK 用于评估和兼容性测试，尚未签名，也不是生产版本。

## 目录结构

```text
.
├── bin/                         c2go-clang、c2go-lto、c2go-bind
├── include/                     c2go-libc 公共 C 头文件
├── lib/clang/<version>/         Clang resource，包含 c2go.h
├── licenses/                    各组件及第三方授权记录
├── BUILD-INFO.json              目标、版本、revision 与校验值
├── toolchain.lock.json          协同源码快照
└── LICENSE、NOTICE 等           工具链授权文档
```

SDK 可以整体移动，但 `bin/`、`include/` 和 `lib/` 必须位于同一个根目录下。
`c2go-clang` 在 `-fc2go` 模式会自动找到本包的 `include/` 和自身 resource 目录，不要
额外加入宿主系统 libc 的头文件目录。

## 环境要求

- Go 1.25.x 或 Go 1.26.x；Go 1.27 及以后版本在中央 toolchain contract
  provider 完成验证前会被拒绝。
- 与宿主 OS/架构匹配的平台压缩包。
- Go module 必须将 `github.com/c2gohq/c2go_libc` 固定到同一个协同版本
  `@C2GO_VERSION@`。

Go runtime 包有意通过带版本的 Go module 获取。预编译 Go package archive 会与
Go 版本、构建参数及依赖 build ID 绑定，不能作为通用 SDK 库分发。

## 快速开始

把 SDK 工具加入 `PATH`：

```sh
export C2GO_HOME=/absolute/path/to/c2go-toolchain-@C2GO_VERSION@-<target>
export PATH="$C2GO_HOME/bin:$PATH"
```

按照所下载的平台包选择 target triple：

| 平台包 | C2Go target triple |
| --- | --- |
| `linux-amd64` | `x86_64-unknown-linux-goabi` |
| `linux-arm64` | `aarch64-unknown-linux-goabi` |
| `windows-amd64` | `x86_64-pc-windows-goabi` |
| `macos-arm64` | `aarch64-apple-darwin` |

创建 Go module 并固定配套 runtime：

```sh
go mod init example.com/demo
go get github.com/c2gohq/c2go_libc@@C2GO_VERSION@
```

假设 `input.c` 为：

```c
#include <stdint.h>
#include <c2go.h>

c2go_extern int add(int a, int b) { return a + b; }
```

将它编译并绑定成 Go package（把 `$C2GO_TARGET` 换成表格中的对应 triple）：

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

`c2go-bind` 会把生成的 `.go`/`.s` package 文件及其生成代码授权记录写入
`translated/`。

## 校验与 macOS quarantine

解压前先校验 release 的 SHA-256。可以使用汇总文件：

```sh
sha256sum --check SHA256SUMS
```

macOS 包尚未 notarize。浏览器下载可能附加 Gatekeeper quarantine 属性。确认
SHA-256 后，如果 macOS 阻止执行，只移除已解压 SDK 目录上的 quarantine：

```sh
xattr -dr com.apple.quarantine "$C2GO_HOME"
```

精确组件 revision 见 `BUILD-INFO.json` 和 `toolchain.lock.json`。授权条款位于根
目录文档与 `licenses/`；再分发 SDK 或生成的支持代码时必须保留相关文件。
