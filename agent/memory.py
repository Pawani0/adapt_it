"""
memory.py — Persistent candidate performance memory.

Stores each candidate's quiz history in candidate_memory.json so the
OrchestratorAgent can reason about weak topics and adapt questions over time.
"""

import json
import os
from datetime import datetime
from typing import Optional
import db

MEMORY_FILE = os.environ.get("CANDIDATE_MEMORY_FILE", "candidate_memory.json")


# ─── Read / Write ────────────────────────────────────────────────────────────

def _load() -> dict:
    """Load the full memory file. Returns empty dict if it doesn't exist."""
    if db.using_postgres():
        db.initialize_schema()
        with db.connect() as conn:
            rows = conn.execute("SELECT email, payload_json FROM candidate_memory").fetchall()
        return {
            row["email"]: json.loads(row["payload_json"])
            for row in rows
        }

    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[-] Memory load error: {e}. Starting fresh.")
        return {}


def _save(data: dict) -> None:
    """Persist memory dict to disk."""
    if db.using_postgres():
        db.initialize_schema()
        with db.connect() as conn:
            conn.execute("DELETE FROM candidate_memory")
            for email, payload in data.items():
                conn.execute(
                    "INSERT INTO candidate_memory (email, payload_json) VALUES (?, ?)",
                    (email, json.dumps(payload, ensure_ascii=False))
                )
        return

    memory_dir = os.path.dirname(MEMORY_FILE)
    if memory_dir:
        os.makedirs(memory_dir, exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── Public API ──────────────────────────────────────────────────────────────

def get_candidate(email: str) -> dict:
    """
    Return a candidate's full history profile.
    If candidate has no history, returns a default profile.
    """
    data = _load()
    if email not in data:
        return {
            "email": email,
            "name": "Unknown",
            "total_quizzes": 0,
            "avg_score": None,
            "avg_time_taken": None,
            "overall_weak_topics": [],
            "overall_strong_topics": [],
            "quiz_history": [],
            "note": "No history yet. This is a new candidate."
        }
    return data[email]


def get_all_history() -> dict:
    """Return the full memory dict (all candidates)."""
    return _load()


def update_candidate(
    email: str,
    name: str,
    score: int,
    total: int,
    topics_covered: list,
    tab_switches: int,
    time_taken: int,
    date: Optional[str] = None
) -> None:
    """
    Record a new quiz result for a candidate and update their aggregate stats.

    Args:
        email:          Candidate email (primary key).
        name:           Candidate display name.
        score:          Number of correct answers.
        total:          Total number of questions.
        topics_covered: List of topic names covered in this quiz.
        tab_switches:   Number of browser focus losses.
        time_taken:     Seconds taken to complete the quiz.
        date:           Date string (YYYY-MM-DD). Defaults to today.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    data = _load()

    # Initialise profile if first time
    if email not in data:
        data[email] = {
            "email": email,
            "name": name,
            "total_quizzes": 0,
            "avg_score": 0.0,
            "avg_time_taken": 0.0,
            "overall_weak_topics": [],
            "overall_strong_topics": [],
            "quiz_history": []
        }

    profile = data[email]
    profile["name"] = name  # Keep name up to date

    # Append history entry
    entry = {
        "date": date,
        "score": score,
        "total": total,
        "percentage": round(score / total * 100) if total else 0,
        "topics_covered": topics_covered,
        "tab_switches": tab_switches,
        "time_taken": time_taken
    }
    profile["quiz_history"].append(entry)
    profile["total_quizzes"] += 1

    # Recalculate aggregates
    all_scores = [h["score"] for h in profile["quiz_history"]]
    all_times  = [h["time_taken"] for h in profile["quiz_history"]]
    profile["avg_score"]      = round(sum(all_scores) / len(all_scores), 2)
    profile["avg_time_taken"] = round(sum(all_times)  / len(all_times),  1)

    # Identify weak/strong topics across last 5 quizzes
    recent = profile["quiz_history"][-5:]
    topic_scores: dict = {}
    for h in recent:
        pct = h["percentage"]
        for t in h.get("topics_covered", []):
            if t not in topic_scores:
                topic_scores[t] = []
            topic_scores[t].append(pct)

    weak, strong = [], []
    for topic, pcts in topic_scores.items():
        avg_pct = sum(pcts) / len(pcts)
        if avg_pct < 50:
            weak.append(topic)
        elif avg_pct >= 75:
            strong.append(topic)

    profile["overall_weak_topics"]   = weak
    profile["overall_strong_topics"] = strong

    data[email] = profile
    _save(data)
    print(f"[+] Memory updated for {name} ({email}): {score}/{total} on {date}")


def format_history_for_agent(email: str) -> str:
    """
    Format a candidate's history as a readable string for the LLM prompt.
    """
    profile = get_candidate(email)
    if profile["total_quizzes"] == 0:
        return f"No history for {email}. Treat as a new candidate — use a balanced topic mix."

    lines = [
        f"Candidate: {profile['name']} ({email})",
        f"Total quizzes taken: {profile['total_quizzes']}",
        f"Average score: {profile['avg_score']}",
        f"Average time taken: {profile['avg_time_taken']}s",
        f"Weak topics (score < 50%): {', '.join(profile['overall_weak_topics']) or 'None identified yet'}",
        f"Strong topics (score ≥ 75%): {', '.join(profile['overall_strong_topics']) or 'None identified yet'}",
        "",
        "Last 3 quiz results:",
    ]
    for h in profile["quiz_history"][-3:]:
        lines.append(
            f"  - {h['date']}: {h['score']}/{h['total']} "
            f"({h['percentage']}%) | Topics: {', '.join(h.get('topics_covered', []))} "
            f"| Tab switches: {h['tab_switches']} | Time: {h['time_taken']}s"
        )
    return "\n".join(lines)
