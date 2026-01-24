"""국립국악원 - 학술연구(고서) Provider

KCISA API 기반으로, 국립국악원에서 제공하는 고서 자료를 검색합니다.
"""

from typing import ClassVar

from academic_mcp.models import ProviderCategory
from academic_mcp.providers.base_kcisa import BaseKCISAProvider, KCISAFieldMapping


class GugakProvider(BaseKCISAProvider):
    """국립국악원 - 학술연구(고서) Provider"""

    name: ClassVar[str] = "gugak"
    display_name: ClassVar[str] = "국립국악원(학술연구-고서)"
    category: ClassVar[ProviderCategory] = ProviderCategory.ANCIENT

    BASE_URL: ClassVar[str] = "https://api.kcisa.kr/openapi/service/rest/meta10/get20150035"
    DEFAULT_JOURNAL: ClassVar[str] = "국립국악원 고서"
    
    FIELD_MAPPING: ClassVar[KCISAFieldMapping] = KCISAFieldMapping(
        title="title",
        creator="creator",
        description="description",
        url="url",
        category="subjectCategory",
        date="regDate",
        temporal="temporal",  # 시간적 범위 (고서 특화)
    )

    def _build_abstract(
        self, 
        description: str, 
        alt_title: str, 
        temporal: str, 
        category: str
    ) -> str | None:
        """Gugak 특화: temporal과 category 정보를 포함"""
        parts = []
        if description:
            parts.append(description)
        if temporal:
            parts.append(f"시간적범위: {temporal}")
        if category:
            parts.append(f"분류: {category}")
        
        return "\n".join(parts) if parts else None
