# 交付前本地验证

日期：2026-10-24。环境：Debian 13、AMD64、CPython 3.13.5。本环境没有 Docker，也不能从构建脚本下载外部源码。

| 已执行项目 | 结果 |
|---|---|
| 单元测试 | 44 项通过，无跳过 |
| Python 源码解析 | 28 个文件通过 Python 3.9 语法检查 |
| Bash 语法 | 3 个脚本通过 `bash -n` |
| 工作流 YAML 结构 | 触发器、单验证作业、发布依赖关系均通过本地解析检查 |
| 完整 mysqlclient 2.3.0 本机打包 | 生成 wheel 成功 |
| 包名、分发版本、原始运行时版本、导入 | 检查通过 |
| 最终扩展动态导出 | 仅 `PyInit__mysql` |
| 发布审计负向对照 | 正确拒绝本机生成的实验产物 |

本机打包使用已安装的 Debian 静态库，目的为检查新项目的打包元数据和链接导出规则。该实验没有使用 `versions.json` 固定的完整原生源码构建链，不属于正式 manylinux 产物。其 glibc 要求为 2.38，并残留系统 zstd 的四个弱回调，因此被项目的正式发布审计拒绝。

实验 wheel 未装入交付包，也未当作端到端通过结果。本机实验日志保留于 `docs/validation/`。机器可读状态见 `local-validation.json`。

尚待 GitHub Actions 实际执行的项目：固定原生依赖的 manylinux 构建、全部六个 ABI 的发布 wheel、118 个真实 MySQL / Django / HTTP / Celery 测试组合。工作流只会在这些必测组合全部通过后开放产物发布。
