import os
FACE_SERVICE_URL = os.getenv(
    "FACE_SERVICE_URL",
    "http://localhost:5001"  # Default cho development
)


# Timeout cho request (seconds)
FACE_SERVICE_TIMEOUT = int(os.getenv("FACE_SERVICE_TIMEOUT", "30"))


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_FILE_PATH = os.path.join(BASE_DIR, ".env")
FACE_MATCH_THRESHOLD = 0.35

def _load_dotenv(path):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as dotenv_file:
        for raw_line in dotenv_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()

            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]

            if key:
                os.environ.setdefault(key, value)


_load_dotenv(ENV_FILE_PATH)


def _env_bool(name, default):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "tickethub-secret-key")

    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", 
                                        "mysql+pymysql://root:123456@localhost/ticketdb"
                                        )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DB_AUTO_INIT = _env_bool("DB_AUTO_INIT", True)

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _env_bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_TIMEOUT = int(os.getenv("MAIL_TIMEOUT", "10"))
    # Default "From" address for all outgoing emails.
    # Can be overridden via MAIL_DEFAULT_SENDER in .env.
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER") or MAIL_USERNAME or "tickethub@gmail.com"

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://nonvinous-walker-postpositively.ngrok-free.dev/callback")
    GOOGLE_DISCOVERY_URL = os.getenv(
        "GOOGLE_DISCOVERY_URL",
        "https://accounts.google.com/.well-known/openid-configuration",
    )
    QR_SECRET = os.getenv("QR_SECRET", "your-qr-secret-key-change-this")

    VNP_TMNCODE = os.getenv("VNP_TMNCODE", "YOUR_TMNCODE")
    VNP_HASHSECRET = os.getenv("VNP_HASHSECRET", "YOUR_SECRET_KEY")
    VNP_URL = os.getenv("VNP_URL", "")
    VNP_RETURN_URL = os.getenv("VNP_RETURN_URL", "")
    VNP_API_URL = os.getenv("VNP_API_URL", "")

    SESSION_COOKIE_SECURE = True  # Chỉ gửi qua HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'  
    PERMANENT_SESSION_LIFETIME = 1800 