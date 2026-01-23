import xml.etree.ElementTree as ET

from academic_mcp.models import Author, Paper, PaperDetail, SearchQuery
from academic_mcp.providers.base import BaseProvider


class KoreanTKProvider(BaseProvider):
    """지식재산 용어사전 (공공데이터포털)"""

    name = "koreantk"
    display_name = "지식재산 용어사전"
    base_url = "http://apis.data.go.kr/1430000/TermDicInfoService"

    async def search(self, query: SearchQuery) -> list[Paper]:
        """용어 검색"""
        if not self.api_key:
            return []

        params = {
            "serviceKey": self.api_key,
            "termNm": query.keyword,
            "numOfRows": str(query.max_results),
            "pageNo": "1",
        }

        try:
            response = await self.client.get(
                f"{self.base_url}/getTermDicSearch",
                params=params,
            )
            response.raise_for_status()

            # XML 파싱
            root = ET.fromstring(response.content)
            items = root.findall(".//item")

            papers = []
            for item in items:
                dic_cd = item.findtext("dicCd", "")
                term_nm = item.findtext("termNm", "")
                term_df = item.findtext("termDf", "")  # 정의

                if not term_nm:
                    continue

                papers.append(
                    Paper(
                        id=dic_cd,
                        source="koreantk",
                        title=term_nm,
                        authors=[Author(name="특허청")],
                        url="https://www.kipris.or.kr/",
                        # 정의는 PaperDetail.abstract에 있으므로 여기서는 생략
                    )
                )

            return papers

        except Exception as e:
            print(f"KoreanTK Search Error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """상세 조회 (현재 미지원)"""
        return None
