"""Token cost estimation for cloud LLM API equivalents and on-prem TCO.

The fraud detection app runs against a local inference service (Ollama or
CAII), so actual dollar cost is $0. This module estimates what the same token
usage *would* cost if the workload were routed to Anthropic's API or OpenAI's
API instead — so the UI can display a live savings counter.

It also computes an **on-premises TCO estimate** (energy, hardware
amortization, maintenance) so operators can see the real marginal cost of
running inference locally.

Pricing is fetched live from LiteLLM's community-maintained price list via
``pricing_fetcher``. If that fetch fails we fall back to the hardcoded
``PROVIDER_PRICING`` table below so the feature still works offline.

Sources for on-prem cost model:
  - Energy formula: energy.inference.net (E = power × time, scaled by PUE)
  - GPU TDP / pricing: NVIDIA spec sheets, Introl cost-per-token analysis 2025
  - TokenPowerBench (arxiv 2512.03024): empirical joules-per-token measurements
  - PUE defaults: Uptime Institute 2024 global average ~1.58, hyperscale ~1.1-1.2
  - Electricity rates: US EIA average commercial rate
"""

import os
import yaml
from pricing_fetcher import fetch_live_pricing

# ---------------------------------------------------------------------------
# GPU presets: empirical specs for common inference GPUs
# Sources:
#   TDP & memory: NVIDIA product data sheets / Intel Gaudi3 spec
#   cost_usd: street / enterprise pricing as of mid-2025 (Introl, SiliconData)
#   default_tok_s: representative throughput for ~8B param model, batch=1,
#                  FP16, measured via vLLM / TensorRT-LLM benchmarks
# ---------------------------------------------------------------------------
GPU_PRESETS = {
    "h100_sxm": {
        "label": "NVIDIA H100 SXM",
        "tdp_watts": 700,
        "cost_usd": 30000,
        "memory_gb": 80,
        "default_tok_s": 3500,
    },
    "h100_pcie": {
        "label": "NVIDIA H100 PCIe",
        "tdp_watts": 350,
        "cost_usd": 25000,
        "memory_gb": 80,
        "default_tok_s": 2000,
    },
    "a100_80gb": {
        "label": "NVIDIA A100 80GB",
        "tdp_watts": 400,
        "cost_usd": 15000,
        "memory_gb": 80,
        "default_tok_s": 1500,
    },
    "a100_40gb": {
        "label": "NVIDIA A100 40GB",
        "tdp_watts": 250,
        "cost_usd": 10000,
        "memory_gb": 40,
        "default_tok_s": 1200,
    },
    "l40s": {
        "label": "NVIDIA L40S",
        "tdp_watts": 350,
        "cost_usd": 8000,
        "memory_gb": 48,
        "default_tok_s": 1000,
    },
    "rtx_4090": {
        "label": "NVIDIA RTX 4090",
        "tdp_watts": 450,
        "cost_usd": 2000,
        "memory_gb": 24,
        "default_tok_s": 800,
    },
    "rtx_3090": {
        "label": "NVIDIA RTX 3090",
        "tdp_watts": 350,
        "cost_usd": 1000,
        "memory_gb": 24,
        "default_tok_s": 500,
    },
    "gaudi3": {
        "label": "Intel Gaudi 3",
        "tdp_watts": 600,
        "cost_usd": 15000,
        "memory_gb": 128,
        "default_tok_s": 2500,
    },
}

# Default on-prem config — overridden by config.yaml `on_prem` section.
DEFAULT_ON_PREM = {
    "enabled": True,
    "gpu_preset": "rtx_4090",
    "num_gpus": 1,
    "server_power_watts": 300,       # non-GPU server power (CPU, RAM, NIC, fans)
    "pue": 1.3,                      # Power Usage Effectiveness (cooling overhead)
    "electricity_rate_kwh": 0.15,    # USD per kWh (US commercial average)
    "gpu_utilization_pct": 50,       # percentage of time GPU is actively serving
    "amortization_years": 3,
    "maintenance_pct": 10,           # annual maintenance as % of hardware cost
    "server_base_cost_usd": 5000,    # chassis, CPU, RAM, NIC, storage
    "tokens_per_second": None,       # null → use GPU preset default
}


def _load_on_prem_config() -> dict:
    """Load on-prem settings from config.yaml, merged over defaults."""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "config", "config.yaml")
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        on_prem = cfg.get("on_prem", {})
        merged = {**DEFAULT_ON_PREM, **{k: v for k, v in on_prem.items() if v is not None}}
        return merged
    except Exception:
        return dict(DEFAULT_ON_PREM)


def estimate_on_prem_cost(prompt_tokens: int, completion_tokens: int, config: dict | None = None) -> dict:
    """Compute on-prem TCO estimate for a given token count.

    Returns a breakdown with energy, hardware amortization, and maintenance
    costs as well as a total.
    """
    if config is None:
        config = _load_on_prem_config()

    if not config.get("enabled", True):
        return {"enabled": False}

    total_tokens = prompt_tokens + completion_tokens
    if total_tokens == 0:
        return {
            "enabled": True,
            "cost_usd": 0.0,
            "energy_cost_usd": 0.0,
            "hardware_cost_usd": 0.0,
            "maintenance_cost_usd": 0.0,
            "config_summary": _config_summary(config),
        }

    preset_id = config.get("gpu_preset", "rtx_4090")
    preset = GPU_PRESETS.get(preset_id, GPU_PRESETS["rtx_4090"])
    num_gpus = max(int(config.get("num_gpus", 1)), 1)
    server_watts = float(config.get("server_power_watts", 300))
    pue = float(config.get("pue", 1.3))
    elec_rate = float(config.get("electricity_rate_kwh", 0.15))
    utilization = max(float(config.get("gpu_utilization_pct", 50)) / 100.0, 0.01)
    amort_years = max(float(config.get("amortization_years", 3)), 0.5)
    maint_pct = float(config.get("maintenance_pct", 10)) / 100.0
    server_cost = float(config.get("server_base_cost_usd", 5000))
    tok_s = config.get("tokens_per_second")
    if tok_s is None or tok_s == 0:
        tok_s = preset["default_tok_s"]
    tok_s = max(float(tok_s), 1)

    # --- Energy cost (only while generating) ---
    gpu_watts = preset["tdp_watts"] * num_gpus
    total_watts = (gpu_watts + server_watts) * pue
    total_kw = total_watts / 1000.0
    generation_seconds = total_tokens / tok_s
    generation_hours = generation_seconds / 3600.0
    energy_kwh = total_kw * generation_hours
    energy_cost = energy_kwh * elec_rate

    # --- Hardware amortization (spread over all served tokens, adjusted for utilization) ---
    total_hardware = (preset["cost_usd"] * num_gpus) + server_cost
    hourly_amort = total_hardware / (amort_years * 8760.0)
    hardware_cost = hourly_amort * generation_hours / utilization

    # --- Maintenance (% of hardware per year, spread same way) ---
    annual_maint = total_hardware * maint_pct
    hourly_maint = annual_maint / 8760.0
    maintenance_cost = hourly_maint * generation_hours / utilization

    total_cost = energy_cost + hardware_cost + maintenance_cost

    return {
        "enabled": True,
        "cost_usd": round(total_cost, 6),
        "energy_cost_usd": round(energy_cost, 6),
        "hardware_cost_usd": round(hardware_cost, 6),
        "maintenance_cost_usd": round(maintenance_cost, 6),
        "energy_kwh": round(energy_kwh, 8),
        "total_watts": round(total_watts, 1),
        "generation_seconds": round(generation_seconds, 3),
        "config_summary": _config_summary(config),
    }


def _config_summary(config: dict) -> dict:
    """Return a human-readable summary of the on-prem config for the UI."""
    preset_id = config.get("gpu_preset", "rtx_4090")
    preset = GPU_PRESETS.get(preset_id, GPU_PRESETS["rtx_4090"])
    return {
        "gpu_label": preset["label"],
        "gpu_preset": preset_id,
        "num_gpus": config.get("num_gpus", 1),
        "pue": config.get("pue", 1.3),
        "electricity_rate_kwh": config.get("electricity_rate_kwh", 0.15),
        "gpu_utilization_pct": config.get("gpu_utilization_pct", 50),
        "amortization_years": config.get("amortization_years", 3),
        "tokens_per_second": config.get("tokens_per_second") or preset["default_tok_s"],
    }


# Fallback pricing: USD per 1,000,000 tokens (input, output).
# Used only if the live fetch from LiteLLM fails and no cache exists.
PROVIDER_PRICING = {
    "anthropic": {
        "default": "claude-sonnet-4-5",
        "models": {
            "claude-opus-4-5":    {"input": 15.00, "output": 75.00, "label": "Claude Opus 4.5"},
            "claude-sonnet-4-5":  {"input":  3.00, "output": 15.00, "label": "Claude Sonnet 4.5"},
            "claude-haiku-4-5":   {"input":  1.00, "output":  5.00, "label": "Claude Haiku 4.5"},
        },
    },
    "openai": {
        "default": "gpt-4o",
        "models": {
            "gpt-4o":       {"input":  2.50, "output": 10.00, "label": "GPT-4o"},
            "gpt-4o-mini":  {"input":  0.15, "output":  0.60, "label": "GPT-4o mini"},
            "gpt-4-turbo":  {"input": 10.00, "output": 30.00, "label": "GPT-4 Turbo"},
        },
    },
}


def _cost(prompt_tokens: int, completion_tokens: int, rates: dict) -> float:
    return (
        (prompt_tokens     / 1_000_000.0) * rates["input"] +
        (completion_tokens / 1_000_000.0) * rates["output"]
    )


def _resolve_pricing() -> tuple[dict, dict]:
    """Return (pricing_map, source_metadata).

    Uses live LiteLLM data when available, otherwise the hardcoded table.
    """
    payload = fetch_live_pricing()
    live = payload.get("pricing")
    if live and live.get("anthropic", {}).get("models") and live.get("openai", {}).get("models"):
        return live, {
            "source": payload.get("source", "unknown"),
            "source_url": payload.get("source_url"),
            "fetched_at": payload.get("fetched_at", 0),
            "stale": payload.get("stale", False),
            "error": payload.get("error"),
        }
    return PROVIDER_PRICING, {
        "source": "builtin",
        "source_url": None,
        "fetched_at": 0,
        "stale": False,
        "error": payload.get("error"),
    }


def estimate_costs(prompt_tokens: int, completion_tokens: int) -> dict:
    """Return a structured cost estimate for the given token counts.

    Shape:
    {
      "tokens": {"input": N, "output": N, "total": N},
      "providers": {
        "anthropic": {
          "default_model": "claude-sonnet-4-6",
          "default_label": "Claude Sonnet 4.6",
          "default_cost_usd": 0.0123,
          "models": {<model_id>: {"label": ..., "cost_usd": ...}, ...}
        },
        "openai": {...}
      },
      "pricing_source": {
        "source": "litellm" | "builtin",
        "source_url": "...",
        "fetched_at": <unix ts>,
        "stale": bool,
      }
    }
    """
    prompt_tokens = max(int(prompt_tokens or 0), 0)
    completion_tokens = max(int(completion_tokens or 0), 0)

    pricing, source_meta = _resolve_pricing()

    result = {
        "tokens": {
            "input": prompt_tokens,
            "output": completion_tokens,
            "total": prompt_tokens + completion_tokens,
        },
        "on_prem": estimate_on_prem_cost(prompt_tokens, completion_tokens),
        "providers": {},
        "pricing_source": source_meta,
    }

    for provider, spec in pricing.items():
        default_id = spec.get("default") or ""
        models_out = {}
        for model_id, rates in spec.get("models", {}).items():
            models_out[model_id] = {
                "label": rates["label"],
                "input_per_mtok_usd":  rates["input"],
                "output_per_mtok_usd": rates["output"],
                "cost_usd": round(_cost(prompt_tokens, completion_tokens, rates), 6),
            }
        if not models_out:
            continue
        if default_id not in models_out:
            default_id = next(iter(models_out))
        default_cost = models_out[default_id]["cost_usd"]
        result["providers"][provider] = {
            "default_model": default_id,
            "default_label": spec["models"][default_id]["label"],
            "default_cost_usd": default_cost,
            "models": models_out,
        }

    return result
