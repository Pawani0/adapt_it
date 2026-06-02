# Deploy Adaptit on Render

This project uses Render for both services:

- A Flask web service that hosts the quiz.
- A Render Cron Job that runs `python main.py` every day and dispatches the quiz.

No GitHub Actions setup is required.

## 1. Create the Render Blueprint

1. Push this repository to GitHub.
2. In Render, choose **New -> Blueprint**.
3. Select this repository.
4. Render reads `render.yaml` and creates:
   - `daily-aptitude-quiz`
   - `daily-aptitude-quiz-dispatcher`

The cron schedule is:

```text
30 2 * * *
```

Render cron schedules use UTC, so this runs at **8:00 AM IST**.

Note: Render Cron Jobs have a minimum monthly charge, and the persistent disk for SQLite requires a paid Render service.

## 2. Add Render environment variables

For both the web service and cron job, set the same values for:

```text
ADMIN_API_KEY
SENDER_EMAIL
SENDER_PASSWORD
GOOGLE_SHEET_ID
NVIDIA_API_KEY
QUIZ_BASE_URL
```

Set `QUIZ_BASE_URL` to your Render web service URL, for example:

```text
https://adaptit.onrender.com
```

For the web service only, also set:

```text
GOOGLE_CREDENTIALS_JSON
```

Paste the full Google service-account JSON as one environment variable value.

## 3. Persistent data

The web service uses a Render persistent disk for:

```text
QUIZ_DB_FILE=/var/data/quiz.db
CANDIDATE_MEMORY_FILE=/var/data/candidate_memory.json
```

Render Cron Jobs cannot access that disk, so the cron dispatcher records used question IDs through the Flask API:

```text
GET  /api/sent-questions
POST /api/sent-questions
```

Both endpoints require `X-API-Key: ADMIN_API_KEY`.

## 4. Test

1. Deploy the Blueprint.
2. Open the web service URL. It should return:

```json
{"service":"daily-aptitude-quiz","status":"ok"}
```

3. Open the cron job in Render and click **Trigger Run**.
4. Check the cron logs for successful scraping, setup, and email sending.
5. Check the web service logs for `/api/setup-quiz` and `/api/sent-questions` returning `200`.

## Security

Do not commit `.env`, `credentials.json`, `quiz.db`, or logs. If any real secret was pushed before `.gitignore` was added, rotate that credential before production.
