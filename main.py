#!/usr/bin/env python3
"""Run the six column detectors and classify CSV columns.

Run interactively:
    python main.py

Or pass a CSV path directly:
    python main.py sample_employees.csv
    python main.py sample_employees.csv --json
    python main.py sample_employees.csv --verbose
"""
import argparse
import csv
import datetime as dt
import io
import json
import sys
from pathlib import Path

from detectors import ssn, email, phone_number, date_of_birth, city, person_name, us_state, employment_position

DATA_DIR = Path(__file__).resolve().parent / "data"
MANDATORY_COLUMN_THRESHOLD = 0.95
NULL_VALUES = {"", "null", "none", "n/a", "na", "nan", "nil", "-", "--", "?", "undefined", "unknown"}

# Specific categories run before broad categories such as City and Person Name.
DETECTORS = [
    ("National ID (US SSN)", ssn.detect),
    ("Email Address", email.detect),
    ("Phone Number", phone_number.detect),
    ("Date of Birth", date_of_birth.detect),
    ("US State", us_state.detect),
    ("Employment Position", employment_position.detect),
    ("City", city.detect),
    ("Person Name", person_name.detect),
]

DOB_HEADERS = {"dob", "date_of_birth", "birth_date", "birthdate", "date_birth"}
NON_DOB_DATE_HEADERS = {
    "start_date", "hire_date", "employment_start", "employment_start_date",
    "termination_date", "end_date", "created_at", "updated_at",
    "date_created", "date_updated", "joining_date",
}


class Resources:
    """Optional reference data used only as supplemental evidence."""

    def __init__(self, today=None):
        self.today = today or dt.date.today()
        self.cities = self._load_set("cities.txt")
        self.first_names = self._load_set("first_names.txt")
        self.surnames = self._load_set("surnames.txt")
        self.us_states = self._load_set("us_states.txt")
        self.employment_positions = self._load_set("employment_positions.txt")

    @staticmethod
    def _load_set(filename):
        path = DATA_DIR / filename
        values = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.lstrip().startswith("#"):
                    continue
                values.update(item.strip().lower() for item in line.split(",") if item.strip())
        return values


def supplemental_result(category, value, details, resources, header=""):
    """Return whether optional evidence supports a mandatory match."""
    if category == "National ID (US SSN)":
        return bool(details.get("formatted") or details.get("area_at_or_below_772"))
    if category == "Email Address":
        return bool(details.get("valid_looking_tld"))
    if category == "Phone Number":
        return bool(details.get("has_country_prefix") or details.get("formatted_us_number"))
    if category == "Date of Birth":
        normalized_header = header.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized_header in NON_DOB_DATE_HEADERS:
            return False
        return bool(details.get("plausible_birth_age") or normalized_header in DOB_HEADERS)
    if category == "US State":
        return bool(details.get("known_us_state"))
    if category == "Employment Position":
        return bool(details.get("known_employment_position"))
    if category == "City":
        return bool(details.get("known_city"))
    if category == "Person Name":
        return bool(details.get("known_first_name") and details.get("known_last_name"))
    return False


def classify_column(header, raw_values, resources=None):
    resources = resources or Resources()
    values = [v.strip() if isinstance(v, str) else v for v in raw_values]
    values = [v for v in values if not (isinstance(v, str) and v.lower() in NULL_VALUES) and v is not None]
    result = {
        "column": header,
        "data_class": "Not classified",
        "confidence": None,
        "rows_non_empty": len(values),
        "candidates": [],
        "reason": "",
    }
    if not values:
        result["reason"] = "Column contains no non-empty values."
        return result

    accepted = []
    for category, detector in DETECTORS:
        mandatory = 0
        supplemental = 0
        for value in values:
            valid, details = detector(value, resources)
            if valid:
                mandatory += 1
                if supplemental_result(category, value, details, resources, header):
                    supplemental += 1
        mandatory_rate = mandatory / len(values)
        supplemental_rate = supplemental / len(values)
        normalized_header = header.strip().lower().replace(" ", "_").replace("-", "_")
        header_excludes_dob = category == "Date of Birth" and normalized_header in NON_DOB_DATE_HEADERS
        passed = mandatory_rate >= MANDATORY_COLUMN_THRESHOLD and not header_excludes_dob
        candidate = {
            "data_class": category,
            "mandatory_matches": mandatory,
            "mandatory_rate": round(mandatory_rate, 4),
            "supplemental_matches": supplemental,
            "supplemental_rate": round(supplemental_rate, 4),
            "accepted": passed,
        }
        result["candidates"].append(candidate)
        if passed:
            accepted.append((category, mandatory_rate, supplemental_rate))

    if not accepted:
        best = max(result["candidates"], key=lambda item: (item["mandatory_rate"], item["supplemental_rate"]))
        result["reason"] = (
            f"No category reached the {MANDATORY_COLUMN_THRESHOLD:.0%} mandatory-match threshold. "
            f"Closest: {best['data_class']} ({best['mandatory_rate']:.0%} mandatory matches)."
        )
        return result

    accepted.sort(key=lambda item: (item[1], item[2]), reverse=True)
    category, mandatory_rate, supplemental_rate = accepted[0]
    confidence = "High" if supplemental_rate >= 0.80 else "Medium"
    if len(values) < 3:
        confidence = "Low"
    result.update(
        data_class=category,
        confidence=confidence,
        reason=(
            f"{mandatory_rate:.0%} of non-empty values pass mandatory {category} checks; "
            f"{supplemental_rate:.0%} also pass the available supplemental checks. "
            f"Column threshold: {MANDATORY_COLUMN_THRESHOLD:.0%} mandatory matches."
        ),
    )
    return result


def read_csv(path, max_rows=100000):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    try:
        delimiter = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        headers = next(reader)
    except StopIteration:
        return [], []
    headers = [(name.strip() or f"column_{i + 1}") for i, name in enumerate(headers)]
    columns = [[] for _ in headers]
    for row_index, row in enumerate(reader):
        if max_rows and row_index >= max_rows:
            break
        if not row:
            continue
        for index in range(len(headers)):
            columns[index].append(row[index] if index < len(row) else "")
    return headers, columns


def ask_for_csv_path():
    print("\nWelcome to the Column Data Classifier!")
    print("This tool checks CSV columns for eight data categories.")
    print("Your CSV is read locally by this program; it is not uploaded.\n")
    while True:
        try:
            entered = input("Enter the path to your CSV file (or type 'q' to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return None
        if entered.lower() in {"q", "quit", "exit"}:
            print("Goodbye!")
            return None
        # Allow paths pasted from terminals that surround them with quotes.
        entered = entered.strip().strip('"').strip("'")
        if not entered:
            print("Please enter a file path. You can also drag the CSV file into this terminal.\n")
            continue
        path = Path(entered).expanduser()
        if not path.exists():
            print(f"Could not find: {path}. Check the path and try again.\n")
            continue
        if not path.is_file():
            print("That path is a folder, not a file. Please choose a CSV file.\n")
            continue
        if path.suffix.lower() != ".csv":
            print("That file does not have a .csv extension. Please choose a CSV file.\n")
            continue
        return path


def print_results(results, file_name, verbose=False):
    print("\n" + "=" * 64)
    print("                 COLUMN CLASSIFICATION RESULTS")
    print("=" * 64)
    print(f"File: {file_name}")
    print(f"Columns analyzed: {len(results)}")
    print("-" * 64)
    for item in results:
        confidence = f" ({item['confidence']} confidence)" if item["confidence"] else ""
        print(f"\n{item['column']}  ->  {item['data_class']}{confidence}")
        print(f"  {item['reason']}")
        if verbose:
            print("  Candidate checks:")
            for candidate in item["candidates"]:
                status = "matched" if candidate["accepted"] else "not matched"
                print(
                    f"    - {candidate['data_class']}: "
                    f"mandatory {candidate['mandatory_rate']:.0%}, "
                    f"supplemental {candidate['supplemental_rate']:.0%} ({status})"
                )
    print("\n" + "=" * 64)
    print("Done. Your original CSV file has not been modified.")
    print("=" * 64 + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classify CSV columns into eight data categories.")
    parser.add_argument("csv_path", nargs="?", help="path to a CSV file; omit it for interactive mode")
    parser.add_argument("--json", action="store_true", help="print JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="include per-category match rates")
    parser.add_argument("--max-rows", type=int, default=100000, help="inspect first N rows; 0 means all rows")
    args = parser.parse_args(argv)

    if args.max_rows < 0:
        parser.error("--max-rows must be zero or a positive integer")

    path = Path(args.csv_path).expanduser() if args.csv_path else ask_for_csv_path()
    if path is None:
        return
    if not path.exists() or not path.is_file():
        parser.error(f"CSV file not found or is not a file: {path}")
    if path.suffix.lower() != ".csv":
        parser.error("Input file must have a .csv extension")

    try:
        print(f"\nReading {path} ...")
        headers, columns = read_csv(path, args.max_rows)
        if not headers:
            print("The CSV file is empty or does not contain a header row.")
            return
        print(f"Analyzing {len(headers)} columns ...")
        resources = Resources()
        results = [classify_column(header, values, resources) for header, values in zip(headers, columns)]
    except (OSError, csv.Error) as exc:
        print(f"Could not read this CSV file: {exc}", file=sys.stderr)
        return

    if args.json:
        print(json.dumps({"file": str(path), "columns": results}, indent=2, default=str))
    else:
        print_results(results, path.name, args.verbose)


if __name__ == "__main__":
    main()
