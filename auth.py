"""Sign-up (with email OTP verification) and login for ScopeForge.

Design:
  - Passwords are hashed with streamlit_authenticator's Hasher (bcrypt) —
    never stored or compared in plaintext.
  - A new account is inactive (email_verified=0) until the user enters the
    6-digit code emailed to them at signup. Only verified accounts can log in.
  - Login itself (credential check + session cookie) is handled by
    streamlit_authenticator's Authenticate class — battle-tested session/
    cookie handling rather than hand-rolled.
  - MFA is intentionally NOT implemented here. That's a deliberately separate,
    later phase (before PM-tool integration), not bundled into this one.

Required secrets for signup email to actually send (see otp_email.py):
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL
Optional secret to pin the auth cookie's signing key across restarts
(recommended in production so logins don't get invalidated on every deploy):
    AUTH_COOKIE_KEY
"""
import os
import re

import streamlit as st
import streamlit_authenticator as stauth

import db
import otp_email

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_secret(key):
    try:
        val = st.secrets.get(key)
    except Exception:
        val = None
    return val or os.environ.get(key)


def _build_authenticator():
    users = db.get_all_verified_users()
    credentials = {"usernames": {}}
    for u in users:
        credentials["usernames"][u["username"]] = {
            "email": u["email"],
            "name": u["username"],
            "password": u["password_hash"],
        }
    cookie_key = _get_secret("AUTH_COOKIE_KEY")
    if not cookie_key:
        st.caption(
            "⚠️ No AUTH_COOKIE_KEY secret set — using a temporary session key, "
            "so everyone will be logged out on the next restart. Fine for local "
            "testing; add AUTH_COOKIE_KEY as a secret before real use."
        )
        cookie_key = "scopeforge_dev_insecure_default_key"
    return stauth.Authenticate(
        credentials,
        cookie_name="scopeforge_auth",
        cookie_key=cookie_key,
        cookie_expiry_days=30,
        auto_hash=False,  # already hashed via Hasher.hash() at signup time
    )


def _render_signup():
    st.subheader("Create an account")
    with st.form("signup_form"):
        username = st.text_input("Username", key="signup_username")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        confirm = st.text_input("Confirm Password", type="password", key="signup_confirm")
        submitted = st.form_submit_button("Sign Up")

    if not submitted:
        return

    username = (username or "").strip()
    email = (email or "").strip().lower()

    if not USERNAME_RE.match(username):
        st.error("Username must be 3-20 characters: letters, numbers, or underscore.")
        return
    if not EMAIL_RE.match(email):
        st.error("Enter a valid email address.")
        return
    if len(password or "") < 8:
        st.error("Password must be at least 8 characters.")
        return
    if password != confirm:
        st.error("Passwords don't match.")
        return

    existing_by_email = db.get_user_by_email(email)
    existing_by_username = db.get_user_by_username(username)

    if existing_by_email and existing_by_email["email_verified"]:
        st.error("An account with that email already exists. Try logging in instead.")
        return
    if existing_by_username and existing_by_username["email"] != email:
        if existing_by_username["email_verified"]:
            st.error("That username is already taken.")
        else:
            st.error("That username is pending verification under a different email. Choose a different username.")
        return

    password_hash = stauth.Hasher.hash(password)

    if existing_by_email:
        # An unverified, abandoned signup for this email already exists — most
        # likely the first verification email never arrived. Resume it instead
        # of permanently blocking this email address: update the username/
        # password in case they changed, and send a fresh code below.
        user_id = existing_by_email["id"]
        db.update_pending_user(user_id, username, password_hash)
        st.info("Resuming your previous signup for this email — sending a new code.")
    else:
        try:
            user_id = db.create_user(username, email, password_hash)
        except Exception as e:
            st.error(f"Couldn't create account: {e}")
            return

    code = otp_email.generate_otp()
    db.create_otp(user_id, otp_email.hash_otp(code), otp_email.SIGNUP_PURPOSE, otp_email.otp_expiry_iso())
    try:
        otp_email.send_otp_email(email, code, _get_secret)
    except Exception as e:
        st.warning(
            f"Account created, but the verification email couldn't be sent ({e}). "
            "Ask your admin to configure SMTP secrets, then use 'Resend Code' below once fixed."
        )

    st.session_state["pending_signup_user_id"] = user_id
    st.session_state["pending_signup_email"] = email
    st.rerun()


def _render_otp_verify():
    """Returns True if it rendered the verification screen (i.e. caller should
    stop here), False if there's no pending signup to verify."""
    user_id = st.session_state.get("pending_signup_user_id")
    email = st.session_state.get("pending_signup_email")
    if not user_id:
        return False

    st.subheader("Verify your email")
    st.caption(f"Enter the 6-digit code sent to {email}. It expires in {otp_email.OTP_TTL_MINUTES} minutes.")
    with st.form("otp_form"):
        code = st.text_input("Verification code", max_chars=6, key="otp_code_input")
        col1, col2 = st.columns(2)
        with col1:
            verify_clicked = st.form_submit_button("Verify")
        with col2:
            resend_clicked = st.form_submit_button("Resend Code")

    if resend_clicked:
        new_code = otp_email.generate_otp()
        db.create_otp(user_id, otp_email.hash_otp(new_code), otp_email.SIGNUP_PURPOSE, otp_email.otp_expiry_iso())
        try:
            otp_email.send_otp_email(email, new_code, _get_secret)
            st.success("New code sent.")
        except Exception as e:
            st.error(f"Couldn't send email: {e}")
        return True

    if verify_clicked:
        otp_row = db.get_latest_otp(user_id, otp_email.SIGNUP_PURPOSE)
        if not otp_row:
            st.error("No pending code found — click 'Resend Code'.")
        elif otp_email.is_expired(otp_row["expires_at"]):
            st.error("That code expired — click 'Resend Code'.")
        elif otp_email.hash_otp((code or "").strip()) != otp_row["code_hash"]:
            st.error("Incorrect code.")
        else:
            db.consume_otp(otp_row["id"])
            db.mark_email_verified(user_id)
            st.session_state.pop("pending_signup_user_id", None)
            st.session_state.pop("pending_signup_email", None)
            st.success("Email verified! Log in below.")
            st.rerun()

    if st.button("Cancel and start over", key="otp_cancel"):
        db.delete_unverified_user(user_id)
        st.session_state.pop("pending_signup_user_id", None)
        st.session_state.pop("pending_signup_email", None)
        st.rerun()

    return True


def require_login():
    """Call at the top of the app. Returns True once a verified user is
    logged in; otherwise renders the login/signup UI and returns False so
    the caller can st.stop()."""
    db.init_db()

    if st.session_state.get("authentication_status"):
        return True

    st.markdown("## Welcome to ScopeForge")

    if _render_otp_verify():
        return False

    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        authenticator = _build_authenticator()
        authenticator.login(location="main", key="login_form")
        st.session_state["_authenticator"] = authenticator
        status = st.session_state.get("authentication_status")
        if status is False:
            st.error("Incorrect username or password.")
        elif status is None:
            st.info("Enter your credentials to log in.")

    with tab_signup:
        _render_signup()

    return bool(st.session_state.get("authentication_status"))


def render_logout_control():
    """Call from the sidebar once logged in."""
    authenticator = st.session_state.get("_authenticator")
    if authenticator:
        authenticator.logout(button_name="Log Out", location="sidebar", key="logout_btn")
    username = st.session_state.get("username")
    if username:
        st.sidebar.caption(f"Signed in as **{username}**")
