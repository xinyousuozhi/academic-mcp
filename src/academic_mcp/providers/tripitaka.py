"""고려대장경연구소 - 고려대장경지식베이스 Provider

KCISA API 기반으로, 고려대장경 경전 정보를 검색합니다.
"""

from typing import ClassVar

from academic_mcp.models import ProviderCategory
from academic_mcp.providers.base_kcisa import BaseKCISAProvider, KCISAFieldMapping


class TripitakaProvider(BaseKCISAProvider):
    """고려대장경연구소 - 고려대장경지식베이스 Provider"""

    name: ClassVar[str] = "tripitaka"
    display_name: ClassVar[str] = "고려대장경지식베이스"
    category: ClassVar[ProviderCategory] = ProviderCategory.DICTIONARY

    BASE_URL: ClassVar[str] = "https://api.kcisa.kr/openapi/service/rest/other/getSUTN2601"
    DEFAULT_JOURNAL: ClassVar[str] = "고려대장경"
    
    FIELD_MAPPING: ClassVar[KCISAFieldMapping] = KCISAFieldMapping(
        title="title",
        creator="creator",
        description="description",  # 경전 해설 (핵심 내용)
        url="url",
        category="collectionDb",  # 소속DB
        date="regDate",
        alternative_title="alternativeTitle",  # 이칭/다른 표제
    )

    def _build_abstract(
        self, 
        description: str, 
        alt_title: str, 
        temporal: str, 
        category: str
    ) -> str | None:
        """Tripitaka 특화: 이칭(alternativeTitle)을 앞에 표시"""
        parts = []
        if alt_title:
            parts.append(f"[이칭] {alt_title}")
        if description:
            parts.append(description)
        
        return "\n\n".join(parts) if parts else None
