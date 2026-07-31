<p align="center">
  <img src="assets/c2gohq-logo.png" width="240" alt="C2Go 标志">
</p>

<h1 align="center">C2Go Toolchain</h1>

<p align="center">
  一套协同发布的 C 到 Go 编译器、绑定生成器和运行时兼容层。
</p>

<p align="center">
  <a href="README.md">English</a>
</p>

> **预发布协调仓库——尚不能用于生产环境**
>
> 本仓库已通过 Git submodule 固定当前协同候选版本
> `v0.20260729.0-rc.3`。这是未签名的评估版本，尚不能作为生产工具链使用。

## 本仓库的职责

`c2go-toolchain` 是 C2Go 的权威发布协调仓库。它固定三个顶层组件的候选
revision，记录支持的 Go 版本和 C2Go ABI 范围，执行默认拒绝发布的检查，并
统一承载 release notes 与下载包。

它不是 monorepo。各组件仍在自己的仓库中开发并保留独立历史；本仓库只对某个
C2Go toolchain 版本实际包含的精确组合负责。

## 组件

| 组件 | 仓库 | 挂载路径 | 职责 | 许可边界 |
| --- | --- | --- | --- | --- |
| c2go-clang | `c2gohq/c2go_clang` | `components/c2go-clang` | 基于 LLVM/Clang 的 C2Go 前端、lowering、`c2go-lto` 与 Plan 9 汇编输出 | `Apache-2.0 WITH LLVM-exception`，以及原有第三方声明 |
| c2go-bind | `c2gohq/c2go_bind` | `components/c2go-bind` | 将 C2Go 汇编和 manifest 转换成 Go 包 | C2Go 原创材料为 `AGPL-3.0-only` 或另行商业协议；第三方部分保留原许可 |
| c2go-libc | `c2gohq/c2go_libc` | `components/c2go-libc` | C 库运行时兼容层和 Go runtime bridge | 混合项目：C2Go 原创材料、musl 及其他第三方材料分别适用各自条款 |

修改后的 `c2gohq/musl` fork 是由 c2go-libc release 管理并固定 commit 的嵌套
依赖，不是第四个顶层 toolchain 组件。

## 流水线

```text
C 源码
  |
  v
c2go-clang + c2go-lto
  |  Plan 9 汇编 + export manifest
  v
c2go-bind
  |  生成的 Go 包
  v
c2go-libc + Go toolchain
  |
  v
Go 可执行文件或库
```

## 当前状态

本仓库有意采用 fail-closed 设计：

- `.gitmodules` 已记录三个公开组件远端，gitlink 固定到各远端可达的 commit；
- [toolchain.lock.json](toolchain.lock.json) 已记录这些精确 revision、统一 RC tag
  和不可变 release 元数据；
- release 元数据、远端 tag、组件 revision、递归依赖或干净工作树不一致时，正式
  release 校验必须失败；
- 候选版本的兼容范围为 Go 1.25.x 和 C2Go ABI epoch 1，并已由四目标原生 release
  dry run 覆盖。

只检查仓库骨架结构：

```sh
python3 scripts/verify-release.py --structure-only
```

真正的 release gate 更严格：

```sh
python3 scripts/verify-release.py
```

release 元数据、tag、组件 revision、递归依赖和干净工作树全部一致前，该命令
不会通过。

release workflow 也支持手动触发 unsigned dry run。它在 GitHub 托管的原生
runner 上完成构建和测试，并打包：

- Linux amd64/arm64（`.tar.gz`）、Windows amd64（`.zip`）和 macOS
  arm64（`.tar.gz`）的可搬移二进制 SDK；每个平台包只包含已安装的
  `bin/`、`include/`、`lib/`、`licenses/` 与 release 元数据；
- 一个递归完整的源码包；
- 每个文件的 SHA-256 sidecar 与汇总的 `SHA256SUMS`。

二进制 SDK 不再包含仓库 checkout、测试或源码树。每个原生 builder 会在上传前
解压自己的产物，检查精确的已安装头文件和许可文件集，不添加额外 `-I`
编译每个受支持的公共头文件，并完整跑通已打包工具的 C 到 Go smoke test。
对应源码由独立源码包提供。

推送协同 `v*` tag 后，workflow 会创建 GitHub Release **草稿**。草稿保留为
许可证、声明、checksum 和安装 smoke test 的人工门禁；workflow 不会覆盖已有
release，当前也不会对产物签名或公证。

## 版本规则与第一个版本

协同发布采用置于 SemVer 兼容外壳中的日期版本：

```text
vMAJOR.YYYYMMDD.REVISION[-rc.N]
```

`MAJOR` 表示兼容线（项目处于 pre-1.0 阶段时为 `0`），`YYYYMMDD` 表示在
UTC 下建立协同 release 版本线的日期；`REVISION` 从 `0` 开始，同一天发布另一
维护版本时递增。候选版本追加 `-rc.N`；精确依赖 revision 仍记录在
`toolchain.lock.json` 中。

当前公开候选版本是 `v0.20260729.0-rc.3`，不是稳定版本；它用于评估、可复现性
检查和兼容性测试。

初始化 submodule 和发布的完整顺序见
[RELEASING.zh-CN.md](RELEASING.zh-CN.md)。平台压缩包内置 SDK 专用中英文
README，包含匹配 runtime module 和 C 到 Go 快速上手说明。

## 仓库结构

```text
.
├── assets/                 品牌资源及来源说明
├── components/             固定 revision 的顶层 submodule
├── .github/workflows/      原生多平台 release 构建
├── SDK-README*.md          安装到二进制 SDK 的 README 模板
├── scripts/                release 校验与确定性打包
├── toolchain.lock.json     协同版本和 revision 清单
├── RELEASING*.md           发布流程
├── LICENSING*.md           聚合仓及组件许可边界
├── COMMERCIAL-LICENSING*   商业授权意图；不直接授予权利
└── TRADEMARKS.md           名称和 Logo 使用规则
```

## 许可与品牌

本仓库原创的协调文档和脚本按 GNU AGPL version 3 only 提供；替代商业条款
只能通过另行签署的协议取得。每个组件及生成物继续适用自己的许可边界，成为
submodule 不会改变其许可证。

C2Go 名称和 Logo 属于品牌资源，不会因为存放在本仓库中就自动作为软件按
AGPL 授权。详见 [LICENSE](LICENSE)、[LICENSING.zh-CN.md](LICENSING.zh-CN.md)、
[COMMERCIAL-LICENSING.zh-CN.md](COMMERCIAL-LICENSING.zh-CN.md)、[NOTICE](NOTICE)
和 [TRADEMARKS.md](TRADEMARKS.md)。

GitHub Sponsors 可以在另行签署的商业协议中被指定为付款渠道；赞助付款本身
不会授予软件或商标权利。

## 贡献

项目采用能够保留商业再授权能力的贡献者协议之前，不接受代码贡献。公开 issue
建立后，欢迎提交 bug、release 可复现性问题和原创文档反馈。详见
[CONTRIBUTING.md](CONTRIBUTING.md)。
