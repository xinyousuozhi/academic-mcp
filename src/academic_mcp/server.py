"""MCP 서버 설정 및 초기화"""

from mcp.server import Server

from academic_mcp.config import settings
from academic_mcp.providers import (
    CiNiiProvider,
    HGISProvider,
    KCIProvider,
    KOSTMAProvider,
    LOSIProvider,
    NLProvider,
    OAKProvider,
    KoreanTKProvider,
    NRICHProvider,
    EYISProvider,
    GugakProvider,
    TripitakaProvider,
    FolkencyProvider,
    StdictProvider,
    MunjipProvider,
)
from academic_mcp.providers.base import BaseProvider
from academic_mcp.tools import register_search_tools


def create_server() -> tuple[Server, dict[str, BaseProvider]]:
    """MCP 서버 생성 및 Provider 초기화"""

    server = Server("academic-mcp")

    # Provider 초기화
    providers: dict[str, BaseProvider] = {}

    # KCI - OAI-PMH 사용 (API 키 불필요)
    if "kci" in settings.enabled_provider_list:
        providers["kci"] = KCIProvider(api_key=settings.kci_api_key, data_go_kr_key=settings.data_go_kr_api_key)

    # LOSI - 사용 키 사용
    if "losi" in settings.enabled_provider_list:
        providers["losi"] = LOSIProvider(api_key=settings.losi_api_key)

    # 국립중앙도서관 - NL 사용 키 사용
    if "nl" in settings.enabled_provider_list:
        providers["nl"] = NLProvider(api_key=settings.nl_api_key)

    # KOSTMA - 한국학자료센터 (API 키 불필요)
    if "kostma" in settings.enabled_provider_list:
        providers["kostma"] = KOSTMAProvider(api_key=None)

    # OAK - 오픈액세스코리아 (API 키 불필요)
    if "oak" in settings.enabled_provider_list:
        providers["oak"] = OAKProvider(api_key=None)

    # HGIS - 국사편찬위원회 역사지리정보
    if "hgis" in settings.enabled_provider_list:
        providers["hgis"] = HGISProvider(api_key=settings.history_api_key)

    # CiNii - 일본 학술 데이터베이스
    if "cinii" in settings.enabled_provider_list:
        providers["cinii"] = CiNiiProvider(api_key=settings.cinii_api_key)

    # KoreanTK - 지식재산 용어사전 (공공데이터포털)
    if "koreantk" in settings.enabled_provider_list:
        providers["koreantk"] = KoreanTKProvider(api_key=settings.data_go_kr_api_key)

    # NRICH - 국립문화유산연구원 (키 불필요)
    if "nrich" in settings.enabled_provider_list:
        providers["nrich"] = NRICHProvider(api_key=None)

    # EYIS - 여성사전시관 인물연구 (공공데이터포털)
    if "eyis" in settings.enabled_provider_list:
        providers["eyis"] = EYISProvider(api_key=settings.data_go_kr_api_key)

    # Gugak - 국립국악원 고서 (사용 키)
    if "gugak" in settings.enabled_provider_list:
        providers["gugak"] = GugakProvider(api_key=settings.gugak_api_key)

    # Tripitaka - 고려대장경 (사용 키)
    if "tripitaka" in settings.enabled_provider_list:
        providers["tripitaka"] = TripitakaProvider(api_key=settings.tripitaka_api_key)

    # Folkency - 한국민속대백과사전 (사용 키)
    if "folkency" in settings.enabled_provider_list:
        providers["folkency"] = FolkencyProvider(api_key=settings.folkency_api_key)

    # Stdict - 표준국어대사전 (사용 키)
    if "stdict" in settings.enabled_provider_list:
        providers["stdict"] = StdictProvider(api_key=settings.stdict_api_key)

    # Munjip - 한국고전번역원 한국문집총간 (공공데이터포털)
    if "munjip" in settings.enabled_provider_list:
        providers["munjip"] = MunjipProvider(api_key=settings.munjip_api_key)

    # Tools 등록
    register_search_tools(server, providers)

    return server, providers


async def cleanup_providers(providers: dict[str, BaseProvider]) -> None:
    """Provider 정리 (HTTP 클라이언트 종료 등)"""
    for provider in providers.values():
        await provider.close()
