import xml.etree.ElementTree as ET

from academic_mcp.models import Author, Paper, PaperDetail, SearchQuery
from academic_mcp.providers.base import BaseProvider


def _get_cdata_text(element: ET.Element | None, tag: str) -> str:
    """Get text from element, handling CDATA and 'null' values."""
    if element is None:
        return ""
    child = element.find(tag)
    if child is None or child.text is None:
        return ""
    text = child.text.strip()
    return "" if text == "null" else text


class NRICHProvider(BaseProvider):
    """국립문화유산연구원 - 일제강점기 문헌목록 Open API"""

    name = "nrich"
    display_name = "국립문화유산연구원"
    base_url = "http://portal.nrich.go.kr/kor/openapi.do"

    async def search(self, query: SearchQuery) -> list[Paper]:
        """일제강점기 문헌목록 검색 (idx=10)"""
        params = {
            "idx": "10",
            "firstindex": "1",
            "recordcountperpage": str(query.max_results),
        }

        try:
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()

            # XML 파싱: <list><data>...</data></list>
            root = ET.fromstring(response.content)
            items = root.findall(".//data")

            papers = []
            for item in items:
                id_val = _get_cdata_text(item, "md_data2")

                # 제목: 명칭(한글) 우선, 없으면 명칭(한문), 없으면 논문/도서 제목
                title = _get_cdata_text(item, "md_data4") or _get_cdata_text(item, "md_data3")
                if not title:
                    title = _get_cdata_text(item, "md_data8") or _get_cdata_text(item, "md_data7")
                if not title:
                    continue

                # 저자: Author 객체로 변환
                author_name = _get_cdata_text(item, "md_data6") or _get_cdata_text(item, "md_data5")
                authors = [Author(name=author_name)] if author_name else []

                # 연도
                year_str = _get_cdata_text(item, "md_data11")
                year = int(year_str) if year_str and year_str.isdigit() else None

                # URL
                url = _get_cdata_text(item, "md_data18")

                papers.append(
                    Paper(
                        id=id_val,
                        source="nrich",
                        title=title,
                        authors=authors,
                        year=year,
                        url=url,
                    )
                )

            # 클라이언트 사이드 필터링
            if query.keyword:
                kw = query.keyword.lower()
                papers = [
                    p
                    for p in papers
                    if kw in p.title.lower()
                    or any(kw in a.name.lower() for a in p.authors)
                ]

            return papers

        except Exception as e:
            print(f"NRICH Search Error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """상세 조회 (별도 API 없음 - 목록의 DATA_LINK 사용)"""
        return None
