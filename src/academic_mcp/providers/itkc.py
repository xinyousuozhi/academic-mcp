"""ITKC (Korean Classics DB) OpenAPI provider.

Endpoint:
- http://db.itkc.or.kr/openapi/search

The OpenAPI returns XML with `<doc><field ...>` entries.
This provider maps those documents to the shared Paper/PaperDetail models.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import ClassVar

from academic_mcp.models import Author, Paper, PaperDetail, ProviderCategory, SearchQuery
from academic_mcp.providers.base import BaseProvider


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_year(value: str) -> int | None:
    match = re.search(r"(1[0-9]{3}|20[0-9]{2})", value or "")
    return int(match.group(1)) if match else None


class ITKCProvider(BaseProvider):
    """Korean Classics DB OpenAPI provider."""

    name: ClassVar[str] = "itkc"
    display_name: ClassVar[str] = "Korean Classics DB (ITKC)"
    category: ClassVar[ProviderCategory] = ProviderCategory.ANCIENT

    SEARCH_URL: ClassVar[str] = "http://db.itkc.or.kr/openapi/search"
    ITEM_URL_PREFIX: ClassVar[str] = "https://db.itkc.or.kr/dir/item?itemId="
    DEFAULT_SEC_ID: ClassVar[str] = "CS_AA"
    DETAIL_SEARCH_ROWS: ClassVar[int] = 20

    def is_available(self) -> bool:
        # This endpoint is public and does not require an API key.
        return True

    async def search(self, query: SearchQuery) -> list[Paper]:
        keyword = self._compose_keyword(query)
        if not keyword:
            return []

        try:
            docs = await self._search_docs(keyword=keyword, rows=query.max_results)
        except Exception as exc:
            print(f"[ITKC] Search error: {exc}")
            return []

        papers: list[Paper] = []
        for doc in docs:
            paper = self._doc_to_paper(doc)
            if paper is None:
                continue

            if query.year_from is not None and (paper.year is None or paper.year < query.year_from):
                continue
            if query.year_to is not None and (paper.year is None or paper.year > query.year_to):
                continue

            papers.append(paper)

        return papers[: query.max_results]

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        if not paper_id:
            return None

        try:
            docs = await self._search_docs(keyword=paper_id, rows=self.DETAIL_SEARCH_ROWS)
        except Exception as exc:
            print(f"[ITKC] Detail lookup error: {exc}")
            return None

        if not docs:
            return None

        target = next(
            (
                doc
                for doc in docs
                if doc.get("자료ID") == paper_id or doc.get("DCI_s") == paper_id
            ),
            docs[0],
        )

        paper = self._doc_to_paper(target)
        if paper is None:
            return None

        keywords: list[str] = []
        for key in ("아이템명", "문체명", "서명"):
            value = target.get(key, "").strip()
            if value and value not in keywords:
                keywords.append(value)

        return PaperDetail(
            **paper.model_dump(),
            keywords=keywords,
            publisher="한국고전번역원",
            language="ko",
        )

    async def _search_docs(self, keyword: str, rows: int) -> list[dict[str, str]]:
        params = {
            "secId": self.DEFAULT_SEC_ID,
            "keyword": keyword,
            "start": "0",
            "rows": str(max(1, rows)),
        }
        response = await self.client.get(self.SEARCH_URL, params=params)
        response.raise_for_status()
        return self._parse_docs(response.content)

    def _parse_docs(self, xml_bytes: bytes) -> list[dict[str, str]]:
        docs: list[dict[str, str]] = []
        root = ET.fromstring(xml_bytes)

        for node in root.findall("./result/doc"):
            data: dict[str, str] = {}
            for field in node.findall("field"):
                name = (field.get("name") or "").strip()
                if not name:
                    continue

                # A few fields include inline XML tags (<em>), so use itertext().
                value = _normalize_space("".join(field.itertext()))
                if not value:
                    continue

                if name in data:
                    data[name] = f"{data[name]} {value}".strip()
                else:
                    data[name] = value

            if data:
                docs.append(data)

        return docs

    def _doc_to_paper(self, doc: dict[str, str]) -> Paper | None:
        data_id = doc.get("자료ID", "").strip()
        dci = doc.get("DCI_s", "").strip()
        paper_id = data_id or dci
        if not paper_id:
            return None

        title = (
            doc.get("기사명")
            or doc.get("서명")
            or doc.get("권차명")
            or doc.get("검색필드")
            or "Untitled"
        ).strip()

        authors = self._parse_authors(doc)
        journal = (doc.get("서명") or doc.get("아이템명") or "Korean Classics DB").strip()
        year = _extract_year(doc.get("간행기간", ""))

        abstract_parts: list[str] = []
        for key, label in (
            ("검색필드", None),
            ("권차명", "권차"),
            ("문체명", "문체"),
            ("간행기간", "간행기간"),
        ):
            value = doc.get(key, "").strip()
            if not value:
                continue
            abstract_parts.append(value if label is None else f"{label}: {value}")

        return Paper(
            id=paper_id,
            source=self.name,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            url=self._build_url(doc.get("아이템ID", ""), data_id, dci),
            abstract="\n".join(abstract_parts) if abstract_parts else None,
        )

    def _parse_authors(self, doc: dict[str, str]) -> list[Author]:
        authors: list[Author] = []

        writer = self._format_person(doc.get("저자", ""))
        if writer:
            authors.append(Author(name=writer))

        translator = self._format_person(doc.get("역자", ""))
        if translator:
            authors.append(Author(name=f"역자: {translator}"))

        return authors

    def _format_person(self, raw: str) -> str:
        value = raw.strip()
        if not value:
            return ""

        # Typical ITKC value: "안정복|安鼎福"
        parts = [p.strip() for p in value.split("|") if p.strip()]
        if len(parts) == 2 and "," not in value and ";" not in value:
            return f"{parts[0]} ({parts[1]})"
        return _normalize_space(value.replace("|", ", "))

    def _compose_keyword(self, query: SearchQuery) -> str:
        terms: list[str] = []
        if query.keyword:
            terms.append(query.keyword.strip())
        if query.author:
            terms.append(query.author.strip())
        return " ".join(t for t in terms if t)

    def _build_url(self, item_id: str, data_id: str, dci: str) -> str:
        item_id = item_id.strip()
        data_id = data_id.strip()
        dci = dci.strip()

        if item_id.startswith("ITKC_"):
            return f"{self.ITEM_URL_PREFIX}{item_id.split('_', 1)[1]}"

        if data_id:
            parts = [p for p in data_id.split("_") if p]
            if len(parts) >= 2:
                return f"{self.ITEM_URL_PREFIX}{parts[1]}"

        if dci:
            return f"{self.SEARCH_URL}?secId={self.DEFAULT_SEC_ID}&keyword={dci}"

        return "https://db.itkc.or.kr"
