# Column Data Classifier

A Python tool that analyzes CSV columns and classifies them into seven data categories:

- National ID (US SSN)
- Email Address
- Phone Number
- Date of Birth
- US State
- City
- Person Name

The classifier uses mandatory format checks and supplemental evidence from reference files. A column is classified only when it meets the configured match thresholds.

## Run

No third-party packages are required.

```bash
git clone https://github.com/adigurevich-tau/column-data-classifier.git
cd column-data-classifier
python3 main.py
```

The program asks for a CSV file path. You can also pass the path directly:

```bash
python3 main.py sample_employees.csv
```

Optional arguments:

- `--verbose` — show match rates for each candidate category.
- `--json` — print results as JSON.
- `--max-rows N` — analyze the first N rows; use `0` to analyze all rows.

## Results

The program prints the classification results and creates an HTML report next to the input CSV. For example, `sample_employees.csv` produces `sample_employees_report.html`.

The HTML report contains column names and classification statistics, not CSV cell values. The CSV is read locally and is not modified or uploaded.

The `example_results/` folder contains sample terminal output and the HTML report for the employees example.

## Tests

Run the test suite from the project directory:

```bash
python3 -m unittest discover -s tests -v
```

## Project files

- `main.py` — command-line application and classification logic.
- `detectors/` — the seven category detectors.
- `data/` — supplemental reference lists for cities, names, and US states.
- `report/` — HTML report generator.
- `example_results/` — example terminal and HTML results.
- `tests/` — automated tests.

