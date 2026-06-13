"""
tools.py — All tool definitions for the OrchestratorAgent.

Each tool has:
  1. A Python function  — the actual implementation
  2. A JSON schema      — passed to the LLM so it knows what tools exist

The TOOL_EXECUTOR function maps tool names → function calls and is passed
to nim_client.run_react_loop().
"""

import json
import time
import uuid
import sys
import os
import sqlite3
import concurrent.futures

# Allow imports from parent project directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
import scraper
import emailer
import tracker
import config
import db
from agent import memory
from contextlib import contextmanager
from contextvars import ContextVar


# In-memory cache: stores the full scraped question pool so the LLM only
# receives a slim summary, not the full question text on every iteration.
_SCRAPED_QUESTION_CACHE: list = []

# ─── Available IndiaBix Topics ───────────────────────────────────────────────

INDIABIX_TOPICS = {
    "Problems on Trains":    "https://www.indiabix.com/aptitude/problems-on-trains/",
    "Height and Distance":   "https://www.indiabix.com/aptitude/height-and-distance/",
    "Simple Interest":       "https://www.indiabix.com/aptitude/simple-interest/",
    "Compound Interest":     "https://www.indiabix.com/aptitude/compound-interest/",
    "Percentage":            "https://www.indiabix.com/aptitude/percentage/",
    "Profit and Loss":       "https://www.indiabix.com/aptitude/profit-and-loss/",
    "Time and Work":         "https://www.indiabix.com/aptitude/time-and-work/",
    "Time and Distance":     "https://www.indiabix.com/aptitude/time-and-distance/",
    "Average":               "https://www.indiabix.com/aptitude/average/",
    "Ratio and Proportion":  "https://www.indiabix.com/aptitude/ratio-and-proportion/",
    "Numbers":               "https://www.indiabix.com/aptitude/numbers/",
    "Probability":           "https://www.indiabix.com/aptitude/probability/",
    "Permutation and Combination": "https://www.indiabix.com/aptitude/permutation-and-combination/",
    "Pipes and Cisterns":    "https://www.indiabix.com/aptitude/pipes-and-cisterns/",
    "Boats and Streams":     "https://www.indiabix.com/aptitude/boats-and-streams/",
}


def _configured_topics():
    configured = getattr(config, "QUIZ_TOPICS", [])
    if not configured:
        return INDIABIX_TOPICS

    selected = {
        name: url
        for name, url in INDIABIX_TOPICS.items()
        if name.lower() in {topic.lower() for topic in configured}
    }

    missing = [topic for topic in configured if topic.lower() not in {name.lower() for name in INDIABIX_TOPICS}]
    if missing:
        print(f"[-] Unknown configured quiz topics ignored: {', '.join(missing)}")

    return selected or INDIABIX_TOPICS


def _admin_headers():
    return {
        "X-API-Key": config.ADMIN_API_KEY,
        "Content-Type": "application/json"
    }


_SENT_LOG_BACKEND = ContextVar("sent_log_backend", default=None)
_QUIZ_SETUP_BACKEND = ContextVar("quiz_setup_backend", default=None)


@contextmanager
def runtime_backends(sent_log_backend=None, quiz_setup_backend=None):
    sent_token = _SENT_LOG_BACKEND.set(sent_log_backend)
    setup_token = _QUIZ_SETUP_BACKEND.set(quiz_setup_backend)
    try:
        yield
    finally:
        _SENT_LOG_BACKEND.reset(sent_token)
        _QUIZ_SETUP_BACKEND.reset(setup_token)


def _sent_log_backend():
    backend = _SENT_LOG_BACKEND.get()
    if backend:
        return backend
    return os.environ.get("SENT_LOG_BACKEND", "local").lower()


def _quiz_setup_backend():
    backend = _QUIZ_SETUP_BACKEND.get()
    if backend:
        return backend
    return os.environ.get("QUIZ_SETUP_BACKEND", "remote").lower()


def _load_database_sent_ids():
    db.initialize_schema()
    with db.connect() as conn:
        rows = conn.execute("SELECT id FROM sent_questions").fetchall()
    return set(row["id"] for row in rows)


def _record_database_sent_questions(questions):
    db.initialize_schema()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    with db.connect() as conn:
        for q in questions:
            q_id = q.get("id")
            if not q_id:
                continue
            conn.execute(
                """
                INSERT INTO sent_questions (id, question_text, topic, first_sent_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (id) DO NOTHING
                """,
                (q_id, q.get("question", ""), q.get("topic", ""), now)
            )
    return True


def _setup_quiz_direct(questions, tokens, deadline_epoch):
    db.initialize_schema()
    with db.connect() as conn:
        conn.execute("DELETE FROM questions")
        conn.execute("DELETE FROM tokens")
        conn.execute("DELETE FROM settings")
        for q in questions:
            conn.execute(
                "INSERT INTO questions (id, text, options_json, correct_answer) VALUES (?, ?, ?, ?)",
                (q["id"], q["question"], json.dumps(q["options"]), q["answer"])
            )
        for token in tokens:
            conn.execute(
                "INSERT INTO tokens (token, name, email) VALUES (?, ?, ?)",
                (token["token"], token["name"], token["email"])
            )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("deadline_epoch", str(deadline_epoch))
        )
    return True


def _load_remote_sent_ids():
    try:
        response = requests.get(
            f"{config.QUIZ_BASE_URL}/api/sent-questions",
            headers=_admin_headers(),
            timeout=30
        )
        if response.status_code == 200:
            return set(response.json().get("ids", []))
        print(f"[-] Remote sent-log load failed: HTTP {response.status_code} {response.text[:200]}")
    except Exception as e:
        print(f"[-] Remote sent-log load failed: {e}")
    return None


def _record_remote_sent_questions(questions):
    try:
        response = requests.post(
            f"{config.QUIZ_BASE_URL}/api/sent-questions",
            json={"questions": questions},
            headers=_admin_headers(),
            timeout=30
        )
        if response.status_code == 200:
            return True
        print(f"[-] Remote sent-log update failed: HTTP {response.status_code} {response.text[:200]}")
    except Exception as e:
        print(f"[-] Remote sent-log update failed: {e}")
    return False


def _use_remote_sent_log():
    return _sent_log_backend() == "server"


# ─── Tool Implementations ────────────────────────────────────────────────────

def tool_list_available_topics(_args: dict) -> dict:
    """Return all available topic names and their URLs."""
    topics = _configured_topics()
    return {
        "topics": [
            {"name": name, "url": url}
            for name, url in topics.items()
        ],
        "configured_topics_only": bool(getattr(config, "QUIZ_TOPICS", []))
    }


def tool_get_candidate_history(args: dict) -> dict:
    """Get a candidate's quiz history from persistent memory."""
    email = args.get("email", "")
    profile = memory.get_candidate(email)
    summary = memory.format_history_for_agent(email)
    return {"profile": profile, "summary": summary}


def tool_get_all_candidates(_args: dict) -> dict:
    """Return the list of all configured candidates."""
    return {"candidates": config.FRIENDS_LIST}


def tool_scrape_topic(args: dict) -> dict:
    """Scrape MCQ questions from an IndiaBix topic URL."""
    topic_url = args.get("topic_url", "")
    topic_name = args.get("topic_name", "Unknown")
    max_q = args.get("max_questions", max(10, getattr(config, "QUIZ_QUESTION_COUNT", 5)))

    print(f"[TOOL] Scraping topic: {topic_name} ({topic_url})")
    questions = scraper.scrape_indiabix_topic(topic_url, max_questions=max_q)

    # Tag each question with its topic name for memory tracking
    for q in questions:
        q["topic"] = topic_name

    return {
        "topic": topic_name,
        "url": topic_url,
        "count": len(questions),
        "questions": questions
    }


def tool_select_questions(args: dict) -> dict:
    """
    Pick the configured number of questions from the provided pool, filtering out already-sent ones.
    Updates sent_log.json by default, or the deployed server sent log when SENT_LOG_BACKEND=server.
    """
    questions = args.get("questions", [])
    if not questions and _SCRAPED_QUESTION_CACHE:
        print("[TOOL] select_questions: using cached scrape results.")
        questions = _SCRAPED_QUESTION_CACHE
    count = args.get("count", getattr(config, "QUIZ_QUESTION_COUNT", 5))

    sent_log_source = "sent_log.json"
    sent_ids = None
    backend = _sent_log_backend()
    if backend == "database":
        sent_log_source = "database"
        sent_ids = _load_database_sent_ids()
    elif backend == "server":
        sent_log_source = "server"
        sent_ids = _load_remote_sent_ids()

    if sent_ids is None:
        sent_log_source = "sent_log.json"
        sent_ids = tracker.load_sent_log("sent_log.json")

    fresh = tracker.filter_new_questions(questions, sent_ids)

    if len(fresh) < count:
        print(f"[-] Only {len(fresh)} fresh questions available. Recycling pool.")
        fresh = questions  # Recycle if needed

    picked = tracker.pick_daily_questions(fresh, count)
    if sent_log_source == "database":
        _record_database_sent_questions(picked)
    elif sent_log_source == "server":
        if not _record_remote_sent_questions(picked):
            tracker.update_sent_log(picked, sent_ids, "sent_log.json")
            sent_log_source = "sent_log.json"
    else:
        tracker.update_sent_log(picked, sent_ids, "sent_log.json")

    return {
        "selected_count": len(picked),
        "questions": picked,
        "topics_covered": list({q.get("topic", "Unknown") for q in picked}),
        "sent_log_source": sent_log_source
    }


def tool_setup_daily_quiz(args: dict) -> dict:
    """
    Push selected questions and candidate tokens to the Flask quiz server.
    Returns per-candidate quiz links for use in email sending.
    """
    questions = args.get("questions", [])
    candidates = args.get("candidates", config.FRIENDS_LIST)

    # Generate UUID tokens per candidate
    tokens = []
    for candidate in candidates:
        token = str(uuid.uuid4())
        tokens.append({
            "token": token,
            "name": candidate["name"],
            "email": candidate["email"],
            "link": f"{config.QUIZ_BASE_URL}/quiz/{token}"
        })

    result_deadline_hours = getattr(config, "QUIZ_RESULT_DEADLINE_HOURS", 12)
    deadline_epoch = int(time.time() + result_deadline_hours * 3600)

    payload = {
        "questions": questions,
        "tokens": [{"token": t["token"], "name": t["name"], "email": t["email"]} for t in tokens],
        "deadline_epoch": deadline_epoch
    }
    if _quiz_setup_backend() == "direct":
        success = _setup_quiz_direct(
            questions,
            [{"token": t["token"], "name": t["name"], "email": t["email"]} for t in tokens],
            deadline_epoch
        )
        return {
            "success": success,
            "candidate_links": tokens,
            "deadline_epoch": deadline_epoch
        }

    try:
        response = requests.post(
            f"{config.QUIZ_BASE_URL}/api/setup-quiz",
            json=payload,
            headers=_admin_headers(),
            timeout=30
        )
        success = response.status_code == 200
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {
        "success": success,
        "candidate_links": tokens,
        "deadline_epoch": deadline_epoch
    }


def tool_send_quiz_email(args: dict) -> dict:
    """Send a quiz invitation email to a single candidate."""
    name  = args.get("name", "")
    email = args.get("email", "")
    link  = args.get("link", "")

    success = emailer.send_quiz_email(name, email, link)
    return {"sent": success, "name": name, "email": email}


def tool_update_candidate_memory(args: dict) -> dict:
    """Record a quiz result into the candidate's persistent memory profile."""
    memory.update_candidate(
        email          = args["email"],
        name           = args["name"],
        score          = args["score"],
        total          = args["total"],
        topics_covered = args.get("topics_covered", []),
        tab_switches   = args.get("tab_switches", 0),
        time_taken     = args.get("time_taken", 0),
        date           = args.get("date")
    )
    return {"updated": True, "email": args["email"]}


def tool_get_todays_submissions(_args: dict) -> dict:
    """Fetch all submitted quiz results from today's SQLite database."""
    try:
        db.initialize_schema()
        with db.connect() as conn:
            rows = conn.execute(
            "SELECT * FROM tokens WHERE submitted_at IS NOT NULL"
        ).fetchall()

        submissions = []
        for row in rows:
            submissions.append({
                "name":         row["name"],
                "email":        row["email"],
                "score":        row["score"],
                "time_taken":   row["time_taken"],
                "tab_switches": row["tab_switches"],
                "submitted_at": row["submitted_at"],
                "answers":      row["answers"]
            })
        return {"count": len(submissions), "submissions": submissions}
    except Exception as e:
        return {"error": str(e), "submissions": []}


def tool_scrape_topics_batch(args: dict) -> dict:
    """Scrape multiple IndiaBix topics in parallel and return the combined question pool."""
    global _SCRAPED_QUESTION_CACHE
    topics = args.get("topics", [])
    max_q = args.get("max_questions_per_topic", max(10, getattr(config, "QUIZ_QUESTION_COUNT", 5)))

    def _scrape_one(topic):
        url = topic.get("topic_url", "")
        name = topic.get("topic_name", "Unknown")
        print(f"[TOOL] Scraping topic: {name} ({url})")
        questions = scraper.scrape_indiabix_topic(url, max_questions=max_q)
        for q in questions:
            q["topic"] = name
        return questions

    all_questions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(topics) or 1) as executor:
        futures = {executor.submit(_scrape_one, t): t for t in topics}
        for future in concurrent.futures.as_completed(futures):
            try:
                all_questions.extend(future.result())
            except Exception as e:
                topic_name = futures[future].get("topic_name", "?")
                print(f"[-] Failed to scrape {topic_name}: {e}")

    _SCRAPED_QUESTION_CACHE = all_questions

    # Return only a slim summary to the LLM — full data lives in the cache
    # and will be used automatically by select_questions.
    by_topic = {}
    for q in all_questions:
        by_topic.setdefault(q.get("topic", "Unknown"), 0)
        by_topic[q["topic"]] += 1

    return {
        "total_scraped": len(all_questions),
        "topics_scraped": list(by_topic.keys()),
        "questions_per_topic": by_topic,
        "note": "Full question data cached. Call select_questions with questions=[] to use the cache."
    }


def tool_send_all_quiz_emails(args: dict) -> dict:
    """Send quiz invitation emails sequentially, capped at 2 emails/sec (Resend limit)."""
    candidate_links = args.get("candidate_links", [])

    results = []
    for i, candidate in enumerate(candidate_links):
        if i > 0:
            time.sleep(0.55)  # stay just under the 2/sec Resend rate limit
        try:
            success = emailer.send_quiz_email(
                candidate.get("name", ""),
                candidate.get("email", ""),
                candidate.get("link", "")
            )
            results.append({"sent": success, "name": candidate.get("name"), "email": candidate.get("email")})
        except Exception as e:
            results.append({"sent": False, "name": candidate.get("name"), "error": str(e)})

    sent_count = sum(1 for r in results if r.get("sent"))
    print(f"[+] Emails sent: {sent_count}/{len(candidate_links)}")
    return {"sent_count": sent_count, "total": len(candidate_links), "results": results}


def tool_send_feedback_email(args: dict) -> dict:
    """Sends a personalized feedback email to a candidate."""
    name  = args.get("name", "")
    email = args.get("email", "")
    body  = args.get("body", "")
    
    success = emailer.send_feedback_email(name, email, body)
    if success:
        return {"status": "success", "message": f"Feedback email sent to {email}"}
    return {"status": "error", "message": f"Failed to send feedback to {email}"}


# ─── Tool Registry ────────────────────────────────────────────────────────────

_TOOL_MAP = {
    "list_available_topics":    tool_list_available_topics,
    "get_candidate_history":    tool_get_candidate_history,
    "get_all_candidates":       tool_get_all_candidates,
    "scrape_topic":             tool_scrape_topic,
    "scrape_topics_batch":      tool_scrape_topics_batch,
    "select_questions":         tool_select_questions,
    "setup_daily_quiz":         tool_setup_daily_quiz,
    "send_quiz_email":          tool_send_quiz_email,
    "send_all_quiz_emails":     tool_send_all_quiz_emails,
    "send_feedback_email":      tool_send_feedback_email,
    "update_candidate_memory":  tool_update_candidate_memory,
    "get_todays_submissions":   tool_get_todays_submissions,
}


def tool_executor(tool_name: str, tool_args: dict):
    """Dispatch a tool call by name. Used by nim_client.run_react_loop()."""
    fn = _TOOL_MAP.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: {tool_name}"}
    return fn(tool_args)


# ─── JSON Schemas for the LLM ─────────────────────────────────────────────────

ORCHESTRATOR_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_available_topics",
            "description": (
                "List all available IndiaBix aptitude topics with their URLs. "
                "Call this first to see what topics you can scrape."
            ),
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_candidates",
            "description": "Get the list of all candidates who should receive today's quiz.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_candidate_history",
            "description": (
                "Get a candidate's quiz performance history including average score, "
                "weak topics, strong topics, and last 3 results. "
                "Use this to decide which topics to focus on for today's quiz."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "The candidate's email address"
                    }
                },
                "required": ["email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_topic",
            "description": (
                "Scrape MCQ questions from a single IndiaBix topic URL. "
                "Prefer scrape_topics_batch when scraping more than one topic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic_url":  {"type": "string", "description": "The IndiaBix topic URL"},
                    "topic_name": {"type": "string", "description": "Human-readable topic name"},
                    "max_questions": {
                        "type": "integer",
                        "description": "Max questions to scrape",
                        "default": max(10, getattr(config, "QUIZ_QUESTION_COUNT", 5))
                    }
                },
                "required": ["topic_url", "topic_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_topics_batch",
            "description": (
                "Scrape multiple IndiaBix topics in parallel in a single call. "
                "Use this instead of calling scrape_topic multiple times — it is much faster."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topics": {
                        "type": "array",
                        "description": "List of topics to scrape in parallel",
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic_url":  {"type": "string"},
                                "topic_name": {"type": "string"}
                            },
                            "required": ["topic_url", "topic_name"]
                        }
                    },
                    "max_questions_per_topic": {
                        "type": "integer",
                        "description": "Max questions to scrape per topic",
                        "default": max(10, getattr(config, "QUIZ_QUESTION_COUNT", 5))
                    }
                },
                "required": ["topics"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_questions",
            "description": (
                "Pick the configured number of questions from the pool of scraped questions. "
                "Automatically filters out already-sent questions and updates the log."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "description": "The combined pool of scraped questions",
                        "items": {"type": "object"}
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of questions to pick",
                        "default": getattr(config, "QUIZ_QUESTION_COUNT", 5)
                    }
                },
                "required": ["questions"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "setup_daily_quiz",
            "description": (
                "Push the selected questions and candidate list to the Flask quiz server. "
                "Returns per-candidate quiz links to use when sending emails."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "description": "The selected quiz questions",
                        "items": {"type": "object"}
                    },
                    "candidates": {
                        "type": "array",
                        "description": "List of candidates with name and email",
                        "items": {"type": "object"}
                    }
                },
                "required": ["questions", "candidates"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_quiz_email",
            "description": (
                "Send the quiz invitation email to one candidate. "
                "Prefer send_all_quiz_emails when emailing more than one candidate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name":  {"type": "string", "description": "Candidate's name"},
                    "email": {"type": "string", "description": "Candidate's email"},
                    "link":  {"type": "string", "description": "The unique quiz URL for this candidate"}
                },
                "required": ["name", "email", "link"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_all_quiz_emails",
            "description": (
                "Send quiz invitation emails to all candidates in parallel in a single call. "
                "Pass the candidate_links list returned by setup_daily_quiz directly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_links": {
                        "type": "array",
                        "description": "The candidate_links list from setup_daily_quiz",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name":  {"type": "string"},
                                "email": {"type": "string"},
                                "link":  {"type": "string"}
                            },
                            "required": ["name", "email", "link"]
                        }
                    }
                },
                "required": ["candidate_links"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_todays_submissions",
            "description": "Fetch all quiz submissions recorded in today's database.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]
