# Maps Agentic UI Toolkit(A2UI) 아키텍처 해설

이 문서는 **Maps Agentic UI Toolkit이 무엇을 하는 도구인지**, 그리고 이 프로젝트에서
**어떤 코드가 핵심 역할을 하는지**를 설명합니다.

---

## 1. 툴킷의 존재 이유: "텍스트로 말하지 말고, UI로 보여줘라"

일반적인 LLM 챗봇은 맛집을 물어보면 **글자로 된 목록**을 돌려줍니다.
Maps Agentic UI Toolkit은 에이전트가 글자 대신 **실제로 동작하는 지도 UI**
(장소 카드, 인터랙티브 지도, 경로 안내)를 응답으로 생성하게 해주는 도구입니다.

이를 위해 두 가지 개방형 표준을 조합합니다:

| 표준 | 역할 | 비유 |
| --- | --- | --- |
| **A2A** (Agent-to-Agent) | 클라이언트 ↔ 에이전트 간 **통신 프로토콜** (JSON-RPC) | 전화선 |
| **A2UI** (Agent-to-User Interface) | 에이전트가 그릴 UI를 기술하는 **선언적 JSON 포맷** | 전화로 불러주는 설계도 |

핵심 아이디어: **LLM이 HTML/JS 코드를 생성하는 것이 아니라**, 미리 정의된 컴포넌트
카탈로그(장소 카드, 지도, 리스트, 버튼 등)를 조합하는 **JSON 메시지**를 생성합니다.
클라이언트는 이 JSON을 검증된 웹 컴포넌트로 렌더링하므로, LLM이 임의 코드를
실행시킬 수 없어 안전하고, 플랫폼(웹/Android/iOS)마다 네이티브로 그릴 수 있습니다.

---

## 2. 전체 데이터 흐름

```
[사용자] "강남역 근처 스시 맛집 보여줘"
   │
   ▼ ①  A2UIClient.send() — A2A JSON-RPC + 확장 헤더
   │     X-A2A-Extensions: https://a2ui.org/a2a-extension/a2ui/v0.9
   ▼
[Python A2A 서버 :10002]
   │  ②  MatjipAgentExecutor — 메시지 분해 (텍스트? UI 액션?)
   │  ③  try_activate_a2ui_extension() — 클라이언트가 A2UI를 지원하는지 협상
   ▼
[MatjipAgent (google-adk LlmAgent + Gemini)]
   │  ④  시스템 프롬프트 = 페르소나 + A2UI JSON 스키마 + 컴포넌트 카탈로그
   │  ⑤  Maps Grounding Lite MCP 도구 호출 → 실제 장소 데이터 획득
   │      (이름·주소·좌표·place id — LLM 기억으로 지어내는 것 금지)
   │  ⑥  LLM이 <a2ui-json>[ {surfaceUpdate...}, {dataModelUpdate...} ]</a2ui-json> 생성
   │  ⑦  jsonschema로 검증 — 실패 시 오류 내용을 붙여 1회 재시도
   ▼
   ⑧  A2A DataPart(mimeType: application/json+a2ui)로 스트리밍 응답
   │
   ▼
[React 클라이언트 :5173]
   │  ⑨  A2UIRenderer.processResponse() — 메시지를 서피스 모델로 변환
   │  ⑩  <a2ui-surface> Lit 웹 컴포넌트가 장소 카드·지도·경로를 렌더링
   │      (지도는 Maps JavaScript API v=alpha 채널 사용)
   ▼
[사용자가 카드 버튼 클릭]
   │  ⑪  userAction 이벤트가 DataPart로 서버에 회신 → ②로 순환
```

---

## 3. 핵심 코드 맵

### 백엔드 (Python)

#### [agent/matjip_agent.py](../agent/matjip_agent.py) — 에이전트의 "인격"과 조립
이 프로젝트의 커스터마이징 핵심. 코어 `MAUIAgent`를 상속해 3가지를 바꿉니다.

- **`MATJIP_INSTRUCTION`** — 한국어 맛집 페르소나. 이 프롬프트의 다음 제약들이
  툴킷 동작의 생명선입니다:
  - *"ALL TEXT RESPONSES MUST BE CONTAINED WITHIN A TEXT COMPONENT IN THE A2UI OUTPUT"*
    → 대화 텍스트조차 A2UI 구조 밖으로 새면 렌더링이 깨짐
  - *"EXACTLY ONE `<a2ui-json>` block"* → 블록이 2개면 UI가 그려지지 않음
  - *"always fetch the place's name, address, lat, lng, and place id"*
    → 지도 마커·카드가 이 필드들을 요구
- **`_build_llm_agent()`** — LLM + 도구 + 스키마 프롬프트의 조립 지점:
  ```python
  instruction = schema_manager.generate_system_prompt(   # A2UI 스키마+카탈로그를
      role_description=MATJIP_INSTRUCTION, ...)          # 페르소나에 주입
  return LlmAgent(
      model=LiteLlm(model="gemini/gemini-3-flash-preview"),
      tools=[grounding_lite_mcp, skill_manager_tool],    # 실데이터 도구 + UI 생성 스킬
  )
  ```

#### [agent/agent_executor.py](../agent/agent_executor.py) — A2A 프로토콜 어댑터
A2A 서버와 에이전트 사이의 번역기. 세 가지 일을 합니다.

1. **입력 분해**: 메시지 파트를 순회하며 일반 텍스트인지, UI에서 온
   `userAction`(버튼 클릭 등)인지 판별 → 액션이면
   `"User submitted an event: {action} with data: {ctx}"` 형태의 질의로 변환
2. **확장 협상**: `try_activate_a2ui_extension()` — 클라이언트가 A2UI v0.9를
   요청했을 때만 UI 모드로 동작 (아니면 일반 텍스트 응답)
3. **스트리밍 중계**: `agent.stream()`이 내놓는 부분 응답을 A2A `TaskState.working`
   상태로 흘려보내고, 완료되면 `input_required`로 마무리 (대화 지속)

#### [agent/__main__.py](../agent/__main__.py) — 서버 부트스트랩
`A2AStarletteApplication`으로 JSON-RPC 서버(:10002)를 띄우고, 에이전트의 정체를
알리는 **에이전트 카드**(`/.well-known/agent-card.json`)를 서빙합니다. 카드에는
`https://a2ui.org/a2a-extension/a2ui/v0.9` 확장이 선언되어 있어 클라이언트가
"이 에이전트는 UI를 그릴 줄 안다"를 발견할 수 있습니다.

#### [vendor/a2ui/agent/python-agent/](../vendor/a2ui/agent/python-agent/) — 코어 라이브러리 (`maui-a2ui-python`)
직접 수정하지 않지만 동작을 이해하려면 알아야 할 부분:

| 파일 | 역할 |
| --- | --- |
| `agent.py` (`MAUIAgent`) | **툴킷의 심장.** 스키마 프롬프트 생성 → LLM 스트리밍 → `<a2ui-json>` 파싱 → jsonschema 검증 → 실패 시 재시도 → A2A Part 변환의 전 과정 (`stream()` 메서드) |
| `shared/schema/maps_catalog_extension.json` | **지도 전용 컴포넌트 카탈로그.** 기본 A2UI 카탈로그(텍스트·리스트·버튼)에 `GoogleMap`, `PlaceCard` 같은 지도 컴포넌트를 추가 정의 |
| `skills/google-maps-enriched-local-query-response/` | LLM에게 "장소 질의에는 이런 구조의 A2UI를 만들어라"를 가르치는 ADK 스킬 |
| `make_grounding_lite_mcp()` | `https://mapstools.googleapis.com/mcp` (Maps Grounding Lite)를 MCP 도구로 연결 — 장소 검색·경로의 **실데이터 소스** |

### 프론트엔드 (React + `@googlemaps/a2ui`)

#### [web/src/App.tsx](../web/src/App.tsx) — 클라이언트 통합의 전부
npm 패키지 `@googlemaps/a2ui`가 제공하는 두 클래스만 알면 됩니다:

```tsx
const clientRef   = useRef(new A2UIClient(window.SERVER_URL))  // ① A2A 통신
const rendererRef = useRef(new A2UIRenderer())                 // ② 상태/렌더링

const response = await clientRef.current.send(messageText)    // ③ 전송
rendererRef.current.processResponse(response)                  // ④ A2UI 메시지 처리
setTimeline([...rendererRef.current.timeline])                 // ⑤ React 상태 동기화
```

- **`A2UIClient`** — 에이전트 카드를 가져와 A2A 연결을 만들고, 모든 요청에
  A2UI 확장 헤더를 자동으로 붙입니다.
- **`A2UIRenderer`** — 응답 속 A2UI 메시지(`surfaceUpdate`, `dataModelUpdate` 등)를
  누적 처리해 **서피스 모델**을 만들고, 시간순 타임라인을 제공합니다.
- **`<a2ui-surface surface={...}>`** — 서피스 모델을 받아 실제 UI로 그리는
  Lit 웹 컴포넌트. 내부적으로 `a2ui-googlemap`(지도), `a2ui-placecard`(장소 카드)
  같은 지도 특화 컴포넌트로 위임합니다.
- **`<maui-providers>`** — 마크다운 렌더러 등 컨텍스트 제공자. 타임라인을 감싸야 합니다.
- **`themeStyleSheet`** — A2UI 위젯 테마. `document.adoptedStyleSheets`에 1회 등록.

#### [web/index.html](../web/index.html) — 지도 로더 (요구사항 주의)
```html
<script src="https://maps.googleapis.com/maps/api/js?v=alpha&key=...
  &libraries=maps,marker,places,maps3d,routes&loading=async">
```
- **`v=alpha` 채널 필수** — 툴킷의 지도 컴포넌트가 알파 채널의 웹 컴포넌트 기능을
  사용합니다 (Pre-GA, SLA 없음)
- 라이브러리 5종(`maps,marker,places,maps3d,routes`)도 툴킷 요구사항

---

## 4. A2UI 메시지는 실제로 어떻게 생겼나

에이전트가 생성하는 것은 이런 JSON 배열입니다 (개념 예시):

```jsonc
[
  { "version": "0.9",
    "surfaceUpdate": {
      "surfaceId": "s1",
      "components": [
        { "id": "root",  "component": { "List": { "children": ["title", "map", "card1"] } } },
        { "id": "title", "component": { "Text": { "text": "강남역 스시 맛집 3곳이에요 🍣" } } },
        { "id": "map",   "component": { "GoogleMap": { "markers": "/places" } } },
        { "id": "card1", "component": { "PlaceCard": { "place": "/places/0" } } }
      ]
    }
  },
  { "version": "0.9",
    "dataModelUpdate": {
      "surfaceId": "s1",
      "path": "/places",
      "contents": [ { "name": "스시선수", "lat": 37.49, "lng": 127.02, "placeId": "ChIJ..." } ]
    }
  },
  { "version": "0.9", "beginRendering": { "surfaceId": "s1", "root": "root" } }
]
```

- **`surfaceUpdate`** — 컴포넌트 트리(무엇을 그릴지)
- **`dataModelUpdate`** — 데이터(장소 목록 등). 컴포넌트가 `/places` 같은
  JSON 포인터로 바인딩
- **`beginRendering`** — "이제 그려도 됨" 신호
- UI에서 발생한 사용자 이벤트는 역방향으로 `userAction` 메시지가 되어
  에이전트에게 전달됩니다 ([agent_executor.py](../agent/agent_executor.py)의 처리 대상)

**UI(구조)와 데이터가 분리**되어 있어서, LLM이 스트리밍 중에 데이터만 갱신하거나
기존 서피스를 부분 업데이트할 수 있습니다.

---

## 5. 신뢰성 장치 (왜 그냥 "JSON 만들어줘"가 아닌가)

LLM이 만드는 JSON은 깨질 수 있습니다. 툴킷은 3중 안전망을 둡니다:

1. **스키마 주입** — 시스템 프롬프트에 A2UI JSON 스키마 + 카탈로그를 통째로 넣어
   생성 단계에서부터 형식을 유도 (`A2uiSchemaManager.generate_system_prompt`)
2. **서버 측 검증** — 응답을 `jsonschema`로 검증하고, 실패하면 **오류 내용을
   프롬프트에 붙여 1회 재시도**, 그래도 실패하면 텍스트 폴백
   (코어 `MAUIAgent.stream()`의 검증 루프)
3. **데이터 그라운딩** — 장소 정보는 Grounding Lite MCP 도구 결과만 사용.
   환각된 장소·좌표가 지도에 찍히는 것을 프롬프트 규칙으로 차단

---

## 6. 커스터마이징 지점 요약

| 바꾸고 싶은 것 | 수정할 곳 |
| --- | --- |
| 에이전트 말투·도메인(맛집→호텔 등) | [agent/matjip_agent.py](../agent/matjip_agent.py) `MATJIP_INSTRUCTION` |
| LLM 모델 | `.env`의 `LITELLM_MODEL` (API 키 모드) 또는 `VERTEX_MODEL` (Cloud 인증 모드) |
| LLM 인증 방식 | `.env`의 `GOOGLE_GENAI_USE_ENTERPRISE=TRUE` + `GOOGLE_CLOUD_PROJECT` → Gemini Enterprise/Vertex AI(ADC), 미설정 시 `GEMINI_API_KEY` ([matjip_agent.py](../agent/matjip_agent.py)의 `_make_model()`) |
| 채팅 UI 디자인 | [web/src/App.tsx](../web/src/App.tsx) + [App.css](../web/src/App.css) (A2UI 위젯 내부는 `themeStyleSheet` 오버라이드) |
| UI 컴포넌트 종류 추가 | 코어의 `maps_catalog_extension.json` 방식처럼 카탈로그 확장 + 클라이언트 컴포넌트 등록 |
| 버튼 클릭 등 액션 처리 | [agent/agent_executor.py](../agent/agent_executor.py)의 `userAction` 분기 |

## 참고 자료

- 샘플 리포: <https://github.com/googlemaps-samples/a2ui>
- 코어 툴킷: <https://github.com/googlemaps/a2ui>
- A2UI 표준: <https://a2ui.org>
- A2A 프로토콜: <https://a2a-protocol.org>
- Maps JS API 문서: <https://developers.google.com/maps/documentation/javascript?utm_campaign=gmp_git_agentskills_v1>
