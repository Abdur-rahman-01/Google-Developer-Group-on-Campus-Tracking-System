import unittest
from unittest.mock import patch

import gspread

from google_sheets import GoogleSheetsStore, TRACKING_HEADERS, phone_number_for_student


class FakeWorksheet:
    def __init__(self, values, title=""):
        self.values = values
        self.title = title
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
        self._worksheets = worksheets
        self.batch_ranges = []

    def worksheet(self, title):
        if title not in self._worksheets:
            raise gspread.WorksheetNotFound(title)
        return self._worksheets[title]

    def add_worksheet(self, title, rows, cols):
        worksheet = FakeWorksheet([], title)
        self._worksheets[title] = worksheet
        return worksheet

    def worksheets(self):
        return list(self._worksheets.values())

    def values_batch_get(self, ranges):
        self.batch_ranges = ranges
        return {
            "valueRanges": [
                {
                    "values": self._worksheets[
                        sheet_range.split("!")[0].strip("'").replace("''", "'")
                    ].values
                }
                for sheet_range in ranges
            ]
        }


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

    def test_reads_tracking_and_roll_map_in_one_batch(self):
        store, spreadsheet = self.make_store(
            {
                "Tracking Data": FakeWorksheet(
                    [
                        ["User Name", "User Email"],
                        ["A Student", "a@example.com"],
                    ],
                    "Tracking Data",
                ),
                "rollno map": FakeWorksheet(
                    [
                        ["Name", "Roll Number"],
                        ["A Student", "123"],
                    ],
                    "rollno map",
                ),
            }
        )

        headers, records, roll_map = store.read_tracking_and_roll_number_map()

        self.assertEqual(headers, ["User Name", "User Email"])
        self.assertEqual(records[0]["User Name"], "A Student")
        self.assertEqual(roll_map[0]["Roll Number"], "123")
        self.assertEqual(
            spreadsheet.batch_ranges,
            ["'Tracking Data'!A:ZZ", "'rollno map'!A:ZZ"],
        )

    def test_creates_roll_map_tab_with_required_header(self):
        store, spreadsheet = self.make_store({})

        self.assertEqual(store.read_roll_number_map(), [])

        worksheet = spreadsheet._worksheets["rollno map"]
        self.assertEqual(worksheet.updates[0]["range_name"], "A1:B1")
        self.assertEqual(
            worksheet.updates[0]["values"],
            [["Name", "Roll Number"]],
        )

    def test_saves_student_mapping_and_updates_existing_identity(self):
        worksheet = FakeWorksheet(
            [
                ["Name", "Roll No"],
                ["Student One", "123"],
            ],
            "rollno map",
        )
        store, _ = self.make_store({"rollno map": worksheet})

        store.save_student_mapping(
            " student   one ",
            "456",
        )

        self.assertEqual(
            worksheet.updates,
            [
                {
                    "range_name": "A2:B2",
                    "values": [["student   one", "456"]],
                    "value_input_option": "RAW",
                }
            ],
        )
        self.assertEqual(worksheet.appended, [])

    def test_reads_name_roll_map_and_rejects_duplicate_names(self):
        store, _ = self.make_store(
            {
                "rollno map": FakeWorksheet(
                    [
                        ["Name", "Roll Number"],
                        ["Student One", "123"],
                        ["Student Two", "456"],
                    ],
                    "rollno map",
                )
            }
        )
        self.assertEqual(
            store.read_roll_number_map(),
            [
                {"Name": "Student One", "Roll Number": "123", "Phone Number": ""},
                {"Name": "Student Two", "Roll Number": "456", "Phone Number": ""},
            ],
        )

    def test_reads_roll_map_headers_after_title_row_and_with_invisible_prefix(self):
        store, _ = self.make_store(
            {
                "rollno map": FakeWorksheet(
                    [
                        ["Curated student roster"],
                        ["\ufeffName ", "Roll Number"],
                        ["Student One", "123"],
                    ],
                    "rollno map",
                )
            }
        )

        self.assertEqual(
            store.read_roll_number_map(),
            [{"Name": "Student One", "Roll Number": "123", "Phone Number": ""}],
        )

    def test_reads_phone_numbers_as_text_from_optional_roll_map_column(self):
        store, _ = self.make_store(
            {
                "rollno map": FakeWorksheet(
                    [
                        ["Name", "Roll Number", "Phone Number"],
                        ["Student One", "00123", "+966 54 815 2008"],
                    ],
                    "rollno map",
                )
            }
        )

        self.assertEqual(
            store.read_roll_number_map(),
            [
                {
                    "Name": "Student One",
                    "Roll Number": "00123",
                    "Phone Number": "+966 54 815 2008",
                }
            ],
        )

    def test_phone_number_lookup_prefers_roll_number_and_falls_back_to_name(self):
        roll_map = [
            {
                "Name": "Original Name",
                "Roll Number": "MCET-001",
                "Phone Number": "1111111111",
            },
            {
                "Name": "Renamed Student",
                "Roll Number": "MCET-002",
                "Phone Number": "2222222222",
            },
        ]

        self.assertEqual(
            phone_number_for_student(
                {"name": "Student Name Updated", "roll_number": "mcet-002"},
                roll_map,
            ),
            "2222222222",
        )
        self.assertEqual(
            phone_number_for_student(
                {"name": "  ORIGINAL   NAME ", "roll_number": ""},
                roll_map,
            ),
            "1111111111",
        )

    def test_saves_roll_map_entry_below_title_and_header_rows(self):
        worksheet = FakeWorksheet(
            [
                ["Curated student roster"],
                ["Name", "Roll Number"],
                ["Student One", "123"],
            ],
            "rollno map",
        )
        store, _ = self.make_store({"rollno map": worksheet})

        store.save_student_mapping("Student One", "456")

        self.assertEqual(
            worksheet.updates,
            [
                {
                    "range_name": "A3:B3",
                    "values": [["Student One", "456"]],
                    "value_input_option": "RAW",
                }
            ],
        )

    def test_rejects_duplicate_name_and_roll_number_entries(self):
        duplicate_names, _ = self.make_store(
            {
                "rollno map": FakeWorksheet(
                    [
                        ["Name", "Roll Number"],
                        ["Student One", "123"],
                        [" student  one ", "456"],
                    ],
                    "rollno map",
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "duplicate student name"):
            duplicate_names.read_roll_number_map()

        duplicate_rolls, _ = self.make_store(
            {
                "rollno map": FakeWorksheet(
                    [
                        ["Name", "Roll Number"],
                        ["Student One", "123"],
                        ["Student Two", "123"],
                    ],
                    "rollno map",
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "duplicate roll number"):
            duplicate_rolls.read_roll_number_map()

    def test_finds_roll_map_tab_when_configured_with_old_tab_label(self):
        store, _ = self.make_store(
            {
                "rollno map": FakeWorksheet(
                    [["Name", "Roll Number"], ["Student One", "123"]],
                    "rollno map",
                )
            }
        )
        store.roll_map_tab = "Roll Number Map"

        self.assertEqual(store.read_roll_number_map()[0]["Roll Number"], "123")


if __name__ == "__main__":
    unittest.main()
