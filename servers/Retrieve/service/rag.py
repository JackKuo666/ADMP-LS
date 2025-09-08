import asyncio
import time
from typing import List
from service.rerank import RerankService
from search_service.base_search import BaseSearchService
from utils.bio_logger import bio_logger as logger

from dto.bio_document import BaseBioDocument

from bio_requests.rag_request import RagRequest


class RagService:
    def __init__(self):
        self.rerank_service = RerankService()
        # 确保所有子类都被加载
        self.search_services = [
            subclass() for subclass in BaseSearchService.get_subclasses()
        ]
        logger.info(
            f"Loaded search services: {[service.__class__.__name__ for service in self.search_services]}"
        )

    async def multi_query(self, rag_request: RagRequest) -> List[BaseBioDocument]:
        start_time = time.time()
        batch_search = [
            service.filter_search(rag_request=rag_request)
            for service in self.search_services
        ]
        task_result = await asyncio.gather(*batch_search, return_exceptions=True)
        all_results = []
        for result in task_result:
            if isinstance(result, Exception):
                logger.error(f"Error in search service: {result}")
                continue
            all_results.extend(result)
        end_search_time = time.time()
        logger.info(
            f"Found {len(all_results)} results in total,time used:{end_search_time - start_time:.2f}s"
        )
        if rag_request.is_rerank:
            logger.info("RerankService: is_rerank is True")
            reranked_results = await self.rerank_service.rerank(
                rag_request=rag_request, documents=all_results
            )
            end_rerank_time = time.time()
            logger.info(
                f"Reranked {len(reranked_results)} results,time used:{end_rerank_time - end_search_time:.2f}s"
            )
        else:
            logger.info("RerankService: is_rerank is False, skip rerank")
            reranked_results = all_results

        return reranked_results[0 : rag_request.top_k]
