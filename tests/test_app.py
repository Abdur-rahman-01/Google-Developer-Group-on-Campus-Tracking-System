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
            self.assertEqual(
                list(app.radio[0].options),
                ["Home", "Leaderboard"],
            )
            self.assertFalse(any("Admin console" in item.value for item in app.markdown))

            app.radio[0].set_value("Leaderboard").run()
            self.assertFalse(app.exception)
            self.assertTrue(
                any("Community leaderboard" in item.value for item in app.markdown)
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
            self.assertTrue(
                any(item.label == "Filter participants" for item in app.text_input)
            )
            self.assertIn("Load more participants", [button.label for button in app.button])
            app.button(key="load_more_participants").click().run()
            self.assertFalse(app.exception)
            participants_query.assert_called_with(limit=50, search="")
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
            self.assertEqual(markdown.count(">Step 1: Claim the credits</a>"), 2)


if __name__ == "__main__":
    unittest.main()
