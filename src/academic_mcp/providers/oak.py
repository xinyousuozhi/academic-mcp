"""OAK (오픈액세스코리아) OAI-PMH Provider

OAI-PMH 프로토콜 사용 (API 키 불필요):
- Base URL: https://oak.go.kr/OAIHandler
- 논문 목록 조회: ListRecords, ListIdentifiers
- 개별 논문 조회: GetRecord
- 메타데이터 형식: oai_dc (Dublin Core)

OAK는 국가 오픈액세스 플랫폼으로 기관 리포지토리, OA 논문, 학위논문 등을 제공.
"""

import xml.etree.ElementTree as ET
from typing import ClassVar
from datetime import datetime

from academic_mcp.models import Paper, PaperDetail, SearchQuery, Author
from academic_mcp.providers.base import BaseProvider


# OAI-PMH XML 네임스페이스
NAMESPACES = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}


class OAKProvider(BaseProvider):
    """OAK (오픈액세스코리아) OAI-PMH 클라이언트

    OAI-PMH는 키워드 검색이 아닌 목록 수확(harvesting) 프로토콜입니다.
    - 최근 논문 목록 조회 (날짜 범위 지정 가능)
    - 특정 논문 ID로 상세 조회
    """

    name: ClassVar[str] = "oak"
    display_name: ClassVar[str] = "오픈액세스코리아(OAK)"

    BASE_URL = "https://oak.go.kr/OAIHandler"

    def is_available(self) -> bool:
        """OAI-PMH는 API 키 불필요"""
        return True

    async def search(self, query: SearchQuery) -> list[Paper]:
        """OAK 논문 목록 조회

        OAI-PMH의 ListRecords를 사용하여 논문 목록 조회.
        키워드 검색은 지원하지 않으며, 날짜 범위로 필터링 가능.

        Note: 클라이언트 측에서 keyword 필터링 수행
        """
        params = {
            "verb": "ListRecords",
            "metadataPrefix": "oai_dc",
        }

        # 날짜 범위 설정
        if query.year_from:
            params["from"] = f"{query.year_from}-01-01"
        if query.year_to:
            params["until"] = f"{query.year_to}-12-31"

        # 기본값: 최근 6개월 데이터
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
                self.BASE_URL, params=params, timeout=60.0, follow_redirects=True
            )
            response.raise_for_status()

            papers = self._parse_list_records(response.text)

            # 키워드 필터링 (클라이언트 측)
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
            print(f"[OAK] OAI-PMH ListRecords error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """개별 논문 상세 조회

        Args:
            paper_id: OAK 논문 ID (예: "oai:oak.go.kr:6067" 또는 "6067")
        """
        # ID 형식 정규화
        if not paper_id.startswith("oai:"):
            paper_id = f"oai:oak.go.kr:{paper_id}"

        params = {
            "verb": "GetRecord",
            "identifier": paper_id,
            "metadataPrefix": "oai_dc",
        }

        try:
            response = await self.client.get(
                self.BASE_URL, params=params, timeout=30.0, follow_redirects=True
            )
            response.raise_for_status()

            return self._parse_get_record(response.text)

        except Exception as e:
            print(f"[OAK] OAI-PMH GetRecord error: {e}")
            return None

    async def identify(self) -> dict | None:
        """저장소 정보 조회"""
        params = {"verb": "Identify"}

        try:
            response = await self.client.get(
                self.BASE_URL, params=params, timeout=30.0, follow_redirects=True
            )
            response.raise_for_status()

            root = ET.fromstring(response.text)
            identify = root.find(".//oai:Identify", NAMESPACES)

            if identify is None:
                return None

            return {
                "repositoryName": identify.findtext("oai:repositoryName", "", NAMESPACES),
                "baseURL": identify.findtext("oai:baseURL", "", NAMESPACES),
                "protocolVersion": identify.findtext("oai:protocolVersion", "", NAMESPACES),
                "adminEmail": identify.findtext("oai:adminEmail", "", NAMESPACES),
                "earliestDatestamp": identify.findtext("oai:earliestDatestamp", "", NAMESPACES),
            }

        except Exception as e:
            print(f"[OAK] OAI-PMH Identify error: {e}")
            return None

    def _parse_list_records(self, xml_text: str) -> list[Paper]:
        """ListRecords 응답 파싱"""
        papers = []

        try:
            root = ET.fromstring(xml_text)

            # OAI-PMH 에러 체크
            error = root.find(".//oai:error", NAMESPACES)
            if error is not None:
                error_code = error.get("code", "unknown")
                error_msg = error.text or "Unknown error"
                print(f"[OAK] OAI-PMH Error [{error_code}]: {error_msg}")
                return []

            # 레코드 파싱
            for record in root.findall(".//oai:record", NAMESPACES):
                paper = self._parse_record(record)
                if paper:
                    papers.append(paper)

            # resumptionToken 확인 (페이지네이션용)
            token_elem = root.find(".//oai:resumptionToken", NAMESPACES)
            if token_elem is not None and token_elem.text:
                complete_size = token_elem.get("completeListSize")
                if complete_size:
                    print(f"[OAK] Total records available: {complete_size}")

        except ET.ParseError as e:
            print(f"[OAK] XML parse error: {e}")
        except Exception as e:
            print(f"[OAK] Parse error: {e}")

        return papers

    def _parse_get_record(self, xml_text: str) -> PaperDetail | None:
        """GetRecord 응답 파싱"""
        try:
            root = ET.fromstring(xml_text)

            # 에러 체크
            error = root.find(".//oai:error", NAMESPACES)
            if error is not None:
                print(f"[OAK] OAI-PMH Error: {error.text}")
                return None

            record = root.find(".//oai:record", NAMESPACES)
            if record is None:
                return None

            paper = self._parse_record(record, include_detail=True)
            if paper and isinstance(paper, PaperDetail):
                return paper

            return None

        except Exception as e:
            print(f"[OAK] GetRecord parse error: {e}")
            return None

    def _parse_record(
        self, record: ET.Element, include_detail: bool = False
    ) -> Paper | PaperDetail | None:
        """개별 OAI 레코드 파싱 (OAK 커스텀 Dublin Core 형식)

        OAK는 표준 Dublin Core와 다른 필드명 사용:
        - dc:title_h (제목)
        - dc:author (저자)
        - dc:abstract_e (초록)
        - dc:deep_link (URL)
        - dc:keyword (키워드)
        """
        try:
            # Header에서 ID 추출
            header = record.find("oai:header", NAMESPACES)
            if header is None:
                return None

            # 삭제된 레코드 스킵
            if header.get("status") == "deleted":
                return None

            identifier = header.findtext("oai:identifier", "", NAMESPACES)
            datestamp = header.findtext("oai:datestamp", "", NAMESPACES)

            # 메타데이터에서 Dublin Core 추출
            metadata = record.find("oai:metadata", NAMESPACES)
            if metadata is None:
                return None

            dc = metadata.find("oai_dc:dc", NAMESPACES)
            if dc is None:
                return None

            # 제목 (OAK: dc:title_h 또는 dc:title)
            title = self._get_dc_text(dc, ["title_h", "title"])
            if not title:
                return None

            # 저자 (OAK: dc:author, 표준: dc:creator)
            authors = []
            # OAK 형식: dc:author (|로 구분된 다중 저자)
            author_text = self._get_dc_text(dc, ["author"])
            if author_text:
                for name in author_text.split("|"):
                    name = name.strip()
                    if name:
                        authors.append(Author(name=name))
            # 표준 형식: dc:creator
            if not authors:
                for creator in dc.findall("dc:creator", NAMESPACES):
                    name = (creator.text or "").strip()
                    if name:
                        authors.append(Author(name=name))

            # 연도 (publisher 필드에서 추출 시도)
            year = None
            # dc:date에서 추출
            date_text = self._get_dc_text(dc, ["date"])
            if date_text:
                year = self._extract_year(date_text)
            # publisher에서 연도 추출 (예: "[1991] [刊寫地未詳]")
            if not year:
                pub_text = self._get_dc_text(dc, ["publisher"])
                if pub_text:
                    year = self._extract_year(pub_text)
            # datestamp에서 추출
            if not year and datestamp:
                year = self._extract_year(datestamp)

            # 출판사/소장처 (OAK: dc:location_org, dc:publisher)
            journal = self._get_dc_text(dc, ["location_org", "source", "publisher"])

            # URL (OAK: dc:deep_link, dc:contents_url)
            url = self._get_dc_text(dc, ["deep_link", "contents_url"])

            # DOI
            doi = None
            for id_elem in dc.findall("dc:identifier", NAMESPACES):
                id_text = (id_elem.text or "").strip()
                if id_text.startswith("10.") or "doi.org" in id_text:
                    doi = id_text.replace("https://doi.org/", "").replace("http://doi.org/", "")
                    break

            # URL이 없으면 OAK 기본 URL 생성
            if not url and identifier:
                parts = identifier.split(":")
                if len(parts) >= 3:
                    oak_id = parts[-1]
                    url = f"https://oak.go.kr/detail/detail.do?metadataSeq={oak_id}"

            # Paper ID
            paper_id = identifier
            if identifier.startswith("oai:oak.go.kr:"):
                paper_id = identifier.replace("oai:oak.go.kr:", "")

            if include_detail:
                # 초록 (OAK: dc:abstract_e, dc:abstract_k)
                abstract = self._get_dc_text(dc, ["abstract_e", "abstract_k", "description"])

                # 키워드 (OAK: dc:keyword, 표준: dc:subject)
                keywords = []
                kw_text = self._get_dc_text(dc, ["keyword"])
                if kw_text:
                    keywords.append(kw_text)
                for subject in dc.findall("dc:subject", NAMESPACES):
                    kw = (subject.text or "").strip()
                    if kw and kw not in keywords:
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
            print(f"[OAK] Record parse error: {e}")
            return None

    def _get_dc_text(self, dc: ET.Element, field_names: list[str]) -> str | None:
        """Dublin Core 필드에서 텍스트 추출 (여러 필드명 시도)"""
        for field in field_names:
            # 네임스페이스 있는 경우
            elem = dc.find(f"dc:{field}", NAMESPACES)
            if elem is not None and elem.text:
                return elem.text.strip()
            # 네임스페이스 없는 경우 (OAK 커스텀 필드)
            for child in dc:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == field and child.text:
                    return child.text.strip()
        return None

    def _extract_year(self, text: str) -> int | None:
        """텍스트에서 4자리 연도 추출"""
        import re
        # 4자리 숫자 찾기 (1900-2099)
        match = re.search(r'(19|20)\d{2}', text)
        if match:
            return int(match.group())
        return None
