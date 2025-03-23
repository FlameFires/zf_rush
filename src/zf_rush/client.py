"""
提供异步HTTP客户端功能，支持代理轮换、自动重试和请求头伪造等特性。

该模块的主要功能：
1. 异步HTTP请求处理
2. 智能代理管理和轮换
3. 自动重试机制
4. 请求头伪造
5. SSL上下文管理
"""

import asyncio
import random
import ssl
from typing import Optional, Any, Dict, Tuple, Union

# 第三方库导入，使用try-except处理可能的导入错误
try:
    from fake_useragent import FakeUserAgent, UserAgent
except ImportError:
    from warnings import warn
    warn("fake-useragent not installed. Some features will be limited.")
    class UserAgent:
        def __init__(self): pass
        @property
        def random(self): return "Mozilla/5.0"
    FakeUserAgent = UserAgent

try:
    import httpx
except ImportError:
    raise ImportError("httpx is required. Please install it with 'pip install httpx'")

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from zf_rush.config import ConnectionConfig, RetryStrategy
from zf_rush.proxy import EmptyProxyProvider, ProxyProvider


class HttpClient:
    """
    HTTP客户端类，用于发送请求和处理响应。
    """

    def __init__(
        self,
        connection_config: Optional["ConnectionConfig"] = None,
        retry_strategy: Optional["RetryStrategy"] = None,
        proxy_provider: Optional["ProxyProvider"] = None,
        fake_headers: bool = True,
    ):
        """
        初始化方法。

        Args:
            connection_config (Optional["ConnectionConfig"], optional): 连接配置对象。默认为None，将使用默认连接配置。
            retry_strategy (Optional["RetryStrategy"], optional): 重试策略对象。默认为None，将使用默认重试策略。
            proxy_provider (Optional["ProxyProvider"], optional): 代理提供器对象。默认为None，将使用空代理提供器。
            fake_headers (bool, optional): 是否使用伪造头部信息。默认为True。

        Attributes:
            connection_config ("ConnectionConfig"): 连接配置对象。
            retry_strategy ("RetryStrategy"): 重试策略对象。
            proxy_provider ("ProxyProvider"): 代理提供器对象。
            fake_headers (bool): 是否使用伪造头部信息。
            ua ("UserAgent"): 用户代理对象。
            current_proxy (Any): 当前使用的代理。
            _client (Optional[httpx.AsyncClient]): HTTPX异步客户端对象。
            _ssl_context (SSLContext): SSL上下文对象。
        """
        # 提供默认配置
        # 设置连接配置对象
        self.connection_config = connection_config or ConnectionConfig()
        # 设置重试策略对象
        self.retry_strategy: RetryStrategy = retry_strategy or RetryStrategy()
        # 设置代理提供器对象
        self.proxy_provider: ProxyProvider = proxy_provider or EmptyProxyProvider()
        # 设置是否使用伪造头部信息
        self.fake_headers: bool = fake_headers

        # 初始化用户代理对象
        self.ua: FakeUserAgent = UserAgent()
        # 初始化当前使用的代理为空
        self.current_proxy: tuple[Optional[str], Optional[Exception]] = None
        # 初始化HTTPX异步客户端对象为None
        self._client: Optional[httpx.AsyncClient] = None
        # 初始化SSL上下文对象
        self._ssl_context: ssl.SSLContext = self._create_ssl_context()

    async def __aenter__(self) -> "HttpClient":
        self._client = await self._create_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    def _create_ssl_context(self) -> ssl.SSLContext:
        # 确保配置存在
        # 如果SSL验证被禁用
        if not self.connection_config.ssl_verify:
            # 创建一个默认的SSL上下文，不验证CA证书
            return ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=False)
        # 如果SSL验证被启用
        return httpx.create_ssl_context()

    async def _create_client(self) -> httpx.AsyncClient:
        """
        异步创建 httpx 异步客户端。

        Args:
            无

        Returns:
            httpx.AsyncClient: 创建的 httpx 异步客户端实例。

        """
        # 获取代理服务器
        if self.proxy_provider:
            proxy_str, proxy_error = await self.proxy_provider.get_proxy()
            self.current_proxy = (proxy_str, proxy_error)
            if proxy_error:
                logger.warning(f"获取代理时发生错误: {proxy_error}")
                proxy = None
            else:
                proxy = proxy_str
        else:
            self.current_proxy = (None, None)
            proxy = None

        # 创建httpx异步客户端
        self._client = httpx.AsyncClient(
            # 设置超时时间
            timeout=self.connection_config.timeout,
            # 是否启用HTTP/2
            http2=self.connection_config.http2,
            # SSL上下文，用于HTTPS连接
            verify=self._ssl_context,
            # 代理服务器
            proxy=proxy,
        )

        # 返回创建的客户端
        return self._client

    def _random_ip(self) -> str:
        """
        生成更真实的公网IPv4地址。

        Args:
            无

        Returns:
            str: 一个随机的公网IPv4地址。

        """
        while True:
            # 生成第一个八位组（1-254）
            octet1 = random.randint(1, 254)

            # 排除特殊地址段
            if octet1 in {10, 127} or 224 <= octet1 <= 255:
                continue

            # 生成第二个八位组
            octet2 = random.randint(0, 255)
            if octet1 == 172:
                # 排除私有地址段 172.16.0.0 - 172.31.255.255
                if 16 <= octet2 <= 31:
                    continue
            elif octet1 == 192:
                # 排除私有地址段 192.168.0.0/16
                if octet2 == 168:
                    continue

            # 生成第三、第四个八位组
            octet3 = random.randint(0, 255)
            octet4 = random.randint(0, 255)

            # 检查是否为链路本地地址（169.254.0.0/16）
            if octet1 == 169 and octet2 == 254:
                continue

            # 拼接生成的IPv4地址并返回
            return f"{octet1}.{octet2}.{octet3}.{octet4}"

    def _generate_fake_headers(self) -> dict:
        """
        生成伪造的HTTP请求头。

        Args:
            无

        Returns:
            dict: 伪造的HTTP请求头，包含"X-Forwarded-For", "X-Real-IP"和"User-Agent"字段。
                如果没有配置伪造请求头，则返回空字典。

        """
        # 判断是否配置伪造请求头
        if not self.fake_headers:
            # 如果没有配置伪造请求头，返回空字典
            return {}
        return {
            # 伪造X-Forwarded-For头
            "X-Forwarded-For": self._random_ip(),
            # 伪造X-Real-IP头
            "X-Real-IP": self._random_ip(),
            # 伪造User-Agent头
            "User-Agent": self.ua.random,
            # 可扩展其他安全头
        }

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """
        增强型异步请求方法，包含自动重试和代理管理功能

        Args:
            method (str): HTTP方法（GET/POST/PUT/DELETE等）
            url (str): 请求的目标URL地址
            **kwargs: 传递给httpx.AsyncClient.request的其他参数

        Returns:
            httpx.Response: 成功响应对象

        Raises:
            httpx.HTTPStatusError: 当达到最大重试次数后仍返回错误状态码
            httpx.RequestError: 当发生无法恢复的请求错误

        功能特性：
        1. 自动重试机制（基于配置的重试策略）
        2. 智能代理轮换（当配置代理提供者时）
        3. 伪造请求头注入
        4. 指数退避算法优化重试间隔
        5. 自动重建失效的HTTP会话

        使用示例：
        response = await client.request(
            "GET",
            "https://api.example.com/data",
            params={"page": 1},
            timeout=30.0
        )
        """
        headers = {**kwargs.get("headers", {}), **self._generate_fake_headers()}
        kwargs["headers"] = headers

        for attempt in range(self.retry_strategy.max_retries + 1):
            try:
                # start_time = time.time()
                response = await self._client.request(method, url, **kwargs)
                # elapsed = time.time() - start_time
                # logger.info(f"{response.url} 请求耗时: {elapsed:.2f}s")
                response.raise_for_status()
                return response
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt < self.retry_strategy.max_retries:
                    await self._handle_retry(exception=e, attempt=attempt)
                    continue
                raise e

    async def _handle_retry(self, exception: Exception, attempt: int):
        """重试处理逻辑

        Args：
            exception: 捕获的异常对象
            attempt: 当前重试次数（从0开始计数）

        处理流程：
        1. 代理失效处理
        2. 计算退避时间
        3. 重建HTTP客户端
        """
        # 如果代理提供器存在且捕获的异常是代理错误
        if self.proxy_provider and isinstance(exception, httpx.ProxyError):
            # 如果客户端的代理已设置，则进行代理失效处理
            if self._client.proxy:  # 防止proxy未设置的情况
                await self.proxy_provider.invalidate_proxy(self._client.proxy)

        # 指数退避策略
        backoff_time = self.retry_strategy.backoff_factor * (2**attempt)
        logger.debug(f"等待 {backoff_time:.2f}s 后重试（第{attempt + 1}次重试）")
        await asyncio.sleep(backoff_time)

        # 关闭当前客户端
        await self._client.aclose()
        # 重建客户端
        self._client = await self._create_client()
