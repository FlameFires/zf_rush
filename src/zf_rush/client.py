from abc import ABC, abstractmethod
from typing import Optional, Any, Union
import random
import ssl

import httpx
from loguru import logger
from fake_useragent import UserAgent

from .config import AppConfig
from .proxy import ProxyPool


class BaseApiClient(ABC):
    def __init__(
        self,
        app_config: AppConfig,
        proxy_pool: Optional[ProxyPool] = None,
        *args,
        **kwargs,
    ):
        # 应用配置
        self.app_config = app_config

        # 缓存数据
        # self.cache_data = cache_data

        # 代理配置
        self.proxy: Optional[str] = None

        # 请求客户端
        self._ssl_context = self._create_ssl_context()
        self._async_client: Optional[httpx.AsyncClient] = None

        # 代理池相关配置
        self.current_proxy = None
        self.proxy_pool = proxy_pool if proxy_pool else ProxyPool(app_config)
        self.max_retries = app_config.max_retries
        self.retry_status_codes = {429, 500, 502, 503, 504}
        self.retry_exceptions = (
            httpx.RequestError,
            httpx.ProxyError,
            httpx.ConnectTimeout,
            ConnectionResetError,
        )

        # 模拟UA
        self.fake_headers_enabled = getattr(app_config, "fake_headers_enabled", True)
        self.ua = UserAgent()

        # 日志消息
        self.execute_message = ""
        self.sign_message = ""

        # 其他数据
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        self._async_client = await self._create_http_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.proxy_pool:
            await self.proxy_pool.close()
        if self._async_client:
            await self._async_client.aclose()

    def _create_ssl_context(self):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("ALL")
        return ctx

    def process_cookies(self, cookies: Union[str, dict]) -> dict:
        default_cookies = {}
        if isinstance(cookies, str):
            # 解析字符串并合并到默认值
            cookie_dict = {}
            for pair in cookies.split(";"):
                key, value = pair.strip().split("=", 1)
                cookie_dict[key] = value
            default_cookies.update(cookie_dict)
            return default_cookies
        elif isinstance(cookies, dict):
            # 合并字典到默认值
            default_cookies.update(cookies)
            return default_cookies
        return default_cookies

    async def _create_http_client(self) -> httpx.AsyncClient:
        if self.proxy_pool:
            proxy = await self.proxy_pool.get_next_proxy()
            if proxy:
                self.current_proxy = proxy

        # 处理 cookies
        cookies = self.kwargs.get("cookies")
        processed_cookies = self.process_cookies(cookies) if cookies else None

        return httpx.AsyncClient(
            cookies=processed_cookies,
            timeout=self.app_config.request_timeout,
            http2=True,
            verify=self._ssl_context,
            proxy=self.current_proxy,
        )

    def _generate_fake_headers(self) -> dict:
        if not self.fake_headers_enabled:
            return {}
        return {
            "X-Forwarded-For": self._random_ip(),
            "X-Real-IP": self._random_ip(),
            "User-Agent": self.ua.random,
            "Accept-Language": random.choice(["zh-CN,zh;q=0.9", "en-US,en;q=0.5"]),
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            # 可扩展其他安全头
        }

    def _random_ip(self) -> str:
        """生成更真实的公网IPv4地址"""
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

            return f"{octet1}.{octet2}.{octet3}.{octet4}"

    async def _refresh_client(self):
        if self._async_client:
            await self._async_client.aclose()
        self._async_client = await self._create_http_client()

    async def _get_http_client(self) -> httpx.AsyncClient:
        if not self._async_client:
            self._async_client = await self._create_http_client()
        return self._async_client

    async def _request_with_retry(self, method: str, url: str, **kwargs) -> Any:
        # 在请求前添加伪装头
        headers = kwargs.get("headers", {}).copy()
        headers.update(self._generate_fake_headers())
        kwargs["headers"] = headers

        retries = 0
        while retries <= self.max_retries:
            try:
                client = await self._get_http_client()
                response = await client.request(method, url, **kwargs)
                if response.status_code in self.retry_status_codes:
                    raise httpx.HTTPStatusError(
                        f"请求失败，HTTP 状态码为 {response.status_code}，该状态码属于需要重试的范围。",
                        response=response,
                        request=response.request,
                    )
                return response
            except self.retry_exceptions as e:
                logger.warning(f"请求失败: {e}, 重试次数: {retries}/{self.max_retries}")
                await self.proxy_pool.get_next_proxy()
                await self._refresh_client()
                retries += 1
                if retries > self.max_retries:
                    logger.error("达到最大重试次数")
                    raise

    @abstractmethod
    async def perform_action(self, action: str, *args, **kwargs) -> Any:
        """统一操作入口，处理不同业务逻辑"""
        pass
