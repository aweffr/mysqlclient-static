# 测试矩阵

精确的组合由 `ci.plan` 生成：

```bash
uv run python -m ci.plan
MCS_PLATFORM=macos uv run python -m ci.plan
```

| 测试组 | Linux AMD64 | macOS ARM64 |
|---|---:|---:|
| Driver | 56 | 28 |
| Django ORM | 34 | 18 |
| Gunicorn WSGI | 8 | 8 |
| Uvicorn ASGI | 8 | 8 |
| Celery prefork | 8 | 8 |
| 符号冲突注入 | 4 | 4 |
| Ubuntu / Rocky 运行 | 8 | 0 |
| 必测合计 | 126 | 74 |

Linux 另有 6 个 Django 6.1 / MySQL 8.0 组合标记为 EXCLUDED，不计入通过数。
macOS 使用 MySQL 8.0.46 和 8.4.13，另有两个 Django 6.1 / MySQL 8.0
组合标记为 EXCLUDED。

每种组合使用新数据库和新账号。首次 SHA-2 认证不会复用其他组合的缓存。最终报
告同时提供 Markdown、HTML、JSON 和 JUnit，保留实际版本和原始日志。

Driver 覆盖常规 Python 3.9–3.14 和自由线程版 3.14t。3.14t 检查导入驱动
前后、并发数据库操作和 cryptography 调用之后 GIL 均保持关闭。

`docs/local-validation.*` 和 `docs/validation/` 是附件中的历史实验记录。当前
发行结果以 GitHub Actions 的当轮报告为准。
