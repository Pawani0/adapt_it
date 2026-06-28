import os
import json
import threading
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
import db

app = Flask(__name__)

# Ensure templates directory is recognized
app.template_folder = os.path.abspath('templates')

DAILY_JOB_STATUS = {
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "last_state": "idle",
    "last_result": None,
    "last_error": None,
}

def get_db():
    return db.connect()

def init_db():
    db.initialize_schema()

init_db()

# Import config (will be created in later phases)
try:
    import config
except ImportError:
    # Fallback configuration for testing
    class DummyConfig:
        ADMIN_API_KEY = "testkey"
        QUIZ_DEADLINE_HOUR = 21  # 9 PM IST
        QUIZ_DEADLINE_MINUTE = 0
        QUIZ_TIME_LIMIT_MINUTES = 15
        QUIZ_SUBMISSION_BUFFER_SECONDS = 45
    config = DummyConfig()

def get_deadline_passed():
    """Helper to check if the submission deadline has passed for the day."""
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'deadline_epoch'").fetchone()
        if row:
            try:
                deadline_epoch = float(row['value'])
                return datetime.now().timestamp() >= deadline_epoch
            except ValueError:
                pass
                
    # Fallback to daily 9 PM local time if not explicitly set
    now = datetime.now()
    deadline = now.replace(hour=config.QUIZ_DEADLINE_HOUR, minute=config.QUIZ_DEADLINE_MINUTE, second=0, microsecond=0)
    return now >= deadline

@app.route('/', methods=['GET'])
def health_check():
    """Simple health endpoint for deployment platforms and uptime checks."""
    return jsonify({"status": "ok", "service": "daily-aptitude-quiz"})

def require_admin_api_key():
    api_key = request.headers.get('X-API-Key')
    expected_key = getattr(config, 'ADMIN_API_KEY', 'testkey')
    if not api_key or api_key != expected_key:
        return jsonify({"error": "Unauthorized"}), 401
    return None


def _run_daily_quiz_background():
    from agent.orchestrator_agent import run_daily_quiz_job

    DAILY_JOB_STATUS["running"] = True
    DAILY_JOB_STATUS["last_state"] = "running"
    DAILY_JOB_STATUS["last_started_at"] = datetime.now().isoformat()
    DAILY_JOB_STATUS["last_error"] = None

    try:
        result = run_daily_quiz_job(
            sent_log_backend="database",
            quiz_setup_backend="direct"
        )
        DAILY_JOB_STATUS["last_result"] = result
        DAILY_JOB_STATUS["last_state"] = "succeeded"
    except Exception as e:
        import traceback
        print(f"[-] Daily quiz job failed: {e}")
        traceback.print_exc()
        DAILY_JOB_STATUS["last_error"] = str(e)
        DAILY_JOB_STATUS["last_state"] = "failed"
    finally:
        DAILY_JOB_STATUS["running"] = False
        DAILY_JOB_STATUS["last_finished_at"] = datetime.now().isoformat()

@app.route('/api/sent-questions', methods=['GET'])
def get_sent_questions():
    """Return sent question IDs for the Render cron dispatcher."""
    auth_error = require_admin_api_key()
    if auth_error:
        return auth_error

    with get_db() as conn:
        rows = conn.execute("SELECT id FROM sent_questions").fetchall()

    return jsonify({"ids": [row["id"] for row in rows]}), 200

@app.route('/api/sent-questions', methods=['POST'])
def record_sent_questions():
    """Persist selected question IDs so cron runs avoid repeats."""
    auth_error = require_admin_api_key()
    if auth_error:
        return auth_error

    data = request.get_json() or {}
    questions = data.get("questions", [])
    now = datetime.now().isoformat()

    with get_db() as conn:
        for q in questions:
            q_id = q.get("id")
            if not q_id:
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO sent_questions (id, question_text, topic, first_sent_at)
                VALUES (?, ?, ?, ?)
                """,
                (q_id, q.get("question", ""), q.get("topic", ""), now)
            )
        conn.commit()

    return jsonify({"success": True, "recorded": len(questions)}), 200

@app.route('/api/setup-quiz', methods=['POST'])
def setup_quiz():
    """
    Setup the daily quiz. Called by GitHub Actions orchestrator.
    Expects payload:
    {
      "questions": [
        {"id": "...", "question": "...", "options": [...], "answer": "..."}
      ],
      "tokens": [
        {"token": "...", "name": "...", "email": "..."}
      ],
      "deadline_epoch": 1780272000
    }
    """
    auth_error = require_admin_api_key()
    if auth_error:
        return auth_error
        
    data = request.get_json()
    if not data or 'questions' not in data or 'tokens' not in data:
        return jsonify({"error": "Invalid payload"}), 400
        
    with get_db() as conn:
        # Clear existing tables
        conn.execute("DELETE FROM questions")
        conn.execute("DELETE FROM tokens")
        conn.execute("DELETE FROM settings")
        
        # Insert new questions
        for q in data['questions']:
            conn.execute(
                "INSERT INTO questions (id, text, options_json, correct_answer) VALUES (?, ?, ?, ?)",
                (q['id'], q['question'], json.dumps(q['options']), q['answer'])
            )
            
        # Insert new tokens
        for t in data['tokens']:
            conn.execute(
                "INSERT INTO tokens (token, name, email) VALUES (?, ?, ?)",
                (t['token'], t['name'], t['email'])
            )
            
        # Store deadline
        deadline_epoch = data.get('deadline_epoch', datetime.now().timestamp() + 12 * 3600)
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('deadline_epoch', ?)",
            (str(deadline_epoch),)
        )
        
        conn.commit()
        
    return jsonify({"success": True, "message": "Quiz setup complete"}), 200


@app.route('/api/run-daily-quiz', methods=['POST'])
def run_daily_quiz():
    """Trigger the full daily quiz generation pipeline inside the Flask app."""
    auth_error = require_admin_api_key()
    if auth_error:
        return auth_error

    if DAILY_JOB_STATUS["running"]:
        return jsonify({"success": False, "error": "Daily quiz job is already running"}), 409

    worker = threading.Thread(target=_run_daily_quiz_background, daemon=True)
    worker.start()
    return jsonify({"success": True, "status": "started"}), 202


@app.route('/api/run-daily-quiz/status', methods=['GET'])
def run_daily_quiz_status():
    """Read the last known daily job state."""
    auth_error = require_admin_api_key()
    if auth_error:
        return auth_error

    status_code = 200
    if DAILY_JOB_STATUS["running"]:
        status_code = 202
    elif DAILY_JOB_STATUS["last_state"] == "failed":
        status_code = 500
    return jsonify(DAILY_JOB_STATUS), status_code

@app.route('/quiz/<token>', methods=['GET'])
def start_quiz_welcome(token):
    """Welcome page with rules. Does not start the timer yet."""
    with get_db() as conn:
        user = conn.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()
        
    if not user:
        return render_template('error.html', message="Invalid Quiz Token! Please check your email link."), 404
        
    if user['submitted_at']:
        return redirect(url_for('quiz_result', token=token))
        
    return render_template(
        'start.html',
        token=token,
        name=user['name'],
        question_count=getattr(config, 'QUIZ_QUESTION_COUNT', 5),
        time_limit_minutes=getattr(config, 'QUIZ_TIME_LIMIT_MINUTES', 15)
    )

@app.route('/quiz/<token>/start', methods=['POST'])
def start_quiz_timer(token):
    """Sets the start timestamp on the server and redirects to the quiz."""
    with get_db() as conn:
        user = conn.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()
        
        if not user:
            abort(404)
            
        if user['submitted_at']:
            return redirect(url_for('quiz_result', token=token))
            
        # Set opened_at if it's the first time
        if not user['opened_at']:
            opened_at_str = datetime.now().isoformat()
            conn.execute("UPDATE tokens SET opened_at = ? WHERE token = ?", (opened_at_str, token))
            conn.commit()
            
    return redirect(url_for('play_quiz', token=token))

@app.route('/quiz/<token>/play', methods=['GET'])
def play_quiz(token):
    """Renders the quiz form and handles the configured countdown."""
    with get_db() as conn:
        user = conn.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()
        
    if not user:
        return render_template('error.html', message="Invalid Link!"), 404
        
    if user['submitted_at']:
        return redirect(url_for('quiz_result', token=token))
        
    if not user['opened_at']:
        return redirect(url_for('start_quiz_welcome', token=token))
        
    # Calculate time remaining
    opened_at = datetime.fromisoformat(user['opened_at'])
    elapsed = (datetime.now() - opened_at).total_seconds()
    time_limit_minutes = getattr(config, 'QUIZ_TIME_LIMIT_MINUTES', 15)
    time_limit = time_limit_minutes * 60
    remaining = time_limit - elapsed
    
    if remaining <= -30:  # Allow a small buffer for load/network
        # Time expired. Invalidate or auto-submit score as 0
        with get_db() as conn:
            conn.execute(
                "UPDATE tokens SET submitted_at = ?, time_taken = ?, score = 0, answers = '{}', tab_switches = 0 WHERE token = ?",
                (datetime.now().isoformat(), int(elapsed), token)
            )
            conn.commit()
        return render_template('error.html', message=f"Time Limit Exceeded! Your quiz took longer than {time_limit_minutes} minutes and was marked void (0 score)."), 400
        
    # Fetch questions
    with get_db() as conn:
        db_qs = conn.execute("SELECT * FROM questions").fetchall()
        
    questions = []
    for q in db_qs:
        questions.append({
            "id": q['id'],
            "text": q['text'],
            "options": json.loads(q['options_json'])
        })
        
    return render_template(
        'quiz.html',
        token=token,
        name=user['name'],
        questions=questions,
        total_questions=len(questions),
        remaining_seconds=max(0, int(remaining)),
        time_limit_seconds=time_limit,
        time_limit_minutes=time_limit_minutes
    )

@app.route('/quiz/<token>/submit', methods=['POST'])
def submit_quiz(token):
    """Processes submissions, grades answers, and writes to Google Sheets."""
    with get_db() as conn:
        user = conn.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()
        
    if not user:
        abort(404)
        
    if user['submitted_at']:
        return redirect(url_for('quiz_result', token=token))
        
    if not user['opened_at']:
        return redirect(url_for('start_quiz_welcome', token=token))
        
    opened_at = datetime.fromisoformat(user['opened_at'])
    now = datetime.now()
    elapsed = (now - opened_at).total_seconds()
    
    time_limit_minutes = getattr(config, 'QUIZ_TIME_LIMIT_MINUTES', 15)
    submission_buffer_seconds = getattr(config, 'QUIZ_SUBMISSION_BUFFER_SECONDS', 45)

    if elapsed > (time_limit_minutes * 60 + submission_buffer_seconds):
        with get_db() as conn:
            conn.execute(
                "UPDATE tokens SET submitted_at = ?, time_taken = ?, score = 0, answers = 'LATE', tab_switches = ? WHERE token = ?",
                (now.isoformat(), int(elapsed), int(request.form.get('tab_switches', 0)), token)
            )
            conn.commit()
            
        # Log to sheet as late submission
        try:
            import sheets
            question_count = getattr(config, 'QUIZ_QUESTION_COUNT', 5)
            sheets.log_submission(user['name'], user['email'], 0, int(elapsed), int(request.form.get('tab_switches', 0)), ["Late"] * question_count)
        except Exception as e:
            print(f"[-] Error writing late submission to Google Sheets: {e}")
            
        return render_template('error.html', message=f"Submission Rejected! Time limit of {time_limit_minutes} minutes was exceeded. Your score has been logged as 0."), 400

    # Fetch questions and grade answers
    with get_db() as conn:
        db_qs = conn.execute("SELECT * FROM questions").fetchall()
        
    q_map = {q['id']: q for q in db_qs}
    
    submitted_answers = {}
    score = 0
    sheet_answers = []
    
    # Retrieve answers from form matching question IDs
    for q in db_qs:
        q_id = q['id']
        selected = request.form.get(f"q_{q_id}", "").strip().upper()
        submitted_answers[q_id] = selected
        
        # Check answer correctness
        correct = q['correct_answer'].strip().upper()
        if selected == correct:
            score += 1
            
        sheet_answers.append(selected)
        
    question_count = getattr(config, 'QUIZ_QUESTION_COUNT', 5)
    while len(sheet_answers) < question_count:
        sheet_answers.append("")
        
    tab_switches = int(request.form.get('tab_switches', 0))
    
    # Update local DB
    with get_db() as conn:
        conn.execute(
            "UPDATE tokens SET submitted_at = ?, time_taken = ?, score = ?, answers = ?, tab_switches = ? WHERE token = ?",
            (now.isoformat(), int(elapsed), score, json.dumps(submitted_answers), tab_switches, token)
        )
        conn.commit()
        
    # Append to Google Sheet
    try:
        import sheets
        ok = sheets.log_submission(user['name'], user['email'], score, int(elapsed), tab_switches, sheet_answers)
        if ok:
            print(f"[+] Result row appended to Google Sheet for {user['name']}.")
    except Exception as e:
        print(f"[-] Error writing submission to Google Sheets: {e}")

    # Update candidate memory for adaptive quiz selection
    try:
        from agent.memory import update_candidate
        question_ids = [q['id'] for q in db_qs]
        with get_db() as conn:
            placeholders = ",".join("?" * len(question_ids))
            rows = conn.execute(
                f"SELECT DISTINCT topic FROM sent_questions WHERE id IN ({placeholders})",
                question_ids
            ).fetchall()
        topics_covered = [r['topic'] for r in rows if r['topic']]
        update_candidate(
            email=user['email'],
            name=user['name'],
            score=score,
            total=len(db_qs),
            topics_covered=topics_covered,
            tab_switches=tab_switches,
            time_taken=int(elapsed),
        )
    except Exception as e:
        print(f"[-] Failed to update candidate memory: {e}")
        
    # Trigger background AI agents for feedback and suspicion analysis
    try:
        import threading
        
        # We need historical average for SuspicionAgent, so we read it from memory
        from agent.memory import _load as load_memory
        mem = load_memory()
        candidate_hist = mem.get(user['email'], {})
        avg_score = candidate_hist.get("avg_score", 0.0)
        
        # Prepare quiz data for FeedbackAgent
        quiz_data = []
        for q in db_qs:
            q_id = q['id']
            q_data = dict(q)
            q_data['user_answer'] = submitted_answers.get(q_id, "")
            quiz_data.append(q_data)

        from agent.feedback_agent import process_feedback
        from agent.suspicion_agent import analyze_submission
        
        feedback_thread = threading.Thread(
            target=process_feedback, 
            args=(user['name'], user['email'], quiz_data, score)
        )
        suspicion_thread = threading.Thread(
            target=analyze_submission,
            args=(user['name'], user['email'], score, int(elapsed), tab_switches, avg_score)
        )
        
        feedback_thread.start()
        # Stagger by 5s so both threads don't hit the NIM API simultaneously
        threading.Timer(5.0, suspicion_thread.start).start()
        print(f"[+] Spawned Feedback and Suspicion agents for {user['name']}.")
    except Exception as e:
        print(f"[-] Failed to start AI agent threads: {e}")
        
    return redirect(url_for('quiz_result', token=token))

@app.route('/quiz/<token>/result', methods=['GET'])
def quiz_result(token):
    """Results page. Hides answers before the daily deadline."""
    with get_db() as conn:
        user = conn.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()
        
    if not user or not user['submitted_at']:
        return redirect(url_for('start_quiz_welcome', token=token))
        
    deadline_passed = get_deadline_passed()
    
    if not deadline_passed:
        # Show thank you page without answers/scores
        return render_template('result.html', token=token, name=user['name'], deadline_passed=False)
        
    # deadline passed, show correct answers and explanations
    with get_db() as conn:
        db_qs = conn.execute("SELECT * FROM questions").fetchall()
        
    user_answers = json.loads(user['answers']) if user['answers'] and user['answers'] != 'LATE' else {}
    
    graded_questions = []
    for q in db_qs:
        q_id = q['id']
        graded_questions.append({
            "text": q['text'],
            "options": json.loads(q['options_json']),
            "correct_answer": q['correct_answer'],
            "user_answer": user_answers.get(q_id, "")
        })
        
    return render_template('result.html', 
                           token=token, 
                           name=user['name'], 
                           deadline_passed=True, 
                           score=user['score'], 
                           total_questions=len(graded_questions),
                           questions=graded_questions,
                           time_taken=user['time_taken'],
                           tab_switches=user['tab_switches'])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '').lower() in {'1', 'true', 'yes'}
    app.run(host='0.0.0.0', debug=debug, port=port)
