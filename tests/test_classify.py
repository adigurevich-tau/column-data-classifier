import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from detectors import ssn, email, phone_number, date_of_birth, city, person_name, us_state


class DetectorTests(unittest.TestCase):
    def setUp(self):
        """Create shared reference data with a fixed date for repeatable tests."""
        self.resources = main.Resources(today=dt.date(2026, 11, 12))

    def test_ssn_rules(self):
        """Verify mandatory SSN formatting and invalid-number rejection."""
        self.assertTrue(ssn.detect("123-45-6789", self.resources)[0])
        self.assertTrue(ssn.detect("123456789", self.resources)[0])
        for value in ("000-12-3456", "666-12-3456", "900-12-3456", "123-00-4567", "123-45-0000"):
            self.assertFalse(ssn.detect(value, self.resources)[0])
        self.assertFalse(ssn.detect(-123456789, self.resources)[0])

    def test_email_rules(self):
        """Verify accepted and rejected email address formats."""
        for value in ("a@b.com", "first.last@example.org", "x+y@domain.co.il"):
            self.assertTrue(email.detect(value, self.resources)[0])
        for value in ("@example.com", "a@","a..b@example.com", ".a@example.com",
                      "a.@example.com", "a b@example.com", "a@example..com", "a@example"):
            self.assertFalse(email.detect(value, self.resources)[0])

    def test_phone_rules(self):
        """Verify phone formats, extensions, and invalid-number rejection."""
        for value in ("123-456-7890", "+972 (50) 123-4567", "1234567", 1234567890):
            self.assertTrue(phone_number.detect(value, self.resources)[0])
        for value in ("857-790-7181x349", "331-892-8037x349", "001-795-896-4482x3819",
                      "857-790-7181 ext 349", "857-790-7181 extension 349"):
            self.assertTrue(phone_number.detect(value, self.resources)[0])
        self.assertTrue(phone_number.detect("857-790-7181x349", self.resources)[1]["has_extension"])
        for value in ("123456", "1234567890123456", "12+3456789", "++1234567", "123-ABC-7890",
                      "857-790-7181x", "857-790-7181x1234567", -1234567):
            self.assertFalse(phone_number.detect(value, self.resources)[0])

    def test_us_state_mandatory_format_and_supplemental_reference(self):
        """Verify state format checks and known-state supplemental evidence."""
        for value in ("California", "New York", "Rhode Island", "NY", "CA", "New  York"):
            passed, details = us_state.detect(value, self.resources)
            self.assertTrue(passed, value)
            self.assertTrue(details["known_us_state"], value)

        for value in ("XX", "New Zealand"):
            passed, details = us_state.detect(value, self.resources)
            self.assertTrue(passed, value)  # plausible format passes mandatory
            self.assertFalse(details["known_us_state"], value)  # not a US state

        for value in ("", "New York State 3", " New York", "New York "):
            self.assertFalse(us_state.detect(value, self.resources)[0], value)

    def test_dob_rules(self):
        """Verify supported date formats and invalid calendar-date rejection."""
        for value in ("1990-03-14", "14/03/1990", "03/14/1990", "14-03-1990"):
            self.assertTrue(date_of_birth.detect(value, self.resources)[0])
        for value in ("1990-02-30", "1990-13-01", "01/02/90", "2024-12-3100"):
            self.assertFalse(date_of_birth.detect(value, self.resources)[0])

    def test_city_rules(self):
        """Verify accepted city-name formats and invalid-value rejection."""
        for value in ("Tel Aviv", "NEW YORK", "paris", "St. Louis"):
            self.assertTrue(city.detect(value, self.resources)[0])
        for value in ("A", "New York 2", "New_York", "New York, NY", " New York "):
            self.assertFalse(city.detect(value, self.resources)[0])

    def test_person_name_rules(self):
        """Verify accepted person-name formats and placeholder rejection."""
        for value in ("Emily Carter", "JANE DOE", "john smith", "Anne-Marie O'Neil"):
            self.assertTrue(person_name.detect(value, self.resources)[0])
        self.assertTrue(person_name.detect("Burks, Rosella", self.resources)[0])
        self.assertTrue(person_name.detect("Smith, John", self.resources)[0])
        for value in ("Unknown", "Anonymous", "N/A", "Test User"):
            self.assertFalse(person_name.detect(value, self.resources)[0])
        for value in ("N/A", "A", "John  Smith", "John_ Smith",
                      "Burks,, Rosella", ", Rosella", "Burks, "):
            self.assertFalse(person_name.detect(value, self.resources)[0])

    def test_surname_first_column_classification(self):
        """Verify surname-first names can classify a column as Person Name."""
        result = main.classify_column(
            "person_name",
            ["Burks, Rosella", "Miller, Ava", "Davis, Noah"],
            self.resources,
        )
        self.assertEqual(result["data_class"], "Person Name")

    def test_column_threshold_and_order(self):
        """Verify email classification and detector ordering."""
        result = main.classify_column("email", ["a@example.com", "b@example.org", "c@example.net"], self.resources)
        self.assertEqual(result["data_class"], "Email Address")
        self.assertEqual([name for name, _ in main.DETECTORS][-2:], ["City", "Person Name"])


if __name__ == "__main__":
    unittest.main()
