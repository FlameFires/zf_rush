from typing import Optional
from abc import ABC, abstractmethod
from urllib.parse import urlparse
import ipaddress
import asyncio

import httpx
from loguru import logger

from .config import AppConfig, ProxyPlatformConfig


class ProxyProvider(ABC):
    @abstractmethod
    async def get_proxy(self) -> Optional[str]:
        pass


class DebugProxyProvider(ProxyProvider):
    def __init__(self, platform_config: ProxyPlatformConfig):
        self.proxy = platform_config.get("value")

    async def get_proxy(self) -> Optional[str]:
        return self.proxy


class RemoteProxyProvider(ProxyProvider):
    def __init__(self, platform_config: ProxyPlatformConfig):
        self.config = platform_config
        self.get_proxy_link = platform_config.get("get_proxy_link", None)

    async def get_proxy(self) -> Optional[str]:
        if not self.get_proxy_link:
            return None
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.get_proxy_link, timeout=5)
                return f"http://{resp.text.strip()}"
        except Exception as e:
            logger.error(f"获取{self.config.get('name')}代理失败: {e}")
            return None


class ProxyPool:
    def __init__(self, app_config: AppConfig):
        # 应用配置
        self.app_config = app_config
        # 代理提供者
        self.providers: list[ProxyProvider] = []
        # 代理队列
        self.lock = asyncio.Lock()
        self.proxy_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        self._stop_event = asyncio.Event()  # 新增停止信号
        self._cooldown_time = 0.5  # 基础冷却时间
        self._full_queue_cooldown = 5  # 队列满时的冷却时间
        self.invalid_proxy_count = 0
        # 预加载任务
        self._preload_task = None
        # 初始化代理提供者
        self._init_providers()

    def _init_providers(self):
        """根据配置初始化代理提供者"""
        proxy_conf = self.app_config.proxy_config
        if not proxy_conf["enable"]:
            return

        # 根据配置创建代理提供者
        if proxy_conf["use"] == "debug_proxy":
            platforms = [
                p
                for p in proxy_conf["proxy_platforms"]
                if p["name"] == proxy_conf["use"]
            ]
            if platforms:
                self.providers.append(DebugProxyProvider(platforms[0]))
        else:
            # 过滤并排序代理平台
            platforms = [
                p
                for p in proxy_conf["proxy_platforms"]
                if p["name"] == proxy_conf["use"]
            ]
            platforms.sort(key=lambda x: x.get("priority", 200))

            for platform in platforms:
                self.providers.append(
                    RemoteProxyProvider(ProxyPlatformConfig(**platform))
                )

        self._start_preload()

    def _start_preload(self):
        """安全启动预加载任务"""
        if self.providers and not self._preload_task:
            self._preload_task = asyncio.create_task(self._preload_worker())

    async def _preload_worker(self):
        """优化后的预加载协程"""
        while not self._stop_event.is_set():
            try:
                # 动态调整等待时间
                wait_time = self._cooldown_time

                # 检查队列状态
                if self.proxy_queue.full():
                    wait_time = self._full_queue_cooldown
                else:
                    # 尝试获取并填充代理
                    async with self.lock:
                        for provider in self.providers:
                            if self._stop_event.is_set():
                                return

                            proxy = await provider.get_proxy()
                            if proxy and self._validate_proxy(proxy):
                                try:
                                    self.proxy_queue.put_nowait(proxy)
                                    wait_time = 0  # 成功获取后立即继续
                                except asyncio.QueueFull:
                                    logger.warning("代理队列已满，暂停填充")
                                    break  # 队列已满时停止当前循环
                            else:
                                self.invalid_proxy_count += 1

                # 等待计算
                if not self._stop_event.is_set():
                    await asyncio.sleep(wait_time)

            except asyncio.CancelledError:
                logger.info("预加载协程被取消")
                break
            except Exception as e:
                logger.error(f"预加载协程异常: {e}")
                await asyncio.sleep(1)  # 防止异常导致死循环

    def _validate_proxy(self, proxy: str) -> bool:
        """验证代理格式是否符合http://ip:port规范"""
        try:
            # 解析URL
            parsed = urlparse(proxy)
            if parsed.scheme not in ("http", "https"):
                logger.error(f"代理协议错误: {proxy}，必须为http或https")
                return False

            # 验证主机格式
            try:
                ipaddress.IPv4Address(parsed.hostname)
            except ipaddress.AddressValueError:
                logger.error(f"无效的IP地址格式: {parsed.hostname}")
                return False

            # 验证端口
            if not parsed.port:
                logger.error(f"代理地址缺少端口号: {proxy}")
                return False

            if not (1 <= parsed.port <= 65535):
                logger.error(f"端口超出有效范围: {parsed.port}")
                return False

            return True

        except Exception as e:
            logger.error(f"代理验证异常: {proxy} - {str(e)}")
            return False

    async def get_next_proxy(self) -> Optional[str]:
        """获取代理（优先从预加载队列获取）"""
        # 尝试从队列获取代理
        try:
            proxy = self.proxy_queue.get_nowait()
            self.current_proxy = proxy
            return proxy
        except asyncio.QueueEmpty:
            pass

        # 实时获取代理作为后备
        async with self.lock:
            for provider in self.providers:
                proxy = await provider.get_proxy()
                if proxy:
                    self.current_proxy = proxy
                    return proxy
        return None

    async def close(self):
        """优雅关闭预加载任务"""
        self._stop_event.set()
        if self._preload_task and not self._preload_task.done():
            try:
                await asyncio.wait_for(self._preload_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("预加载协程关闭超时，强制取消")
                self._preload_task.cancel()
                await self._preload_task
