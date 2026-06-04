"""
orchestrator_agent.py — The main AI brain that oversees the daily quiz process.
"""

import sys
import os
import json
from agent.nim_client import run_react_loop
from agent.tools import ORCHESTRATOR_TOOL_SCHEMAS, tool_executor, runtime_backends
from agent.memory import _load as load_memory
import config

SYSTEM_PROMPT = f"""You are the Quiz Orchestrator Agent.
Your job is to run the daily quiz setup by picking adaptive questions based on past weaknesses and sending out emails.
You have tools to:
1. List available topics
2. Get a candidate's history
3. Get all candidates
4. Scrape questions for a topic
5. Select {config.QUIZ_QUESTION_COUNT} questions intelligently based on weaknesses
6. Set up the quiz on the Flask backend
7. Send out quiz emails
8. Update the candidate memory

Execute the following workflow for all candidates, then stop.
1. Get candidate histories.
2. Select appropriate topics for today's quiz based on past performance.
3. Scrape and select {config.QUIZ_QUESTION_COUNT} questions.
4. Setup the daily quiz.
5. Send email to each candidate.
"""

def _choose_fallback_topics(topics, memory_data, max_topics=3):
    """Pick a stable topic set when the LLM is unavailable."""
    configured = getattr(config, "QUIZ_TOPICS", [])
    if configured:
        configured_lower = {topic.lower() for topic in configured}
        selected = [
            topic for topic in topics
            if topic["name"].lower() in configured_lower
        ]
        if selected:
            return selected[:max_topics]

    weak_topic_names = []
    for profile in memory_data.values():
        weak_topic_names.extend(profile.get("overall_weak_topics", []))

    if weak_topic_names:
        weak_lower = {topic.lower() for topic in weak_topic_names}
        selected = [
            topic for topic in topics
            if topic["name"].lower() in weak_lower
        ]
        if selected:
            return selected[:max_topics]

    return topics[:max_topics]


def run_deterministic_dispatch(memory_data):
    """
    Dispatch a quiz without the LLM.
    This keeps the scheduled job useful when the NVIDIA API is unavailable.
    """
    print("--- Starting deterministic fallback dispatcher ---")

    candidates_result = tool_executor("get_all_candidates", {})
    candidates = candidates_result.get("candidates", [])
    if not candidates:
        print("No candidates found. Fallback dispatcher stopping.")
        return {"mode": "fallback", "sent": 0, "candidates": 0}

    topics_result = tool_executor("list_available_topics", {})
    topics = topics_result.get("topics", [])
    if not topics:
        raise RuntimeError("No IndiaBix topics available to scrape.")

    selected_topics = _choose_fallback_topics(topics, memory_data)
    print("[FALLBACK] Selected topics:", ", ".join(t["name"] for t in selected_topics))

    question_pool = []
    scrape_limit = max(10, getattr(config, "QUIZ_QUESTION_COUNT", 5))
    for topic in selected_topics:
        scrape_result = tool_executor(
            "scrape_topic",
            {
                "topic_url": topic["url"],
                "topic_name": topic["name"],
                "max_questions": scrape_limit
            }
        )
        question_pool.extend(scrape_result.get("questions", []))

    if not question_pool:
        raise RuntimeError("Fallback dispatcher could not scrape any questions.")

    select_result = tool_executor(
        "select_questions",
        {
            "questions": question_pool,
            "count": getattr(config, "QUIZ_QUESTION_COUNT", 5)
        }
    )
    selected_questions = select_result.get("questions", [])
    if not selected_questions:
        raise RuntimeError("Fallback dispatcher could not select questions.")

    setup_result = tool_executor(
        "setup_daily_quiz",
        {
            "questions": selected_questions,
            "candidates": candidates
        }
    )
    if not setup_result.get("success"):
        raise RuntimeError(f"Fallback quiz setup failed: {setup_result}")

    sent_count = 0
    for candidate_link in setup_result.get("candidate_links", []):
        email_result = tool_executor("send_quiz_email", candidate_link)
        if email_result.get("sent"):
            sent_count += 1

    print(f"[FALLBACK] Quiz dispatched. Emails sent: {sent_count}/{len(candidates)}")
    return {"mode": "fallback", "sent": sent_count, "candidates": len(candidates)}

def run_daily_quiz_job(sent_log_backend=None, quiz_setup_backend=None):
    print("--- Starting Orchestrator Agent ---")
    with runtime_backends(
        sent_log_backend=sent_log_backend,
        quiz_setup_backend=quiz_setup_backend
    ):
        memory_data = load_memory()
        
        if not config.FRIENDS_LIST:
            print("No candidates found in config.FRIENDS_LIST.")
            return {"mode": "noop", "reason": "no_candidates"}

        print(f"Loaded memory for {len(memory_data)} candidates. Proceeding with ReAct loop...")
        
        configured_topics = ", ".join(config.QUIZ_TOPICS) if config.QUIZ_TOPICS else "adaptive topic selection"
        user_task = (
            "It is time for the daily quiz. "
            f"Use {configured_topics}. "
            f"Select exactly {config.QUIZ_QUESTION_COUNT} questions and send it to all candidates."
        )

        if os.environ.get("USE_AI_ORCHESTRATOR", "true").lower() in {"0", "false", "no"}:
            return run_deterministic_dispatch(memory_data)
        
        try:
            final_answer = run_react_loop(
                system_prompt=SYSTEM_PROMPT,
                user_message=user_task,
                tools=ORCHESTRATOR_TOOL_SCHEMAS,
                tool_executor=tool_executor,
                max_iterations=20,
                verbose=True
            )

            print("\n--- Orchestrator Loop Complete ---")
            print(f"Final Agent Response: {final_answer}")
            return {"mode": "ai", "final_answer": final_answer}
        except Exception as e:
            print(f"[-] AI orchestrator failed: {e}")
            return run_deterministic_dispatch(memory_data)


def main():
    return run_daily_quiz_job()


if __name__ == "__main__":
    main()
