import json
import os
import random

try:
    import config
except ImportError:
    config = None


def _default_question_count():
    return getattr(config, "QUIZ_QUESTION_COUNT", 5)

def load_sent_log(filepath="sent_log.json"):
    """Loads already-sent question IDs from a JSON file."""
    if not os.path.exists(filepath):
        return set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data)
    except Exception as e:
        print(f"[-] Warning: Failed to load sent log: {e}")
        return set()

def save_sent_log(sent_ids, filepath="sent_log.json"):
    """Saves a list of sent question IDs to a JSON file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(list(sent_ids), f, indent=2)
        return True
    except Exception as e:
        print(f"[-] Error: Failed to save sent log: {e}")
        return False

def filter_new_questions(scraped_questions, sent_ids):
    """Filters out questions that have already been sent."""
    return [q for q in scraped_questions if q['id'] not in sent_ids]

def pick_daily_questions(questions, count=None):
    """Randomly picks N questions from the available pool."""
    if count is None:
        count = _default_question_count()

    if len(questions) < count:
        print(f"[-] Warning: Only {len(questions)} questions available, but requested {count}.")
        return questions # Return all if not enough
    return random.sample(questions, count)

def update_sent_log(picked_questions, sent_ids, filepath="sent_log.json"):
    """Adds the newly picked question IDs to the log and saves the log."""
    new_ids = {q['id'] for q in picked_questions}
    updated_ids = sent_ids.union(new_ids)
    save_sent_log(updated_ids, filepath)
    return updated_ids

def run_tracker_test():
    """Verify that tracker picks correctly and prevents repeats."""
    print("[*] Starting Tracker Verification...")
    temp_log = "test_sent_log.json"
    if os.path.exists(temp_log):
        os.remove(temp_log)
        
    mock_questions = [
        {"id": f"q_{i}", "question": f"Question text {i}", "options": ["A", "B", "C", "D"], "answer": "A"}
        for i in range(1, 11)
    ]
    
    # 1. First run
    sent_ids = load_sent_log(temp_log)
    available = filter_new_questions(mock_questions, sent_ids)
    picked = pick_daily_questions(available)
    update_sent_log(picked, sent_ids, temp_log)
    
    print(f"[+] Run 1: Selected {[q['id'] for q in picked]}")
    
    # 2. Second run
    sent_ids_2 = load_sent_log(temp_log)
    available_2 = filter_new_questions(mock_questions, sent_ids_2)
    picked_2 = pick_daily_questions(available_2)
    
    print(f"[+] Run 2: Selected {[q['id'] for q in picked_2]}")
    
    # Confirm no overlap
    overlap = set(q['id'] for q in picked).intersection(set(q['id'] for q in picked_2))
    if not overlap:
        print("[+] Success: No repeated questions selected between runs!")
    else:
        print(f"[-] Failure: Overlapping questions found: {overlap}")
        
    # Cleanup
    if os.path.exists(temp_log):
        os.remove(temp_log)

if __name__ == "__main__":
    run_tracker_test()
