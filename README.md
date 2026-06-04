# Daily Aptitude Quiz Agent 📝🤖

An automated daily aptitude quiz platform that scrapes questions from IndiaBix, delivers personalized, timed, single-use test links to candidates via Resend, scores attempts, logs focus loss statistics, and logs the final graded results in real-time to Google Sheets.

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
- **Automated Orchestrator:** Runs daily via GitHub Actions, wakes the Render web service, pushes today's questions, and mails candidate links.

---

## File Structure

```text
├── main.py                  Local entry point for running the orchestrator manually
├── scraper.py               IndiaBix web scraper (4 or 5 options, md5 hashing)
├── tracker.py               Tracks already-sent question IDs in sent_log.json
├── emailer.py               Personalized HTML mail builder & Resend API dispatcher
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
├── render.yaml              Optional Render web service config
├── .github/workflows/daily.yml GitHub Actions daily scheduler
└── DEPLOYMENT.md            Free deployment checklist
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

### Phase B: Resend Setup
1. Create a [Resend](https://resend.com/) account.
2. Create an API key in the Resend dashboard.
3. Verify a sending domain in Resend.
4. Choose a sender address on that verified domain, for example `Quiz Bot <onboarding@yourdomain.com>`.

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
   - Update `RESEND_API_KEY` and `RESEND_FROM_EMAIL` for local testing (or leave them empty to run in simulation mode).
   - Enter your `GOOGLE_SHEET_ID`.
4. Start the Flask server locally:
   ```bash
   python app.py
   ```
   The server will start at `http://localhost:5000`.
5. Run the orchestrator script to simulate the daily quiz generation locally:
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
- `render.yaml` for optional Render web service configuration.
- `.github/workflows/daily.yml` for the trigger-only daily scheduler.
- `/` health endpoint for platform health checks.

### Recommended Free Setup
1. Push this folder to a GitHub repository.
2. In Render, create a **New Web Service** from the repository.
3. Select the **Free** instance type.
4. Use `pip install -r requirements.txt` as the build command.
5. Use `gunicorn app:app --bind 0.0.0.0:$PORT` as the start command.
6. Add these environment variables in the Render dashboard:
   - `ADMIN_API_KEY`
   - `RESEND_API_KEY`
   - `RESEND_FROM_EMAIL`
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
7. Deploy, then open the service URL. A healthy app returns:
   ```json
   {"service":"daily-aptitude-quiz","status":"ok"}
   ```

### GitHub Actions Scheduler
Configure these repository secrets under **Settings -> Secrets and variables -> Actions**:

```text
ADMIN_API_KEY
RESEND_API_KEY
RESEND_FROM_EMAIL
GOOGLE_SHEET_ID
NVIDIA_API_KEY
QUIZ_BASE_URL
```

`ADMIN_API_KEY` and `QUIZ_BASE_URL` must match the Render service.

The workflow sends a protected `POST` request to `/api/run-daily-quiz` daily at `30 2 * * *` UTC, which is 8:00 AM IST.
