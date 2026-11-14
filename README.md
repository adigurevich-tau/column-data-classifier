# Sensitive-data column classifier

A deterministic, standard-library-only CSV column classifier. Each category has its
own detector module under `detectors/`; `main.py` runs the seven checks in a fixed order.

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
├── detectors/
│   ├── __init__.py
│   ├── ssn.py
│   ├── email.py
│   ├── phone_number.py
│   ├── date_of_birth.py
│   ├── city.py
│   ├── person_name.py
│   ├── us_state.py
├── report/
│   └── html_report.py
├── example_results/
│   ├── sample_output.txt
│   └── sample_employees_report.html
├── data/
│   ├── cities.txt
│   ├── first_names.txt
│   ├── surnames.txt
│   ├── us_states.txt
└── tests/
    ├── test_classify.py
```

## Detection order

1. US Social Security Number
2. Email Address
3. Phone Number
4. Date of Birth
5. US State
7. City
8. Person Name

City and Person Name intentionally run last because their patterns are broader.
The US State reference list can be edited in `data/us_states.txt`.

## HTML report

After each successful CSV analysis, the program creates a standalone HTML report
beside the input file. For example, `sample_employees.csv` produces
`sample_employees_report.html`. The report includes summary statistics, a card for
each column, confidence, match rates, and expandable candidate-check details.

For privacy, the HTML report does **not** include CSV cell values or sample records.
It contains column headers and aggregate classification information only. The
original CSV is not changed. The terminal results and optional `--json` output
continue to work as before.

The `example_results/` folder contains the terminal output and HTML report generated
for the included `sample_employees.csv` example.

Run all tests with:

```bash
python3 -m unittest discover -s tests -v
```

## Rules

Each detector enforces the agreed mandatory value-level checks. Reference lists and
format-specific hints are supplemental evidence; they do not replace mandatory checks.

- **SSN:** string or non-negative integer; exactly nine digits, either contiguous or in
  consistent 3-2-4 groups separated by hyphens/spaces; area not 000, 666, or 900-999;
  group not 00; serial not 0000. The 772 area ceiling is recorded only as supplemental
  evidence, not as a validity condition.
- **Email:** one @, non-empty local/domain parts, no leading/trailing/consecutive dots
  in the local part, no whitespace or invalid characters, and a domain with at least
  two non-empty labels. A valid-looking TLD is supplemental.
- **Phone:** string or non-negative integer; 7-15 digits after removing allowed spaces,
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
  lowercase, or title case. First-name and surname dictionaries, multiple name
  components, and city exclusion are supplemental signals.

## Column decision

The current configurable default is **95% mandatory matches** among non-empty values.
Supplemental match rates are reported separately and contribute to confidence; they do
not override a failed mandatory check. This threshold is an implementation default,
not a statistically calibrated value. Tune it against a labelled validation set before
using the classifier for consequential decisions.
