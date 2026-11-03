import csv
import io
import tempfile
import unittest
from pathlib import Path

import tracker


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "tracker.db"
        tracker.initialize_database(self.db_path)
        self.mapping = {
            "name": "User Name",
            "email": "User Email",
            "skills_profile_url": "Google Skills Profile URL",
            "developer_profile_url": "Google Developer Profile URL",
            "badges_count": "Skill Badges Completed Count",
            "badges_names": "Skill Badges Completed Names",
            "access_code": "Access Code",
            "roll_number": "Roll Number",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_csv(self, rows, headers=None):
        headers = headers or list(rows[0].keys())
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode("utf-8")

    def preview(self, content):
        return tracker.preview_import(content, self.mapping, self.db_path)

    def import_csv(self, content, authoritative=False):
        preview = self.preview(content)
        result = tracker.import_records(
            preview["records"],
            "tracking.csv",
            preview["errors"],
            authoritative=authoritative,
            db_path=self.db_path,
        )
        return preview, result

    def import_public_profile(self, row):
        content = self.make_csv([row])
        headers, _ = tracker.parse_csv(content)
        preview = tracker.preview_import(
            content,
            tracker.default_mapping(headers),
            self.db_path,
        )
        tracker.import_records(
            preview["records"],
            "tracking.csv",
            preview["errors"],
            db_path=self.db_path,
        )
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        tracker.update_student_settings(student["id"], "MCET-001", True, self.db_path)
        result = tracker.get_student_profile(student["id"], db_path=self.db_path)
        return tracker.search_public_students("MCET-001", self.db_path)[0], result

    def row(self, **values):
        row = {
            "User Name": "Test Student",
            "User Email": "student@example.edu",
            "Google Skills Profile URL": "https://skills.example/student-1",
            "Google Developer Profile URL": "https://developers.example/student-1",
            "Skill Badges Completed Count": "0",
            "Skill Badges Completed Names": "",
            "Access Code": "PRIVATE-CODE",
            "Roll Number": "",
        }
        row.update(values)
        return row

    def test_initial_import_calculates_xp_and_profile_is_private_by_default(self):
        row = self.row(
            **{
                "Skill Badges Completed Count": "5",
                "Skill Badges Completed Names": tracker.LAB_CATALOG[0],
            }
        )
        preview, result = self.import_csv(self.make_csv([row]))
        self.assertEqual(preview["new_students"], 1)
        self.assertEqual(result["new_students"], 1)
        self.assertEqual(tracker.get_dashboard_data(self.db_path)["students"], 1)
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        self.assertEqual(student["xp"], 750)
        self.assertIsNone(tracker.get_student_profile(student["id"], db_path=self.db_path))

    def test_reimport_is_idempotent_and_does_not_duplicate_xp(self):
        row = self.row(
            **{
                "Skill Badges Completed Count": "10",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG),
            }
        )
        content = self.make_csv([row])
        self.import_csv(content)
        preview, result = self.import_csv(content)
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        self.assertEqual(preview["unchanged_students"], 1)
        self.assertEqual(result["unchanged_students"], 1)
        self.assertEqual(student["xp"], 1750)
        with tracker.get_connection(self.db_path) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM student_achievements WHERE student_id = ?",
                    (student["id"],),
                ).fetchone()[0],
                6,
            )

    def test_cumulative_import_preserves_progress_and_blank_values(self):
        initial = self.row(
            **{
                "Skill Badges Completed Count": "5",
                "Skill Badges Completed Names": tracker.LAB_CATALOG[0],
            }
        )
        self.import_csv(self.make_csv([initial]))
        update = self.row(
            **{
                "User Name": "Updated Name",
                "Skill Badges Completed Count": "2",
                "Skill Badges Completed Names": "",
                "Access Code": "",
            }
        )
        self.import_csv(self.make_csv([update]))
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        self.assertEqual(student["name"], "Updated Name")
        self.assertEqual(student["badges_count"], 5)
        with tracker.get_connection(self.db_path) as connection:
            stored = connection.execute(
                "SELECT access_code FROM students WHERE id = ?", (student["id"],)
            ).fetchone()[0]
        self.assertEqual(stored, "PRIVATE-CODE")
        self.assertEqual(student["xp"], 750)

    def test_authoritative_import_can_correct_progress_and_compensates_xp(self):
        full = self.row(
            **{
                "Skill Badges Completed Count": "5",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:5]),
            }
        )
        self.import_csv(self.make_csv([full]))
        corrected = self.row(
            **{
                "Skill Badges Completed Count": "2",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:2]),
            }
        )
        self.import_csv(self.make_csv([corrected]), authoritative=True)
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        self.assertEqual(student["badges_count"], 2)
        self.assertEqual(student["xp"], 200)

    def test_duplicate_email_rows_are_reported_and_skipped(self):
        content = self.make_csv([self.row(), self.row(**{"User Name": "Second Row"})])
        preview = self.preview(content)
        self.assertEqual(len(preview["records"]), 1)
        self.assertEqual(len(preview["errors"]), 1)
        self.assertIn("Duplicate student identifier", preview["errors"][0]["message"])

    def test_search_requires_public_approval_and_never_returns_private_fields(self):
        self.import_csv(self.make_csv([self.row()]))
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        self.assertEqual(tracker.search_public_students("Test", self.db_path), [])
        tracker.update_student_settings(student["id"], "160726748099", True, self.db_path)
        found = tracker.search_public_students("160726748099", self.db_path)
        found_by_partial_roll_number = tracker.search_public_students("6748", self.db_path)
        found_by_name = tracker.search_public_students("Test Student", self.db_path)
        found_by_email = tracker.search_public_students("STUDENT@example.edu", self.db_path)
        found_by_partial_email = tracker.search_public_students("student@example", self.db_path)
        self.assertEqual(len(found), 1)
        self.assertEqual(len(found_by_partial_roll_number), 1)
        self.assertEqual(found_by_partial_roll_number[0]["id"], student["id"])
        self.assertEqual(len(found_by_name), 1)
        self.assertEqual(len(found_by_email), 1)
        self.assertEqual(found_by_email[0]["id"], student["id"])
        self.assertEqual(found_by_partial_email, [])
        self.assertNotIn("email", found[0])
        self.assertNotIn("access_code", found[0])
        profile = tracker.get_student_profile(student["id"], db_path=self.db_path)
        self.assertNotIn("email", profile)
        self.assertNotIn("access_code", profile)
        self.assertEqual(profile["skills_profile_url"], "https://skills.example/student-1")
        self.assertEqual(
            profile["developer_profile_url"],
            "https://developers.example/student-1",
        )

    def test_public_participants_are_paginated_and_hide_private_fields(self):
        rows = [
            self.row(
                **{
                    "User Name": f"Student {index}",
                    "User Email": f"student{index}@example.edu",
                    "Google Skills Profile URL": f"https://skills.example/student-{index}",
                }
            )
            for index in range(3)
        ]
        self.import_csv(self.make_csv(rows))
        students = tracker.get_admin_students(db_path=self.db_path)
        for student in students:
            tracker.update_student_settings(
                student["id"],
                student["roll_number"],
                True,
                self.db_path,
            )
        first_page, has_more = tracker.get_public_participants(
            limit=2,
            db_path=self.db_path,
        )
        matching_page, matching_has_more = tracker.get_public_participants(
            limit=2,
            search="Student 1",
            db_path=self.db_path,
        )
        second_page, has_more_after = tracker.get_public_participants(
            limit=2,
            offset=2,
            db_path=self.db_path,
        )
        self.assertEqual(len(first_page), 2)
        self.assertTrue(has_more)
        self.assertEqual(len(second_page), 1)
        self.assertFalse(has_more_after)
        self.assertEqual([student["name"] for student in matching_page], ["Student 1"])
        self.assertFalse(matching_has_more)
        self.assertNotIn("email", first_page[0])
        self.assertNotIn("access_code", first_page[0])
        self.assertEqual(
            first_page[0]["skills_profile_url"],
            "https://skills.example/student-0",
        )

    def test_curated_import_snapshot_preserves_rolls_and_never_exports_access_codes(self):
        row = self.row(
            **{
                "Access Code": "DO-NOT-EXPORT",
                "Skill Badges Completed Count": "2",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:2]),
            }
        )
        self.import_public_profile(row)
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        tracker.update_student_settings(
            student["id"],
            "MCET-001",
            True,
            self.db_path,
        )
        snapshot = tracker.export_import_snapshot(self.db_path)
        self.assertIn("MCET-001", snapshot)
        self.assertIn("student@example.edu", snapshot)
        self.assertIn(tracker.LAB_CATALOG[0], snapshot)
        self.assertNotIn("DO-NOT-EXPORT", snapshot)
        self.assertNotIn("Access Code,", snapshot)

    def test_import_can_approve_new_students_only_when_explicitly_requested(self):
        content = self.make_csv([self.row()])
        preview = self.preview(content)
        tracker.import_records(
            preview["records"],
            "curated-snapshot.csv",
            preview["errors"],
            approve_new_students=True,
            db_path=self.db_path,
        )
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        self.assertTrue(student["public_visible"])

    def test_public_search_shows_selected_details_for_all_participants(self):
        search_result, profile = self.import_public_profile(
            self.row(
                **{
                    "Skill Badges Completed Count": "2",
                    "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:2]),
                    "GEAR Digital Badges": "Not applicable",
                    "Milestone Completed": "No Milestone",
                    "Google Skills Profile Status": "Complete",
                    "Google Developer Profile Status": "Complete",
                    "Google Skills Profile URL": "https://skills.google/profile/student",
                    "Google Developer Profile URL": "https://developers.google.com/profile/student",
                    "Access Code Redemption Status": "Redeemed",
                }
            )
        )
        self.assertEqual(
            set(search_result),
            {"id", "roll_number", "name", "badges_count"},
        )
        self.assertEqual(
            set(profile),
            {
                "id",
                "roll_number",
                "name",
                "badges_count",
                "badges_names",
                "skills_profile_url",
                "developer_profile_url",
                "access_code_status",
                "milestone",
                "gear_badges",
                "skills_profile_status",
                "developer_profile_status",
                "is_gear_participant",
            },
        )
        self.assertFalse(profile["is_gear_participant"])
        self.assertEqual(profile["badges_names"], list(tracker.LAB_CATALOG[:2]))
        self.assertEqual(
            profile["skills_profile_url"],
            "https://skills.google/profile/student",
        )
        self.assertEqual(
            profile["developer_profile_url"],
            "https://developers.google.com/profile/student",
        )
        self.assertEqual(profile["access_code_status"], "Redeemed")
        self.assertEqual(profile["milestone"], "No Milestone")
        self.assertEqual(profile["gear_badges"], "Not applicable")
        self.assertEqual(profile["skills_profile_status"], "Complete")
        self.assertEqual(profile["developer_profile_status"], "Complete")
        self.assertNotIn("access_code", profile)

    def test_public_gear_profile_includes_program_status_but_not_xp(self):
        _, profile = self.import_public_profile(
            self.row(
                **{
                    "GEAR Digital Badges": "No Badge",
                    "Milestone Completed": "No Milestone",
                    "Google Skills Profile Status": "Complete",
                    "Google Developer Profile Status": "Complete",
                    "Access Code Redemption Status": "Redeemed",
                }
            )
        )
        self.assertTrue(profile["is_gear_participant"])
        self.assertEqual(profile["gear_badges"], "No Badge")
        self.assertEqual(profile["developer_profile_status"], "Complete")
        self.assertEqual(profile["access_code_status"], "Redeemed")
        self.assertEqual(profile["badges_names"], [])
        self.assertNotIn("xp", profile)
        self.assertNotIn("access_code", profile)

    def test_duplicate_rows_and_invalid_counts_are_skipped(self):
        invalid = self.row(**{"Skill Badges Completed Count": "11"})
        preview = self.preview(self.make_csv([self.row(), invalid]))
        self.assertEqual(len(preview["records"]), 1)
        self.assertEqual(len(preview["errors"]), 1)
        self.assertIn("between 0 and 10", preview["errors"][0]["message"])

    def test_duplicate_roll_numbers_are_reported_before_import(self):
        first = self.row(**{"Roll Number": "MCET-001"})
        second = self.row(
            **{
                "User Name": "Another Student",
                "User Email": "another@example.edu",
                "Google Skills Profile URL": "https://skills.example/another",
                "Roll Number": "mcet-001",
            }
        )
        preview = self.preview(self.make_csv([first, second]))
        self.assertEqual(len(preview["records"]), 1)
        self.assertTrue(any("Duplicate roll number" in error["message"] for error in preview["errors"]))

    def test_missing_optional_columns_are_supported(self):
        content = self.make_csv(
            [
                {
                    "Full Name": "Mapped Student",
                    "Email Address": "mapped@example.edu",
                    "Badges Completed Count": "2",
                }
            ]
        )
        headers, _ = tracker.parse_csv(content)
        mapping = tracker.default_mapping(headers)
        preview = tracker.preview_import(content, mapping, self.db_path)
        self.assertEqual(preview["new_students"], 1)
        tracker.import_records(preview["records"], "partial.csv", [], db_path=self.db_path)
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        self.assertEqual(student["badges_count"], 2)
        self.assertIsNone(student["skills_profile_url"])

    def test_saved_mapping_and_level_threshold_validation(self):
        tracker.save_mapping(self.mapping, self.db_path)
        self.assertEqual(tracker.load_mapping(self.db_path), self.mapping)
        with self.assertRaises(ValueError):
            tracker.update_level_settings(
                [{"name": "Level 1", "xp": 50}], self.db_path
            )

    def test_level_progress_reports_xp_to_next_level_and_caps_at_maximum(self):
        middle = tracker.get_level_progress(300)
        self.assertEqual(middle["current_level"], "Cloud Explorer")
        self.assertEqual(middle["next_level"], "Cloud Practitioner")
        self.assertEqual(middle["xp_to_next"], 200)
        self.assertAlmostEqual(middle["progress"], 1 / 3)

        maximum = tracker.get_level_progress(2500)
        self.assertEqual(maximum["current_level"], "Cloud Master")
        self.assertIsNone(maximum["next_level"])
        self.assertEqual(maximum["xp_to_next"], 0)
        self.assertEqual(maximum["progress"], 1.0)

    def test_supplied_tracking_sheet_maps_all_records_and_badge_titles(self):
        source = Path(__file__).parent.parent / "GDGC-MCETH [01 Nov].csv"
        headers, rows = tracker.parse_csv(source.read_bytes())
        self.assertEqual(len(headers), 13)
        self.assertEqual(len(rows), 98)
        mapping = tracker.default_mapping(headers)
        self.assertEqual(mapping["name"], "User Name")
        self.assertEqual(mapping["email"], "User Email")
        self.assertEqual(mapping["roll_number"], "Roll Number")
        preview = tracker.preview_import(source.read_bytes(), mapping, self.db_path)
        self.assertEqual(preview["total"], 98)
        self.assertEqual(preview["new_students"], 98)
        self.assertEqual(preview["errors"], [])
        self.assertNotIn("access_code", mapping)
        self.assertEqual(
            {name for record in preview["records"] for name in record["badges_names"]},
            set(tracker.LAB_CATALOG),
        )

    def test_authoritative_correction_and_recompletion_do_not_duplicate_milestone_bonus(self):
        full = self.row(
            **{
                "Skill Badges Completed Count": "5",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:5]),
            }
        )
        self.import_csv(self.make_csv([full]))
        lower = self.row(
            **{
                "Skill Badges Completed Count": "2",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:2]),
            }
        )
        self.import_csv(self.make_csv([lower]), authoritative=True)
        self.import_csv(self.make_csv([full]), authoritative=True)
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        self.assertEqual(student["xp"], 750)

    def test_authoritative_correction_reverses_the_xp_amount_originally_awarded(self):
        full = self.row(
            **{
                "Skill Badges Completed Count": "5",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:5]),
            }
        )
        self.import_csv(self.make_csv([full]))
        tracker.update_gamification_settings(200, 500, 1000, self.db_path)
        lower = self.row(
            **{
                "Skill Badges Completed Count": "2",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:2]),
            }
        )
        self.import_csv(self.make_csv([lower]), authoritative=True)
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        self.assertEqual(student["xp"], 200)

    def test_import_history_keeps_a_progress_snapshot(self):
        self.import_csv(self.make_csv([self.row()]))
        history = tracker.get_import_history(self.db_path)
        self.assertEqual(history[0]["uploaded_by"], "Admin (shared login)")
        self.assertEqual(history[0]["snapshot"]["total_students"], 1)

    def test_xp_transaction_audit_returns_entries_for_selected_student(self):
        completed = self.row(
            **{
                "Skill Badges Completed Count": "1",
                "Skill Badges Completed Names": tracker.LAB_CATALOG[0],
            }
        )
        self.import_csv(self.make_csv([completed]))
        student = tracker.get_admin_students(db_path=self.db_path)[0]
        transactions = tracker.get_xp_transactions(student["id"], self.db_path)
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]["amount"], 100)
        self.assertEqual(transactions[0]["reason"], "Skill badge 1 completed")

    def test_leaderboard_can_sort_by_progress_or_xp(self):
        first = self.row(
            **{
                "User Name": "Progress Leader",
                "User Email": "first@example.edu",
                "Google Skills Profile URL": "https://skills.example/first",
                "Skill Badges Completed Count": "5",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:5]),
            }
        )
        self.import_csv(self.make_csv([first]))
        tracker.update_gamification_settings(200, 0, 0, self.db_path)
        second = self.row(
            **{
                "User Name": "XP Leader",
                "User Email": "second@example.edu",
                "Google Skills Profile URL": "https://skills.example/second",
                "Skill Badges Completed Count": "4",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:4]),
            }
        )
        self.import_csv(self.make_csv([second]))
        students = tracker.get_admin_students(db_path=self.db_path)
        for student in students:
            tracker.update_student_settings(student["id"], student["name"], True, self.db_path)
        self.assertEqual(tracker.get_leaderboard(db_path=self.db_path)[0]["name"], "Progress Leader")
        self.assertEqual(tracker.get_leaderboard(db_path=self.db_path, sort_by="xp")[0]["name"], "XP Leader")

    def test_excluded_leaderboard_student_keeps_searchable_profile(self):
        excluded = self.row(
            **{
                "User Name": "Abdur Rahman Qasim",
                "User Email": "abdur@example.edu",
                "Google Skills Profile URL": "https://skills.example/abdur",
                "Skill Badges Completed Count": "10",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG),
            }
        )
        other = self.row(
            **{
                "User Name": "Another Student",
                "User Email": "another@example.edu",
                "Google Skills Profile URL": "https://skills.example/another",
                "Skill Badges Completed Count": "9",
                "Skill Badges Completed Names": ", ".join(tracker.LAB_CATALOG[:9]),
            }
        )
        self.import_csv(self.make_csv([excluded, other]))
        for student in tracker.get_admin_students(db_path=self.db_path):
            tracker.update_student_settings(
                student["id"], student["name"], True, self.db_path
            )

        leaderboard = tracker.get_leaderboard(db_path=self.db_path)
        matches = tracker.search_public_students("Abdur Rahman Qasim", self.db_path)
        self.assertEqual([student["name"] for student in leaderboard], ["Another Student"])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "Abdur Rahman Qasim")
        self.assertIsNotNone(tracker.get_student_profile(matches[0]["id"], db_path=self.db_path))

    def test_csv_exports_escape_spreadsheet_formulas(self):
        output = tracker.export_students(
            [
                {
                    "name": "=HYPERLINK(\"https://example.invalid\")",
                    "roll_number": "+SUM(1,1)",
                    "email": "@example.edu",
                    "badges_count": 1,
                    "xp": 100,
                    "updated_at": "2026-01-01",
                }
            ]
        )
        self.assertIn("'=HYPERLINK", output)
        self.assertIn("'+SUM", output)
        self.assertIn("'@example.edu", output)


if __name__ == "__main__":
    unittest.main()
