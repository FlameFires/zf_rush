from abc import ABC, abstractmethod
from typing import Optional
import httpx


# 代理接口
class ProxyProvider(ABC):
    """代理提供者接口"""

    @abstractmethod
    async def get_proxy(self) -> tuple[Optional[str], Optional[Exception]]:
        pass

    @abstractmethod
    async def invalidate_proxy(self, proxy: str) -> None:
        pass


# 空代理实现
class EmptyProxyProvider(ProxyProvider):
    async def get_proxy(self) -> tuple[Optional[str], Optional[Exception]]:
        return None, None

    async def invalidate_proxy(self, proxy: str) -> None:
        # 无效化代理的逻辑块
        pass


# 调试代理实现
class DebugProxyProvider(ProxyProvider):
    def __init__(self, ip_port):
        """
        初始化代理对象。

        Args:
            ip_port (str): 代理服务器的IP地址和端口，格式为 'http://IP:PORT'。

        Raises:
            TypeError: 如果 ip_port 不是字符串类型。
            ValueError: 如果 ip_port 不是以 'http://' 开头。
        """
        if not isinstance(ip_port, str):
            raise TypeError("ip_port must be a string")
        if not ip_port.startswith("http://"):
            raise ValueError("ip_port must start with 'http://'")
        self.proxy = ip_port

    async def get_proxy(self) -> tuple[Optional[str], Optional[Exception]]:
        return self.proxy, None

    async def invalidate_proxy(self, proxy: str) -> None:
        pass


# 具体代理实现
class RotatingProxyProvider(ProxyProvider):
    def __init__(self, proxies: list):
        """
        初始化函数，用于设置代理列表和当前代理索引。

        Args:
            proxies (list): 包含代理地址的列表。

        Attributes:
            self.proxies (list): 存储传入的代理列表。
            self.current (int): 初始化为0，表示当前使用的代理索引。
        """
        self.proxies = proxies
        self.current = 0

    async def get_proxy(self) -> tuple[Optional[str], Optional[Exception]]:
        """
        获取当前代理服务器地址。

        Args:
            无

        Returns:
            Optional[str]: 返回当前代理服务器的地址。如果代理列表为空，则返回 None。

        """
        proxy = self.proxies[self.current]
        self.current = (self.current + 1) % len(self.proxies)
        return proxy, None

    async def invalidate_proxy(self, proxy: str) -> None:
        # 实际场景可能需要更复杂的处理
        pass


# 易代理实现
# 官网：https://www.ydaili.cn/
class YiProxyProvider(ProxyProvider):
    def __init__(self, link: str):
        """
        初始化代理类实例。

        Args:
            link (str): 代理服务器的链接。

        Attributes:
            proxy_link (str): 存储传入的代理链接。
            _client (httpx.AsyncClient): 初始化一个异步的 HTTP 客户端。
        """
        self.proxy_link = link
        self._client = httpx.AsyncClient()  # 初始化持久化客户端

    async def get_proxy(self) -> tuple[Optional[str], Optional[Exception]]:
        """
        异步获取代理服务器地址。

        Args:
            无

        Returns:
            tuple: 包含两个元素的元组：
                - Optional[str]: 代理服务器的地址（如果获取成功）或 None（如果 proxy_link 为空）。
                - Exception: 如果在获取代理地址时发生异常，则返回该异常对象。

        """
        if not self.proxy_link:
            return None, ValueError("Proxy link is empty.")
        try:
            # start_time = time.time()
            resp = await self._client.get(self.proxy_link, timeout=5)
            # elapsed = time.time() - start_time
            # logger.info(f"获取代理耗时: {elapsed:.2f}秒")
            return f"http://{resp.text.strip()}", None
        except Exception as e:
            return None, e

    async def invalidate_proxy(self, proxy: str) -> None:
        # 实际场景可能需要更复杂的处理
        pass

    async def close(self) -> None:
        """显式关闭客户端连接"""
        await self._client.aclose()

    # 支持异步上下文管理器协议
    async def __aenter__(self) -> "YiProxyProvider":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
