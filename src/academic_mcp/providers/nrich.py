"""국립문화유산연구원 Open API Provider (멀티 엔드포인트)

NRICH(National Research Institute of Cultural Heritage) 포털에서 제공하는
여러 API 엔드포인트를 하나의 Provider로 통합하여 지원합니다.

Available Datasets (idx):
- 39: 한국고고학사전 (기본값)
- 10: 일제강점기 문헌목록
- 추후 추가 가능
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import ClassVar

from academic_mcp.models import Author, Paper, PaperDetail, SearchQuery, ProviderCategory
from academic_mcp.providers.base import BaseProvider


def _get_cdata_text(element: ET.Element | None, tag: str) -> str:
    """XML 요소에서 텍스트 추출 (CDATA, null 처리)"""
    if element is None:
        return ""
    child = element.find(tag)
    if child is None or child.text is None:
        return ""
    text = child.text.strip()
    return "" if text == "null" else text


@dataclass
class NRICHEndpoint:
    """NRICH API 엔드포인트 정의"""
    idx: str
    name: str
    display_name: str
    category: ProviderCategory
    default_journal: str
    # 필드 매핑 (md_data* 필드 → 의미)
    id_field: str = "md_data2"
    title_field: str = "md_data3"
    content_field: str = "md_data4"  # 내용/정의
    reference_field: str = "md_data5"  # 참고문헌
    source_field: str = "md_data8"  # 출전/사전명
    url_field: str = "md_data12"


# 지원하는 엔드포인트 목록
NRICH_ENDPOINTS: dict[str, NRICHEndpoint] = {
    "archaeology": NRICHEndpoint(
        idx="39",
        name="archaeology",
        display_name="한국고고학사전",
        category=ProviderCategory.DICTIONARY,
        default_journal="한국고고학사전",
    ),
    "colonial_docs": NRICHEndpoint(
        idx="10",
        name="colonial_docs",
        display_name="일제강점기 문헌목록",
        category=ProviderCategory.ANCIENT,
        default_journal="일제강점기 문헌목록",
    ),
    # 추후 추가 가능:
    # "excavation": NRICHEndpoint(idx="?", name="excavation", ...),
}

DEFAULT_DATASET = "archaeology"


class NRICHProvider(BaseProvider):
    """국립문화유산연구원 Open API Provider
    
    여러 데이터셋(idx)을 하나의 Provider로 통합 지원합니다.
    
    사용 예:
    - 기본(한국고고학사전): search(query)
    - 특정 데이터셋: search(query, dataset="colonial_docs")
    - 전체 순회: search(query, dataset="all")
    
    Note:
    - 서버 측 검색을 지원하지 않아 전체 데이터를 가져온 후 클라이언트에서 필터링합니다.
    - API 키가 필요 없습니다.
    """

    name: ClassVar[str] = "nrich"
    display_name: ClassVar[str] = "국립문화유산연구원"
    category: ClassVar[ProviderCategory] = ProviderCategory.DICTIONARY  # 기본 카테고리
    
    BASE_URL = "http://portal.nrich.go.kr/kor/openapi.do"

    def is_available(self) -> bool:
        return True  # API 키 불필요

    async def search(
        self, 
        query: SearchQuery, 
        dataset: str | None = None
    ) -> list[Paper]:
        """NRICH 데이터 검색
        
        Args:
            query: 검색 쿼리
            dataset: 데이터셋 이름 ("archaeology", "colonial_docs", "all")
                     None이면 기본값(archaeology) 사용
        
        Returns:
            검색 결과 Paper 목록
        """
        dataset = dataset or DEFAULT_DATASET
        
        if dataset == "all":
            # 모든 엔드포인트 순회
            all_papers = []
            for ep in NRICH_ENDPOINTS.values():
                papers = await self._search_endpoint(query, ep)
                all_papers.extend(papers)
            return all_papers[:query.max_results]
        
        if dataset not in NRICH_ENDPOINTS:
            print(f"[NRICH] Unknown dataset: {dataset}. Using default.")
            dataset = DEFAULT_DATASET
        
        endpoint = NRICH_ENDPOINTS[dataset]
        return await self._search_endpoint(query, endpoint)

    async def _search_endpoint(
        self, 
        query: SearchQuery, 
        endpoint: NRICHEndpoint
    ) -> list[Paper]:
        """특정 엔드포인트에서 검색"""
        params = {
            "idx": endpoint.idx,
            "firstindex": "1",
            "recordcountperpage": "3000",  # 서버 검색 미지원, 전체 수집
        }

        try:
            response = await self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()

            papers = self._parse_response(response.content, endpoint)

            # 클라이언트 사이드 필터링
            if query.keyword:
                kw = query.keyword.lower()
                papers = [
                    p for p in papers
                    if kw in p.title.lower() or (p.abstract and kw in p.abstract.lower())
                ]

            return papers[:query.max_results]

        except Exception as e:
            print(f"[NRICH/{endpoint.name}] Search error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """상세 정보 조회"""
        return None

    def _parse_response(
        self, 
        content: bytes, 
        endpoint: NRICHEndpoint
    ) -> list[Paper]:
        """XML 응답 파싱"""
        papers = []
        try:
            root = ET.fromstring(content)
            items = root.findall(".//data")

            for item in items:
                try:
                    paper_id = _get_cdata_text(item, endpoint.id_field)
                    title = _get_cdata_text(item, endpoint.title_field)
                    
                    if not paper_id or not title:
                        continue

                    content_text = _get_cdata_text(item, endpoint.content_field)
                    references = _get_cdata_text(item, endpoint.reference_field)
                    source_name = _get_cdata_text(item, endpoint.source_field)
                    url = _get_cdata_text(item, endpoint.url_field)

                    # Abstract 구성
                    abstract = content_text
                    if references:
                        abstract += f"\n\n[참고문헌]\n{references}"

                    papers.append(Paper(
                        id=paper_id,
                        source=f"nrich_{endpoint.name}",  # 출처 구분
                        title=title,
                        authors=[],
                        journal=source_name or endpoint.default_journal,
                        year=None,
                        url=url or None,
                        abstract=abstract
                    ))
                except Exception as e:
                    print(f"[NRICH/{endpoint.name}] Item parse error: {e}")
                    continue

        except Exception as e:
            print(f"[NRICH/{endpoint.name}] XML parse error: {e}")
        
        return papers

    @classmethod
    def list_datasets(cls) -> dict[str, str]:
        """사용 가능한 데이터셋 목록 반환"""
        return {name: ep.display_name for name, ep in NRICH_ENDPOINTS.items()}
