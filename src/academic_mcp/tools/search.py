"""통합 검색 MCP Tools"""

import asyncio
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from academic_mcp.models import SearchQuery, SearchResult
from academic_mcp.providers.base import BaseProvider


def register_search_tools(server: Server, providers: dict[str, BaseProvider]) -> None:
    """검색 관련 MCP Tools 등록"""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search",
                description="여러 학술 DB에서 논문/문헌을 통합 검색합니다. 키워드, 저자, 연도 등으로 검색할 수 있습니다.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "검색 키워드",
                        },
                        "author": {
                            "type": "string",
                            "description": "저자명 (선택)",
                        },
                        "year_from": {
                            "type": "integer",
                            "description": "시작 연도 (선택)",
                        },
                        "year_to": {
                            "type": "integer",
                            "description": "종료 연도 (선택)",
                        },
                        "providers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": f"검색할 기관 목록 (선택). 가능한 값: {list(providers.keys())}",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "최대 결과 수 (기본: 20, 최대: 100)",
                            "default": 20,
                        },
                    },
                    "required": ["keyword"],
                },
            ),
            Tool(
                name="get_paper_detail",
                description="논문/문헌의 상세 정보(초록, 키워드, 인용정보 등)를 조회합니다.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "paper_id": {
                            "type": "string",
                            "description": "논문 ID",
                        },
                        "source": {
                            "type": "string",
                            "description": f"출처 기관. 가능한 값: {list(providers.keys())}",
                        },
                    },
                    "required": ["paper_id", "source"],
                },
            ),
            Tool(
                name="list_providers",
                description="사용 가능한 학술 DB 목록을 조회합니다.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "search":
            return await _handle_search(arguments, providers)
        elif name == "get_paper_detail":
            return await _handle_get_detail(arguments, providers)
        elif name == "list_providers":
            return await _handle_list_providers(providers)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_search(
    arguments: dict[str, Any],
    providers: dict[str, BaseProvider],
) -> list[TextContent]:
    """통합 검색 처리"""
    try:
        query = SearchQuery(
            keyword=arguments["keyword"],
            author=arguments.get("author"),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            providers=arguments.get("providers"),
            max_results=arguments.get("max_results", 20),
        )
    except Exception as e:
        return [TextContent(type="text", text=f"Invalid query: {e}")]

    # 검색할 Provider 결정
    target_providers = query.providers or list(providers.keys())
    active_providers = {
        name: p for name, p in providers.items()
        if name in target_providers and p.is_available()
    }

    if not active_providers:
        return [TextContent(type="text", text="사용 가능한 학술 DB가 없습니다. API 키를 확인해주세요.")]

    # 병렬 검색
    async def search_provider(name: str, provider: BaseProvider) -> tuple[str, list, str | None]:
        try:
            results = await provider.search(query)
            return (name, results, None)
        except Exception as e:
            return (name, [], str(e))

    tasks = [search_provider(n, p) for n, p in active_providers.items()]
    results = await asyncio.gather(*tasks)

    # 결과 집계
    all_papers = []
    errors = {}
    for name, papers, error in results:
        if error:
            errors[name] = error
        else:
            all_papers.extend(papers)

    # 결과 포맷팅
    result = SearchResult(
        query=query,
        total_count=len(all_papers),
        papers=all_papers,
        errors=errors,
    )

    # 텍스트 응답 생성
    lines = [f"## 검색 결과: '{query.keyword}'", f"총 {result.total_count}건\n"]

    for i, paper in enumerate(result.papers[:50], 1):  # 최대 50개만 표시
        authors_str = ", ".join(a.name for a in paper.authors[:3])
        if len(paper.authors) > 3:
            authors_str += " 외"

        line = f"{i}. **{paper.title}**"
        if authors_str:
            line += f"\n   저자: {authors_str}"
        if paper.journal:
            line += f"\n   학술지: {paper.journal}"
        if paper.year:
            line += f" ({paper.year})"
        line += f"\n   출처: {paper.source} | ID: {paper.id}"
        if paper.url:
            line += f"\n   URL: {paper.url}"
        lines.append(line)

    if errors:
        lines.append("\n### 오류 발생")
        for name, err in errors.items():
            lines.append(f"- {name}: {err}")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_get_detail(
    arguments: dict[str, Any],
    providers: dict[str, BaseProvider],
) -> list[TextContent]:
    """상세 정보 조회 처리"""
    paper_id = arguments.get("paper_id")
    source = arguments.get("source")

    if not paper_id or not source:
        return [TextContent(type="text", text="paper_id와 source가 필요합니다.")]

    provider = providers.get(source)
    if not provider:
        return [TextContent(type="text", text=f"알 수 없는 출처: {source}")]

    if not provider.is_available():
        return [TextContent(type="text", text=f"{source} API가 사용 불가능합니다. API 키를 확인해주세요.")]

    detail = await provider.get_detail(paper_id)
    if not detail:
        return [TextContent(type="text", text=f"논문을 찾을 수 없습니다: {paper_id}")]

    # 상세 정보 포맷팅
    lines = [
        f"## {detail.title}",
        "",
        f"**출처**: {detail.source}",
        f"**ID**: {detail.id}",
    ]

    if detail.authors:
        authors_str = ", ".join(a.name for a in detail.authors)
        lines.append(f"**저자**: {authors_str}")

    if detail.journal:
        journal_info = detail.journal
        if detail.volume:
            journal_info += f", Vol. {detail.volume}"
        if detail.issue:
            journal_info += f", No. {detail.issue}"
        if detail.pages:
            journal_info += f", pp. {detail.pages}"
        lines.append(f"**학술지**: {journal_info}")

    if detail.year:
        lines.append(f"**발행연도**: {detail.year}")

    if detail.doi:
        lines.append(f"**DOI**: {detail.doi}")

    if detail.citation_count is not None:
        lines.append(f"**피인용 횟수**: {detail.citation_count}")

    if detail.keywords:
        lines.append(f"**키워드**: {', '.join(detail.keywords)}")

    if detail.abstract:
        lines.append(f"\n### 초록\n{detail.abstract}")

    if detail.url:
        lines.append(f"\n**원문 링크**: {detail.url}")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_list_providers(
    providers: dict[str, BaseProvider],
) -> list[TextContent]:
    """Provider 목록 조회"""
    lines = ["## 사용 가능한 학술 DB", ""]

    for name, provider in providers.items():
        status = "✅ 사용 가능" if provider.is_available() else "❌ API 키 필요"
        lines.append(f"- **{name}** ({provider.display_name}): {status}")

    return [TextContent(type="text", text="\n".join(lines))]
