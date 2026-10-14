"""FastAPI routes for the fraud detection app."""

import os
import sys
import json
import sqlite3
import subprocess
from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _backend_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    PROJECT_ROOT = os.getcwd()
    _backend_dir = os.path.join(PROJECT_ROOT, "app", "backend")
sys.path.insert(0, os.path.join(PROJECT_ROOT, "ai", "agents"))
if _backend_dir not in sys.path:
    sys.path.append(_backend_dir)  # append (not insert) to avoid shadowing agent imports

from agent import run_agent, TOOL_FUNCTIONS
from cost_estimator import estimate_costs, GPU_PRESETS, _load_on_prem_config
from pricing_fetcher import fetch_live_pricing
from llm_client import chat_completion_stream, get_llm_client
from guard import (
    screen_input, screen_output, guard_settings,
    BLOCKED_INPUT_MESSAGE, BLOCKED_OUTPUT_MESSAGE,
)
from prompts import SYSTEM_PROMPT

sys.path.insert(0, os.path.join(PROJECT_ROOT, "pipelines", "model_training"))
from experiment_runner import (
    get_original_model_metrics, get_label_corrections, apply_label_correction,
    remove_label_correction, get_false_positives, generate_additional_data,
    run_experiment, run_experiment_async, promote_experiment,
    get_experiment_status, list_experiments, get_experiment_detail,
)
from tool_registry import TOOLS
from tools.risk_dashboard import get_date_range
from tools.threshold_analysis import get_threshold_analysis
from tools.trace_fraud_network import trace_fraud_network
from tools.merchant_investigation import investigate_merchant
from tools.drift_monitor import (
    compute_drift_report, compute_performance_over_time, compute_score_distribution,
)

DB_PATH = os.path.join(PROJECT_ROOT, "data", "transactions.db")

router = APIRouter()


def _connect_db() -> sqlite3.Connection:
    """Open the transactions DB, or fail with a clean 503 if it doesn't exist yet."""
    if not os.path.isfile(DB_PATH):
        raise HTTPException(
            status_code=503,
            detail="Transaction database not found — run the data pipeline first.",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

_sessions: dict[str, list] = {}
# Cumulative token totals per session id: {"prompt_tokens", "completion_tokens", "total_tokens"}
_session_usage: dict[str, dict] = {}
# Every browser tab mints a fresh session id, so evict the oldest sessions
# once the process has seen more than this many.
MAX_SESSIONS = 100


def _evict_stale_sessions():
    while len(_sessions) > MAX_SESSIONS:
        oldest = next(iter(_sessions))
        _sessions.pop(oldest, None)
        _session_usage.pop(oldest, None)


def _empty_usage():
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _accumulate_usage(session_id: str, turn_usage: dict) -> dict:
    cum = _session_usage.setdefault(session_id, _empty_usage())
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        cum[k] += int(turn_usage.get(k, 0) or 0)
    return cum


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    tool_calls: list
    session_id: str
    usage: dict  # {"turn": estimate_costs(...), "session": estimate_costs(...)}
    guard: Optional[dict] = None  # set when Llama Guard blocked the turn


class TransactionQuery(BaseModel):
    user_id: Optional[int] = None
    merchant_name: Optional[str] = None
    merchant_state: Optional[str] = None
    merchant_country: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    is_fraud: Optional[bool] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 20
    order_by: Optional[str] = None


def _blocked_chat_response(session_id: str, message: str, verdict) -> ChatResponse:
    """A blocked turn costs nothing and is not written to the session history."""
    cum_usage = _session_usage.get(session_id) or _empty_usage()
    return ChatResponse(
        response=message,
        tool_calls=[],
        session_id=session_id,
        usage={
            "turn": estimate_costs(0, 0),
            "session": estimate_costs(cum_usage["prompt_tokens"], cum_usage["completion_tokens"]),
        },
        guard=verdict.as_dict(),
    )


@router.post("/chat")
def chat(req: ChatRequest):
    input_verdict = screen_input(req.message)
    if not input_verdict.safe:
        return _blocked_chat_response(
            req.session_id,
            BLOCKED_INPUT_MESSAGE.format(categories=input_verdict.category_names),
            input_verdict,
        )

    history = _sessions.get(req.session_id, [])
    result = run_agent(req.message, conversation_history=history)

    output_verdict = screen_output(req.message, result["response"])
    if not output_verdict.safe:
        # Drop the unsafe turn from history so it can't seed later answers.
        return _blocked_chat_response(
            req.session_id,
            BLOCKED_OUTPUT_MESSAGE.format(categories=output_verdict.category_names),
            output_verdict,
        )

    _sessions[req.session_id] = result["messages"]
    _evict_stale_sessions()

    turn_usage = result.get("usage") or _empty_usage()
    cum_usage = _accumulate_usage(req.session_id, turn_usage)
    usage_payload = {
        "turn": estimate_costs(turn_usage["prompt_tokens"], turn_usage["completion_tokens"]),
        "session": estimate_costs(cum_usage["prompt_tokens"], cum_usage["completion_tokens"]),
    }

    return ChatResponse(
        response=result["response"],
        tool_calls=result["tool_calls"],
        session_id=req.session_id,
        usage=usage_payload,
    )


@router.get("/sessions/{session_id}/usage")
def get_session_usage(session_id: str):
    cum = _session_usage.get(session_id) or _empty_usage()
    return estimate_costs(cum["prompt_tokens"], cum["completion_tokens"])


@router.post("/config/pricing/refresh")
def refresh_pricing():
    """Force a re-fetch of the LiteLLM pricing table, bypassing cache TTL."""
    payload = fetch_live_pricing(force_refresh=True)
    pricing = payload.get("pricing") or {}
    return {
        "source": payload.get("source"),
        "source_url": payload.get("source_url"),
        "fetched_at": payload.get("fetched_at"),
        "stale": payload.get("stale", False),
        "error": payload.get("error"),
        "anthropic_model_count": len(pricing.get("anthropic", {}).get("models", {})),
        "openai_model_count": len(pricing.get("openai", {}).get("models", {})),
    }


@router.post("/chat/stream")
def chat_stream(req: ChatRequest):
    input_verdict = screen_input(req.message)
    if not input_verdict.safe:
        blocked = BLOCKED_INPUT_MESSAGE.format(categories=input_verdict.category_names)

        def blocked_stream():
            yield f"data: {json.dumps({'type': 'guard', 'guard': input_verdict.as_dict()})}\n\n"
            yield f"data: {json.dumps({'type': 'content', 'content': blocked})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(blocked_stream(), media_type="text/event-stream")

    history = _sessions.get(req.session_id, [])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": req.message})

    # Sync generator on purpose: Starlette iterates it in a threadpool, so the
    # blocking OpenAI stream and run_agent don't starve the event loop.
    def generate():
        try:
            stream = chat_completion_stream(messages, tools=TOOLS)
            collected_content = ""
            tool_calls_detected = False
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.tool_calls:
                    tool_calls_detected = True
                    break
                if delta.content:
                    collected_content += delta.content
                    yield f"data: {json.dumps({'type': 'content', 'content': delta.content})}\n\n"
            if tool_calls_detected:
                result = run_agent(req.message, conversation_history=history)
                output_verdict = screen_output(req.message, result["response"])
                if not output_verdict.safe:
                    blocked = BLOCKED_OUTPUT_MESSAGE.format(categories=output_verdict.category_names)
                    yield f"data: {json.dumps({'type': 'guard', 'guard': output_verdict.as_dict()})}\n\n"
                    yield f"data: {json.dumps({'type': 'content', 'content': blocked})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return
                _sessions[req.session_id] = result["messages"]
                turn_usage = result.get("usage") or _empty_usage()
                cum_usage = _accumulate_usage(req.session_id, turn_usage)
                yield f"data: {json.dumps({'type': 'tool_calls', 'tool_calls': result['tool_calls']})}\n\n"
                yield f"data: {json.dumps({'type': 'content', 'content': result['response']})}\n\n"
                usage_payload = {
                    'turn': estimate_costs(turn_usage['prompt_tokens'], turn_usage['completion_tokens']),
                    'session': estimate_costs(cum_usage['prompt_tokens'], cum_usage['completion_tokens']),
                }
                yield f"data: {json.dumps({'type': 'usage', 'usage': usage_payload})}\n\n"
            else:
                # Tokens are already on the wire here, so the guard can only flag
                # the finished answer — the client is told to discard what it rendered.
                output_verdict = screen_output(req.message, collected_content)
                if not output_verdict.safe:
                    blocked = BLOCKED_OUTPUT_MESSAGE.format(categories=output_verdict.category_names)
                    yield f"data: {json.dumps({'type': 'guard', 'guard': output_verdict.as_dict(), 'replacement': blocked})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return
                history.append({"role": "user", "content": req.message})
                history.append({"role": "assistant", "content": collected_content})
                _sessions[req.session_id] = history
            _evict_stale_sessions()
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception:
            # Don't leak endpoint URLs / internals from provider exceptions
            yield f"data: {json.dumps({'type': 'error', 'error': 'LLM request failed — check the backend logs and LLM settings.'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/transactions/query")
def query_transactions(query: TransactionQuery):
    func = TOOL_FUNCTIONS["query_transactions"]
    return func(**query.model_dump(exclude_none=True))


@router.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: int):
    conn = _connect_db()
    try:
        row = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?",
            (transaction_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return dict(row)


@router.get("/transactions/{transaction_id}/score")
def score_transaction(transaction_id: int, explain: bool = True):
    func = TOOL_FUNCTIONS["score_transaction"]
    return func(transaction_id=transaction_id, explain=explain)


@router.get("/transactions/{transaction_id}/explain")
def explain_transaction(transaction_id: int):
    func = TOOL_FUNCTIONS["explain_prediction"]
    return func(transaction_id=transaction_id)


@router.get("/dashboard")
def dashboard(
    time_period: str = "all",
    group_by: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    func = TOOL_FUNCTIONS["get_risk_dashboard"]
    return func(
        time_period=time_period,
        group_by=group_by,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/dashboard/date-range")
def dashboard_date_range():
    return get_date_range()


@router.get("/model/threshold-analysis")
def threshold_analysis(sample_size: int = 5000):
    return get_threshold_analysis(sample_size=min(sample_size, 10000))


@router.get("/export/transactions")
def export_transactions_csv(
    user_id: Optional[int] = None,
    is_fraud: Optional[bool] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10000,
):
    """Export transactions as CSV for download."""
    import io
    import csv

    def date_num(date_str):
        try:
            y, m, d = (int(p) for p in date_str.split("-"))
            return y * 10000 + m * 100 + d
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"Invalid date: {date_str!r} (expected YYYY-MM-DD)")

    conditions = []
    params = []

    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)
    if is_fraud is not None:
        conditions.append("is_fraud = ?")
        params.append(1 if is_fraud else 0)
    if start_date:
        conditions.append("(year * 10000 + month * 100 + day) >= ?")
        params.append(date_num(start_date))
    if end_date:
        conditions.append("(year * 10000 + month * 100 + day) <= ?")
        params.append(date_num(end_date))

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    safe_limit = min(limit, 50000)

    conn = _connect_db()
    try:
        # Check if merchant_country column exists in this DB
        col_cursor = conn.execute("PRAGMA table_info(transactions)")
        db_cols = {row["name"] for row in col_cursor.fetchall()}
        country_col = ", merchant_country" if "merchant_country" in db_cols else ""

        rows = conn.execute(f"""
            SELECT transaction_id, user_id, card_id, merchant_name, merchant_city,
                   merchant_state{country_col}, mcc, amount, hour, minute,
                   day, month, year, use_chip, errors, is_fraud
            FROM transactions
            {where}
            ORDER BY transaction_id DESC
            LIMIT ?
        """, params + [safe_limit]).fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=dict(rows[0]).keys())
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))

    from starlette.responses import Response
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions_export.csv"},
    )


@router.get("/fraud-network")
def fraud_network(
    merchant_name: Optional[str] = None,
    user_id: Optional[int] = None,
    direction: str = "auto",
    fraud_only: bool = True,
    max_counterparties: int = 25,
):
    """Trace fraud between a merchant and its customers (or a user and their merchants)."""
    return trace_fraud_network(
        merchant_name=merchant_name,
        user_id=user_id,
        direction=direction,
        fraud_only=fraud_only,
        max_counterparties=min(max_counterparties, 100),
    )


@router.get("/investigation/merchant")
def merchant_investigation(
    merchant_name: str,
    max_counterparties: int = 25,
    max_transactions: int = 20,
):
    """Composite merchant investigation: KPIs + geo + trend + trace + patterns + top fraud txns."""
    return investigate_merchant(
        merchant_name=merchant_name,
        max_counterparties=min(max_counterparties, 100),
        max_transactions=min(max_transactions, 100),
    )


@router.get("/model/drift")
def drift_report(
    reference_year: int = 2018,
    current_year: int = 2020,
    report_type: str = "feature_drift",
):
    if report_type == "performance_over_time":
        return compute_performance_over_time()
    if report_type == "score_distribution":
        return compute_score_distribution(reference_year=reference_year, current_year=current_year)
    return compute_drift_report(reference_year=reference_year, current_year=current_year)


@router.get("/alerts")
def alerts(
    user_id: Optional[int] = None,
    merchant_name: Optional[str] = None,
    pattern_type: str = "all",
):
    func = TOOL_FUNCTIONS["detect_alert_patterns"]
    return func(user_id=user_id, merchant_name=merchant_name, pattern_type=pattern_type)


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    _session_usage.pop(session_id, None)
    return {"status": "cleared"}


@router.get("/health")
async def health():
    db_exists = os.path.exists(DB_PATH)
    model_exists = os.path.exists(os.path.join(PROJECT_ROOT, "models", "xgboost_fraud.json"))
    return {"status": "ok", "database": db_exists, "model": model_exists}


@router.get("/config/guard")
async def get_guard_config():
    """Llama Guard status for the Settings panel (never returns the API key)."""
    settings = guard_settings()
    return {
        "enabled": settings["enabled"],
        "model": settings["model"],
        # Blank endpoint means the guard shares the chat provider's connection.
        "endpoint": settings["endpoint"],
        "shares_chat_endpoint": not settings["endpoint"],
    }


@router.get("/config/llm")
async def get_llm_config():
    try:
        config = _load_config()
        llm = config.get("llm", {})
        provider = os.environ.get("LLM_PROVIDER", llm.get("provider", "ollama"))
        ollama_cfg = llm.get("ollama", {})
        caii_cfg = llm.get("caii", {})
        vllm_cfg = llm.get("vllm", {})
        return {
            "provider": provider,
            "ollama": {
                "endpoint": os.environ.get("OLLAMA_ENDPOINT", ollama_cfg.get("endpoint", "http://localhost:11434/v1")),
                "model": ollama_cfg.get("model", "llama3.1:8b"),
            },
            "caii": {
                "endpoint": os.environ.get("CAII_ENDPOINT", caii_cfg.get("endpoint", "")),
                "model": caii_cfg.get("model", ""),
                "has_api_key": bool(os.environ.get("CDP_TOKEN", caii_cfg.get("api_key", ""))),
            },
            "vllm": {
                "endpoint": os.environ.get("VLLM_ENDPOINT", vllm_cfg.get("endpoint", "http://localhost:8000/v1")),
                "model": vllm_cfg.get("model", ""),
                "has_api_key": bool(os.environ.get("VLLM_API_KEY", vllm_cfg.get("api_key", ""))),
            },
            "temperature": llm.get("temperature", 0.1),
            "max_tokens": llm.get("max_tokens", 2048),
        }
    except Exception as e:
        # Exception text from the OpenAI client can embed the endpoint URL — return the class only
        return {"provider": "unknown", "error": type(e).__name__}


class LlmConfigUpdate(BaseModel):
    provider: str  # "ollama", "caii", or "vllm"
    endpoint: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None


@router.put("/config/llm")
async def update_llm_config(update: LlmConfigUpdate):
    if update.provider not in ("ollama", "caii", "vllm"):
        raise HTTPException(status_code=400, detail="provider must be 'ollama', 'caii', or 'vllm'")

    config = _load_config()
    if "llm" not in config:
        config["llm"] = {}
    config["llm"]["provider"] = update.provider

    provider_key = update.provider
    if provider_key not in config["llm"]:
        config["llm"][provider_key] = {}

    if update.endpoint is not None:
        config["llm"][provider_key]["endpoint"] = update.endpoint
    if update.model is not None:
        config["llm"][provider_key]["model"] = update.model
    if update.api_key is not None:
        config["llm"][provider_key]["api_key"] = update.api_key

    _rewrite_config(config)

    # Update env vars so the current process picks up the change
    os.environ["LLM_PROVIDER"] = update.provider
    if update.provider == "caii" and update.endpoint:
        os.environ["CAII_ENDPOINT"] = update.endpoint
    if update.provider == "caii" and update.api_key:
        os.environ["CDP_TOKEN"] = update.api_key
    if update.provider == "ollama" and update.endpoint:
        os.environ["OLLAMA_ENDPOINT"] = update.endpoint
    if update.provider == "vllm" and update.endpoint:
        os.environ["VLLM_ENDPOINT"] = update.endpoint
    if update.provider == "vllm" and update.api_key:
        os.environ["VLLM_API_KEY"] = update.api_key

    return {
        "provider": update.provider,
        "message": f"LLM provider set to '{update.provider}'. Changes take effect immediately.",
    }


@router.post("/config/llm/test")
async def test_llm_connection():
    """Quick connectivity test to the configured LLM endpoint."""
    try:
        client, model, llm_config = get_llm_client()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'ok' and nothing else."}],
            max_tokens=5,
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        return {"status": "connected", "model": model, "response": content.strip()}
    except Exception as e:
        # Exception text from the OpenAI client can embed the endpoint URL and
        # auth details — log the full error server-side, return only the class.
        print(f"[llm-test] connection failed: {e}")
        return {"status": "error", "error": f"{type(e).__name__} — see backend logs for details"}


@router.get("/config/on-prem")
def get_on_prem_config():
    """Return the current on-prem TCO configuration."""
    return _load_on_prem_config()


@router.get("/config/on-prem/presets")
def get_gpu_presets():
    """Return available GPU presets for the on-prem calculator."""
    return {"presets": GPU_PRESETS}


class OnPremConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    gpu_preset: Optional[str] = None
    num_gpus: Optional[int] = None
    server_power_watts: Optional[float] = None
    pue: Optional[float] = None
    electricity_rate_kwh: Optional[float] = None
    gpu_utilization_pct: Optional[float] = None
    amortization_years: Optional[float] = None
    maintenance_pct: Optional[float] = None
    server_base_cost_usd: Optional[float] = None
    tokens_per_second: Optional[float] = None


@router.put("/config/on-prem")
def update_on_prem_config(update: OnPremConfigUpdate):
    """Update on-prem TCO settings in config.yaml."""
    if update.gpu_preset and update.gpu_preset not in GPU_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown GPU preset: {update.gpu_preset}")

    config = _load_config()
    if "on_prem" not in config:
        config["on_prem"] = {}

    updates = update.model_dump(exclude_none=True)
    config["on_prem"].update(updates)

    _rewrite_config(config)

    return {"message": "On-prem config saved", "config": _load_on_prem_config()}


def _load_config():
    config_path = os.path.join(PROJECT_ROOT, "config", "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def _save_config(config):
    """Save config, preserving comments by only updating changed values in-place."""
    config_path = os.path.join(PROJECT_ROOT, "config", "config.yaml")

    # Try to do a targeted update to preserve comments and formatting
    try:
        with open(config_path) as f:
            lines = f.readlines()

        gpu_enabled = config.get("gpu", {}).get("enabled", "auto")
        in_gpu_section = False
        updated = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Detect top-level gpu: section
            if line.startswith("gpu:"):
                in_gpu_section = True
                continue
            # Detect next top-level section (not indented)
            if in_gpu_section and stripped and not line[0].isspace():
                in_gpu_section = False
            # Update the enabled key within gpu section
            if in_gpu_section and stripped.startswith("enabled:"):
                indent = line[:len(line) - len(line.lstrip())]
                lines[i] = f'{indent}enabled: "{gpu_enabled}"'
                # Preserve inline comment if present
                if "#" in line.split(":", 1)[1]:
                    comment = "#" + line.split("#", 1)[1]
                    lines[i] = lines[i].rstrip() + "          " + comment
                else:
                    lines[i] += "\n"
                updated = True
                break

        if updated:
            with open(config_path, "w") as f:
                f.writelines(lines)
            return
    except Exception:
        pass

    # Fallback: full rewrite
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def _rewrite_config(config):
    """Write config.yaml as a full YAML dump. Comments and ordering are NOT
    preserved — use _save_config for the targeted, comment-preserving path."""
    config_path = os.path.join(PROJECT_ROOT, "config", "config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def _detect_nvidia_gpu():
    """Detect an NVIDIA GPU via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            return {
                "detected": True,
                "vendor": "NVIDIA",
                "name": parts[0] if len(parts) > 0 else "Unknown",
                "memory": parts[1] if len(parts) > 1 else "Unknown",
                "driver": parts[2] if len(parts) > 2 else "Unknown",
            }
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _detect_amd_gpu():
    """Detect an AMD GPU via rocm-smi (present in the ROCm image)."""
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        cards = json.loads(result.stdout)
        for card in cards.values():
            name = (card.get("Card Series") or card.get("Card Model")
                    or card.get("Card SKU") or "AMD GPU")
            total = card.get("VRAM Total Memory (B)")
            memory = f"{int(total) / (1024 ** 3):.0f} GiB" if total else "Unknown"
            return {
                "detected": True,
                "vendor": "AMD",
                "name": name,
                "memory": memory,
                "driver": "ROCm",
            }
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, TypeError):
        pass
    return None


def _detect_gpu_hardware():
    """Detect a local GPU — NVIDIA first, then AMD/ROCm."""
    return (
        _detect_nvidia_gpu()
        or _detect_amd_gpu()
        or {"detected": False, "vendor": None, "name": None, "memory": None, "driver": None}
    )


def _detect_rapids():
    """Check if RAPIDS libraries are installed."""
    libs = {}
    for lib_name in ["cudf", "cuml", "cupy"]:
        try:
            mod = __import__(lib_name)
            libs[lib_name] = getattr(mod, "__version__", "installed")
        except ImportError:
            libs[lib_name] = None
    return libs


@router.get("/config/gpu")
async def get_gpu_config():
    config = _load_config()
    gpu_setting = config.get("gpu", {}).get("enabled", "auto")
    hardware = _detect_gpu_hardware()
    rapids = _detect_rapids()
    force_cpu = os.environ.get("FRAUD_DETECTION_FORCE_CPU", "").lower() in ("1", "true", "yes")

    from gpu_utils import GPU_ENABLED, gpu_info, xgboost_gpu_available

    return {
        "setting": gpu_setting,
        "hardware": hardware,
        "rapids": rapids,
        "active": GPU_ENABLED,
        # True on ROCm, where XGBoost trains on the GPU but RAPIDS is absent.
        "xgboost_gpu": xgboost_gpu_available(),
        "force_cpu_env": force_cpu,
        "status": gpu_info(),
    }


class GpuConfigUpdate(BaseModel):
    enabled: str  # "auto", "true", "false"


@router.put("/config/gpu")
async def update_gpu_config(update: GpuConfigUpdate):
    if update.enabled not in ("auto", "true", "false"):
        raise HTTPException(status_code=400, detail="enabled must be 'auto', 'true', or 'false'")

    config = _load_config()
    if "gpu" not in config:
        config["gpu"] = {}
    config["gpu"]["enabled"] = update.enabled

    _save_config(config)

    # Update the environment variable for the current process
    if update.enabled == "false":
        os.environ["FRAUD_DETECTION_FORCE_CPU"] = "1"
    else:
        os.environ.pop("FRAUD_DETECTION_FORCE_CPU", None)

    return {
        "setting": update.enabled,
        "message": f"GPU mode set to '{update.enabled}'. Pipeline scripts will use this setting on next run.",
    }


# ---------------------------------------------------------------------------
# Experiment / Model Retraining Routes
# ---------------------------------------------------------------------------

@router.get("/experiments/original-metrics")
def experiment_original_metrics():
    """Get current production model metrics."""
    return get_original_model_metrics()


@router.get("/experiments/false-positives")
def experiment_false_positives(limit: int = 50):
    """Get fraud-labeled transactions that may be mislabeled (for analyst review)."""
    return get_false_positives(limit=min(limit, 200))


@router.get("/experiments/corrections")
def experiment_corrections():
    """List all label corrections."""
    return get_label_corrections()


class LabelCorrectionRequest(BaseModel):
    transaction_id: int
    corrected_label: int  # 0 = not fraud, 1 = fraud


@router.post("/experiments/corrections")
def experiment_apply_correction(req: LabelCorrectionRequest):
    """Record a label correction."""
    if req.corrected_label not in (0, 1):
        raise HTTPException(status_code=400, detail="corrected_label must be 0 or 1")
    return apply_label_correction(req.transaction_id, req.corrected_label)


@router.delete("/experiments/corrections/{transaction_id}")
def experiment_remove_correction(transaction_id: int):
    """Remove a label correction."""
    return remove_label_correction(transaction_id)


class GenerateDataRequest(BaseModel):
    n_transactions: int = 10000


@router.post("/experiments/generate-data")
def experiment_generate_data(req: GenerateDataRequest):
    """Generate additional synthetic transactions."""
    n = max(1000, min(req.n_transactions, 500000))
    return generate_additional_data(n_transactions=n)


class RunExperimentRequest(BaseModel):
    use_corrections: bool = True
    use_generated_data: bool = True
    description: str = ""
    hyperparams: Optional[dict] = None


@router.post("/experiments/run")
def experiment_run(req: RunExperimentRequest):
    """Kick off retraining in a background thread; poll /experiments/status for progress."""
    ack = run_experiment_async(
        use_corrections=req.use_corrections,
        use_generated_data=req.use_generated_data,
        hyperparams=req.hyperparams or None,
        description=req.description,
    )
    if ack.get("status") == "busy":
        raise HTTPException(status_code=409, detail=ack)
    return ack


@router.post("/experiments/run/sync")
def experiment_run_sync(req: RunExperimentRequest):
    """Blocking retrain — retained for scripting / CLI use. Prefer /experiments/run."""
    return run_experiment(
        use_corrections=req.use_corrections,
        use_generated_data=req.use_generated_data,
        hyperparams=req.hyperparams or None,
        description=req.description,
    )


@router.get("/experiments/status")
def experiment_status():
    """Poll for current experiment run status."""
    status = get_experiment_status()
    if status is None:
        return {"status": "idle"}
    return status


@router.get("/experiments/{experiment_id}")
def experiment_detail(experiment_id: str):
    """Return the full stored result for a single experiment."""
    detail = get_experiment_detail(experiment_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
    return detail


@router.post("/experiments/{experiment_id}/promote")
def experiment_promote(experiment_id: str):
    """Promote an experiment model to production."""
    result = promote_experiment(experiment_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/experiments")
def experiment_list():
    """List all saved experiments."""
    return {"experiments": list_experiments()}
