"""ReAct-style tool-calling agent for fraud detection."""

import os
import re
import sys
import json

try:
    _dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _dir = os.path.join(os.getcwd(), "ai", "agents")
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from llm_client import chat_completion
from prompts import SYSTEM_PROMPT
from tool_registry import TOOLS
from pii_mask import mask_for_llm
from tools.query_transactions import query_transactions
from tools.score_transaction import score_transaction
from tools.explain_prediction import explain_prediction
from tools.risk_dashboard import get_risk_dashboard
from tools.alert_patterns import detect_alert_patterns
from tools.threshold_analysis import get_threshold_analysis
from tools.drift_monitor import (
    compute_drift_report, compute_performance_over_time, compute_score_distribution,
)
from tools.trace_fraud_network import trace_fraud_network
from tools.merchant_investigation import investigate_merchant
from tools.retrain import generate_training_data, retrain_model

MAX_TOOL_ROUNDS = 5


def _analyze_threshold(sample_size: int = 5000):
    capped = max(100, min(int(sample_size or 5000), 10000))
    return get_threshold_analysis(sample_size=capped)


def _monitor_drift(reference_year: int = 2018, current_year: int = 2020,
                   report_type: str = "feature_drift"):
    ref = int(reference_year or 2018)
    cur = int(current_year or 2020)
    if report_type == "performance_over_time":
        return compute_performance_over_time()
    if report_type == "score_distribution":
        return compute_score_distribution(reference_year=ref, current_year=cur)
    return compute_drift_report(reference_year=ref, current_year=cur)


TOOL_FUNCTIONS = {
    "query_transactions": query_transactions,
    "score_transaction": score_transaction,
    "explain_prediction": explain_prediction,
    "get_risk_dashboard": get_risk_dashboard,
    "detect_alert_patterns": detect_alert_patterns,
    "analyze_threshold": _analyze_threshold,
    "monitor_drift": _monitor_drift,
    "trace_fraud_network": trace_fraud_network,
    "investigate_merchant": investigate_merchant,
    "generate_training_data": generate_training_data,
    "retrain_model": retrain_model,
}

# Build a lookup from tool name → {param_name: param_type} from the schema
_TOOL_PARAM_TYPES = {}
for _tool_def in TOOLS:
    _fname = _tool_def["function"]["name"]
    _props = _tool_def["function"]["parameters"].get("properties", {})
    _TOOL_PARAM_TYPES[_fname] = {k: v.get("type") for k, v in _props.items()}


def _sanitize_args(func_name, args):
    """Validate and coerce tool arguments against the schema.

    Small LLMs sometimes hallucinate dict-like strings or pass tool names
    as parameter values.  Catch those before they hit the real tool.
    Returns (sanitized_args, error_string_or_None).
    """
    schema = _TOOL_PARAM_TYPES.get(func_name)
    if not schema or not isinstance(args, dict):
        return args, None

    sanitized = {}
    for key, value in args.items():
        expected = schema.get(key)
        if expected is None:
            # Unknown param — drop it so the tool doesn't get unexpected kwargs
            continue

        if expected == "string" and isinstance(value, str):
            stripped = value.strip()
            # Reject dict-like / JSON-like strings that aren't real values
            if stripped.startswith("{") or stripped.startswith("["):
                return None, (
                    f"Bad value for '{key}': looks like a dict/list, not a real "
                    f"string. Read the result of a previous tool call and pass "
                    f"the actual value (e.g. a real merchant_name from "
                    f"get_risk_dashboard)."
                )
            # Reject values that look like a tool name or function call
            # Check against all registered tool names
            bare = stripped.split("(")[0]  # "get_risk_dashboard(...)" → "get_risk_dashboard"
            if bare in TOOL_FUNCTIONS:
                return None, (
                    f"Bad value for '{key}': '{stripped}' is a tool name, "
                    f"not a real value. Call {bare}() as a tool first, "
                    f"then use a value from its result."
                )

        if expected == "integer":
            if isinstance(value, str) and value.strip().isdigit():
                sanitized[key] = int(value.strip())
                continue
            if not isinstance(value, (int, float)):
                return None, (
                    f"Bad value for '{key}': expected an integer, got "
                    f"{type(value).__name__}."
                )
            sanitized[key] = int(value)
            continue

        if expected == "boolean" and isinstance(value, str):
            sanitized[key] = value.strip().lower() in ("true", "1", "yes")
            continue

        sanitized[key] = value

    return sanitized, None


# ---------------------------------------------------------------------------
# Auto-correction: when the LLM passes a tool name as a parameter value,
# look up the most recent tool result and extract the real value.
# ---------------------------------------------------------------------------

def _deep_find_first(obj, key):
    """Find the first occurrence of *key* in a nested dict/list structure."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _deep_find_first(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _deep_find_first(item, key)
            if found is not None:
                return found
    return None


# When the LLM passes a tool name as a value and we have no prior result
# to pull from, auto-execute the prerequisite tool with these args.
_PREREQUISITE_ARGS = {
    ("merchant_name", "get_risk_dashboard"): {"group_by": "merchant"},
    ("user_id", "get_risk_dashboard"):       {"group_by": "user"},
}

# Fallback by param key alone, used when the bad value is a placeholder
# like "<top fraud merchant name>" (not a tool name we can key off of).
_PREREQUISITE_BY_KEY = {
    "merchant_name":  ("get_risk_dashboard", {"group_by": "merchant"}),
    "user_id":        ("get_risk_dashboard", {"group_by": "user"}),
    "transaction_id": ("query_transactions",
                      {"is_fraud": True, "limit": 1, "order_by": "amount_desc"}),
}

# Matches whole-string placeholders like "<merchant>", "<top fraud merchant name>",
# "{user_id}". Not used for values that merely contain angle brackets.
_PLACEHOLDER_RE = re.compile(r"^\s*[<{][^<>{}]*[>}]\s*$")


def _auto_correct_args(func_name, args, messages, tool_calls_log=None):
    """Substitute real values for LLM-invented tool names, placeholders,
    and non-numeric ints in string/integer parameters.

    Looks through prior tool results for the param key, then falls back
    to auto-executing a prerequisite tool (see _PREREQUISITE_BY_KEY).
    Returns the (possibly modified) args dict.
    """
    schema = _TOOL_PARAM_TYPES.get(func_name)
    if not schema or not isinstance(args, dict):
        return args

    for key, value in list(args.items()):
        expected = schema.get(key)
        if expected not in ("string", "integer"):
            continue
        if not isinstance(value, str):
            continue

        stripped = value.strip()
        bare = stripped.split("(")[0]
        is_tool_name = bare in TOOL_FUNCTIONS
        is_placeholder = bool(_PLACEHOLDER_RE.match(stripped))
        # A string value for an integer param that isn't a digit string is
        # almost certainly a placeholder the LLM invented.
        is_bad_int = expected == "integer" and not stripped.isdigit()

        if not (is_tool_name or is_placeholder or is_bad_int):
            continue

        # Search backwards through tool results for a real value
        replacement = None
        for msg in reversed(messages):
            if msg.get("role") != "tool":
                continue
            try:
                result = json.loads(msg.get("content", ""))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            if not isinstance(result, dict):
                continue
            replacement = _deep_find_first(result, key)
            if replacement is not None:
                break

        # No prior result — auto-execute a prerequisite tool
        if replacement is None:
            prereq = None
            if is_tool_name:
                pargs = _PREREQUISITE_ARGS.get((key, bare))
                if pargs is not None:
                    prereq = (bare, pargs)
            if prereq is None:
                prereq = _PREREQUISITE_BY_KEY.get(key)
            if prereq:
                tool, prereq_args = prereq
                if tool in TOOL_FUNCTIONS:
                    try:
                        prereq_result = TOOL_FUNCTIONS[tool](**prereq_args)
                        replacement = _deep_find_first(prereq_result, key)
                        if tool_calls_log is not None:
                            tool_calls_log.append({
                                "tool": tool,
                                "args": prereq_args,
                                "result_summary": _summarize_result(prereq_result),
                            })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": f"auto_{tool}",
                            "content": json.dumps(
                                mask_for_llm(prereq_result), default=str
                            ),
                        })
                    except Exception:
                        pass

        if replacement is not None:
            args[key] = replacement

    return args


# ---------------------------------------------------------------------------
# Hallucination detection & cleanup
# ---------------------------------------------------------------------------
# Small LLMs sometimes write fake tool calls or fake JSON results in their
# text instead of using the tool-calling API.  We detect several variants
# and either retry (once) or strip the fake content from the final response.

_HALLUCINATION_PATTERNS = None  # built lazily


def _get_hallucination_patterns():
    global _HALLUCINATION_PATTERNS
    if _HALLUCINATION_PATTERNS is None:
        names = "|".join(re.escape(n) for n in TOOL_FUNCTIONS)
        _HALLUCINATION_PATTERNS = [
            # "Running/Calling/Let me call/I'll call tool_name" with ( or "with"
            re.compile(
                rf"(?:Running|Calling|calling|running|Let me call|I'll call"
                rf"|I will call|I need to call|I'll use|Let me use)"
                rf"\s+(?:`)?({names})(?:`)?(?:\s*\(|\s+with\b)",
                re.IGNORECASE,
            ),
            # "I'll/I will [now] call tool_name" at end of sentence
            re.compile(
                rf"I(?:'ll| will)\s+(?:now\s+)?(?:call|use|run)\s+(?:`)?({names})(?:`)?",
                re.IGNORECASE,
            ),
            # Raw JSON tool calls: {"name": "tool_name", ...}
            re.compile(
                rf'\{{\s*"name"\s*:\s*"({names})"',
            ),
            # Fake JSON result dumps: multi-line JSON objects with quoted keys
            re.compile(
                r'\{\s*\n\s*"[a-z_]+":\s*[\[\{"\d]',
            ),
        ]
    return _HALLUCINATION_PATTERNS


def _contains_hallucinated_tool_calls(text):
    """Return True if the assistant text narrates fake tool calls or results."""
    if not text:
        return False
    return any(p.search(text) for p in _get_hallucination_patterns())


def _strip_hallucinated_json(text):
    """Remove fake JSON blocks from a response, keeping only the narrative."""
    lines = text.split("\n")
    result = []
    depth = 0
    in_json = False
    in_fence = False

    for line in lines:
        stripped = line.strip()

        # Handle code fences wrapping JSON
        if stripped.startswith("```"):
            if not in_fence and in_json:
                continue
            if not in_fence:
                in_fence = True
                continue
            in_fence = False
            in_json = False
            depth = 0
            continue

        if not in_json:
            if stripped.startswith("{") or stripped.startswith("["):
                in_json = True
                depth = (stripped.count("{") + stripped.count("[")
                         - stripped.count("}") - stripped.count("]"))
                if depth <= 0:
                    in_json = False
                continue
            result.append(line)
        else:
            depth += (stripped.count("{") + stripped.count("[")
                      - stripped.count("}") - stripped.count("]"))
            if depth <= 0:
                in_json = False
            continue

    cleaned = "\n".join(result)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


# Reasoning-channel markers leak into content when the serving stack's chat
# template doesn't fully parse a model's thinking tokens (seen with gemma4 on
# llama-swap: replies after tool results start with "<|channel>thought\n<channel|>").
_THINK_BLOCK_RE = re.compile(r"<think>.*?(?:</think>|\Z)", re.IGNORECASE | re.DOTALL)
_CHANNEL_MARKER_RE = re.compile(
    r"<\|?/?(?:channel|message|start|end|return)[^<>]*?\|?>"
    r"\s*(?:(?:thought|thinking|analysis|commentary|final)\b:?\s*)?",
    re.IGNORECASE,
)


def _strip_reasoning_markers(text):
    """Remove leaked thinking blocks and channel-marker tokens from a reply."""
    if not text or "<" not in text:
        return text
    cleaned = _THINK_BLOCK_RE.sub("", text)
    cleaned = _CHANNEL_MARKER_RE.sub("", cleaned)
    return cleaned.strip()


_HALLUCINATION_CORRECTION = (
    "STOP. You wrote fake data in your response instead of calling tools. "
    "Do NOT write JSON in your response. You MUST use the function-calling "
    "API. Call the tool you need now — for example, to get top merchants, "
    "call get_risk_dashboard with group_by='merchant'."
)


def _add_usage(totals, response):
    """Accumulate prompt/completion/total tokens from an OpenAI-style response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    totals["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
    totals["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
    totals["total_tokens"] += getattr(usage, "total_tokens", 0) or 0


def run_agent(user_message, conversation_history=None):
    if conversation_history is None:
        conversation_history = []

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    tool_calls_log = []
    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    hallucination_retries = 0

    for round_num in range(MAX_TOOL_ROUNDS):
        response = chat_completion(messages, tools=TOOLS)
        _add_usage(usage_totals, response)
        choice = response.choices[0]

        if choice.finish_reason == "stop" or not choice.message.tool_calls:
            assistant_msg = _strip_reasoning_markers(choice.message.content or "")

            if _contains_hallucinated_tool_calls(assistant_msg):
                if (hallucination_retries < 1
                        and round_num < MAX_TOOL_ROUNDS - 1):
                    # First offense: correct the LLM and retry once
                    hallucination_retries += 1
                    messages.append({"role": "assistant", "content": assistant_msg})
                    messages.append({"role": "user", "content": _HALLUCINATION_CORRECTION})
                    continue
                # Gave it a chance — strip the fake JSON and return what's left
                assistant_msg = _strip_hallucinated_json(assistant_msg)
                if not assistant_msg:
                    assistant_msg = (
                        "I wasn't able to retrieve the data. Please try a "
                        "more specific question, for example:\n"
                        "- \"Show the risk dashboard grouped by merchant\"\n"
                        "- \"Query fraud transactions for user 1977\"\n"
                        "- \"Trace fraud network from merchant X\""
                    )

            messages.append({"role": "assistant", "content": assistant_msg})
            updated_history = [m for m in messages if m["role"] != "system"]
            return {
                "response": assistant_msg,
                "tool_calls": tool_calls_log,
                "messages": updated_history,
                "usage": usage_totals,
            }

        assistant_message = {
            "role": "assistant",
            "content": choice.message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in choice.message.tool_calls
            ],
        }
        messages.append(assistant_message)

        for tool_call in choice.message.tool_calls:
            func_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            tool_func = TOOL_FUNCTIONS.get(func_name)
            if tool_func is None:
                result = {"error": f"Unknown tool: {func_name}"}
            else:
                # Auto-correct tool-name-as-value from prior results
                args = _auto_correct_args(func_name, args, messages, tool_calls_log)
                sanitized, sanitize_err = _sanitize_args(func_name, args)
                if sanitize_err:
                    result = {"error": sanitize_err}
                else:
                    args = sanitized
                    try:
                        result = tool_func(**args)
                    except Exception as e:
                        result = {"error": str(e)}

            tool_calls_log.append({
                "tool": func_name,
                "args": args or {},
                "result_summary": _summarize_result(result),
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(mask_for_llm(result), default=str),
            })

    response = chat_completion(messages)
    _add_usage(usage_totals, response)
    final_msg = _strip_reasoning_markers(response.choices[0].message.content or "")
    final_msg = final_msg or "I've completed my analysis."
    messages.append({"role": "assistant", "content": final_msg})

    updated_history = [m for m in messages if m["role"] != "system"]
    return {
        "response": final_msg,
        "tool_calls": tool_calls_log,
        "messages": updated_history,
        "usage": usage_totals,
    }


def _summarize_result(result):
    if isinstance(result, dict):
        if "error" in result:
            return f"Error: {result['error']}"
        if "transactions" in result:
            return f"{result.get('showing', 0)} of {result.get('total_matching', 0)} transactions"
        if "fraud_score" in result:
            return f"Score: {result['fraud_score']}, Risk: {result.get('risk_level', 'N/A')}"
        if "narrative" in result:
            return result["narrative"][:100]
        if "merchant_name" in result and "kpis" in result and "trace" in result:
            kpis = result.get("kpis", {})
            trace = result.get("trace", {}) or {}
            tsum = trace.get("summary", {}) if isinstance(trace, dict) else {}
            return (
                f"Investigation of {result['merchant_name']}: "
                f"{kpis.get('fraud_transactions', 0)} fraud / "
                f"{kpis.get('total_transactions', 0)} txns, "
                f"{tsum.get('counterparties_returned', 0)} customers affected"
            )
        if "kpis" in result:
            kpis = result["kpis"]
            return f"Total: {kpis.get('total_transactions', 0):,}, Fraud: {kpis.get('total_fraud', 0):,}"
        if "alerts" in result:
            return f"{len(result['alerts'])} alerts found"
        if "curve" in result and "distribution" in result:
            pts = result["curve"]
            best = max(pts, key=lambda p: p["f1"]) if pts else None
            if best:
                return (
                    f"Threshold sweep ({result.get('sample_size', 0)} samples); "
                    f"best F1={best['f1']} at t={best['threshold']}"
                )
            return f"Threshold sweep over {result.get('sample_size', 0)} samples"
        if "features" in result and "summary" in result and "overall_status" in result.get("summary", {}):
            s = result["summary"]
            return (
                f"Drift {s['overall_status']}: {s['significant']} significant, "
                f"{s['moderate']} moderate, {s['no_drift']} stable"
            )
        if "periods" in result:
            return f"Performance across {len(result['periods'])} years"
        if "counterparties" in result:
            s = result.get("summary", {})
            seed = result.get("seed", {})
            seed_desc = seed.get("merchant_name") or f"user {seed.get('user_id', '?')}"
            return (
                f"Traced {s.get('counterparties_returned', 0)} counterparties from "
                f"{seed_desc} — {s.get('fraud_heavy_counterparties', 0)} with shared fraud"
            )
        if "generated" in result and "fraud_rate" in result and "legitimate" in result:
            return (
                f"Generated {result['generated']:,} transactions "
                f"({result['fraud']} fraud, {result['legitimate']} legitimate, "
                f"{result['fraud_rate']}% fraud rate)"
            )
        if "experiment_id" in result and "status" in result:
            return f"Experiment {result['experiment_id']} {result['status']}"
        if "promoted" in result:
            return f"Promoted experiment {result['promoted']}"
    return str(result)[:100]
