from abc import ABC, abstractmethod
from typing import ClassVar

import httpx

from academic_mcp.models import Paper, PaperDetail, SearchQuery, Citation, ProviderCategory


class BaseProvider(ABC):
    """학술 정보 제공 기관 API 클라이언트 베이스 클래스"""

    name: ClassVar[str]  # 기관 식별자 (예: "kci", "riss")
    display_name: ClassVar[str]  # 표시명 (예: "한국학술지인용색인")
    category: ClassVar[ProviderCategory]  # 카테고리 (논문, 고서류, 사전 등)

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[Paper]:
        """논문/문헌 검색"""
        ...

    @abstractmethod
    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """논문/문헌 상세 정보 조회"""
        ...

    async def get_citations(self, paper_id: str) -> list[Citation]:
        """인용 정보 조회 (지원하는 기관만 구현)"""
        return []

    def is_available(self) -> bool:
        """API 사용 가능 여부 (키 필요 여부 등)"""
        return True
