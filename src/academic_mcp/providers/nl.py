"""국립중앙도서관 서지 정보 Provider

공공데이터포털 API:
- Endpoint: https://apis.data.go.kr/1371029/BookInformationService
- /getbookList - 도서 검색
- /getElectronicJournalList - 전자저널 검색
"""

import json
from typing import ClassVar

from academic_mcp.models import Paper, PaperDetail, SearchQuery, Author
from academic_mcp.providers.base import BaseProvider


class NLProvider(BaseProvider):
    """국립중앙도서관 서지 정보 API 클라이언트"""

    name: ClassVar[str] = "nl"
    display_name: ClassVar[str] = "국립중앙도서관"

    BASE_URL = "https://apis.data.go.kr/1371029/BookInformationService"
    BOOK_LIST_URL = f"{BASE_URL}/getbookList"
    JOURNAL_LIST_URL = f"{BASE_URL}/getElectronicJournalList"

    def is_available(self) -> bool:
        return self.api_key is not None

    async def search(self, query: SearchQuery) -> list[Paper]:
        """도서/전자저널 검색"""
        if not self.api_key:
            return []

        # 도서 검색과 전자저널 검색을 병렬로 수행
        import asyncio
        book_task = self._search_books(query)
        journal_task = self._search_journals(query)

        results = await asyncio.gather(book_task, journal_task, return_exceptions=True)

        papers = []
        for result in results:
            if isinstance(result, list):
                papers.extend(result)

        return papers[:query.max_results]

    async def _search_books(self, query: SearchQuery) -> list[Paper]:
        """도서 검색"""
        params = {
            "serviceKey": self.api_key,
            "pageNo": "1",
            "numOfRows": str(query.max_results),
            "resultType": "json",
        }

        # 검색어 설정
        if query.keyword:
            params["titleKeyword"] = query.keyword
        if query.author:
            params["authorKeyword"] = query.author

        try:
            response = await self.client.get(self.BOOK_LIST_URL, params=params)
            response.raise_for_status()
            return self._parse_json_response(response.text, "book")
        except Exception as e:
            print(f"[NL] Book search error: {e}")
            return []

    async def _search_journals(self, query: SearchQuery) -> list[Paper]:
        """전자저널 검색"""
        params = {
            "serviceKey": self.api_key,
            "pageNo": "1",
            "numOfRows": str(min(query.max_results, 20)),
            "resultType": "json",
        }

        if query.keyword:
            params["titleKeyword"] = query.keyword

        try:
            response = await self.client.get(self.JOURNAL_LIST_URL, params=params)
            response.raise_for_status()
            return self._parse_json_response(response.text, "journal")
        except Exception as e:
            print(f"[NL] Journal search error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """상세 정보 조회 (현재 API는 목록만 제공)"""
        # 국립중앙도서관 API는 상세 조회 엔드포인트가 없음
        # ID로 다시 검색하여 정보 반환
        return None

    def _parse_json_response(self, text: str, doc_type: str) -> list[Paper]:
        """JSON 응답 파싱"""
        papers = []
        try:
            data = json.loads(text)

            # 응답 구조 확인
            response = data.get("response", data)
            body = response.get("body", {})
            items = body.get("items", {})

            # items가 리스트인 경우와 딕셔너리인 경우 처리
            item_list = items if isinstance(items, list) else items.get("item", [])
            if not isinstance(item_list, list):
                item_list = [item_list] if item_list else []

            for item in item_list:
                paper = self._parse_item(item, doc_type)
                if paper:
                    papers.append(paper)

        except json.JSONDecodeError as e:
            print(f"[NL] JSON parse error: {e}")
        except Exception as e:
            print(f"[NL] Parse error: {e}")

        return papers

    def _parse_item(self, item: dict, doc_type: str) -> Paper | None:
        """개별 항목 파싱"""
        try:
            # ID 추출
            paper_id = str(
                item.get("controlNo") or
                item.get("isbn") or
                item.get("id") or
                ""
            )

            # 제목 추출
            title = (
                item.get("titleInfo") or
                item.get("title") or
                ""
            ).strip()

            if not paper_id or not title:
                return None

            # 저자 파싱
            authors = []
            author_info = item.get("authorInfo") or item.get("author") or ""
            if author_info:
                # 저자 정보에서 이름 추출 (다양한 형식 처리)
                for name in str(author_info).replace(",", ";").split(";"):
                    name = name.strip()
                    if name and not name.startswith("["):
                        authors.append(Author(name=name))

            # 연도 파싱
            year = None
            pub_year = item.get("pubYear") or item.get("publishYear") or ""
            if pub_year:
                year_str = str(pub_year)[:4]
                if year_str.isdigit():
                    year = int(year_str)

            return Paper(
                id=paper_id,
                source=self.name,
                title=title,
                authors=authors,
                journal=item.get("publisher") or item.get("publisherInfo"),
                year=year,
                doi=item.get("doi"),
                url=item.get("url") or item.get("detailLink"),
            )
        except Exception as e:
            print(f"[NL] Item parse error: {e}")
            return None
