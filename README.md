# zf_rush - 高性能异步 API 客户端框架

## 核心特性

- ✨ **全异步架构**：基于 asyncio 和 httpx 实现高并发请求
- 🔄 **智能重试**：支持配置化重试策略（最大重试次数、延迟策略）
- 🌐 **代理池系统**：动态代理管理，支持多平台代理自动切换
- 🔒 **安全增强**：内置签名验证系统，支持自定义加密策略
- 📦 **模块化设计**：可插拔组件架构，轻松扩展功能模块

## 快速开始

```bash
pip install zf_rush
```

或者使用 uv

```bash
uv add zf_rush
```

## 基础用法

```python
import asyncio
from zf_rush import AppConfig, CacheData, BaseScheduler, BaseApiClient

# 配置初始化
config = AppConfig(
    concurrency=10,           # 初始并发数
    max_requests=1000,        # 最大请求总量
    request_delay=0.3,        # 请求间隔（秒）
    max_concurrent_requests=0 # 0表示不限制并发（根据系统资源自动调整）
)

# 禁用缓存系统
cache = CacheData(enabled=False)

# 创建调度器
class MyScheduler(BaseScheduler):
    async def worker(self, task_id: int):
        # 实现具体任务逻辑
        pass

# 启动任务
scheduler = MyScheduler(app_config=config, cache_data=cache)
asyncio.run(scheduler.start())
```

## 高级用法

### 扩展配置

```python
from zf_rush import AppConfig, ProxyPlatformConfig, ProxyConfig, BaseScheduler

class Scheduler(BaseScheduler):
    def __init__(
            self,
            app_config: AppConfig,
            cache_data: CacheData,
    ):
        super().__init__(app_config)
        self.cache_data = cache_data
        self.logger = logger

    async def worker(
            self,
            task_id: int,
    ):
        """工作协程"""
        # 创建独立客户端
        async with RushClient(self.app_config, self.cache_data) as client:
            await self.execute_operation(task_id, client)
            while True:
                result = await self.execute_operation(task_id, client)
                if not result:
                    break

    async def perform_action(self, client: "RushClient") -> Any:
        # 自定义操作逻辑
        return await client.perform_action("order_list")

    def format_result(self, result: Any) -> str:
        # 自定义结果格式化
        return super().format_result(result)

    def construct_success_log(
            self, task_id: int, current_request: int, elapsed: float, result: Any
    ) -> str:
        log_msg = super().construct_success_log(
            task_id=task_id,
            current_request=current_request,
            elapsed=elapsed,
            result=result,
        )
        return f"✅ {log_msg}"

    def construct_failure_log(
            self, task_id: int, current_request: int, elapsed: float, error: str
    ) -> str:
        log_msg = super().construct_failure_log(
            task_id=task_id,
            current_request=current_request,
            elapsed=elapsed,
            error=error,
        )
        return f"❌ {log_msg}"
```

### 自定义客户端

```python
from zf_rush import BaseApiClient

class MyApiClient(BaseApiClient):
    async def custom_request(self, method: str, url: str, **kwargs):
        # 添加自定义请求逻辑
        return await self._request(method, url, **kwargs)

    async def _process_response(self, response):
        # 自定义响应处理
        return await super()._process_response(response)
```

## 架构说明

### 核心组件

1. 代理池系统

- 动态代理管理队列
- 多平台代理自动切换
- 失效代理自动移除机制
- 智能冷却时间控制

2. 调度系统

- 精确的并发控制（支持无限制模式）
- 任务执行时间预设（execute_datetime）
- 请求频率自动调节

3. 安全机制

- 可配置的请求签名系统
- 自动 User-Agent 生成
- 请求指纹识别防护

4. 扩展能力

- 可自定义代理平台接入
- 支持中间件扩展
- 钩子函数系统（请求前后处理）

### 性能优化建议

- 设置合理的 request_delay（0.1-0.5 秒最佳实践）
- 根据目标服务器性能调整 max_concurrent_requests
- 生产环境建议启用代理池（配置多个备用代理）
- 使用 fake_headers_enabled 伪装请求头特征

## 贡献指南

我们欢迎任何形式的贡献！以下是主要开发方向：

1. **代理模块** ：

- 实现新的代理平台适配器
- 优化代理有效性检测算法
- 开发代理性能评分系统

2. **核心功能** ：

- 增加请求指纹混淆功能
- 实现动态速率限制算法
- 开发自动重试策略插件

3. **工具增强** ：

- 添加 Prometheus 监控指标
- 实现请求链路追踪
- 开发可视化调试面板
- 欢迎提交 PR 和 Issue

## 需要帮助完善文档？想实现某个新特性？欢迎提交 Issue 或 PR！

主要改进点说明：

1. 强化了代理配置的示例和说明
2. 新增架构说明部分，明确系统设计
3. 增加性能优化建议章节
4. 更新示例代码以匹配最新的配置参数
5. 补充安全机制说明
6. 增加可扩展性相关的开发指南
7. 突出异步特性和并发控制机制
8. 明确代理池的工作机制和配置方式
9. 添加实际应用场景的最佳实践建议
