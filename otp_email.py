"""OTP generation/verification and the SMTP send for ScopeForge's signup
email-verification step. Provider-agnostic: works with any SMTP account
(Gmail/Workspace app password, Outlook, a company mail server, etc.) — the
app never assumes a specific vendor.

Required secrets (st.secrets or environment variables):
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL
"""
import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

OTP_LENGTH = 6
OTP_TTL_MINUTES = 10
SIGNUP_PURPOSE = "signup_verification"


def generate_otp():
    """Cryptographically random 6-digit numeric code."""
    return "".join(str(secrets.randbelow(10)) for _ in range(OTP_LENGTH))


def hash_otp(code):
    # OTPs are short-lived and low-entropy (6 digits) — a fast, salted hash is
    # appropriate here (unlike passwords, where bcrypt's slowness matters).
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def otp_expiry_iso():
    return (datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()


def is_expired(expires_at_iso):
    return datetime.now(timezone.utc) > datetime.fromisoformat(expires_at_iso)


def _get_smtp_config(secrets_getter):
    """secrets_getter(key) should check st.secrets then os.environ — passed in
    from auth.py so this module has no Streamlit dependency of its own."""
    config = {
        "host": secrets_getter("SMTP_HOST"),
        "port": secrets_getter("SMTP_PORT"),
        "username": secrets_getter("SMTP_USERNAME"),
        "password": secrets_getter("SMTP_PASSWORD"),
        "from_email": secrets_getter("SMTP_FROM_EMAIL"),
    }
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing SMTP config: {', '.join(missing)}. Add these to Streamlit "
            "secrets or as environment variables to enable signup email verification."
        )
    return config


def send_otp_email(to_email, code, secrets_getter):
    config = _get_smtp_config(secrets_getter)
    body = (
        f"Your ScopeForge verification code is: {code}\n\n"
        f"This code expires in {OTP_TTL_MINUTES} minutes. If you didn't request this, "
        "you can ignore this email."
    )
    msg = MIMEText(body)
    msg["Subject"] = "Your ScopeForge verification code"
    msg["From"] = config["from_email"]
    msg["To"] = to_email

    with smtplib.SMTP(config["host"], int(config["port"])) as server:
        server.starttls()
        server.login(config["username"], config["password"])
        server.sendmail(config["from_email"], [to_email], msg.as_string())
