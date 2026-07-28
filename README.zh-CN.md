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
> 本仓库已通过 Git submodule 固定当前预发布组件快照，但尚未发布协同 tag 或
> 可安装的 C2Go 版本。

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
- [toolchain.lock.json](toolchain.lock.json) 已记录这些精确 revision，而 release
  tag 与协同发布元数据仍保持未设置；
- release 元数据或 tag 未填写时，正式 release 校验必须失败；
- 暂定兼容范围为 Go 1.25.x 和 C2Go ABI epoch 1，最终仍以 clean checkout
  的 release 验证为准。

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

- Linux amd64 与 arm64（`.tar.gz`）；
- Windows amd64（`.zip`）；
- macOS arm64（`.tar.gz`）；
- 一个递归完整的源码包；
- 每个文件的 SHA-256 sidecar 与汇总的 `SHA256SUMS`。

推送协同 `v*` tag 后，workflow 会创建 GitHub Release **草稿**。草稿保留为
许可证、声明、checksum 和安装 smoke test 的人工门禁；workflow 不会覆盖已有
release，当前也不会对产物签名或公证。

## 第一个版本

首个公开版本应为 `v0.1.0-rc.1` 之类的 release candidate，而不是稳定
`v0.1.0`。打 tag 前，必须关闭各组件记录的来源审计、生成物、musl、
`c2go_libc/dl`、clean clone 和平台测试阻断项。

初始化 submodule 和发布的完整顺序见
[RELEASING.zh-CN.md](RELEASING.zh-CN.md)。release gate 通过之前，不要发布
安装说明。

## 仓库结构

```text
.
├── assets/                 品牌资源及来源说明
├── components/             固定 revision 的顶层 submodule
├── .github/workflows/      原生多平台 release 构建
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
