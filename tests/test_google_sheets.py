import unittest
from unittest.mock import patch

import gspread

from google_sheets import GoogleSheetsStore, TRACKING_HEADERS


class FakeWorksheet:
    def __init__(self, values):
        self.values = values
        self.updates = []
        self.appended = []

    def get_all_values(self):
        return self.values

    def update(self, **kwargs):
        self.updates.append(kwargs)

    def append_row(self, row, **kwargs):
        self.appended.append((row, kwargs))


class FakeSpreadsheet:
    def __init__(self, worksheets):
        self.worksheets = worksheets

    def worksheet(self, title):
        if title not in self.worksheets:
            raise gspread.WorksheetNotFound(title)
        return self.worksheets[title]

    def add_worksheet(self, title, rows, cols):
        worksheet = FakeWorksheet([])
        self.worksheets[title] = worksheet
        return worksheet


class GoogleSheetsStoreTests(unittest.TestCase):
    def make_store(self, worksheets):
        spreadsheet = FakeSpreadsheet(worksheets)
        client = unittest.mock.Mock()
        client.open_by_key.return_value = spreadsheet
        with patch("gspread.service_account_from_dict", return_value=client):
            store = GoogleSheetsStore("spreadsheet-id", {"client_email": "test@example.com"})
        return store, spreadsheet

    def test_reads_tracking_headers_and_rows(self):
        store, _ = self.make_store(
            {
                "Tracking Data": FakeWorksheet(
                    [
                        ["User Name", "User Email", "Skill Badges Completed Count"],
                        ["A Student", "a@example.com", "4"],
                        ["", "", ""],
                    ]
                )
            }
        )

        headers, rows = store.read_tracking_data()

        self.assertEqual(headers, ["User Name", "User Email", "Skill Badges Completed Count"])
        self.assertEqual(
            rows,
            [
                {
                    "User Name": "A Student",
                    "User Email": "a@example.com",
                    "Skill Badges Completed Count": "4",
                }
            ],
        )

    def test_creates_roll_map_tab_with_required_header(self):
        store, spreadsheet = self.make_store({})

        self.assertEqual(store.read_roll_number_map(), [])

        worksheet = spreadsheet.worksheets["Roll Number Map"]
        self.assertEqual(worksheet.updates[0]["range_name"], "A1:D1")
        self.assertEqual(worksheet.updates[0]["values"], [list(TRACKING_HEADERS)])

    def test_saves_student_mapping_and_updates_existing_identity(self):
        worksheet = FakeWorksheet(
            [
                list(TRACKING_HEADERS),
                ["student@example.com", "https://skills.example/1", "123", "FALSE"],
            ]
        )
        store, _ = self.make_store({"Roll Number Map": worksheet})

        store.save_student_mapping(
            "STUDENT@example.com",
            "https://skills.example/1",
            "456",
            True,
        )

        self.assertEqual(
            worksheet.updates,
            [
                {
                    "range_name": "A2:D2",
                    "values": [
                        [
                            "STUDENT@example.com",
                            "https://skills.example/1",
                            "456",
                            "TRUE",
                        ]
                    ],
                    "value_input_option": "RAW",
                }
            ],
        )
        self.assertEqual(worksheet.appended, [])


if __name__ == "__main__":
    unittest.main()
