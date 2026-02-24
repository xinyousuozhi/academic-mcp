# Academic MCP

한국·일본 학술 데이터베이스를 AI 도구에서 검색할 수 있게 해주는 MCP(Model Context Protocol) 서버입니다.

Claude Desktop, Cursor, Windsurf 등 MCP를 지원하는 AI 도구에서 사용할 수 있습니다.

## 지원 데이터베이스

> **📌 안내**: Provider 목록은 향후 추가, 수정 또는 삭제될 수 있습니다.

### 1. 📚 논문/문헌 (Academic Papers)

학술 논문 및 연구 보고서를 검색합니다.

| Provider | 국가 | 콘텐츠 | API 키 | 비고 |
|----------|------|--------|--------|------|
| **KCI** | 🇰🇷 | 한국학술지인용색인 | ❌ 불필요 | OAI-PMH (최신자료 위주) |
| **OAK** | 🇰🇷 | 오픈액세스코리아 | ❌ 불필요 | OAI-PMH (최신자료 위주) |
| **LOSI** | 🇰🇷 | 국회도서관 입법정보 | ✅ 필요 | |
| **CiNii** | 🇯🇵 | 일본 학술논문 | ✅ 필요 | |

> **⚠️ KCI/OAK 검색 제한사항**
>
> KCI와 OAK는 별도의 검색 API 키 없이 **OAI-PMH 프로토콜**을 사용하여 데이터를 수집합니다. 프로토콜 특성상 **최근 6개월** 이내의 데이터만 검색 범위에 포함되며, 과거 전체 논문에 대한 키워드 검색은 제한될 수 있습니다. (전체 검색을 위해서는 해당 기관의 정식 검색 API 키가 필요할 수 있으나, 현재 본 패키지는 무료 OAI-PMH만 지원합니다.)

### 2. 📜 고서류/역사 (Ancient Documents & History)

고문헌, 역사 자료, 지리 정보를 검색합니다.

| Provider | 국가 | 콘텐츠 | API 키 | 비고 |
|----------|------|--------|--------|------|
| **NL** | 🇰🇷 | 한국고문헌종합목록 | ❌ 불필요 | 국립중앙도서관 (KORCIS) |
| **KOSTMA** | 🇰🇷 | 한국학자료센터 | ❌ 불필요 | 고서/고문서 원문 |
| **ITKC** | 🇰🇷 | 한국고전종합DB OpenAPI | ❌ 불필요 | 한국고전번역원 |
| **HGIS** | 🇰🇷 | 국사편찬위원회 역사지리 | ✅ 필요 | 역사/지리 통합 정보 |
| **Gugak** | 🇰🇷 | 국립국악원 학술연구-고서 | ✅ 필요 | 고서/고악보 |

### 3. 📖 사전/기타 (Dictionary & Others)

특수 목적의 사전 및 인물 정보를 검색합니다.

| Provider | 국가 | 콘텐츠 | API 키 | 비고 |
|----------|------|--------|--------|------|
| **KoreanTK**| 🇰🇷 | 지식재산 용어사전 | ✅ 필요 | 특허청/공공데이터포털 |
| **Eyis** | 🇰🇷 | 여성사전시관 인물연구 | ✅ 필요 | 여성가족부/공공데이터포털 |
| **NRICH** | 🇰🇷 | 한국고고학사전 | ❌ 불필요 | 국립문화유산연구원 |
| **Tripitaka** | 🇰🇷 | 고려대장경지식베이스 | ✅ 필요 | 고려대장경연구소 |
| **Folkency** | 🇰🇷 | 한국민속대백과사전 | ✅ 필요 | 국립민속박물관 |
| **Stdict** | 🇰🇷 | 표준국어대사전 | ✅ 필요 | 국립국어원 |

> **Note**: API 키가 필요한 Provider는 각 기관에서 개별 발급받아야 합니다. 아래 [API 키 발급](#api-키-발급) 섹션을 참고하세요.

## 빠른 시작

### 1. 설치

```bash
git clone https://github.com/xinsyousuozhi/academic-mcp.git
cd academic-mcp
uv sync
```

### 2. 설정

```bash
cp .env.example .env
# 필요한 API 키 입력 (선택사항)
# KCI, OAK, KOSTMA는 키 없이도 사용 가능
```

### 3. Claude Desktop 설정

`claude_desktop_config.json`에 추가:

```json
{
  "mcpServers": {
    "academic-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/academic-mcp",
        "run",
        "academic-mcp"
      ]
    }
  }
}
```

**설정 파일 위치:**
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

### 4. 재시작

Claude Desktop을 완전히 종료 후 다시 시작하면 사용 가능합니다.

## 환경 변수

`.env` 파일에서 설정:

```bash
# 활성화할 Provider (쉼표 구분)
# 키 없이 사용 가능: kci, oak, kostma, itkc
ENABLED_PROVIDERS=kci,oak,kostma,itkc

# API 키가 필요한 Provider 추가 시
# ENABLED_PROVIDERS=kci,oak,kostma,itkc,losi,cinii

# 개별 API 키 (필요한 것만 입력)
LOSI_API_KEY=your_losi_key
HISTORY_API_KEY=your_history_key
DATA_GO_KR_API_KEY=your_data_go_kr_key
CINII_API_KEY=your_cinii_key
GUGAK_API_KEY=your_gugak_key
TRIPITAKA_API_KEY=your_tripitaka_key
FOLKENCY_API_KEY=your_folkency_key
STDICT_API_KEY=your_stdict_key
```

## API 키 발급

| Provider | 발급처 | 비고 |
|----------|--------|------|
| **LOSI** | [국회도서관 입법정보](https://losi-open.nanet.go.kr/main.do) | 회원가입 후 신청 |
| **HGIS** | [국사편찬위원회 HGIS](https://hgis.history.go.kr/pro_g1/mainPage.do) | 역사지리정보 |
| **NL** | [국립중앙도서관](https://www.nl.go.kr/korcis/openapi/openApiView.do) | KORCIS 사용 시 키 불필요 |
| **CiNii** | [CiNii API 등록](https://support.nii.ac.jp/en/cinii/api/developer) | 일본 NII 계정 필요 |
| **Gugak** | [문화체육관광부 공공데이터광장](https://www.culture.go.kr/data/openapi/openapiList.do) | "학술연구-고서" 신청 |
| **Tripitaka** | [문화체육관광부 공공데이터광장](https://www.culture.go.kr/data/openapi/openapiList.do) | "고려대장경지식베이스" 신청 |
| **Folkency** | [문화체육관광부 공공데이터광장](https://www.culture.go.kr/data/openapi/openapiList.do) | "한국민속대백과사전" 신청 |
| **Stdict** | [표준국어대사전 개발 지원](https://stdict.korean.go.kr/openapi/openApiInfo.do) | 회원가입 후 API 키 신청 |
| **KoreanTK** | [공공데이터포털](https://www.data.go.kr/) | "지식재산 용어사전" 신청 |
| **Eyis** | [공공데이터포털](https://www.data.go.kr/) | "여성사전시관 인물연구" 신청 |

## 커스터마이징

이 프로젝트는 자유롭게 수정해서 사용할 수 있습니다.

### Provider 추가/제거

`.env` 파일의 `ENABLED_PROVIDERS`에서 원하는 것만 활성화:

```bash
# 예: KCI와 CiNii만 사용
ENABLED_PROVIDERS=kci,cinii
```

### 새 Provider 작성

`src/academic_mcp/providers/` 폴더에 새 Provider 추가:

```python
from academic_mcp.providers.base import BaseProvider

class MyProvider(BaseProvider):
    name = "my_provider"
    display_name = "My Custom Provider"

    async def search(self, query):
        # 구현
        pass
```

## 프로젝트 구조

```
academic-mcp/
├── src/academic_mcp/
│   ├── __main__.py      # 진입점
│   ├── server.py        # MCP 서버 설정
│   ├── config.py        # 환경 변수 설정
│   ├── models.py        # 데이터 모델
│   ├── tools.py         # MCP 도구 정의
│   └── providers/       # 데이터베이스별 Provider
│       ├── base.py
│       ├── kci.py       # KCI (OAI-PMH)
│       ├── oak.py       # OAK (OAI-PMH)
│       ├── kostma.py
│       ├── losi.py
│       ├── hgis.py
│       ├── nl.py
│       └── cinii.py
├── .env.example
└── pyproject.toml
```

## 다른 MCP 클라이언트

Claude Desktop 외에도 MCP를 지원하는 도구에서 사용 가능합니다:

**Cursor:**
```json
// ~/.cursor/mcp.json
{
  "mcpServers": {
    "academic-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/academic-mcp", "run", "academic-mcp"]
    }
  }
}
```

## 라이선스

MIT License

## 관련 프로젝트

- [CNKI MCP](https://github.com/h-lu/cnki-mcp) - 중국 CNKI 학술 데이터베이스
