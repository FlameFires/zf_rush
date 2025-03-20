from abc import ABC, abstractmethod
from typing import Any
import traceback
import time
import json
from datetime import datetime
import sys
import asyncio

from loguru import logger

from .client import RushClient
from .config import AppConfig


class BaseScheduler(ABC):
    def __init__(
        self,
        app_config: "AppConfig",
        max_concurrent_requests: int = 10,
    ):
        self.app_config = app_config
        # concurrency settings
        self.max_concurrent_requests = max_concurrent_requests
        self._request_counter = 0
        self._counter_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def start(self):
        """主调度入口"""
        await self._wait_for_execution_time()
        await self._run_concurrent_tasks()

    async def _wait_for_execution_time(self):
        """等待预设执行时间"""
        if self.app_config.execute_datetime:
            execute_time = datetime.strptime(
                self.app_config.execute_datetime, "%Y-%m-%d %H:%M:%S"
            )
            now = datetime.now()
            if execute_time > now:
                await asyncio.sleep((execute_time - now).total_seconds())

    async def _run_concurrent_tasks(self):
        """创建并管理并发任务"""
        tasks = [
            asyncio.create_task(self._managed_worker(i))
            for i in range(self.app_config.concurrency)
        ]
        await asyncio.gather(*tasks)
        logger.info("所有任务已完成")

    async def _managed_worker(self, task_id: int):
        """带信号量控制的worker包装器"""
        async with self._semaphore:
            await self.worker(task_id)

    @abstractmethod
    async def worker(self, task_id: int):
        """需要子类实现的工作协程"""
        pass

    async def execute_operation(self, task_id: int, client: "RushClient") -> Any:
        """执行核心操作的模板方法"""
        async with self._counter_lock:
            if self._request_counter >= self.app_config.max_requests:
                return None
            self._request_counter += 1
            current_request = self._request_counter

        start_time = time.time()
        try:
            result = await self.perform_action(client)
            return await self.handle_success(
                task_id=task_id,
                result=result,
                current_request=current_request,
                elapsed=time.time() - start_time,
            )
        except Exception as e:
            return await self.handle_failure(
                task_id=task_id,
                exception=e,
                current_request=current_request,
                elapsed=time.time() - start_time,
            )
        finally:
            await asyncio.sleep(self.app_config.request_delay)

    @abstractmethod
    async def perform_action(self, client: "RushClient") -> Any:
        """执行具体业务操作的抽象方法"""
        pass

    async def handle_success(
        self, task_id: int, result: Any, current_request: int, elapsed: float
    ) -> dict:
        """成功处理模板方法"""
        formatted_result = self.format_result(result)
        log_message = self.construct_success_log(
            task_id=task_id,
            current_request=current_request,
            elapsed=elapsed,
            result=formatted_result,
        )
        logger.info(log_message)
        return {
            "status": "success",
            "task_id": task_id,
            "request_num": current_request,
            "result": formatted_result,
        }

    async def handle_failure(
        self, task_id: int, exception: Exception, current_request: int, elapsed: float
    ) -> dict:
        """失败处理模板方法"""
        error_info = self.format_exception(exception)
        log_message = self.construct_failure_log(
            task_id=task_id,
            current_request=current_request,
            elapsed=elapsed,
            error=error_info,
        )
        logger.error(log_message)
        return {
            "status": "failure",
            "task_id": task_id,
            "request_num": current_request,
            "error": error_info,
        }

    # 可覆盖的格式化方法
    def format_result(self, result: Any) -> str:
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"))

    def format_exception(self, exception: Exception) -> str:
        # 获取异常堆栈信息
        exc_type, exc_value, exc_traceback = sys.exc_info()
        # 提取最后一级的堆栈帧（实际发生错误的位置）
        tb_last = traceback.extract_tb(exc_traceback)[-1]
        return (
            f"在 {tb_last.name}() "
            f"({tb_last.filename}:{tb_last.lineno}): {str(exception)}"
        )

    # 日志构建方法
    def construct_success_log(
        self, task_id: int, current_request: int, elapsed: float, result: str
    ) -> str:
        return (
            f"Task-{task_id:02d} | Request-{current_request:03d} | "
            f"Elapsed: {elapsed:.2f}s | "
            f"Response: {result}"
        )

    def construct_failure_log(
        self, task_id: int, current_request: int, elapsed: float, error: str
    ) -> str:
        return (
            f"Task-{task_id:02d} | Request-{current_request:03d} | "
            f"Elapsed: {elapsed:.2f}s | "
            f"Error: {error}"
        )
