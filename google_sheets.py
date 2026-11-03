from __future__ import annotations

from typing import Any

import gspread


TRACKING_HEADERS = (
    "Name",
    "Roll Number",
)


def _header_key(value: str) -> str:
    key = "".join(character for character in str(value).casefold() if character.isalnum())
    return key.replace("rollno", "rollnumber")


def _normalize_name(value: str) -> str:
    return " ".join(str(value).casefold().split())


def phone_number_for_student(
    student: dict[str, Any],
    roll_map: list[dict[str, str]],
) -> str:
    student_roll = _normalize_name(str(student.get("roll_number") or ""))
    student_name = _normalize_name(str(student.get("name") or ""))
    for row in roll_map:
        if not row.get("Phone Number"):
            continue
        if student_roll and _normalize_name(row.get("Roll Number", "")) == student_roll:
            return row["Phone Number"]
    for row in roll_map:
        if (
            student_name
            and _normalize_name(row.get("Name", "")) == student_name
            and row.get("Phone Number")
        ):
            return row["Phone Number"]
    return ""


def _roll_map_columns(headers: list[str]) -> tuple[int, int, int | None]:
    indexes = {_header_key(header): index for index, header in enumerate(headers)}
    name_index = next(
        (
            indexes[key]
            for key in ("name", "studentname", "username")
            if key in indexes
        ),
        None,
    )
    roll_index = next(
        (
            indexes[key]
            for key in ("rollnumber", "rollno", "roll")
            if key in indexes
        ),
        None,
    )
    phone_index = next(
        (
            indexes[key]
            for key in ("phonenumber", "phone", "contactnumber", "mobilenumber", "mobile")
            if key in indexes
        ),
        None,
    )
    if name_index is None or roll_index is None:
        raise ValueError(
            'The roll-number map needs "Name" and "Roll Number" columns.'
        )
    return name_index, roll_index, phone_index


def _find_roll_map_header(
    values: list[list[str]],
) -> tuple[int, list[str], int, int, int | None]:
    for row_index, row in enumerate(values[:10]):
        headers = [str(value).strip() for value in row]
        try:
            name_index, roll_index, phone_index = _roll_map_columns(headers)
        except ValueError:
            continue
        return row_index, headers, name_index, roll_index, phone_index
    raise ValueError(
        'Could not find "Name" and "Roll Number" columns in the first 10 rows '
        "of the roll-number map tab. Check the configured tab name and header row."
    )


def _update_row(worksheet, row_number: int, values: list[str]) -> None:
    last_cell = gspread.utils.rowcol_to_a1(row_number, len(values))
    worksheet.update(
        range_name=f"A{row_number}:{last_cell}",
        values=[values],
        value_input_option="RAW",
    )


class GoogleSheetsStore:
    def __init__(
        self,
        spreadsheet_id: str,
        service_account_info: dict[str, Any],
        tracking_tab: str = "Tracking Data",
        roll_map_tab: str = "rollno map",
    ) -> None:
        client = gspread.service_account_from_dict(service_account_info)
        self.spreadsheet = client.open_by_key(spreadsheet_id)
        self.tracking_tab = tracking_tab
        self.roll_map_tab = roll_map_tab

    def _worksheet(self, title: str, headers: tuple[str, ...] | None = None):
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            requested_key = _header_key(title)
            for worksheet in self.spreadsheet.worksheets():
                if _header_key(worksheet.title) == requested_key:
                    return worksheet
            if headers is None:
                raise
            worksheet = self.spreadsheet.add_worksheet(
                title=title,
                rows=100,
                cols=len(headers),
            )
            _update_row(worksheet, 1, list(headers))
            return worksheet

    def read_tracking_data(self) -> tuple[list[str], list[dict[str, str]]]:
        values = self._worksheet(self.tracking_tab).get_all_values()
        if not values or not any(str(value).strip() for value in values[0]):
            raise ValueError(
                f'The "{self.tracking_tab}" tab must have a header row and participant data.'
            )
        headers = [str(value).strip() for value in values[0]]
        if len(set(header.casefold() for header in headers)) != len(headers):
            raise ValueError(f'The "{self.tracking_tab}" tab has duplicate column names.')
        records = []
        for values_row in values[1:]:
            padded = [*values_row, *("" for _ in range(len(headers) - len(values_row)))]
            record = {
                header: str(padded[index]).strip()
                for index, header in enumerate(headers)
                if header
            }
            if any(record.values()):
                records.append(record)
        if not records:
            raise ValueError(f'The "{self.tracking_tab}" tab contains no participant rows.')
        return headers, records

    def read_roll_number_map(self) -> list[dict[str, str]]:
        worksheet = self._worksheet(self.roll_map_tab, TRACKING_HEADERS)
        values = worksheet.get_all_values()
        if not values:
            _update_row(worksheet, 1, list(TRACKING_HEADERS))
            return []
        header_row, headers, name_index, roll_index, phone_index = _find_roll_map_header(values)
        rows = []
        seen_names: set[str] = set()
        seen_roll_numbers: set[str] = set()
        for values_row in values[header_row + 1 :]:
            padded = [*values_row, *("" for _ in range(len(headers) - len(values_row)))]
            row = {
                "Name": str(padded[name_index]).strip(),
                "Roll Number": str(padded[roll_index]).strip(),
                "Phone Number": (
                    str(padded[phone_index]).strip()
                    if phone_index is not None
                    else ""
                ),
            }
            if row["Name"]:
                normalized_name = _normalize_name(row["Name"])
                if normalized_name in seen_names:
                    raise ValueError(
                        f'The "{self.roll_map_tab}" tab contains a duplicate student name: '
                        f'{row["Name"]}.'
                    )
                seen_names.add(normalized_name)
                roll_number = row["Roll Number"].casefold()
                if roll_number and roll_number in seen_roll_numbers:
                    raise ValueError(
                        f'The "{self.roll_map_tab}" tab contains a duplicate roll number: '
                        f'{row["Roll Number"]}.'
                    )
                if roll_number:
                    seen_roll_numbers.add(roll_number)
                rows.append(row)
        return rows

    def save_student_mapping(
        self,
        name: str,
        roll_number: str,
    ) -> None:
        worksheet = self._worksheet(self.roll_map_tab, TRACKING_HEADERS)
        values = worksheet.get_all_values()
        if not values:
            _update_row(worksheet, 1, list(TRACKING_HEADERS))
            values = [list(TRACKING_HEADERS)]
        header_row, headers, name_index, roll_index, _ = _find_roll_map_header(values)
        name = name.strip()
        if not name:
            raise ValueError("A student name is required to save a roll number.")
        target_row = None
        for row_number, values_row in enumerate(values[header_row + 1 :], start=header_row + 2):
            padded = [*values_row, *("" for _ in range(len(headers) - len(values_row)))]
            stored_name = _normalize_name(str(padded[name_index]))
            if stored_name == _normalize_name(name):
                target_row = row_number
                break

        row = list(values[target_row - 1]) if target_row else [""] * len(headers)
        row.extend("" for _ in range(len(headers) - len(row)))
        row[name_index] = name
        row[roll_index] = roll_number.strip()
        if target_row is None:
            worksheet.append_row(row, value_input_option="RAW")
        else:
            _update_row(worksheet, target_row, row)
