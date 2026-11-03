from __future__ import annotations

from typing import Any

import gspread


TRACKING_HEADERS = (
    "User Email",
    "Google Skills Profile URL",
    "Roll Number",
    "Public Visible",
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
        roll_map_tab: str = "Roll Number Map",
    ) -> None:
        client = gspread.service_account_from_dict(service_account_info)
        self.spreadsheet = client.open_by_key(spreadsheet_id)
        self.tracking_tab = tracking_tab
        self.roll_map_tab = roll_map_tab

    def _worksheet(self, title: str, headers: tuple[str, ...] | None = None):
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
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
        headers = [str(value).strip() for value in values[0]]
        normalized = {header.casefold(): index for index, header in enumerate(headers)}
        required = {header.casefold() for header in TRACKING_HEADERS}
        missing = required - normalized.keys()
        if missing:
            raise ValueError(
                f'The "{self.roll_map_tab}" tab is missing required columns: '
                f'{", ".join(sorted(missing))}.'
            )
        rows = []
        seen_identities: set[str] = set()
        for values_row in values[1:]:
            padded = [*values_row, *("" for _ in range(len(headers) - len(values_row)))]
            row = {
                header: str(padded[normalized[header.casefold()]]).strip()
                for header in TRACKING_HEADERS
            }
            if row["User Email"] or row["Google Skills Profile URL"]:
                identities = {
                    value.casefold()
                    for value in (row["User Email"], row["Google Skills Profile URL"])
                    if value
                }
                if seen_identities.intersection(identities):
                    raise ValueError(
                        f'The "{self.roll_map_tab}" tab contains a duplicate student identity.'
                    )
                seen_identities.update(identities)
                rows.append(row)
        return rows

    def save_student_mapping(
        self,
        email: str,
        skills_profile_url: str,
        roll_number: str,
        public_visible: bool,
    ) -> None:
        worksheet = self._worksheet(self.roll_map_tab, TRACKING_HEADERS)
        values = worksheet.get_all_values()
        if not values:
            _update_row(worksheet, 1, list(TRACKING_HEADERS))
            values = [list(TRACKING_HEADERS)]
        headers = [str(value).strip() for value in values[0]]
        indexes = {header.casefold(): index for index, header in enumerate(headers)}
        required = {header.casefold() for header in TRACKING_HEADERS}
        missing = required - indexes.keys()
        if missing:
            raise ValueError(
                f'The "{self.roll_map_tab}" tab is missing required columns: '
                f'{", ".join(sorted(missing))}.'
            )
        email = email.strip()
        skills_profile_url = skills_profile_url.strip()
        target_row = None
        for row_number, values_row in enumerate(values[1:], start=2):
            padded = [*values_row, *("" for _ in range(len(headers) - len(values_row)))]
            stored_email = str(padded[indexes["user email"]]).strip().casefold()
            stored_profile = str(
                padded[indexes["google skills profile url"]]
            ).strip().casefold()
            if (
                (email and stored_email == email.casefold())
                or (
                    skills_profile_url
                    and stored_profile == skills_profile_url.casefold()
                )
            ):
                target_row = row_number
                break

        row = [""] * len(headers)
        row[indexes["user email"]] = email
        row[indexes["google skills profile url"]] = skills_profile_url
        row[indexes["roll number"]] = roll_number.strip()
        row[indexes["public visible"]] = "TRUE" if public_visible else "FALSE"
        if target_row is None:
            worksheet.append_row(row, value_input_option="RAW")
        else:
            _update_row(worksheet, target_row, row)
