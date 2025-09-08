"""
RAG request class, used to encapsulate the parameters of RAG requests
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class RagRequest(BaseModel):
    """
    RAG request class, used to encapsulate the parameters of RAG requests
    """

    query: str = Field(default="", description="Search query")

    top_k: int = Field(default=5, ge=1, description="Number of results to return")

    search_type: Optional[str] = Field(
        default="keyword",
        description="Type of search to perform (keyword or advanced), please note that if data_source is not ['pubmed'], this field will be ignored",
    )

    is_rewrite: Optional[bool] = Field(
        default=True, description="Whether the query is a subquery of a larger query"
    )

    data_source: List[str] = Field(
        default=["pubmed"],
        description="Data source to search in (e.g., pubmed, web)",
    )

    pubmed_topk: int = Field(
        default=30,
        description="Number of results to return from one specific pubmed search, only used when is_rewrite is True",
    )

    is_rerank: Optional[bool] = Field(
        default=True,
        description="Whether to use reranker to rerank the results, only used when data_source is ['pubmed']",
    )

    language: Optional[str] = Field(
        default="en", description="Response language (zh/en), default is English"
    )
