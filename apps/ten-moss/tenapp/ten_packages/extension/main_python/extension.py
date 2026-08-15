import json
import time
from typing import Literal

from .agent.decorators import agent_event_handler
from ten_runtime import (
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    CmdResult,
    Data,
    StatusCode,
)

from .agent.agent import Agent
from .agent.events import (
    ASRResultEvent,
    LLMResponseEvent,
    ToolRegisterEvent,
    UserJoinedEvent,
    UserLeftEvent,
)
from .helper import _send_cmd, _send_data, parse_sentences
from .config import MainControlConfig

from ten_moss import MossSessionManager
from ten_ai_base.const import CMD_PROPERTY_RESULT
from ten_ai_base.types import LLMToolMetadata, LLMToolMetadataParameter

import uuid

SEARCH_KNOWLEDGE_BASE = "search_knowledge_base"
MAX_MOSS_TOOL_CALLS = 2


class MainControlExtension(AsyncExtension):

    def __init__(self, name: str):
        super().__init__(name)
        self.ten_env: AsyncTenEnv = None
        self.agent: Agent = None
        self.config: MainControlConfig = None
        self.moss: MossSessionManager | None = None

        self.stopped: bool = False
        self._rtc_user_count: int = 0
        self.sentence_fragment: str = ""
        self.turn_id: int = 0
        self.session_id: str = "0"

        self._turn_t0: float | None = None
        self._retrieval_ms: float | None = None
        self._llm_sent_at: float | None = None
        self._llm_first_at: float | None = None
        self._last_grounding: str = ""
        self._last_sdk_ms = None
        self._last_user_text: str = ""
        self._moss_tool_calls: int = 0

    def _current_metadata(self) -> dict:
        return {"session_id": self.session_id, "turn_id": self.turn_id}

    async def on_init(self, ten_env: AsyncTenEnv):
        self.ten_env = ten_env

        config_json, _ = await ten_env.get_property_to_json(None)
        try:
            payload = json.loads(config_json) if config_json else {}
        except json.JSONDecodeError:
            payload = {}
        if payload.get("moss_mode") not in ("ambient", "tool"):
            if payload.get("moss_mode") not in (None, ""):
                ten_env.log_error(
                    f"[MainControlExtension] unknown moss_mode={payload.get('moss_mode')!r}; using ambient"
                )
            payload["moss_mode"] = "ambient"
        self.config = MainControlConfig.model_validate(payload)

        self.moss = None
        if self.config.enable_moss and self.config.moss_index_name:
            try:
                self.moss = MossSessionManager.from_config(self.config)
                await self.moss.open()
                ten_env.log_info("[MainControlExtension] Moss session opened")
            except Exception as exc:
                self.moss = None
                ten_env.log_error(
                    f"[MainControlExtension] Moss session failed to open: {exc}"
                )

        self.agent = Agent(ten_env)

        for attr_name in dir(self):
            fn = getattr(self, attr_name)
            event_type = getattr(fn, "_agent_event_type", None)
            if event_type:
                self.agent.on(event_type, fn)

        if self.config.moss_mode == "tool":
            await self._register_search_knowledge_base()

    @agent_event_handler(UserJoinedEvent)
    async def _on_user_joined(self, event: UserJoinedEvent):
        self._rtc_user_count += 1
        if self._rtc_user_count == 1 and self.config and self.config.greeting:
            await self._send_to_tts(self.config.greeting, True)
            await self._send_transcript(
                "assistant", self.config.greeting, True, 100
            )

    @agent_event_handler(UserLeftEvent)
    async def _on_user_left(self, event: UserLeftEvent):
        self._rtc_user_count -= 1

    @agent_event_handler(ToolRegisterEvent)
    async def _on_tool_register(self, event: ToolRegisterEvent):
        await self.agent.register_llm_tool(event.tool, event.source)

    @agent_event_handler(ASRResultEvent)
    async def _on_asr_result(self, event: ASRResultEvent):
        self.session_id = event.metadata.get("session_id", "100")
        try:
            stream_id = int(self.session_id)
        except (TypeError, ValueError):
            stream_id = 0
        if not event.text:
            return
        if event.final or len(event.text) > 2:
            await self._interrupt()
        if event.final:
            self.turn_id += 1
            self._turn_t0 = time.perf_counter()
            self._retrieval_ms = None
            self._last_grounding = ""
            self._last_sdk_ms = None
            self._last_user_text = event.text
            self._moss_tool_calls = 0
            llm_input = event.text
            if self.moss is not None and self.config.moss_mode != "tool":
                context = await self._query_moss(event.text)
                if context:
                    llm_input = f"{context}\n\n[Current User Question]\n{event.text}"
            self._llm_sent_at = time.perf_counter()
            self._llm_first_at = None
            await self.agent.queue_llm_input(llm_input)
        await self._send_transcript("user", event.text, event.final, stream_id)
        if event.final and self.moss is not None and self.config.moss_mode != "tool":
            await self._send_retrieval_note(self._last_grounding, self._last_sdk_ms)

    @agent_event_handler(LLMResponseEvent)
    async def _on_llm_response(self, event: LLMResponseEvent):
        if (
            event.type == "message"
            and self._llm_first_at is None
            and self._llm_sent_at is not None
        ):
            self._llm_first_at = time.perf_counter()

        if not event.is_final and event.type == "message":
            sentences, self.sentence_fragment = parse_sentences(
                self.sentence_fragment, event.delta
            )
            for s in sentences:
                await self._send_to_tts(s, False)

        if event.is_final and event.type == "message":
            remaining_text = self.sentence_fragment or ""
            self.sentence_fragment = ""
            await self._send_to_tts(remaining_text, True)
            await self._log_latency_breakdown()

        await self._send_transcript(
            "assistant",
            event.text,
            event.is_final,
            100,
            data_type=("reasoning" if event.type == "reasoning" else "text"),
        )

    async def on_start(self, ten_env: AsyncTenEnv):
        ten_env.log_info("[MainControlExtension] on_start")

    async def on_stop(self, ten_env: AsyncTenEnv):
        ten_env.log_info("[MainControlExtension] on_stop")
        self.stopped = True
        await self.agent.stop()

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd):
        if cmd.get_name() == "tool_call":
            await self._on_tool_call(cmd)
            return
        await self.agent.on_cmd(cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data):
        await self.agent.on_data(data)

    async def _register_search_knowledge_base(self) -> None:
        tool = LLMToolMetadata(
            name=SEARCH_KNOWLEDGE_BASE,
            description=(
                "Search the knowledge base for facts that answer the user's "
                "question. Pass a focused natural-language query."
            ),
            parameters=[
                LLMToolMetadataParameter(
                    name="query",
                    type="string",
                    description="The user's question or a focused search query.",
                    required=True,
                ),
            ],
        )
        await self.agent.register_llm_tool(tool, "main_control")
        self.ten_env.log_info(
            "[MainControlExtension] registered tool search_knowledge_base"
        )

    async def _on_tool_call(self, cmd: Cmd) -> None:
        try:
            raw, _ = cmd.get_property_to_json(None)
            payload = json.loads(raw) if raw else {}
        except Exception as exc:  # noqa: BLE001
            self.ten_env.log_error(
                f"[MainControlExtension] tool_call payload unreadable: {exc}"
            )
            payload = {}
        name = payload.get("name") or ""
        arguments = payload.get("arguments") or payload.get("args") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        query = ""
        if isinstance(arguments, dict):
            query = str(arguments.get("query") or "")
        if not query:
            query = self._last_user_text

        grounding = ""
        if name == SEARCH_KNOWLEDGE_BASE:
            if self._moss_tool_calls >= MAX_MOSS_TOOL_CALLS:
                self.ten_env.log_info(
                    f"[MainControlExtension] search_knowledge_base cap "
                    f"({MAX_MOSS_TOOL_CALLS}) reached this turn"
                )
            else:
                self._moss_tool_calls += 1
                grounding = await self._query_moss(query)
                await self._send_retrieval_note(grounding, self._last_sdk_ms)
        else:
            self.ten_env.log_error(
                f"[MainControlExtension] unknown tool_call name={name!r}"
            )

        result = CmdResult.create(StatusCode.OK, cmd)
        result.set_property_from_json(
            CMD_PROPERTY_RESULT,
            json.dumps({"type": "llmresult", "content": grounding or ""}),
        )
        await self.ten_env.return_result(result)

    async def _query_moss(self, user_text: str) -> str:
        # Reset per-query state up front so a failed search never replays the
        # previous hit's grounding/latency in the retrieval note.
        self._last_grounding = ""
        self._last_sdk_ms = None
        if self.moss is None:
            return ""
        try:
            t0 = time.perf_counter()
            context = await self.moss.query_context(user_text)
            took_ms = (time.perf_counter() - t0) * 1000.0
            sdk_ms = getattr(self.moss, "last_time_taken_ms", None)
            self._retrieval_ms = float(sdk_ms) if sdk_ms is not None else took_ms
            self._last_grounding = context
            self._last_sdk_ms = sdk_ms
            self.ten_env.log_info(
                f"[retrieval-latency] backend=moss(in-process) "
                f"time_taken_ms={sdk_ms} (wall_clock={took_ms:.0f}ms)"
            )
            return context
        except Exception as exc:  # noqa: BLE001
            self.ten_env.log_error(
                f"[MainControlExtension] Moss grounding failed: {exc}"
            )
            return ""

    async def _log_latency_breakdown(self):
        now = time.perf_counter()

        def _ms(v: float | None) -> str:
            return f"{v:.0f}" if v is not None else "n/a"

        retrieval = self._retrieval_ms
        ttft = (
            (self._llm_first_at - self._llm_sent_at) * 1000.0
            if self._llm_first_at is not None and self._llm_sent_at is not None
            else None
        )
        llm_total = (now - self._llm_sent_at) * 1000.0 if self._llm_sent_at is not None else None
        turn_total = (now - self._turn_t0) * 1000.0 if self._turn_t0 is not None else None

        self.ten_env.log_info(
            f"[latency-breakdown] turn={self.turn_id} "
            f"moss_retrieval_ms={_ms(retrieval)} llm_ttft_ms={_ms(ttft)} "
            f"llm_total_ms={_ms(llm_total)} turn_total_ms={_ms(turn_total)}"
        )
        note = (
            f"⏱ turn {self.turn_id} · Moss {_ms(retrieval)} ms (time_taken_ms) · "
            f"LLM first token {_ms(ttft)} ms · LLM total {_ms(llm_total)} ms"
        )
        await self._send_transcript(
            "assistant", note, True, 710_000_000 + self.turn_id, data_type="reasoning"
        )

    async def _send_retrieval_note(self, grounding: str, time_taken_ms):
        ms_txt = f"{time_taken_ms}" if time_taken_ms is not None else "n/a"
        body = (
            f"🔎 Moss · retrieved in {ms_txt} ms (SDK time_taken_ms)\n\n{grounding}"
            if grounding
            else f"🔎 Moss · retrieved in {ms_txt} ms (SDK time_taken_ms) — no match"
        )
        # Distinct stream_id so this note is not merged into the answer bubble.
        await self._send_transcript(
            "assistant", body, True, 700_000_000 + self.turn_id, data_type="reasoning"
        )

    async def _send_transcript(
        self,
        role: str,
        text: str,
        final: bool,
        stream_id: int,
        data_type: Literal["text", "reasoning"] = "text",
    ):
        if data_type == "text":
            await _send_data(
                self.ten_env,
                "message",
                "message_collector",
                {
                    "data_type": "transcribe",
                    "role": role,
                    "text": text,
                    "text_ts": int(time.time() * 1000),
                    "is_final": final,
                    "stream_id": stream_id,
                },
            )
        elif data_type == "reasoning":
            await _send_data(
                self.ten_env,
                "message",
                "message_collector",
                {
                    "data_type": "raw",
                    "role": role,
                    "text": json.dumps(
                        {
                            "type": "reasoning",
                            "data": {
                                "text": text,
                            },
                        }
                    ),
                    "text_ts": int(time.time() * 1000),
                    "is_final": final,
                    "stream_id": stream_id,
                },
            )
        self.ten_env.log_info(
            f"[MainControlExtension] Sent transcript: {role}, final={final}, text={text}"
        )

    async def _send_to_tts(self, text: str, is_final: bool):
        request_id = f"tts-request-{self.turn_id}"
        await _send_data(
            self.ten_env,
            "tts_text_input",
            "tts",
            {
                "request_id": request_id,
                "text": text,
                "text_input_end": is_final,
                "metadata": self._current_metadata(),
            },
        )
        self.ten_env.log_info(
            f"[MainControlExtension] Sent to TTS: is_final={is_final}, text={text}"
        )

    async def _interrupt(self):
        self.sentence_fragment = ""
        await self.agent.flush_llm()
        await _send_data(
            self.ten_env, "tts_flush", "tts", {"flush_id": str(uuid.uuid4())}
        )
        await _send_cmd(self.ten_env, "flush", "agora_rtc")
        self.ten_env.log_info("[MainControlExtension] Interrupt signal sent")
