import xml.etree.ElementTree as ET

from academic_mcp.models import Author, Paper, PaperDetail, SearchQuery
from academic_mcp.providers.base import BaseProvider


class EYISProvider(BaseProvider):
    """여성사전시관 인물연구 정보 (공공데이터포털)"""

    name = "eyis"
    display_name = "여성사전시관 인물연구"
    base_url = "http://apis.data.go.kr/1383000/eyis/personResearchService/eyis/getPersonResearchList"

    async def search(self, query: SearchQuery) -> list[Paper]:
        """인물연구 검색"""
        if not self.api_key:
            return []

        params = {
            "serviceKey": self.api_key,
            "pageNo": "1",
            "type": "xml",
            "numOfRows": str(query.max_results),
            "prsnRsrchNm": query.keyword,  # 인물연구명으로 검색
        }

        try:
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()

            # XML 파싱
            root = ET.fromstring(response.content)

            # 에러 체크
            result_code = root.findtext(".//resultCode")
            if result_code and result_code != "0":
                result_msg = root.findtext(".//resultMsg", "Unknown error")
                print(f"EYIS API Error: {result_msg}")
                return []

            items = root.findall(".//item")

            papers = []
            for item in items:
                # 필드 매핑:
                # prsnRsrchNm: 인물연구명
                # prsnLbrtryNm: 인물연구실명 (시대 등)
                # regYmd: 등록일자
                # dataCrtrYmd: 데이터기준일자

                prsn_rsrch_nm = item.findtext("prsnRsrchNm", "")
                prsn_lbrtry_nm = item.findtext("prsnLbrtryNm", "")
                reg_ymd = item.findtext("regYmd", "")

                if not prsn_rsrch_nm:
                    continue

                # 연도 추출 (regYmd: YYYYMMDD 형식)
                year = None
                if reg_ymd and len(reg_ymd) >= 4:
                    try:
                        year = int(reg_ymd[:4])
                    except ValueError:
                        pass

                # ID 생성 (고유 식별자가 없으므로 조합)
                paper_id = f"eyis_{reg_ymd}_{prsn_rsrch_nm[:20]}"

                papers.append(
                    Paper(
                        id=paper_id,
                        source="eyis",
                        title=prsn_rsrch_nm,
                        authors=[Author(name="여성사전시관")],
                        journal=prsn_lbrtry_nm if prsn_lbrtry_nm else None,  # 시대 정보를 journal에
                        year=year,
                        url="https://www.hermuseum.go.kr/",
                    )
                )

            return papers

        except Exception as e:
            print(f"EYIS Search Error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """상세 조회 (현재 미지원)"""
        return None
