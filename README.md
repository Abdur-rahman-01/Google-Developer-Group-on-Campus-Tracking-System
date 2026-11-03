# GDG MCET Cloud Learning Tracker

A Streamlit portal for GDG on Campus at Methodist College of Engineering and Technology. The sidebar switches between Home and Leaderboard. When `GDG_ADMIN_PASSWORD` is configured, an authenticated Admin page is also available for CSV imports, student visibility approvals, import history, and gamification settings.

The supplied Google Cloud logo image is stored in `assets/google-cloud-logo.png` and is used in the sidebar and the Home and Leaderboard banners.

## What this CSV contains

The supplied `GDGC-MCETH [01 Nov].csv` has 98 records and these columns:

- User Name, User Email
- Google Skills Profile URL and Status
- Google Developer Profile URL and Status
- Access Code and Access Code Redemption Status
- Milestone Completed, GEAR Digital Badges
- Skill Badges Completed Count and Skill Badges Completed Names

There is **no roll-number column**. The app matches student records by email (or Google Skills profile URL) and loads curated roll numbers from the separate **Roll Number Map** tab. Raw access codes are deliberately skipped because they are redeemable secrets; the redemption-status field is imported.

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

Public search and the Home-page participant list show only profiles explicitly approved by an administrator. They return a student's name, roll number, completed badge titles, and access-code redemption status. Students can search by name, roll number, or exact email; the email is used only for matching and is never displayed. The participant list has a filter for names and roll numbers. GEAR program details are shown only for students whose GEAR badge field indicates GEAR participation; profile URLs and raw access codes are never displayed. Incomplete profiles show learning links for the campaign syllabus, lab playlist, and the Step 1 credit-claim guide, alongside a WhatsApp help button. Completed profiles celebrate all 10 skill badges with a completion message and visual effects. Public pages rank students by badge progress and do not display XP or platform levels. Use HTTPS for any public deployment.

## Google Sheets synchronization rules

1. The app reads the full **Tracking Data** tab, detects supported headers, and matches records by email or Google Skills profile URL.
2. The latest tab is treated as an authoritative snapshot, so corrected badge counts can decrease. Progress and XP adjustments are applied only when the source data changes.
3. Roll numbers and public-profile approvals are read from **Roll Number Map** and are never overwritten by replacing the tracking export.
4. New profiles are hidden by default. Approve a profile through **Admin → Students**; the choice is saved to the map tab.
5. The app skips raw access codes. Keep the spreadsheet private because it contains participant email and profile data.

The CSV's completed-badge count is the source for overall progress. Named badge completion is shown only when the supplied “Skill Badges Completed Names” field identifies one of the ten badge titles; unnamed completions are not guessed.

## Deployment

Keep Streamlit Community Cloud and use a private Google spreadsheet as the durable source for student progress, roll numbers, and public-profile approvals. SQLite is only a local working cache for the app's calculations and admin history; student roster data is reloaded from Sheets and roll-number settings are written back to Sheets.

### Prepare the spreadsheet

1. Create a private Google spreadsheet with a **Tracking Data** tab. Paste the latest Google tracking export there, including its header row. The app detects supported column names automatically; the tab must contain a student name plus an email or Google Skills profile URL.
2. The app creates a **Roll Number Map** tab the first time it connects. Keep its header row and contents. Its columns are `User Email`, `Google Skills Profile URL`, `Roll Number`, and `Public Visible`. The map is kept separate so replacing the tracking export does not remove curated roll numbers or approvals.
3. For the initial migration, copy the email/profile URL and roll number pairs from your private curated snapshot into **Roll Number Map**. Once loaded, later tracking exports do not need roll numbers. Admin edits to roll numbers and profile approvals are saved to this tab.

### Connect Streamlit to Sheets

1. Create a Google service account, enable the Google Sheets API for its project, and share the spreadsheet with the service account's `client_email` as an **Editor**. The app needs write access to update **Roll Number Map**.
2. In Streamlit Community Cloud, open the app's **Settings → Secrets** and add the spreadsheet ID, tab names, and service-account fields. Keep these credentials private and out of GitHub:

```toml
SPREADSHEET_ID = "your-google-spreadsheet-id"
TRACKING_SHEET_TAB = "Tracking Data"
ROLL_NUMBER_MAP_TAB = "Roll Number Map"
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
4. When updating participant progress, replace the data rows in **Tracking Data** while preserving the header row. Do not clear or replace **Roll Number Map**.

The spreadsheet must remain private. Google Sheets version history provides recovery for edits; the app's ignored local SQLite file is not required for preserving the roster across deploys. The app's import/sync history and gamification settings remain local and may reset when Community Cloud replaces the app instance.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests cover initial imports, repeat-import idempotency, cumulative and authoritative updates, blank-field preservation, duplicate detection, public-profile privacy, and configurable mappings.
