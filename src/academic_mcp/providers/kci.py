"""KCI (한국학술지인용색인) Provider - 이중 모드 지원

1차: KCI Open API (키워드 검색 지원, API 키 필요)
   - Endpoint: https://open.kci.go.kr/po/openapi/openApiSearch.kci
   - apiCode=articleSearch로 제목/키워드/저자 검색
   - API 키 발급: https://www.kci.go.kr → Open API → 키 발급 신청

2차 (폴백): OAI-PMH (키 불필요, 키워드 검색 제한적)
   - Base URL: https://open.kci.go.kr/oai/request
   - 날짜 범위 기반 목록 조회 후 클라이언트 측 필터링
"""

import xml.etree.ElementTree as ET
from typing import ClassVar
from datetime import datetime
from urllib.parse import quote

from academic_mcp.models import Paper, PaperDetail, SearchQuery, Author, ProviderCategory
from academic_mcp.providers.base import BaseProvider


# OAI-PMH XML 네임스페이스
NAMESPACES = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}


class KCIProvider(BaseProvider):
    """KCI 프로바이더 - Open API + OAI-PMH 이중 모드

    - KCI API 키가 있으면: Open API articleSearch (키워드 검색 가능)
    - KCI API 키가 없으면: OAI-PMH (날짜 범위 조회 + 클라이언트 필터링)
    """

    name: ClassVar[str] = "kci"
    display_name: ClassVar[str] = "한국학술지인용색인(KCI)"
    category: ClassVar[ProviderCategory] = ProviderCategory.PAPERS

    # KCI Open API 엔드포인트 (키워드 검색용)
    SEARCH_API_URL = "https://open.kci.go.kr/po/openapi/openApiSearch.kci"
    # OAI-PMH 엔드포인트 (폴백)
    OAI_PMH_URL = "https://open.kci.go.kr/oai/request"
    # data.go.kr 경유 엔드포인트
    DATA_GO_KR_URL = "http://apis.data.go.kr/B552540/KCIOpenApi/artiInfo/openApiD217List"

    def __init__(self, api_key: str | None = None, data_go_kr_key: str | None = None):
        super().__init__(api_key=api_key)
        self.data_go_kr_key = data_go_kr_key

    def is_available(self) -> bool:
        """KCI API 키, data.go.kr 키, 또는 OAI-PMH (키 불필요) 중 하나라도 사용 가능"""
        return True

    async def search(self, query: SearchQuery) -> list[Paper]:
        """KCI 논문 검색 - 3단계 폴백

        1차: KCI Open API (API 키 필요)
        2차: data.go.kr 경유 (data.go.kr 키 필요)
        3차: OAI-PMH (키 불필요, 키워드 검색 제한적)
        """
        # 1차: KCI Open API
        if self.api_key:
            papers = await self._search_via_open_api(query)
            if papers is not None:
                return papers

        # 2차: data.go.kr 경유
        if self.data_go_kr_key:
            papers = await self._search_via_data_go_kr(query)
            if papers is not None:
                return papers

        # 3차: OAI-PMH 폴백
        return await self._search_via_oai_pmh(query)

    async def _search_via_open_api(self, query: SearchQuery) -> list[Paper] | None:
        """KCI Open API로 검색"""
        params = {
            "apiCode": "articleSearch",
            "key": self.api_key,
            "title": query.keyword,
            "displayCount": str(query.max_results),
        }

        if query.author:
            params["author"] = query.author

        try:
            response = await self.client.get(
                self.SEARCH_API_URL, params=params, timeout=30.0
            )
            response.raise_for_status()
            return self._parse_open_api_response(response.text)
        except Exception as e:
            print(f"[KCI] Open API search error: {e}")
            return None

    async def _search_via_data_go_kr(self, query: SearchQuery) -> list[Paper] | None:
        """data.go.kr 경유로 KCI 검색"""
        params = {
            "serviceKey": self.data_go_kr_key,
            "title": query.keyword,
            "numOfRows": str(query.max_results),
            "pageNo": "1",
        }

        if query.author:
            params["author"] = query.author

        try:
            response = await self.client.get(
                self.DATA_GO_KR_URL, params=params, timeout=30.0
            )
            response.raise_for_status()
            return self._parse_data_go_kr_response(response.text)
        except Exception as e:
            print(f"[KCI] data.go.kr search error: {e}")
            return None

    async def _search_via_oai_pmh(self, query: SearchQuery) -> list[Paper]:
        """OAI-PMH로 검색 (폴백)"""
        params = {
            "verb": "ListRecords",
            "set": "ARTI",
            "metadataPrefix": "oai_dc",
        }

        if query.year_from:
            params["from"] = f"{query.year_from}-01-01"
        if query.year_to:
            params["until"] = f"{query.year_to}-12-31"

        # 기본값: 최근 6개월
        if "from" not in params and "until" not in params:
            now = datetime.now()
            year = now.year
            month = now.month - 6
            if month < 1:
                month += 12
                year -= 1
            params["from"] = f"{year}-{month:02d}-01"

        try:
            response = await self.client.get(
                self.OAI_PMH_URL, params=params, timeout=60.0
            )
            response.raise_for_status()

            papers = self._parse_oai_list_records(response.text)

            # 클라이언트 측 키워드 필터링
            if query.keyword:
                keyword_lower = query.keyword.lower()
                papers = [
                    p for p in papers
                    if keyword_lower in p.title.lower()
                    or any(keyword_lower in a.name.lower() for a in p.authors)
                ]

            # 저자 필터링
            if query.author:
                author_lower = query.author.lower()
                papers = [
                    p for p in papers
                    if any(author_lower in a.name.lower() for a in p.authors)
                ]

            return papers[:query.max_results]

        except Exception as e:
            print(f"[KCI] OAI-PMH search error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """개별 논문 상세 조회

        1차: KCI Open API (API 키 있을 때)
        2차: OAI-PMH GetRecord
        """
        # KCI Open API로 상세 조회 시도
        if self.api_key:
            detail = await self._get_detail_via_open_api(paper_id)
            if detail:
                return detail

        # OAI-PMH 폴백
        return await self._get_detail_via_oai_pmh(paper_id)

    async def _get_detail_via_open_api(self, paper_id: str) -> PaperDetail | None:
        """KCI Open API로 논문 상세 조회"""
        # paper_id에서 ART 번호 추출
        arti_id = paper_id
        if paper_id.startswith("ARTI/"):
            arti_id = paper_id.replace("ARTI/", "ART")
        elif not paper_id.startswith("ART"):
            arti_id = f"ART{paper_id}"

        params = {
            "apiCode": "articleDetail",
            "key": self.api_key,
            "artiId": arti_id,
        }

        try:
            response = await self.client.get(
                self.SEARCH_API_URL, params=params, timeout=30.0
            )
            response.raise_for_status()
            return self._parse_open_api_detail(response.text)
        except Exception as e:
            print(f"[KCI] Open API detail error: {e}")
            return None

    async def _get_detail_via_oai_pmh(self, paper_id: str) -> PaperDetail | None:
        """OAI-PMH GetRecord로 논문 상세 조회"""
        if not paper_id.startswith("oai:"):
            paper_id = f"oai:kci.go.kr:{paper_id}"

        params = {
            "verb": "GetRecord",
            "identifier": paper_id,
            "metadataPrefix": "oai_dc",
        }

        try:
            response = await self.client.get(
                self.OAI_PMH_URL, params=params, timeout=30.0
            )
            response.raise_for_status()
            return self._parse_oai_get_record(response.text)
        except Exception as e:
            print(f"[KCI] OAI-PMH GetRecord error: {e}")
            return None

    # ── KCI Open API 응답 파싱 ──

    def _parse_open_api_response(self, xml_text: str) -> list[Paper] | None:
        """KCI Open API articleSearch 응답 파싱"""
        papers = []
        try:
            root = ET.fromstring(xml_text)

            # 에러 확인
            result = root.find(".//result")
            if result is not None:
                result_msg = result.findtext("resultMsg", "")
                if "등록되지 않은 key" in result_msg or "error" in result_msg.lower():
                    print(f"[KCI] Open API Error: {result_msg}")
                    return None

            # 논문 레코드 파싱
            for record in root.findall(".//record"):
                paper = self._parse_open_api_record(record)
                if paper:
                    papers.append(paper)

            # 대체 구조: <article> 또는 <item> 태그
            if not papers:
                for record in root.findall(".//article"):
                    paper = self._parse_open_api_record(record)
                    if paper:
                        papers.append(paper)

            if not papers:
                for record in root.findall(".//item"):
                    paper = self._parse_open_api_record(record)
                    if paper:
                        papers.append(paper)

            return papers

        except ET.ParseError as e:
            print(f"[KCI] Open API XML parse error: {e}")
            return None

    def _parse_open_api_record(self, record: ET.Element) -> Paper | None:
        """KCI Open API 개별 레코드 파싱"""
        try:
            # 제목 (여러 가능한 태그명)
            title = (
                record.findtext("articleTitle", "").strip()
                or record.findtext("title", "").strip()
                or record.findtext("TITLE", "").strip()
                or record.findtext("artiTitle", "").strip()
            )
            if not title:
                return None

            # 저자
            authors = []
            author_text = (
                record.findtext("authorName", "").strip()
                or record.findtext("author", "").strip()
                or record.findtext("AUTHORS", "").strip()
            )
            if author_text:
                for name in author_text.split(";"):
                    name = name.strip()
                    if name:
                        authors.append(Author(name=name))

            # 학술지
            journal = (
                record.findtext("journalTitle", "").strip()
                or record.findtext("journal", "").strip()
                or record.findtext("JOURNAL", "").strip()
            )

            # 연도
            year = None
            year_text = (
                record.findtext("pubYear", "").strip()
                or record.findtext("pubiYear", "").strip()
                or record.findtext("YEAR", "").strip()
            )
            if year_text and year_text[:4].isdigit():
                year = int(year_text[:4])

            # DOI
            doi = record.findtext("doi", "").strip() or None

            # 논문 ID
            paper_id = (
                record.findtext("articleId", "").strip()
                or record.findtext("artiId", "").strip()
                or record.findtext("ARTI_ID", "").strip()
                or ""
            )

            # URL 생성
            url = None
            if paper_id:
                url = f"https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId={paper_id}"

            return Paper(
                id=paper_id or title[:50],
                source=self.name,
                title=title,
                authors=authors,
                journal=journal or None,
                year=year,
                doi=doi,
                url=url,
            )

        except Exception as e:
            print(f"[KCI] Open API record parse error: {e}")
            return None

    def _parse_open_api_detail(self, xml_text: str) -> PaperDetail | None:
        """KCI Open API 논문 상세 응답 파싱"""
        try:
            root = ET.fromstring(xml_text)
            record = root.find(".//record") or root.find(".//article") or root.find(".//item")
            if record is None:
                return None

            paper = self._parse_open_api_record(record)
            if not paper:
                return None

            # 초록
            abstract = (
                record.findtext("abstract", "").strip()
                or record.findtext("abstractKor", "").strip()
                or record.findtext("ABSTRACT", "").strip()
                or None
            )

            # 키워드
            keywords = []
            kw_text = (
                record.findtext("keyword", "").strip()
                or record.findtext("keywords", "").strip()
            )
            if kw_text:
                keywords = [k.strip() for k in kw_text.split(";") if k.strip()]

            # 권/호/페이지
            volume = record.findtext("volume", "").strip() or None
            issue = record.findtext("issue", "").strip() or None
            pages = record.findtext("pages", "").strip() or None

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
            print(f"[KCI] Open API detail parse error: {e}")
            return None

    # ── data.go.kr API 응답 파싱 ──

    def _parse_data_go_kr_response(self, xml_text: str) -> list[Paper] | None:
        """data.go.kr KCI 논문정보서비스 응답 파싱"""
        papers = []
        try:
            root = ET.fromstring(xml_text)

            # 에러 확인
            result_code = root.findtext(".//resultCode", "")
            if result_code and result_code != "00":
                result_msg = root.findtext(".//resultMsg", "Unknown error")
                print(f"[KCI] data.go.kr Error [{result_code}]: {result_msg}")
                return None

            # 레코드 파싱 (data.go.kr 구조)
            for item in root.findall(".//item"):
                paper = self._parse_open_api_record(item)
                if paper:
                    papers.append(paper)

            return papers

        except ET.ParseError as e:
            print(f"[KCI] data.go.kr XML parse error: {e}")
            return None

    # ── OAI-PMH 응답 파싱 (기존 코드 유지) ──

    def _parse_oai_list_records(self, xml_text: str) -> list[Paper]:
        """OAI-PMH ListRecords 응답 파싱"""
        papers = []
        try:
            root = ET.fromstring(xml_text)

            error = root.find(".//oai:error", NAMESPACES)
            if error is not None:
                error_code = error.get("code", "unknown")
                error_msg = error.text or "Unknown error"
                print(f"[KCI] OAI-PMH Error [{error_code}]: {error_msg}")
                return []

            for record in root.findall(".//oai:record", NAMESPACES):
                paper = self._parse_oai_record(record)
                if paper:
                    papers.append(paper)

            token_elem = root.find(".//oai:resumptionToken", NAMESPACES)
            if token_elem is not None and token_elem.text:
                complete_size = token_elem.get("completeListSize")
                if complete_size:
                    print(f"[KCI] Total records available: {complete_size}")

        except ET.ParseError as e:
            print(f"[KCI] OAI XML parse error: {e}")
        except Exception as e:
            print(f"[KCI] OAI parse error: {e}")

        return papers

    def _parse_oai_get_record(self, xml_text: str) -> PaperDetail | None:
        """OAI-PMH GetRecord 응답 파싱"""
        try:
            root = ET.fromstring(xml_text)

            error = root.find(".//oai:error", NAMESPACES)
            if error is not None:
                print(f"[KCI] OAI-PMH Error: {error.text}")
                return None

            record = root.find(".//oai:record", NAMESPACES)
            if record is None:
                return None

            paper = self._parse_oai_record(record, include_detail=True)
            if paper and isinstance(paper, PaperDetail):
                return paper
            return None

        except Exception as e:
            print(f"[KCI] OAI GetRecord parse error: {e}")
            return None

    def _parse_oai_record(
        self, record: ET.Element, include_detail: bool = False
    ) -> Paper | PaperDetail | None:
        """OAI-PMH 개별 레코드 파싱 (Dublin Core 형식)"""
        try:
            header = record.find("oai:header", NAMESPACES)
            if header is None:
                return None

            if header.get("status") == "deleted":
                return None

            identifier = header.findtext("oai:identifier", "", NAMESPACES)
            datestamp = header.findtext("oai:datestamp", "", NAMESPACES)

            metadata = record.find("oai:metadata", NAMESPACES)
            if metadata is None:
                return None

            dc = metadata.find("oai_dc:dc", NAMESPACES)
            if dc is None:
                return None

            title = dc.findtext("dc:title", "", NAMESPACES).strip()
            if not title:
                return None

            authors = []
            for creator in dc.findall("dc:creator", NAMESPACES):
                name = (creator.text or "").strip()
                if name:
                    authors.append(Author(name=name))

            year = None
            date_text = dc.findtext("dc:date", "", NAMESPACES)
            if date_text and len(date_text) >= 4:
                year_str = date_text[:4]
                if year_str.isdigit():
                    year = int(year_str)

            if not year and datestamp and len(datestamp) >= 4:
                year_str = datestamp[:4]
                if year_str.isdigit():
                    year = int(year_str)

            journal = (
                dc.findtext("dc:source", "", NAMESPACES).strip()
                or dc.findtext("dc:publisher", "", NAMESPACES).strip()
                or None
            )

            doi = None
            url = None
            for id_elem in dc.findall("dc:identifier", NAMESPACES):
                id_text = (id_elem.text or "").strip()
                if id_text.startswith("10.") or "doi.org" in id_text:
                    doi = id_text.replace("https://doi.org/", "").replace("http://doi.org/", "")
                elif id_text.startswith("http"):
                    url = id_text

            if not url and identifier:
                parts = identifier.split(":")
                if len(parts) >= 3:
                    arti_id = parts[-1].replace("/", "")
                    url = f"https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId={arti_id}"

            paper_id = identifier
            if identifier.startswith("oai:kci.go.kr:"):
                paper_id = identifier.replace("oai:kci.go.kr:", "")

            if include_detail:
                abstract = dc.findtext("dc:description", "", NAMESPACES).strip() or None
                keywords = []
                for subject in dc.findall("dc:subject", NAMESPACES):
                    kw = (subject.text or "").strip()
                    if kw:
                        keywords.append(kw)

                return PaperDetail(
                    id=paper_id,
                    source=self.name,
                    title=title,
                    authors=authors,
                    journal=journal,
                    year=year,
                    doi=doi,
                    url=url,
                    abstract=abstract,
                    keywords=keywords,
                )

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
            print(f"[KCI] OAI record parse error: {e}")
            return None
