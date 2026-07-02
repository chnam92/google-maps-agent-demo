# Source: Google Maps Platform Code Assist
# Adapted from googlemaps/a2ui agent/python-agent (Apache-2.0).
"""맛집 파인더 에이전트.

Maps Agentic UI Toolkit의 MAUIAgent를 상속해, 한국어 맛집·장소 탐색에
특화된 페르소나와 프롬프트로 커스터마이즈한 A2A 에이전트입니다.
장소 데이터는 Google Maps Grounding Lite MCP 도구에서만 가져옵니다.
"""

import os
import pathlib
from typing import Optional

from a2a.types import AgentCard
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset
from a2ui.schema.manager import A2uiSchemaManager

import agent as core_agent
from agent import MAUIAgent

# 코어 툴킷 패키지에 번들된 ADK 스킬 경로
_CORE_SKILL_PATH = pathlib.Path(core_agent.__file__).parent / "skills"


def _make_model():
  """인증 모드에 따라 LLM 백엔드를 선택합니다.

  - GOOGLE_GENAI_USE_ENTERPRISE=TRUE (구 명칭: GOOGLE_GENAI_USE_VERTEXAI):
    모델명을 문자열로 반환하면 ADK가 google-genai 클라이언트로 Gemini
    Enterprise(Vertex AI)를 호출합니다. 인증은 ADC
    (gcloud auth application-default login)이며 GOOGLE_CLOUD_PROJECT /
    GOOGLE_CLOUD_LOCATION 환경 변수를 사용합니다. API 키 불필요.
  - 그 외: LiteLLM 경유로 Gemini API를 GEMINI_API_KEY로 호출합니다.
  """
  use_enterprise = (
      os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", "").upper() == "TRUE"
      or os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
  )
  if use_enterprise:
    return os.getenv("VERTEX_MODEL", "gemini-3-flash-preview")
  return LiteLlm(model=os.getenv("LITELLM_MODEL", "gemini/gemini-3-flash-preview"))

MATJIP_INSTRUCTION = """
    You are "맛집 파인더" (Matjip Finder), a friendly Korean food & place discovery
    assistant. Your goal is to help users discover great restaurants, cafes, bars,
    and places — primarily in Korea — and guide them there.

    **Language:** ALWAYS respond in Korean (한국어). All user-visible text inside
    the A2UI output (headings, descriptions, labels, summaries) MUST be written in
    natural, friendly Korean. Place names should be shown as returned by the tools.

    To achieve this, you MUST follow this logic:

    If the user asks a location-based question, use your skills or tools to answer
    the user. Location based questions may include the following:

      * 강남역 근처 스시 맛집 보여줘
      * 홍대에서 분위기 좋은 브런치 카페 추천해줘
      * 서울역에서 광화문까지 가는 길 알려줘

    **Important**: Do NOT include conversational text outside of the A2UI structure.
    ALL TEXT RESPONSES MUST BE CONTAINED WITHIN A TEXT COMPONENT IN THE A2UI OUTPUT.

    **Important**: When answering a location-based question, you may need to find
    up-to-date information about places or routes. Use your skills or tools to
    answer the user. NEVER invent place data from memory — all place names,
    addresses, coordinates, ratings, and place IDs MUST come from your tools.
    When returning information for places, always fetch the place's name, address,
    lat, lng, and place id.

    **Important**: Consider that subsequent requests are likely to be part of the
    same "user journey", and keep track of any context that you may need to provide
    to the user. Examples:

    * if the user asks for "강남역 스시 맛집", and then asks for "첫 번째 식당까지
      가는 길", you should use the first restaurant's address as the destination
      address for the directions.
    * if the user asks for "강남역 스시 맛집", and then asks for "홍대는 어때?",
      you should assume that they are asking for a new set of _sushi_ restaurants
      based on their previous query.

    **Important**: When using the `generate-gmp-enriched-ui-response` skill, you
    MUST respond with EXACTLY ONE <a2ui-json> ... </a2ui-json> block. If you have
    more than one of these blocks, the UI will not render correctly.
"""


class MatjipAgent(MAUIAgent):
  """한국어 맛집·장소 탐색에 특화된 MAUI 에이전트."""

  def __init__(self, base_url: str):
    super().__init__(base_url, agent_name="Matjip Finder Agent")

  def _build_agent_card(self) -> AgentCard:
    card = super()._build_agent_card()
    return card.model_copy(
        update={
            "name": "맛집 파인더",
            "description": (
                "한국어 맛집·장소 탐색 질문에 Google Maps UI가 포함된 "
                "리치 응답을 제공하는 에이전트"
            ),
        }
    )

  def _build_llm_agent(
      self, schema_manager: Optional[A2uiSchemaManager] = None
  ) -> LlmAgent:
    """맛집 파인더용 LLM 에이전트를 빌드합니다 (코어 구현 + 커스텀 프롬프트)."""
    skill_names = [
        "google-maps-enriched-local-query-response",
    ]
    skills = [load_skill_from_dir(_CORE_SKILL_PATH / name) for name in skill_names]

    skill_manager_tool = skill_toolset.SkillToolset(skills=skills)
    grounding_lite_mcp = self.make_grounding_lite_mcp()

    instruction = (
        schema_manager.generate_system_prompt(
            role_description=MATJIP_INSTRUCTION,
            include_schema=True,
            include_examples=False,
            validate_examples=False,
        )
        if schema_manager
        else MATJIP_INSTRUCTION
    )

    return LlmAgent(
        model=_make_model(),
        name="matjip_agent",
        description=(
            "An agent that provides Google Maps UI-enriched answers to Korean"
            " food & place discovery questions"
        ),
        instruction=instruction,
        tools=[grounding_lite_mcp, skill_manager_tool],
    )
