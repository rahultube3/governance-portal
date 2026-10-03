import json
from collections.abc import Iterator
from typing import Any

import anthropic
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from flask.typing import ResponseReturnValue

from portal.knowledge import SYSTEM_PROMPT

# Chat with the governance documents (streams SSE).
bp = Blueprint("chat", __name__)

CHAT_MAX_TURNS = 40
CHAT_MAX_CHARS = 4000


def validate_chat_messages(raw: object) -> tuple[list[dict[str, str]] | None, str | None]:
    if not isinstance(raw, list) or not raw:
        return None, "messages must be a non-empty list"
    if len(raw) > CHAT_MAX_TURNS:
        raw = raw[-CHAT_MAX_TURNS:]
    out: list[dict[str, str]] = []
    for m in raw:
        if not isinstance(m, dict):
            return None, "each message must be an object"
        role, content = m.get("role"), m.get("content")
        if role not in ("user", "assistant"):
            return None, "role must be 'user' or 'assistant'"
        if not isinstance(content, str) or not content.strip():
            return None, "content must be a non-empty string"
        out.append({"role": role, "content": content[:CHAT_MAX_CHARS]})
    if out[0]["role"] != "user":
        return None, "first message must be from the user"
    return out, None


def sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@bp.post("/chat")
def chat() -> ResponseReturnValue:
    data = request.get_json(force=True) or {}
    messages, err = validate_chat_messages(data.get("messages"))
    if err:
        return jsonify({"error": err}), 400

    client = anthropic.Anthropic()
    model = current_app.config["CHAT_MODEL"]

    def generate() -> Iterator[str]:
        try:
            with client.messages.stream(
                model=model,
                max_tokens=2048,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield sse({"text": text})
            yield sse({"done": True})
        # SDK raises TypeError when no api_key/auth_token/credentials resolve
        except TypeError:
            yield sse({"error": "Chat is not configured. Set ANTHROPIC_API_KEY on the API server."})
        except anthropic.AuthenticationError:
            yield sse({"error": "Chat is misconfigured: the API key was rejected."})
        except anthropic.APIStatusError as e:
            yield sse({"error": f"Assistant unavailable ({e.status_code}). Try again shortly."})
        except anthropic.APIConnectionError:
            yield sse({"error": "Could not reach the assistant. Check the API server's network."})
        except Exception:
            yield sse({"error": "Assistant failed unexpectedly. Try again."})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
