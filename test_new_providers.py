import asyncio
import os
from academic_mcp.providers.koreantk import KoreanTKProvider
from academic_mcp.providers.nrich import NRICHProvider
from academic_mcp.providers.eyis import EYISProvider
from academic_mcp.models import SearchQuery
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

async def test_koreantk():
    print("\n=== Testing KoreanTK (지식재산 용어사전) ===")
    api_key = os.getenv("DATA_GO_KR_API_KEY")
    if not api_key:
        print("Skipping: DATA_GO_KR_API_KEY not found")
        return

    provider = KoreanTKProvider(api_key=api_key)
    try:
        results = await provider.search(SearchQuery(keyword="특허", max_results=3))
        if results:
            for p in results:
                authors = ", ".join(a.name for a in p.authors) if p.authors else "N/A"
                print(f"- [{p.id}] {p.title} (저자: {authors})")
        else:
            print("No results found.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await provider.close()

async def test_nrich():
    print("\n=== Testing NRICH (국립문화유산연구원) ===")
    provider = NRICHProvider(api_key=None)
    try:
        # 전체 목록 조회 (키워드 없이)
        results = await provider.search(SearchQuery(keyword="", max_results=5))
        if results:
            for p in results:
                authors = ", ".join(a.name for a in p.authors) if p.authors else "N/A"
                print(f"- [{p.id}] {p.title} ({p.year or 'N/A'}) - {authors}")
                print(f"  URL: {p.url}")
        else:
            print("No results found.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await provider.close()

async def test_eyis():
    print("\n=== Testing Eyis (여성사전시관 인물연구) ===")
    api_key = os.getenv("DATA_GO_KR_API_KEY")
    if not api_key:
        print("Skipping: DATA_GO_KR_API_KEY not found")
        return

    provider = EYISProvider(api_key=api_key)
    try:
        # 인물연구명 검색 예시 (샘플데이터 참고: "평량")
        results = await provider.search(SearchQuery(keyword="평량", max_results=3))
        if results:
            for p in results:
                authors = ", ".join(a.name for a in p.authors) if p.authors else "N/A"
                print(f"- [{p.id}] {p.title} ({p.year or 'N/A'}) - {authors}")
                print(f"  Journal: {p.journal}")
        else:
            print("No results found.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await provider.close()

async def main():
    await test_koreantk()
    await test_nrich()
    await test_eyis()

if __name__ == "__main__":
    asyncio.run(main())
