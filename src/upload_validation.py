"""Read and validate an uploaded event list (CSV or Excel) before it reaches the forecast models.

Needed per event (booking-time information only, the same as the single-event form):
  event_date, event_type, meal_type, guests_expected   (event_id is optional)
Headers are matched loosely ("Pax Booked", "No of Pax" and "guests_expected" all work), and common
words are mapped to what the models know (Day -> lunch, Homecoming -> other).

Bad rows are reported with their Excel row number and skipped; good rows still go through.
The model was trained only on lunch/dinner events and on wedding, corporate, birthday and other
events, so other values are rejected instead of giving a forecast the model cannot back up.
"""
import io
from dataclasses import dataclass, field

import pandas as pd

MAX_ROWS = 2000
MAX_BYTES = 5 * 1024 * 1024
MIN_GUESTS, MAX_GUESTS = 1, 5000

REQUIRED = ["event_date", "event_type", "meal_type", "guests_expected"]
HEADER_ALIASES = {
    "event_id": ["event_id", "event_no", "event_number", "id", "event"],
    "event_date": ["event_date", "date", "date_of_event"],
    "event_type": ["event_type", "type", "type_of_event"],
    "meal_type": ["meal_type", "meal", "session"],
    "guests_expected": ["guests_expected", "guests", "pax", "pax_booked", "no_of_pax", "booked_pax",
                        "booked", "expected_guests"],
}
EVENT_TYPE_MAP = {"wedding": "wedding", "corporate": "corporate", "birthday": "birthday",
                  "birthday_party": "birthday", "other": "other", "homecoming": "other",
                  "engagement": "other", "function": "other"}
MEAL_TYPE_MAP = {"lunch": "lunch", "day": "lunch", "dinner": "dinner", "night": "dinner"}
SUPPORTED_EVENT_TYPES = ["wedding", "corporate", "birthday", "other"]
SUPPORTED_MEAL_TYPES = ["lunch", "dinner"]


class UploadError(ValueError):
    """A problem with the whole file, worded for the person who uploaded it."""


@dataclass
class UploadResult:
    valid: pd.DataFrame                               # clean rows, ready for predict_batch()
    errors: pd.DataFrame                              # one row per problem: row, column, problem
    warnings: list = field(default_factory=list)      # file-level notes that did not stop anything

    @property
    def n_error_rows(self):
        return self.errors["row"].nunique() if len(self.errors) else 0


def _key(text):
    return "_".join(str(text).strip().lower().replace("-", " ").replace(".", " ").split())


def read_upload(name, data: bytes) -> pd.DataFrame:
    """Turn the uploaded bytes into a table. Raises UploadError with a message for the user."""
    if len(data) == 0:
        raise UploadError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise UploadError(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    suffix = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    try:
        if suffix == "csv":
            for enc in ("utf-8-sig", "cp1252"):
                try:
                    return pd.read_csv(io.BytesIO(data), encoding=enc, dtype=str, skip_blank_lines=True)
                except UnicodeDecodeError:
                    continue
            raise UploadError("Could not read the text in this CSV. Save it as 'CSV UTF-8' and try again.")
        if suffix == "xlsx":
            return pd.read_excel(io.BytesIO(data), sheet_name=0, dtype=str)
    except UploadError:
        raise
    except Exception:  # broken, password-protected or mis-named files
        raise UploadError(f"Could not open the file. Is it a valid {suffix.upper()} file?")
    raise UploadError("Only .csv and .xlsx files are accepted.")


def _match_headers(df):
    lookup = {alias: col for col, aliases in HEADER_ALIASES.items() for alias in aliases}
    rename, used, extra = {}, set(), []
    for c in df.columns:
        target = lookup.get(_key(c))
        if target and target not in used:
            rename[c] = target
            used.add(target)
        else:
            extra.append(str(c))
    return df.rename(columns=rename)[list(rename.values())], extra


def _parse_date(value):
    text = str(value).strip()
    for kw in ({"format": "ISO8601"}, {"dayfirst": True}):
        try:
            return pd.to_datetime(text, **kw)
        except (ValueError, TypeError):
            continue
    return None


def validate_upload(df: pd.DataFrame) -> UploadResult:
    errors, warnings = [], []
    no_errors = pd.DataFrame(columns=["row", "column", "value", "problem"])

    df, extra = _match_headers(df)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        errors.append({"row": "-", "column": ", ".join(missing), "value": "",
                       "problem": "Required column missing. Download the template to see the expected headers."})
        return UploadResult(pd.DataFrame(), pd.DataFrame(errors), warnings)
    if extra:
        warnings.append(f"Ignored columns the forecast does not use: {', '.join(extra)}.")

    df = df.apply(lambda s: s.map(lambda v: v.strip() if isinstance(v, str) else v))
    df = df.replace("", pd.NA)
    df["row"] = df.index + 2                         # row number as Excel shows it (header is row 1)
    blank = df[REQUIRED].isna().all(axis=1)
    if blank.any():
        warnings.append(f"Skipped {int(blank.sum())} empty row(s).")
    df = df[~blank]
    if len(df) == 0:
        errors.append({"row": "-", "column": "", "value": "", "problem": "The file has no event rows."})
        return UploadResult(pd.DataFrame(), pd.DataFrame(errors), warnings)
    if len(df) > MAX_ROWS:
        errors.append({"row": "-", "column": "", "value": len(df),
                       "problem": f"Too many rows. Upload at most {MAX_ROWS} events at a time."})
        return UploadResult(pd.DataFrame(), pd.DataFrame(errors), warnings)

    clean, seen_ids = [], {}
    for r in df.to_dict("records"):
        row_errors = []

        def bad(col, problem):
            row_errors.append({"row": r["row"], "column": col, "value": r.get(col), "problem": problem})

        date = _parse_date(r["event_date"]) if pd.notna(r["event_date"]) else None
        if pd.isna(r["event_date"]):
            bad("event_date", "Date is missing.")
        elif date is None:
            bad("event_date", "Not a date. Use YYYY-MM-DD or DD/MM/YYYY.")
        elif not 2000 <= date.year <= 2100:
            bad("event_date", "Year must be between 2000 and 2100.")

        etype = EVENT_TYPE_MAP.get(_key(r["event_type"])) if pd.notna(r["event_type"]) else None
        if etype is None:
            bad("event_type", f"Unknown event type. Use one of: {', '.join(SUPPORTED_EVENT_TYPES)} "
                              "(homecoming, engagement and function count as other).")

        meal = MEAL_TYPE_MAP.get(_key(r["meal_type"])) if pd.notna(r["meal_type"]) else None
        if meal is None:
            bad("meal_type", "Use lunch (or day) or dinner (or night). The model has no data for other meals.")

        guests = pd.to_numeric(str(r["guests_expected"]).replace(",", ""), errors="coerce") \
            if pd.notna(r["guests_expected"]) else float("nan")
        if pd.isna(guests):
            bad("guests_expected", "Guest count must be a number.")
        elif guests != int(guests):
            bad("guests_expected", "Guest count must be a whole number.")
        elif not MIN_GUESTS <= guests <= MAX_GUESTS:
            bad("guests_expected", f"Guest count must be between {MIN_GUESTS} and {MAX_GUESTS}.")

        event_id = str(r["event_id"]) if pd.notna(r.get("event_id", pd.NA)) else f"ROW-{r['row']}"
        if event_id in seen_ids:
            bad("event_id", f"Same event_id as row {seen_ids[event_id]}.")
        else:
            seen_ids[event_id] = r["row"]

        if row_errors:
            errors.extend(row_errors)
        else:
            clean.append({"row": r["row"], "event_id": event_id, "event_date": date.date().isoformat(),
                          "event_type": etype, "meal_type": meal, "guests_expected": int(guests)})

    if any(str(e).startswith("ROW-") for e in seen_ids):
        warnings.append("Some rows had no event_id, so one was made from the row number (ROW-<n>).")
    return UploadResult(pd.DataFrame(clean), pd.DataFrame(errors) if errors else no_errors, warnings)


def template_csv() -> bytes:
    rows = [["EVT-001", "2026-11-14", "wedding", "lunch", 250],
            ["EVT-002", "21/11/2026", "corporate", "dinner", 120]]
    return pd.DataFrame(rows, columns=["event_id"] + REQUIRED).to_csv(index=False).encode()
