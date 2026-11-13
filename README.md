# Sensitive-data column classifier

A deterministic, standard-library-only CSV column classifier. Each category has its
own detector module under `detectors/`; `main.py` runs the checks in a fixed order.

## Quick start

Clone the repository and enter the project folder:

```bash
git clone https://github.com/adigurevich-tau/column-data-classifier.git
cd column-data-classifier
```

Run the interactive program:

```bash
python main.py
```

If your system uses `python3` instead:

```bash
python3 main.py
```

The program welcomes you and asks for the path to your CSV file. You can type the
path or drag the file into the terminal. The CSV is read locally and is not uploaded
or modified.

You can also provide the path directly:

```bash
python main.py sample_employees.csv
python main.py sample_employees.csv --verbose
python main.py sample_employees.csv --json
```

Run the tests with:

```bash
python tests/test_classify.py
```

No third-party packages are required.

## Project layout

```text
.
├── main.py
├── classify.py
├── detectors/
│   ├── __init__.py
│   ├── ssn.py
│   ├── email.py
│   ├── phone_number.py
│   ├── date_of_birth.py
│   ├── city.py
│   └── person_name.py
├── data/
│   ├── cities.txt
│   ├── first_names.txt
│   └── surnames.txt
└── tests/
    └── test_classify.py
```

## Detection order

1. US Social Security Number
2. Email
3. Phone Number
4. Date of Birth
5. City
6. Person Name

City and Person Name intentionally run last.

## Rules

Each detector enforces the agreed mandatory value-level checks. Reference lists and
format-specific hints are supplemental evidence; they do not replace mandatory checks.

- **SSN:** string or unsigned integer; exactly nine digits, either contiguous or in
  consistent 3-2-4 groups separated by hyphens/spaces; area not 000, 666, or 900-999;
  group not 00; serial not 0000. The 772 area ceiling is recorded only as supplemental
  evidence, not as a validity condition.
- **Email:** one @, non-empty local/domain parts, no leading/trailing/consecutive dots
  in the local part, no whitespace or invalid characters, and a domain with at least
  two non-empty labels. A valid-looking TLD is supplemental.
- **Phone:** string or unsigned integer; 7-15 digits after removing allowed spaces,
  hyphens, and parentheses; optional plus only at the beginning; no other characters.
  Country-specific numbering checks are supplemental and are not fully implemented.
- **Date of Birth:** string/date/datetime in one of the agreed four-digit-year formats;
  real calendar date with valid month/day components. A plausible age (0-120) is
  supplemental evidence.
- **City:** 1-4 words, starts with a letter, at least two characters, letters/spaces/
  periods/apostrophes only, and all uppercase, all lowercase, or title case. The city
  gazetteer is supplemental evidence.
- **Person Name:** 1-5 words, at least two characters, letters/spaces/hyphens/
  apostrophes/periods only, no leading/trailing/repeated spaces, consistent uppercase,
  lowercase, or title case, and not a known placeholder. First-name and surname
  dictionaries, multiple name components, city exclusion, and generic/job-title
  exclusions are supplemental signals.

## Column decision

The current configurable default is **95% mandatory matches** among non-empty values.
Supplemental match rates are reported separately and contribute to confidence; they do
not override a failed mandatory check. This threshold is an implementation default,
not a statistically calibrated value. Tune it against a labelled validation set before
using the classifier for consequential decisions.
