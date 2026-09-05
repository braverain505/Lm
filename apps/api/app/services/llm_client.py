"""Minimal Groq (OpenAI-compatible) client for the AI generation engines.

Every call is best-effort by design: a missing key, network failure, timeout,
or non-2xx response all return ``None`` so callers fall back to the
deterministic template engines (which remain the offline default). When a call
does succeed the result carries the real model + token usage so metering stays
accurate regardless of which provider produced the text.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_TOKENS = 2400


@dataclass
class LlmResult:
    """A successful chat-completion response."""

    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int


def _enabled() -> bool:
    return bool(settings.groq_api_key)


def _request(
    *,
    system: str,
    user: str,
    json_mode: bool,
    temperature: float,
    max_tokens: int,
) -> LlmResult | None:
    if not _enabled():
        return None

    url = f"{settings.groq_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=settings.groq_timeout_seconds or DEFAULT_TIMEOUT_SECONDS) as client:
            resp = client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        logger.warning("Groq request timed out (model=%s)", settings.groq_model)
        return None
    except httpx.HTTPError as exc:
        logger.warning("Groq request failed: %s", exc)
        return None

    latency_ms = int((time.perf_counter() - started) * 1000)

    if resp.status_code != 200:
        # Don't log the body — it can echo prompt content back.
        logger.warning(
            "Groq returned HTTP %s (model=%s)", resp.status_code, settings.groq_model
        )
        return None

    try:
        data = resp.json()
        text = (data["choices"][0]["message"]["content"] or "").strip()
    except (ValueError, KeyError, IndexError, TypeError):
        logger.warning("Groq response was not parseable (model=%s)", settings.groq_model)
        return None
    if not text:
        return None

    usage = data.get("usage") or {}
    return LlmResult(
        text=text,
        model=data.get("model") or settings.groq_model,
        tokens_in=int(usage.get("prompt_tokens") or 0),
        tokens_out=int(usage.get("completion_tokens") or 0),
        latency_ms=latency_ms,
    )


def complete_text(
    *,
    system: str,
    user: str,
    temperature: float = 0.3,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LlmResult | None:
    """Free-text completion (result comments). Returns None on any failure."""
    return _request(
        system=system,
        user=user,
        json_mode=False,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def complete_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> tuple[dict | None, LlmResult | None]:
    """JSON-object completion (lesson plans, question banks).

    Returns ``(parsed_object, result)``; ``parsed_object`` is None when the
    model did not return parseable JSON. The caller validates shape — a valid
    parse with the wrong keys still falls back.
    """
    result = _request(
        system=system,
        user=user,
        json_mode=True,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if result is None:
        return None, None
    try:
        return json.loads(result.text), result
    except json.JSONDecodeError:
        logger.warning("Groq returned invalid JSON for a structured request")
        return None, result
