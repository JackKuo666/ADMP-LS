"""Biomedical RAG service main program entry point."""

import importlib
import os
import pkgutil
import time

import uvicorn
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from asgi_correlation_id import CorrelationIdMiddleware, correlation_id
from fastapi import FastAPI, Request
from fastapi_mcp import FastApiMCP
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from routers import sensor, mcp_sensor
from utils.bio_logger import bio_logger as logger

# 调试：验证环境变量是否加载
logger.info(f"SERPER_API_KEY loaded: {'Yes' if os.getenv('SERPER_API_KEY') else 'No'}")


app = FastAPI(
    docs_url=None,  # 关闭 Swagger UI 文档
    redoc_url=None,  # 关闭 ReDoc 文档
    openapi_url=None,  # 关闭 OpenAPI 规范文件
    debug=False,  # 关闭调试模式
)

# 全局限流配置（按客户端IP）
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 第一个添加的中间件
app.add_middleware(CorrelationIdMiddleware)
# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(sensor.router)
app.include_router(mcp_sensor.router)  # 包含 MCP 路由

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "bio-rag-mcp"}


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """HTTP中间件，记录请求处理时间和状态。完全兼容SSE流式响应。"""
    start_time = time.time()
    
    # 检查是否为SSE端点
    is_sse_endpoint = request.url.path.startswith("/sse")
    
    logger.info(f"Request started  | URL: {request.url}")

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # 对于SSE端点，只记录请求开始时间，不尝试访问响应属性
        if is_sse_endpoint:
            logger.info(
                f"SSE connection established | "
                f"Time: {process_time:.2f}s"
            )
        else:
            # 对于普通HTTP请求，安全地获取状态码
            try:
                status_code = getattr(response, 'status_code', 'UNKNOWN')
                logger.info(
                    f"Request completed | "
                    f"Status: {status_code} | "
                    f"Time: {process_time:.2f}s"
                )
            except Exception as e:
                logger.warning(f"Could not get status code: {e}")
                logger.info(
                    f"Request completed | "
                    f"Status: UNKNOWN | "
                    f"Time: {process_time:.2f}s"
                )
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"Request failed | "
            f"Error: {str(e)} | "
            f"Time: {process_time:.2f}s"
        )
        raise


def dynamic_import_subclasses(parent_dir: str) -> None:
    """动态导入指定目录下的所有Python模块。

    Args:
        parent_dir: 要导入的目录路径
    """
    for _, module_name, _ in pkgutil.iter_modules([parent_dir]):
        module = importlib.import_module(f"{parent_dir}.{module_name}")
        logger.info(f"Imported: {module.__name__}")


# Add MCP server to the FastAPI app
mcp = FastApiMCP(app, name="bio qa mcp", include_operations=["bio_qa_stream_chat"])

# Mount the MCP server to the FastAPI app
mcp.mount_sse()

if __name__ == "__main__":
    logger.info("Starting Bio RAG Server...")
    dynamic_import_subclasses("search_service")
    uvicorn.run(app, host="0.0.0.0", port=9487)
