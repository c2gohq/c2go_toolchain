# 发布 C2Go Toolchain

[English](RELEASING.md)

本流程默认拒绝不完整发布。准备过的本地 checkout、尚未推送的 commit 或单个
组件测试通过，都不能作为 release 证据。

## 1. 先发布组件仓库

首先创建并填充以下受控仓库：

- `https://github.com/c2gohq/c2go-clang.git`
- `https://github.com/c2gohq/c2go-bind.git`
- `https://github.com/c2gohq/c2go-libc.git`
- `https://github.com/c2gohq/musl.git`

c2go-clang fork 不得继续以上游 LLVM 仓库作为 push 目标；必须保留上游历史和
全部 LLVM 声明。

添加 submodule 前，应确认每个 release commit 均可从公开远端访问，并确认
c2go-libc 已把目标 musl commit 作为自己的嵌套 submodule 固定。

## 2. 启用顶层 submodule

仅在上述远端真实存在后执行：

```sh
git submodule add https://github.com/c2gohq/c2go-clang.git components/c2go-clang
git submodule add https://github.com/c2gohq/c2go-bind.git components/c2go-bind
git submodule add https://github.com/c2gohq/c2go-libc.git components/c2go-libc
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

统一 release 通常在三个顶层组件使用同一版本号。首个公开候选版本应为
`v0.1.0-rc.1`。

更新 [toolchain.lock.json](toolchain.lock.json)：

- 填写 `release.version`、`release.status` 和 `release.published_at`；
- 为每个组件和嵌套依赖填写完整 commit hash 与 tag；
- Go 版本窗口和 C2Go ABI epoch 只能依据已验证证据修改；
- submodule gitlink 与 lock 文件必须在同一个 commit 中提交。

## 5. 执行 release gate

在本仓库的 clean recursive clone 中执行：

```sh
git submodule update --init --recursive
python3 scripts/verify-release.py
```

然后运行各组件记录的构建/测试矩阵，并保存机器可读日志作为 release 证据。

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

## 7. Tag 与发布

先为经过复核的组件 commit 打 tag，再为 gitlink 和 lock 文件精确引用这些 commit
的 c2go-toolchain commit 打 tag。创建 GitHub Release 草稿，上传已验证产物，
人工检查声明与 checksum 后再正式发布。

不得移动或替换已经发布的 tag；修正应使用新的候选版或补丁版本。
