"""국사편찬위원회 역사지리정보(HGIS) Provider

역사지리정보 Open API:
- Base URL: https://hgis.history.go.kr/openapi/get.do
- 1919년 역사배경지도 (map1919)
- 1970년대 역사배경지도 (map1970)

Note: 이 API는 지도 레이어 정보를 제공하며, 문서 검색 기능은 없습니다.
"""

import xml.etree.ElementTree as ET
from typing import ClassVar

from academic_mcp.models import Paper, PaperDetail, SearchQuery, Author, ProviderCategory
from academic_mcp.providers.base import BaseProvider


class HGISProvider(BaseProvider):
    """국사편찬위원회 역사지리정보(HGIS) API 클라이언트

    역사지리정보 API는 지도 레이어 서비스를 제공합니다:
    - map1919: 1919년 역사배경지도
    - map1919_index: 1919년 지도 색인 정보
    - map1970: 1970년대 역사배경지도
    - map1970_index: 1970년대 지도 색인 정보

    Note: 문서 검색이 아닌 지도 메타데이터 제공
    """

    name: ClassVar[str] = "hgis"
    display_name: ClassVar[str] = "국사편찬위원회 역사지리정보(HGIS)"
    category: ClassVar[ProviderCategory] = ProviderCategory.ANCIENT

    BASE_URL = "https://hgis.history.go.kr/openapi/get.do"

    # 사용 가능한 레이어
    LAYERS = {
        "map1919": "1919년 역사배경지도",
        "map1919_index": "1919년 지도 색인",
        "map1970": "1970년대 역사배경지도",
        "map1970_index": "1970년대 지도 색인",
    }

    def is_available(self) -> bool:
        return self.api_key is not None

    async def search(self, query: SearchQuery) -> list[Paper]:
        """지도 레이어 정보 조회

        HGIS API는 문서 검색이 아닌 지도 레이어 메타데이터 제공.
        키워드에 따라 관련 레이어 정보 반환.
        """
        if not self.api_key:
            return []

        # 검색어에 따른 레이어 필터링
        results = []
        keyword = (query.keyword or "").lower()

        for layer_id, layer_name in self.LAYERS.items():
            # 키워드가 없거나 매칭되면 포함
            if not keyword or keyword in layer_name or keyword in layer_id:
                # 레이어 정보를 Paper 형태로 반환
                year = 1919 if "1919" in layer_id else 1970
                results.append(Paper(
                    id=layer_id,
                    source=self.name,
                    title=layer_name,
                    authors=[Author(name="국사편찬위원회")],
                    journal="역사지리정보시스템",
                    year=year,
                    doi=None,
                    url=f"https://hgis.history.go.kr/?layer={layer_id}",
                ))

        return results[:query.max_results]

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """레이어 상세 정보 조회"""
        if not self.api_key:
            return None

        layer_name = self.LAYERS.get(paper_id)
        if not layer_name:
            return None

        # WMTS GetCapabilities 요청으로 상세 정보 조회
        params = {
            "Service": "WMTS",
            "Request": "GetCapabilities",
            "apiKey": self.api_key,
        }

        try:
            response = await self.client.get(
                self.BASE_URL, params=params, timeout=30.0
            )
            response.raise_for_status()

            # XML 파싱하여 레이어 정보 추출
            capabilities = self._parse_capabilities(response.text, paper_id)

            year = 1919 if "1919" in paper_id else 1970
            description = f"{layer_name} - 국사편찬위원회 역사지리정보시스템 제공"

            if capabilities:
                description = capabilities.get("abstract", description)

            return PaperDetail(
                id=paper_id,
                source=self.name,
                title=layer_name,
                authors=[Author(name="국사편찬위원회")],
                journal="역사지리정보시스템",
                year=year,
                doi=None,
                url=f"https://hgis.history.go.kr/?layer={paper_id}",
                abstract=description,
                keywords=["역사지도", "HGIS", str(year)],
            )

        except Exception as e:
            print(f"[HGIS] GetCapabilities error: {e}")
            return None

    async def get_capabilities(self) -> dict | None:
        """WMTS GetCapabilities 조회"""
        if not self.api_key:
            return None

        params = {
            "Service": "WMTS",
            "Request": "GetCapabilities",
            "apiKey": self.api_key,
        }

        try:
            response = await self.client.get(
                self.BASE_URL, params=params, timeout=30.0
            )
            response.raise_for_status()

            return {"xml": response.text[:2000], "status": "success"}

        except Exception as e:
            print(f"[HGIS] GetCapabilities error: {e}")
            return {"error": str(e), "status": "failed"}

    def _parse_capabilities(self, xml_text: str, layer_id: str) -> dict | None:
        """GetCapabilities XML에서 레이어 정보 추출"""
        try:
            # WMTS 네임스페이스
            ns = {
                "wmts": "http://www.opengis.net/wmts/1.0",
                "ows": "http://www.opengis.net/ows/1.1",
            }

            root = ET.fromstring(xml_text)

            # Layer 요소 찾기
            for layer in root.findall(".//wmts:Layer", ns):
                identifier = layer.findtext("ows:Identifier", "", ns)
                if identifier == layer_id:
                    return {
                        "identifier": identifier,
                        "title": layer.findtext("ows:Title", "", ns),
                        "abstract": layer.findtext("ows:Abstract", "", ns),
                    }

            return None

        except Exception as e:
            print(f"[HGIS] XML parse error: {e}")
            return None
