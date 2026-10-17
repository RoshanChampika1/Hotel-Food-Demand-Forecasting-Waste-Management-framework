"""Upload checks: every rule in src/upload_validation.py has a test that it catches the problem."""
import io

import pandas as pd
import pytest

from upload_validation import MAX_ROWS, UploadError, read_upload, template_csv, validate_upload


def check(csv_text):
    return validate_upload(read_upload("events.csv", csv_text.encode()))


def problems(result):
    return set(zip(result.errors["row"], result.errors["column"]))


def test_template_passes_with_no_problems():
    r = validate_upload(read_upload("t.csv", template_csv()))
    assert len(r.valid) == 2 and len(r.errors) == 0


def test_loose_headers_and_words_are_understood():
    r = check("Event No,Date,Type of Event,Session,No of Pax\nA1,21/11/2026,Homecoming,Night,\"1,200\"\n")
    row = r.valid.iloc[0]
    assert (row.event_date, row.event_type, row.meal_type, row.guests_expected) == ("2026-11-21", "other", "dinner", 1200)


@pytest.mark.parametrize("line, column", [
    ("A1,notadate,wedding,lunch,100", "event_date"),
    ("A1,,wedding,lunch,100", "event_date"),
    ("A1,1990-01-01,wedding,lunch,100", "event_date"),
    ("A1,2026-11-14,party,lunch,100", "event_type"),
    ("A1,2026-11-14,wedding,breakfast,100", "meal_type"),
    ("A1,2026-11-14,wedding,lunch,abc", "guests_expected"),
    ("A1,2026-11-14,wedding,lunch,12.5", "guests_expected"),
    ("A1,2026-11-14,wedding,lunch,0", "guests_expected"),
    ("A1,2026-11-14,wedding,lunch,6000", "guests_expected"),
])
def test_each_bad_value_is_reported_on_its_row(line, column):
    r = check("event_id,event_date,event_type,meal_type,guests_expected\n" + line + "\n")
    assert problems(r) == {(2, column)} and r.valid.empty


def test_good_rows_still_go_through_when_others_are_bad():
    r = check("event_id,event_date,event_type,meal_type,guests_expected\n"
              "A1,2026-11-14,wedding,lunch,100\nA2,bad,wedding,lunch,100\nA3,2026-11-15,corporate,dinner,80\n")
    assert list(r.valid.event_id) == ["A1", "A3"] and r.n_error_rows == 1


def test_duplicate_event_id():
    r = check("event_id,event_date,event_type,meal_type,guests_expected\n"
              "A1,2026-11-14,wedding,lunch,100\nA1,2026-11-15,wedding,lunch,90\n")
    assert problems(r) == {(3, "event_id")}


def test_missing_event_id_gets_one_from_the_row():
    r = check("event_date,event_type,meal_type,guests_expected\n2026-11-14,wedding,lunch,100\n")
    assert r.valid.event_id.iloc[0] == "ROW-2" and r.warnings


def test_missing_columns_stop_the_whole_file():
    r = check("date,guests\n2026-11-14,100\n")
    assert r.valid.empty and "event_type" in r.errors.column.iloc[0]


def test_empty_rows_and_extra_columns_only_warn():
    r = check("event_id,event_date,event_type,meal_type,guests_expected,notes\n"
              "A1,2026-11-14,wedding,lunch,100,hi\n,,,,,\n")
    assert len(r.valid) == 1 and len(r.errors) == 0 and len(r.warnings) == 2


def test_too_many_rows():
    body = "".join(f"E{i},2026-11-14,wedding,lunch,100\n" for i in range(MAX_ROWS + 1))
    r = check("event_id,event_date,event_type,meal_type,guests_expected\n" + body)
    assert r.valid.empty and "Too many rows" in r.errors.problem.iloc[0]


def test_excel_upload_works():
    buf = io.BytesIO()
    pd.DataFrame([{"event_date": "2026-11-14", "event_type": "Wedding", "meal_type": "Day",
                   "guests_expected": 150}]).to_excel(buf, index=False)
    r = validate_upload(read_upload("events.xlsx", buf.getvalue()))
    assert len(r.valid) == 1


@pytest.mark.parametrize("name, data, message", [
    ("events.csv", b"", "empty"),
    ("events.xls", b"x", "Only .csv and .xlsx"),
    ("events.pdf", b"x", "Only .csv and .xlsx"),
    ("events.xlsx", b"not really excel", "Could not open"),
    ("events.csv", b"x" * (5 * 1024 * 1024 + 1), "larger than"),
], ids=["empty", "xls", "pdf", "broken-xlsx", "too-big"])
def test_bad_files_are_refused_with_a_clear_message(name, data, message):
    with pytest.raises(UploadError, match=message):
        read_upload(name, data)
