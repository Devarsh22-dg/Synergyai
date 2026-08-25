"""Sign-up and login for ScopeForge.

Design:
  - Passwords are hashed with streamlit_authenticator's Hasher (bcrypt) —
    never stored or compared in plaintext.
  - Accounts are activated immediately on signup. There is no email
    verification step — it was built, then removed, on 2026-08-17.
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
from theme import NAVY, ACCENT, SIDEBAR_TEXT, SIDEBAR_MUTED, TEXT_MUTED

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")

# What the login page showcases. Kept in sync with the tabs that actually
# exist in ba_module() — don't advertise the PM/PgM modules here, they're
# still placeholders.
CAPABILITIES = [
    ("Elicitation Analysis", "Upload notes, transcripts, or documents and get ambiguities, missing NFRs, and stakeholder conflicts flagged with a risk score."),
    ("Documentation Generator", "First-draft BRDs, FRDs, Use Cases, Data Dictionaries, and As-Is / To-Be process maps, exportable to Word, Excel, or Visio."),
    ("Agile Story & Test Cases", "Turn requirements into user stories with Gherkin acceptance criteria, then derive test cases from them. Exports to Jira and Azure DevOps."),
    ("Meeting Actionizer", "Raw transcript in, structured minutes out: decisions, action items, owners, and due dates."),
    ("Traceability & Change Impact", "Auto-linked Requirement to Story to Test Case matrix, plus impact analysis on incoming change requests."),
]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_secret(key):
    try:
        val = st.secrets.get(key)
    except Exception:
        val = None
    return val or os.environ.get(key)


def _build_authenticator(warn_missing_key=True):
    """warn_missing_key is suppressed when rebuilding an authenticator for an
    already-logged-in session — that path runs above the main app body, where
    the caption would surface as a stray warning on an otherwise normal page."""
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
        if warn_missing_key:
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


def _render_showcase():
    """The left-hand panel on the login screen: an optional demo video plus
    what the app actually does.

    The video is intentionally configuration, not a committed asset — set a
    DEMO_VIDEO_URL secret (or env var) to any URL st.video accepts (YouTube,
    Vimeo, a direct .mp4, an S3/CDN link). Until one is set, the capability
    list below carries the page on its own, so this never renders as a broken
    or empty player."""
    video_url = _get_secret("DEMO_VIDEO_URL")

    st.markdown(
        f"""
        <div style="background-color: {NAVY}; border-radius: 10px;
                    padding: 1.5rem 1.6rem 0.4rem 1.6rem; margin-bottom: 1rem;">
            <div style="font-size: 1.5rem; font-weight: 700; color: {SIDEBAR_TEXT};
                        letter-spacing: 0.2px; margin-bottom: 0.2rem;">ScopeForge</div>
            <div style="font-size: 0.9rem; color: {SIDEBAR_MUTED}; margin-bottom: 1.2rem;">
                An AI-augmented workspace for business analysts.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if video_url:
        st.video(video_url)
        st.caption("A two-minute tour of what ScopeForge does.")
        st.markdown("")

    for name, description in CAPABILITIES:
        st.markdown(
            f"""
            <div style="border-left: 3px solid {ACCENT}; padding: 0.15rem 0 0.15rem 0.8rem;
                        margin-bottom: 0.9rem;">
                <div style="font-size: 0.95rem; font-weight: 600; color: {NAVY};">{name}</div>
                <div style="font-size: 0.85rem; color: {TEXT_MUTED}; line-height: 1.45;">{description}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def require_login():
    """Call at the top of the app. Returns True once a verified user is
    logged in; otherwise renders the login/signup UI and returns False so
    the caller can st.stop()."""
    db.init_db()

    if st.session_state.get("authentication_status"):
        # A returning user authenticated from their cookie can reach this
        # early return without the login widget ever running, so nothing has
        # stored an authenticator — and render_logout_control() then silently
        # skips the Log Out button, stranding them with no way to sign out.
        if "_authenticator" not in st.session_state:
            st.session_state["_authenticator"] = _build_authenticator(warn_missing_key=False)
        return True

    showcase_col, auth_col = st.columns([1.15, 1], gap="large")

    with showcase_col:
        _render_showcase()

    with auth_col:
        st.markdown("### Welcome to ScopeForge")
        tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

        with tab_login:
            if not db.get_all_verified_users():
                # streamlit_authenticator raises LoginError('User not
                # authorized') if handed an empty credentials dict, which
                # surfaces as a raw Python traceback on the login page. That
                # is the normal state for a fresh deployment — and on
                # Streamlit Community Cloud the SQLite file is wiped on every
                # redeploy, so it would recur constantly. Show the signup
                # prompt instead of instantiating the login widget at all.
                st.info("No accounts exist yet. Use the Sign Up tab to create the first one.")
            else:
                authenticator = _build_authenticator()
                try:
                    authenticator.login(location="main", key="login_form")
                except stauth.LoginError:
                    # The browser is holding a re-authentication cookie naming a
                    # user who no longer exists in the database, so
                    # streamlit_authenticator raises before rendering anything.
                    #
                    # This is not an edge case here: Streamlit Community Cloud's
                    # filesystem is ephemeral, so the SQLite file is wiped on
                    # every redeploy while users' 30-day cookies survive. Left
                    # unhandled it renders a raw Python traceback in place of the
                    # login form — locking the user out of even signing up again
                    # until they manually clear cookies. Drop the dead cookie and
                    # retry once; the guard stops that becoming a reload loop if
                    # deletion doesn't take effect.
                    authenticator.cookie_controller.delete_cookie()
                    if st.session_state.get("_stale_cookie_cleared"):
                        st.warning(
                            "Your saved session is no longer valid. Please refresh "
                            "the page to log in again."
                        )
                    else:
                        st.session_state["_stale_cookie_cleared"] = True
                        st.rerun()
                else:
                    st.session_state.pop("_stale_cookie_cleared", None)
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
