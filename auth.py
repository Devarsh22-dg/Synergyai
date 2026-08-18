"""Sign-up and login for ScopeForge.

Design:
  - Passwords are hashed with streamlit_authenticator's Hasher (bcrypt) —
    never stored or compared in plaintext.
  - Accounts are activated immediately on signup — email OTP verification is
    turned OFF for now (was removed 2026-08-17; see otp_email.py, which is
    kept in place but unused, in case it's turned back on later).
  - Login itself (credential check + session cookie) is handled by
    streamlit_authenticator's Authenticate class — battle-tested session/
    cookie handling rather than hand-rolled.
  - MFA is intentionally NOT implemented here. That's a deliberately separate,
    later phase (before PM-tool integration), not bundled into this one.

Optional secret to pin the auth cookie's signing key across restarts
(recommended in production so logins don't get invalidated on every deploy):
    AUTH_COOKIE_KEY
"""
import os
import re

import streamlit as st
import streamlit_authenticator as stauth

import db

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
        # Handles any pre-existing unverified row from before OTP verification
        # was turned off, or a create_user() that partially failed previously.
        user_id = existing_by_email["id"]
        db.update_pending_user(user_id, username, password_hash)
    else:
        try:
            user_id = db.create_user(username, email, password_hash)
        except Exception as e:
            st.error(f"Couldn't create account: {e}")
            return

    db.mark_email_verified(user_id)
    st.success("Account created — switch to the Log In tab and sign in with your new credentials.")


def require_login():
    """Call at the top of the app. Returns True once a verified user is
    logged in; otherwise renders the login/signup UI and returns False so
    the caller can st.stop()."""
    db.init_db()

    if st.session_state.get("authentication_status"):
        return True

    st.markdown("## Welcome to ScopeForge")

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
