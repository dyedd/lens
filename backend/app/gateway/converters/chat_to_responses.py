import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from ._chat_stream import ChatToolCall, ChatToolCalls, chat_choice_index
from ._sse import (
    FINISH_REASON_CHAT_TO_RESPONSES,
    format_sse_event,
    parse_sse_json_stream,
)


def chat_response_to_responses(
    chat_body: dict[str, Any], original_model: str
) -> dict[str, Any]:
    """Convert a chat response into a Responses API response."""
    choice = (chat_body.get("choices") or [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason")
    status, incomplete_details = _response_status(finish_reason)

    output: list[dict[str, Any]] = []
    message_item: dict[str, Any] = {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "status": status,
        "role": "assistant",
        "content": [],
    }
    text = message.get("content")
    if text:
        message_item["content"].append(
            {"type": "output_text", "text": text, "annotations": []}
        )
    output.append(message_item)

    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function", {})
        output.append(
            {
                "id": f"fc_{uuid.uuid4().hex[:24]}",
                "type": "function_call",
                "status": status,
                "name": function.get("name", ""),
                "arguments": function.get("arguments", "{}"),
                "call_id": tool_call.get("id", ""),
            }
        )

    usage = chat_body.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    result: dict[str, Any] = {
        "id": chat_body.get("id", f"resp_{uuid.uuid4().hex[:24]}"),
        "object": "response",
        "created_at": int(time.time()),
        "model": chat_body.get("model", original_model),
        "status": status,
        "output": output,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }
    if incomplete_details is not None:
        result["incomplete_details"] = incomplete_details
    return result


async def chat_stream_to_responses_stream(
    raw_iterator: AsyncIterator[bytes],
    original_model: str,
) -> AsyncIterator[bytes]:
    """Convert a chat SSE stream into a Responses API SSE stream."""
    state = _ResponsesStreamState(
        response_id=f"resp_{uuid.uuid4().hex[:24]}",
        message_id=f"msg_{uuid.uuid4().hex[:24]}",
        created_at=int(time.time()),
        model=original_model,
    )
    for event in state.start_events():
        yield event
    async for payload in parse_sse_json_stream(raw_iterator, require_done=True):
        for event in state.update(payload):
            yield event
    for event in state.finish_events():
        yield event
    yield b"data: [DONE]\n\n"


@dataclass(slots=True)
class _ResponsesStreamState:
    response_id: str
    message_id: str
    created_at: int
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    text_output_index: int | None = None
    text_parts: list[str] = field(default_factory=list)
    tool_calls: ChatToolCalls = field(default_factory=ChatToolCalls)
    next_output_index: int = 0
    finish_reason: str | None = None
    sequence_number: int = 0

    def start_events(self) -> list[bytes]:
        return [
            self.event(
                event_type,
                response=self.response(status="in_progress", output=[], usage=None),
            )
            for event_type in ("response.created", "response.in_progress")
        ]

    def update(self, payload: dict[str, Any]) -> list[bytes]:
        model = payload.get("model")
        if isinstance(model, str) and model:
            self.model = model
        usage = payload.get("usage") or {}
        if usage.get("prompt_tokens"):
            self.input_tokens = usage["prompt_tokens"]
        if usage.get("completion_tokens"):
            self.output_tokens = usage["completion_tokens"]

        events: list[bytes] = []
        for choice in payload.get("choices", []):
            self.finish_reason = choice.get("finish_reason") or self.finish_reason
            delta = choice.get("delta", {})
            events.extend(self._text_events(delta.get("content")))
            for value in delta.get("tool_calls") or []:
                events.extend(
                    self._tool_events(value, choice_index=chat_choice_index(choice))
                )
        return events

    def finish_events(self) -> list[bytes]:
        status, incomplete_details = _response_status(self.finish_reason)
        events: list[bytes] = []
        output_by_index: dict[int, dict[str, Any]] = {}

        text_events, text_output = self._finish_text(status)
        events.extend(text_events)
        if text_output is not None:
            output_index, item = text_output
            output_by_index[output_index] = item

        for tool_call in self.tool_calls:
            tool_events, output_index, item = self._finish_tool(tool_call, status)
            events.extend(tool_events)
            output_by_index[output_index] = item

        response = self.response(
            status=status,
            output=[output_by_index[index] for index in sorted(output_by_index)],
            usage={
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.input_tokens + self.output_tokens,
            },
        )
        if incomplete_details is not None:
            response["incomplete_details"] = incomplete_details
        terminal_type = (
            "response.completed" if status == "completed" else "response.incomplete"
        )
        events.append(self.event(terminal_type, response=response))
        return events

    def _text_events(self, delta: Any) -> list[bytes]:
        if not delta:
            return []
        if not isinstance(delta, str):
            raise ValueError("Chat content delta must be a string")
        events: list[bytes] = []
        if self.text_output_index is None:
            self.text_output_index = self.allocate_output_index()
            events.extend(
                [
                    self.event(
                        "response.output_item.added",
                        output_index=self.text_output_index,
                        item={
                            "id": self.message_id,
                            "type": "message",
                            "status": "in_progress",
                            "role": "assistant",
                            "content": [],
                        },
                    ),
                    self.event(
                        "response.content_part.added",
                        output_index=self.text_output_index,
                        content_index=0,
                        part={
                            "type": "output_text",
                            "text": "",
                            "annotations": [],
                        },
                    ),
                ]
            )
        self.text_parts.append(delta)
        events.append(
            self.event(
                "response.output_text.delta",
                output_index=self.text_output_index,
                content_index=0,
                delta=delta,
            )
        )
        return events

    def _tool_events(self, value: Any, *, choice_index: int) -> list[bytes]:
        events: list[bytes] = []
        for tool_call in self.tool_calls.update_many(value, choice_index=choice_index):
            if tool_call.target_index is None:
                tool_call.target_index = self.allocate_output_index()
            if not tool_call.announced and tool_call.call_id and tool_call.name:
                events.append(self._announce_tool(tool_call))
            if tool_call.announced:
                arguments_delta = tool_call.take_argument_delta()
                if arguments_delta:
                    events.append(
                        self._tool_arguments_event(tool_call, arguments_delta)
                    )
        return events

    def _finish_text(
        self, status: str
    ) -> tuple[list[bytes], tuple[int, dict[str, Any]] | None]:
        if self.text_output_index is None:
            return [], None
        text = "".join(self.text_parts)
        part = {"type": "output_text", "text": text, "annotations": []}
        item = {
            "id": self.message_id,
            "type": "message",
            "status": status,
            "role": "assistant",
            "content": [part],
        }
        events = [
            self.event(
                "response.output_text.done",
                item_id=self.message_id,
                output_index=self.text_output_index,
                content_index=0,
                text=text,
            ),
            self.event(
                "response.content_part.done",
                item_id=self.message_id,
                output_index=self.text_output_index,
                content_index=0,
                part=part,
            ),
            self.event(
                "response.output_item.done",
                output_index=self.text_output_index,
                item=item,
            ),
        ]
        return events, (self.text_output_index, item)

    def _finish_tool(
        self, tool_call: ChatToolCall, status: str
    ) -> tuple[list[bytes], int, dict[str, Any]]:
        events: list[bytes] = []
        if not tool_call.announced:
            events.append(self._announce_tool(tool_call))
        arguments_delta = tool_call.take_argument_delta()
        if arguments_delta:
            events.append(self._tool_arguments_event(tool_call, arguments_delta))
        output_index = _tool_output_index(tool_call)
        arguments = tool_call.arguments
        item = _tool_item(self, tool_call, status=status)
        events.extend(
            [
                self.event(
                    "response.function_call_arguments.done",
                    item_id=_tool_item_id(self, tool_call),
                    output_index=output_index,
                    arguments=arguments,
                ),
                self.event(
                    "response.output_item.done",
                    output_index=output_index,
                    item=item,
                ),
            ]
        )
        return events, output_index, item

    def _announce_tool(self, tool_call: ChatToolCall) -> bytes:
        event = self.event(
            "response.output_item.added",
            output_index=_tool_output_index(tool_call),
            item=_tool_item(self, tool_call, status="in_progress"),
        )
        tool_call.announced = True
        return event

    def _tool_arguments_event(self, tool_call: ChatToolCall, delta: str) -> bytes:
        return self.event(
            "response.function_call_arguments.delta",
            item_id=_tool_item_id(self, tool_call),
            output_index=_tool_output_index(tool_call),
            delta=delta,
        )

    def allocate_output_index(self) -> int:
        output_index = self.next_output_index
        self.next_output_index += 1
        return output_index

    def event(self, event_type: str, **payload: Any) -> bytes:
        data = {
            "type": event_type,
            "sequence_number": self.sequence_number,
            **payload,
        }
        self.sequence_number += 1
        return format_sse_event(event_type, data)

    def response(
        self,
        *,
        status: str,
        output: list[dict[str, Any]],
        usage: dict[str, int] | None,
    ) -> dict[str, Any]:
        return {
            "id": self.response_id,
            "object": "response",
            "created_at": self.created_at,
            "model": self.model,
            "status": status,
            "output": output,
            "usage": usage,
        }


def _response_status(finish_reason: Any) -> tuple[str, dict[str, str] | None]:
    status = FINISH_REASON_CHAT_TO_RESPONSES.get(finish_reason, "completed")
    if status == "completed":
        return status, None
    reason = (
        "content_filter" if finish_reason == "content_filter" else "max_output_tokens"
    )
    return status, {"reason": reason}


def _tool_item(
    state: _ResponsesStreamState,
    tool_call: ChatToolCall,
    *,
    status: str,
) -> dict[str, Any]:
    if not tool_call.call_id:
        raise ValueError("Chat tool call stream ended without id")
    if not tool_call.name:
        raise ValueError("Chat tool call stream ended without function.name")
    return {
        "id": _tool_item_id(state, tool_call),
        "type": "function_call",
        "status": status,
        "name": tool_call.name,
        "arguments": tool_call.arguments if status != "in_progress" else "",
        "call_id": tool_call.call_id,
    }


def _tool_item_id(state: _ResponsesStreamState, tool_call: ChatToolCall) -> str:
    return f"fc_{state.response_id.removeprefix('resp_')}_{tool_call.index}"


def _tool_output_index(tool_call: ChatToolCall) -> int:
    if tool_call.target_index is None:
        raise ValueError("Chat tool call stream ended without an output index")
    return tool_call.target_index
