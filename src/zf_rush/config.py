from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from typing import Type, TypeVar, Optional, Literal
from typing_extensions import TypedDict
from datetime import datetime
import os
import json

T = TypeVar("T", bound="BaseConfig")  # 所有配置类都继承自BaseConfig


class BaseConfig(ABC):
    @classmethod
    def from_dict(cls: Type[T], data: dict) -> T:
        """统一反序列化入口（需子类实现具体逻辑）"""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> dict:
        """将配置转换为字典格式"""
        raise NotImplementedError


class ProxyPlatformConfig(TypedDict):
    name: str
    value: Optional[str]
    get_proxy_link: Optional[str]
    home_page: Optional[str]
    zh_name: Optional[str]
    priority: int


@dataclass
class ProxyConfig:
    enable: bool
    use: Literal["debug_proxy", "yi_dai_li"]
    proxy_platforms: list[ProxyPlatformConfig]


@dataclass
class AppConfig(BaseConfig):
    execute_datetime: Optional[str] = None
    concurrency: int = 1
    max_requests: int = 10
    max_retries: int = 3
    request_delay: float = 0.5
    request_timeout: float = 10
    fake_headers_enabled: bool = True

    # 新增代理配置结构
    proxy_config: ProxyConfig = field(
        default_factory=lambda: {
            "enable": True,
            "use": "debug_proxy",
            "proxy_platforms": [
                {"name": "debug_proxy", "value": "http://127.0.0.1:7890", "priority": 1}
            ],
        }
    )

    # 可选的额外属性（保持向后兼容）
    _extra: dict = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理逻辑"""
        if not self.execute_datetime:
            self.execute_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 将旧配置转换为新结构（兼容旧版本配置）
        if "enable_proxy" in self._extra or "proxy_url" in self._extra:
            self.proxy_config["enable"] = self._extra.get("enable_proxy", False)
            self.proxy_config["use"] = (
                "custom" if self.proxy_config["enable"] else "none"
            )
            if self._extra.get("proxy_url"):
                self.proxy_config["proxy_platforms"] = [
                    {
                        "name": "custom",
                        "get_proxy_link": self._extra["proxy_url"],
                        "home_page": "",
                        "zh_name": "自定义代理",
                        "priority": 1,
                    }
                ]

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """从字典创建配置实例"""
        filtered_data = {k: v for k, v in data.items() if k in cls.__annotations__}
        extra = {k: v for k, v in data.items() if k not in cls.__annotations__}

        # 处理新旧配置转换
        if "proxy_config" not in filtered_data and (
            "enable_proxy" in data or "proxy_url" in data
        ):
            filtered_data["proxy_config"] = {
                "enable": data.get("enable_proxy", False),
                "use": "custom" if data.get("enable_proxy") else "none",
                "proxy_platforms": [
                    {
                        "name": "custom",
                        "get_proxy_link": data.get("proxy_url", ""),
                        "home_page": "",
                        "zh_name": "自定义代理",
                        "priority": 1,
                    }
                ]
                if data.get("enable_proxy")
                else [],
            }

        config = cls(**filtered_data)
        config._extra = extra
        return config

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {**asdict(self), **self._extra}

    # @property
    # def execute_timestamp(self) -> float:
    #     """获取执行时间的时间戳"""
    #     if not self.execute_datetime:  # 检查是否为 None 或空字符串
    #         return datetime.now().timestamp()  # 默认使用当前时间
    #     return datetime.strptime(self.execute_datetime, "%Y-%m-%d %H:%M:%S").timestamp()


class ConfigManager:
    @staticmethod
    def save(config: BaseConfig, file_path: str) -> bool:
        """
        保存配置到JSON文件，自动创建目录并处理异常

        Args:
            config: 配置对象
            file_path: 文件保存路径

        Returns:
            bool: 保存是否成功
        """

        # 确保目录存在
        directory = os.path.dirname(file_path)
        if directory:  # 处理文件在根目录的情况（如file_path为"config.json"）
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                print(f"无法创建目录 {directory}: {e}")
                return False

        try:
            # 显式指定文件对象类型为 SupportsWrite[str]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(
                    config.to_dict(),
                    f,  # type: ignore[arg-type]
                    indent=2,
                    ensure_ascii=False,
                )
            return True
        except IOError as e:
            print(f"文件写入失败 {file_path}: {e}")
        except Exception as e:
            print(f"保存配置时发生未知错误: {e}")

        return False

    @staticmethod
    def load(file_path: str, config_class: Type[T]) -> T:
        """从JSON文件加载配置

        Args:
            file_path: 配置文件路径
            config_class: 要实例化的配置类（如AppConfig/CacheData）

        Returns:
            指定类型的配置对象实例
        """

        if not os.path.exists(file_path):
            return config_class()

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 调用类的from_dict方法进行反序列化
        return config_class.from_dict(data)
