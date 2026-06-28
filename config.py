import os


def _load_dotenv(path=".env"):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                # Decode standard escape sequences inside double-quoted values
                inner = value[1:-1]
                inner = (inner
                         .replace('\\\\', '\x00BACKSLASH\x00')
                         .replace('\\"', '"')
                         .replace('\\n', '\n')
                         .replace('\\r', '\r')
                         .replace('\\t', '\t')
                         .replace('\x00BACKSLASH\x00', '\\'))
                value = inner
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)


def _csv_env(name, default=""):
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


_load_dotenv()

# Base URL for the quiz server (exclude trailing slash)
QUIZ_BASE_URL = os.environ.get("QUIZ_BASE_URL", "http://localhost:5000")

# Secret Admin API Key for setups (Actions -> Flask)
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "admin-default-secret-key-12345")

# Email Delivery Settings
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "")

# Google Sheets Config
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "your-google-sheet-id-here")

# Database Config
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# NVIDIA NIM Config
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_MODEL = "minimaxai/minimax-m2.7"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_TIMEOUT_SECONDS = float(os.environ.get("NVIDIA_TIMEOUT_SECONDS", 120))
NVIDIA_MAX_RETRIES = int(os.environ.get("NVIDIA_MAX_RETRIES", 1))

# Groq Fallback Config
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3-32b")

# OpenRouter Fallback Config
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Daily Quiz Submission Deadline (IST)
QUIZ_DEADLINE_HOUR = int(os.environ.get("QUIZ_DEADLINE_HOUR", 21))      # 9 PM IST
QUIZ_DEADLINE_MINUTE = int(os.environ.get("QUIZ_DEADLINE_MINUTE", 0))

# Quiz Content and Timing
QUIZ_QUESTION_COUNT = int(os.environ.get("QUIZ_QUESTION_COUNT", 5))
QUIZ_TIME_LIMIT_MINUTES = int(os.environ.get("QUIZ_TIME_LIMIT_MINUTES", 15))
QUIZ_SUBMISSION_BUFFER_SECONDS = int(os.environ.get("QUIZ_SUBMISSION_BUFFER_SECONDS", 45))
QUIZ_RESULT_DEADLINE_HOURS = int(os.environ.get("QUIZ_RESULT_DEADLINE_HOURS", 12))

# Leave empty for adaptive topic selection, or set comma-separated topic names.
# Example: Percentage,Profit and Loss,Time and Work
QUIZ_TOPICS = _csv_env("QUIZ_TOPICS")

# List of Friends/Candidates
# Change this list to contain your target friends
FRIENDS_LIST = [
    {
        "name": "Rishabh Pawani",
        "email": "rishabhpawani09@gmail.com"
    },
    {
        "name": "Priyani Rathod",
        "email": "priyanirathod1695@gmail.com"
    },
    {
        "name": "Deepika Vishwakarma",
        "email": "vishwakarmadeepika2806@gmail.com"
    },
    {
        "name": "Rishu Pandey",
        "email": "prishu342@gmail.com"
    },
    {
        "name": "Rishu Kumar",
        "email": "rishutiwari0018@gmail.com"
    },
    {
        "name": "Mohnish Singh",
        "email": "mohnishsr255@gmail.com"
    },
    {
        "name": "Priyanka Vishwakarma",
        "email": "priyankavishwakarma03@gmail.com"
    },
    {
        "name": "Vaibhav Sharma",
        "email": "viabhav9039939889@gmail.com"
    },
    {
        "name": "Rounak Jain",
        "email": "rounakjain049@gmail.com"
    }
]
