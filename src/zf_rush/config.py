"""
提供配置类，用于管理应用程序的各种设置。

包含以下配置类：
- AppConfig: 应用程序全局配置
- ConnectionConfig: HTTP连接相关配置
- RetryStrategy: 请求重试策略配置
"""

from dataclasses import dataclass
from typing import Optional, FrozenSet


@dataclass
class AppConfig:
    """
    应用程序全局配置类。

    属性:
        execute_time (Optional[str]): 计划执行时间，格式：YYYY-MM-DD HH:MM:SS
        concurrency (int): 最大并发请求数
        max_requests (int): 最大请求总数
        request_delay (float): 请求间隔时间（秒）
        retry_attempts (int): 失败重试次数
    """
    execute_time: Optional[str] = None  # 格式：YYYY-MM-DD HH:MM:SS
    concurrency: int = 1
    max_requests: int = 100
    request_delay: float = 0.1
    retry_attempts: int = 3


# 配置模块
@dataclass
class ConnectionConfig:
    """连接相关配置"""

    timeout: float = 10.0
    ssl_verify: bool = False
    max_connections: int = 100
    http2: bool = True


@dataclass
class RetryStrategy:
    """重试策略配置"""

    max_retries: int = 3
    retry_status_codes: set = frozenset({429, 500, 502, 503, 504})
    backoff_factor: float = 0.5
