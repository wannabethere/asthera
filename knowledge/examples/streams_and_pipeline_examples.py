"""
Runnable examples: streams API and AsyncQueryPipeline.
Set BASE_URL (e.g. http://localhost:8000) and run with: python -m examples.streams_and_pipeline_examples
"""
import asyncio
import json
import sys

BASE_URL = "http://localhost:8000"


# --- Streams (HTTP) ---

def list_assistants():
    import requests
    r = requests.get(f"{BASE_URL}/api/streams/assistants")
    r.raise_for_status()
    data = r.json()
    for a in data.get("assistants", []):
        print(a["assistant_id"], a.get("name"))
    return data


def ask_assistant(question: str, dataset: str, agent: str = None):
    import requests
    body = {"question": question, "dataset": dataset}
    if agent:
        body["agent"] = agent
    r = requests.post(f"{BASE_URL}/api/streams/ask", json=body)
    r.raise_for_status()
    return r.json()


def invoke_stream(assistant_id: str, query: str):
    import requests
    r = requests.post(
        f"{BASE_URL}/api/streams/invoke",
        json={"assistant_id": assistant_id, "query": query},
        stream=True,
    )
    r.raise_for_status()
    for line in r.iter_lines():
        if line and line.startswith(b"data: "):
            print(line.decode("utf-8"))


# --- AsyncQueryPipeline (in-process) ---

async def run_pipeline_query(query: str, context: dict = None):
    from app.pipelines import get_pipeline_registry
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("general_query")
    if not pipeline:
        raise RuntimeError("general_query pipeline not registered (run app startup first)")
    result = await pipeline.run(
        inputs={
            "query": query,
            "context": context or {},
            "options": {},
        }
    )
    return result


# --- Run examples ---

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "streams":
        print("--- list assistants ---")
        list_assistants()
        print("\n--- ask (no agent = first assistant) ---")
        out = ask_assistant("What is SOC2?", "Snyk")
        print(out.get("answer", "")[:200], "...")
        print("agent_used:", out.get("agent_used"))
        print("\n--- invoke stream (first assistant_id from list) ---")
        data = list_assistants()
        aids = [a["assistant_id"] for a in data.get("assistants", [])]
        if aids:
            invoke_stream(aids[0], "Explain compliance in one sentence")
    else:
        print("--- pipeline run ---")
        result = asyncio.run(run_pipeline_query("What are key SOC2 controls?"))
        print("success:", result.get("success"))
        print("data:", result.get("data"))
        print("error:", result.get("error"))


if __name__ == "__main__":
    main()
