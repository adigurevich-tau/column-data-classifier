import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report.html_report import render_report, write_report


class HtmlReportTests(unittest.TestCase):
    def test_report_contains_summary_and_no_cell_values(self):
        results = [{
            "column": "email",
            "data_class": "Email Address",
            "confidence": "High",
            "rows_non_empty": 3,
            "reason": "All values passed the email checks.",
            "candidates": [{
                "data_class": "Email Address",
                "mandatory_rate": 1.0,
                "supplemental_rate": 1.0,
                "accepted": True,
            }],
        }]
        html = render_report(results, "employees.csv", 3)
        self.assertIn("Column classification report", html)
        self.assertIn("Email Address", html)
        self.assertIn("100%", html)
        self.assertIn("does not include CSV cell values", html)
        self.assertNotIn("alice@example.com", html)

    def test_report_filename_uses_csv_stem(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / "sample_employees.csv"
            csv_path.write_text("email\na@example.com\n", encoding="utf-8")
            report_path = write_report([], csv_path, 1)
            self.assertEqual(report_path.name, "sample_employees_report.html")
            self.assertTrue(report_path.exists())


if __name__ == "__main__":
    unittest.main()
