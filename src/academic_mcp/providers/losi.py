"""LOSI (국가학술정보) Provider

국회도서관 국가학술정보 OpenAPI (losi-api.nanet.go.kr)
- 통합검색: POST /searchTotal
- 상세보기: POST /searchView
- 연관학술지: POST /relJournal
- 연구자정보: POST /authorView
- 주제어정보: POST /subjectView
"""

from typing import ClassVar

from academic_mcp.models import Author, Paper, PaperDetail, SearchQuery
from academic_mcp.providers.base import BaseProvider


class LOSIProvider(BaseProvider):
    """LOSI (국가학술정보) API 클라이언트"""

    name: ClassVar[str] = "losi"
    display_name: ClassVar[str] = "국가학술정보(LOSI)"

    # API 엔드포인트
    BASE_URL = "http://losi-api.nanet.go.kr"
    SEARCH_URL = f"{BASE_URL}/searchTotal"
    DETAIL_URL = f"{BASE_URL}/searchView"

    def is_available(self) -> bool:
        return self.api_key is not None

    async def search(self, query: SearchQuery) -> list[Paper]:
        """LOSI 학술정보 통합검색 (POST)"""
        if not self.api_key:
            return []

        # 검색 파라미터 구성
        params = {
            "authKey": self.api_key,
            "searchTerm": query.keyword,
            "searchRange": "ARTICLE",  # ARTICLE, THESIS, BOOK
            "pageNo": 1,
            "displayCnt": query.max_results,
        }

        # 저자 검색 시 검색어에 포함
        if query.author:
            params["searchTerm"] = f"{query.keyword} {query.author}"

        try:
            response = await self.client.post(
                self.SEARCH_URL,
                data=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return self._parse_search_response(response.json())
        except Exception as e:
            print(f"[LOSI] Search error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """LOSI 상세 정보 조회 (POST)

        paper_id 형식: "{divFlag}:{lodID}" (예: "ARTICLE:123456")
        """
        if not self.api_key:
            return None

        # paper_id에서 divFlag와 lodID 분리
        if ":" in paper_id:
            div_flag, lod_id = paper_id.split(":", 1)
        else:
            # 기본값으로 ARTICLE 사용
            div_flag = "ARTICLE"
            lod_id = paper_id

        params = {
            "authKey": self.api_key,
            "lodID": lod_id,
            "divFlag": div_flag,
        }

        try:
            response = await self.client.post(
                self.DETAIL_URL,
                data=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return self._parse_detail_response(response.json(), paper_id)
        except Exception as e:
            print(f"[LOSI] Detail error: {e}")
            return None

    def _parse_search_response(self, data: dict) -> list[Paper]:
        """검색 결과 JSON 파싱

        응답 구조: {"result": [{"searchList": [...]}]}
        """
        papers = []

        try:
            # 에러 체크
            if data.get("resultCode") and data.get("resultCode") != "00":
                print(f"[LOSI] API Error: {data.get('resultMsg', 'Unknown error')}")
                return []

            # 결과 목록 추출: result[0].searchList
            result = data.get("result", [])
            if isinstance(result, list) and len(result) > 0:
                items = result[0].get("searchList", [])
            else:
                items = []

            for item in items:
                paper = self._parse_item(item)
                if paper:
                    papers.append(paper)

        except Exception as e:
            print(f"[LOSI] Parse error: {e}")

        return papers

    def _parse_item(self, item: dict) -> Paper | None:
        """개별 항목 파싱

        항목 구조:
        {
            "divFlag": "ARTICLE",
            "lodID": "9282594",
            "title": "...",
            "pubYear": "2025",
            "authorList": [{"lodAuthorID": null, "name": "..."}],
            "publisher": "...",
            "journal": {"lodJournalID": "117528", "title": "..."},
            "keywordList": [...],
            "url": null,
            "abstractCont": ""
        }
        """
        try:
            # ID 추출 - lodID 사용
            lod_id = str(item.get("lodID") or item.get("id") or "").strip()

            # 제목 추출
            title = str(item.get("title") or "").strip()

            if not lod_id or not title:
                return None

            # 자료구분 (divFlag)
            div_flag = str(item.get("divFlag") or "ARTICLE")

            # paper_id를 "divFlag:lodID" 형태로 저장
            paper_id = f"{div_flag}:{lod_id}"

            # 저자 파싱 - authorList 배열
            authors = []
            author_list = item.get("authorList") or []
            for author in author_list:
                if isinstance(author, dict):
                    name = author.get("name") or ""
                    if name.strip():
                        authors.append(Author(name=name.strip()))

            # 연도 추출 - pubYear
            year = None
            year_val = item.get("pubYear") or item.get("year")
            if year_val:
                year_str = str(year_val)[:4]
                if year_str.isdigit():
                    year = int(year_str)

            # 학술지 - journal 객체에서 title 추출
            journal_data = item.get("journal")
            journal = None
            if isinstance(journal_data, dict):
                journal = journal_data.get("title")
            elif isinstance(journal_data, str):
                journal = journal_data

            # 출판사
            publisher = item.get("publisher")

            return Paper(
                id=paper_id,
                source=self.name,
                title=title,
                authors=authors,
                journal=journal or publisher,
                year=year,
                doi=item.get("doi"),
                url=item.get("url") or item.get("linkUrl"),
            )

        except Exception as e:
            print(f"[LOSI] Item parse error: {e}")
            return None

    def _parse_detail_response(self, data: dict, paper_id: str) -> PaperDetail | None:
        """상세 정보 JSON 파싱"""
        try:
            # 에러 체크
            if data.get("resultCode") and data.get("resultCode") != "00":
                print(f"[LOSI] API Error: {data.get('resultMsg', 'Unknown error')}")
                return None

            # 상세 정보 추출
            item = (
                data.get("result")
                or data.get("item")
                or data.get("detail")
                or data
            )

            title = str(
                item.get("title")
                or item.get("articleTitle")
                or ""
            ).strip()

            if not title:
                return None

            # 저자 파싱
            authors = []
            author_data = item.get("author") or item.get("authors") or ""
            if isinstance(author_data, str):
                for name in author_data.replace(",", ";").split(";"):
                    name = name.strip()
                    if name:
                        authors.append(Author(name=name))
            elif isinstance(author_data, list):
                for author in author_data:
                    if isinstance(author, dict):
                        name = author.get("name") or author.get("authorNm") or ""
                    else:
                        name = str(author)
                    if name.strip():
                        authors.append(Author(name=name.strip()))

            # 연도
            year = None
            year_val = item.get("year") or item.get("pubYear")
            if year_val:
                year_str = str(year_val)[:4]
                if year_str.isdigit():
                    year = int(year_str)

            # 키워드
            keywords = []
            kw_data = item.get("keyword") or item.get("keywords") or []
            if isinstance(kw_data, str):
                keywords = [k.strip() for k in kw_data.replace(",", ";").split(";") if k.strip()]
            elif isinstance(kw_data, list):
                keywords = [str(k).strip() for k in kw_data if k]

            return PaperDetail(
                id=paper_id,
                source=self.name,
                title=title,
                authors=authors,
                journal=item.get("journal") or item.get("journalTitle") or item.get("source"),
                year=year,
                doi=item.get("doi"),
                url=item.get("url") or item.get("linkUrl"),
                abstract=item.get("abstract") or item.get("summary") or item.get("abstractKor"),
                keywords=keywords,
                volume=item.get("volume") or item.get("vol"),
                issue=item.get("issue") or item.get("no"),
                pages=item.get("pages") or item.get("page"),
                publisher=item.get("publisher") or item.get("publisherNm"),
            )

        except Exception as e:
            print(f"[LOSI] Detail parse error: {e}")
            return None
