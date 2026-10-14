"""TLS trust for the OpenAI-compatible LLM endpoints (CAII, vLLM, Llama Guard).

httpx (used by the OpenAI SDK) trusts only certifi's public CA list by default.
On CML Private Cloud, Cloudera AI Inference endpoints are usually signed by the
cluster's internal CA, which the runtime image adds to the SYSTEM trust store,
not to certifi. So we trust the system store, then certifi, then any bundle
named in CAII_CA_BUNDLE / REQUESTS_CA_BUNDLE / SSL_CERT_FILE.

Set TLS_VERIFY=false only as a last resort for a lab.
"""

import os
import ssl
from functools import lru_cache

import httpx

CA_ENV = ("CAII_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE")


@lru_cache(maxsize=1)
def ssl_context():
    if os.environ.get("TLS_VERIFY", "true").lower() in ("0", "false", "no"):
        return False
    ctx = ssl.create_default_context()  # system trust store
    try:
        import certifi

        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:
        pass
    for name in CA_ENV:
        path = os.environ.get(name)
        if path and os.path.exists(path):
            try:
                if os.path.isdir(path):
                    ctx.load_verify_locations(capath=path)
                else:
                    ctx.load_verify_locations(cafile=path)
            except (ssl.SSLError, OSError):
                pass
    return ctx


def http_client() -> httpx.Client:
    """httpx client for OpenAI(http_client=...); trust_env keeps HTTPS_PROXY / NO_PROXY working."""
    return httpx.Client(verify=ssl_context(), trust_env=True)
