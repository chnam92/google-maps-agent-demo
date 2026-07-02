# Source: Google Maps Platform Code Assist
# Adapted from googlemaps-samples/a2ui agent/python/__main__.py (Apache-2.0).
"""맛집 파인더 A2A 서버 부트스트랩 (기본 포트: 10002)."""

import logging
import os
import pathlib

import click
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

# 프로젝트 루트의 .env를 우선 로드하고, agent/ 로컬 .env가 있으면 덮어씀
_ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv()

# 하위 호환: 구 명칭 GOOGLE_GENAI_USE_VERTEXAI=TRUE도 신 명칭으로 매핑
# (google-genai 2.x부터 표준 변수는 GOOGLE_GENAI_USE_ENTERPRISE)
if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
  os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "TRUE")

from agent_executor import MatjipAgentExecutor  # noqa: E402
from matjip_agent import MatjipAgent  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
  """Exception for missing API key."""


@click.command()
@click.option("--serverurl", default="")
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=10002)
def main(serverurl, host, port):
  try:
    # 인증 모드 검증: ADC 또는 Gemini API 키 중 하나
    if os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", "").upper() == "TRUE":
      if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        raise MissingAPIKeyError(
            "Gemini Enterprise Agent Platform 모드(GOOGLE_GENAI_USE_ENTERPRISE=TRUE)에는"
            " GOOGLE_CLOUD_PROJECT 환경 변수가 필요합니다."
        )
      logger.info(
          "인증 모드: Gemini Enterprise / Vertex AI (ADC) — project=%s, location=%s",
          os.getenv("GOOGLE_CLOUD_PROJECT"),
          os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
      )
    else:
      if not os.getenv("GEMINI_API_KEY"):
        raise MissingAPIKeyError(
            "GEMINI_API_KEY 환경 변수가 설정되지 않았습니다."
            " 프로젝트 루트의 .env 파일을 확인하세요."
            " (Cloud 인증을 쓰려면 GOOGLE_GENAI_USE_ENTERPRISE=TRUE 설정)"
        )
      logger.info("인증 모드: Gemini API 키")
    if not os.getenv("GOOGLE_MAPS_API_KEY"):
      logger.warning(
          "GOOGLE_MAPS_API_KEY가 설정되지 않았습니다."
          " Maps Grounding Lite 도구 호출이 실패할 수 있습니다."
      )

    base_url = f"http://{host}:{port}"
    if serverurl != "":
      base_url = serverurl

    matjip_agent = MatjipAgent(base_url=base_url)
    agent_executor = MatjipAgentExecutor(agent=matjip_agent)

    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=matjip_agent.agent_card, http_handler=request_handler
    )
    import uvicorn

    app = server.build()

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://localhost:\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.info(f"Starting 맛집 파인더 A2A server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
  except Exception:
    logger.exception("An error occurred during server startup")
    exit(1)


if __name__ == "__main__":
  main()
