from typing import List

from bio_requests.rag_request import RagRequest
from dto.bio_document import BaseBioDocument


class BaseSearchService:
    _registry = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseSearchService._registry.append(cls)

    @classmethod
    def get_subclasses(cls):
        return cls._registry

    def __init__(self):
        self.data_source = "Base"
        pass

    async def filter_search(self, rag_request: RagRequest) -> List[BaseBioDocument]:
        if self.data_source in rag_request.data_source:
            return await self.search(rag_request)
        return []

    async def search(self, rag_request: RagRequest) -> List[BaseBioDocument]:
        return []
