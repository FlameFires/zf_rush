"""
zf_rush - 一个高效的异步HTTP请求库，支持并发控制、代理轮换和请求调度。

该模块提供了一系列工具和装饰器，用于简化异步HTTP请求的处理，
特别适合需要大量并发请求、定时执行和代理轮换的场景。
"""

# 暴露公共 API
from .async_decorators import concurrent, delayed, http_client, scheduled
from .client import HttpClient
from .config import AppConfig, ConnectionConfig, RetryStrategy
from .proxy import (
    DebugProxyProvider,
    EmptyProxyProvider,
    ProxyProvider,
    RotatingProxyProvider,
    YiProxyProvider,
)

__all__ = [
    # 装饰器
    "concurrent",
    "delayed",
    "http_client",
    "scheduled",
    # HTTP客户端
    "HttpClient",
    # 配置类
    "AppConfig",
    "ConnectionConfig",
    "RetryStrategy",
    
    # 代理提供者
    "ProxyProvider",
    "EmptyProxyProvider",
    "DebugProxyProvider",
    "RotatingProxyProvider",
    "YiProxyProvider",
]