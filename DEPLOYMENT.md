# Deploy With Render + Neon + GitHub Actions Trigger

This setup keeps the real automation inside the Flask app:

- Render hosts the Flask app.
- Neon stores quiz state and candidate memory.
- GitHub Actions only triggers the daily quiz run.

## 1. Create a Neon database

1. Create a Neon project.
2. Copy the pooled connection string from the Neon dashboard.
3. It should look like:

```text
postgresql://user:password@ep-xxxx-pooler.region.aws.neon.tech/dbname?sslmode=require
```

Use the pooled connection string for Render.

## 2. Deploy the Flask app on Render

1. In Render, create a **New Web Service** from your GitHub repo.
2. Use:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
```

3. Add these Render environment variables:

```text
ADMIN_API_KEY=<strong shared secret>
SENDER_EMAIL=<your Gmail>
SENDER_PASSWORD=<your Gmail app password>
GOOGLE_SHEET_ID=<your sheet id>
GOOGLE_CREDENTIALS_JSON=<full service-account JSON>
NVIDIA_API_KEY=<your NVIDIA NIM key>
QUIZ_BASE_URL=<your Render app URL>
DATABASE_URL=<your Neon pooled connection string>
QUIZ_QUESTION_COUNT=15
QUIZ_TIME_LIMIT_MINUTES=15
QUIZ_SUBMISSION_BUFFER_SECONDS=45
QUIZ_RESULT_DEADLINE_HOURS=12
QUIZ_DEADLINE_HOUR=21
QUIZ_DEADLINE_MINUTE=0
QUIZ_TOPICS=
USE_AI_ORCHESTRATOR=true
```

After deploy, open:

```text
https://your-app.onrender.com/
```

You should see:

```json
{"service":"daily-aptitude-quiz","status":"ok"}
```

## 3. Configure GitHub Actions

In GitHub:

```text
Settings -> Secrets and variables -> Actions
```

Add these repository secrets:

```text
ADMIN_API_KEY=<same value as Render>
QUIZ_BASE_URL=<your Render app URL>
```

That is all Actions needs now.

## 4. How the trigger works

The workflow calls:

```text
POST /api/run-daily-quiz
```

with:

```text
X-API-Key: ADMIN_API_KEY
```

The endpoint starts the job in the background and returns immediately. GitHub Actions then polls:

```text
GET /api/run-daily-quiz/status
```

The Flask app then:

1. Runs the quiz-generation agent.
2. Scrapes/selects questions.
3. Creates tokens.
4. Stores quiz state in Neon.
5. Sends emails.

## 5. Test it

1. Open GitHub **Actions**.
2. Run **Daily Aptitude Quiz Dispatcher** manually.
3. Check the workflow output.
4. Check Render logs for `/api/run-daily-quiz`.
5. Open a quiz link from the email.

## 6. Why this fixes the token issue

Previously, GitHub Actions generated the quiz and Flask stored tokens in local SQLite on Render, which could disappear.

Now:

- GitHub Actions only sends a trigger.
- Flask generates the quiz itself.
- Tokens and quiz data are stored in Neon, not local SQLite.

## Security

The Google service-account key and NVIDIA API key shown in chat/editor are exposed and should be rotated.
