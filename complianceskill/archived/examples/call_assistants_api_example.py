"""
Example: calling the Knowledge Assistants API with token auth.

Server: http://52.6.13.191:8040
Token: loaded from API_PROVISIONED_TOKENS in knowledge/.env (first token used).

Run from repo root or knowledge/:
  python examples/call_assistants_api_example.py

Requires: requests (pip install requests)
Optional: python-dotenv (pip install python-dotenv) to load .env automatically.
"""

import json
import os
import sys

# Resolve path to knowledge/.env (script may be run from repo root or knowledge/)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_KNOWLEDGE_ROOT = os.path.dirname(_SCRIPT_DIR)
_ENV_PATH = os.path.join(_KNOWLEDGE_ROOT, ".env")

BASE_URL = "http://52.6.13.191:8040"


def load_token_from_env_file():
    """Load first API token from knowledge/.env API_PROVISIONED_TOKENS."""
    if not os.path.isfile(_ENV_PATH):
        return None
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("API_PROVISIONED_TOKENS="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                tokens = [t.strip() for t in value.split(",") if t.strip()]
                return tokens[0] if tokens else None
    return None


def get_auth_token():
    """Prefer env var, then .env file."""
    token = os.environ.get("API_PROVISIONED_TOKENS", "").strip()
    if token:
        # Env may be comma-separated; use first
        token = token.split(",")[0].strip()
    if not token:
        token = load_token_from_env_file()
    return token


def main():
    try:
        import requests
    except ImportError:
        print("This example requires 'requests'. Install with: pip install requests")
        sys.exit(1)

    token = get_auth_token()
    if not token:
        print("No API token found. Set API_PROVISIONED_TOKENS or ensure knowledge/.env contains API_PROVISIONED_TOKENS=...")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    # Alternative: headers["X-API-Token"] = token

    print("Base URL:", BASE_URL)
    print("Using token (first 20 chars):", token[:20] + "...")
    print()

    # 1) Health (no auth required per docs, but we send it anyway for consistency)
    print("1) GET /api/health")
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    print("   Status:", r.status_code)
    print("   Body:", json.dumps(r.json(), indent=2)[:500])
    print()

    # 2) Streaming router health
    print("2) GET /api/streams/health")
    r = requests.get(f"{BASE_URL}/api/streams/health", headers=headers, timeout=10)
    print("   Status:", r.status_code)
    if r.ok:
        print("   Body:", json.dumps(r.json(), indent=2)[:400])
    else:
        print("   Body:", r.text[:300])
    print()

    # 3) List assistants
    print("3) GET /api/streams/assistants")
    r = requests.get(f"{BASE_URL}/api/streams/assistants", headers=headers, timeout=10)
    print("   Status:", r.status_code)
    if r.ok:
        data = r.json()
        assistants = data.get("assistants", [])
        for a in assistants[:5]:
            print("   -", a.get("assistant_id"), ":", a.get("name", ""))
    else:
        print("   Body:", r.text[:300])
    print()

    # 4) POST /api/streams/ask (simple Q&A) — can take several minutes
    ASK_TIMEOUT_SEC = 600  # 10 minutes for long-running assistant
    print("4) POST /api/streams/ask (waiting up to %ds for response)..." % ASK_TIMEOUT_SEC)
    payload = {
        "question": "What SOC2 vulnerability metrics and KPIs should I show for an audit report?",
        "dataset": "Snyk",
        "agent": "compliance_assistant",
    }
    r = requests.post(
        f"{BASE_URL}/api/streams/ask",
        headers=headers,
        json=payload,
        timeout=ASK_TIMEOUT_SEC,
    )
    print("   Status:", r.status_code)
    if r.ok:
        data = r.json()
        print("   agent_used:", data.get("agent_used"))
        print("   answer (first 400 chars):", (data.get("answer") or "")[:400])
    else:
        print("   Body:", r.text[:400])
    print()

    # 5) POST /api/streams/mcp (list_assistants)
    print("5) POST /api/streams/mcp (list_assistants)")
    mcp_payload = {
        "jsonrpc": "2.0",
        "method": "list_assistants",
        "params": {},
        "id": "req-1",
    }
    r = requests.post(
        f"{BASE_URL}/api/streams/mcp",
        headers=headers,
        json=mcp_payload,
        timeout=10,
    )
    print("   Status:", r.status_code)
    if r.ok:
        data = r.json()
        result = data.get("result", {})
        for a in result.get("assistants", [])[:3]:
            print("   -", a.get("assistant_id"))
    else:
        print("   Body:", r.text[:300])

    print("\nDone.")


if __name__ == "__main__":
    main()
