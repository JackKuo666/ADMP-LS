"""生物医学聊天服务模块，提供RAG问答和流式响应功能。"""

import datetime
import json
import time
from typing import Any, AsyncGenerator, List

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from bio_requests.chat_request import ChatRequest
from bio_requests.rag_request import RagRequest
from config.global_storage import get_model_config
from search_service.pubmed_search import PubMedSearchService

from search_service.web_search import WebSearchService
from service.query_rewrite import QueryRewriteService
from service.rerank import RerankService
from utils.bio_logger import bio_logger as logger
from utils.i18n_util import get_error_message, get_label_message
from utils.token_util import num_tokens_from_messages, num_tokens_from_text
from utils.snowflake_id import snowflake_id_str


class ChatService:
    """生物医学聊天服务，提供RAG问答和流式响应功能。"""

    def __init__(self):
        self.pubmed_search_service = PubMedSearchService()
        self.web_search_service = WebSearchService()
        self.query_rewrite_service = QueryRewriteService()

        self.rag_request = RagRequest()
        self.rerank_service = RerankService()
        self.model_config = get_model_config()

    def _initialize_rag_request(self, chat_request: ChatRequest) -> None:
        """初始化RAG请求参数"""
        self.rag_request.query = chat_request.query

    async def generate_stream(self, chat_request: ChatRequest):
        """
        Generate a stream of messages for the chat request.

        Args:
            chat_request: 聊天请求
        """

        start_time = time.time()

        try:
            # 初始化RAG请求
            self._initialize_rag_request(chat_request)

            # PubMed搜索
            logger.info("QA-RAG: Start search pubmed...")

            pubmed_results = await self._search_pubmed(chat_request)

            pubmed_task_text = self._generate_pubmed_search_task_text(pubmed_results)
            yield pubmed_task_text
            logger.info(
                f"QA-RAG: Finished search pubmed, length: {len(pubmed_results)}"
            )

            # Web搜索
            web_results = []
            if chat_request.is_web: 
                logger.info("QA-RAG: Start search web...")

                web_urls = await self._search_web()
                logger.info("QA-RAG: Finished search web...")
            else:
                logger.info(f"QA-RAG: No web search...is_web:{chat_request.is_web}")
                web_urls = []

            web_results = (
                await self.web_search_service.enrich_url_results_with_contents(web_urls)
            )

            task_text = self._generate_web_search_task_text(web_results)

            yield task_text

            # 创建消息
            messages, citation_list = self._create_messages(
                pubmed_results, web_results, chat_request
            )
            citation_text = self._generate_citation_text(citation_list)
            yield citation_text
            # 流式聊天完成
            async for content in self._stream_chat_completion(messages):
                yield content

            logger.info(
                f"Finished search and chat, query: [{chat_request.query}], total time: {time.time() - start_time:.2f}s"
            )

        except Exception as e:
            logger.error(f"Error occurred: {e}")
            # 使用上下文中的语言返回错误消息
            error_msg = get_error_message("llm_service_error")
            yield f"data: {error_msg}\n\n"
            return

    def _generate_citation_text(self, citation_list: List[Any]) -> str:
        """生成引用文本"""

        return f"""
```bio-resource-lookup
{json.dumps(citation_list)}
```
    """

    async def _search_pubmed(self, chat_request: ChatRequest) -> List[Any]:
        """执行PubMed搜索"""
        try:
            logger.info(f"query: {chat_request.query}, Using pubmed search...")
            self.rag_request.top_k = self.model_config["qa-topk"]["pubmed"]
            self.rag_request.pubmed_topk = self.model_config["qa-topk"]["pubmed"]

            start_search_time = time.time()
            pubmed_results = await self.pubmed_search_service.search(self.rag_request)
            end_search_time = time.time()

            logger.info(
                f"length of pubmed_results: {len(pubmed_results)},time used:{end_search_time - start_search_time:.2f}s"
            )
            pubmed_results = pubmed_results[0 : self.rag_request.top_k]
            logger.info(f"length of pubmed_results after rerank: {len(pubmed_results)}")

            end_rerank_time = time.time()
            logger.info(
                f"Reranked {len(pubmed_results)} results,time used:{end_rerank_time - end_search_time:.2f}s"
            )

            return pubmed_results
        except Exception as e:
            logger.error(f"error in search pubmed: {e}")
            return []

    async def _search_web(self) -> tuple[List[Any], str]:
        """执行Web搜索"""
        web_topk = self.model_config["qa-topk"]["web"]
        try:
            # 尝试获取重写后的查询
            query_list = await self.query_rewrite_service.query_split_for_web(
                self.rag_request.query
            )
            # 安全获取重写查询，如果query_list为空或获取失败则使用原始查询
            serper_query = (
                query_list[0].get("query_item", "").strip() if query_list else None
            )
            # 如果重写查询为空，则回退到原始查询
            if not serper_query:
                serper_query = self.rag_request.query
            # 使用最终确定的查询执行搜索
            url_results = await self.web_search_service.search_serper(
                query=serper_query, max_results=web_topk
            )
        except Exception as e:
            logger.error(f"error in query rewrite web or serper retrieval: {e}")
            # 出错时使用原始查询进行搜索
            url_results = await self.web_search_service.search_serper(
                query=self.rag_request.query, max_results=web_topk
            )

        return url_results


    def _generate_pubmed_search_task_text(self, pubmed_results: List[Any]) -> str:
        """生成PubMed搜索任务文本"""
        docs = [
            {
                "docId": result.bio_id,
                "url": result.url,
                "title": result.title,
                "description": result.text,
                "author": result.authors,
                "JournalInfo": result.journal.get("title", "")
                + "."
                + result.journal.get("year", "")
                + "."
                + (
                    result.journal.get("start_page", "")
                    + "-"
                    + result.journal.get("end_page", "")
                    + "."
                    if result.journal.get("start_page")
                    and result.journal.get("end_page")
                    else ""
                )
                + "doi:"
                + result.doi,
                "PMID": result.source_id,
            }
            for result in pubmed_results
        ]
        label = get_label_message("pubmed_search")
        return self._generate_task_text(label, "pubmed", docs)

    def _generate_web_search_task_text(self, url_results: List[Any]) -> str:
        """生成Web搜索任务文本"""
        web_docs = [
            {
                "docId": url_result.bio_id,
                "url": url_result.url,
                "title": url_result.title,
                "description": url_result.description,
            }
            for url_result in url_results
        ]

        logger.info(f"URL Results: {web_docs}")

        label = get_label_message("web_search")

        return self._generate_task_text(label, "webSearch", web_docs)

    def _generate_task_text(self, label, source, bio_docs: List[Any]):
        """生成任务文本"""
        task = {
            "type": "search",
            "label": label,
            "hoverable": True,
            "handler": "QASearch",
            "status": "running",
            "handlerParam": {"source": source, "bioDocs": bio_docs},
        }
        return f"""
```bio-chat-agent-task
{json.dumps(task)}
``` 
"""

    def _build_document_texts(
        self, pubmed_results: List[Any], web_results: List[Any]
    ) -> tuple[str, str, List[Any]]:
        """构建文档文本"""
        # 个人向量搜索结果
        citation_list = []
        temp_doc_list = []

        # pubmed结果
        pubmed_offset = 0
        for idx, doc in enumerate(pubmed_results):
            _idx = idx + 1 + pubmed_offset
            temp_doc_list.append(
                "[document {idx} begin] title: {title}. content: {abstract} [document {idx} end]".format(
                    idx=_idx, title=doc.title, abstract=doc.abstract
                )
            )
            citation_list.append(
                {"source": "pubmed", "docId": doc.bio_id, "citation": _idx}
            )
        pubmed_texts = "\n".join(temp_doc_list)

        temp_doc_list = []
        # 联网搜索结果
        web_offset = pubmed_offset + len(pubmed_results)
        for idx, doc in enumerate(web_results):
            _idx = idx + 1 + web_offset
            temp_doc_list.append(
                "[document {idx} begin] title: {title}. content: {content} [document {idx} end]".format(
                    idx=_idx, title=doc.title, content=doc.text
                )
            )
            citation_list.append(
                {"source": "webSearch", "docId": doc.bio_id, "citation": _idx}
            )
        web_texts = "\n".join(temp_doc_list)

        return pubmed_texts, web_texts, citation_list

    def _truncate_documents_to_token_limit(
        self,
        pubmed_texts: str,
        web_texts: str,
        chat_request: ChatRequest,
    ) -> tuple[List[ChatCompletionMessageParam], int]:
        """截断文档以符合token限制"""
        pubmed_list = pubmed_texts.split("\n")
        web_list = web_texts.split("\n")

        today = datetime.date.today()
        openai_client_rag_prompt = self.model_config["chat"]["rag_prompt"]
        max_tokens = self.model_config["qa-prompt-max-token"]["max_tokens"]
        pubmed_token_limit = max_tokens
        web_token_limit = 60000
        personal_vector_token_limit = 80000
        if chat_request.is_pubmed and chat_request.is_web:
            personal_vector_token_limit = 40000
            pubmed_token_limit = 20000
            web_token_limit = 60000
        elif chat_request.is_pubmed and not chat_request.is_web:
            personal_vector_token_limit = 80000
            pubmed_token_limit = 40000
            web_token_limit = 0
        elif chat_request.is_pubmed and chat_request.is_web:
            personal_vector_token_limit = 0
            pubmed_token_limit = 60000
            web_token_limit = 60000
        elif chat_request.is_pubmed and not chat_request.is_web:
            personal_vector_token_limit = 0
            pubmed_token_limit = 120000
            web_token_limit = 0

        def calculate_num_tokens(
            pubmed_list: List[str], web_list: List[str]
        ) -> tuple[int, List[ChatCompletionMessageParam]]:
            # 合并结果
            docs_text = "\n".join(pubmed_list + web_list)

            pt = (
                openai_client_rag_prompt.replace("{search_results}", docs_text)
                .replace("{cur_date}", str(today))
                .replace("{question}", chat_request.query)
            )
            messages: List[ChatCompletionMessageParam] = [
                {"role": "user", "content": pt}
            ]
            # 计算token数
            num_tokens = num_tokens_from_messages(messages)
            return num_tokens, messages

        while True:
            num_tokens, messages = calculate_num_tokens(pubmed_list, web_list)
            if num_tokens <= max_tokens:
                break
            # 如果超过token限制，则按照比例进行截断
            logger.info(
                f"start truncate documents to token limit: max_tokens: {max_tokens}"
            )
            logger.info(
                f"pubmed_token_limit: {pubmed_token_limit}, web_token_limit: {web_token_limit}, personal_vector_token_limit: {personal_vector_token_limit}"
            )

            while True:
                if num_tokens_from_text("\n".join(pubmed_list)) > pubmed_token_limit:
                    pubmed_list.pop()
                else:
                    break

            # 截断pubmed之后，重新计算token数，如果token数小于max_tokens，则停止截断
            num_tokens, messages = calculate_num_tokens(pubmed_list, web_list)
            if num_tokens <= max_tokens:
                break

            while True:
                if num_tokens_from_text("\n".join(web_list)) > web_token_limit:
                    web_list.pop()
                else:
                    break

            # 截断web之后，重新计算token数，如果token数小于max_tokens，则停止截断
            num_tokens, messages = calculate_num_tokens(pubmed_list, web_list)
            if num_tokens <= max_tokens:
                break

        logger.info(f"Final token count: {num_tokens}")
        return messages, num_tokens

    def _create_messages(
        self,
        pubmed_results: List[Any],
        web_results: List[Any],
        chat_request: ChatRequest,
    ) -> tuple[List[ChatCompletionMessageParam], List[Any]]:
        """创建聊天消息"""
        if len(pubmed_results) == 0 and len(web_results) == 0:
            logger.info(f"No results found for query: {chat_request.query}")
            pt = chat_request.query
            messages: List[ChatCompletionMessageParam] = [
                {"role": "user", "content": pt}
            ]
            num_tokens = num_tokens_from_messages(messages)
            logger.info(f"Total tokens: {num_tokens}")
            return messages, []

        # 构建文档文本
        pubmed_texts, web_texts, citation_list = self._build_document_texts(
            pubmed_results, web_results
        )

        # 截断文档以符合token限制
        messages, num_tokens = self._truncate_documents_to_token_limit(
            pubmed_texts, web_texts, chat_request
        )

        return messages, citation_list

    async def _stream_chat_completion(
        self, messages: List[ChatCompletionMessageParam]
    ) -> AsyncGenerator[bytes, None]:
        """流式聊天完成，支持qa-llm的main/backup配置"""

        async def create_stream_with_config(
            qa_config: dict, config_name: str
        ) -> AsyncGenerator[bytes, None]:
            """使用指定配置创建流式响应"""
            try:
                logger.info(f"Using qa-llm {config_name} configuration")

                client = AsyncOpenAI(
                    api_key=qa_config["api_key"],
                    base_url=qa_config["base_url"],
                )

                chat_start_time = time.time()

                # 创建聊天完成流
                stream = await client.chat.completions.create(
                    model=qa_config["model"],
                    messages=messages,
                    stream=True,
                    temperature=qa_config["temperature"],
                    max_tokens=qa_config["max_tokens"],
                )

                logger.info(
                    f"Finished chat completion with {config_name} config, total time: {time.time() - chat_start_time:.2f}s"
                )

                is_start_answer = False
                # 处理流式响应
                async for chunk in stream:
                    if chunk.choices and (content := chunk.choices[0].delta.content):
                        if not is_start_answer:
                            is_start_answer = True
                            # 在开始返回内容前添加标志
                            yield "Bio-QA-final-Answer：".encode("utf-8")

                        yield content.encode("utf-8")

            except Exception as e:
                logger.info(f"qa-llm {config_name} configuration failed: {e}")
                raise e

        async def with_fallback(main_func, backup_func):
            """高阶函数：尝试主函数，失败时使用备选函数"""
            try:
                async for content in main_func():
                    yield content
            except Exception as main_error:
                logger.info("Main config failed, falling back to backup configuration")
                try:
                    async for content in backup_func():
                        yield content
                except Exception as backup_error:
                    logger.error(
                        f"Both main and backup qa-llm configurations failed. "
                        f"Main error: {main_error}, Backup error: {backup_error}"
                    )
                    raise backup_error

        # 创建主用和备选配置的生成器函数
        async def main_stream():
            logger.info("Using main qa-llm configuration")
            async for content in create_stream_with_config(
                self.model_config["qa-llm"]["main"], "main"
            ):
                yield content

        async def backup_stream():
            logger.info("Using backup qa-llm configuration")
            async for content in create_stream_with_config(
                self.model_config["qa-llm"]["backup"], "backup"
            ):
                yield content

        # 使用fallback逻辑
        async for content in with_fallback(main_stream, backup_stream):
            yield content
