"""KCI (한국학술지인용색인) OAI-PMH Provider

OAI-PMH 프로토콜 사용 (API 키 불필요):
- Base URL: https://open.kci.go.kr/oai/request
- 논문 목록 조회: ListRecords, ListIdentifiers
- 개별 논문 조회: GetRecord
- 메타데이터 형식: oai_dc (Dublin Core)

OAI-PMH는 표준 수확 프로토콜로, 키워드 검색 대신 날짜 범위 기반 목록 조회 제공.
"""

import xml.etree.ElementTree as ET
from typing import ClassVar
from datetime import datetime

from academic_mcp.models import Paper, PaperDetail, SearchQuery, Author, ProviderCategory
from academic_mcp.providers.base import BaseProvider


# OAI-PMH XML 네임스페이스
NAMESPACES = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}


class KCIProvider(BaseProvider):
    """KCI OAI-PMH 클라이언트

    OAI-PMH는 키워드 검색이 아닌 목록 수확(harvesting) 프로토콜입니다.
    - 최근 논문 목록 조회 (날짜 범위 지정 가능)
    - 특정 논문 ID로 상세 조회
    """

    name: ClassVar[str] = "kci"
    display_name: ClassVar[str] = "한국학술지인용색인(KCI)"
    category: ClassVar[ProviderCategory] = ProviderCategory.PAPERS

    BASE_URL = "https://open.kci.go.kr/oai/request"

    def is_available(self) -> bool:
        """OAI-PMH는 API 키 불필요"""
        return True

    async def search(self, query: SearchQuery) -> list[Paper]:
        """KCI 논문 목록 조회

        OAI-PMH의 ListRecords를 사용하여 논문 목록 조회.
        키워드 검색은 지원하지 않으며, 날짜 범위로 필터링 가능.

        Note: 클라이언트 측에서 keyword 필터링 수행
        """
        params = {
            "verb": "ListRecords",
            "set": "ARTI",  # 논문 세트
            "metadataPrefix": "oai_dc",
        }

        # 날짜 범위 설정 (기본: 최근 1년)
        if query.year_from:
            params["from"] = f"{query.year_from}-01-01"
        if query.year_to:
            params["until"] = f"{query.year_to}-12-31"

        # 기본값: 최근 논문
        if "from" not in params and "until" not in params:
            # 최근 6개월 데이터
            now = datetime.now()
            year = now.year
            month = now.month - 6
            if month < 1:
                month += 12
                year -= 1
            params["from"] = f"{year}-{month:02d}-01"

        try:
            response = await self.client.get(
                self.BASE_URL, params=params, timeout=60.0
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
            print(f"[KCI] OAI-PMH ListRecords error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """개별 논문 상세 조회

        Args:
            paper_id: KCI 논문 ID (예: "oai:kci.go.kr:ARTI/10000" 또는 "ARTI/10000")
        """
        # ID 형식 정규화
        if not paper_id.startswith("oai:"):
            paper_id = f"oai:kci.go.kr:{paper_id}"

        params = {
            "verb": "GetRecord",
            "identifier": paper_id,
            "metadataPrefix": "oai_dc",
        }

        try:
            response = await self.client.get(
                self.BASE_URL, params=params, timeout=30.0
            )
            response.raise_for_status()

            return self._parse_get_record(response.text)

        except Exception as e:
            print(f"[KCI] OAI-PMH GetRecord error: {e}")
            return None

    async def list_sets(self) -> list[dict]:
        """저장소 세트 목록 조회"""
        params = {"verb": "ListSets"}

        try:
            response = await self.client.get(
                self.BASE_URL, params=params, timeout=30.0
            )
            response.raise_for_status()

            root = ET.fromstring(response.text)
            sets = []

            for set_elem in root.findall(".//oai:set", NAMESPACES):
                set_spec = set_elem.findtext("oai:setSpec", "", NAMESPACES)
                set_name = set_elem.findtext("oai:setName", "", NAMESPACES)
                if set_spec:
                    sets.append({"spec": set_spec, "name": set_name})

            return sets

        except Exception as e:
            print(f"[KCI] OAI-PMH ListSets error: {e}")
            return []

    async def identify(self) -> dict | None:
        """저장소 정보 조회"""
        params = {"verb": "Identify"}

        try:
            response = await self.client.get(
                self.BASE_URL, params=params, timeout=30.0
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
            print(f"[KCI] OAI-PMH Identify error: {e}")
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
                print(f"[KCI] OAI-PMH Error [{error_code}]: {error_msg}")
                return []

            # 레코드 파싱
            for record in root.findall(".//oai:record", NAMESPACES):
                paper = self._parse_record(record)
                if paper:
                    papers.append(paper)

            # resumptionToken 확인 (페이지네이션용)
            token_elem = root.find(".//oai:resumptionToken", NAMESPACES)
            if token_elem is not None and token_elem.text:
                # 토큰 정보 로깅 (추후 페이지네이션 구현 시 사용)
                complete_size = token_elem.get("completeListSize")
                if complete_size:
                    print(f"[KCI] Total records available: {complete_size}")

        except ET.ParseError as e:
            print(f"[KCI] XML parse error: {e}")
        except Exception as e:
            print(f"[KCI] Parse error: {e}")

        return papers

    def _parse_get_record(self, xml_text: str) -> PaperDetail | None:
        """GetRecord 응답 파싱"""
        try:
            root = ET.fromstring(xml_text)

            # 에러 체크
            error = root.find(".//oai:error", NAMESPACES)
            if error is not None:
                print(f"[KCI] OAI-PMH Error: {error.text}")
                return None

            record = root.find(".//oai:record", NAMESPACES)
            if record is None:
                return None

            paper = self._parse_record(record, include_detail=True)
            if paper and isinstance(paper, PaperDetail):
                return paper

            return None

        except Exception as e:
            print(f"[KCI] GetRecord parse error: {e}")
            return None

    def _parse_record(
        self, record: ET.Element, include_detail: bool = False
    ) -> Paper | PaperDetail | None:
        """개별 OAI 레코드 파싱 (Dublin Core 형식)"""
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

            # 제목
            title = dc.findtext("dc:title", "", NAMESPACES).strip()
            if not title:
                return None

            # 저자 (다중)
            authors = []
            for creator in dc.findall("dc:creator", NAMESPACES):
                name = (creator.text or "").strip()
                if name:
                    authors.append(Author(name=name))

            # 연도 (date 필드에서 추출)
            year = None
            date_text = dc.findtext("dc:date", "", NAMESPACES)
            if date_text and len(date_text) >= 4:
                year_str = date_text[:4]
                if year_str.isdigit():
                    year = int(year_str)

            # datestamp에서 연도 추출 (date가 없는 경우)
            if not year and datestamp and len(datestamp) >= 4:
                year_str = datestamp[:4]
                if year_str.isdigit():
                    year = int(year_str)

            # 출처/저널 (source 또는 publisher)
            journal = (
                dc.findtext("dc:source", "", NAMESPACES).strip() or
                dc.findtext("dc:publisher", "", NAMESPACES).strip() or
                None
            )

            # DOI/URL (identifier 필드들)
            doi = None
            url = None
            for id_elem in dc.findall("dc:identifier", NAMESPACES):
                id_text = (id_elem.text or "").strip()
                if id_text.startswith("10.") or "doi.org" in id_text:
                    doi = id_text.replace("https://doi.org/", "").replace("http://doi.org/", "")
                elif id_text.startswith("http"):
                    url = id_text

            # KCI URL 생성 (URL이 없는 경우)
            if not url and identifier:
                # identifier: "oai:kci.go.kr:ARTI/12345" -> ARTI12345
                parts = identifier.split(":")
                if len(parts) >= 3:
                    arti_id = parts[-1].replace("/", "")
                    url = f"https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId={arti_id}"

            # Paper ID (identifier에서 추출)
            paper_id = identifier
            if identifier.startswith("oai:kci.go.kr:"):
                paper_id = identifier.replace("oai:kci.go.kr:", "")

            if include_detail:
                # 초록 (description)
                abstract = dc.findtext("dc:description", "", NAMESPACES).strip() or None

                # 주제/키워드 (subject)
                keywords = []
                for subject in dc.findall("dc:subject", NAMESPACES):
                    kw = (subject.text or "").strip()
                    if kw:
                        keywords.append(kw)

                # 언어
                language = dc.findtext("dc:language", "", NAMESPACES).strip() or None

                # 유형
                doc_type = dc.findtext("dc:type", "", NAMESPACES).strip() or None

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
            print(f"[KCI] Record parse error: {e}")
            return None
