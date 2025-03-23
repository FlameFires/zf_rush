# 基础配置类
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
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
