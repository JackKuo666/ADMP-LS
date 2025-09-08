# 处理相对导入
try:
    from ..setting_config import settings
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from setting_config import settings
import logging
from typing import Union


from agents import (
    OpenAIChatCompletionsModel,
    OpenAIResponsesModel,
    set_tracing_disabled,
)
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
set_tracing_disabled(True)
OPENAI_API_KEY = settings.OPENAI_API_KEY
QIANWEN_API_KEY = settings.QIANWEN_API_KEY

LONG_MODEL_KEY = OPENAI_API_KEY
LONG_MODEL = "claude-3-7-sonnet-20250219"
# QIANWEN_MODEL_KEY = QIANWEN_API_KEY
QIANWEN_PLUS_MODEL = "qwen-plus-latest"


qianwen_client = AsyncOpenAI(
    api_key=QIANWEN_API_KEY,
    base_url=settings.QIANWEN_BASE_URL,
)

qianwen_plus_model = OpenAIChatCompletionsModel(
    model=QIANWEN_PLUS_MODEL,  # qwen-long-latest,qwen-plus-latest
    openai_client=qianwen_client,
)

claude_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
)
long_model = OpenAIChatCompletionsModel(
    model=LONG_MODEL,
    openai_client=claude_client,
)


def get_base_url(model: Union[OpenAIChatCompletionsModel, OpenAIResponsesModel]) -> str:
    """Utility function to get the base URL for a given model"""
    return str(model._client._base_url)


def model_supports_structured_output(
    model: Union[OpenAIChatCompletionsModel, OpenAIResponsesModel],
) -> bool:
    """Utility function to check if a model supports structured output"""
    structured_output_providers = [
        "openai.com",
        "anthropic.com",
        "sohoyo.io",
        "nhss.zhejianglab.com",
    ]
    return any(
        provider in get_base_url(model) for provider in structured_output_providers
    )
