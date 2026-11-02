from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


LAB_CATALOG = (
    "Analyze Images with the Cloud Vision API",
    "Build a Website on Google Cloud",
    "Configure Service Accounts and IAM Roles for Google Cloud",
    "Create Your First Gemini Enterprise Application",
    "Develop AI-Powered Prototypes in Google AI Studio",
    "Explore Generative AI in Agent Platform",
    "Implement Speech and Language Solutions with Pre-trained APIs",
    "Store, Process, and Manage Data on Google Cloud - Console",
    "The Basics of Google Cloud Compute",
    "Using the Google Cloud Speech API",
)

CSV_TEMPLATE_HEADERS = (
    "User Name",
    "User Email",
    "Google Skills Profile URL",
    "Google Skills Profile Status",
    "Google Developer Profile URL",
    "Google Developer Profile Status",
    "Access Code",
    "Access Code Redemption Status",
    "Milestone Completed",
    "GEAR Digital Badges",
    "Skill Badges Completed Count",
    "Skill Badges Completed Names",
    "Roll Number",
)

FIELD_LABELS = {
    "name": "Student name",
    "email": "Student email (private)",
    "roll_number": "Roll number",
    "skills_profile_url": "Google Skills profile URL (private)",
    "skills_profile_status": "Google Skills profile status",
    "developer_profile_url": "Google Developer profile URL (private)",
    "developer_profile_status": "Google Developer profile status",
    "access_code": "Access code (sensitive; skip unless strictly needed)",
    "access_code_status": "Access code redemption status",
    "milestone": "Milestone completed",
    "gear_badges": "GEAR digital badges",
    "badges_count": "Skill badges completed count",
    "badges_names": "Skill badges completed names",
}

ALIASES = {
    "name": ("name", "user name", "student name", "full name"),
    "email": ("email", "user email", "student email", "email address"),
    "roll_number": ("roll no", "roll number", "rollno", "registration id", "student id"),
    "skills_profile_url": ("google skills profile url", "skills profile url"),
    "skills_profile_status": ("google skills profile status", "skills profile status"),
    "developer_profile_url": ("google developer profile url", "developer profile url"),
    "developer_profile_status": ("google developer profile status", "developer profile status"),
    "access_code": ("access code",),
    "access_code_status": ("access code redemption status", "access code status"),
    "milestone": ("milestone completed", "milestone"),
    "gear_badges": ("gear digital badges", "gear badges"),
    "badges_count": ("skill badges completed count", "badges completed count", "badges count"),
    "badges_names": ("skill badges completed names", "badges completed names", "badge names"),
}

DEFAULT_LEVELS = [
    {"name": "Cloud Beginner", "xp": 0},
    {"name": "Cloud Explorer", "xp": 200},
    {"name": "Cloud Practitioner", "xp": 500},
    {"name": "Cloud Enthusiast", "xp": 900},
    {"name": "Cloud Achiever", "xp": 1300},
    {"name": "Cloud Champion", "xp": 1700},
    {"name": "Cloud Master", "xp": 2100},
]

ACHIEVEMENTS = (
    ("first_step", "First Step", 1, "Complete your first skill badge."),
    ("halfway_hero", "Halfway Hero", 5, "Complete five skill badges."),
    ("cloud_explorer", "Cloud Explorer", 7, "Complete seven skill badges."),
    ("almost_there", "Almost There", 9, "Complete nine skill badges."),
    ("cloud_champion", "Cloud Champion", 10, "Complete all ten skill badges."),
    ("perfect_ten", "Perfect Ten", 10, "Reach the ten-badge milestone."),
)

LEADERBOARD_EXCLUDED_NAMES = frozenset({"abdur rahman qasim"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def default_mapping(columns: list[str]) -> dict[str, str]:
    normalized = {normalize_header(column): column for column in columns}
    mapping: dict[str, str] = {}
    for field, aliases in ALIASES.items():
        if field == "access_code":
            continue
        for alias in aliases:
            if normalize_header(alias) in normalized:
                mapping[field] = normalized[normalize_header(alias)]
                break
    return mapping


@contextmanager
def get_connection(db_path: str | Path | None = None):
    path = str(db_path or os.getenv("GDG_DB_PATH", "data/gdg_tracker.db"))
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: str | Path | None = None) -> None:
    with get_connection(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_number TEXT UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL,
                email TEXT UNIQUE COLLATE NOCASE,
                skills_profile_url TEXT,
                skills_profile_status TEXT,
                developer_profile_url TEXT,
                developer_profile_status TEXT,
                access_code TEXT,
                access_code_status TEXT,
                milestone TEXT,
                gear_badges TEXT,
                badges_count INTEGER NOT NULL DEFAULT 0 CHECK (badges_count BETWEEN 0 AND 10),
                badges_names TEXT NOT NULL DEFAULT '[]',
                public_visible INTEGER NOT NULL DEFAULT 0 CHECK (public_visible IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_students_name ON students(name COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_students_roll ON students(roll_number COLLATE NOCASE);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_students_skills_profile_url
                ON students(skills_profile_url) WHERE skills_profile_url IS NOT NULL;
            CREATE TABLE IF NOT EXISTS csv_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                uploaded_by TEXT NOT NULL DEFAULT 'Admin (shared login)',
                imported_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                total_records INTEGER NOT NULL DEFAULT 0,
                new_students INTEGER NOT NULL DEFAULT 0,
                updated_students INTEGER NOT NULL DEFAULT 0,
                unchanged_students INTEGER NOT NULL DEFAULT 0,
                failed_records INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS import_snapshots (
                import_id INTEGER PRIMARY KEY REFERENCES csv_imports(id) ON DELETE CASCADE,
                imported_at TEXT NOT NULL,
                total_students INTEGER NOT NULL,
                total_badges INTEGER NOT NULL,
                completed_students INTEGER NOT NULL,
                average_badges REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS csv_import_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_id INTEGER NOT NULL REFERENCES csv_imports(id) ON DELETE CASCADE,
                row_number INTEGER,
                message TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS xp_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_xp_student ON xp_transactions(student_id);
            CREATE TABLE IF NOT EXISTS student_achievements (
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                achievement_key TEXT NOT NULL,
                earned_at TEXT NOT NULL,
                PRIMARY KEY (student_id, achievement_key)
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        import_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(csv_imports)")
        }
        if "uploaded_by" not in import_columns:
            connection.execute(
                "ALTER TABLE csv_imports ADD COLUMN uploaded_by TEXT NOT NULL DEFAULT 'Admin (shared login)'"
            )
        connection.execute(
            "INSERT OR IGNORE INTO app_settings(key, value) VALUES ('levels', ?)",
            (json.dumps(DEFAULT_LEVELS),),
        )
        connection.execute(
            "INSERT OR IGNORE INTO app_settings(key, value) VALUES ('xp_per_badge', '100')"
        )
        connection.execute(
            "INSERT OR IGNORE INTO app_settings(key, value) VALUES ('bonus_5', '250')"
        )
        connection.execute(
            "INSERT OR IGNORE INTO app_settings(key, value) VALUES ('bonus_10', '500')"
        )


def parse_csv(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = content.decode("utf-8-sig")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("The uploaded file does not contain a header row.")
    headers = [str(header or "").strip() for header in reader.fieldnames]
    if not any(headers):
        raise ValueError("The uploaded CSV has an empty header row.")
    normalized_headers = [normalize_header(header) for header in headers]
    if len(set(normalized_headers)) != len(normalized_headers):
        raise ValueError("The uploaded CSV contains duplicate column names.")
    records = []
    for row in reader:
        record = {
            str(key or "").strip(): str(value or "").strip()
            for key, value in row.items()
            if key is not None
        }
        if None in row:
            record["_csv_error"] = "CSV row contains more values than the header defines."
        records.append(record)
    return headers, records


def _read_record(row: dict[str, str], mapping: dict[str, str]) -> dict[str, Any]:
    record = {
        field: (row.get(column, "").strip() if column else "")
        for field, column in mapping.items()
        if field in FIELD_LABELS
    }
    if record.get("badges_count"):
        try:
            number = Decimal(str(record["badges_count"]))
            if not number.is_finite() or number != number.to_integral_value():
                raise InvalidOperation
            count = int(number)
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Skill badges completed count must be a whole number.")
        if not 0 <= count <= 10:
            raise ValueError("Skill badges completed count must be between 0 and 10.")
        record["badges_count"] = count
    else:
        record["badges_count"] = None
    record["badges_names"] = badge_names_from_text(str(record.get("badges_names") or ""))
    if (
        record["badges_count"] is not None
        and record["badges_count"] < len(record["badges_names"])
    ):
        raise ValueError("Completed badge count is lower than the number of named completed badges.")
    if record["badges_count"] is None and record["badges_names"]:
        record["badges_count"] = len(record["badges_names"])
    return record


def badge_names_from_text(value: str) -> list[str]:
    lowered = value.casefold()
    return [badge for badge in LAB_CATALOG if badge.casefold() in lowered]


def _find_existing(
    connection: sqlite3.Connection, record: dict[str, Any]
) -> sqlite3.Row | None:
    email = str(record.get("email") or "").strip().casefold()
    profile_url = str(record.get("skills_profile_url") or "").strip()
    if email:
        existing = connection.execute(
            "SELECT * FROM students WHERE email = ? COLLATE NOCASE", (email,)
        ).fetchone()
        if existing:
            return existing
    if profile_url:
        existing = connection.execute(
            "SELECT * FROM students WHERE skills_profile_url = ?", (profile_url,)
        ).fetchone()
        if existing:
            return existing
    return None


def preview_import(
    content: bytes, mapping: dict[str, str], db_path: str | Path | None = None
) -> dict[str, Any]:
    headers, rows = parse_csv(content)
    mapped_columns = [column for column in mapping.values() if column]
    if len(set(mapped_columns)) != len(mapped_columns):
        raise ValueError("Each CSV column can be mapped to only one application field.")
    if "name" not in mapping:
        raise ValueError("Map a CSV column to Student name before importing.")
    if not ({"email", "skills_profile_url"} & mapping.keys()):
        raise ValueError("Map a CSV column to email or Google Skills profile URL to match students.")
    accepted: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        try:
            if row.get("_csv_error"):
                raise ValueError(row["_csv_error"])
            record = _read_record(row, mapping)
            if not record.get("name"):
                raise ValueError("Student name is required.")
            email = str(record.get("email") or "").strip().casefold()
            profile_url = str(record.get("skills_profile_url") or "").strip().casefold()
            if not email and not profile_url:
                raise ValueError("A student email or Google Skills profile URL is required.")
            identities = set()
            if email:
                identities.add(f"email:{email}")
            if profile_url:
                identities.add(f"profile:{profile_url}")
            if identities & seen_keys:
                raise ValueError("Duplicate student identifier in this CSV.")
            seen_keys.update(identities)
            record["_row_number"] = row_number
            accepted.append(record)
        except ValueError as error:
            errors.append({"row_number": row_number, "message": str(error)})

    with get_connection(db_path) as connection:
        seen_rolls: set[str] = set()
        unique_records = []
        for record in accepted:
            roll = str(record.get("roll_number") or "").strip().casefold()
            if roll and roll in seen_rolls:
                errors.append(
                    {"row_number": record["_row_number"], "message": "Duplicate roll number in this CSV."}
                )
                continue
            if roll:
                seen_rolls.add(roll)
            record["_existing"] = _find_existing(connection, record)
            existing = record["_existing"]
            matching_profile = None
            if record.get("skills_profile_url"):
                matching_profile = connection.execute(
                    "SELECT id FROM students WHERE skills_profile_url = ?",
                    (record["skills_profile_url"],),
                ).fetchone()
            if matching_profile and existing and matching_profile["id"] != existing["id"]:
                errors.append(
                    {
                        "row_number": record["_row_number"],
                        "message": "Email and Google Skills profile URL match different existing students.",
                    }
                )
                continue
            if matching_profile and not existing:
                existing = connection.execute(
                    "SELECT * FROM students WHERE id = ?", (matching_profile["id"],)
                ).fetchone()
                record["_existing"] = existing
            roll = str(record.get("roll_number") or "").strip()
            if roll:
                conflict = connection.execute(
                    "SELECT id FROM students WHERE roll_number = ? COLLATE NOCASE",
                    (roll,),
                ).fetchone()
                if conflict and (existing is None or conflict["id"] != existing["id"]):
                    errors.append(
                        {
                            "row_number": record["_row_number"],
                            "message": "Roll number is already assigned to another student.",
                        }
                    )
                    continue
            email = str(record.get("email") or "").strip()
            if email:
                conflict = connection.execute(
                    "SELECT id FROM students WHERE email = ? COLLATE NOCASE",
                    (email,),
                ).fetchone()
                if conflict and (existing is None or conflict["id"] != existing["id"]):
                    errors.append(
                        {
                            "row_number": record["_row_number"],
                            "message": "Email is already assigned to another student.",
                        }
                    )
                    continue
            unique_records.append(record)
        accepted = unique_records
        new_count = sum(record["_existing"] is None for record in accepted)
        updated_count = 0
        unchanged_count = 0
        for record in accepted:
            existing = record["_existing"]
            if existing is None:
                record["_changed_fields"] = []
                continue
            changed = False
            changed_fields = []
            for field in FIELD_LABELS:
                incoming = record.get(field)
                previous = existing[field] if field in existing.keys() else None
                if field == "badges_count":
                    incoming = incoming if incoming is not None else previous
                    if incoming is not None:
                        incoming = max(int(previous or 0), int(incoming))
                elif field == "badges_names":
                    previous_names = json.loads(existing["badges_names"] or "[]")
                    incoming = list(dict.fromkeys(previous_names + record["badges_names"]))
                    previous = previous_names
                elif not incoming:
                    incoming = previous
                if incoming != previous:
                    changed = True
                    changed_fields.append(field)
            if changed:
                updated_count += 1
            else:
                unchanged_count += 1
            record["_changed_fields"] = changed_fields
            record["_existing"] = True

    return {
        "headers": headers,
        "records": accepted,
        "errors": errors,
        "total": len(rows),
        "new_students": new_count,
        "updated_students": updated_count,
        "unchanged_students": unchanged_count,
    }


def _settings(connection: sqlite3.Connection) -> dict[str, str]:
    return {row["key"]: row["value"] for row in connection.execute("SELECT key, value FROM app_settings")}


def _add_xp(
    connection: sqlite3.Connection, student_id: int, amount: int, reason: str
) -> None:
    if amount:
        connection.execute(
            "INSERT INTO xp_transactions(student_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
            (student_id, amount, reason, utc_now()),
        )


def _award_achievements(
    connection: sqlite3.Connection, student_id: int, count: int
) -> None:
    for key, _title, threshold, _description in ACHIEVEMENTS:
        if count >= threshold:
            connection.execute(
                "INSERT OR IGNORE INTO student_achievements(student_id, achievement_key, earned_at) "
                "VALUES (?, ?, ?)",
                (student_id, key, utc_now()),
            )


def _apply_progress(
    connection: sqlite3.Connection,
    student_id: int,
    old_count: int,
    new_count: int,
    settings: dict[str, str],
) -> None:
    badge_xp = int(settings.get("xp_per_badge", "100"))
    if new_count > old_count:
        for badge_number in range(old_count + 1, new_count + 1):
            _add_xp(connection, student_id, badge_xp, f"Skill badge {badge_number} completed")
    elif new_count < old_count:
        for badge_number in range(old_count, new_count, -1):
            earned_amount = connection.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM xp_transactions "
                "WHERE student_id = ? AND reason LIKE ?",
                (student_id, f"%Skill badge {badge_number}%"),
            ).fetchone()[0]
            if earned_amount > 0:
                _add_xp(
                    connection,
                    student_id,
                    -earned_amount,
                    f"Correction: skill badge {badge_number} removed",
                )

    for threshold, setting_key in ((5, "bonus_5"), (10, "bonus_10")):
        if old_count < threshold <= new_count:
            reason_pattern = f"%{threshold}-badge milestone bonus%"
            history = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM xp_transactions "
                "WHERE student_id = ? AND reason LIKE ?",
                (student_id, reason_pattern),
            ).fetchone()
            if history[0] and history[1] <= 0:
                _add_xp(
                    connection,
                    student_id,
                    int(settings.get(setting_key, "0")),
                    f"Correction: {threshold}-badge milestone bonus restored",
                )
            elif not history[0]:
                _add_xp(
                    connection,
                    student_id,
                    int(settings.get(setting_key, "0")),
                    f"{threshold}-badge milestone bonus",
                )
        elif new_count < threshold <= old_count:
            reason_pattern = f"%{threshold}-badge milestone bonus%"
            current_bonus = connection.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM xp_transactions "
                "WHERE student_id = ? AND reason LIKE ?",
                (student_id, reason_pattern),
            ).fetchone()[0]
            if current_bonus > 0:
                _add_xp(
                    connection,
                    student_id,
                    -current_bonus,
                    f"Correction: {threshold}-badge milestone bonus removed",
                )
    _award_achievements(connection, student_id, new_count)


def import_records(
    records: list[dict[str, Any]],
    filename: str,
    errors: list[dict[str, Any]],
    authoritative: bool = False,
    approve_new_students: bool = False,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    counts = Counter()
    mode = "authoritative" if authoritative else "cumulative"
    with get_connection(db_path) as connection:
        try:
            connection.execute("BEGIN")
            cursor = connection.execute(
                "INSERT INTO csv_imports(filename, uploaded_by, imported_at, mode, status, total_records) "
                "VALUES (?, 'Admin (shared login)', ?, ?, 'processing', ?)",
                (Path(filename).name, utc_now(), mode, len(records) + len(errors)),
            )
            import_id = cursor.lastrowid
            for error in errors:
                connection.execute(
                    "INSERT INTO csv_import_errors(import_id, row_number, message) VALUES (?, ?, ?)",
                    (import_id, error.get("row_number"), error["message"]),
                )

            settings = _settings(connection)
            for record in records:
                incoming = {field: record.get(field) for field in FIELD_LABELS}
                existing = _find_existing(connection, incoming)
                if not existing:
                    now = utc_now()
                    names = list(record.get("badges_names") or [])
                    count = record.get("badges_count")
                    count = int(count if count is not None else len(names))
                    values = {
                        field: incoming.get(field) or None
                        for field in FIELD_LABELS
                        if field not in ("badges_count", "badges_names")
                    }
                    roll = values.pop("roll_number", None)
                    email = values.pop("email", None)
                    profile = values.pop("skills_profile_url", None)
                    connection.execute(
                        """
                        INSERT INTO students (
                            roll_number, name, email, skills_profile_url, skills_profile_status,
                            developer_profile_url, developer_profile_status, access_code,
                            access_code_status, milestone, gear_badges, badges_count, badges_names,
                            public_visible, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            roll,
                            values.get("name") or "Student",
                            email,
                            profile,
                            values.get("skills_profile_status"),
                            values.get("developer_profile_url"),
                            values.get("developer_profile_status"),
                            values.get("access_code"),
                            values.get("access_code_status"),
                            values.get("milestone"),
                            values.get("gear_badges"),
                            count,
                            json.dumps(names),
                            int(approve_new_students),
                            now,
                            now,
                        ),
                    )
                    student_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                    _apply_progress(connection, student_id, 0, count, settings)
                    counts["new_students"] += 1
                    continue

                old_count = int(existing["badges_count"])
                incoming_count = record.get("badges_count")
                if incoming_count is None:
                    incoming_count = old_count
                elif not authoritative:
                    incoming_count = max(old_count, int(incoming_count))
                incoming_names = list(record.get("badges_names") or [])
                old_names = json.loads(existing["badges_names"] or "[]")
                names = (
                    incoming_names
                    if authoritative and incoming_names
                    else list(dict.fromkeys(old_names + incoming_names))
                )
                assignments: dict[str, Any] = {}
                for field in FIELD_LABELS:
                    if field in ("badges_count", "badges_names"):
                        continue
                    value = incoming.get(field)
                    if value:
                        target = "roll_number" if field == "roll_number" else field
                        assignments[target] = value
                assignments["badges_count"] = max(0, min(10, int(incoming_count)))
                assignments["badges_names"] = json.dumps(names)
                changed = any(
                    str(existing[field] or "") != str(value or "")
                    for field, value in assignments.items()
                )
                if changed:
                    assignments["updated_at"] = utc_now()
                    columns = ", ".join(f"{column} = ?" for column in assignments)
                    connection.execute(
                        f"UPDATE students SET {columns} WHERE id = ?",
                        (*assignments.values(), existing["id"]),
                    )
                    counts["updated_students"] += 1
                else:
                    counts["unchanged_students"] += 1
                _apply_progress(connection, existing["id"], old_count, assignments["badges_count"], settings)

            connection.execute(
                "UPDATE csv_imports SET status = ?, new_students = ?, updated_students = ?, "
                "unchanged_students = ?, failed_records = ? WHERE id = ?",
                (
                    "completed_with_errors" if errors else "completed",
                    counts["new_students"],
                    counts["updated_students"],
                    counts["unchanged_students"],
                    len(errors),
                    import_id,
                ),
            )
            snapshot = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(badges_count), 0), "
                "COALESCE(SUM(CASE WHEN badges_count = 10 THEN 1 ELSE 0 END), 0), "
                "COALESCE(AVG(badges_count), 0) FROM students"
            ).fetchone()
            connection.execute(
                "INSERT INTO import_snapshots(import_id, imported_at, total_students, total_badges, "
                "completed_students, average_badges) VALUES (?, ?, ?, ?, ?, ?)",
                (import_id, utc_now(), snapshot[0], snapshot[1], snapshot[2], snapshot[3]),
            )
            connection.commit()
        except Exception as error:
            connection.rollback()
            cursor = connection.execute(
                "INSERT INTO csv_imports(filename, uploaded_by, imported_at, mode, status, "
                "total_records, failed_records) VALUES (?, 'Admin (shared login)', ?, ?, 'failed', ?, ?)",
                (Path(filename).name, utc_now(), mode, len(records) + len(errors), len(records) + len(errors)),
            )
            import_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO csv_import_errors(import_id, message) VALUES (?, ?)",
                (import_id, f"Transaction rolled back: {error}"),
            )
            connection.commit()
            raise
    return {
        "import_id": import_id,
        "new_students": counts["new_students"],
        "updated_students": counts["updated_students"],
        "unchanged_students": counts["unchanged_students"],
        "failed_records": len(errors),
    }


def search_public_students(query: str, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    term = query.strip()
    if not term:
        return []
    pattern = f"%{term}%"
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, roll_number, name, badges_count
            FROM students
            WHERE public_visible = 1 AND (
                name LIKE ? COLLATE NOCASE
                OR roll_number LIKE ? COLLATE NOCASE
                OR email = ? COLLATE NOCASE
            )
            ORDER BY name COLLATE NOCASE
            LIMIT 30
            """,
            (pattern, pattern, term),
        ).fetchall()
    return [dict(row) for row in rows]


def is_gear_participant(gear_badges: str | None) -> bool:
    value = (gear_badges or "").strip().casefold()
    return bool(value and value not in {"not applicable", "n/a", "na"})


def get_student_profile(student_id: int, public_only: bool = True, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with get_connection(db_path) as connection:
        visibility_filter = "AND public_visible = 1" if public_only else ""
        row = connection.execute(
            f"""
            SELECT id, roll_number, name, badges_count, badges_names, updated_at, public_visible,
                   milestone, gear_badges, skills_profile_status, developer_profile_status,
                   access_code_status
            FROM students WHERE id = ? {visibility_filter}
            """,
            (student_id,),
        ).fetchone()
        if not row:
            return None
        student = dict(row)
        if public_only:
            is_gear = is_gear_participant(student.get("gear_badges"))
            profile = {
                "id": student["id"],
                "roll_number": student["roll_number"],
                "name": student["name"],
                "badges_count": student["badges_count"],
                "badges_names": json.loads(student["badges_names"] or "[]"),
                "access_code_status": student["access_code_status"],
                "is_gear_participant": is_gear,
            }
            if is_gear:
                profile.update(
                    {
                        field: student[field]
                        for field in (
                            "milestone",
                            "gear_badges",
                            "skills_profile_status",
                            "developer_profile_status",
                        )
                    }
                )
            return profile
        student["badges_names"] = json.loads(student["badges_names"] or "[]")
        student["xp"] = int(connection.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_transactions WHERE student_id = ?",
            (student_id,),
        ).fetchone()[0])
        student["achievements"] = [
            {"title": title, "description": description}
            for key, title, threshold, description in ACHIEVEMENTS
            if student["badges_count"] >= threshold
        ]
        return student


def get_dashboard_data(db_path: str | Path | None = None) -> dict[str, Any]:
    with get_connection(db_path) as connection:
        total, started, completed, badge_total, average, latest = connection.execute(
            """
            SELECT COUNT(*),
                COALESCE(SUM(CASE WHEN badges_count > 0 THEN 1 ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN badges_count = 10 THEN 1 ELSE 0 END), 0),
                COALESCE(SUM(badges_count), 0),
                COALESCE(AVG(badges_count), 0),
                MAX(updated_at)
            FROM students
            """
        ).fetchone()
        return {
            "students": total,
            "started": started,
            "not_started": total - started,
            "completed": completed,
            "badges": badge_total,
            "average": round(average or 0, 1),
            "completion_rate": round(completed / total * 100, 1) if total else 0,
            "last_updated": latest,
            "recently_added": connection.execute(
                "SELECT COUNT(*) FROM students WHERE created_at >= ?",
                ((datetime.now(timezone.utc) - timedelta(days=14)).isoformat(timespec="seconds"),),
            ).fetchone()[0],
        }


def get_leaderboard(
    limit: int | None = None,
    db_path: str | Path | None = None,
    sort_by: str = "progress",
) -> list[dict[str, Any]]:
    excluded_names = sorted(LEADERBOARD_EXCLUDED_NAMES)
    order = (
        "xp DESC, s.badges_count DESC, s.name COLLATE NOCASE ASC, s.id ASC"
        if sort_by == "xp"
        else "s.badges_count DESC, xp DESC, s.name COLLATE NOCASE ASC, s.id ASC"
    )
    sql = f"""
        SELECT s.id, s.name, s.roll_number, s.badges_count, s.badges_names,
               COALESCE(SUM(x.amount), 0) AS xp
        FROM students s
        LEFT JOIN xp_transactions x ON x.student_id = s.id
        WHERE s.public_visible = 1
          AND lower(trim(s.name)) NOT IN ({",".join("?" for _ in excluded_names)})
        GROUP BY s.id
    """
    sql += f" ORDER BY {order}"
    if limit is not None:
        sql += " LIMIT ?"
    parameters: tuple[Any, ...] = tuple(name.casefold() for name in excluded_names)
    if limit is not None:
        parameters += (limit,)
    with get_connection(db_path) as connection:
        rows = connection.execute(sql, parameters).fetchall()
    return [dict(row) for row in rows]


def get_public_participants(
    limit: int,
    offset: int = 0,
    search: str = "",
    db_path: str | Path | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    if limit < 1:
        raise ValueError("Participant page size must be positive.")
    if offset < 0:
        raise ValueError("Participant offset cannot be negative.")
    term = search.strip()
    pattern = f"%{term}%"
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, name, roll_number, badges_count
            FROM students
            WHERE public_visible = 1
              AND (? = '' OR name LIKE ? COLLATE NOCASE OR roll_number LIKE ? COLLATE NOCASE)
            ORDER BY name COLLATE NOCASE, id
            LIMIT ? OFFSET ?
            """,
            (term, pattern, pattern, limit + 1, offset),
        ).fetchall()
    has_more = len(rows) > limit
    return [dict(row) for row in rows[:limit]], has_more


def get_admin_students(
    search: str = "",
    db_path: str | Path | None = None,
    limit: int | None = None,
    offset: int = 0,
    completion_filter: str = "All",
) -> list[dict[str, Any]]:
    pattern = f"%{search.strip()}%"
    progress_conditions = {
        "All": "1 = 1",
        "Not started": "s.badges_count = 0",
        "In progress": "s.badges_count BETWEEN 1 AND 9",
        "1–2 remaining": "s.badges_count IN (8, 9)",
        "Completed all 10": "s.badges_count = 10",
    }
    progress_filter = progress_conditions.get(completion_filter, progress_conditions["All"])
    sql = """
        SELECT s.*, COALESCE(SUM(x.amount), 0) AS xp
        FROM students s LEFT JOIN xp_transactions x ON x.student_id = s.id
        WHERE (? = '%%' OR s.name LIKE ? COLLATE NOCASE OR s.email LIKE ? COLLATE NOCASE
               OR s.roll_number LIKE ? COLLATE NOCASE) AND {progress_filter}
        GROUP BY s.id ORDER BY s.name COLLATE NOCASE
    """
    sql = sql.format(progress_filter=progress_filter)
    params: tuple[Any, ...] = (pattern, pattern, pattern, pattern)
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += (limit, offset)
    with get_connection(db_path) as connection:
        rows = connection.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def count_admin_students(
    search: str = "", db_path: str | Path | None = None, completion_filter: str = "All"
) -> int:
    pattern = f"%{search.strip()}%"
    progress_conditions = {
        "All": "1 = 1",
        "Not started": "badges_count = 0",
        "In progress": "badges_count BETWEEN 1 AND 9",
        "1–2 remaining": "badges_count IN (8, 9)",
        "Completed all 10": "badges_count = 10",
    }
    progress_filter = progress_conditions.get(completion_filter, progress_conditions["All"])
    with get_connection(db_path) as connection:
        return connection.execute(
            f"""
            SELECT COUNT(*) FROM students
            WHERE (? = '%%' OR name LIKE ? COLLATE NOCASE OR email LIKE ? COLLATE NOCASE
                   OR roll_number LIKE ? COLLATE NOCASE) AND {progress_filter}
            """,
            (pattern, pattern, pattern, pattern),
        ).fetchone()[0]


def update_student_settings(
    student_id: int,
    roll_number: str | None,
    public_visible: bool,
    db_path: str | Path | None = None,
) -> None:
    roll = (roll_number or "").strip() or None
    with get_connection(db_path) as connection:
        connection.execute(
            "UPDATE students SET roll_number = ?, public_visible = ?, updated_at = ? WHERE id = ?",
            (roll, int(public_visible), utc_now(), student_id),
        )


def get_import_history(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        imports = connection.execute("SELECT * FROM csv_imports ORDER BY imported_at DESC LIMIT 50").fetchall()
        result = []
        for item in imports:
            row = dict(item)
            snapshot = connection.execute(
                "SELECT total_students, total_badges, completed_students, average_badges "
                "FROM import_snapshots WHERE import_id = ?",
                (row["id"],),
            ).fetchone()
            row["snapshot"] = dict(snapshot) if snapshot else None
            row["errors"] = [
                dict(error)
                for error in connection.execute(
                    "SELECT row_number, message FROM csv_import_errors WHERE import_id = ? ORDER BY id",
                    (row["id"],),
                )
            ]
            result.append(row)
    return result


def get_all_students(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    return get_admin_students(db_path=db_path)


def get_xp_transactions(
    student_id: int,
    db_path: str | Path | None = None,
    limit: int = 250,
) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT amount, reason, created_at
            FROM xp_transactions
            WHERE student_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (student_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def export_students(students: list[dict[str, Any]]) -> str:
    fields = [
        "name",
        "roll_number",
        "email",
        "badges_count",
        "remaining_badges",
        "completion_percent",
        "xp",
        "updated_at",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for student in students:
        row = {
                **student,
                "remaining_badges": 10 - int(student["badges_count"]),
                "completion_percent": int(student["badges_count"]) * 10,
            }
        writer.writerow({field: spreadsheet_safe(row.get(field, "")) for field in fields})
    return output.getvalue()


def export_import_snapshot(db_path: str | Path | None = None) -> str:
    fields = (
        "User Name",
        "User Email",
        "Google Skills Profile URL",
        "Google Skills Profile Status",
        "Google Developer Profile URL",
        "Google Developer Profile Status",
        "Access Code Redemption Status",
        "Milestone Completed",
        "GEAR Digital Badges",
        "Skill Badges Completed Count",
        "Skill Badges Completed Names",
        "Roll Number",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for student in get_admin_students(db_path=db_path):
        names = json.loads(student.get("badges_names") or "[]")
        writer.writerow(
            {
                "User Name": spreadsheet_safe(student.get("name") or ""),
                "User Email": spreadsheet_safe(student.get("email") or ""),
                "Google Skills Profile URL": spreadsheet_safe(
                    student.get("skills_profile_url") or ""
                ),
                "Google Skills Profile Status": spreadsheet_safe(
                    student.get("skills_profile_status") or ""
                ),
                "Google Developer Profile URL": spreadsheet_safe(
                    student.get("developer_profile_url") or ""
                ),
                "Google Developer Profile Status": spreadsheet_safe(
                    student.get("developer_profile_status") or ""
                ),
                "Access Code Redemption Status": spreadsheet_safe(
                    student.get("access_code_status") or ""
                ),
                "Milestone Completed": spreadsheet_safe(student.get("milestone") or ""),
                "GEAR Digital Badges": spreadsheet_safe(student.get("gear_badges") or ""),
                "Skill Badges Completed Count": int(student["badges_count"]),
                "Skill Badges Completed Names": spreadsheet_safe(", ".join(names)),
                "Roll Number": spreadsheet_safe(student.get("roll_number") or ""),
            }
        )
    return output.getvalue()


def spreadsheet_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def csv_template() -> str:
    output = io.StringIO(newline="")
    csv.writer(output).writerow(CSV_TEMPLATE_HEADERS)
    return output.getvalue()


def save_mapping(mapping: dict[str, str], db_path: str | Path | None = None) -> None:
    with get_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO app_settings(key, value) VALUES ('column_mapping', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (json.dumps(mapping),),
        )


def load_mapping(db_path: str | Path | None = None) -> dict[str, str]:
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'column_mapping'"
        ).fetchone()
    return json.loads(row["value"]) if row else {}


def get_level(xp: int, levels: list[dict[str, Any]] | None = None) -> str:
    return get_level_progress(xp, levels)["current_level"]


def get_level_progress(
    xp: int, levels: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    active_levels = sorted(
        levels or DEFAULT_LEVELS, key=lambda level: int(level["xp"])
    )
    if not active_levels:
        raise ValueError("At least one level is required.")
    if int(active_levels[0]["xp"]) != 0:
        raise ValueError("The first level must start at 0 XP.")
    if any(
        int(current["xp"]) == int(previous["xp"])
        for previous, current in zip(active_levels, active_levels[1:])
    ):
        raise ValueError("Each level must have a unique XP threshold.")
    current_index = max(
        index
        for index, level in enumerate(active_levels)
        if xp >= int(level["xp"])
    ) if xp >= 0 else 0
    current = active_levels[current_index]
    if current_index == len(active_levels) - 1:
        return {
            "current_level": current["name"],
            "current_xp": xp,
            "current_threshold": int(current["xp"]),
            "next_level": None,
            "next_threshold": None,
            "xp_to_next": 0,
            "progress": 1.0,
        }
    next_level = active_levels[current_index + 1]
    current_threshold = int(current["xp"])
    next_threshold = int(next_level["xp"])
    span = next_threshold - current_threshold
    progress = min(1.0, max(0.0, (xp - current_threshold) / span))
    return {
        "current_level": current["name"],
        "current_xp": xp,
        "current_threshold": current_threshold,
        "next_level": next_level["name"],
        "next_threshold": next_threshold,
        "xp_to_next": max(0, next_threshold - xp),
        "progress": progress,
    }


def update_level_settings(levels: list[dict[str, Any]], db_path: str | Path | None = None) -> None:
    ordered = sorted(
        ({"name": str(level["name"]).strip(), "xp": int(level["xp"])} for level in levels),
        key=lambda level: level["xp"],
    )
    if not ordered or ordered[0]["xp"] != 0:
        raise ValueError("The first level must start at 0 XP.")
    if any(not level["name"] for level in ordered):
        raise ValueError("Level names cannot be blank.")
    if any(a["xp"] == b["xp"] for a, b in zip(ordered, ordered[1:])):
        raise ValueError("Each level must have a unique XP threshold.")
    with get_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO app_settings(key, value) VALUES ('levels', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (json.dumps(ordered),),
        )


def get_level_settings(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        row = connection.execute("SELECT value FROM app_settings WHERE key = 'levels'").fetchone()
    return json.loads(row["value"]) if row else DEFAULT_LEVELS


def get_gamification_settings(db_path: str | Path | None = None) -> dict[str, int]:
    with get_connection(db_path) as connection:
        settings = _settings(connection)
    return {
        "xp_per_badge": int(settings.get("xp_per_badge", "100")),
        "bonus_5": int(settings.get("bonus_5", "250")),
        "bonus_10": int(settings.get("bonus_10", "500")),
    }


def update_gamification_settings(
    xp_per_badge: int,
    bonus_5: int,
    bonus_10: int,
    db_path: str | Path | None = None,
) -> None:
    values = {
        "xp_per_badge": int(xp_per_badge),
        "bonus_5": int(bonus_5),
        "bonus_10": int(bonus_10),
    }
    if any(value < 0 for value in values.values()):
        raise ValueError("XP values cannot be negative.")
    with get_connection(db_path) as connection:
        connection.executemany(
            "INSERT INTO app_settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(key, str(value)) for key, value in values.items()],
        )


def get_import_errors(import_id: int, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT row_number, message FROM csv_import_errors WHERE import_id = ? ORDER BY id",
                (import_id,),
            )
        ]
