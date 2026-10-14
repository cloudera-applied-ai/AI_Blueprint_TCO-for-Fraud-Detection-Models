"""Mask PII in tool results before they are sent to the LLM.

Cloudera Data Governance policy: sensitive fields are redacted at the
prompt boundary. The UI continues to display unmasked values for operators;
only the LLM-facing payload is transformed.
"""

from typing import Any

PII_FIELDS = frozenset({
    "card_id",
    "card_number",
    "email",
    "phone",
    "phone_number",
    "ssn",
    "tax_id",
    "address",
    "street_address",
})

MASKED_TOKEN = "XXX-REDACTED"


def _mask_card_id(value: Any) -> str:
    """Preserve last 2 chars so the LLM can distinguish cards without seeing the full id."""
    s = str(value)
    if len(s) <= 4:
        return "card_****"
    return f"card_****{s[-2:]}"


def _mask_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in ("card_id", "card_number"):
        return _mask_card_id(value)
    return MASKED_TOKEN


def mask_pii(obj: Any) -> Any:
    """Recursively mask PII fields in a dict/list structure.

    Returns a new structure; the input is not modified.
    """
    if isinstance(obj, dict):
        return {
            k: (_mask_value(k, v) if k in PII_FIELDS else mask_pii(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [mask_pii(item) for item in obj]
    return obj


def mask_for_llm(result: Any) -> Any:
    """Wrap a tool result with a governance notice and masked payload.

    The notice is visible to the LLM so it can cite the policy when asked
    why fields are redacted.
    """
    masked = mask_pii(result)
    if isinstance(masked, dict):
        masked.setdefault(
            "_governance",
            "PII masked per Cloudera Data Governance policy "
            "(card_id, email, phone, ssn redacted before LLM).",
        )
    return masked
