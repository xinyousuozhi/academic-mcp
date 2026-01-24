"""국립국어원 - 표준국어대사전 Open API Provider

국립국어원에서 제공하는 표준국어대사전 검색 API입니다.
https://stdict.korean.go.kr
"""

import json
from typing import ClassVar

from academic_mcp.models import Author, Paper, PaperDetail, SearchQuery, ProviderCategory
from academic_mcp.providers.base import BaseProvider


class StdictProvider(BaseProvider):
    """국립국어원 - 표준국어대사전 Provider
    
    국어 어휘에 대한 표준 정의를 제공합니다.
    JSON 응답을 사용하여 빠른 파싱이 가능합니다.
    """

    name: ClassVar[str] = "stdict"
    display_name: ClassVar[str] = "표준국어대사전"
    category: ClassVar[ProviderCategory] = ProviderCategory.DICTIONARY

    BASE_URL = "https://stdict.korean.go.kr/api/search.do"

    def is_available(self) -> bool:
        return self.api_key is not None

    async def search(self, query: SearchQuery) -> list[Paper]:
        """표준국어대사전 검색"""
        if not self.api_key:
            return []

        params = {
            "key": self.api_key,
            "q": query.keyword,
            "req_type": "json",  # JSON 사용 (XML보다 파싱 용이)
            "start": "1",
            "num": str(query.max_results),
            "sort": "dict",  # 사전순 정렬
            "part": "word",  # 어휘 검색
        }

        try:
            response = await self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            return self._parse_response(response.text)

        except Exception as e:
            print(f"[Stdict] Search error: {e}")
            return []

    async def get_detail(self, paper_id: str) -> PaperDetail | None:
        """상세 정보 조회 (별도 API 필요 - 미구현)"""
        return None

    def _parse_response(self, content: str) -> list[Paper]:
        """JSON 응답 파싱"""
        papers = []
        try:
            data = json.loads(content)
            
            # API 응답 구조: {"channel": {"total": N, "item": [...]}}
            channel = data.get("channel", {})
            items = channel.get("item", [])
            
            if not isinstance(items, list):
                items = [items] if items else []

            for item in items:
                try:
                    target_code = str(item.get("target_code", ""))
                    word = item.get("word", "").strip()
                    
                    if not word:
                        continue

                    # 뜻풀이 (sense는 객체 또는 배열)
                    sense = item.get("sense", {})
                    if isinstance(sense, list):
                        # 여러 뜻이 있는 경우
                        definitions = []
                        for i, s in enumerate(sense, 1):
                            dfn = s.get("definition", "").strip()
                            if dfn:
                                definitions.append(f"{i}. {dfn}")
                        abstract = "\n".join(definitions) if definitions else None
                        url = sense[0].get("link", "").strip() if sense else None
                    else:
                        # 단일 뜻
                        abstract = sense.get("definition", "").strip() or None
                        url = sense.get("link", "").strip() or None
                    
                    # 품사 정보
                    pos = item.get("pos", "").strip()
                    
                    # 원어 정보 (한자 등)
                    origin = item.get("origin", "").strip()
                    if origin:
                        word_display = f"{word} ({origin})"
                    else:
                        word_display = word

                    papers.append(Paper(
                        id=target_code or word,
                        source="stdict",
                        title=word_display,
                        authors=[Author(name="국립국어원")] if pos else [],
                        journal=f"표준국어대사전 [{pos}]" if pos else "표준국어대사전",
                        year=None,
                        url=url,
                        abstract=abstract
                    ))
                except Exception as e:
                    print(f"[Stdict] Item parse error: {e}")
                    continue

        except json.JSONDecodeError as e:
            print(f"[Stdict] JSON parse error: {e}")
        except Exception as e:
            print(f"[Stdict] Parse error: {e}")
        
        return papers
