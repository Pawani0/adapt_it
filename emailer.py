import requests
import config

RESEND_API_URL = "https://api.resend.com/emails"


def _resend_ready():
    return bool(config.RESEND_API_KEY and config.RESEND_FROM_EMAIL)


def _send_via_resend(recipient_email, subject, html_content):
    if not _resend_ready():
        print(f"[-] Resend not configured. Simulating email to {recipient_email}...")
        return True

    payload = {
        "from": config.RESEND_FROM_EMAIL,
        "to": [recipient_email],
        "subject": subject,
        "html": html_content,
    }
    headers = {
        "Authorization": f"Bearer {config.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            RESEND_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )
        if 200 <= response.status_code < 300:
            return True

        print(
            f"[-] Resend email failed for {recipient_email}: "
            f"HTTP {response.status_code} {response.text[:300]}"
        )
        return False
    except Exception as e:
        print(f"[-] Resend email failed for {recipient_email}: {e}")
        return False


def send_quiz_email(recipient_name, recipient_email, quiz_link):
    """
    Sends a styled HTML email containing a personalized quiz link.
    """
    question_count = getattr(config, "QUIZ_QUESTION_COUNT", 5)
    time_limit_minutes = getattr(config, "QUIZ_TIME_LIMIT_MINUTES", 15)
    subject = f"Your Daily Aptitude Quiz is Ready, {recipient_name}!"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f3f4f6;
                color: #1f2937;
                margin: 0;
                padding: 0;
            }}
            .email-container {{
                max-width: 600px;
                margin: 30px auto;
                background-color: #ffffff;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
                border: 1px solid #e5e7eb;
            }}
            .header {{
                background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
                padding: 40px 20px;
                text-align: center;
                color: #ffffff;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: 800;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .greeting {{
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 20px;
            }}
            .instructions {{
                font-size: 15px;
                line-height: 1.6;
                color: #4b5563;
                margin-bottom: 30px;
            }}
            .rules-box {{
                background-color: #f9fafb;
                border: 1px solid #f3f4f6;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 35px;
            }}
            .rules-title {{
                font-weight: 700;
                font-size: 14px;
                color: #374151;
                text-transform: uppercase;
                margin-bottom: 12px;
            }}
            .rule-item {{
                font-size: 14px;
                color: #4b5563;
                margin-bottom: 10px;
            }}
            .cta-container {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .btn-cta {{
                display: inline-block;
                padding: 16px 36px;
                background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
                color: #ffffff !important;
                font-weight: 700;
                font-size: 16px;
                text-decoration: none;
                border-radius: 12px;
            }}
            .footer {{
                background-color: #f9fafb;
                border-top: 1px solid #e5e7eb;
                padding: 20px 30px;
                text-align: center;
                font-size: 12px;
                color: #9ca3af;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h1>DAILY APTITUDE CHALLENGE</h1>
            </div>
            <div class="content">
                <div class="greeting">Hi {recipient_name},</div>
                <div class="instructions">
                    Your daily aptitude assessment is ready. Click the button below to start your challenge.
                </div>
                <div class="rules-box">
                    <div class="rules-title">Assessment Rules</div>
                    <div class="rule-item">Questions: {question_count} multiple-choice questions.</div>
                    <div class="rule-item">Time Limit: {time_limit_minutes} minutes.</div>
                    <div class="rule-item">No resubmissions: the link is single-use only.</div>
                    <div class="rule-item">Anti-cheat logging is enabled for focus loss and tab switching.</div>
                </div>
                <div class="cta-container">
                    <a href="{quiz_link}" class="btn-cta">Start Assessment</a>
                </div>
            </div>
            <div class="footer">
                This is an automated delivery. Please submit within the daily deadline.
            </div>
        </div>
    </body>
    </html>
    """

    success = _send_via_resend(recipient_email, subject, html_content)
    if success:
        print(f"[+] Email successfully sent to {recipient_name} ({recipient_email}).")
    return success


def send_feedback_email(recipient_name, recipient_email, feedback_body):
    """
    Sends a personalized feedback email to a candidate after a quiz.
    """
    subject = f"Feedback on your Quiz, {recipient_name}"
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; padding: 20px;">
        <h2 style="color: #4CAF50;">Quiz Feedback</h2>
        <p>Hi <b>{recipient_name}</b>,</p>
        <p>Thank you for submitting your quiz. Here is some personalized feedback on your performance:</p>
        <div style="background: #f9f9f9; border-left: 4px solid #4CAF50; margin: 20px 0; padding: 15px;">
            <p>{feedback_body.replace(chr(10), "<br>")}</p>
        </div>
        <p>Keep practicing and improving!</p>
        <p>Best,<br>Your Quiz Bot</p>
      </body>
    </html>
    """

    success = _send_via_resend(recipient_email, subject, html_content)
    if success:
        print(f"[+] Feedback email successfully sent to {recipient_name} ({recipient_email}).")
    return success


if __name__ == "__main__":
    send_quiz_email("Test Friend", "test.friend@example.com", "http://localhost:5000/quiz/test-token-123")
