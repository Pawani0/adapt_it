# Free Deploy: Flask on Render, Scheduler on GitHub Actions

This setup avoids paid Render features:

- Render Free Web Service hosts the Flask quiz app.
- GitHub Actions runs `python main.py` every day.
- `sent_log.json` is committed back to the repo so question history persists.

Do not use Render Blueprint, Render Cron Jobs, or Render persistent disks for the free setup.

## 1. Deploy Flask on Render

1. Go to Render.
2. Click **New + -> Web Service**.
3. Connect your GitHub repository.
4. Select the repo.
5. Use:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
Instance Type: Free
```

6. Add these Render environment variables:

```text
ADMIN_API_KEY=<make a strong secret>
SENDER_EMAIL=<your Gmail address>
SENDER_PASSWORD=<your Gmail app password>
GOOGLE_SHEET_ID=<your Google Sheet ID>
GOOGLE_CREDENTIALS_JSON=<full service-account JSON>
NVIDIA_API_KEY=<your NVIDIA NIM API key>
QUIZ_BASE_URL=<your Render web service URL>
QUIZ_QUESTION_COUNT=15
QUIZ_TIME_LIMIT_MINUTES=15
QUIZ_SUBMISSION_BUFFER_SECONDS=45
QUIZ_RESULT_DEADLINE_HOURS=12
QUIZ_DEADLINE_HOUR=21
QUIZ_DEADLINE_MINUTE=0
```

At first, `QUIZ_BASE_URL` can be blank or temporary. After Render gives you the final URL, set it to that URL and redeploy.

## 2. Verify Render

Open your Render URL. It should return:

```json
{"service":"daily-aptitude-quiz","status":"ok"}
```

## 3. Configure GitHub Actions

In your GitHub repo, go to:

```text
Settings -> Secrets and variables -> Actions
```

Add these **Repository secrets**:

```text
ADMIN_API_KEY=<same value as Render>
SENDER_EMAIL=<same value as Render>
SENDER_PASSWORD=<same value as Render>
GOOGLE_SHEET_ID=<same value as Render>
NVIDIA_API_KEY=<same value as Render>
QUIZ_BASE_URL=<your Render web service URL>
```

Add optional **Repository variables**:

```text
QUIZ_QUESTION_COUNT=15
QUIZ_TIME_LIMIT_MINUTES=15
QUIZ_SUBMISSION_BUFFER_SECONDS=45
QUIZ_RESULT_DEADLINE_HOURS=12
QUIZ_TOPICS=
```

## 4. Run the Scheduler

The workflow is:

```text
.github/workflows/daily.yml
```

It runs daily at:

```text
30 2 * * *
```

That is **8:00 AM IST**.

To test manually:

1. Open GitHub **Actions**.
2. Select **Daily Aptitude Quiz Dispatcher**.
3. Click **Run workflow**.
4. Check logs for scraping, setup, and emails.
5. Check Render logs for `/api/setup-quiz` returning `200`.

## Free-Tier Caveat

Render free web services can sleep and their local filesystem is not reliable long-term. This means `quiz.db` can reset after redeploys/restarts. For a demo/MVP this is usually fine. For reliable production, move quiz state to a hosted database such as Neon or Supabase.

## Security

Do not commit `.env`, `credentials.json`, `quiz.db`, or logs. If any real secret was pushed before `.gitignore` was added, rotate that credential before production.
