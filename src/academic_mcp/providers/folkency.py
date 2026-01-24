"""국립민속박물관 - 한국민속대백과사전 Provider

KCISA API 기반으로, 한국민속대백과사전의 민속 자료를 검색합니다.
한국 민속에 대한 총체적 설명을 제공하는 전문백과사전입니다.
"""

from typing import ClassVar

from academic_mcp.models import ProviderCategory
from academic_mcp.providers.base_kcisa import BaseKCISAProvider, KCISAFieldMapping


class FolkencyProvider(BaseKCISAProvider):
    """국립민속박물관 - 한국민속대백과사전 Provider"""

    name: ClassVar[str] = "folkency"
    display_name: ClassVar[str] = "한국민속대백과사전"
    category: ClassVar[ProviderCategory] = ProviderCategory.DICTIONARY

    BASE_URL: ClassVar[str] = "https://api.kcisa.kr/openapi/API_CHA_083/request"
    DEFAULT_JOURNAL: ClassVar[str] = "한국민속대백과사전"
    
    # 이 API는 필드명이 대문자로 되어 있음
    FIELD_MAPPING: ClassVar[KCISAFieldMapping] = KCISAFieldMapping(
        title="TITLE",
        creator="AUTHOR",
        description="DESCRIPTION",
        url="URL",
        category="SUBJECT_KEYWORD",  # 키워드를 카테고리 대용으로 사용
        date="ISSUED_DATE",
        alternative_title="ALTERNATIVE_TITLE",  # 부제
    )

    def _build_abstract(
        self, 
        description: str, 
        alt_title: str, 
        temporal: str, 
        category: str
    ) -> str | None:
        """Folkency 특화: 부제와 키워드 정보 포함"""
        parts = []
        if alt_title:
            parts.append(f"[부제] {alt_title}")
        if description:
            # 설명이 매우 길 수 있으므로 적절히 truncate
            if len(description) > 500:
                parts.append(description[:500] + "...")
            else:
                parts.append(description)
        if category:
            parts.append(f"키워드: {category}")
        
        return "\n\n".join(parts) if parts else None
