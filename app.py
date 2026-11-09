from __future__ import annotations

import csv
import hashlib
import hmac
import html
import io
import json
import os
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from google_sheets import GoogleSheetsStore, phone_number_for_student
import tracker


LOGO_PATH = Path(__file__).parent / "assets" / "google-cloud-logo.png"
CAMPAIGN_SYLLABUS_URL = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vTVMEFW24yi5IVcBblZFEK5xMd"
    "QyeF9pndf-wxE37BKu5hyOghhSkYiCHW6rSLjNJd5U3OI_E_I9vZi/pubhtml"
    "?gid=411469390&single=true"
)
LAB_PLAYLIST_URL = "https://youtube.com/playlist?list=PLNPCsw6Vr8qk&si=Vn8nUlMYnvNwyZXY"
CLAIM_CREDITS_URL = "https://youtu.be/WVdUW1wJwyI?si=-QUUEoe4gE6-gfG5"
SUPPORT_PHONE = "+966571696327"


st.set_page_config(
    page_title="GDG MCET | Cloud Learning Tracker",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
      --blue:#4285f4; --green:#34a853; --yellow:#fbbc04; --red:#ea4335;
      --purple:#a142f4; --cyan:#24c1e0;
    }
    html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
    .stApp {
      background:
        radial-gradient(ellipse at 8% 8%, rgba(66,133,244,.10), transparent 30%),
        radial-gradient(ellipse at 92% 20%, rgba(161,66,244,.08), transparent 26%),
        radial-gradient(ellipse at 70% 88%, rgba(52,168,83,.07), transparent 30%);
    }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; letter-spacing: -.025em; }
    .block-container { max-width: 1440px; padding-top: 2rem; padding-bottom: 4rem; text-align: center; }
    .block-container h1, .block-container h2, .block-container h3, .block-container h4,
    .block-container p, .block-container [data-testid="stCaptionContainer"],
    .block-container [data-testid="stProgress"] { text-align: center; }
    .block-container [data-testid="stMetricLabel"],
    .block-container [data-testid="stMetricValue"] { text-align: left; }
    [data-testid="stMetric"] {
      background: linear-gradient(145deg, rgba(66,133,244,.34), rgba(25,34,52,.96) 68%);
      border: 1px solid rgba(138,180,248,.38); border-radius: 18px; padding: 18px 20px;
      box-shadow: 0 10px 28px rgba(0,0,0,.16);
    }
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) [data-testid="stMetric"] {
      background: linear-gradient(145deg, rgba(52,168,83,.32), rgba(22,42,38,.96) 68%);
      border-color: rgba(52,168,83,.42);
    }
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) [data-testid="stMetric"] {
      background: linear-gradient(145deg, rgba(249,171,0,.30), rgba(47,39,23,.96) 68%);
      border-color: rgba(249,171,0,.42);
    }
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4) [data-testid="stMetric"] {
      background: linear-gradient(145deg, rgba(234,67,53,.30), rgba(47,29,34,.96) 68%);
      border-color: rgba(234,67,53,.42);
    }
    [data-testid="stMetricLabel"] { color: var(--text-color); opacity: .78; font-weight: 600; }
    [data-testid="stMetricValue"] { color: var(--text-color); font-family: 'Space Grotesk',sans-serif; }
    [data-testid="stAlert"] {
      border-radius: 14px; border-width: 1px;
      box-shadow: 0 6px 20px rgba(0,0,0,.12);
    }
    div.stButton > button { border-radius: 11px; font-weight: 600; min-height: 2.7rem; }
    .hero { color: white; margin: 0; text-align: center; }
    .hero h1 { color: white; font-size: clamp(1.9rem, 3.5vw, 3rem); margin: 0 0 .45rem; }
    .hero p { color: rgba(255,255,255,.86); font-size: 1rem; max-width: 730px; margin: 0 auto; }
    .eyebrow { color: #a9ccff; text-transform: uppercase; letter-spacing: .14em; font-weight: 700; font-size: .75rem; }
    .st-key-home_banner, .st-key-leaderboard_banner {
      padding: clamp(18px, 3vw, 36px); border-radius: 26px; margin: .4rem 0 1.6rem;
      border: 1px solid rgba(138,180,248,.32);
      box-shadow: 0 18px 45px rgba(0,0,0,.2);
      background: radial-gradient(circle at 88% 18%, rgba(52,168,83,.34), transparent 28%),
                  radial-gradient(circle at 78% 110%, rgba(161,66,244,.30), transparent 30%),
                  radial-gradient(circle at 8% 100%, rgba(234,67,53,.28), transparent 24%),
                  linear-gradient(120deg, #101722 0%, #172238 52%, #252044 100%);
    }
    .st-key-home_banner [data-testid="stImage"],
    .st-key-leaderboard_banner [data-testid="stImage"] {
      display: flex; justify-content: center; align-items: center;
      background: #fff; border-radius: 20px; padding: 6px; max-width: 154px; margin: auto;
    }
    .st-key-home_banner [data-testid="stImage"] img,
    .st-key-leaderboard_banner [data-testid="stImage"] img {
      width: 140px; max-width: 100%; height: auto; object-fit: contain;
    }
    section[data-testid="stSidebar"] [data-testid="stImage"] {
      display: flex; justify-content: center; align-items: center;
    }
    section[data-testid="stSidebar"] [data-testid="stImage"] img {
      width: 128px; height: auto; object-fit: contain;
    }
    .section-note { color: var(--text-color); opacity: .78; margin-top: -.5rem; }
    .st-key-student_search_result {
      border: 1px solid rgba(138,180,248,.38); border-radius: 20px; padding: 1rem 1.25rem;
      box-shadow: 0 12px 30px rgba(0,0,0,.18);
      background: radial-gradient(circle at 90% 0%, rgba(52,168,83,.22), transparent 35%),
                  radial-gradient(circle at 0% 100%, rgba(249,171,0,.20), transparent 35%),
                  rgba(66,133,244,.10);
    }
    .completion-celebration {
      padding: 1.5rem; margin: 1rem auto; border: 1px solid rgba(249,171,0,.65);
      border-radius: 22px; box-shadow: 0 14px 36px rgba(249,171,0,.12);
      background: radial-gradient(circle at 50% 0%, rgba(249,171,0,.34), transparent 65%),
      linear-gradient(135deg, rgba(66,133,244,.22), rgba(161,66,244,.22), rgba(52,168,83,.22));
    }
    .completion-celebration .celebration-icons { font-size: 2rem; letter-spacing: .35rem; }
    .completion-celebration .celebration-title { font-size: 1.6rem; font-weight: 700; margin: .4rem 0; }
    .completion-celebration .celebration-reward {
      display: inline-block; margin-top: .5rem; padding: .5rem 1rem; border-radius: 999px;
      background: rgba(249,171,0,.2); font-weight: 700;
    }
    .resource-button-row {
      display: flex; flex-wrap: wrap; align-items: stretch; justify-content: center;
      gap: .75rem; width: min(100%, 1120px); margin: 1rem auto;
    }
    .resource-button {
      display: flex; align-items: center; justify-content: center; gap: .55rem;
      box-sizing: border-box; flex: 1 1 220px; max-width: 270px;
      min-height: 3.1rem; padding: .65rem 1rem;
      border: 1px solid rgba(138,180,248,.45); border-radius: 12px;
      background: linear-gradient(135deg, rgba(66,133,244,.34), rgba(66,133,244,.14));
      color: #fff !important; font-weight: 700;
      text-align: center; text-decoration: none !important; transition: background .15s ease;
    }
    .resource-button:hover { background: linear-gradient(135deg, rgba(66,133,244,.55), rgba(66,133,244,.25)); color: #fff !important; }
    .resource-button.claim-credits {
      border-color: rgba(249,171,0,.68);
      background: linear-gradient(135deg, rgba(249,171,0,.42), rgba(234,67,53,.22));
    }
    .resource-button.claim-credits:hover {
      background: linear-gradient(135deg, rgba(249,171,0,.60), rgba(234,67,53,.34));
    }
    .resource-button.playlist {
      border-color: rgba(161,66,244,.58);
      background: linear-gradient(135deg, rgba(161,66,244,.36), rgba(66,133,244,.20));
    }
    .resource-button.whatsapp { border-color: #25d366; background: #128c4a; }
    .resource-button.whatsapp:hover { background: #0e7540; }
    .resource-button svg { flex: 0 0 auto; width: 1.35rem; height: 1.35rem; fill: currentColor; }
    @media (max-width: 600px) {
      .st-key-home_banner, .st-key-leaderboard_banner { padding: 18px; }
      .st-key-home_banner [data-testid="stHorizontalBlock"],
      .st-key-leaderboard_banner [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
      .st-key-home_banner [data-testid="column"],
      .st-key-leaderboard_banner [data-testid="column"] {
        flex: 1 1 100% !important; width: 100% !important; min-width: 0;
      }
      .st-key-home_banner [data-testid="stImage"],
      .st-key-leaderboard_banner [data-testid="stImage"] {
        max-width: 112px; padding: 4px; border-radius: 16px;
      }
      .st-key-home_banner [data-testid="stImage"] img,
      .st-key-leaderboard_banner [data-testid="stImage"] img { width: 104px; }
      .resource-button { flex-basis: 100%; max-width: none; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

tracker.initialize_database()


@st.cache_resource
def google_sheets_store(
    spreadsheet_id: str,
    tracking_tab: str,
    roll_map_tab: str,
    service_account_json: str,
) -> GoogleSheetsStore:
    return GoogleSheetsStore(
        spreadsheet_id,
        json.loads(service_account_json),
        tracking_tab,
        roll_map_tab,
    )


@st.cache_data(ttl=120)
def read_google_sheet_tabs(
    spreadsheet_id: str,
    tracking_tab: str,
    roll_map_tab: str,
    service_account_json: str,
) -> tuple[list[str], list[dict[str, str]], list[dict[str, str]]]:
    store = google_sheets_store(
        spreadsheet_id,
        tracking_tab,
        roll_map_tab,
        service_account_json,
    )
    return store.read_tracking_and_roll_number_map()


def google_sheets_configuration() -> tuple[str, str, str, dict] | None:
    try:
        spreadsheet_id = str(st.secrets.get("SPREADSHEET_ID", "")).strip()
        service_account = dict(st.secrets.get("google_service_account", {}))
        tracking_tab = str(st.secrets.get("TRACKING_SHEET_TAB", "Tracking Data")).strip()
        roll_map_tab = str(st.secrets.get("ROLL_NUMBER_MAP_TAB", "rollno map")).strip()
    except StreamlitSecretNotFoundError:
        return None
    if not spreadsheet_id or not service_account:
        return None
    return spreadsheet_id, tracking_tab, roll_map_tab, service_account


SHEET_ROLL_MAP: list[dict[str, str]] = []


def synchronize_google_sheet() -> tuple[GoogleSheetsStore | None, str | None]:
    global SHEET_ROLL_MAP

    configuration = google_sheets_configuration()
    if configuration is None:
        return None, None
    spreadsheet_id, tracking_tab, roll_map_tab, service_account = configuration
    credentials_json = json.dumps(service_account, sort_keys=True)
    headers, records, roll_map = read_google_sheet_tabs(
        spreadsheet_id,
        tracking_tab,
        roll_map_tab,
        credentials_json,
    )
    SHEET_ROLL_MAP = roll_map
    source_digest = hashlib.sha256(
        json.dumps([headers, records], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    mapping = tracker.default_mapping(headers)
    if "name" not in mapping or not {
        "email",
        "skills_profile_url",
    }.intersection(mapping):
        raise ValueError(
            f'The "{tracking_tab}" tab must include a student name and email '
            "or Google Skills profile URL column."
        )
    if tracker.get_app_setting("google_sheet_source_digest") != source_digest:
        content = io.StringIO(newline="")
        writer = csv.DictWriter(content, fieldnames=headers)
        writer.writeheader()
        writer.writerows(records)
        csv_content = content.getvalue().encode("utf-8")
        preview = tracker.preview_import(csv_content, mapping)
        tracker.import_records(
            preview["records"],
            f"Google Sheets · {tracking_tab}",
            preview["errors"],
            authoritative=True,
            approve_new_students=True,
        )
        tracker.set_app_setting("google_sheet_source_digest", source_digest)

    def normalized_name(value: str) -> str:
        return " ".join(value.casefold().split())

    roll_numbers_by_name = {
        normalized_name(row["Name"]): row["Roll Number"]
        for row in roll_map
        if row["Name"]
    }
    tracking_names = {
        normalized_name(str(record.get(mapping["name"], "")))
        for record in records
    }
    students = tracker.get_admin_students()
    students_by_name: dict[str, list[dict]] = {}
    for student in students:
        students_by_name.setdefault(normalized_name(student["name"]), []).append(student)
    for name in roll_numbers_by_name:
        if len(students_by_name.get(name, [])) > 1:
            raise ValueError(
                f'The name "{name}" appears more than once in Tracking Data; its roll number is ambiguous.'
            )
    for student in students:
        name = normalized_name(student["name"])
        visible = name in tracking_names
        roll_number = (
            roll_numbers_by_name[name]
            if name in roll_numbers_by_name
            else student.get("roll_number")
        )
        roll_number = roll_number or None
        if (
            student.get("roll_number") != roll_number
            or bool(student["public_visible"]) != visible
        ):
            tracker.update_student_settings(
                student["id"],
                roll_number,
                visible,
            )
    return (
        google_sheets_store(
            spreadsheet_id,
            tracking_tab,
            roll_map_tab,
            credentials_json,
        ),
        None,
    )


SHEET_STORE: GoogleSheetsStore | None = None
SHEET_SYNC_ERROR: str | None = None
try:
    SHEET_STORE, SHEET_SYNC_ERROR = synchronize_google_sheet()
except Exception as error:
    SHEET_SYNC_ERROR = str(error)


def render_google_sheet_sync() -> None:
    heading(
        "Google Sheets sync",
        "The private spreadsheet is the source of participant progress and curated roll numbers.",
    )
    if SHEET_SYNC_ERROR:
        st.error(
            "Google Sheets sync failed. The displayed roster may be from the last successful "
            f"sync. Details: {SHEET_SYNC_ERROR}"
        )
    elif SHEET_STORE:
        st.success(
            "Google Sheets connected. Data is refreshed on page load and after the two-minute cache expires."
        )
    else:
        st.warning(
            "Google Sheets is not configured. The app is currently using its local SQLite database. "
            "Set SPREADSHEET_ID and [google_service_account] in Streamlit Secrets."
        )
    st.markdown(
        "Update **Tracking Data** with the latest export. Keep the **rollno map** tab intact; it "
        "matches the `Name` and `Roll Number` columns and preserves your curated roll numbers."
    )
    if st.button("Refresh Google Sheets now", type="primary"):
        read_google_sheet_tabs.clear()
        st.rerun()


def admin_password() -> str:
    value = os.getenv("GDG_ADMIN_PASSWORD", "")
    try:
        value = value or str(st.secrets.get("GDG_ADMIN_PASSWORD", ""))
    except StreamlitSecretNotFoundError:
        pass
    return value


def is_admin() -> bool:
    return bool(st.session_state.get("gdg_admin_authenticated"))


def verify_admin_login(configured_password: str) -> None:
    now = time.time()
    attempts = st.session_state.get("gdg_admin_login_attempts", [])
    attempts = [attempt for attempt in attempts if now - attempt < 300]
    password = st.session_state.get("admin_password_input", "")
    if hmac.compare_digest(password, configured_password):
        st.session_state.gdg_admin_authenticated = True
        st.session_state.gdg_admin_login_attempts = []
        st.session_state.gdg_admin_login_error = False
    else:
        attempts.append(now)
        st.session_state.gdg_admin_login_attempts = attempts
        st.session_state.gdg_admin_login_error = True
    st.session_state.pop("admin_password_input", None)


def admin_login() -> bool:
    configured_password = admin_password()
    if not configured_password:
        st.warning(
            "Admin access is not configured. Set `GDG_ADMIN_PASSWORD` in your deployment secrets before enabling imports."
        )
        return False
    if is_admin():
        return True
    now = time.time()
    attempts = [
        attempt
        for attempt in st.session_state.get("gdg_admin_login_attempts", [])
        if now - attempt < 300
    ]
    st.session_state.gdg_admin_login_attempts = attempts
    if len(attempts) >= 5:
        st.error("Too many sign-in attempts. Try again in five minutes.")
        return False
    with st.form("admin_login_form"):
        st.markdown("#### Administrator sign in")
        st.text_input("Admin password", type="password", key="admin_password_input")
        st.form_submit_button(
            "Sign in",
            type="primary",
            on_click=verify_admin_login,
            args=(configured_password,),
        )
    if st.session_state.pop("gdg_admin_login_error", False):
        st.error("That password was not accepted.")
    return is_admin()


def heading(title: str, subtitle: str | None = None) -> None:
    st.title(title)
    if subtitle:
        st.markdown(f'<p class="section-note">{subtitle}</p>', unsafe_allow_html=True)


def render_brand_banner(key: str, eyebrow: str, title: str, description: str) -> None:
    with st.container(key=key):
        copy, logo = st.columns([1.5, 0.65], vertical_alignment="center")
        with copy:
            st.markdown(
                f"""
                <div class="hero">
                  <div class="eyebrow">{eyebrow}</div>
                  <h1>{title}</h1>
                  <p>{description}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with logo:
            st.image(str(LOGO_PATH), width=170)


def render_resource_buttons() -> None:
    phone = SUPPORT_PHONE.lstrip("+")
    resources = [
        ("Step 1: Claim the credits", CLAIM_CREDITS_URL, "claim-credits"),
        ("Campaign syllabus", CAMPAIGN_SYLLABUS_URL, "syllabus"),
        ("Playlist to complete", LAB_PLAYLIST_URL, "playlist"),
    ]
    buttons = "".join(
        f'<a class="resource-button {style}" href="{html.escape(url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{html.escape(label)}</a>'
        for label, url, style in resources
    )
    st.markdown(
        f"""
        <div class="resource-button-row">
          {buttons}
          <a class="resource-button whatsapp" href="https://wa.me/{phone}" target="_blank"
             rel="noopener noreferrer" aria-label="Contact for help on WhatsApp">
            <svg viewBox="0 0 32 32" role="img" aria-label="WhatsApp">
            <path d="M16.04 3C8.86 3 3.02 8.84 3.02 16.02c0 2.3.6 4.55 1.74 6.54L3 29l6.62-1.73a13 13 0 0 0 6.42 1.69h.01c7.18 0 13.02-5.84 13.02-13.02A12.94 12.94 0 0 0 16.04 3Zm0 23.75h-.01c-2.01 0-3.98-.54-5.69-1.57l-.41-.24-3.93 1.03 1.05-3.83-.27-.42a10.7 10.7 0 0 1-1.64-5.7c0-6.02 4.9-10.92 10.92-10.92 2.92 0 5.66 1.14 7.72 3.2a10.85 10.85 0 0 1 3.2 7.73c0 6.02-4.9 10.92-10.94 10.92Zm5.99-8.18c-.33-.16-1.95-.96-2.25-1.07-.3-.11-.52-.16-.74.16-.22.33-.85 1.07-1.04 1.29-.19.22-.38.25-.71.08-.33-.16-1.39-.51-2.65-1.63-.98-.87-1.64-1.95-1.83-2.28-.19-.33-.02-.5.14-.66.15-.15.33-.38.49-.57.16-.19.22-.33.33-.55.11-.22.05-.41-.03-.57-.08-.16-.74-1.78-1.01-2.44-.26-.64-.53-.55-.74-.56h-.63c-.22 0-.57.08-.87.41-.3.33-1.15 1.13-1.15 2.75 0 1.62 1.18 3.18 1.34 3.4.16.22 2.32 3.54 5.63 4.97.79.34 1.4.54 1.87.69.79.25 1.51.21 2.08.13.63-.09 1.95-.8 2.23-1.56.27-.77.27-1.43.19-1.56-.08-.14-.3-.22-.63-.38Z"/>
            </svg>
            <span>Contact for help</span>
          </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def skills_profile_id(profile_url: str | None) -> str | None:
    if not profile_url:
        return None
    parsed_url = urlparse(profile_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        return None
    path_segments = [segment for segment in parsed_url.path.split("/") if segment]
    try:
        profile_index = path_segments.index("public_profiles")
    except ValueError:
        return None
    return path_segments[profile_index + 1] if profile_index + 1 < len(path_segments) else None


def safe_profile_url(profile_url: str | None) -> str:
    if not profile_url:
        return ""
    parsed_url = urlparse(profile_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        return ""
    return profile_url


def render_student(student: dict) -> None:
    with st.container(key="student_search_result"):
        st.subheader(student["name"])
        st.caption(f"Roll number: {student.get('roll_number') or 'Not assigned'}")
        boost_profile_id = skills_profile_id(student.get("skills_profile_url"))
        st.caption(
            "Google Skills Boost profile ID: "
            f"{boost_profile_id or 'Not available in profile link'}"
        )
        profile_links = [
            ("Google Skills profile", student.get("skills_profile_url")),
            (
                "Google Developer profile",
                student.get("developer_profile_url")
                if student.get("is_gear_participant")
                else None,
            ),
        ]
        available_links = [
            (label, url)
            for label, url in profile_links
            if safe_profile_url(url)
        ]
        if available_links:
            link_columns = st.columns(len(available_links))
            for column, (label, url) in zip(link_columns, available_links):
                column.link_button(label, url, use_container_width=True)
        count = int(student["badges_count"])
        st.progress(count / 10, text=f"{count}/10 skill badges completed")
        if count >= 10:
            st.balloons()
            st.markdown(
                f"""
                <div class="completion-celebration">
                  <div class="celebration-icons">🏆 🎉 ✨</div>
                  <div class="celebration-title">Quest complete!</div>
                  <h2>Congratulations, {html.escape(student["name"])}!</h2>
                  <p>You earned all 10 skill badges. Your dedication paid off!</p>
                  <div class="celebration-reward">🏅 10 / 10 badges earned</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif count == 0:
            st.info("You haven't started your skill badges yet. Use these resources to get started.")
        else:
            st.info(f"You've completed {count} of 10 skill badges, with {10 - count} to go.")
        st.markdown("#### Completed skill badges")
        badge_names = student.get("badges_names", [])
        if len(badge_names) > count:
            st.warning(
                "The badge titles do not match the recorded completion count. "
                "Check the latest tracking sheet before relying on individual titles."
            )
        elif badge_names:
            badge_columns = st.columns(2)
            for index, badge_name in enumerate(badge_names):
                badge_columns[index % 2].success(f"✅ {badge_name}")
        else:
            st.info("No completed badge titles are recorded yet.")
        if count > len(badge_names):
            st.caption(
                f'{count - len(badge_names)} additional completed badge(s) are included in the total, '
                "but their titles were not provided."
            )
        st.metric("Access code status", student.get("access_code_status") or "Not reported")
        if count < 10:
            st.markdown("#### Your learning resources")
            render_resource_buttons()
        st.markdown("#### GEAR and profile status")
        details = [
            ("GEAR digital badges", student.get("gear_badges")),
            ("Milestone", student.get("milestone")),
            ("Google Skills profile status", student.get("skills_profile_status")),
            ("Google Developer profile status", student.get("developer_profile_status")),
        ]
        for start in range(0, len(details), 2):
            columns = st.columns(2)
            for column, (label, value) in zip(columns, details[start : start + 2]):
                column.metric(label, value or "Not reported")


def render_home() -> None:
    st.iframe(
        """
        <style>
          :root { color-scheme: dark; }
          .countdown {
            box-sizing: border-box; width: 100%; padding: 18px 24px; border-radius: 22px;
            border: 1px solid rgba(138,180,248,.42);
            background: linear-gradient(120deg, #101722, #172238 58%, #252044);
            box-shadow: 0 12px 32px rgba(0,0,0,.18); color: #fff; text-align: center;
            font-family: Arial, sans-serif;
          }
          .countdown-title {
            margin: 0 0 12px; color: #a9ccff; font-size: .78rem;
            font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
          }
          .countdown-units {
            display: flex; justify-content: center; gap: clamp(10px, 3vw, 30px);
          }
          .countdown-unit { min-width: 58px; }
          .countdown-value { font-size: clamp(1.7rem, 5vw, 2.5rem); font-weight: 700; }
          .countdown-label {
            color: rgba(255,255,255,.72); font-size: .7rem;
            letter-spacing: .09em; text-transform: uppercase;
          }
          .countdown-deadline { margin: 12px 0 0; color: rgba(255,255,255,.78); font-size: .85rem; }
          @media (max-width: 420px) {
            .countdown { padding: 16px 10px; }
            .countdown-units { gap: 8px; }
            .countdown-unit { min-width: 52px; }
          }
        </style>
        <section class="countdown" aria-label="Campaign countdown">
          <h2 class="countdown-title">Time remaining to complete the campaign</h2>
          <div class="countdown-units" id="countdown" role="timer">
            <div class="countdown-unit"><div class="countdown-value" id="days">--</div><div class="countdown-label">Days</div></div>
            <div class="countdown-unit"><div class="countdown-value" id="hours">--</div><div class="countdown-label">Hours</div></div>
            <div class="countdown-unit"><div class="countdown-value" id="minutes">--</div><div class="countdown-label">Minutes</div></div>
            <div class="countdown-unit"><div class="countdown-value" id="seconds">--</div><div class="countdown-label">Seconds</div></div>
          </div>
          <p class="countdown-deadline">Deadline: November 23, 2026 at 11:59 PM (your local time)</p>
        </section>
        <script>
          const deadline = new Date(2026, 10, 23, 23, 59, 0).getTime();
          const updateCountdown = () => {
            const remaining = deadline - Date.now();
            if (remaining <= 0) {
              document.getElementById("countdown").innerHTML =
                '<div class="countdown-value">Campaign complete</div>';
              return;
            }
            const days = Math.floor(remaining / 86400000);
            const hours = Math.floor((remaining % 86400000) / 3600000);
            const minutes = Math.floor((remaining % 3600000) / 60000);
            const seconds = Math.floor((remaining % 60000) / 1000);
            document.getElementById("days").textContent = days;
            document.getElementById("hours").textContent = String(hours).padStart(2, "0");
            document.getElementById("minutes").textContent = String(minutes).padStart(2, "0");
            document.getElementById("seconds").textContent = String(seconds).padStart(2, "0");
          };
          updateCountdown();
          setInterval(updateCountdown, 1000);
        </script>
        """,
        height=180,
        alt="Campaign countdown",
    )
    render_brand_banner(
        "home_banner",
        "GDG on Campus · MCET",
        "Make your cloud progress visible.",
        "Find your learning progress, celebrate milestones, and keep moving forward.",
    )
    metrics = tracker.get_dashboard_data()
    first, second, third, fourth = st.columns(4)
    first.metric("Participating students", f'{metrics["students"]:,}')
    second.metric("Students completed all 10", f'{metrics["completed"]:,}')
    third.metric(
        "Access code redemption status",
        f'{metrics["access_codes_redeemed"]:,} redeemed · '
        f'{metrics["access_codes_not_redeemed"]:,} not redeemed',
    )
    fourth.metric("Overall completion", f'{metrics["completion_rate"]:.1f}%')
    st.markdown("### Campaign resources")
    render_resource_buttons()
    st.markdown("### Find a student")
    st.caption(
        "Participants in the tracking sheet are public. Roll numbers and Google profile links are shown; student emails are not."
    )
    query = st.text_input(
        "Search by name, roll number, or email",
        placeholder="Enter your name, college ID, or email address",
        help="Names and roll numbers can be partial; email search requires your exact email address.",
        key="student_search",
    )
    if query.strip():
        matches = tracker.search_public_students(query)
        if not matches:
            st.info("No participant matched that search.")
        elif len(matches) == 1:
            profile = tracker.get_student_profile(matches[0]["id"])
            if profile:
                render_student(profile)
        else:
            labels = {
                f'{student["name"]} · {student.get("roll_number") or "Roll number not assigned"} · Match {index}': student["id"]
                for index, student in enumerate(matches, start=1)
            }
            selected = st.selectbox("Choose a matching profile", list(labels))
            profile = tracker.get_student_profile(labels[selected])
            if profile:
                render_student(profile)
    st.markdown("---")
    st.subheader("Community leaderboard")
    community_target = metrics["students"] * 10
    community_progress = metrics["badges"] / community_target if community_target else 0
    st.progress(
        community_progress,
        text=f'Community quest · {metrics["badges"]:,}/{community_target:,} skill badges',
    )
    leaders = tracker.get_leaderboard(limit=3)
    if leaders:
        for index, leader in enumerate(leaders, start=1):
            icon = ("🥇", "🥈", "🥉")[index - 1]
            st.markdown(f"{icon} **{leader['name']}** · {leader['badges_count']}/10 badges")
    else:
        st.info("The leaderboard will appear when participant data is available.")
    st.markdown("---")
    st.subheader("GDG participants")
    st.caption("Browse names only, or search by name or roll number to find a participant.")
    participant_search = st.text_input(
        "Filter participants",
        placeholder="Search participant name or roll number",
        key="participant_search",
    ).strip()
    page_size = 25
    if st.session_state.get("participant_list_search") != participant_search:
        st.session_state.participant_list_search = participant_search
        st.session_state.participant_list_limit = page_size
    participant_limit = st.session_state.setdefault("participant_list_limit", page_size)
    participants, has_more_participants = tracker.get_public_participants(
        limit=participant_limit,
        search=participant_search,
    )
    if participants:
        participant_frame = pd.DataFrame(
            [
                {
                    "Participant": participant["name"],
                }
                for participant in participants
            ]
        )
        st.dataframe(
            participant_frame,
            width="stretch",
            hide_index=True,
            height=min(460, 38 + 35 * len(participants)),
        )
        if has_more_participants and st.button(
            "Load more participants",
            key="load_more_participants",
            use_container_width=False,
        ):
            st.session_state.participant_list_limit += page_size
            st.rerun()
    else:
        if participant_search:
            st.info("No participants matched that filter.")
        else:
            st.info("No participants are available yet.")


def render_leaderboard() -> None:
    render_brand_banner(
        "leaderboard_banner",
        "GDG on Campus · MCET",
        "Community leaderboard",
        "Celebrate progress and see how students rank by completed skill badges.",
    )
    st.caption("Ties use a consistent, alphabetical order.")
    limit_label = st.selectbox("Show students", ["Top 10", "Top 25"])
    limit = int(limit_label.split()[1])
    leaders = tracker.get_leaderboard(limit=limit, sort_by="progress")
    if not leaders:
        st.info("No student profiles are available on the leaderboard yet.")
        return
    if len(leaders) >= 3:
        podium = st.columns([1, 1.15, 1])
        for idx, display_idx in enumerate((1, 0, 2)):
            student = leaders[display_idx]
            with podium[idx]:
                st.markdown(f"### {('🥈', '🥇', '🥉')[idx]} #{display_idx + 1}")
                st.subheader(student["name"])
                st.metric("Skill badges", f'{student["badges_count"]}/10')
    frame = pd.DataFrame(
        [
            {
                "Rank": rank,
                "Student": student["name"],
                "Roll number": student.get("roll_number") or "Not assigned",
                "Skill badges": student["badges_count"],
                "Google Skills profile": student.get("skills_profile_url") or "",
                "Google Developer profile": student.get("developer_profile_url") or "",
            }
            for rank, student in enumerate(leaders, start=1)
        ]
    )
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Google Skills profile": st.column_config.LinkColumn(
                "Google Skills profile", display_text="Open profile"
            ),
            "Google Developer profile": st.column_config.LinkColumn(
                "Google Developer profile", display_text="Open profile"
            ),
        },
    )
    safe_frame = pd.DataFrame(
        [
            {key: tracker.spreadsheet_safe(value) for key, value in row.items()}
            for row in frame.to_dict(orient="records")
        ]
    )
    st.download_button(
        "Download leaderboard CSV",
        data=safe_frame.to_csv(index=False).encode("utf-8-sig"),
        file_name="gdg-mcet-leaderboard.csv",
        mime="text/csv",
    )


def render_csv_import() -> None:
    heading("CSV sync", "Review the latest tracking sheet before applying an atomic, record-level update.")
    st.warning(
        "The provided sheet does not contain roll numbers. Students are matched by email (or Google Skills profile URL), "
        "and administrators can assign roll numbers after importing."
    )
    st.download_button(
        "Download CSV template",
        data=tracker.csv_template().encode("utf-8-sig"),
        file_name="gdg-mcet-tracking-template.csv",
        mime="text/csv",
    )
    uploaded = st.file_uploader("Upload the latest Google tracking CSV", type=["csv"], key="csv_upload")
    approve_new_students = st.checkbox(
        "Approve new profiles for public display",
        value=False,
        help=(
            "Use only for a trusted, already-curated migration snapshot. "
            "Leave unchecked for routine tracking-sheet updates."
        ),
        key="approve_new_students",
    )
    if not uploaded:
        st.download_button(
            "Download curated migration snapshot",
            data=tracker.export_import_snapshot().encode("utf-8-sig"),
            file_name="gdg-mcet-curated-migration.csv",
            mime="text/csv",
            help="Contains student emails and roll numbers; keep this file private and never commit it to GitHub.",
        )
        history = tracker.get_import_history()
        if history:
            last = history[0]
            st.caption(f'Last successful import: {last["filename"]} · {last["imported_at"][:16]}')
        st.info("Choose the latest CSV to preview new, changed, and unchanged student records.")
        return

    content = uploaded.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    try:
        headers, _ = tracker.parse_csv(content)
    except (UnicodeDecodeError, csv.Error, ValueError) as error:
        st.error(f"Could not read this CSV: {error}")
        return

    stored = tracker.load_mapping()
    defaults = tracker.default_mapping(headers)
    default_mapping = {**defaults, **stored}
    st.markdown("#### Map columns")
    st.caption("The current Google sheet columns are detected automatically; change mappings for future sheet formats.")
    mapping: dict[str, str] = {}
    grid = st.columns(3)
    for index, (field, label) in enumerate(tracker.FIELD_LABELS.items()):
        options = ["— Skip —", *headers]
        saved = default_mapping.get(field, "")
        selected = saved if saved in headers else "— Skip —"
        with grid[index % 3]:
            value = st.selectbox(
                label,
                options,
                index=options.index(selected),
                key=f"map_{field}_{digest[:8]}",
            )
        if value != "— Skip —":
            mapping[field] = value
    save_column, _ = st.columns([1, 1])
    with save_column:
        if st.button("Save column mapping", key="save_column_mapping"):
            tracker.save_mapping(mapping)
            st.success("Column mapping saved for your next upload.")
    authoritative = st.checkbox(
        "This is a full authoritative snapshot — allow progress decreases",
        help=(
            "Leave unchecked for the usual cumulative tracking sheet. Blank fields never erase existing values. "
            "Only check this when the source explicitly represents a complete corrected snapshot."
        ),
    )
    if authoritative:
        st.warning("Authoritative mode can lower recorded badge counts and add compensating XP ledger entries.")
        confirm = st.checkbox("I confirm this file is the complete, corrected snapshot.")
    else:
        confirm = False

    if st.button("Analyze CSV", type="primary", key="analyze_csv"):
        try:
            preview = tracker.preview_import(content, mapping)
            st.session_state.csv_preview = {
                "digest": digest,
                "mapping": mapping,
                "authoritative": authoritative,
                "approve_new_students": approve_new_students,
                "confirmed": confirm,
                "preview": preview,
                "filename": uploaded.name,
            }
        except ValueError as error:
            st.error(str(error))

    saved_preview = st.session_state.get("csv_preview")
    if (
        not saved_preview
        or saved_preview["digest"] != digest
        or saved_preview["mapping"] != mapping
        or saved_preview["authoritative"] != authoritative
        or saved_preview.get("approve_new_students", False) != approve_new_students
    ):
        st.caption("Analyze the current file and mapping to see its impact.")
        return
    preview = saved_preview["preview"]
    st.markdown("#### Import preview")
    metric_columns = st.columns(4)
    metric_columns[0].metric("Rows detected", preview["total"])
    metric_columns[1].metric("New students", preview["new_students"])
    metric_columns[2].metric("Existing records changed", preview["updated_students"])
    metric_columns[3].metric("Unchanged", preview["unchanged_students"])
    if preview["errors"]:
        with st.expander(f"Review {len(preview['errors'])} skipped row(s)"):
            st.dataframe(pd.DataFrame(preview["errors"]), width="stretch", hide_index=True)
    if preview["records"]:
        sample = [
            {
                "Student": row.get("name"),
                "Email": row.get("email") or "—",
                "Roll number": row.get("roll_number") or "—",
                "Skill badges": row.get("badges_count") if row.get("badges_count") is not None else "—",
                "Record": "New" if row["_existing"] is None else "Existing",
                "Changes": (
                    "New student"
                    if row["_existing"] is None
                    else ", ".join(tracker.FIELD_LABELS[field] for field in row["_changed_fields"])
                    or "No changes"
                ),
            }
            for row in preview["records"][:10]
        ]
        st.dataframe(pd.DataFrame(sample), width="stretch", hide_index=True)
        st.caption(f"Previewing up to 10 of {len(preview['records'])} importable records.")
    valid_authoritative = not saved_preview["authoritative"] or saved_preview["confirmed"]
    if not valid_authoritative and st.button("Confirm authoritative correction", key="confirm_authoritative"):
        st.session_state.csv_preview["confirmed"] = True
        st.rerun()
    if not valid_authoritative:
        st.info("Confirm that this is a full corrected snapshot before importing in authoritative mode.")
    elif st.button("Import and synchronize", type="primary", key="run_import"):
        try:
            result = tracker.import_records(
                preview["records"],
                saved_preview["filename"],
                preview["errors"],
                authoritative=saved_preview["authoritative"],
                approve_new_students=saved_preview["approve_new_students"],
            )
            st.session_state.pop("csv_preview", None)
            st.success(
                f"Import #{result['import_id']} completed: {result['new_students']} new, "
                f"{result['updated_students']} updated, {result['unchanged_students']} unchanged, "
                f"{result['failed_records']} skipped."
            )
            st.rerun()
        except sqlite3.IntegrityError as error:
            st.error(f"Import was rolled back because a unique student value conflicts with an existing record: {error}")
        except Exception as error:
            st.error(f"Import was rolled back. No partial changes were saved: {error}")


def render_student_admin() -> None:
    heading(
        "Student records",
        "Participant roster and roll numbers are synced from Tracking Data and rollno map.",
    )
    if st.button("Refresh contact numbers from Google Sheets", key="refresh_admin_contacts"):
        read_google_sheet_tabs.clear()
        st.rerun()
    contact_count = sum(bool(row.get("Phone Number")) for row in SHEET_ROLL_MAP)
    st.caption(f"{contact_count} contact numbers loaded from rollno map.")
    search = st.text_input("Filter by name, email, or roll number")
    completion_filter = st.selectbox(
        "Progress status", ["All", "Not started", "In progress", "1–2 remaining", "Completed all 10"]
    )
    total = tracker.count_admin_students(search, completion_filter=completion_filter)
    page_size = 100
    page_count = max(1, (total + page_size - 1) // page_size)
    page_number = st.selectbox("Page", range(1, page_count + 1), format_func=lambda value: f"{value} of {page_count}")
    students = tracker.get_admin_students(
        search,
        limit=page_size,
        offset=(page_number - 1) * page_size,
        completion_filter=completion_filter,
    )
    if not students:
        st.info("No student records found. Add participant rows to the Tracking Data sheet.")
        return
    st.caption(f"Showing {len(students)} of {total} matching records.")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Name": student["name"],
                    "Roll number": student.get("roll_number") or "",
                    "Phone number (admin only)": phone_number_for_student(
                        student,
                        SHEET_ROLL_MAP,
                    ),
                    "Email (admin only)": student.get("email") or "",
                    "Badges": f'{student["badges_count"]}/10',
                    "Achievement status": "Complete" if student["badges_count"] == 10 else "In progress",
                    "XP": student["xp"],
                    "Public profile": "Public" if student["public_visible"] else "Not in tracking sheet",
                    "Google Skills Boost profile": safe_profile_url(
                        student.get("skills_profile_url")
                    ),
                    "Google Developer profile": safe_profile_url(
                        student.get("developer_profile_url")
                    ),
                }
                for student in students
            ]
        ),
        width="stretch",
        hide_index=True,
        column_config={
            "Google Skills Boost profile": st.column_config.LinkColumn(
                "Google Skills Boost profile",
                display_text="Open profile",
            ),
            "Google Developer profile": st.column_config.LinkColumn(
                "Google Developer profile",
                display_text="Open profile",
            ),
        },
    )
    st.download_button(
        "Export filtered records (admin only)",
        data=tracker.export_students(
            tracker.get_admin_students(search, completion_filter=completion_filter)
        ).encode("utf-8-sig"),
        file_name="gdg-mcet-student-progress.csv",
        mime="text/csv",
    )
    st.markdown("#### Student record")
    options = {
        f'{student["name"]} · {student.get("roll_number") or "No roll number"} · {student.get("email") or ""}': student
        for student in students
    }
    selected_label = st.selectbox("Select a student", list(options))
    selected = options[selected_label]
    selected_phone = phone_number_for_student(selected, SHEET_ROLL_MAP)
    st.caption(
        f'Roll number: {selected.get("roll_number") or "Not assigned"} · '
        f'Phone number: {selected_phone or "Not provided"} · '
        "Public visibility follows membership in Tracking Data. Manage roll numbers and phone numbers in the rollno map tab."
    )
    transactions = tracker.get_xp_transactions(selected["id"])
    if transactions:
        with st.expander("XP transaction audit"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "XP change": item["amount"],
                            "Reason": item["reason"],
                            "Date": item["created_at"],
                        }
                        for item in transactions
                    ]
                ),
                width="stretch",
                hide_index=True,
            )


def render_import_history() -> None:
    heading("Sync history", "Recent spreadsheet synchronizations and skipped-row reports.")
    history = tracker.get_import_history()
    if not history:
        st.info("No Google Sheets changes have been synchronized yet.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": item["id"],
                    "File": item["filename"],
                    "Uploaded by": item["uploaded_by"],
                    "Imported at": item["imported_at"],
                    "Mode": item["mode"],
                    "Status": item["status"],
                    "Rows": item["total_records"],
                    "New": item["new_students"],
                    "Updated": item["updated_students"],
                    "Unchanged": item["unchanged_students"],
                    "Skipped": item["failed_records"],
                }
                for item in history
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    snapshots = [
        {"Date": item["imported_at"], **item["snapshot"]}
        for item in reversed(history)
        if item.get("snapshot")
    ]
    if snapshots:
        st.markdown("#### Progress across imports")
        snapshot_frame = pd.DataFrame(snapshots)
        import plotly.express as px

        fig = px.line(
            snapshot_frame,
            x="Date",
            y=["total_students", "total_badges", "completed_students"],
            markers=True,
            labels={"value": "Total", "variable": "Measure"},
            color_discrete_sequence=["#4285f4", "#34a853", "#f9ab00"],
        )
        st.plotly_chart(fig, width="stretch")
    for item in history:
        if item["errors"]:
            with st.expander(f'Import #{item["id"]} · {len(item["errors"])} skipped row(s)'):
                st.dataframe(pd.DataFrame(item["errors"]), width="stretch", hide_index=True)


def render_gamification_settings() -> None:
    heading("Gamification settings", "XP and levels are internal community rewards, not official Google credentials.")
    scoring = tracker.get_gamification_settings()
    with st.form("xp_settings_form"):
        xp_per_badge = st.number_input("XP per skill badge", min_value=0, step=25, value=scoring["xp_per_badge"])
        bonus_5 = st.number_input("Bonus at 5 badges", min_value=0, step=50, value=scoring["bonus_5"])
        bonus_10 = st.number_input("Bonus at 10 badges", min_value=0, step=50, value=scoring["bonus_10"])
        save_scoring = st.form_submit_button("Save XP scoring", type="primary")
    if save_scoring:
        try:
            tracker.update_gamification_settings(xp_per_badge, bonus_5, bonus_10)
            st.success("XP scoring saved. New settings apply to future progress changes; existing transactions remain auditable.")
        except ValueError as error:
            st.error(str(error))
    levels = tracker.get_level_settings()
    edited = st.data_editor(
        pd.DataFrame(levels),
        num_rows="dynamic",
        width="stretch",
        column_config={
            "name": st.column_config.TextColumn("Level name", required=True),
            "xp": st.column_config.NumberColumn("Minimum XP", min_value=0, step=50, required=True),
        },
        key="levels_editor",
    )
    if st.button("Save level thresholds", type="primary"):
        try:
            tracker.update_level_settings(edited.to_dict(orient="records"))
            st.success("Level thresholds saved.")
        except (ValueError, KeyError, TypeError) as error:
            st.error(str(error))
def render_admin() -> None:
    heading(
        "Admin console",
        "Review participant analytics, roll-number records, spreadsheet sync, and community settings.",
    )
    if not admin_login():
        return
    metrics = tracker.get_dashboard_data()
    if SHEET_SYNC_ERROR:
        st.error(f"Google Sheets sync failed: {SHEET_SYNC_ERROR}")
    elif not SHEET_STORE:
        st.warning(
            "Google Sheets is not configured. Changes are local only and may be lost when the app restarts."
        )
    elif metrics["students"]:
        st.warning(
            "All participants in Tracking Data are publicly visible, including roll numbers and any "
            "Google profile links present in the sheet."
        )
    with st.sidebar:
        if st.button("Sign out of admin"):
            st.session_state.gdg_admin_authenticated = False
            st.rerun()
    stat_columns = st.columns(5)
    stat_columns[0].metric("Registered", metrics["students"])
    stat_columns[1].metric("Started", metrics["started"])
    stat_columns[2].metric("Not started", metrics["not_started"])
    stat_columns[3].metric("Completed all 10", metrics["completed"])
    stat_columns[4].metric("Average badges", f'{metrics["average"]:.1f}/10')
    students = tracker.get_all_students()
    if students:
        import plotly.express as px

        counts = pd.Series([int(student["badges_count"]) for student in students])
        distribution = counts.value_counts().reindex(range(11), fill_value=0).sort_index()
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.markdown("#### Student progress distribution")
            fig = px.bar(
                x=[f"{n}/10" for n in distribution.index],
                y=distribution.values,
                labels={"x": "Skill badges completed", "y": "Students"},
                color=distribution.index,
                color_continuous_scale=["#d9e2f2", "#4285f4"],
            )
            fig.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")
        with chart_right:
            st.markdown("#### Badge-wise completion")
            by_badge = [
                {
                    "Skill badge": title,
                    "Named completions": sum(
                        title in json.loads(student["badges_names"] or "[]") for student in students
                    ),
                }
                for title in tracker.LAB_CATALOG
            ]
            fig = px.bar(
                pd.DataFrame(by_badge),
                x="Named completions",
                y="Skill badge",
                orientation="h",
                color_discrete_sequence=["#34a853"],
            )
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, width="stretch")
        alerts = st.columns(3)
        alerts[0].metric("No badges yet", sum(s["badges_count"] == 0 for s in students))
        alerts[1].metric("1–2 badges remaining", sum(s["badges_count"] in (8, 9) for s in students))
        alerts[2].metric("Added in last 14 days", metrics["recently_added"])
        st.markdown("#### Top performers")
        top = sorted(students, key=lambda row: (-row["badges_count"], row["name"].casefold()))[:5]
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Student": student["name"],
                        "Roll number": student.get("roll_number") or "Not assigned",
                        "Badges": f'{student["badges_count"]}/10',
                    }
                    for student in top
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    tab_sheet, tab_students, tab_history, tab_settings = st.tabs(
        ["Google Sheets", "Students", "Sync history", "Gamification"]
    )
    with tab_sheet:
        render_google_sheet_sync()
    with tab_students:
        render_student_admin()
    with tab_history:
        render_import_history()
    with tab_settings:
        render_gamification_settings()


with st.sidebar:
    st.image(str(LOGO_PATH), width=160)
    st.caption("Cloud learning tracker")
    if SHEET_SYNC_ERROR:
        st.warning("Google Sheets is unavailable; the roster may be stale.")
    elif not SHEET_STORE:
        st.caption("Google Sheets is not configured.")
    pages = ["Home", "Leaderboard"]
    if admin_password():
        pages.append("Admin")
    page = st.radio(
        "Navigate",
        pages,
        label_visibility="collapsed",
        key="page_navigation",
    )

if page == "Home":
    render_home()
elif page == "Leaderboard":
    render_leaderboard()
else:
    render_admin()