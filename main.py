#!/usr/bin/env python3
"""Run the six column detectors and classify CSV columns.

Usage:
    python main.py file.csv
    python main.py file.csv --json
    python main.py file.csv --verbose

All detectors validate individual values. A column is classified when at least
95% of its non-empty values pass that category's mandatory checks. Supplemental
evidence is reported separately and never silently replaces mandatory checks.
City and person-name detectors deliberately run last.
"""
import argparse
import csv
import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

from detectors import ssn, email, phone_number, date_of_birth, city, person_name

DATA_DIR = Path(__file__).resolve().parent / "data"
MANDATORY_COLUMN_THRESHOLD = 0.95
NULL_VALUES = {"", "null", "none", "n/a", "na", "nan", "nil", "-", "--", "?", "undefined", "unknown"}

# Execution order requested: City and Person Name are last.
DETECTORS = [
    ("National ID (US SSN)", ssn.detect),
    ("Email Address", email.detect),
    ("Phone Number", phone_number.detect),
    ("Date of Birth", date_of_birth.detect),
    ("City", city.detect),
    ("Person Name", person_name.detect),
]


class Resources:
    """Optional reference data used only as supplemental evidence."""

    def __init__(self, today=None):
        self.today = today or dt.date.today()
        self.cities = self._load_set("cities.txt")
        self.first_names = self._load_set("first_names.txt")
        self.surnames = self._load_set("surnames.txt")

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


def supplemental_result(category, value, details, resources):
    """Return whether optional evidence supports a mandatory match."""
    if category == "National ID (US SSN)":
        return bool(details.get("formatted") or details.get("area_at_or_below_772"))
    if category == "Email Address":
        return bool(details.get("valid_looking_tld"))
    if category == "Phone Number":
        # Country-specific numbering validation is not implemented in this lightweight version.
        return bool(details.get("has_country_prefix"))
    if category == "Date of Birth":
        return bool(details.get("plausible_birth_age"))
    if category == "City":
        return bool(details.get("known_city"))
    if category == "Person Name":
        # Supplemental name evidence: recognized first and last names, with city exclusion
        # already applied by the detector.
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
                if supplemental_result(category, value, details, resources):
                    supplemental += 1
        mandatory_rate = mandatory / len(values)
        supplemental_rate = supplemental / len(values)
        passed = mandatory_rate >= MANDATORY_COLUMN_THRESHOLD
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

    # Prefer the category with the strongest mandatory match rate, then supplemental evidence.
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
    headers = [(name.strip() or f"column_{i}") for i, name in enumerate(headers)]
    columns = [[] for _ in headers]
    for row_index, row in enumerate(reader):
        if max_rows and row_index >= max_rows:
            break
        if not row:
            continue
        for index in range(len(headers)):
            columns[index].append(row[index] if index < len(row) else "")
    return headers, columns


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classify CSV columns into six data categories.")
    parser.add_argument("csv_path")
    parser.add_argument("--json", action="store_true", help="print JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="include per-category match rates")
    parser.add_argument("--max-rows", type=int, default=100000, help="inspect first N rows; 0 means all rows")
    args = parser.parse_args(argv)

    headers, columns = read_csv(args.csv_path, args.max_rows)
    resources = Resources()
    results = [classify_column(header, values, resources) for header, values in zip(headers, columns)]

    if args.json:
        print(json.dumps({"file": args.csv_path, "columns": results}, indent=2, default=str))
    else:
        for item in results:
            print(f"Column {item['column']!r} -> {item['data_class']}"
                  + (f" [{item['confidence']} confidence]" if item["confidence"] else ""))
            print(f"  {item['reason']}")
            if args.verbose:
                for candidate in item["candidates"]:
                    print(
                        f"  - {candidate['data_class']}: mandatory={candidate['mandatory_rate']:.0%}, "
                        f"supplemental={candidate['supplemental_rate']:.0%}, "
                        f"accepted={candidate['accepted']}"
                    )


if __name__ == "__main__":
    main()
