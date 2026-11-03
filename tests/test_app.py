import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def test_sidebar_navigates_single_page_sections_without_admin(self):
        app_path = Path(__file__).parent.parent / "app.py"
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"GDG_DB_PATH": str(Path(temp_dir) / "app.db")},
        ):
            app = AppTest.from_file(str(app_path), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertEqual(list(app.radio[0].options)[:2], ["Home", "Leaderboard"])
            self.assertFalse(any("Admin console" in item.value for item in app.markdown))

            app.radio[0].set_value("Leaderboard").run()
            self.assertFalse(app.exception)
            self.assertTrue(
                any("Community leaderboard" in item.value for item in app.markdown)
            )

    def test_admin_navigation_is_available_only_when_password_is_configured(self):
        app_path = Path(__file__).parent.parent / "app.py"
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "GDG_DB_PATH": str(Path(temp_dir) / "app.db"),
                "GDG_ADMIN_PASSWORD": "test-admin-password",
            },
        ):
            app = AppTest.from_file(str(app_path), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertEqual(list(app.radio[0].options), ["Home", "Leaderboard", "Admin"])

            app.radio[0].set_value("Admin").run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Admin console" in item.value for item in app.title))
            self.assertTrue(any(item.label == "Admin password" for item in app.text_input))

    def test_authenticated_admin_renders_analysis_and_roll_number_breakdown(self):
        app_path = Path(__file__).parent.parent / "app.py"
        student = {
            "id": 1,
            "name": "Analysis Student",
            "roll_number": "MCET-001",
            "badges_count": 3,
            "badges_names": '["Badge One"]',
            "updated_at": "2026-11-03",
            "public_visible": True,
            "email": "student@example.edu",
            "xp": 150,
            "skills_profile_url": "https://skills.google/profile/admin-student",
            "developer_profile_url": "https://developers.google.com/profile/admin-student",
        }
        metrics = {
            "students": 1,
            "started": 1,
            "not_started": 0,
            "completed": 0,
            "average": 3.0,
            "recently_added": 1,
            "badges": 3,
            "completion_rate": 0.0,
            "last_updated": "2026-11-03",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "GDG_DB_PATH": str(Path(temp_dir) / "app.db"),
                "GDG_ADMIN_PASSWORD": "test-admin-password",
            },
        ), patch("tracker.get_dashboard_data", return_value=metrics), patch(
            "tracker.get_all_students", return_value=[student]
        ), patch("tracker.count_admin_students", return_value=1), patch(
            "tracker.get_admin_students", return_value=[student]
        ), patch("tracker.get_xp_transactions", return_value=[]):
            app = AppTest.from_file(str(app_path), default_timeout=30).run()
            app.radio[0].set_value("Admin").run()
            app.session_state["gdg_admin_authenticated"] = True
            app.run()

            self.assertFalse(app.exception)
            self.assertTrue(any(item.label == "Registered" for item in app.metric))
            self.assertTrue(any("Student progress distribution" in item.value for item in app.markdown))
            self.assertTrue(any("Top performers" in item.value for item in app.markdown))
            self.assertTrue(
                any("MCET-001" in str(frame) for frame in (item.value for item in app.dataframe))
            )
            self.assertTrue(
                any(
                    "Phone number (admin only)" in item.value.columns
                    for item in app.dataframe
                )
            )
            admin_students_frame = next(
                item.value
                for item in app.dataframe
                if "Phone number (admin only)" in item.value.columns
            )
            self.assertIn("Google Skills Boost profile", admin_students_frame.columns)
            self.assertIn("Google Developer profile", admin_students_frame.columns)
            self.assertNotIn("Last updated", admin_students_frame.columns)
            self.assertEqual(
                admin_students_frame.iloc[0]["Google Skills Boost profile"],
                "https://skills.google/profile/admin-student",
            )
            self.assertEqual(
                admin_students_frame.iloc[0]["Google Developer profile"],
                "https://developers.google.com/profile/admin-student",
            )
            self.assertIn(
                "Refresh contact numbers from Google Sheets",
                [button.label for button in app.button],
            )

    def test_home_has_whatsapp_help_and_hides_outdated_update_section(self):
        app_path = Path(__file__).parent.parent / "app.py"
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"GDG_DB_PATH": str(Path(temp_dir) / "app.db")},
        ), patch(
            "tracker.get_public_participants",
            return_value=(
                [
                    {
                        "id": 1,
                        "name": "Approved Participant",
                        "roll_number": "MCET-001",
                        "badges_count": 3,
                    }
                ],
                True,
            ),
        ) as participants_query:
            app = AppTest.from_file(str(app_path), default_timeout=30).run()
            self.assertFalse(app.exception)
            markdown = "\n".join(item.value for item in app.markdown)
            self.assertIn("https://wa.me/966571696327", markdown)
            self.assertIn("Contact for help", markdown)
            self.assertIn("class=\"resource-button-row\"", markdown)
            self.assertIn("class=\"resource-button claim-credits\"", markdown)
            self.assertNotIn("[data-testid=\"stProgress\"] > div > div", markdown)
            self.assertIn("Step 1: Claim the credits", markdown)
            self.assertIn("https://youtu.be/WVdUW1wJwyI?si=-QUUEoe4gE6-gfG5", markdown)
            self.assertLess(
                markdown.index("https://youtu.be/WVdUW1wJwyI?si=-QUUEoe4gE6-gfG5"),
                markdown.index("https://docs.google.com/spreadsheets/"),
            )
            self.assertLess(
                markdown.index("https://youtu.be/WVdUW1wJwyI?si=-QUUEoe4gE6-gfG5"),
                markdown.index("https://youtube.com/playlist"),
            )
            self.assertNotIn("Your next badge is one step away", markdown)
            self.assertNotIn("Latest student record update", markdown)
            self.assertTrue(any("GDG participants" in item.value for item in app.subheader))
            self.assertEqual(list(app.dataframe[0].value.columns), ["Participant"])
            self.assertTrue(
                any(item.label == "Filter participants" for item in app.text_input)
            )
            self.assertIn("Load more participants", [button.label for button in app.button])
            app.button(key="load_more_participants").click().run()
            self.assertFalse(app.exception)
            participants_query.assert_called_with(limit=50, search="")
            app.text_input(key="participant_search").set_value("MCET-001").run()
            self.assertFalse(app.exception)
            participants_query.assert_called_with(limit=25, search="MCET-001")
            app.text_input(key="participant_search").set_value("Approved").run()
            self.assertFalse(app.exception)
            participants_query.assert_called_with(limit=25, search="Approved")

    def test_completed_student_gets_celebration_without_resource_buttons(self):
        app_path = Path(__file__).parent.parent / "app.py"
        student = {
            "id": 1,
            "name": "Test Student",
            "roll_number": "12345",
            "badges_count": 10,
            "badges_names": ["Badge One"],
            "access_code_status": "Redeemed",
            "is_gear_participant": False,
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"GDG_DB_PATH": str(Path(temp_dir) / "app.db")},
        ), patch("tracker.search_public_students", return_value=[student]), patch(
            "tracker.get_student_profile", return_value=student
        ):
            app = AppTest.from_file(str(app_path), default_timeout=30).run()
            app.text_input(key="student_search").set_value("Test Student").run()
            self.assertFalse(app.exception)
            markdown = "\n".join(item.value for item in app.markdown)
            self.assertIn("Quest complete!", markdown)
            self.assertIn("Congratulations, Test Student!", markdown)
            self.assertIn("10 / 10 badges earned", markdown)
            self.assertEqual(markdown.count(">Campaign syllabus</a>"), 1)
            self.assertEqual(markdown.count(">Playlist to complete</a>"), 1)

    def test_incomplete_student_sees_progress_status_and_learning_resources(self):
        app_path = Path(__file__).parent.parent / "app.py"
        student = {
            "id": 1,
            "name": "In Progress Student",
            "roll_number": "12345",
            "badges_count": 0,
            "badges_names": [],
            "access_code_status": "Not reported",
            "is_gear_participant": False,
            "skills_profile_url": (
                "https://www.cloudskillsboost.google/public_profiles/boost-student-id"
            ),
            "developer_profile_url": "https://developers.google.com/profile/student",
            "skills_profile_status": "Complete",
            "developer_profile_status": "In progress",
            "gear_badges": "Not applicable",
            "milestone": "Not applicable",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"GDG_DB_PATH": str(Path(temp_dir) / "app.db")},
        ), patch("tracker.search_public_students", return_value=[student]), patch(
            "tracker.get_student_profile", return_value=student
        ):
            app = AppTest.from_file(str(app_path), default_timeout=30).run()
            app.text_input(key="student_search").set_value("In Progress Student").run()
            self.assertFalse(app.exception)
            markdown = "\n".join(item.value for item in app.markdown)
            self.assertTrue(
                any("You haven't started your skill badges yet" in item.value for item in app.info)
            )
            self.assertIn("#### Your learning resources", markdown)
            self.assertIn("#### GEAR and profile status", markdown)
            self.assertIn(
                "Google Skills Boost profile ID: boost-student-id",
                "\n".join(item.value for item in app.caption),
            )
            self.assertNotIn(
                "Google Developer profile",
                [button.label for button in app.button],
            )
            metric_labels = {item.label for item in app.metric}
            self.assertIn("Google Skills profile status", metric_labels)
            self.assertIn("Google Developer profile status", metric_labels)
            self.assertEqual(markdown.count(">Step 1: Claim the credits</a>"), 2)


if __name__ == "__main__":
    unittest.main()
