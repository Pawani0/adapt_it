"""
orchestrator_agent.py -- The main AI brain that oversees the daily quiz process.
"""

import os
import json
from datetime import date
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


def _ordered_unique(items):
    seen = set()
    unique = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _recent_topic_names(memory_data: dict, history_count=1) -> list:
    recent_topics = []
    for profile in memory_data.values():
        for entry in profile.get("quiz_history", [])[-history_count:]:
            recent_topics.extend(entry.get("topics_covered", []))
    return _ordered_unique([topic for topic in recent_topics if topic])


def _rotate_topics_by_day(topics: list) -> list:
    if not topics:
        return []
    offset = date.today().toordinal() % len(topics)
    return topics[offset:] + topics[:offset]


def _choose_fallback_topics(topics, memory_data, max_topics=3):
    """Pick adaptive topics when the LLM is unavailable, rotating away from the last quiz."""
    configured = getattr(config, "QUIZ_TOPICS", [])
    topic_order = _rotate_topics_by_day(topics)
    if configured:
        configured_lower = {topic.lower() for topic in configured}
        selected = [
            topic for topic in topic_order
            if topic["name"].lower() in configured_lower
        ]
        if selected:
            return selected[:max_topics]

    weak_topic_names = []
    for profile in memory_data.values():
        weak_topic_names.extend(profile.get("overall_weak_topics", []))
    weak_lower = {topic.lower() for topic in weak_topic_names}
    recent_lower = {topic.lower() for topic in _recent_topic_names(memory_data)}

    selected = []
    selected_lower = set()

    # Weak topics are intentionally allowed even if they appeared yesterday.
    for topic in topic_order:
        topic_lower = topic["name"].lower()
        if topic_lower in weak_lower and topic_lower not in selected_lower:
            selected.append(topic)
            selected_lower.add(topic_lower)
        if len(selected) >= max_topics:
            return selected[:max_topics]

    for topic in topic_order:
        topic_lower = topic["name"].lower()
        if topic_lower in selected_lower or topic_lower in recent_lower:
            continue
        selected.append(topic)
        selected_lower.add(topic_lower)
        if len(selected) >= max_topics:
            return selected[:max_topics]

    for topic in topic_order:
        topic_lower = topic["name"].lower()
        if topic_lower not in selected_lower:
            selected.append(topic)
            selected_lower.add(topic_lower)
        if len(selected) >= max_topics:
            break

    return selected[:max_topics]


def _print_memory_snapshot(memory_data: dict) -> None:
    """Log the candidate memory that will be used for topic selection."""
    print("[MEMORY] Loaded candidate memory snapshot:")
    if not memory_data:
        print("[MEMORY] {}")
        return

    snapshot = {}
    for email, profile in memory_data.items():
        snapshot[email] = {
            "name": profile.get("name"),
            "total_quizzes": profile.get("total_quizzes", 0),
            "avg_score": profile.get("avg_score"),
            "avg_time_taken": profile.get("avg_time_taken"),
            "overall_weak_topics": profile.get("overall_weak_topics", []),
            "overall_strong_topics": profile.get("overall_strong_topics", []),
            "recent_quiz_history": profile.get("quiz_history", [])[-5:],
        }

    print(json.dumps(snapshot, indent=2, ensure_ascii=False))


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


def _build_context_message(memory_data: dict) -> str:
    """Pre-load candidates, histories, and topics into the user message to skip discovery turns."""
    from agent.tools import _configured_topics

    candidates = config.FRIENDS_LIST
    topics = _configured_topics()

    candidate_summaries = []
    for c in candidates:
        email = c["email"]
        profile = memory_data.get(email, {})
        weak = profile.get("overall_weak_topics", [])
        strong = profile.get("overall_strong_topics", [])
        recent_topics = _recent_topic_names({email: profile})
        avg = profile.get("avg_score", None)
        summary = f"- {c['name']} ({email})"
        if avg is not None:
            summary += f": avg score {avg:.1f}"
        if weak:
            summary += f", weak topics: {', '.join(weak)}"
        if strong:
            summary += f", strong topics: {', '.join(strong)}"
        if recent_topics:
            summary += f", last quiz topics: {', '.join(recent_topics)}"
        candidate_summaries.append(summary)

    topic_lines = "\n".join(f"  - {name}: {url}" for name, url in topics.items())
    recent_topic_names = _recent_topic_names(memory_data)
    recent_topic_text = ", ".join(recent_topic_names) if recent_topic_names else "none"
    configured_topics = ", ".join(config.QUIZ_TOPICS) if config.QUIZ_TOPICS else "adaptive (choose based on weaknesses)"

    return (
        f"It is time for the daily quiz.\n\n"
        f"Candidates ({len(candidates)}):\n" + "\n".join(candidate_summaries) + "\n\n"
        f"Available topics (use these exact URLs):\n{topic_lines}\n\n"
        f"Configured topic filter: {configured_topics}\n"
        f"Most recent quiz topics to avoid repeating tomorrow unless weak: {recent_topic_text}\n\n"
        f"Instructions:\n"
        f"1. Call scrape_topics_batch with 2-3 topics from the list above. Use the exact URLs listed.\n"
        f"2. Do not repeat the most recent quiz topics on consecutive days unless those topics are weak. Prefer topics not covered in the last quiz.\n"
        f"3. Call select_questions with questions=[].\n"
        f"4. Call setup_daily_quiz with the selected questions.\n"
        f"5. Call send_all_quiz_emails with all candidate_links from step 4.\n"
        f"Select exactly {config.QUIZ_QUESTION_COUNT} questions. Do not call get_candidate_history or "
        f"list_available_topics -- that data is already above."
    )


def run_daily_quiz_job(sent_log_backend=None, quiz_setup_backend=None):
    print("--- Starting Orchestrator Agent ---")
    with runtime_backends(
        sent_log_backend=sent_log_backend,
        quiz_setup_backend=quiz_setup_backend
    ):
        memory_data = load_memory()
        _print_memory_snapshot(memory_data)

        if not config.FRIENDS_LIST:
            print("No candidates found in config.FRIENDS_LIST.")
            return {"mode": "noop", "reason": "no_candidates"}

        print(f"Loaded memory for {len(memory_data)} candidates. Proceeding with ReAct loop...")

        if os.environ.get("USE_AI_ORCHESTRATOR", "true").lower() in {"0", "false", "no"}:
            return run_deterministic_dispatch(memory_data)

        user_task = _build_context_message(memory_data)

        try:
            final_answer = run_react_loop(
                system_prompt=SYSTEM_PROMPT,
                user_message=user_task,
                tools=ORCHESTRATOR_TOOL_SCHEMAS,
                tool_executor=tool_executor,
                max_iterations=10,
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