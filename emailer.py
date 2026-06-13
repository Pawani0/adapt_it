import time
import requests
import config

RESEND_API_URL = "https://api.resend.com/emails"


def _resend_ready():
    return bool(config.RESEND_API_KEY and config.RESEND_FROM_EMAIL)


def _send_via_resend(recipient_email, subject, html_content, _retries=2):
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

    for attempt in range(1 + _retries):
        try:
            response = requests.post(
                RESEND_API_URL,
                json=payload,
                headers=headers,
                timeout=30,
            )
            if 200 <= response.status_code < 300:
                return True

            if response.status_code == 429 and attempt < _retries:
                wait = 1.0 * (attempt + 1)
                print(f"[!] Resend rate limit hit for {recipient_email}. Retrying in {wait}s…")
                time.sleep(wait)
                continue

            print(
                f"[-] Resend email failed for {recipient_email}: "
                f"HTTP {response.status_code} {response.text[:300]}"
            )
            return False
        except Exception as e:
            if attempt < _retries:
                time.sleep(1.0)
                continue
            print(f"[-] Resend email failed for {recipient_email}: {e}")
            return False

    return False


def send_quiz_email(recipient_name, recipient_email, quiz_link):
    """
    Sends a styled HTML email containing a personalized quiz link.
    """
    question_count = getattr(config, "QUIZ_QUESTION_COUNT", 5)
    time_limit_minutes = getattr(config, "QUIZ_TIME_LIMIT_MINUTES", 15)
    subject = f"Your Daily Quiz is Live — {recipient_name}"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Aptitude Quiz</title>
</head>
<body style="margin:0;padding:0;background-color:#0f0f0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#0f0f0f;padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;width:100%;">

          <!-- Logo / Brand bar -->
          <tr>
            <td style="padding-bottom:32px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <span style="font-size:13px;font-weight:600;letter-spacing:0.12em;color:#555;text-transform:uppercase;">Aptitude Engine</span>
                  </td>
                  <td align="right">
                    <span style="font-size:12px;color:#333;letter-spacing:0.04em;">Daily Challenge</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main card -->
          <tr>
            <td style="background-color:#1a1a1a;border-radius:12px;overflow:hidden;border:1px solid #2a2a2a;">

              <!-- Top accent line -->
              <tr>
                <td style="height:3px;background-color:#e8c97a;font-size:0;line-height:0;">&nbsp;</td>
              </tr>

              <!-- Header -->
              <tr>
                <td style="padding:40px 40px 0 40px;">
                  <p style="margin:0 0 8px 0;font-size:11px;font-weight:600;letter-spacing:0.14em;color:#e8c97a;text-transform:uppercase;">Today's Assessment</p>
                  <h1 style="margin:0;font-size:28px;font-weight:700;color:#f5f5f5;line-height:1.2;letter-spacing:-0.02em;">Ready when<br>you are, {recipient_name}.</h1>
                </td>
              </tr>

              <!-- Divider -->
              <tr>
                <td style="padding:28px 40px;">
                  <div style="height:1px;background-color:#2a2a2a;"></div>
                </td>
              </tr>

              <!-- Stats row -->
              <tr>
                <td style="padding:0 40px 32px 40px;">
                  <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                      <td width="50%" style="padding-right:8px;">
                        <div style="background-color:#111;border:1px solid #2a2a2a;border-radius:8px;padding:18px 20px;">
                          <p style="margin:0 0 4px 0;font-size:10px;font-weight:600;letter-spacing:0.12em;color:#555;text-transform:uppercase;">Questions</p>
                          <p style="margin:0;font-size:26px;font-weight:700;color:#f5f5f5;">{question_count}</p>
                          <p style="margin:4px 0 0 0;font-size:11px;color:#444;">multiple choice</p>
                        </div>
                      </td>
                      <td width="50%" style="padding-left:8px;">
                        <div style="background-color:#111;border:1px solid #2a2a2a;border-radius:8px;padding:18px 20px;">
                          <p style="margin:0 0 4px 0;font-size:10px;font-weight:600;letter-spacing:0.12em;color:#555;text-transform:uppercase;">Time Limit</p>
                          <p style="margin:0;font-size:26px;font-weight:700;color:#f5f5f5;">{time_limit_minutes}<span style="font-size:14px;font-weight:400;color:#666;">min</span></p>
                          <p style="margin:4px 0 0 0;font-size:11px;color:#444;">strictly enforced</p>
                        </div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- Rules -->
              <tr>
                <td style="padding:0 40px 32px 40px;">
                  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#111;border:1px solid #2a2a2a;border-radius:8px;padding:20px;">
                    <tr>
                      <td style="padding:20px;">
                        <p style="margin:0 0 14px 0;font-size:10px;font-weight:600;letter-spacing:0.12em;color:#555;text-transform:uppercase;">Before you begin</p>
                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                          <tr><td style="padding:5px 0;font-size:13px;color:#888;line-height:1.5;"><span style="color:#e8c97a;margin-right:10px;">—</span>Link is single-use. No resubmissions.</td></tr>
                          <tr><td style="padding:5px 0;font-size:13px;color:#888;line-height:1.5;"><span style="color:#e8c97a;margin-right:10px;">—</span>Tab switching and focus loss are logged.</td></tr>
                          <tr><td style="padding:5px 0;font-size:13px;color:#888;line-height:1.5;"><span style="color:#e8c97a;margin-right:10px;">—</span>Copy, paste, and right-click are disabled.</td></tr>
                          <tr><td style="padding:5px 0;font-size:13px;color:#888;line-height:1.5;"><span style="color:#e8c97a;margin-right:10px;">—</span>Results are released after the daily deadline.</td></tr>
                        </table>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- CTA -->
              <tr>
                <td style="padding:0 40px 40px 40px;">
                  <table cellpadding="0" cellspacing="0" border="0">
                    <tr>
                      <td style="background-color:#e8c97a;border-radius:6px;">
                        <a href="{quiz_link}" style="display:inline-block;padding:14px 32px;font-size:14px;font-weight:600;color:#0f0f0f;text-decoration:none;letter-spacing:0.02em;">Begin Assessment &rarr;</a>
                      </td>
                    </tr>
                  </table>
                  <p style="margin:14px 0 0 0;font-size:12px;color:#444;">
                    Or paste this link: <span style="color:#666;">{quiz_link}</span>
                  </p>
                </td>
              </tr>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:28px 0 0 0;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="font-size:11px;color:#333;line-height:1.6;">
                    Automated dispatch &bull; Submit before the 9 PM IST deadline &bull; Do not reply to this email
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    success = _send_via_resend(recipient_email, subject, html_content)
    if success:
        print(f"[+] Email successfully sent to {recipient_name} ({recipient_email}).")
    return success


def send_feedback_email(recipient_name, recipient_email, feedback_body):
    """
    Sends a personalized feedback email to a candidate after a quiz.
    """
    subject = f"Your Quiz Feedback — {recipient_name}"
    formatted_body = feedback_body.replace(chr(10), "<br>")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Quiz Feedback</title>
</head>
<body style="margin:0;padding:0;background-color:#0f0f0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#0f0f0f;padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;width:100%;">

          <!-- Brand bar -->
          <tr>
            <td style="padding-bottom:32px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <span style="font-size:13px;font-weight:600;letter-spacing:0.12em;color:#555;text-transform:uppercase;">Aptitude Engine</span>
                  </td>
                  <td align="right">
                    <span style="font-size:12px;color:#333;letter-spacing:0.04em;">Performance Review</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main card -->
          <tr>
            <td style="background-color:#1a1a1a;border-radius:12px;overflow:hidden;border:1px solid #2a2a2a;">

              <!-- Top accent line -->
              <tr>
                <td style="height:3px;background-color:#7edea8;font-size:0;line-height:0;">&nbsp;</td>
              </tr>

              <!-- Header -->
              <tr>
                <td style="padding:40px 40px 0 40px;">
                  <p style="margin:0 0 8px 0;font-size:11px;font-weight:600;letter-spacing:0.14em;color:#7edea8;text-transform:uppercase;">Assessment Complete</p>
                  <h1 style="margin:0;font-size:28px;font-weight:700;color:#f5f5f5;line-height:1.2;letter-spacing:-0.02em;">Here's how you<br>did, {recipient_name}.</h1>
                </td>
              </tr>

              <!-- Divider -->
              <tr>
                <td style="padding:28px 40px;">
                  <div style="height:1px;background-color:#2a2a2a;"></div>
                </td>
              </tr>

              <!-- Feedback body -->
              <tr>
                <td style="padding:0 40px 32px 40px;">
                  <p style="margin:0 0 16px 0;font-size:10px;font-weight:600;letter-spacing:0.12em;color:#555;text-transform:uppercase;">Personalized Feedback</p>
                  <div style="background-color:#111;border:1px solid #2a2a2a;border-left:3px solid #7edea8;border-radius:0 8px 8px 0;padding:24px;">
                    <p style="margin:0;font-size:14px;color:#aaa;line-height:1.8;">{formatted_body}</p>
                  </div>
                </td>
              </tr>

              <!-- Closing note -->
              <tr>
                <td style="padding:0 40px 40px 40px;">
                  <p style="margin:0;font-size:13px;color:#555;line-height:1.6;">
                    Keep showing up. Consistency compounds.<br>
                    <span style="color:#333;">— Aptitude Engine</span>
                  </p>
                </td>
              </tr>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:28px 0 0 0;">
              <p style="margin:0;font-size:11px;color:#333;line-height:1.6;">
                Automated feedback report &bull; Do not reply to this email
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    success = _send_via_resend(recipient_email, subject, html_content)
    if success:
        print(f"[+] Feedback email successfully sent to {recipient_name} ({recipient_email}).")
    return success


if __name__ == "__main__":
    send_quiz_email("Test Friend", "test.friend@example.com", "http://localhost:5000/quiz/test-token-123")
