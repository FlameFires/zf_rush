# zf_rush - 高性能异步 API 客户端框架

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/FlameFires/zf_rush/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

一个专注于高性能、易扩展的异步 API 客户端和任务调度框架。

## 特性

- ✨ **全异步架构**：基于 Python 3.12+ 的现代异步特性
- 🚀 **装饰器驱动**：通过装饰器优雅地实现并发控制、重试策略、延迟执行等功能
- 🌐 **智能代理**：内置多种代理提供方式，支持动态切换和失效处理
- 📝 **日志系统**：集成 loguru，提供美观的控制台输出和文件日志
- 🔄 **任务调度**：支持定时执行和并发控制
- 🛡️ **异常处理**：完善的错误处理和重试机制

## 安装

要求 Python 3.12 或更高版本。

```bash
pip install zf_rush
# 或使用 uv（推荐）
uv add zf_rush
```

## 快速开始

### 基础示例

```python
import asyncio
from loguru import logger
from zf_rush import concurrent, http_client
from zf_rush import HttpClient
from zf_rush import ConnectionConfig, RetryStrategy
from zf_rush import DebugProxyProvider

# 配置连接和重试策略
connection_config = ConnectionConfig(timeout=15.0, http2=True)
retry_strategy = RetryStrategy(max_retries=5)
proxy_provider = DebugProxyProvider("http://your-proxy:port/")

@concurrent(max_concurrent=2, max_requests=8)  # 控制并发和请求数
@http_client(
    connection_config=connection_config,
    retry_strategy=retry_strategy,
    proxy_provider=proxy_provider,
)
async def api_call(client: HttpClient, task_id: int, request_num: int):
    response = await client.request("GET", "https://api.example.com/")
    logger.info(f"TaskId-{task_id:02d} | Request-{request_num + 1:03d} | Response: {response.text[:50]}")

# 运行任务
async def main():
    await api_call()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
```

### 日志配置

```python
from loguru import logger
import sys

# 配置控制台日志
logger.remove()  # 移除默认处理器
logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <4.4}</level> | "
    "<level>{message}</level>",
    enqueue=True,
    colorize=False,
)

# 配置文件日志
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <4.4}</level> | "
    "<level>{message}</level>",
    rotation="00:00",  # 每天轮换
    compression="zip",  # 压缩旧日志
    level="INFO",
    enqueue=True,
    backtrace=True,
    diagnose=True,
)
```

### 高级用法：多重装饰器组合

```python
from zf_rush import concurrent, scheduled, delayed
from datetime import datetime

# 组合多个装饰器实现复杂功能
@scheduled(execute_time="2025-03-22 18:50:00")  # 定时执行
@concurrent(max_concurrent=2, max_requests=10)   # 并发控制
@delayed(delay=0.5)                             # 请求延迟
async def complex_task(task_id: int, request_num: int):
    # 任务实现
    pass

# 使用配置对象创建装饰器
from zf_rush.config import AppConfig

config = AppConfig(
    execute_time="2024-01-01 12:00:00",
    concurrency=5,
    max_requests=20,
    request_delay=0.5,
    retry_attempts=3,
)

def create_scheduler(config: AppConfig):
    def decorator(func):
        @scheduled(config.execute_time)
        @concurrent(config.concurrency, config.max_requests)
        @delayed(config.request_delay)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

@create_scheduler(config)
async def configured_task(task_id: int, request_num: int):
    # 任务实现
    pass
```

### 代理配置示例

```python
from zf_rush import DebugProxyProvider, RotatingProxyProvider, YiProxyProvider

# 调试代理
debug_proxy = DebugProxyProvider("http://debug-proxy:8080/")

# 轮转代理
rotating_proxy = RotatingProxyProvider([
    "http://proxy1:8080",
    "http://proxy2:8080"
])

# 易代理
yi_proxy = YiProxyProvider(
    "http://api.ydaili.cn/api?key=your_key"
)
```

## 核心组件

### 装饰器

- `@concurrent`: 控制并发数和最大请求数
- `@http_client`: 配置 HTTP 客户端（代理、重试、超时等）
- `@scheduled`: 定时执行任务
- `@delayed`: 添加请求延迟

### 配置类

- `ConnectionConfig`: HTTP 连接配置
- `RetryStrategy`: 重试策略配置
- `AppConfig`: 应用全局配置

### 代理提供者

- `DebugProxyProvider`: 用于调试的固定代理
- `RotatingProxyProvider`: 轮转多个代理
- `YiProxyProvider`: 易代理平台集成
- `ProxyProvider`: 自定义代理提供者的基类

## 项目依赖

- Python >= 3.12
- httpx[http2] >= 0.28.1
- fake-useragent >= 2.1.0
- loguru >= 0.7.3

## 最佳实践

1. **错误处理**

   - 使用 try-except 捕获具体异常
   - 实现合理的重试策略
   - 记录详细的错误日志
2. **性能优化**

   - 合理设置并发数和请求延迟
   - 使用 HTTP/2 提升性能
   - 启用代理池分散请求压力
3. **日志管理**

   - 配置合适的日志级别
   - 启用日志轮换和压缩
   - 记录关键性能指标

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 链接

- [项目主页](https://github.com/FlameFires/zf_rush/)
- [问题反馈](https://github.com/FlameFires/zf_rush/issues)
- [更新日志](https://github.com/FlameFires/zf_rush/releases)
