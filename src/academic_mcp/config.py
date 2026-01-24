from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 공공데이터포털 통합 키 (지식재산 용어사전, 여성사전시관 등)
    data_go_kr_api_key: str | None = None

    # KCI 포털 키 (kci.go.kr에서 발급)
    kci_api_key: str | None = None

    # 개별 기관 키
    losi_api_key: str | None = None  # 국가학술정보
    nl_api_key: str | None = None  # 국립중앙도서관 소장자료
    data4library_api_key: str | None = None  # 도서관 정보나루
    nanet_api_key: str | None = None  # 국회도서관
    scienceon_api_key: str | None = None  # KISTI ScienceON
    dbpia_api_key: str | None = None  # DBPIA
    kostma_api_key: str | None = None  # 한국학자료센터
    nrich_api_key: str | None = None  # 국립문화재연구원
    hgis_api_key: str | None = None  # 한국역사정보통합시스템
    history_api_key: str | None = None  # 국사편찬위원회 HGIS
    cinii_api_key: str | None = None  # CiNii Research (일본)
    gugak_api_key: str | None = None  # 국립국악원 학술연구-고서
    tripitaka_api_key: str | None = None  # 고려대장경연구소 지식베이스
    folkency_api_key: str | None = None  # 국립민속박물괄 한국민속대백과사전
    stdict_api_key: str | None = None  # 국립국어원 표준국어대사전

    # 활성화할 Provider (쉼표 구분)
    enabled_providers: str = "kci,losi"

    @property
    def enabled_provider_list(self) -> list[str]:
        return [p.strip() for p in self.enabled_providers.split(",") if p.strip()]


settings = Settings()
