"""
suspicion_agent.py
Sub-agent: triggered by Flask on every quiz submission.
Analyzes if the submission might be cheating.
"""

import threading

from agent.nim_client import simple_completion

SYSTEM_PROMPT = """You are the Quiz Suspicion Agent.
A candidate has just submitted their quiz.
Given their score, time taken (in seconds), tab switches, and historical average score, reason if there are signs of cheating.
Output a short reasoning paragraph and conclude with YES or NO.
"""

_RETRY_DELAY_SECONDS = 300


def analyze_submission(candidate_name: str, candidate_email: str, score: int, time_taken: int, tab_switches: int, avg_score: float, _retry: bool = True):
    try:
        prompt = f"Candidate: {candidate_name} ({candidate_email})\nScore: {score}/5\nTime taken: {time_taken} seconds\nTab switches: {tab_switches}\nHistorical Average: {avg_score}/5\nAre there signs of cheating?"
        reasoning = simple_completion(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=512)

        log_entry = f"--- Suspicion Report ---\nName: {candidate_name}\nEmail: {candidate_email}\nScore: {score}/5\nTime: {time_taken}s\nSwitches: {tab_switches}\nAvg: {avg_score}\nAnalysis:\n{reasoning}\n\n"

        with open("suspicion_report.txt", "a", encoding="utf-8") as f:
            f.write(log_entry)

        print(f"[SuspicionAgent] Analysis complete for {candidate_email}.")
    except Exception as e:
        print(f"[-] SuspicionAgent failed for {candidate_email}: {e}")
        if _retry:
            print(f"[SuspicionAgent] Scheduling retry in {_RETRY_DELAY_SECONDS // 60} min...")
            threading.Timer(
                _RETRY_DELAY_SECONDS,
                analyze_submission,
                args=[candidate_name, candidate_email, score, time_taken, tab_switches, avg_score],
                kwargs={"_retry": False},
            ).start()
        else:
            print(f"[-] SuspicionAgent retry also failed for {candidate_email}. Giving up.")

if __name__ == "__main__":
    analyze_submission("Test", "test@example.com", 5, 20, 10, 1.0)
