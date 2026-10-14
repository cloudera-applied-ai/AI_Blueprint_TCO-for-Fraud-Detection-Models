"""LLM client abstraction using OpenAI SDK for CAII, vLLM, and Ollama."""

import os
import json
import yaml
from openai import OpenAI

from net import http_client

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    PROJECT_ROOT = os.getcwd()


def load_config():
    config_path = os.path.join(PROJECT_ROOT, "config", "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def _get_caii_api_key(config_api_key=""):
    """Resolve CAII API key: CML session JWT > CDP_TOKEN env var > config value."""
    # Inside a CML session, the JWT is written to /tmp/jwt
    jwt_path = "/tmp/jwt"
    if os.path.isfile(jwt_path):
        try:
            with open(jwt_path) as f:
                return json.load(f)["access_token"]
        except Exception:
            pass
    return os.environ.get("CDP_TOKEN", config_api_key)


def _normalize_base_url(endpoint):
    """Ensure the endpoint ends with /v1 as required by the OpenAI SDK."""
    endpoint = endpoint.rstrip("/")
    if not endpoint.endswith("/v1"):
        endpoint += "/v1"
    return endpoint


def get_llm_client():
    config = load_config()
    provider = os.environ.get("LLM_PROVIDER", config["llm"]["provider"])

    if provider == "caii":
        endpoint = os.environ.get("CAII_ENDPOINT", config["llm"]["caii"]["endpoint"])
        api_key = _get_caii_api_key(config["llm"]["caii"].get("api_key", ""))
        model = config["llm"]["caii"]["model"]
    elif provider == "vllm":
        vllm_cfg = config["llm"]["vllm"]
        endpoint = os.environ.get("VLLM_ENDPOINT", vllm_cfg["endpoint"])
        # vLLM only checks the key when started with --api-key; "EMPTY" is the
        # conventional placeholder for unauthenticated servers.
        api_key = os.environ.get("VLLM_API_KEY", vllm_cfg.get("api_key", "")) or "EMPTY"
        model = vllm_cfg["model"]
    else:
        endpoint = os.environ.get("OLLAMA_ENDPOINT", config["llm"]["ollama"]["endpoint"])
        api_key = config["llm"]["ollama"]["api_key"]
        model = config["llm"]["ollama"]["model"]
    base_url = _normalize_base_url(endpoint)

    client = OpenAI(base_url=base_url, api_key=api_key, http_client=http_client())
    return client, model, config["llm"]


def chat_completion(messages, tools=None, temperature=None):
    client, model, llm_config = get_llm_client()
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature or llm_config.get("temperature", 0.1),
        "max_tokens": llm_config.get("max_tokens", 2048),
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return client.chat.completions.create(**kwargs)


def chat_completion_stream(messages, tools=None, temperature=None):
    client, model, llm_config = get_llm_client()
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature or llm_config.get("temperature", 0.1),
        "max_tokens": llm_config.get("max_tokens", 2048),
        "stream": True,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return client.chat.completions.create(**kwargs)
