"""全局配置存储模块，提供配置文件的加载和缓存功能。"""

import os
import re
from typing import Any, Dict, Optional

import yaml


class ConfigManager:
    """配置管理器，使用单例模式缓存配置。"""

    _instance = None
    _config: Optional[Dict[str, Any]] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_config(self) -> Dict[str, Any]:
        """获取配置，如果未加载则自动加载。

        Returns:
            包含所有配置信息的字典
        """
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _get_environment(self) -> str:
        """获取当前环境类型。

        Returns:
            环境类型：'prod' 或 'dev'
        """
        return os.getenv("ENVIRONMENT", "dev").lower()

    def _get_config_path(self) -> str:
        """根据环境获取配置文件路径。

        Returns:
            配置文件路径
        """
        env = self._get_environment()
        if env == "prod":
            return "config/app_config_prod.yaml"

        return "config/app_config_dev.yaml"

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件。

        Returns:
            从YAML文件加载的配置字典
        """
        config_path = self._get_config_path()
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                content = file.read()
                # 替换环境变量
                content = self._replace_env_vars(content)
                config = yaml.safe_load(content)
                # 添加环境信息到配置中
                config["environment"] = self._get_environment()
                return config
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"配置文件未找到: {config_path}") from exc
        except yaml.YAMLError as exc:
            raise ValueError(f"配置文件格式错误: {exc}") from exc

    def _replace_env_vars(self, content: str) -> str:
        """替换配置文件中的环境变量占位符。

        Args:
            content: 配置文件内容

        Returns:
            替换环境变量后的内容
        """
        def replace_var(match):
            var_name = match.group(1)
            # 获取环境变量值，如果不存在则使用占位符
            value = os.getenv(var_name, match.group(0))
            return value

        # 匹配 ${VAR_NAME} 格式的环境变量
        pattern = r'\$\{([^}]+)\}'
        return re.sub(pattern, replace_var, content)


# 全局配置管理器实例
_config_manager = ConfigManager()


def get_model_config() -> Dict[str, Any]:
    """获取模型配置。

    Returns:
        包含所有配置信息的字典
    """
    return _config_manager.get_config()
