# 构建结构

UV 管理仓库工具依赖；根目录项目不作为 Python 分发包发布。`ci.fetch_sources`
在宿主机获取固定上游源码，原始来源记录保留在报告中。

`ci.build_wheels` 为每条上游版本线准备分发元数据，保留上游 `MySQLdb.release`
 和 C 扩展运行时版本。分发名与版本独立为 `mysqlclient-static` 和 `.postN`。

原生依赖每个平台构建一次。Linux 在 manylinux 2.28 自定义构建镜像中编译；
macOS 在 ARM64 runner 中编译。随后 cibuildwheel 使用静态归档的明确路径和上游
 setuptools 定义生成各 CPython wheel，构建 frontend 为 `build[uv]`。

Linux 采用 GNU linker 的归档符号隐藏和导出白名单。macOS 使用 Clang 隐藏可见
性与 Mach-O 导出白名单。认证插件和压缩插件静态内置，OpenSSL 不依赖外部模块。
最终 wheel 分别通过 ELF/Mach-O 审计。

`ci.plan` 定义测试组合，Linux Docker runner 和 macOS 原生 runner 共享账号创建、
认证检查、测试客户端、Django 应用和报告器。
macOS 使用 MySQL 8.0.46 和 8.4.13 验证平台路径；
Linux 覆盖四个指定数据库版本及发行版基线。

发布工作流复用同一套验证工作流。只有两个平台都完成才能上传；上传后从索引重新
安装并执行数据库测试。源码包按平台保留原始源码归档和本仓库构建材料。
