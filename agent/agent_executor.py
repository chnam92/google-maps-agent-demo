# Source: Google Maps Platform Code Assist
# Adapted from googlemaps-samples/a2ui agent/python/agent_executor.py (Apache-2.0).
"""A2A AgentExecutor — 사용자 메시지/UI 이벤트를 맛집 파인더 에이전트로 라우팅합니다."""

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    DataPart,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_parts_message,
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError
from a2ui.a2a.extension import try_activate_a2ui_extension

from matjip_agent import MatjipAgent

logger = logging.getLogger(__name__)


class MatjipAgentExecutor(AgentExecutor):
  """맛집 파인더 AgentExecutor."""

  def __init__(self, agent: MatjipAgent):
    self._agent = agent

  async def execute(
      self,
      context: RequestContext,
      event_queue: EventQueue,
  ) -> None:
    query = ""
    ui_event_part = None

    if context.message and context.message.parts:
      logger.info(
          f"--- AGENT_EXECUTOR: Processing {len(context.message.parts)} message"
          " parts ---"
      )
      for i, part in enumerate(context.message.parts):
        if isinstance(part.root, DataPart):
          if "userAction" in part.root.data:
            logger.info(f"  Part {i}: Found a2ui UI ClientEvent payload.")
            ui_event_part = part.root.data["userAction"]
          else:
            logger.info(f"  Part {i}: DataPart (data: {part.root.data})")
        elif isinstance(part.root, TextPart):
          logger.info(f"  Part {i}: TextPart (text: {part.root.text})")
        else:
          logger.info(f"  Part {i}: Unknown part type ({type(part.root)})")

    if ui_event_part:
      # a2ui 컴포넌트에서 발생한 사용자 액션(예: 카드 버튼 클릭)을 질의로 변환
      logger.info(f"Received a2ui ClientEvent: {ui_event_part}")
      action = ui_event_part.get("actionName")
      ctx = ui_event_part.get("context", {})
      query = f"User submitted an event: {action} with data: {ctx}"
    else:
      logger.info("No a2ui UI event part found. Falling back to text input.")
      query = context.get_user_input()

    logger.info(f"--- AGENT_EXECUTOR: Final query for LLM: '{query}' ---")
    logger.info(f"--- Client requested extensions: {context.requested_extensions} ---")

    active_ui_version = try_activate_a2ui_extension(context, self._agent.agent_card)
    if active_ui_version:
      logger.info("--- AGENT_EXECUTOR: A2UI extension is active. Using UI mode. ---")
    else:
      logger.info("--- AGENT_EXECUTOR: A2UI extension inactive. Text-only mode. ---")

    task = context.current_task
    if not task:
      task = new_task(context.message)
      await event_queue.enqueue_event(task)
    updater = TaskUpdater(event_queue, task.id, task.context_id)

    async for item in self._agent.stream(query, task.context_id, active_ui_version):
      is_task_complete = item["is_task_complete"]
      if not is_task_complete:
        message = None
        if "parts" in item:
          message = new_agent_parts_message(item["parts"], task.context_id, task.id)
        elif "updates" in item:
          message = new_agent_text_message(item["updates"], task.context_id, task.id)

        if message:
          await updater.update_status(TaskState.working, message)
        continue

      # 대화형 데모이므로 항상 추가 입력을 기다리는 상태로 유지
      await updater.update_status(
          TaskState.input_required,
          new_agent_parts_message(item["parts"], task.context_id, task.id),
          final=False,
      )
      break

  async def cancel(
      self, request: RequestContext, event_queue: EventQueue
  ) -> Task | None:
    raise ServerError(error=UnsupportedOperationError())
