# Synergyai (ScopeForge)
Functional tool

## Setup: required secrets

Add these via Streamlit secrets (`.streamlit/secrets.toml` locally, or
Settings → Secrets on Streamlit Community Cloud) or as environment variables.

| Secret | Required for | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | All AI features | Get one at console.anthropic.com |
| `AUTH_COOKIE_KEY` | Keeping users logged in across restarts | Optional but recommended: without it, everyone gets logged out every time the app restarts (e.g. every nightly redeploy). Any long random string. |

**Note on the user database:** accounts are currently stored in a local
SQLite file (`scopeforge.db`, gitignored). This does **not** survive on
Streamlit Community Cloud — its filesystem resets on every redeploy, which
wipes all registered users. Fine for local development; see `db.py`'s
module docstring for the plan to swap in a real backend before going live.

See `evals/README.md` for the nightly automated eval loop.
