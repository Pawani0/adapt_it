"""
feedback_agent.py
Sub-agent: triggered by Flask on every quiz submission.
Generates personalized explanation and sends email.
"""

import threading

from agent.nim_client import simple_completion
from agent.tools import tool_send_feedback_email

SYSTEM_PROMPT = """You are the Quiz Feedback Agent.
The candidate has just submitted their quiz.
Analyze their score and answers, and generate a polite, encouraging, step-by-step personalized feedback email body.
You MUST include a clear explanation for EVERY question the candidate got wrong — do not skip or truncate any.
For each wrong answer, show: the question title, their answer, the correct answer, and a brief step-by-step explanation.
Use plain text with clear separators (---) between questions. Do not use markdown headers or bullet lists.
"""

_RETRY_DELAY_SECONDS = 300  # 5 minutes — matches typical RPM reset window


def process_feedback(candidate_name: str, candidate_email: str, quiz_data: list, score: int, _retry: bool = True):
    try:
        wrong = [q for q in quiz_data if str(q.get("user_answer", "")).strip().upper() != str(q.get("correct_answer", "")).strip().upper()]
        total = len(quiz_data)

        wrong_text = ""
        for i, q in enumerate(wrong, 1):
            wrong_text += (
                f"\nQ{i}. {q.get('question_text') or q.get('text', 'Unknown question')}\n"
                f"   Options: {q.get('options', '')}\n"
                f"   Their answer: {q.get('user_answer', '')}\n"
                f"   Correct answer: {q.get('correct_answer', '')}\n"
                f"   Topic: {q.get('topic', '')}\n"
            )

        prompt = (
            f"Candidate: {candidate_name}\n"
            f"Score: {score} out of {total}\n"
            f"Number of wrong answers: {len(wrong)}\n\n"
            f"Wrong answers to explain (explain ALL {len(wrong)} of them):\n"
            f"{wrong_text}\n"
            f"Generate the complete feedback email body covering every wrong answer above."
        )
        body = simple_completion(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=4096)
        print(f"[FeedbackAgent] Sending feedback to {candidate_email}...")
        tool_send_feedback_email({
            "name": candidate_name,
            "email": candidate_email,
            "body": body
        })
        print("[FeedbackAgent] Feedback sent.")
    except Exception as e:
        print(f"[-] FeedbackAgent failed for {candidate_email}: {e}")
        if _retry:
            print(f"[FeedbackAgent] Scheduling retry in {_RETRY_DELAY_SECONDS // 60} min (RPM reset)...")
            threading.Timer(
                _RETRY_DELAY_SECONDS,
                process_feedback,
                args=[candidate_name, candidate_email, quiz_data, score],
                kwargs={"_retry": False},
            ).start()
        else:
            print(f"[-] FeedbackAgent retry also failed for {candidate_email}. Giving up.")

if __name__ == "__main__":
    process_feedback("Test", "test@example.com", {"q1": "wrong"}, 0)
