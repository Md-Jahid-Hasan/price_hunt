import json
import logging
import requests
from django.conf import settings
from .tools import TOOL_REGISTRY, TOOL_SCHEMAS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a product research assistant for an e-commerce price comparison platform.
You have access to tools for searching products, finding the cheapest options, checking price trends, and comparing prices across sites.
Always use a tool to get real data before answering — never guess prices or product names.
If a tool returns no results, tell the user clearly rather than inventing data.
Keep answers concise and grounded only in tool results."""


class LLMRouterError(Exception):
    pass


def _call_ollama_chat(messages: list[dict]) -> dict:
    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.OLLAMA_CHAT_MODEL,
                "messages": messages,
                "tools": TOOL_SCHEMAS,
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise LLMRouterError(f"Ollama chat request failed: {exc}") from exc

    return response.json()


def handle_query(user_query: str, max_tool_iterations: int = 3) -> dict:
    """
    Runs the tool-calling loop: sends the query to the LLM, executes any
    requested tools, feeds results back, and returns the final answer.
    Returns a dict with the final answer plus a trace of tools used (for debugging).
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]
    tools_used = []

    for _ in range(max_tool_iterations):
        result = _call_ollama_chat(messages)
        message = result.get("message", {})
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            return {"answer": message.get("content", ""), "tools_used": tools_used}

        messages.append(message)

        for call in tool_calls:
            func_name = call["function"]["name"]
            func_args = call["function"].get("arguments", {})
            if isinstance(func_args, str):
                func_args = json.loads(func_args)

            tool_fn = TOOL_REGISTRY.get(func_name)
            if not tool_fn:
                tool_result = {"error": f"Unknown tool '{func_name}'"}
            else:
                try:
                    tool_result = tool_fn(**func_args)
                except Exception as exc:
                    logger.exception(f"Tool '{func_name}' failed")
                    tool_result = {"error": str(exc)}

            tools_used.append({"tool": func_name, "args": func_args})
            messages.append(
                {"role": "tool", "content": json.dumps(tool_result), "name": func_name}
            )

    return {
        "answer": "I wasn't able to fully resolve this in the allotted steps — try rephrasing.",
        "tools_used": tools_used,
    }