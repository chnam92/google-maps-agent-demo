# 맛집 파인더 🍜 — Maps Agentic UI Toolkit 데모

한국어 **맛집·장소 탐색 어시스턴트** 웹 데모입니다.
[Maps Agentic UI Toolkit (A2UI)](https://github.com/googlemaps-samples/a2ui)을 사용해,
AI 에이전트가 장소 카드·지도·경로 같은 **리치 UI를 직접 생성**해 응답합니다.

```
┌───────────────────────────┐        A2A JSON-RPC + A2UI v0.9 ext.
│  web/  React 19 + Vite 8  │ ◄─────────────────────────────────────┐
│  @googlemaps/a2ui (Lit)   │                                       │
└───────────────────────────┘                                       │
                                                     ┌──────────────┴─────────────┐
                                                     │  agent/  Python A2A 서버   │
                                                     │  google-adk + Gemini       │
                                                     │  maui-a2ui-python (vendor) │
                                                     │  Maps Grounding Lite MCP   │
                                                     └────────────────────────────┘
```

> 📖 툴킷의 동작 원리와 핵심 코드 해설은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)를 참고하세요.

## 구성

| 경로 | 설명 |
| --- | --- |
| `agent/` | Python A2A 에이전트 서버 (포트 10002). Gemini가 A2UI JSON을 생성하고, 장소 데이터는 Maps Grounding Lite MCP에서 실시간 조회 |
| `web/` | React 19 + Vite + TypeScript 채팅 UI (포트 5173). `@googlemaps/a2ui`의 `A2UIClient`/`A2UIRenderer`로 A2UI 서피스 렌더링 |
| `vendor/a2ui/` | [googlemaps/a2ui](https://github.com/googlemaps/a2ui) 코어 툴킷 git 서브모듈 (`maui-a2ui-python` 패키지 소스) |

## 사전 준비

- Node.js 20+, `pnpm` 10+, `uv` (Python 3.12+)
- **LLM 인증 (둘 중 하나)**
  - **GEMINI_API_KEY** — [Google AI Studio](https://aistudio.google.com/)에서 무료 발급
  - **Cloud 인증 (Gemini Enterprise / Vertex AI + ADC)** — API 키 없이 `gcloud auth application-default login`으로 인증.
    `.env`에 `GOOGLE_GENAI_USE_ENTERPRISE=TRUE`(구 명칭 `GOOGLE_GENAI_USE_VERTEXAI`도 지원),
    `GOOGLE_CLOUD_PROJECT=<프로젝트ID>` 설정 및 해당 프로젝트에
    [Vertex AI(Agent Platform) API 활성화](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com) 필요
- **GOOGLE_MAPS_API_KEY** — [Google Cloud Console](https://console.cloud.google.com/google/maps-apis/credentials)에서 발급.
  다음 API 활성화 필요: **Maps JavaScript API, Places API (New)/Places UI Kit, Routes API, Geocoding API**

```bash
# vendor/a2ui는 git 서브모듈이므로 --recurse-submodules로 클론
git clone --recurse-submodules <repo-url>
# (이미 클론했다면: git submodule update --init)

cp .env.example .env   # 키를 채워넣기
```

## 실행

```bash
./dev.sh               # 에이전트(10002) + 웹(5173) 동시 실행
```

또는 개별 실행:

```bash
# 터미널 1 — 에이전트
cd agent && uv sync && uv run .

# 터미널 2 — 웹
cd web && pnpm install && pnpm dev
```

브라우저에서 <http://localhost:5173> 접속 후 이렇게 물어보세요:

- "강남역 근처 스시 맛집 보여줘"
- "첫 번째 식당까지 가는 길 알려줘" (이전 대화 맥락 유지)

## 프로덕션 주의사항

- Google Maps Platform 사용은 Google Cloud 결제 계정에 **비용이 발생할 수 있습니다**.
- 프로덕션 키는 반드시 [HTTP 리퍼러·API 제한](https://docs.cloud.google.com/api-keys/docs/add-restrictions-api-keys?utm_campaign=gmp_git_agentskills_v1)을 설정하세요.
- Maps JS API를 `v=alpha` 채널로 로드합니다 (Agentic UI Toolkit 요구사항, 실험적 기능).
- 이 코드의 사용은 [Google Maps Platform 서비스 약관](https://cloud.google.com/maps-platform/terms?utm_campaign=gmp_git_agentskills_v1)의 적용을 받습니다.

## 라이선스

Google 소스 스니펫(에이전트 부트스트랩/실행기, `vendor/a2ui`)은 Apache-2.0으로 제공됩니다.
