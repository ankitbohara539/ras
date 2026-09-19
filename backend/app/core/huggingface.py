"""Our own model, not a third-party AI product's API.

Used only by app.services.summary_service, for the dashboard's AI briefing.
An open-weight instruct model, served through Hugging Face's router
(router.huggingface.co) -- an OpenAI-compatible chat-completions endpoint
that routes to whichever inference provider currently hosts the chosen
model, rather than a single vendor's proprietary API. Swap `settings.
huggingface_model` for a different open model at any time; nothing else
here changes.

Free access token from huggingface.co/settings/tokens. The free monthly
credit is small; specific model+provider pairings are priced at $0 and
change over time -- see huggingface_model's own comment in config.py.

Needs HUGGINGFACE_API_KEY. Without it, generate_text / stream_text raise
AINotConfigured and the caller falls back to a templated summary built from
the same numbers -- the feature degrades, it never breaks.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

from app.core.config import Settings, get_settings


class AINotConfigured(Exception):
    pass


class AIError(Exception):
    """The model could not produce text. `status_code` is the HTTP status, if any."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _configured_settings() -> Settings:
    settings = get_settings()
    if not settings.huggingface_api_key:
        raise AINotConfigured(
            "AI summaries are not set up: add HUGGINGFACE_API_KEY to backend/.env "
            "(free access token from huggingface.co/settings/tokens)."
        )
    return settings


def _request(
    settings: Settings,
    prompt: str,
    system: str | None,
    max_output_tokens: int,
    temperature: float,
    stream: bool,
):
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    return {
        "url": f"{settings.huggingface_api_url.rstrip('/')}/chat/completions",
        "headers": {
            "Authorization": f"Bearer {settings.huggingface_api_key}",
            "Content-Type": "application/json",
        },
        "json": {
            "model": settings.huggingface_model,
            "messages": messages,
            "max_tokens": max_output_tokens,
            "temperature": temperature,
            "stream": stream,
            # Reasoning models (Qwen3) otherwise spend the budget on hidden
            # thinking and can return empty text. Ignored by models without it.
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "timeout": settings.huggingface_timeout_s,
    }


def _error_for(status_code: int, payload: object) -> AIError:
    message = None
    if isinstance(payload, dict):
        error = payload.get("error")
        message = error.get("message") if isinstance(error, dict) else error
    if status_code == 503:
        # A cold model instance spinning up. Worth its own message: this is
        # the one failure that often succeeds if simply tried again.
        return AIError(message or "The model is still starting up.", status_code)
    if status_code in (401, 402, 429):
        return AIError(
            message
            or f"Hugging Face refused the request ({status_code}) -- "
            "check the token and the model's current free-tier availability.",
            status_code,
        )
    return AIError(message or f"Hugging Face answered {status_code}.", status_code)


def generate_text(
    prompt: str,
    *,
    system: str | None = None,
    max_output_tokens: int = 400,
    temperature: float = 0.6,
) -> str:
    settings = _configured_settings()
    try:
        response = httpx.post(
            **_request(settings, prompt, system, max_output_tokens, temperature, stream=False)
        )
    except httpx.HTTPError as exc:
        raise AIError(f"Could not reach Hugging Face: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise AIError(f"Hugging Face answered {response.status_code} with no JSON body.") from exc

    if response.status_code != 200:
        raise _error_for(response.status_code, payload)

    choices = payload.get("choices") or [] if isinstance(payload, dict) else []
    if not choices:
        raise AIError("Hugging Face returned no choices.")

    text = ((choices[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise AIError("Hugging Face returned empty text.")
    return text


def stream_text(
    prompt: str,
    *,
    system: str | None = None,
    max_output_tokens: int = 400,
    temperature: float = 0.6,
) -> Iterator[str]:
    """The model's answer piece by piece, as it writes it (server-sent events).

    A generator: nothing is sent until the first piece is asked for, and
    closing it early closes the upstream connection too. Only the visible
    answer is yielded -- any reasoning deltas a provider sends are skipped.
    """
    settings = _configured_settings()
    request = _request(settings, prompt, system, max_output_tokens, temperature, stream=True)
    try:
        with httpx.stream("POST", **request) as response:
            if response.status_code != 200:
                response.read()
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
                raise _error_for(response.status_code, payload)

            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    return
                try:
                    chunk = json.loads(data)
                except ValueError:
                    continue
                if isinstance(chunk, dict) and chunk.get("error"):
                    raise _error_for(500, chunk)
                choices = chunk.get("choices") or [] if isinstance(chunk, dict) else []
                if not choices:
                    continue
                piece = (choices[0].get("delta") or {}).get("content")
                if piece:
                    yield piece
    except httpx.HTTPError as exc:
        raise AIError(f"Could not reach Hugging Face: {exc}") from exc
