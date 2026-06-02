# Daily Aptitude Quiz Agent 📝🤖

An automated daily aptitude quiz platform that scrapes questions from IndiaBix, delivers personalized, timed, single-use test links to candidates via Gmail SMTP, scores attempts, logs focus loss statistics, and logs the final graded results in real-time to Google Sheets.

---

## Key Features
- **Dynamic Scraper:** Extracts aptitude questions dynamically (supports both 4 and 5 options) with automatic HTML format check.
- **Anti-Cheat Measures:**
  - Blocks right-click context menus.
  - Blocks copy, cut, and paste actions.
  - Disables text highlighting (`user-select: none`).
  - Identifies browser window blur events (switching tabs or opening screenshot tools) and logs total violations.
- **Secure Server-side Validation:** Server logs the exact quiz start time and strictly invalidates/rejects attempts beyond the configured time limit.
- **Result Masking:** Hides correct options and score details until the daily deadline passes (e.g. 9:00 PM IST).
- **Automated Orchestrator:** Runs daily via Render Cron Job, waking up the server, pushing today's questions, and mailing candidate links.

---

## File Structure

```text
├── main.py                  Agent orchestrator (wakes server, pushes state, mails friends)
├── scraper.py               IndiaBix web scraper (4 or 5 options, md5 hashing)
├── tracker.py               Tracks already-sent question IDs in sent_log.json
├── emailer.py               Personalized HTML mail builder & Gmail SMTP dispatcher
├── app.py                   Flask server (manages timer, database states, scoring API)
├── sheets.py                Google Sheets logger (falls back to mock logging if offline)
├── config.py                Shared config values (deadline times, friends list)
├── sent_log.json            [Auto-created] Tracks sent question IDs
├── quiz.db                  [Auto-created] Local SQLite database for operational state
├── templates/
│   ├── start.html           Welcome rules page (prevents accidental timer triggers)
│   ├── quiz.html            Polished timed quiz page (incorporates anti-cheat & timer)
│   ├── result.html          Thank you screen / Graded report page (post-deadline)
│   └── error.html           Failed tokens, timeouts, and late submission warnings
├── render.yaml              Render web service + cron job blueprint
└── DEPLOYMENT.md            Render deployment checklist
```

---

## Setup & Deployment Guide

### Phase A: Google Sheets API Credentials
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project and search for/enable the **Google Sheets API** and **Google Drive API**.
3. Go to **Credentials**, click **Create Credentials**, and choose **Service Account**.
4. Create the Service Account, go to its details, click the **Keys** tab, click **Add Key**, and choose **Create New Key (JSON)**.
5. Download the key, rename it to `credentials.json`, and place it in the project root folder.
6. Open the downloaded JSON and copy the service account email (`client_email`).
7. Create a new Google Sheet, name it (e.g. `Daily Quiz Results`), and share edit access with that service account email address.
8. Copy the Sheet ID from the URL (the string between `/d/` and `/edit` in the address bar).

### Phase B: Gmail App Password
1. Go to your Google Account Settings -> Security.
2. Enable **2-Step Verification** if not already enabled.
3. Search for **App Passwords** in the settings search bar.
4. Create a new App Password (select App: *Mail*, Device: *Other*), and copy the generated 16-character code.

### Phase C: Local Setup & Testing
1. Clone/extract the project files into your workspace.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   pip install requests beautifulsoup4 flask gspread google-auth
   ```
3. Open `config.py` and:
   - Configure the candidate list under `FRIENDS_LIST`.
   - Update `SENDER_EMAIL` and `SENDER_PASSWORD` with your App Password for local testing (or leave default to run in simulation mode).
   - Enter your `GOOGLE_SHEET_ID`.
4. Start the Flask server locally:
   ```bash
   python app.py
   ```
   The server will start at `http://localhost:5000`.
5. Run the orchestrator script to simulate the daily cron job:
   ```bash
   python main.py
   ```
   - This scrapes the configured number of questions from `QUIZ_QUESTION_COUNT`, creates a session in `quiz.db`, logs mock sheets data, and emails links pointing to `http://localhost:5000/quiz/<token>`.
   - If SMTP credentials are not set, it print-simulates the mail link in the console terminal. Copy that link into your browser to test the candidate flow!

---

## Deploying the Flask App

The app is deployment-ready with:
- `requirements.txt` for dependencies.
- `Procfile` using `gunicorn app:app --bind 0.0.0.0:$PORT`.
- `render.yaml` for Render Blueprint deployment.
- `/` health endpoint for platform health checks.

### Recommended: Render
1. Push this folder to a GitHub repository.
2. In Render, create a new **Blueprint** from the repository. Render will read `render.yaml`.
3. Add these environment variables in the Render dashboard:
   - `ADMIN_API_KEY`
   - `SENDER_EMAIL`
   - `SENDER_PASSWORD`
   - `GOOGLE_SHEET_ID`
   - `GOOGLE_CREDENTIALS_JSON` (paste the service-account JSON as one value)
   - `NVIDIA_API_KEY`
   - `QUIZ_BASE_URL` (set this after Render gives you the deployed URL)
   - `QUIZ_QUESTION_COUNT`
   - `QUIZ_TIME_LIMIT_MINUTES`
   - `QUIZ_SUBMISSION_BUFFER_SECONDS`
   - `QUIZ_RESULT_DEADLINE_HOURS`
   - `QUIZ_DEADLINE_HOUR`
   - `QUIZ_DEADLINE_MINUTE`
4. If using the included persistent disk, keep:
   - `QUIZ_DB_FILE=/var/data/quiz.db`
   - `CANDIDATE_MEMORY_FILE=/var/data/candidate_memory.json`
5. Deploy, then open the service URL. A healthy app returns:
   ```json
   {"service":"daily-aptitude-quiz","status":"ok"}
   ```

### Render Cron Job
The included `render.yaml` also creates `daily-aptitude-quiz-dispatcher`, a Render Cron Job that runs:

```bash
python main.py
```

It runs daily at `30 2 * * *` UTC, which is 8:00 AM IST.

Render Cron Jobs do not share the web service disk, so used question IDs are persisted through the Flask API endpoints documented in `DEPLOYMENT.md`.
