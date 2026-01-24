"""KCISA(문화포털) API 기반 Provider 공통 베이스 클래스

문화체육관광부 공공데이터광장(culture.go.kr)에서 제공하는 
KCISA API들의 공통 패턴을 추상화합니다.
"""

import xml.etree.ElementTree as ET
from abc import abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from academic_mcp.models import Author, Paper, PaperDetail, SearchQuery, ProviderCategory
from academic_mcp.providers.base import BaseProvider


def _get_text(element: ET.Element | None, tag: str) -> str:
    """XML 요소에서 태그의 텍스트 추출"""
    if element is None:
        return ""
    child = element.find(tag)
    if child is None or not child.text:
        return ""
    return child.text.strip()


@dataclass
class KCISAFieldMapping:
    """KCISA API 응답 필드와 Paper 모델 필드 간의 매핑 정의
    
    각 Provider는 자신의 API 응답 구조에 맞게 이 매핑을 정의합니다.
    """
    title: str = "title"
    creator: str = "creator"
    description: str = "description"
    url: str = "url"
    category: str = "subjectCategory"
    date: str = "regDate"
    alternative_title: str | None = None  # 일부 API에서 사용
    temporal: str | None = None  # 시간적 범위 (gugak 등)


class BaseKCISAProvider(BaseProvider):
    """KCISA API 기반 Provider의 공통 추상 베이스 클래스
    
    하위 클래스에서 구현해야 할 것:
    - name, display_name, category: ClassVar
    - BASE_URL: str
    - FIELD_MAPPING: KCISAFieldMapping
    - _build_abstract(): 선택적 오버라이드
    """
    
    # 하위 클래스에서 정의해야 할 ClassVar들
    name: ClassVar[str]
    display_name: ClassVar[str]
    category: ClassVar[ProviderCategory]
    
    # 하위 클래스에서 정의해야 할 설정들
    BASE_URL: ClassVar[str]
    FIELD_MAPPING: ClassVar[KCISAFieldMapping]
    DEFAULT_JOURNAL: ClassVar[str] = ""
    
    def is_available(self) -> bool:
        return self.api_key is not None

    async def search(self, query: SearchQuery) -> list[Paper]:
        """KCISA API 공통 검색 로직"""
        if not self.api_key:
            return []

        params = {
            "serviceKey": self.api_key,
            "numOfRows": str(query.max_results),
            "pageNo": "1",
        }

        if query.keyword:
            params["keyword"] = query.keyword

        try:
            response = await self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            return self._parse_response(response.content)

        except Exception as e:
            print(f"[{self.name.upper()}] Search error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """상세 정보 조회 (KCISA API 구조상 목록 정보로 대체)"""
        return None

    def _parse_response(self, content: bytes) -> list[Paper]:
        """XML 응답 파싱 - 공통 로직"""
        papers = []
        try:
            root = ET.fromstring(content)
            items = root.findall(".//item")

            for item in items:
                try:
                    paper = self._parse_item(item)
                    if paper:
                        papers.append(paper)
                except Exception as e:
                    print(f"[{self.name.upper()}] Item parse error: {e}")
                    continue

        except Exception as e:
            print(f"[{self.name.upper()}] XML parse error: {e}")
        
        return papers

    def _parse_item(self, item: ET.Element) -> Paper | None:
        """개별 아이템 파싱 - 필드 매핑 기반"""
        fm = self.FIELD_MAPPING
        
        title = _get_text(item, fm.title)
        if not title:
            return None
            
        creator = _get_text(item, fm.creator)
        description = _get_text(item, fm.description)
        url = _get_text(item, fm.url)
        category = _get_text(item, fm.category)
        date_str = _get_text(item, fm.date)
        
        # 선택적 필드
        alt_title = _get_text(item, fm.alternative_title) if fm.alternative_title else ""
        temporal = _get_text(item, fm.temporal) if fm.temporal else ""
        
        # ID 생성
        paper_id = url if url else title
        
        # 저자
        authors = [Author(name=creator)] if creator else []
        
        # Abstract 구성 (하위 클래스에서 오버라이드 가능)
        abstract = self._build_abstract(
            description=description,
            alt_title=alt_title,
            temporal=temporal,
            category=category
        )
        
        # 연도 추출
        year = None
        if date_str and len(date_str) >= 4 and date_str[:4].isdigit():
            year = int(date_str[:4])
        
        return Paper(
            id=paper_id,
            source=self.name,
            title=title,
            authors=authors,
            journal=category or self.DEFAULT_JOURNAL,
            year=year,
            url=url,
            abstract=abstract
        )

    def _build_abstract(
        self, 
        description: str, 
        alt_title: str, 
        temporal: str, 
        category: str
    ) -> str | None:
        """Abstract 문자열 구성 - 하위 클래스에서 오버라이드 가능"""
        parts = []
        if alt_title:
            parts.append(f"[이칭] {alt_title}")
        if description:
            parts.append(description)
        if temporal:
            parts.append(f"시간적범위: {temporal}")
        
        return "\n\n".join(parts) if parts else None
