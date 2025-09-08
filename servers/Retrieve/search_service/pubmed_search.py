import asyncio
import re
import time
import threading
from typing import Dict, List

from dto.bio_document import BaseBioDocument, create_bio_document
from search_service.base_search import BaseSearchService
from bio_requests.rag_request import RagRequest
from utils.bio_logger import bio_logger as logger


from service.query_rewrite import QueryRewriteService
from service.pubmed_api import PubMedApi
from service.pubmed_async_api import PubMedAsyncApi
from config.global_storage import get_model_config


class PubMedSearchService(BaseSearchService):
    def __init__(self):
        self.query_rewrite_service = QueryRewriteService()
        self.model_config = get_model_config()

        self.pubmed_topk = self.model_config["recall"]["pubmed_topk"]
        self.es_topk = self.model_config["recall"]["es_topk"]
        self.data_source = "pubmed"
        
        # 添加锁来防止并发Bio.Entrez操作
        self._bio_entrez_lock = threading.Lock()
        
        # 限制并发操作数量，防止内存问题
        self._max_concurrent_searches = 3

    async def get_query_list(self, rag_request: RagRequest) -> List[Dict]:
        """根据RagRequest获取查询列表"""
        if rag_request.is_rewrite:
            query_list = await self.query_rewrite_service.query_split(rag_request.query)
            logger.info(f"length of query_list after query_split: {len(query_list)}")
            if len(query_list) == 0:
                logger.info("query_list is empty, use query_split_for_simple")
                query_list = await self.query_rewrite_service.query_split_for_simple(
                    rag_request.query
                )
                logger.info(
                    f"length of query_list after query_split_for_simple: {len(query_list)}"
                )
            self.pubmed_topk = rag_request.pubmed_topk
            self.es_topk = rag_request.pubmed_topk
        else:
            self.pubmed_topk = rag_request.top_k
            self.es_topk = rag_request.top_k
            query_list = [
                {
                    "query_item": rag_request.query,
                    "search_type": rag_request.search_type,
                }
            ]
        return query_list

    async def search(self, rag_request: RagRequest) -> List[BaseBioDocument]:
        """异步搜索PubMed数据库"""
        if not rag_request.query:
            return []

        start_time = time.time()
        query_list = await self.get_query_list(rag_request)

        # 使用异步并发替代线程池
        articles_id_list = []
        es_articles = []

        try:
            # 限制并发搜索数量，防止内存问题
            semaphore = asyncio.Semaphore(self._max_concurrent_searches)
            
            # 创建异步任务列表，使用PubMedApi的search_database方法
            async_tasks = []
            for query in query_list:
                task = self._search_pubmed_with_sync_api(
                    query["query_item"], self.pubmed_topk, query["search_type"], semaphore
                )
                async_tasks.append((query, task))

            # 并发执行所有搜索任务
            results = await asyncio.gather(
                *[task for _, task in async_tasks], return_exceptions=True
            )

            # 处理结果
            for i, (query, _) in enumerate(async_tasks):
                result = results[i]

                if isinstance(result, Exception):
                    logger.error(f"Error in search pubmed: {result}")
                else:
                    articles_id_list.extend(result)

        except Exception as e:
            logger.error(f"Error in concurrent PubMed search: {e}")

        # 获取文章详细信息
        pubmed_docs = await self.fetch_article_details(articles_id_list)

        # 合并结果
        all_results = []
        all_results.extend(pubmed_docs)
        all_results.extend(es_articles)

        logger.info(
            f"""Finished searching PubMed, query:{rag_request.query}, 
            total articles: {len(articles_id_list)}, total time: {time.time() - start_time:.2f}s"""
        )
        return all_results

    async def _search_pubmed_with_sync_api(
        self, query: str, top_k: int, search_type: str, semaphore: asyncio.Semaphore
    ) -> List[str]:
        """
        使用PubMedApi的search_database方法，但通过异步包装来提升并发效率

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            search_type: 搜索类型
            semaphore: 信号量用于限制并发数

        Returns:
            文章ID列表
        """
        async with semaphore:
            try:
                # 在线程池中运行同步的search_database方法
                loop = asyncio.get_event_loop()
                
                # 使用锁来防止并发Bio.Entrez操作
                def search_with_lock():
                    with self._bio_entrez_lock:
                        pubmed_api = PubMedApi()
                        return pubmed_api.search_database(query, top_k, search_type)

                # 使用run_in_executor来异步执行同步方法
                id_list = await loop.run_in_executor(None, search_with_lock)
                return id_list
            except Exception as e:
                logger.error(f"Error in PubMed search for query '{query}': {e}")
                raise e

    async def fetch_article_details(
        self, articles_id_list: List[str]
    ) -> List[BaseBioDocument]:
        """根据文章ID从pubmed获取文章详细信息"""
        if not articles_id_list:
            return []

        # 将articles_id_list去重
        articles_id_list = list(set(articles_id_list))

        # 将articles_id_list以group_size个一组切分成不同的列表
        group_size = 20
        articles_id_groups = [
            articles_id_list[i : i + group_size]
            for i in range(0, len(articles_id_list), group_size)
        ]

        try:
            # 限制并发获取操作数量
            semaphore = asyncio.Semaphore(self._max_concurrent_searches)
            
            # 并发获取所有组的详细信息
            batch_tasks = []
            for ids in articles_id_groups:
                task = self._fetch_details_with_semaphore(ids, semaphore)
                batch_tasks.append(task)

            task_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            fetch_results = []
            for result in task_results:
                if isinstance(result, Exception):
                    logger.error(f"Error in fetch_details: {result}")
                    continue
                fetch_results.extend(result)

        except Exception as e:
            logger.error(f"Error in concurrent fetch_details: {e}")
            return []

        # 转换为BioDocument对象
        all_results = [
            create_bio_document(
                title=result["title"],
                abstract=result["abstract"],
                authors=self.process_authors(result["authors"]),
                doi=result["doi"],
                source=self.data_source,
                source_id=result["pmid"],
                pub_date=result["pub_date"],
                journal=result["journal"],
                text=result["abstract"],
                url=f'https://pubmed.ncbi.nlm.nih.gov/{result["pmid"]}',
            )
            for result in fetch_results
        ]
        return all_results

    async def _fetch_details_with_semaphore(self, ids: List[str], semaphore: asyncio.Semaphore):
        """使用信号量限制并发数的获取详细信息方法"""
        async with semaphore:
            pubmed_async_api = PubMedAsyncApi()
            return await pubmed_async_api.fetch_details(id_list=ids)

    def process_authors(self, author_list: List[Dict]) -> str:
        """处理作者列表，将其转换为字符串"""
        return ", ".join(
            [f"{author['forename']} {author['lastname']}" for author in author_list]
        )
