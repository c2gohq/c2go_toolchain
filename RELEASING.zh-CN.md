# 发布 C2Go Toolchain

[English](RELEASING.md)

本流程默认拒绝不完整发布。准备过的本地 checkout、尚未推送的 commit 或单个
组件测试通过，都不能作为 release 证据。

## 1. 先发布组件仓库

首先创建并填充以下受控仓库：

- `https://github.com/c2gohq/c2go_clang.git`
- `https://github.com/c2gohq/c2go_bind.git`
- `https://github.com/c2gohq/c2go_libc.git`
- `https://github.com/c2gohq/musl.git`

c2go-clang fork 不得继续以上游 LLVM 仓库作为 push 目标；必须保留上游历史和
全部 LLVM 声明。

添加 submodule 前，应确认每个 release commit 均可从公开远端访问，并确认
c2go-libc 已把目标 musl commit 作为自己的嵌套 submodule 固定。

## 2. 初始化顶层 submodule

这些 submodule 已登记在 `.gitmodules` 中。全新 checkout 应执行：

```sh
git submodule sync --recursive
git submodule update --init --recursive
```

每个组件必须 checkout 到已复核、不可变的 commit；release 不能指向移动分支。

## 3. 关闭组件发布阻断项

至少应从 clean recursive clone 验证：

1. c2go-clang 能构建配套编译器，并通过选定的 Clang、LLVM、C2Go 和跨仓测试。
2. c2go-bind 通过 test、race、vet、build 和跨仓 LIT。
3. c2go-libc 已包含或不再依赖 `c2go_libc/dl`，使用真实 musl submodule，交付
   或可复现生成承诺的全部目标产物，并通过经过复核的平台矩阵。
4. Apple/FreeBSD/XNU/MinGW/musl/Go/PureGo 等来源、声明和完整源码义务全部闭环。
5. 商业许可方、贡献者协议和公开联系/付款流程已经具备法律发布条件，且不改变
   第三方材料的权利。

## 4. 锁定版本

统一 release 在三个顶层组件使用同一个 tag。协同发布版本格式为：

```text
vMAJOR.YYYYMMDD.REVISION[-rc.N]
```

- `MAJOR` 是兼容线；公开契约仍处于 pre-1.0 阶段时保持为 `0`。
- `YYYYMMDD` 是在 UTC 下建立协同 release 版本线的日期。
- `REVISION` 从 `0` 开始；同一天需要额外发布维护版本（例如正式发布后的修正）
  时递增。
- `-rc.N` 表示同一个基础版本的连续候选版；候选期修复只递增 `N`，只有把最后
  一个候选版的精确快照提升为稳定版时才移除后缀。

例如，候选期修复应从 `v0.20260729.0-rc.1` 升到
`v0.20260729.0-rc.2`；对应稳定版为 `v0.20260729.0`。如果当天还要发布维护
版本，则从 `v0.20260729.1-rc.1` 开始。组件和依赖的精确 revision 应写入 lock
文件，而不是塞进版本字符串。

这种“SemVer 外壳中的 CalVer”可以让统一 tag 继续适用于当前不带主版本后缀的
Go module path。不要使用 `vYYYY.MM.DD`：带前导零的月、日不是合法 SemVer
数字字段，把年份放在 SemVer 主版本位置还会要求 Go module path 带对应的
`/vYYYY` 后缀。建议的首个公开候选版本是 `v0.20260729.0-rc.1`。未来把
`MAJOR` 提升到 `1` 以上之前，必须把 Go module path 迁移到相应的 `/vN`
后缀，或明确解除组件 tag 与 toolchain tag 的绑定。

更新 [toolchain.lock.json](toolchain.lock.json)：

- 填写 `release.version`、`release.status` 和 `release.published_at`；
- 为每个组件和嵌套依赖填写完整 commit hash 与 tag；
- Go 版本窗口和 C2Go ABI epoch 只能依据已验证证据修改；
- submodule gitlink 与 lock 文件必须在同一个 commit 中提交。

英文 GitHub Release 正文应保存为 `RELEASE_NOTES/<version>.md`；可同时提供
`RELEASE_NOTES/<version>.zh-CN.md` 中文版本。正式 tag 对应的英文 release
note 缺失时，workflow 必须失败。

## 5. 执行 release gate

在本仓库的 clean recursive clone 中执行：

```sh
git submodule update --init --recursive
python3 scripts/verify-release.py
```

然后运行各组件记录的构建/测试矩阵，并保存机器可读日志作为 release 证据。

推送经过复核的 commit 后、创建 tag 前，使用候选版本手动运行
`Release C2Go toolchain` workflow。该步骤是 unsigned dry run：它会执行与
正式发布相同的四个原生构建任务和完整源码打包，但不会创建 GitHub Release。

## 6. 构建发布产物

本仓库的普通 Git archive 不包含 submodule 内容。必须生成完整源码包：其中包含
或能够以合规、可复现方式取得构建发布产物时使用的每个精确组件及嵌套依赖。

每个二进制或源码包都应发布：

- 文件名、平台、架构和 toolchain 版本；
- SHA-256；
- 所有组件和嵌套依赖的精确 revision；
- 适用的许可证和第三方声明包；
- 可复现构建说明及 bootstrap 工具；
- 条件允许时提供 SBOM/来源数据。

当前 workflow 对两个 Linux 架构使用 Ubuntu 22.04，对 Windows amd64 使用
Windows Server 2022，对 macOS arm64 使用 macOS 14，并设置
`CMAKE_OSX_DEPLOYMENT_TARGET=11.0`。它会生成未签名的确定性压缩包、递归完整
源码包、checksum sidecar 和 `SHA256SUMS`。在取得相应凭据并确定策略前，不会
配置签名、Apple notarization 或 Windows Authenticode。

## 7. Tag 与发布

先为经过复核的组件 commit 打 tag，再为 gitlink 和 lock 文件精确引用这些 commit
的 c2go-toolchain commit 打 tag。推送该 tag 后，workflow 会使用仓库自动提供的
`GITHUB_TOKEN` 构建产物并创建 GitHub Release 草稿，无需 personal access token。
人工检查产物、声明、checksum 和安装 smoke test 后，再发布该草稿。

不得移动或替换已经发布的 tag；修正应使用新的候选版或补丁版本。
