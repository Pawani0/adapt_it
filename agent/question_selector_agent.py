"""
question_selector_agent.py
Sub-agent: decides which topics and difficulty to use today.
"""

from agent.nim_client import simple_completion

SYSTEM_PROMPT = """You are the Question Selector Agent.
Given a list of candidates, their past scores, and their weak topics, recommend 3 to 5 topic URLs to scrape for today's daily aptitude quiz.
Consider their weaknesses and output a JSON array of URLs ONLY.
"""

def select_topics(candidates_context: str) -> str:
    prompt = f"Candidates context:\n{candidates_context}\n\nSelect appropriate topics."
    response = simple_completion(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=1024)
    return response

if __name__ == "__main__":
    print(select_topics("Alex scored 2/5 and is weak in 'height-distance'. Dana scored 4/5."))
