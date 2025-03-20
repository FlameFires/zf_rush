# zf_rush - 高性能异步 API 客户端框架

## 特性

-   🚀 异步并发请求支持
-   🔄 自动重试机制
-   🕶️ 代理池支持
-   🔒 签名验证系统
-   📦 易扩展架构

## 快速开始

```bash
pip install zf_rush
```

## 基础用法

```python
from zf_rush import AppConfig, CacheData, Scheduler, RushClient

# 配置初始化
config = AppConfig(
    concurrency=10,
    max_requests=1000,
    request_delay=0.3
)

cache = CacheData(enabled=False)  # 禁用缓存

# 创建调度器
scheduler = Scheduler(
    app_config=config,
    cache_data=cache
)

# 启动任务
asyncio.run(scheduler.start())
```

## 高级用法

### 扩展配置

```python
from zf_rush import AppConfig

class MyConfig(AppConfig):
    api_endpoint: str = "https://api.example.com"
    custom_timeout: int = 30

config = MyConfig()
```

### 自定义客户端

```python
from zf_rush import RushClient

class MyClient(RushClient):
    async def perform_action(self, action: str, *args, **kwargs):
        if action == "custom":
            return await self._custom_method()
        return await super().perform_action(action, *args, **kwargs)

    async def _custom_method(self):
        # 自定义实现
        pass
```

## 贡献

欢迎提交 PR 和 Issue

1. **模块化设计**：

-   独立代理模块
-   分离工具函数
-   明确的模块职责划分

2. **可扩展性**：

-   基于继承的配置扩展
-   可插拔的缓存系统
-   开放的客户端/调度器接口

3. **易用性**：

-   类型提示完善
-   灵活的配置选项
-   详细的文档示例

是否需要针对某个具体模块的实现进行详细说明？或者需要补充其他功能的实现细节？
