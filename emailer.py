import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config

def send_quiz_email(recipient_name, recipient_email, quiz_link):
    """
    Sends a styled HTML email containing a personalized quiz link to a friend.
    """
    sender_email = config.SENDER_EMAIL
    sender_password = config.SENDER_PASSWORD
    question_count = getattr(config, "QUIZ_QUESTION_COUNT", 5)
    time_limit_minutes = getattr(config, "QUIZ_TIME_LIMIT_MINUTES", 15)
    
    # Check if credentials are placeholders
    if sender_email == "your-email@gmail.com" or sender_password == "your-gmail-app-password":
        print(f"[-] SMTP Credentials not configured. Simulating email to {recipient_name} ({recipient_email})...")
        print(f"    Link: {quiz_link}")
        return True

    # Setup the MIME
    message = MIMEMultipart('alternative')
    message['From'] = f"Daily Quiz Agent <{sender_email}>"
    message['To'] = recipient_email
    message['Subject'] = f"📝 Your Daily Aptitude Quiz is Ready, {recipient_name}!"

    # Create HTML content
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
                letter-spacing: -0.5px;
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
                letter-spacing: 0.5px;
            }}
            .rule-item {{
                font-size: 14px;
                color: #4b5563;
                margin-bottom: 10px;
                display: flex;
            }}
            .rule-item:last-child {{
                margin-bottom: 0;
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
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
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
                    Your daily aptitude assessment is ready. Click the button below to start your challenge. The link is personalized for you and will expire upon use.
                </div>
                
                <div class="rules-box">
                    <div class="rules-title">⚠️ Assessment Rules</div>
                    <div class="rule-item">Questions: {question_count} multiple-choice questions.</div>
                    <div class="rule-item">⏱️ Time Limit: {time_limit_minutes} minutes (timer auto-submits on expiration).</div>
                    <div class="rule-item">🚫 No Resubmissions: The link is single-use only.</div>
                    <div class="rule-item">🛡️ Anti-Cheat: Text copying is blocked. App logs all window changes/tab switching.</div>
                </div>
                
                <div class="cta-container">
                    <a href="{quiz_link}" class="btn-cta">Start Assessment</a>
                </div>
            </div>
            
            <div class="footer">
                This is an automated delivery. Please submit within the daily deadline.<br>
                &copy; 2026 Daily Quiz Agent.
            </div>
        </div>
    </body>
    </html>
    """
    
    # Attach body
    message.attach(MIMEText(html_content, 'html'))
    
    try:
        # Create SMTP session for reference
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() # Enable security
        server.login(sender_email, sender_password) # Login
        text = message.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        print(f"[+] Email successfully sent to {recipient_name} ({recipient_email}).")
        return True
    except Exception as e:
        print(f"[-] Failed to send email to {recipient_name}: {e}")
        return False

def send_feedback_email(recipient_name, recipient_email, feedback_body):
    """
    Sends a personalized feedback email to a candidate after a quiz.
    """
    sender_email = config.SENDER_EMAIL
    sender_password = config.SENDER_PASSWORD
    
    if sender_email == "your-email@gmail.com" or sender_password == "your-gmail-app-password":
        print(f"[-] SMTP Credentials not configured. Simulating feedback email to {recipient_name} ({recipient_email})...")
        print(f"    Body: {feedback_body}")
        return True

    message = MIMEMultipart('alternative')
    message['Subject'] = f"Feedback on your Quiz, {recipient_name}"
    message['From'] = f"Daily Quiz <{sender_email}>"
    message['To'] = recipient_email

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

    message.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(message)
        server.quit()
        print(f"[+] Feedback Email successfully sent to {recipient_name} ({recipient_email})")
        return True
    except Exception as e:
        print(f"[-] Failed to send feedback email to {recipient_email}. Error: {e}")
        return False

if __name__ == "__main__":
    # Test emailer (will simulate if credentials aren't set)
    send_quiz_email("Test Friend", "test.friend@example.com", "http://localhost:5000/quiz/test-token-123")
