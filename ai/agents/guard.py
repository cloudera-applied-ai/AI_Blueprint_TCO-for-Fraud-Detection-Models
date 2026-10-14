"""Llama Guard screening for the agent's inputs and outputs.

A second, small model classifies the user's question before the agent runs and
the agent's answer before it reaches the UI. Llama Guard replies with either
``safe`` or ``unsafe\\nS<n>`` where S<n> is an MLCommons hazard category.

The guard is fail-open on purpose: if the guard model is not served, times out,
or answers in an unexpected shape, the turn proceeds unscreened with a logged
warning rather than taking the app down. Screening is a safeguard around a
fraud-analytics demo, not an authentication boundary — a guard outage must not
look like an app outage.
"""

import os
import logging

from openai import OpenAI

from net import http_client
from llm_client import load_config, _normalize_base_url, _get_caii_api_key, get_llm_client

logger = logging.getLogger(__name__)

# MLCommons hazard taxonomy used by Llama Guard 3 / 4.
HAZARD_CATEGORIES = {
    "S1": "Violent Crimes",
    "S2": "Non-Violent Crimes",
    "S3": "Sex-Related Crimes",
    "S4": "Child Sexual Exploitation",
    "S5": "Defamation",
    "S6": "Specialized Advice",
    "S7": "Privacy",
    "S8": "Intellectual Property",
    "S9": "Indiscriminate Weapons",
    "S10": "Hate",
    "S11": "Suicide & Self-Harm",
    "S12": "Sexual Content",
    "S13": "Elections",
    "S14": "Code Interpreter Abuse",
}

BLOCKED_INPUT_MESSAGE = (
    "This question was blocked by the Llama Guard safety check "
    "({categories}). Ask about transactions, fraud patterns, merchants, or model behaviour instead."
)
BLOCKED_OUTPUT_MESSAGE = (
    "The answer was withheld by the Llama Guard safety check ({categories}). "
    "Try rephrasing the question."
)


class GuardVerdict:
    """Outcome of one screening call."""

    def __init__(self, safe: bool, categories=None, screened=True, error=None):
        self.safe = safe
        self.categories = categories or []
        # False when the guard did not actually run (disabled or unreachable).
        self.screened = screened
        self.error = error

    @property
    def category_names(self) -> str:
        if not self.categories:
            return "unspecified category"
        return ", ".join(HAZARD_CATEGORIES.get(c, c) for c in self.categories)

    def as_dict(self) -> dict:
        return {
            "safe": self.safe,
            "screened": self.screened,
            "categories": self.categories,
            "category_names": self.category_names if self.categories else None,
            "error": self.error,
        }


def guard_settings() -> dict:
    """Resolve guard config: env vars override config.yaml's llm.guard block.

    The guard defaults to the same endpoint/credentials as the chat model, since
    the usual setup serves both from one inference server.
    """
    config = load_config()
    guard_cfg = (config.get("llm") or {}).get("guard") or {}

    enabled_raw = os.environ.get("GUARD_ENABLED")
    if enabled_raw is None:
        enabled = bool(guard_cfg.get("enabled", False))
    else:
        enabled = enabled_raw.strip().lower() in ("1", "true", "yes")

    return {
        "enabled": enabled,
        "model": os.environ.get("GUARD_MODEL", guard_cfg.get("model", "")),
        "endpoint": os.environ.get("GUARD_ENDPOINT", guard_cfg.get("endpoint", "")),
        "api_key": os.environ.get("GUARD_API_KEY", guard_cfg.get("api_key", "")),
        "timeout": float(guard_cfg.get("timeout_seconds", 10)),
    }


def _guard_client(settings):
    """Build the OpenAI-compatible client for the guard model."""
    if settings["endpoint"]:
        api_key = settings["api_key"] or _get_caii_api_key("") or "EMPTY"
        client = OpenAI(
            base_url=_normalize_base_url(settings["endpoint"]),
            api_key=api_key,
            timeout=settings["timeout"],
            http_client=http_client(),
        )
        return client, settings["model"]

    # No dedicated endpoint: reuse the chat provider's connection.
    client, chat_model, _ = get_llm_client()
    client = client.with_options(timeout=settings["timeout"])
    return client, settings["model"] or chat_model


def _parse_verdict(text: str) -> GuardVerdict:
    """Parse a Llama Guard reply: 'safe', or 'unsafe' followed by S-codes."""
    lines = [line.strip() for line in (text or "").strip().splitlines() if line.strip()]
    if not lines:
        return GuardVerdict(safe=True, screened=False, error="empty guard response")

    verdict = lines[0].lower()
    if verdict.startswith("safe"):
        return GuardVerdict(safe=True)
    if verdict.startswith("unsafe"):
        codes = []
        for line in lines[1:]:
            codes.extend(c.strip().upper() for c in line.split(",") if c.strip())
        return GuardVerdict(safe=False, categories=codes)

    return GuardVerdict(safe=True, screened=False, error=f"unrecognized guard response: {text[:80]!r}")


def _screen(messages) -> GuardVerdict:
    settings = guard_settings()
    if not settings["enabled"]:
        return GuardVerdict(safe=True, screened=False)

    try:
        client, model = _guard_client(settings)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            # Guard replies are two tokens' worth; temperature 0 keeps them stable.
            temperature=0,
            max_tokens=16,
        )
        return _parse_verdict(response.choices[0].message.content)
    except Exception as exc:
        logger.warning("Llama Guard screening unavailable, allowing turn: %s", exc)
        return GuardVerdict(safe=True, screened=False, error=str(exc))


def screen_input(user_message: str) -> GuardVerdict:
    """Screen the user's question before the agent sees it."""
    return _screen([{"role": "user", "content": user_message}])


def screen_output(user_message: str, assistant_message: str) -> GuardVerdict:
    """Screen the agent's answer in the context of the question that prompted it."""
    return _screen([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_message},
    ])
