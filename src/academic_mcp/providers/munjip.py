"""한국고전번역원 한국문집총간 Provider

공공데이터포털(odcloud.kr) API를 통해 한국문집총간 목록을 검색합니다.
- 1,251종의 한국 고전 문집(文集) 카탈로그
- 제목 기반 키워드 검색 지원
- API 키 필요 (data.go.kr 활용신청)
"""

import re
from typing import ClassVar

from academic_mcp.models import Paper, PaperDetail, SearchQuery, Author, ProviderCategory
from academic_mcp.providers.base import BaseProvider


class MunjipProvider(BaseProvider):
    """한국고전번역원 한국문집총간 Provider"""

    name: ClassVar[str] = "munjip"
    display_name: ClassVar[str] = "한국문집총간"
    category: ClassVar[ProviderCategory] = ProviderCategory.ANCIENT

    API_URL = "https://api.odcloud.kr/api/3074298/v1/uddi:2718d2ff-3213-4cee-90df-f24d00c50f14"

    # 한국고전종합DB - 문집총간 원문 열람 가능
    DB_BASE_URL = "https://db.itkc.or.kr/dir/item?itemId=MO"

    def is_available(self) -> bool:
        """API 키가 있어야 사용 가능"""
        return self.api_key is not None and len(self.api_key) > 0

    async def search(self, query: SearchQuery) -> list[Paper]:
        """문집총간 검색

        키워드로 문집 제목을 검색합니다.
        예: '퇴계' → 퇴계집(退溪集)
            '유고' → 율곡전서(栗谷全書)
        """
        if not self.is_available():
            return []

        params = {
            "serviceKey": self.api_key,
            "page": "1",
            "perPage": str(query.max_results),
        }

        # 키워드가 있으면 제목 검색 조건 추가
        if query.keyword:
            params["cond[제목::LIKE]"] = query.keyword

        try:
            response = await self.client.get(self.API_URL, params=params)
            response.raise_for_status()

            data = response.json()
            return self._parse_response(data)

        except Exception as e:
            print(f"[MUNJIP] Search error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """개별 문집 상세 정보 조회

        현재 API는 상세 정보를 별도로 제공하지 않으므로,
        검색 결과에서 해당 ID의 항목을 반환합니다.
        """
        if not self.is_available():
            return None

        # 연번(ID)으로 직접 조회는 지원하지 않으므로,
        # 전체 목록에서 찾아야 함 (제한적)
        try:
            params = {
                "serviceKey": self.api_key,
                "page": "1",
                "perPage": "1251",  # 전체 목록 (1,251건)
            }

            response = await self.client.get(self.API_URL, params=params)
            response.raise_for_status()

            data = response.json()
            items = data.get("data", [])

            for item in items:
                item_id = str(item.get("연번", ""))
                if item_id == paper_id:
                    parsed = self._parse_title(item.get("제목", ""))
                    return PaperDetail(
                        id=item_id,
                        source=self.name,
                        title=parsed["display_title"],
                        authors=[],
                        journal="한국문집총간",
                        abstract=f"한국고전번역원 한국문집총간 수록 문집.\n원제: {parsed['original_title']}\n등록일: {parsed['date']}",
                        url=self.DB_BASE_URL,
                        publisher="한국고전번역원",
                    )

            return None

        except Exception as e:
            print(f"[MUNJIP] Detail error: {e}")
            return None

    def _parse_response(self, data: dict) -> list[Paper]:
        """API 응답을 Paper 리스트로 변환"""
        papers = []

        items = data.get("data", [])

        for item in items:
            try:
                item_id = str(item.get("연번", ""))
                raw_title = item.get("제목", "")

                if not raw_title:
                    continue

                parsed = self._parse_title(raw_title)

                paper = Paper(
                    id=item_id,
                    source=self.name,
                    title=parsed["display_title"],
                    authors=[],
                    journal="한국문집총간",
                    year=None,
                    url=self.DB_BASE_URL,
                    abstract=f"한국문집총간 수록. 원제: {parsed['original_title']}"
                             + (f" (등록일: {parsed['date']})" if parsed["date"] else ""),
                )
                papers.append(paper)

            except Exception as e:
                print(f"[MUNJIP] Parse error: {e}")
                continue

        return papers

    def _parse_title(self, raw_title: str) -> dict:
        """원본 제목 파싱

        입력 예시:
            "한국고전번역원_한국문집총간_퇴계집(退溪集)_20210125"
            "한국문집총간_율곡전서(栗谷全書)(등록일:2020.03.30)"

        반환:
            {
                "display_title": "퇴계집(退溪集)",
                "korean_name": "퇴계집",
                "chinese_name": "退溪集",
                "original_title": "한국문집총간_퇴계집(退溪集)",
                "date": "2021.01.25" 또는 ""
            }
        """
        result = {
            "display_title": raw_title,
            "korean_name": "",
            "chinese_name": "",
            "original_title": raw_title,
            "date": "",
        }

        # "한국고전번역원_" 또는 "한국문집총간_" 접두어 제거
        title = raw_title
        for prefix in ["한국고전번역원_한국문집총간_", "한국고전번역원_", "한국문집총간_"]:
            if title.startswith(prefix):
                title = title[len(prefix):]
                break

        # 날짜 추출: _YYYYMMDD 또는 (등록일:YYYY.MM.DD)
        date_match = re.search(r'_(\d{8})$', title)
        if date_match:
            d = date_match.group(1)
            result["date"] = f"{d[:4]}.{d[4:6]}.{d[6:8]}"
            title = title[:date_match.start()]

        date_match2 = re.search(r'\(등록일:([^)]+)\)', title)
        if date_match2:
            result["date"] = date_match2.group(1)
            title = title[:date_match2.start()].strip()

        # 한글명(漢字名) 분리
        hanja_match = re.search(r'^(.+?)\(([^)]+)\)$', title)
        if hanja_match:
            result["korean_name"] = hanja_match.group(1).strip()
            result["chinese_name"] = hanja_match.group(2).strip()
            result["display_title"] = f"{result['korean_name']}({result['chinese_name']})"
        else:
            result["display_title"] = title.strip()
            result["korean_name"] = title.strip()

        result["original_title"] = raw_title

        return result
