"""API路由模块"""

from asgi_correlation_id import correlation_id
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from utils.bio_logger import bio_logger as logger
from utils.i18n_util import (
    get_language,
    create_success_response,
    create_error_response,
)
from utils.i18n_context import with_language
from bio_requests.rag_request import RagRequest
from bio_requests.chat_request import ChatRequest
from service.rag import RagService
from service.chat import ChatService
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/retrieve")
@limiter.limit("50/minute")
async def search(request: Request, rag_request: RagRequest) -> JSONResponse:
    """文档检索接口，支持多源数据检索。"""

    logger.info(f"{correlation_id.get()} Searching for {rag_request}")

    # 解析语言设置
    language = get_language(rag_request.language)

    # 使用上下文管理器设置语言
    with with_language(language):
        try:
            rag_assistant = RagService()
            documents = await rag_assistant.multi_query(rag_request)

            logger.info(f"{correlation_id.get()} Found {len(documents)} documents")
            results = [document.__dict__ for document in documents]

            # 返回国际化响应
            response_data = create_success_response(
                data=results, message_key="search_success"
            )

            return JSONResponse(content=response_data)

        except Exception as e:
            logger.error(f"{correlation_id.get()} Search error: {e}")
            error_response = create_error_response(
                error_key="search_failed", details=str(e), error_code=500
            )
            return JSONResponse(content=error_response, status_code=500)


@router.post("/stream-chat")
@limiter.limit("10/minute")
async def stream_chat(request: Request, chat_request: ChatRequest):
    """流式聊天接口，提供RAG问答服务。"""

    logger.info(f"{correlation_id.get()} Streaming chat for {chat_request}")

    # 解析语言设置
    language = get_language(chat_request.language)

    # 使用上下文管理器设置语言
    with with_language(language):
        try:
            chat_service = ChatService()
            return StreamingResponse(
                chat_service.generate_stream(chat_request),
                media_type="text/event-stream",
                headers={
                    "Connection": "keep-alive",
                    "Cache-Control": "no-cache",
                },
            )
        except Exception as e:
            logger.error(f"{correlation_id.get()} Stream chat error: {e}")
            error_response = create_error_response(
                error_key="service_unavailable",
                details=str(e),
                error_code=500,
            )
            return JSONResponse(content=error_response, status_code=500)
