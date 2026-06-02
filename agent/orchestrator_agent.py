"""
orchestrator_agent.py — The main AI brain that oversees the daily quiz process.
"""

import sys
import os
import json
from agent.nim_client import run_react_loop
from agent.tools import ORCHESTRATOR_TOOL_SCHEMAS, tool_executor
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

def main():
    print("--- Starting Orchestrator Agent ---")
    memory_data = load_memory()
    
    # Check if we have friends to send to
    if not config.FRIENDS_LIST:
        print("No candidates found in config.FRIENDS_LIST.")
        return

    print(f"Loaded memory for {len(memory_data)} candidates. Proceeding with ReAct loop...")
    
    # Run the ReAct agent cycle
    configured_topics = ", ".join(config.QUIZ_TOPICS) if config.QUIZ_TOPICS else "adaptive topic selection"
    user_task = (
        "It is time for the daily quiz. "
        f"Use {configured_topics}. "
        f"Select exactly {config.QUIZ_QUESTION_COUNT} questions and send it to all candidates."
    )
    
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


if __name__ == "__main__":
    main()
