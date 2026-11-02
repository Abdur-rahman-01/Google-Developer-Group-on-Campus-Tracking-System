# GDG MCET Cloud Learning Tracker

A single-page Streamlit portal for GDG on Campus at Methodist College of Engineering and Technology. The sidebar switches the main content between Home and Leaderboard. The Admin and About pages have been removed from the app; the CSV synchronization logic remains in `tracker.py`, but CSV uploads and student administration are not currently available through the UI.

The supplied Google Cloud logo image is stored in `assets/google-cloud-logo.png` and is used in the sidebar and the Home and Leaderboard banners.

## What this CSV contains

The supplied `GDGC-MCETH [01 Nov].csv` has 98 records and these columns:

- User Name, User Email
- Google Skills Profile URL and Status
- Google Developer Profile URL and Status
- Access Code and Access Code Redemption Status
- Milestone Completed, GEAR Digital Badges
- Skill Badges Completed Count and Skill Badges Completed Names

There is **no roll-number column**. The importer therefore matches existing students by email (or Google Skills profile URL). Admins can add each roll number after importing; that number is then searchable in the public portal. Column mapping is configurable and saved for future uploads. Raw access codes are deliberately skipped by default because they are redeemable secrets; the redemption-status field is imported.

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

Public search displays only approved profiles and returns a student's name, roll number, completed badge titles, and access-code redemption status. Students can search by name, roll number, or exact email; the email is used only for matching and is never displayed. The Home page also includes an incrementally loaded list of approved participants with their public badge progress and a filter for participant names or roll numbers. GEAR program details are shown only for students whose GEAR badge field indicates GEAR participation; profile URLs and raw access codes are never displayed. Incomplete profiles show learning links for the campaign syllabus, lab playlist, and the Step 1 credit-claim guide, alongside a WhatsApp help button. Completed profiles celebrate all 10 skill badges with a completion message and visual effects. Public pages rank students by badge progress and do not display XP or platform levels. Use HTTPS for any public deployment.

## CSV synchronization rules

1. The synchronization engine can preview a CSV, review or adjust detected column mappings, and analyze it before importing.
2. Duplicate email/profile identifiers and duplicate roll numbers in the file are flagged and skipped; rows without a student name and match identifier are also skipped.
3. Default **cumulative** mode is safe for regular updates: blank fields preserve existing values, badge counts never decrease, and badge names are merged.
4. An explicitly confirmed **authoritative snapshot** can correct a badge count downward. It records compensating XP ledger entries. Use this only when the sheet is a complete, verified snapshot.
5. Student changes, XP transactions, achievements, import history, and row errors are written in one SQLite transaction. Re-uploading the same file does not grant duplicate XP or achievements.
6. XP and levels remain internal tracker records and are not displayed on public pages; they are not official Google Cloud credentials.
7. Progress totals are snapshotted after successful imports for comparison over time.

The CSV's completed-badge count is the source for overall progress. Named badge completion is shown only when the supplied “Skill Badges Completed Names” field identifies one of the ten badge titles; unnamed completions are not guessed.

## Deployment

The app is a standard Streamlit application and can run on any host that supports Python and Streamlit. Configure:

- Build/install: `pip install -r requirements.txt`
- Start: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`
- Persistent database path: `GDG_DB_PATH`

**Use a host with a persistent disk** and set `GDG_DB_PATH` to a file on that mounted disk (for example `/var/data/gdg_tracker.db`). Do not rely on an ephemeral container filesystem for the database: student records and import history would be lost when the instance is replaced. For multiple app instances, use a shared managed database instead of SQLite. Put the app behind HTTPS. The current public app does not expose admin or CSV import controls.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests cover initial imports, repeat-import idempotency, cumulative and authoritative updates, blank-field preservation, duplicate detection, public-profile privacy, and configurable mappings.
