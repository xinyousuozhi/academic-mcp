"""KOSTMA (한국학자료센터) Provider

한국학중앙연구원 한국학자료센터 OpenAPI (kostma.aks.ac.kr)
- 문헌정보 검색: GET /OpenAPI/request.aspx
- 고지도 검색: GET /OpenAPI/oldmap.aspx
- 디렉토리 서비스: GET /api/API_insDirList.aspx

API 키 불필요 (공개 API)
"""

import ssl
import xml.etree.ElementTree as ET
from typing import ClassVar
from urllib.parse import quote

import httpx

from academic_mcp.models import Author, Paper, PaperDetail, SearchQuery
from academic_mcp.providers.base import BaseProvider


def _create_legacy_ssl_context() -> ssl.SSLContext:
    """KOSTMA 서버 호환용 레거시 SSL 컨텍스트 생성"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # 레거시 서버 호환성을 위한 설정
    ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    return ctx


class KOSTMAProvider(BaseProvider):
    """KOSTMA (한국학자료센터) API 클라이언트"""

    name: ClassVar[str] = "kostma"
    display_name: ClassVar[str] = "한국학자료센터(KOSTMA)"

    # API 엔드포인트
    BASE_URL = "http://kostma.aks.ac.kr"
    SEARCH_URL = f"{BASE_URL}/OpenAPI/request.aspx"
    OLDMAP_URL = f"{BASE_URL}/OpenAPI/oldmap.aspx"

    @property
    def client(self) -> httpx.AsyncClient:
        """KOSTMA는 HTTP→HTTPS 리다이렉트 필요, SSL 호환성 문제 있음"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                verify=_create_legacy_ssl_context(),
            )
        return self._client

    def is_available(self) -> bool:
        # KOSTMA는 API 키 불필요
        return True

    async def search(self, query: SearchQuery) -> list[Paper]:
        """KOSTMA 문헌정보 검색

        Parameters:
            query: 검색 쿼리 (keyword, author 등)

        Returns:
            검색된 고문헌 목록
        """
        params = {
            "query": query.keyword,
            "page": 1,
            "ipp": query.max_results,
            "detail": 1,  # 기본정보 포함
        }

        # 세부 검색 조건
        subquery_parts = []
        if query.author:
            subquery_parts.append(f"publisher={query.author}")

        if subquery_parts:
            # subquery 사용 시 query는 무시됨
            params["subquery"] = "&".join(subquery_parts)
            params["subquery"] += f"&title={query.keyword}"

        try:
            response = await self.client.get(
                self.SEARCH_URL,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return self._parse_search_response(response.text)
        except Exception as e:
            print(f"[KOSTMA] Search error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """KOSTMA 상세 정보 조회

        paper_id는 UCI 값 (예: "RIKS+CRMA+KSM-WZ.0000.0000-20090716.AS_SA_243")
        """
        params = {
            "subquery": f"uci={paper_id}",
            "detail": 2,  # 기본정보 + 안내정보
        }

        try:
            response = await self.client.get(
                self.SEARCH_URL,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            papers = self._parse_search_response(response.text, detail=True)
            if papers:
                paper = papers[0]
                return PaperDetail(
                    id=paper.id,
                    source=paper.source,
                    title=paper.title,
                    authors=paper.authors,
                    journal=paper.journal,
                    year=paper.year,
                    url=paper.url,
                    abstract=None,
                    keywords=[],
                )
            return None
        except Exception as e:
            print(f"[KOSTMA] Detail error: {e}")
            return None

    def _parse_search_response(self, xml_text: str, detail: bool = False) -> list[Paper]:
        """검색 결과 XML 파싱

        응답 구조:
        <ksm>
            <info>
                <request>검색어</request>
                <total>전체건수</total>
                <page>현재페이지</page>
                <ipp>페이지당건수</ipp>
            </info>
            <items>
                <item>
                    <uci>UCI값</uci>
                    <subject>분류</subject>
                    <title>자료명</title>
                    <url>서비스URL</url>
                </item>
                ...
            </items>
        </ksm>
        """
        papers = []

        try:
            root = ET.fromstring(xml_text)

            # 전체 건수 확인
            total = root.findtext(".//info/total", "0")
            if total == "0":
                return []

            # 항목 파싱
            for item in root.findall(".//items/item"):
                paper = self._parse_item(item)
                if paper:
                    papers.append(paper)

        except ET.ParseError as e:
            print(f"[KOSTMA] XML Parse error: {e}")
            print(f"[KOSTMA] Response: {xml_text[:500]}")

        return papers

    def _parse_item(self, item: ET.Element) -> Paper | None:
        """개별 XML 항목 파싱"""
        try:
            # UCI (고유 식별자)
            uci = (item.findtext("uci") or "").strip()
            if not uci:
                return None

            # 제목
            title = (item.findtext("title") or "").strip()
            if not title:
                return None

            # 분류 (subject)
            subject = (item.findtext("subject") or "").strip()

            # URL
            url = (item.findtext("url") or "").strip() or None

            # 관련인물 (publisher 필드가 실제로는 관련인물)
            authors = []
            publisher_text = (item.findtext("publisher") or "").strip()
            if publisher_text:
                # 쉼표나 세미콜론으로 구분된 인물명 파싱
                for name in publisher_text.replace(",", ";").split(";"):
                    name = name.strip()
                    if name:
                        authors.append(Author(name=name))

            # 작성시기 (date 필드)
            year = None
            date_text = (item.findtext("date") or "").strip()
            if date_text:
                # 연도만 추출 (예: "1800년대", "1856" 등)
                import re
                year_match = re.search(r"(\d{4})", date_text)
                if year_match:
                    year = int(year_match.group(1))

            return Paper(
                id=uci,
                source=self.name,
                title=title,
                authors=authors,
                journal=subject,  # 분류를 journal 필드에 매핑
                year=year,
                url=url,
            )

        except Exception as e:
            print(f"[KOSTMA] Item parse error: {e}")
            return None

    async def search_oldmap(self, place_name: str, page: int = 1, ipp: int = 10) -> list[dict]:
        """고지도 검색 (추가 기능)

        Parameters:
            place_name: 검색할 고지명
            page: 페이지 번호
            ipp: 페이지당 결과 수

        Returns:
            고지명 검색 결과 목록
        """
        params = {
            "sWord": place_name,
            "page": page,
            "ipp": ipp,
        }

        try:
            response = await self.client.get(
                self.OLDMAP_URL,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return self._parse_oldmap_response(response.text)
        except Exception as e:
            print(f"[KOSTMA] Oldmap search error: {e}")
            return []

    def _parse_oldmap_response(self, xml_text: str) -> list[dict]:
        """고지도 검색 결과 파싱"""
        results = []

        try:
            root = ET.fromstring(xml_text)

            for item in root.findall(".//items/item"):
                result = {
                    "gcode": item.findtext("gcode", "").strip(),
                    "kortitle": item.findtext("kortitle", "").strip(),
                    "title": item.findtext("title", "").strip(),
                    "kind": item.findtext("kind", "").strip(),
                    "current": item.findtext("current", "").strip(),
                    "linking": item.findtext("linking", "").strip(),
                }
                if result["gcode"]:
                    results.append(result)

        except ET.ParseError as e:
            print(f"[KOSTMA] Oldmap XML Parse error: {e}")

        return results
