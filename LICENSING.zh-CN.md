# C2Go Toolchain 许可说明

[English](LICENSING.md)

本文解释许可证边界，不替代正式许可证文本或法律意见。

## 本协调仓库

除品牌资源及明确标识的第三方材料外，专为本仓库创作的原创文档和脚本按 GNU
Affero General Public License version 3 only（`AGPL-3.0-only`）许可，权威
正文为 [LICENSE](LICENSE)。

适用的版权所有者可以仅针对其有权控制的材料另行授予商业条款。没有另行签署
的协议，仅凭本仓库、GitHub Sponsors 付款或下载 release 都不会产生商业授权。
详见 [COMMERCIAL-LICENSING.zh-CN.md](COMMERCIAL-LICENSING.zh-CN.md)。

## 组件边界

本仓库通过 Git submodule 聚合独立许可的组件。聚合和版本固定不会替换或缩小
各组件原许可证：

- c2go-clang 继续适用 `Apache-2.0 WITH LLVM-exception` 以及已有逐文件和
  第三方声明；
- c2go-bind 原创材料计划按 `AGPL-3.0-only` 或另行商业协议提供，PureGo/Go
  派生部分和其他第三方部分保留原条款；
- c2go-libc 是包含 C2Go 原创、musl 派生和其他第三方材料的混合项目，各部分
  适用各自条款；
- musl fork 继续适用 musl 的宽松条款和逐文件声明。

C2Go 商业协议只能许可具名许可方有权控制的权利，不能重新许可 LLVM、musl、
Go、PureGo、Apple/FreeBSD/XNU/MinGW 材料、用户源码或其他第三方材料。

## 生成物

使用编译器或生成器本身不会转移用户输入的所有权。但生成包可能包含复制进去的
C2Go 支持代码和第三方派生支持模板；实际保留的部分继续适用相应许可证与声明。
发布包必须描述真实混合情况，不能把生成物的每个字节都标成 C2Go 完全所有或
全部适用 AGPL。

## 品牌资源

C2Go 名称和 Logo 不是软件源码，不包含在本仓库的 AGPL 授权中。除真实描述性
引用和经过授权的再发布中复制未修改的必要标识外，不授予商标许可。详见
[TRADEMARKS.md](TRADEMARKS.md)。
