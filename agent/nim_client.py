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

# Allow imports from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from openai import OpenAI
import config


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


def run_react_loop(
    system_prompt: str,
    user_message: str,
    tools: list,
    tool_executor: callable,
    max_iterations: int = 15,
    verbose: bool = True
) -> str:
    """
    Run a full ReAct agent loop against NVIDIA NIM.

    Args:
        system_prompt:   The agent's persona and instructions.
        user_message:    The task to accomplish.
        tools:           List of OpenAI-format tool schemas.
        tool_executor:   Callable(tool_name, tool_args) → result dict.
        max_iterations:  Safety cap on the number of LLM turns.
        verbose:         If True, prints the agent's reasoning steps.

    Returns:
        The agent's final text response when it stops calling tools.
    """
    client = get_client()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]

    for iteration in range(max_iterations):
        if verbose:
            print(f"\n[AGENT] Iteration {iteration + 1}/{max_iterations}")

        # Call NVIDIA NIM
        response = client.chat.completions.create(
            model=config.NVIDIA_MODEL,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=0.2,
            max_tokens=4096,
        )

        msg = response.choices[0].message

        # Append the assistant's response to message history
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in (msg.tool_calls or [])
            ] if msg.tool_calls else None
        })

        # If no tool calls → agent is done
        if not msg.tool_calls:
            if verbose:
                print(f"[AGENT] Task complete. Final response:\n{msg.content}")
            return msg.content or ""

        # Execute each tool call
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            if verbose:
                print(f"[AGENT CALLS] {tool_name}({json.dumps(tool_args, indent=2)})")

            # Run the actual tool function
            try:
                result = tool_executor(tool_name, tool_args)
            except Exception as e:
                result = {"error": str(e)}

            if verbose:
                result_preview = str(result)[:300]
                print(f"[TOOL RESULT] {result_preview}{'...' if len(str(result)) > 300 else ''}")

            # Feed result back to the agent
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str)
            })

    # Safety: if we hit max iterations, return whatever the last content was
    last_content = next(
        (m.get("content", "") for m in reversed(messages) if m["role"] == "assistant"),
        "Agent reached maximum iterations without completing the task."
    )
    print(f"[AGENT] Warning: Max iterations ({max_iterations}) reached.")
    return last_content


def simple_completion(prompt: str, system: str = "", max_tokens: int = 2048) -> str:
    """
    Simple one-shot LLM completion (no tools, no loop).
    Used by FeedbackAgent and SuspicionAgent for focused generation.
    """
    client = get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=config.NVIDIA_MODEL,
        messages=messages,
        temperature=0.4,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""
