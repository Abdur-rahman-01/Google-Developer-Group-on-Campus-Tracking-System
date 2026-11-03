# GDG MCET Cloud Learning Tracker

A Streamlit portal for GDG on Campus at Methodist College of Engineering and Technology. The sidebar switches between Home and Leaderboard. When `GDG_ADMIN_PASSWORD` is configured, an authenticated Admin page is also available for Google Sheets sync status, participant records, sync history, and gamification settings.

The supplied Google Cloud logo image is stored in `assets/google-cloud-logo.png` and is used in the sidebar and the Home and Leaderboard banners.

## What this CSV contains

The supplied `GDGC-MCETH [01 Nov].csv` has 98 records and these columns:

- User Name, User Email
- Google Skills Profile URL and Status
- Google Developer Profile URL and Status
- Access Code and Access Code Redemption Status
- Milestone Completed, GEAR Digital Badges
- Skill Badges Completed Count and Skill Badges Completed Names

There is **no roll-number column**. The app matches progress by email (or Google Skills profile URL) and loads curated roll numbers by student name from the separate **rollno map** tab. Raw access codes are deliberately skipped because they are redeemable secrets; the redemption-status field is imported.

## Run locally

Requires Python 3.10 or later.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

The local database is created at `data/gdg_tracker.db`. Set `GDG_DB_PATH` to choose another path. Existing database records are retained; a fresh database will be empty.

## Student privacy

Every participant in **Tracking Data** is public on the Home participant list and leaderboard. The participant list shows names only and can be filtered by name or roll number. Searching for a participant shows their roll number, Google Skills Boost profile ID when present in its URL, both profile links, badge count and names, access-code redemption status, GEAR badges and milestone, and Google Skills/Developer completion statuses. Student emails, raw access codes, XP, and platform levels are never displayed. Keep the spreadsheet private, and only include students who should have these details published. Incomplete profiles show learning links and a WhatsApp help button; completed profiles celebrate all 10 skill badges. Use HTTPS for any public deployment.

## Google Sheets synchronization rules

1. The app reads the full **Tracking Data** tab, detects supported headers, and matches progress records by email or Google Skills profile URL.
2. The latest tab is treated as an authoritative snapshot, so corrected badge counts can decrease. Progress and XP adjustments are applied only when the source data changes.
3. Roll numbers are matched by name from **rollno map** and are never overwritten by replacing the tracking export.
4. All students present in **Tracking Data** are public. Students removed from that tab are hidden on the next successful sync.
5. The app skips raw access codes. Keep the spreadsheet private because it contains participant email and profile data.

The CSV's completed-badge count is the source for overall progress. Named badge completion is shown only when the supplied “Skill Badges Completed Names” field identifies one of the ten badge titles; unnamed completions are not guessed.

## Deployment

Keep Streamlit Community Cloud and use a private Google spreadsheet as the durable source for student progress and roll numbers. SQLite is only a local working cache for calculations and sync history; the participant roster is reloaded from Sheets.

### Prepare the spreadsheet

1. Create a private Google spreadsheet with a **Tracking Data** tab. Paste the latest Google tracking export there, including its header row. The app detects supported column names automatically; the tab must contain a student name plus an email or Google Skills profile URL.
2. Keep the curated **rollno map** tab with columns `Name` and `Roll Number`. The app recognizes common header variants such as `Student Name` and `Roll No`. The tab is kept separate so replacing the tracking export does not remove curated roll numbers.
3. Copy the curated name/roll-number pairs into **rollno map** once. Later tracking exports do not need roll numbers; update the map directly when assigning or correcting them.

### Connect Streamlit to Sheets

1. Create a Google service account, enable the Google Sheets API for its project, and share the spreadsheet with the service account's `client_email` as an **Editor**. The app can create **rollno map** with its required headers if the tab is missing; edit the name/roll-number pairs directly in Sheets.
2. In Streamlit Community Cloud, open the app's **Settings → Secrets** and add the spreadsheet ID, tab names, and service-account fields. Keep these credentials private and out of GitHub:

```toml
SPREADSHEET_ID = "your-google-spreadsheet-id"
TRACKING_SHEET_TAB = "Tracking Data"
ROLL_NUMBER_MAP_TAB = "rollno map"
GDG_ADMIN_PASSWORD = "use-a-long-unique-password"

[google_service_account]
type = "service_account"
project_id = "your-google-cloud-project"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

3. Save the secrets and reboot the app. Open **Admin → Google Sheets** to verify the connection. The app refreshes the tracking tab every two minutes; you can also request an immediate refresh there.
4. When updating participant progress, replace the data rows in **Tracking Data** while preserving the header row. Do not clear or replace **rollno map**. All rows in Tracking Data are publicly visible, including roll number and profile links; do not put anyone there who should remain private.

The spreadsheet must remain private. Google Sheets version history provides recovery for edits; the app's ignored local SQLite file is not required for preserving the roster across deploys. The app's import/sync history and gamification settings remain local and may reset when Community Cloud replaces the app instance.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests cover initial imports, repeat-import idempotency, cumulative and authoritative updates, blank-field preservation, duplicate detection, public-profile privacy, and configurable mappings.
