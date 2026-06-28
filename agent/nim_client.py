"""
nim_client.py — NVIDIA NIM API client using the OpenAI-compatible interface.

Implements the ReAct (Reason + Act) agent loop:
  1. Think  → LLM reasons about the next step
  2. Act    → LLM calls a tool
  3. Observe → Tool result is fed back to LLM
  4. Repeat → Until LLM stops calling tools (task complete)
"""

import json
import sys
import os
import time

# Allow imports from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests as _requests

from openai import OpenAI, APITimeoutError, APIConnectionError, RateLimitError
import config

GROQ_AVAILABLE = False
try:
    from groq import Groq as _Groq
    GROQ_AVAILABLE = True
except ImportError:
    pass


def get_client() -> OpenAI:
    """Create and return an NVIDIA NIM OpenAI-compatible client."""
    if not config.NVIDIA_API_KEY:
        raise ValueError(
            "NVIDIA_API_KEY is not set. "
            "Add it to your .env file or environment variables."
        )
    return OpenAI(
        base_url=config.NVIDIA_BASE_URL,
        api_key=config.NVIDIA_API_KEY,
        timeout=config.NVIDIA_TIMEOUT_SECONDS,
        max_retries=config.NVIDIA_MAX_RETRIES,
    )


def _groq_completion(messages: list, max_tokens: int) -> str:
    """One-shot completion via the Groq SDK (non-streaming)."""
    if not GROQ_AVAILABLE:
        raise RuntimeError("groq package not installed")
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    client = _Groq(api_key=config.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=messages,
        temperature=0.6,
        max_completion_tokens=max_tokens,
        top_p=0.95,
        reasoning_effort="default",
        stream=False,
    )
    content = response.choices[0].message.content or ""
    # Strip <think>...</think> reasoning block emitted by reasoning models
    import re
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    return content


def _openrouter_completion(messages: list, max_tokens: int) -> str:
    """One-shot completion via OpenRouter (direct requests, reasoning enabled)."""
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    resp = _requests.post(
        url=f"{config.OPENROUTER_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.OPENROUTER_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.6,
            "reasoning": {"enabled": True},
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"].get("content") or ""


def _get_react_providers():
    """Returns (name, OpenAI-compatible client, model) for each configured provider."""
    providers = [("NIM", get_client(), config.NVIDIA_MODEL)]
    if GROQ_AVAILABLE and config.GROQ_API_KEY:
        providers.append((
            "Groq",
            OpenAI(base_url=config.GROQ_BASE_URL, api_key=config.GROQ_API_KEY, timeout=120, max_retries=0),
            config.GROQ_MODEL,
        ))
    if config.OPENROUTER_API_KEY:
        providers.append((
            "OpenRouter",
            OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY, timeout=120, max_retries=0),
            config.OPENROUTER_MODEL,
        ))
    return providers


def _run_react_loop_with_client(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_message: str,
    tools: list,
    tool_executor: callable,
    max_iterations: int,
    verbose: bool,
    provider_name: str = "",
) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]

    for iteration in range(max_iterations):
        if verbose:
            label = f"[{provider_name}]" if provider_name else "[AGENT]"
            print(f"\n{label} Iteration {iteration + 1}/{max_iterations}")

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=0.2,
            max_tokens=4096,
        )

        msg = response.choices[0].message

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                }
                for tc in (msg.tool_calls or [])
            ] if msg.tool_calls else None
        })

        if not msg.tool_calls:
            if verbose:
                print(f"[{provider_name or 'AGENT'}] Task complete.")
            return msg.content or ""

        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            if verbose:
                print(f"[AGENT CALLS] {tool_name}({json.dumps(tool_args, indent=2)})")

            try:
                result = tool_executor(tool_name, tool_args)
            except Exception as e:
                result = {"error": str(e)}

            if verbose:
                result_preview = str(result)[:300]
                print(f"[TOOL RESULT] {result_preview}{'...' if len(str(result)) > 300 else ''}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str)
            })

    last_content = next(
        (m.get("content", "") for m in reversed(messages) if m["role"] == "assistant"),
        "Agent reached maximum iterations without completing the task."
    )
    print(f"[{provider_name or 'AGENT'}] Warning: Max iterations ({max_iterations}) reached.")
    return last_content


def run_react_loop(
    system_prompt: str,
    user_message: str,
    tools: list,
    tool_executor: callable,
    max_iterations: int = 15,
    verbose: bool = True
) -> str:
    """
    Run a full ReAct agent loop with automatic provider fallback.
    Try order: NIM → Groq → OpenRouter. Raises if all providers fail.
    """
    last_error = None
    for name, client, model in _get_react_providers():
        try:
            if verbose and name != "NIM":
                print(f"[AGENT] Switching to fallback provider: {name} ({model})")
            return _run_react_loop_with_client(
                client=client,
                model=model,
                system_prompt=system_prompt,
                user_message=user_message,
                tools=tools,
                tool_executor=tool_executor,
                max_iterations=max_iterations,
                verbose=verbose,
                provider_name=name,
            )
        except (APITimeoutError, APIConnectionError, RateLimitError) as e:
            print(f"[AGENT] {name} failed ({type(e).__name__}): {e}")
            last_error = e
        except Exception as e:
            print(f"[AGENT] {name} failed: {e}")
            last_error = e
            break  # Non-transient error — don't try other providers

    raise RuntimeError(f"All ReAct providers failed. Last error: {last_error}")


def simple_completion(prompt: str, system: str = "", max_tokens: int = 2048, retries: int = 2) -> str:
    """
    One-shot LLM completion with automatic provider fallback.

    Try order: NIM (primary) → Groq → OpenRouter.
    NIM is retried up to `retries` times on timeout/connection errors before
    falling through to the next provider. Raises if all providers fail.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # --- Primary: NVIDIA NIM ---
    last_error = None
    for attempt in range(retries + 1):
        try:
            client = get_client()
            response = client.chat.completions.create(
                model=config.NVIDIA_MODEL,
                messages=messages,
                temperature=0.4,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except (APITimeoutError, APIConnectionError, RateLimitError) as e:
            last_error = e
            if attempt < retries:
                wait = 15 * (attempt + 1)
                print(f"[NIM] Attempt {attempt + 1} failed ({type(e).__name__}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"[NIM] All {retries + 1} attempts failed. Trying fallback providers...")

    # --- Fallback: Groq, then OpenRouter ---
    fallbacks = [
        ("Groq", _groq_completion, bool(GROQ_AVAILABLE and config.GROQ_API_KEY)),
        ("OpenRouter", _openrouter_completion, bool(config.OPENROUTER_API_KEY)),
    ]
    for name, fn, enabled in fallbacks:
        if not enabled:
            continue
        try:
            print(f"[LLM] Trying {name} ({config.GROQ_MODEL if name == 'Groq' else config.OPENROUTER_MODEL})...")
            result = fn(messages, max_tokens)
            print(f"[LLM] {name} succeeded.")
            return result
        except Exception as e:
            print(f"[LLM] {name} failed: {e}")
            last_error = e

    raise RuntimeError(
        f"All LLM providers failed. Last error: {last_error}"
    )
