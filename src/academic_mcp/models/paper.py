from datetime import date
from pydantic import BaseModel, Field


class Author(BaseModel):
    """저자 정보"""
    name: str
    affiliation: str | None = None
    orcid: str | None = None


class Paper(BaseModel):
    """논문/문헌 기본 정보 (검색 결과용)"""
    id: str = Field(description="기관별 고유 ID")
    source: str = Field(description="출처 기관 (kci, riss, dbpia 등)")
    title: str
    authors: list[Author] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = Field(default=None, description="원문 링크")


class PaperDetail(Paper):
    """논문/문헌 상세 정보"""
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    citation_count: int | None = Field(default=None, description="피인용 횟수")
    references: list[str] = Field(default_factory=list, description="참고문헌 목록")
    publisher: str | None = None
    language: str | None = None
    publication_date: date | None = None


class Citation(BaseModel):
    """인용 정보"""
    citing_paper_id: str
    citing_paper_title: str
    citing_paper_authors: list[str] = Field(default_factory=list)
    citing_paper_year: int | None = None
    source: str


class SearchQuery(BaseModel):
    """검색 쿼리"""
    keyword: str = Field(description="검색 키워드")
    author: str | None = Field(default=None, description="저자명")
    year_from: int | None = Field(default=None, description="시작 연도")
    year_to: int | None = Field(default=None, description="종료 연도")
    providers: list[str] | None = Field(default=None, description="검색할 기관 목록 (None이면 전체)")
    max_results: int = Field(default=20, ge=1, le=100, description="최대 결과 수")


class SearchResult(BaseModel):
    """검색 결과"""
    query: SearchQuery
    total_count: int
    papers: list[Paper]
    errors: dict[str, str] = Field(default_factory=dict, description="기관별 에러 메시지")
