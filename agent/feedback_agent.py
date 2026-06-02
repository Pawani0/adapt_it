"""
feedback_agent.py
Sub-agent: triggered by Flask on every quiz submission.
Generates personalized explanation and sends email.
"""

from agent.nim_client import simple_completion
from agent.tools import tool_send_feedback_email

SYSTEM_PROMPT = """You are the Quiz Feedback Agent.
The candidate has just submitted their quiz.
Analyze their score and answers, and generate a polite, encouraging, step-by-step personalized feedback email body.
Keep it strictly under 500 words. Focus on explaining the questions they got wrong.
"""

def process_feedback(candidate_name: str, candidate_email: str, quiz_data: dict, score: int):
    prompt = f"Candidate: {candidate_name}\nScore: {score}\nQuiz Data: {str(quiz_data)}\nGenerate feedback email content."
    body = simple_completion(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=1024)
    print(f"[FeedbackAgent] Sending feedback to {candidate_email}...")
    
    # Call the email tool
    tool_send_feedback_email({
        "name": candidate_name,
        "email": candidate_email,
        "body": body
    })
    print("[FeedbackAgent] Feedback sent.")

if __name__ == "__main__":
    process_feedback("Test", "test@example.com", {"q1": "wrong"}, 0)
