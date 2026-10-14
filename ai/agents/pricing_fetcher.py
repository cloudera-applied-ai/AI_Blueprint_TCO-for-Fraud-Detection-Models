"""Fetch live LLM pricing from LiteLLM's community-maintained price list.

Neither Anthropic nor OpenAI publishes pricing via a stable JSON API, but
LiteLLM maintains a constantly-updated JSON file tracking input/output prices,
context windows, and model metadata for every major provider at:

  https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json

This module fetches that file, filters to current Anthropic/OpenAI chat
models, caches the result to disk with a 24h TTL, and falls back to the
hardcoded pricing table in ``cost_estimator.PROVIDER_PRICING`` if the fetch
fails.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

try:
    PROJECT_ROOT = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
except NameError:
    PROJECT_ROOT = os.getcwd()

CACHE_PATH = os.path.join(PROJECT_ROOT, "data", "pricing_cache.json")
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours

SOURCE_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)

# When picking the headline default for each provider we try these prefixes
# in order and use the newest alphabetical match.
DEFAULT_ANTHROPIC_PREFERENCE = [
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
    "claude-3-7-sonnet",
    "claude-3-5-sonnet",
]
DEFAULT_OPENAI_PREFERENCE = [
    "gpt-4o",
    "gpt-4.1",
    "gpt-4-turbo",
]


def _humanize(model_id: str) -> str:
    """Turn a LiteLLM model id into a readable label."""
    base = re.sub(r"-20\d{6}$", "", model_id)   # strip trailing -YYYYMMDD
    base = re.sub(r"-latest$", "", base)

    if base.startswith("claude-"):
        parts = base.split("-")
        # claude-opus-4-5 -> Claude Opus 4.5
        # claude-3-5-sonnet -> Claude 3.5 Sonnet
        if len(parts) >= 2:
            tail = parts[1:]
            # Detect family word (opus/sonnet/haiku/instant) anywhere
            families = {"opus", "sonnet", "haiku", "instant"}
            family = next((p for p in tail if p.lower() in families), None)
            numbers = [p for p in tail if p not in families and re.match(r"^\d", p)]
            if family and numbers:
                return f"Claude {family.title()} {'.'.join(numbers)}"
            return "Claude " + " ".join(p.title() for p in tail)

    if base.startswith("gpt-"):
        rest = base[4:]
        return f"GPT-{rest}"

    if re.match(r"^o\d", base):
        return base.replace("-", " ")

    return base


def _strip_date_suffix(model_id: str) -> str:
    base = re.sub(r"-20\d{6}$", "", model_id)
    base = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", base)
    return base


def _dedupe_dated_variants(models: dict) -> dict:
    """Collapse date-stamped aliases into their unstamped form.

    If both ``gpt-4o`` and ``gpt-4o-2024-11-20`` exist with identical pricing,
    keep only ``gpt-4o``. If only the date-stamped version exists, keep it.
    """
    # Group by stripped base id
    groups: dict[str, list[str]] = {}
    for mid in models:
        base = _strip_date_suffix(mid)
        groups.setdefault(base, []).append(mid)

    result: dict = {}
    for base, variants in groups.items():
        if base in models:
            # Base (unstamped) exists — use it, drop date-stamped variants that
            # match its pricing exactly.
            result[base] = models[base]
            base_rates = (models[base]["input"], models[base]["output"])
            for v in variants:
                if v == base:
                    continue
                v_rates = (models[v]["input"], models[v]["output"])
                if v_rates != base_rates:
                    # Different pricing — keep as a distinct entry.
                    result[v] = models[v]
        else:
            # No unstamped alias — keep the newest date-stamped variant only.
            newest = sorted(variants, reverse=True)[0]
            result[newest] = models[newest]
    return result


def _pick_default(models: dict, prefixes: list[str]) -> str:
    if not models:
        return ""
    # Try exact match first
    for p in prefixes:
        if p in models:
            return p
    # Then prefix match — pick the highest-sorted (often = newest date stamp)
    for p in prefixes:
        matches = sorted(
            (mid for mid in models if mid.startswith(p)),
            reverse=True,
        )
        if matches:
            return matches[0]
    # Fallback: first alphabetical
    return sorted(models.keys())[0]


def _normalize_from_litellm(raw: dict) -> dict:
    """Convert LiteLLM's raw schema into our provider pricing shape."""
    anthropic_models: dict = {}
    openai_models: dict = {}

    for model_id, meta in raw.items():
        if not isinstance(meta, dict):
            continue
        if meta.get("mode") != "chat":
            continue
        provider = meta.get("litellm_provider")
        if provider not in ("anthropic", "openai"):
            continue
        # Skip prefixed aliases like "openai/gpt-4o" or "anthropic/claude-..."
        if "/" in model_id:
            continue
        # Skip fine-tuned model price entries — not relevant for a baseline
        # cost comparison and they bloat the dropdown.
        if model_id.startswith("ft:"):
            continue
        # Skip obviously old / deprecated lineages
        if model_id.startswith(
            ("claude-2", "claude-instant", "text-", "davinci", "curie", "babbage", "ada")
        ):
            continue
        # Skip non-text chat variants that use mode=chat but aren't useful here
        if any(
            tag in model_id
            for tag in ("realtime", "audio", "tts", "whisper", "search-preview", "transcribe")
        ):
            continue
        input_per_token = meta.get("input_cost_per_token")
        output_per_token = meta.get("output_cost_per_token")
        if input_per_token is None or output_per_token is None:
            continue
        entry = {
            "input": round(float(input_per_token) * 1_000_000, 6),
            "output": round(float(output_per_token) * 1_000_000, 6),
            "label": _humanize(model_id),
        }
        if provider == "anthropic":
            anthropic_models[model_id] = entry
        else:
            openai_models[model_id] = entry

    anthropic_models = _dedupe_dated_variants(anthropic_models)
    openai_models = _dedupe_dated_variants(openai_models)

    # Sort models by id descending so newest versions bubble to the top
    anthropic_models = dict(sorted(anthropic_models.items(), reverse=True))
    openai_models = dict(sorted(openai_models.items(), reverse=True))

    return {
        "anthropic": {
            "default": _pick_default(anthropic_models, DEFAULT_ANTHROPIC_PREFERENCE),
            "models": anthropic_models,
        },
        "openai": {
            "default": _pick_default(openai_models, DEFAULT_OPENAI_PREFERENCE),
            "models": openai_models,
        },
    }


def _read_cache() -> dict | None:
    if not os.path.isfile(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(payload: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(payload, f, indent=2)
    except OSError:
        pass


def _fetch_upstream(timeout_seconds: float = 10.0) -> dict:
    req = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "fraud-detection-demo/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        raw = json.load(resp)
    return _normalize_from_litellm(raw)


def fetch_live_pricing(force_refresh: bool = False) -> dict:
    """Return the cached or freshly-fetched pricing payload.

    Shape:
    {
      "source":      "litellm" | "fallback",
      "source_url":  "https://..." | None,
      "fetched_at":  <unix timestamp>,
      "stale":       bool (optional — true if network fetch failed but we
                     still have a previous cached copy),
      "error":       str (optional),
      "pricing":     {"anthropic": {"default": ..., "models": {...}},
                      "openai":    {"default": ..., "models": {...}}} | None
    }
    """
    now = time.time()
    cache = None if force_refresh else _read_cache()

    if cache and cache.get("pricing"):
        age = now - cache.get("fetched_at", 0)
        if age < CACHE_TTL_SECONDS:
            return cache

    try:
        pricing = _fetch_upstream()
        payload = {
            "source": "litellm",
            "source_url": SOURCE_URL,
            "fetched_at": now,
            "pricing": pricing,
        }
        _write_cache(payload)
        return payload
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
        if cache and cache.get("pricing"):
            cache["stale"] = True
            cache["error"] = str(e)
            return cache
        return {
            "source": "fallback",
            "source_url": None,
            "fetched_at": 0,
            "error": str(e),
            "pricing": None,
        }
