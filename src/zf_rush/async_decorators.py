"""
提供了一系列异步装饰器，用于增强HTTP请求的功能。

包含以下装饰器：
- scheduled: 定时执行装饰器，用于在指定时间执行异步函数
- concurrent: 并发控制装饰器，用于限制并发请求数量
- delayed: 请求间隔装饰器，用于控制请求之间的延迟时间
- http_client: HTTP客户端装饰器，用于配置和管理HTTP客户端
"""

import asyncio
from datetime import datetime
from functools import wraps
import traceback
from typing import Callable, Optional, Type, Union

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from zf_rush.client import HttpClient
from zf_rush.config import ConnectionConfig, RetryStrategy
from zf_rush.proxy import EmptyProxyProvider, ProxyProvider


# 1. 定时执行装饰器
def scheduled(execute_time: Optional[str] = None):
    """

    scheduled装饰器

    Args:
        execute_time (Optional[str], optional): 计划执行的时间，支持毫秒格式。默认为None。

    Returns:
        Callable: 返回装饰后的函数。

    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            if execute_time:
                # 自动识别时间格式（支持毫秒）
                time_format = (
                    "%Y-%m-%d %H:%M:%S.%f"
                    if "." in execute_time
                    else "%Y-%m-%d %H:%M:%S"
                )
                target_time = datetime.strptime(execute_time, time_format)

                now = datetime.now()
                time_diff = target_time - now
                wait_seconds = time_diff.total_seconds()

                # 格式化时间显示（保留毫秒）
                target_str = target_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                # now_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                # 美化日志输出
                logger.info(f"🚀 计划时间: {target_str} | 等待: {wait_seconds:.2f} 秒")

                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# 2. 并发控制装饰器
def concurrent(max_concurrent: int, max_requests: int):
    """
    并发控制装饰器。

    Args:
        max_concurrent (int): 允许的最大并发数。
        max_requests (int): 允许的最大请求数。

    Returns:
        function: 返回一个新的装饰器函数。

    装饰器说明：
        该装饰器用于控制并发请求的数量，并确保不会超出允许的最大请求数。
        它使用 asyncio.Semaphore 来控制并发数，并使用 asyncio.Lock 来确保请求计数的正确性。
        每个并发任务会创建一个 HttpClient 实例，并将其传递给被装饰的函数。
        如果请求失败，将记录错误日志。
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            semaphore = asyncio.Semaphore(max_concurrent)
            request_counter = 0
            lock = asyncio.Lock()
            task_id_counter = 0

            async def worker():
                nonlocal request_counter, task_id_counter
                task_id = task_id_counter
                task_id_counter += 1

                # 创建持久化client
                async with HttpClient() as client:
                    while True:
                        async with semaphore:
                            async with lock:
                                if request_counter >= max_requests:
                                    break
                                current_request = request_counter
                                request_counter += 1

                            # 注入client到被装饰函数
                            try:
                                await func(
                                    client=client,
                                    task_id=task_id,
                                    request_num=current_request,
                                    *args,
                                    **kwargs,
                                )
                            except (IOError, ValueError, TimeoutError) as e:
                                # 获取完整的错误追踪信息
                                tb_list = traceback.extract_tb(e.__traceback__)
                                # 取最后一个追踪帧（即异常发生的具体位置）
                                tb_last = tb_list[-1]
                                error_location = f'File "{tb_last.filename}", line {tb_last.lineno} in {tb_last.name}'
                                
                                logger.error(
                                    f"🚨 Task-{task_id:02d} | 请求失败 | 异常类型: {type(e).__name__} | 位置: {error_location} | 错误信息: {str(e)}",
                                    exc_info=False,
                                )
                            finally:
                                await asyncio.sleep(kwargs.get("request_delay", 0))

                logger.info(f"Task-{task_id:02d} 已停止")

            tasks = [asyncio.create_task(worker()) for _ in range(max_concurrent)]
            await asyncio.gather(*tasks)

        return wrapper

    return decorator


# 3. 请求间隔装饰器
def delayed(delay: float):
    """
    异步延迟装饰器

    Args:
        delay (float): 延迟时间，单位为秒。

    Returns:
        Callable: 返回装饰器函数。

    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            await asyncio.sleep(delay)
            return await func(*args, **kwargs)

        return wrapper

    return decorator


# 4. HTTP客户端装饰器
def http_client(
    connection_config: "ConnectionConfig",
    retry_strategy: "RetryStrategy",
    proxy_provider: Optional["ProxyProvider"] = None,
    fake_headers: bool = True,
) -> Callable:
    """
    HTTP客户端装饰器工厂函数。

    Args:
        connection_config (ConnectionConfig): 连接配置对象。
        retry_strategy (RetryStrategy): 重试策略对象。
        proxy_provider (Optional[ProxyProvider], optional): 代理提供者对象，默认为None。
        fake_headers (bool, optional): 是否使用伪造的头信息，默认为True。

    Returns:
        Callable: 返回一个装饰器函数，该装饰器用于包装异步函数，以便在调用时使用自定义的HTTP客户端配置。

    """

    def decorator(func: Callable) -> Callable:
        """
        装饰器函数，用于包装异步函数。

        Args:
            func (Callable): 被装饰的异步函数。

        Returns:
            Callable: 包装后的异步函数。

        """

        @wraps(func)
        async def wrapper(*args, **kwargs) -> any:
            # 优先使用外部传入的client
            if "client" in kwargs:
                client: HttpClient = kwargs["client"]
                client.connection_config = connection_config
                client.retry_strategy = retry_strategy
                client.proxy_provider = (
                    proxy_provider if proxy_provider else EmptyProxyProvider()
                )
                await client.initialize()
                return await func(*args, **kwargs)

            # 使用默认配置防止None
            cc = connection_config or ConnectionConfig()
            rs = retry_strategy or RetryStrategy()
            pp = proxy_provider or EmptyProxyProvider()

            # 否则创建新client并传递配置参数
            async with HttpClient(
                connection_config=cc,
                retry_strategy=rs,
                proxy_provider=pp,
                fake_headers=fake_headers,
            ) as client:
                kwargs["client"] = client
                return await func(*args, **kwargs)

        return wrapper

    return decorator
