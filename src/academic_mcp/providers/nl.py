"""한국고문헌종합목록 Provider

한국고문헌종합목록 OpenAPI (KORCIS):
- Endpoint: https://www.nl.go.kr/korcis/openapi/search.do
- 자료검색 / 상세보기 제공
- API 키 불필요 (가이드상)
"""

import xml.etree.ElementTree as ET
from typing import ClassVar

from academic_mcp.models import Paper, PaperDetail, SearchQuery, Author, ProviderCategory
from academic_mcp.providers.base import BaseProvider


def _get_text(element: ET.Element | None, tag: str) -> str:
    """XML 요소 텍스트 추출"""
    if element is None:
        return ""
    child = element.find(tag)
    if child is None or not child.text:
        return ""
    return child.text.strip()


class NLProvider(BaseProvider):
    """한국고문헌종합목록 (국립중앙도서관 운영)"""

    name: ClassVar[str] = "nl"
    display_name: ClassVar[str] = "한국고문헌종합목록"
    category: ClassVar[ProviderCategory] = ProviderCategory.ANCIENT

    SEARCH_URL = "https://www.nl.go.kr/korcis/openapi/search.do"
    DETAIL_URL = "https://www.nl.go.kr/korcis/openapi/detail.do"

    def is_available(self) -> bool:
        # 키 불필요
        return True

    async def search(self, query: SearchQuery) -> list[Paper]:
        """고문헌 검색"""
        params = {
            "search_field": "total", # 전체 검색
            "search_value": query.keyword,
            "page": "1",
            "display": str(query.max_results),
            # original_yn: "Y" # 원문 있는 것만? 선택하지 않음
        }

        try:
            response = await self.client.get(self.SEARCH_URL, params=params)
            response.raise_for_status()
            
            # API 응답 인코딩 확인 (가끔 EUC-KR일 수 있음)
            # content = response.content.decode("utf-8") # 보통 UTF-8
            
            return self._parse_search_response(response.content)

        except Exception as e:
            print(f"[NL] Search error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """상세 정보 조회"""
        params = {
            "rec_key": paper_id
        }

        try:
            response = await self.client.get(self.DETAIL_URL, params=params)
            response.raise_for_status()
            return self._parse_detail_response(response.content, paper_id)

        except Exception as e:
            print(f"[NL] Detail error: {e}")
            return None

    def _parse_search_response(self, xml_bytes: bytes) -> list[Paper]:
        """검색 결과 XML 파싱"""
        papers = []
        try:
            root = ET.fromstring(xml_bytes)
            
            # 레코드 반복
            for record in root.findall(".//RECORD"):
                paper = self._parse_record(record)
                if paper:
                    papers.append(paper)
                    
        except Exception as e:
            print(f"[NL] XML parse error: {e}")
            
        return papers

    def _parse_record(self, record: ET.Element) -> Paper | None:
        """개별 레코드 파싱"""
        try:
            rec_key = _get_text(record, "REC_KEY")
            title = _get_text(record, "TITLE")
            
            # 한글 제목 우선
            kor_title = _get_text(record, "KOR_TITLE")
            if kor_title:
                title = f"{kor_title} ({title})" if title else kor_title

            if not rec_key:
                return None
                
            # 저자
            author_str = _get_text(record, "AUTHOR")
            kor_author = _get_text(record, "KOR_AUTHOR")
            if kor_author:
                author_str = f"{kor_author} ({author_str})" if author_str else kor_author
            
            authors = [Author(name=author_str)] if author_str else []

            # 발행년도
            pub_year = _get_text(record, "PUBYEAR") or _get_text(record, "KOR_PUBYEAR")
            year = None
            if pub_year:
                # 숫자만 추출 (간단히 첫 4자리)
                import re
                match = re.search(r'\d{4}', pub_year)
                if match:
                    year = int(match.group())

            # 발행자/판종/소장기관
            publisher = _get_text(record, "PUBLISHER") or _get_text(record, "KOR_PUBLISHER")
            edit_name = _get_text(record, "EDIT_NAME")
            lib_name = _get_text(record, "LIB_NAME")
            
            journal_info = []
            if edit_name: journal_info.append(edit_name)
            if lib_name: journal_info.append(lib_name)
            if publisher: journal_info.append(publisher)
            
            journal = " | ".join(journal_info) if journal_info else None
            
            # URL 생성
            url = f"https://www.nl.go.kr/korcis/search/searchDetail.do?rec_key={rec_key}"

            return Paper(
                id=rec_key,
                source=self.name,
                title=title or "제목 없음",
                authors=authors,
                journal=journal,
                year=year,
                url=url
            )

        except Exception as e:
            print(f"[NL] Record parse error: {e}")
            return None

    def _parse_detail_response(self, xml_bytes: bytes, paper_id: str) -> PaperDetail | None:
        """상세 정보 XML 파싱"""
        try:
            root = ET.fromstring(xml_bytes)
            
            bib_info = root.find(".//BIBINFO")
            if bib_info is None:
                return None
                
            # 기본 정보 추출 (검색 결과와 유사하지만 상세 필드 사용)
            title = _get_text(bib_info, "TITLE_INFO")
            pub_info = _get_text(bib_info, "PUBLISH_INFO")
            
            # 저자는 TITLE_INFO 등에서 파싱하기 어려울 수 있으나 일단 검색 결과 로직 대신 
            # 상세 필드를 활용하는 것이 원칙. 
            # 하지만 상세 응답에는 명시적인 AUTHOR 태그가 없고 TITLE_INFO에 포함된 경우가 많음.
            # 예: "해동제국기 / 신숙주 저"
            
            authors = []
            if "/" in title:
                parts = title.split("/")
                title_real = parts[0].strip()
                author_part = parts[1].strip()
                # "신숙주 저" 등 제거
                author_part = author_part.replace("저", "").strip()
                if author_part:
                    authors.append(Author(name=author_part))
            else:
                title_real = title

            # 소장 정보 Loop
            hold_lib_names = []
            for hold in root.findall(".//HOLDINFO"):
                lib_name = _get_text(hold, "LIB_NAME")
                if lib_name and lib_name not in hold_lib_names:
                    hold_lib_names.append(lib_name)
            
            # 초록/내용
            abstract = ""
            note_info = _get_text(bib_info, "NOTE_INFO")
            if note_info:
                abstract += f"[주기사항]\n{note_info}\n"
            
            meta_info = []
            edition = _get_text(bib_info, "EDITION_INFO")
            form = _get_text(bib_info, "FORM_INFO")
            
            if edition: meta_info.append(f"판사항: {edition}")
            if form: meta_info.append(f"형태사항: {form}")
            if pub_info: meta_info.append(f"발행사항: {pub_info}")
            if hold_lib_names: meta_info.append(f"소장기관: {', '.join(hold_lib_names)}")
            
            if meta_info:
                abstract += "\n[서지정보]\n" + "\n".join(meta_info)

            return PaperDetail(
                id=paper_id,
                source=self.name,
                title=title_real or title,
                authors=authors,
                journal=pub_info, # 발행사항을 저널 위치에
                abstract=abstract,
                url=f"https://www.nl.go.kr/korcis/search/searchDetail.do?rec_key={paper_id}"
            )

        except Exception as e:
            print(f"[NL] Detail parse error: {e}")
            return None
