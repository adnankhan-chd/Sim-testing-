"""SIM Lookup - shows the SIMs linked to a user's own ID number.

Data comes from a source YOU are authorised to use (see README). The ID number
is never stored or logged: it is normalised, hashed, and matched in memory.
Gemini only receives masked SIM data (never the ID number) to write a summary.
"""

import hashlib
import os
import re
import time

import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
MAX_ATTEMPTS = 5          # lookups allowed per browser session...
WINDOW_SECONDS = 600      # ...within this many seconds
ID_MIN_LEN, ID_MAX_LEN = 6, 20
DEFAULT_MODEL = "gemini-2.5-flash"

# Fake demo data. Replace with your real, authorised source (README explains).
DEMO_ROWS = [
    {"id_number": "1234567890123", "sim_number": "03001234567",
     "operator": "Operator A", "status": "Active", "registered_on": "2021-03-14"},
    {"id_number": "1234567890123", "sim_number": "03121234567",
     "operator": "Operator B", "status": "Active", "registered_on": "2022-07-02"},
    {"id_number": "1234567890123", "sim_number": "03331234567",
     "operator": "Operator C", "status": "Blocked", "registered_on": "2019-11-23"},
    {"id_number": "9876543210987", "sim_number": "03451112233",
     "operator": "Operator A", "status": "Active", "registered_on": "2020-01-05"},
]


# ----------------------------------------------------------------------------
# Core logic (no Streamlit calls, so it is easy to test)
# ----------------------------------------------------------------------------
def normalize_id(raw: str) -> str:
    """Strip spaces/dashes and upper-case, e.g. '12345-1234567-1' -> '1234512345671'."""
    return re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()


def is_valid_id(normalized: str) -> bool:
    return ID_MIN_LEN <= len(normalized) <= ID_MAX_LEN and normalized.isalnum()


def hash_id(normalized: str, salt: str = "") -> str:
    return hashlib.sha256((salt + normalized).encode("utf-8")).hexdigest()


def mask_number(number: str) -> str:
    """Show only the first 4 and last 2 characters: 0300*****67."""
    n = str(number)
    if len(n) <= 6:
        return "*" * len(n)
    return n[:4] + "*" * (len(n) - 6) + n[-2:]


def build_index(df: pd.DataFrame, salt: str = "") -> dict:
    """Return {hashed_id: [sim records]} so plain ID numbers are not kept in memory."""
    required = {"id_number", "sim_number", "operator", "status", "registered_on"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Data source is missing columns: {sorted(missing)}")
    index: dict = {}
    for row in df.astype(str).to_dict("records"):
        key = hash_id(normalize_id(row.pop("id_number")), salt)
        index.setdefault(key, []).append(row)
    return index


def find_sims(index: dict, raw_id: str, salt: str = "") -> list:
    normalized = normalize_id(raw_id)
    if not is_valid_id(normalized):
        raise ValueError("Please enter a valid ID number.")
    return index.get(hash_id(normalized, salt), [])


def check_rate_limit(attempts: list, now: float) -> tuple:
    """Return (allowed, pruned_attempts)."""
    recent = [t for t in attempts if now - t < WINDOW_SECONDS]
    return len(recent) < MAX_ATTEMPTS, recent


def summarize_with_gemini(sims: list, api_key: str, model: str = DEFAULT_MODEL) -> str:
    """Ask Gemini for a short friendly summary. Only masked data is sent."""
    from google import genai  # imported lazily so the app works without a key

    safe = [
        {
            "sim": mask_number(s["sim_number"]),
            "operator": s["operator"],
            "status": s["status"],
            "registered_on": s["registered_on"],
        }
        for s in sims
    ]
    prompt = (
        "You are a helpful assistant. Write a short, friendly summary (max 4 "
        "sentences) of these SIM registrations for the owner. Mention how many "
        "are active vs blocked, and suggest they report any SIM they do not "
        "recognise to their mobile operator. Do not invent details.\n\n"
        f"SIM data: {safe}"
    )
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    return (response.text or "").strip()


# ----------------------------------------------------------------------------
# Streamlit helpers
# ----------------------------------------------------------------------------
def get_secret(name: str, default: str = "") -> str:
    """Read from st.secrets (Streamlit Cloud) or environment (local)."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


@st.cache_resource(show_spinner=False)
def load_index(salt: str, path: str) -> dict:
    if path and os.path.exists(path):
        df = pd.read_csv(path, dtype=str)
    else:
        df = pd.DataFrame(DEMO_ROWS)
    return build_index(df, salt)


def main() -> None:
    st.set_page_config(page_title="SIM Lookup", page_icon="📱")
    st.title("📱 My SIMs")
    st.caption("Check which SIMs are registered against your own ID number.")

    salt = get_secret("ID_HASH_SALT", "change-me")
    data_path = get_secret("SIM_DATA_PATH", "")
    api_key = get_secret("GEMINI_API_KEY", "")
    model = get_secret("GEMINI_MODEL", DEFAULT_MODEL)

    try:
        index = load_index(salt, data_path)
    except Exception as exc:
        st.error(f"Could not load the data source: {exc}")
        st.stop()

    if not data_path:
        st.info("Demo mode: try ID **1234567890123**. This is fake data.")

    with st.form("lookup"):
        raw_id = st.text_input(
            "ID card number",
            type="password",
            placeholder="Paste your ID number",
            help="Dashes and spaces are fine. It is not stored or logged.",
        )
        consent = st.checkbox("I confirm this is my own ID number.")
        submitted = st.form_submit_button("Show my SIMs")

    if not submitted:
        return

    if not consent:
        st.warning("Please confirm that this is your own ID number.")
        return

    allowed, st.session_state["attempts"] = check_rate_limit(
        st.session_state.get("attempts", []), time.time()
    )
    if not allowed:
        st.error("Too many attempts. Please wait a few minutes and try again.")
        return
    st.session_state["attempts"].append(time.time())

    try:
        sims = find_sims(index, raw_id, salt)
    except ValueError as exc:
        st.error(str(exc))
        return

    if not sims:
        st.success("No SIMs found for this ID number.")
        return

    st.subheader(f"{len(sims)} SIM(s) found")
    table = pd.DataFrame(sims).rename(
        columns={
            "sim_number": "SIM",
            "operator": "Operator",
            "status": "Status",
            "registered_on": "Registered on",
        }
    )
    table["SIM"] = table["SIM"].map(mask_number)
    st.dataframe(table, hide_index=True)

    if api_key:
        with st.spinner("Writing a summary..."):
            try:
                st.markdown("**Summary**")
                st.write(summarize_with_gemini(sims, api_key, model))
            except Exception:
                st.caption("AI summary is unavailable right now.")
    else:
        st.caption("Add GEMINI_API_KEY to enable the AI summary.")


if __name__ == "__main__":
    main()
  
