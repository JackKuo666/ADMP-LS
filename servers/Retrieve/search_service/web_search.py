"""
Web search service for retrieving and processing web content.

This module provides functionality to search the web using Serper API
and extract content from web pages using crawl4ai.
"""

import asyncio
import os
from typing import List, Optional

from bio_requests.rag_request import RagRequest
from config.global_storage import get_model_config
from dto.bio_document import BaseBioDocument, create_bio_document
from search_service.base_search import BaseSearchService
from service.web_search import SerperClient, scrape_urls, url_to_fit_contents
from utils.bio_logger import bio_logger as logger


class WebSearchService(BaseSearchService):
    """
    Web search service that retrieves content from web pages.

    This service uses Serper API for web search and crawl4ai for content extraction.
    """

    def __init__(self):
        """Initialize the web search service."""
        self.data_source = "web"
        self._serper_client: Optional[SerperClient] = None
        self._max_results = 5
        self._content_length_limit = 40000  # ~10k tokens

    @property
    def serper_client(self) -> SerperClient:
        """Lazy initialization of SerperClient."""
        if self._serper_client is None:
            # Priority from environment variables, if not available then from config file
            api_key = os.getenv("SERPER_API_KEY")
            if not api_key:
                try:
                    config = get_model_config()
                    api_key = config.get("web_search", {}).get("serper_api_key")
                except Exception as e:
                    logger.warning(f"Failed to get Serper API key from config: {e}")
                    api_key = None
            
            if not api_key:
                raise ValueError("SERPER_API_KEY environment variable or config not found")
            
            self._serper_client = SerperClient(api_key=api_key)
        return self._serper_client

    async def search(self, rag_request: RagRequest) -> List[BaseBioDocument]:
        """
        Perform web search and extract content from search results.

        Args:
            rag_request: The RAG request containing the search query

        Returns:
            List of BaseBioDocument objects with extracted web content
        """
        try:
            query = rag_request.query
            logger.info(f"Starting web search for query: {query}")

            # Search for URLs using Serper
            url_results = await self.search_serper(query, rag_request.top_k)

            if not url_results:
                logger.info(f"No search results found for query: {query}")
                return []

            # Extract content from URLs
            search_results = await self.enrich_url_results_with_contents(url_results)

            logger.info(f"Web search completed. Found {len(search_results)} documents")
            return search_results

        except Exception as e:
            logger.error(f"Error during web search: {str(e)}", exc_info=e)
            return []

    async def enrich_url_results_with_contents(
        self, results: List
    ) -> List[BaseBioDocument]:
        """
        Extract content from URLs and create BaseBioDocument objects.

        Args:
            results: List of search results with URLs

        Returns:
            List of BaseBioDocument objects with extracted content
        """
        try:
            # Create tasks for concurrent content extraction
            tasks = [self._extract_content_from_url(res) for res in results]
            contents = await asyncio.gather(*tasks, return_exceptions=True)

            enriched_results = []
            for res, content in zip(results, contents):
                # Handle exceptions from content extraction
                if isinstance(content, Exception):
                    logger.error(f"Failed to extract content from {res.url}: {content}")
                    continue

                bio_doc = create_bio_document(
                    title=res.title,
                    url=res.url,
                    text=str(content)[: self._content_length_limit],
                    source=self.data_source,
                )
                enriched_results.append(bio_doc)

            return enriched_results

        except Exception as e:
            logger.error(f"Error enriching URL results: {str(e)}", exc_info=e)
            return []

    async def _extract_content_from_url(self, res) -> str:
        """
        Extract content from a single URL with error handling.

        Args:
            res: Search result object containing URL information

        Returns:
            Extracted content as string
        """
        try:
            return await url_to_fit_contents(res)
        except Exception as e:
            logger.error(f"Error extracting content from {res.url}: {str(e)}")
            return f"Error extracting content: {str(e)}"

    async def search_serper(
        self, query: str, max_results: Optional[int] = None
    ) -> List:
        """
        Perform web search using Serper API.

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of search results with URLs
        """
        try:
            max_results = max_results or self._max_results
            logger.info(f"Searching Serper for: {query} (max_results: {max_results})")

            search_results = await self.serper_client.search(
                query, filter_for_relevance=True, max_results=max_results
            )

            if not search_results:
                logger.info(f"No search results from Serper for query: {query}")
                return []

            # Scrape content from URLs
            results = await scrape_urls(search_results)

            logger.info(f"Serper search completed. Found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error in Serper search: {str(e)}", exc_info=e)
            return []
