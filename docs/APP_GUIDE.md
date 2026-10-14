# Fraud Detection AI

Full-stack fraud detection application with conversational AI analysis powered by XGBoost, SHAP, and NVIDIA RAPIDS.

## Architecture

- **Frontend**: React 19 + TypeScript + Tailwind CSS 4 + Vite 7
- **Backend**: FastAPI + uvicorn, ORJSONResponse
- **ML Pipeline**: XGBoost (GPU-optional), native `pred_contribs` SHAP explanations
- **Data**: SQLite (200K transactions), Parquet for pipeline I/O
- **LLM Agent**: ReAct-style 5-round tool-calling agent via Ollama/CAII (OpenAI-compatible API)
- **GPU**: Optional NVIDIA RAPIDS integration (cuDF, cuML, cuPy) with CPU fallback

## Quick Start

```bash
python app/start_app.py
```

This launches the FastAPI backend and Vite frontend dev server.

## Token Cost Calculator

The application includes a live token cost calculator that tracks LLM token usage per session and compares costs across:

1. **Private Inference** (Ollama/CAII) -- actual API cost is $0
2. **Cloud API equivalents** -- what the same tokens would cost on Anthropic or OpenAI APIs
3. **On-Premises TCO** -- real infrastructure cost including energy, hardware, and maintenance

### Cloud API Pricing

Cloud comparison pricing is fetched live from LiteLLM's community-maintained price list, with fallback to built-in rates.

- **Source**: [LiteLLM pricing database](https://github.com/BerriAI/litellm) (community-maintained, auto-refreshed every 24h)
- **Providers**: Anthropic (Claude Opus/Sonnet/Haiku 4.5), OpenAI (GPT-4o, GPT-4o-mini, GPT-4 Turbo)

### On-Premises TCO Calculator

The on-prem calculator estimates the real marginal cost of running inference on local hardware. It accounts for three cost components:

#### 1. Energy Cost

Power consumption during active token generation, scaled by PUE (Power Usage Effectiveness) to include cooling overhead.

```
energy_cost = (gpu_watts * num_gpus + server_watts) * PUE / 1000 * generation_hours * $/kWh
```

**Sources:**
- [LLM Token Production Energy Cost Calculator](https://energy.inference.net/) -- formula: `E = (2 * N_active * T) / eta`, where eta = hardware efficiency in FLOPs/Joule
- [TokenPowerBench: Benchmarking the Power Consumption of LLM Inference](https://arxiv.org/html/2512.03024v1) -- empirical measurements: 2-4 J/token for 70B models; batch size 32-256 yields ~25% per-token energy reduction; FP8 quantization cuts energy ~30%
- [Per-query Energy Consumption of LLMs (Muxup, 2026)](https://muxup.com/2026q1/per-query-energy-consumption-of-llms) -- DeepSeek-R1 FP8: 0.96-3.74 Wh/query on H100 clusters; prefill is significantly cheaper per token than decode
- [From Prompts to Power: Measuring the Energy Footprint of LLM Inference](https://arxiv.org/html/2511.05597) -- methodology for instrumenting GPU-level power during inference workloads

#### 2. Hardware Amortization

GPU and server hardware costs spread over a configurable depreciation period, adjusted for GPU utilization (low utilization = higher cost per token).

```
hardware_cost = (gpu_cost * num_gpus + server_cost) / (amort_years * 8760h) * generation_hours / utilization
```

**Sources:**
- [Cost Per Token Analysis: Optimizing GPU Infrastructure (Introl)](https://introl.com/blog/cost-per-token-llm-inference-optimization) -- H100 SXM: $25K-$40K, 700W TDP; 8-GPU server: $200K-$400K; utilization below 10% makes on-prem more expensive than premium APIs
- [Inference Unit Economics: True Cost Per Million Tokens (Introl)](https://introl.com/blog/inference-unit-economics-true-cost-per-million-tokens-guide) -- 8xH100 true operational cost: $8-$15/hr fully amortized; cooling/facilities/maintenance adds $2-7/hr; minimum viable volume: >8,000 conversations daily
- [Understanding LLM Cost Per Token: A 2026 Practical Guide (Silicon Data)](https://www.silicondata.com/blog/llm-cost-per-token) -- H200 141GB HBM3e ($30-40K purchase), H100 cloud prices dropped to $1.49-3.90/hr

#### 3. Maintenance Cost

Annual maintenance (staffing, repairs, upkeep) as a percentage of total hardware cost.

```
maintenance_cost = hardware_total * maintenance_pct / 8760h * generation_hours / utilization
```

**Sources:**
- [A Cost-Benefit Analysis of On-Premise LLM Deployment (arXiv 2509.18101)](https://arxiv.org/html/2509.18101v1) -- trade-offs between cloud API spend and amortized hardware costs; impact of FP8 precision and energy efficiency on break-even analysis
- [On-Premise vs Cloud: Generative AI TCO (Lenovo, 2025)](https://lenovopress.lenovo.com/lp2225.pdf) -- chips and staff typically make up 70-80% of total LLM deployment costs; electricity + cooling adds 20-30% on top of raw compute cost
- [Why Most Enterprises Underestimate LLM Inference Costs (Medium)](https://medium.com/aigenverse/why-most-enterprises-underestimate-the-real-cost-of-llm-inference-in-production-9b675adf7860) -- hidden costs of production inference at scale

### GPU Presets

The calculator ships with empirical specs for common inference GPUs:

| GPU | TDP (W) | VRAM | Est. Cost | Default tok/s (8B model) |
|-----|---------|------|-----------|--------------------------|
| NVIDIA H100 SXM | 700W | 80GB | $30,000 | 3,500 |
| NVIDIA H100 PCIe | 350W | 80GB | $25,000 | 2,000 |
| NVIDIA A100 80GB | 400W | 80GB | $15,000 | 1,500 |
| NVIDIA A100 40GB | 250W | 40GB | $10,000 | 1,200 |
| NVIDIA L40S | 350W | 48GB | $8,000 | 1,000 |
| NVIDIA RTX 4090 | 450W | 24GB | $2,000 | 800 |
| NVIDIA RTX 3090 | 350W | 24GB | $1,000 | 500 |
| Intel Gaudi 3 | 600W | 128GB | $15,000 | 2,500 |

TDP and memory from manufacturer spec sheets. Pricing reflects mid-2025 enterprise/street prices. Default throughput is representative for ~8B parameter models at batch=1, FP16.

### Key Parameters

| Parameter | Default | Description | Source |
|-----------|---------|-------------|--------|
| PUE | 1.3 | Power Usage Effectiveness (cooling overhead) | [Uptime Institute](https://uptimeinstitute.com/): global average ~1.58, hyperscale ~1.1-1.2 |
| Electricity rate | $0.15/kWh | US commercial average | [US EIA](https://www.eia.gov/electricity/monthly/) |
| Utilization | 50% | GPU active inference time | [Introl](https://introl.com/blog/cost-per-token-llm-inference-optimization): 10-85% typical range |
| Amortization | 3 years | Hardware depreciation period | Industry standard for GPU servers |
| Maintenance | 10%/yr | Annual upkeep as % of hardware | [Lenovo TCO](https://lenovopress.lenovo.com/lp2225.pdf): industry benchmark |
| Server power | 300W | Non-GPU power draw (CPU, RAM, NIC) | [TokenPowerBench](https://arxiv.org/html/2512.03024v1): baseline server ~1.2kW total |

### Efficiency Factors Not Yet Modeled

These factors significantly affect real-world costs but are not yet included:

- **Quantization**: FP8 reduces energy per token by ~30%, FP4 by ~50% ([TokenPowerBench](https://arxiv.org/html/2512.03024v1))
- **Batch size**: Batch 32-256 reduces per-token energy by 2-3x ([TokenPowerBench](https://arxiv.org/html/2512.03024v1))
- **MoE architectures**: Sparse routing reduces token energy by 2-3x vs dense models
- **Context length**: 2K to 10K input tokens increases energy per token ~3x ([Muxup](https://muxup.com/2026q1/per-query-energy-consumption-of-llms))
- **Prefill vs decode**: Input processing is significantly cheaper per token than output generation
- **Idle power**: GPUs draw ~30% TDP when idle; current model only counts active generation time

## Configuration

All settings in `config/config.yaml`. The on-prem TCO calculator can also be configured through the Settings panel in the UI (gear icon).

## License

Proprietary.
