"""CiNii Research (일본 학술 데이터베이스) Provider

CiNii Research OpenSearch API:
- Base URL: https://cir.nii.ac.jp/opensearch/
- 검색 유형: all, articles, books, dissertations, data, projects
- 응답 형식: json, rss, atom

API 키 발급: https://support.nii.ac.jp/en/cinii/api/developer
"""

import json
from typing import ClassVar

from academic_mcp.models import Paper, PaperDetail, SearchQuery, Author, ProviderCategory
from academic_mcp.providers.base import BaseProvider


class CiNiiProvider(BaseProvider):
    """CiNii Research API 클라이언트

    일본 국립정보학연구소(NII)에서 운영하는 학술 데이터베이스.
    일본 학술논문, 도서, 학위논문, 연구 데이터 등 검색 가능.
    """

    name: ClassVar[str] = "cinii"
    display_name: ClassVar[str] = "CiNii Research (일본)"
    category: ClassVar[ProviderCategory] = ProviderCategory.PAPERS

    BASE_URL = "https://cir.nii.ac.jp/opensearch"

    # 검색 유형
    SEARCH_TYPES = {
        "all": "전체",
        "articles": "논문",
        "books": "도서",
        "dissertations": "학위논문",
        "data": "연구데이터",
        "projects": "연구프로젝트",
    }

    def is_available(self) -> bool:
        return self.api_key is not None

    async def search(self, query: SearchQuery) -> list[Paper]:
        """CiNii 논문 검색

        Args:
            query: 검색 쿼리 (keyword, author, year_from, year_to 지원)
        """
        if not self.api_key:
            return []

        # 기본 파라미터
        params = {
            "appid": self.api_key,
            "format": "json",
            "count": min(query.max_results, 200),
            "sortorder": "0",  # 관련도순 (1: 발행일 신순, 2: 피인용 많은순)
        }

        # 검색어 설정
        search_terms = []
        if query.keyword:
            search_terms.append(query.keyword)
        if query.author:
            search_terms.append(query.author)

        if search_terms:
            params["q"] = " ".join(search_terms)
        else:
            # 검색어 없으면 빈 결과
            return []

        # 연도 범위
        if query.year_from:
            params["from"] = str(query.year_from)
        if query.year_to:
            params["until"] = str(query.year_to)

        # 논문 검색 (articles)
        url = f"{self.BASE_URL}/articles"

        try:
            response = await self.client.get(url, params=params, timeout=30.0)
            response.raise_for_status()

            return self._parse_json_response(response.text)

        except Exception as e:
            print(f"[CiNii] Search error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """논문 상세 정보 조회

        Args:
            paper_id: CiNii 논문 ID (예: 1390577343641498624)
        """
        if not self.api_key:
            return None

        # CiNii Research의 개별 아이템 조회
        # 형식: https://cir.nii.ac.jp/crid/{paper_id}.json
        url = f"https://cir.nii.ac.jp/crid/{paper_id}.json"

        params = {"appid": self.api_key}

        try:
            response = await self.client.get(url, params=params, timeout=30.0)
            response.raise_for_status()

            return self._parse_detail_response(response.text, paper_id)

        except Exception as e:
            print(f"[CiNii] Detail error: {e}")
            return None

    def _parse_json_response(self, text: str) -> list[Paper]:
        """JSON 응답 파싱"""
        papers = []

        try:
            data = json.loads(text)

            # 검색 결과 메타데이터 확인
            total = data.get("opensearch:totalResults", 0)
            if total:
                print(f"[CiNii] Total results: {total}")

            # items 배열에서 논문 추출
            items = data.get("items", [])
            if not items:
                # @graph 형식도 지원 (이전 버전 호환)
                items = data.get("@graph", [])

            for item in items:
                # 채널 메타데이터 스킵
                item_type = item.get("@type", "")
                if item_type in ["channel", "hydra:Collection"]:
                    continue

                paper = self._parse_item(item)
                if paper:
                    papers.append(paper)

        except json.JSONDecodeError as e:
            print(f"[CiNii] JSON parse error: {e}")
        except Exception as e:
            print(f"[CiNii] Parse error: {e}")

        return papers

    def _parse_item(self, item: dict) -> Paper | None:
        """개별 논문 항목 파싱"""
        try:
            # ID 추출 (@id에서 CRID 추출)
            item_id = item.get("@id", "")
            paper_id = item_id.split("/")[-1] if "/" in item_id else item_id

            if not paper_id:
                return None

            # 제목 추출
            title = self._get_text(item.get("dc:title"))
            if not title:
                title = self._get_text(item.get("title"))
            if not title:
                return None

            # 저자 파싱
            authors = []
            creators = item.get("dc:creator", [])
            if not isinstance(creators, list):
                creators = [creators]

            for creator in creators:
                if isinstance(creator, str):
                    authors.append(Author(name=creator))
                elif isinstance(creator, dict):
                    name = creator.get("foaf:name") or creator.get("name") or ""
                    if isinstance(name, list):
                        name = name[0] if name else ""
                    if isinstance(name, dict):
                        name = name.get("@value", "")
                    if name:
                        authors.append(Author(name=name))

            # 연도 추출
            year = None
            date_str = item.get("prism:publicationDate") or item.get("dc:date") or ""
            if isinstance(date_str, list):
                date_str = date_str[0] if date_str else ""
            if isinstance(date_str, dict):
                date_str = date_str.get("@value", "")
            if date_str and len(str(date_str)) >= 4:
                year_str = str(date_str)[:4]
                if year_str.isdigit():
                    year = int(year_str)

            # 저널/출판사
            journal = self._get_text(item.get("prism:publicationName"))
            if not journal:
                journal = self._get_text(item.get("dc:publisher"))

            # DOI
            doi = None
            identifiers = item.get("prism:doi") or item.get("dc:identifier", [])
            if isinstance(identifiers, str) and identifiers.startswith("10."):
                doi = identifiers
            elif isinstance(identifiers, list):
                for ident in identifiers:
                    if isinstance(ident, str) and ident.startswith("10."):
                        doi = ident
                        break

            # URL
            url = item.get("@id")
            if url and not url.startswith("http"):
                url = f"https://cir.nii.ac.jp/crid/{paper_id}"

            return Paper(
                id=paper_id,
                source=self.name,
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                doi=doi,
                url=url,
            )

        except Exception as e:
            print(f"[CiNii] Item parse error: {e}")
            return None

    def _parse_detail_response(self, text: str, paper_id: str) -> PaperDetail | None:
        """상세 정보 JSON 파싱"""
        try:
            data = json.loads(text)

            # 기본 Paper 정보 파싱
            paper = self._parse_item(data)
            if not paper:
                return None

            # 초록
            abstract = self._get_text(data.get("dc:description"))
            if not abstract:
                abstract = self._get_text(data.get("description"))

            # 키워드
            keywords = []
            subjects = data.get("dc:subject", [])
            if not isinstance(subjects, list):
                subjects = [subjects]
            for subj in subjects:
                kw = self._get_text(subj)
                if kw:
                    keywords.append(kw)

            # 볼륨/이슈/페이지
            volume = self._get_text(data.get("prism:volume"))
            issue = self._get_text(data.get("prism:number"))
            pages = None
            start_page = self._get_text(data.get("prism:startingPage"))
            end_page = self._get_text(data.get("prism:endingPage"))
            if start_page:
                pages = f"{start_page}-{end_page}" if end_page else start_page

            return PaperDetail(
                id=paper.id,
                source=self.name,
                title=paper.title,
                authors=paper.authors,
                journal=paper.journal,
                year=paper.year,
                doi=paper.doi,
                url=paper.url,
                abstract=abstract,
                keywords=keywords,
                volume=volume,
                issue=issue,
                pages=pages,
            )

        except Exception as e:
            print(f"[CiNii] Detail parse error: {e}")
            return None

    def _get_text(self, value) -> str | None:
        """다양한 형식의 값에서 텍스트 추출"""
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() if value.strip() else None
        if isinstance(value, list):
            # 첫 번째 값 사용
            return self._get_text(value[0]) if value else None
        if isinstance(value, dict):
            # @value 또는 value 키 확인
            return self._get_text(value.get("@value") or value.get("value"))
        return str(value).strip() if value else None
