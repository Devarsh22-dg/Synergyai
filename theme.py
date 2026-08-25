"""Single source of truth for ScopeForge's color palette.

Both synergyai_app.py and auth.py import from here. That matters: the login
page (auth.py) renders before the main app, and if it kept its own copy of
these values they would drift apart the moment either file changed — which
is exactly the inconsistency the 2026-08-18 redesign removed.

Corporate Navy: one navy surface, one accent blue, neutral grays. Deliberately
NOT a per-section palette — every section uses ACCENT.

No streamlit import here on purpose, so headless importers (evals/) stay clean.
"""

NAVY = "#0F1B2E"           # sidebar / header / masthead surface
NAVY_SOFT = "#1B2A42"      # sidebar input/control backgrounds
ACCENT = "#2554C7"         # the one accent — buttons, links, active states
ACCENT_HOVER = "#1D45A6"
TEXT = "#111827"           # primary body text
TEXT_MUTED = "#6B7280"     # secondary/caption text — on white only (4.83:1)
# TEXT_MUTED drops to 4.39:1 against the gray tab surface, under the 4.5
# minimum. Use this instead wherever muted text sits on a gray fill.
TEXT_MUTED_STRONG = "#4B5563"
BORDER = "#E5E7EB"         # card and table borders

SIDEBAR_BG = NAVY
SIDEBAR_TEXT = "#F3F5F9"
SIDEBAR_MUTED = "#94A3B8"
