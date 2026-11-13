import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from detectors import ssn, email, phone_number, date_of_birth, city, person_name


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.resources = main.Resources(today=dt.date(2026, 11, 12))

    def test_ssn_rules(self):
        self.assertTrue(ssn.detect("123-45-6789", self.resources)[0])
        self.assertTrue(ssn.detect("123456789", self.resources)[0])
        for value in ("000-12-3456", "666-12-3456", "900-12-3456", "123-00-4567", "123-45-0000"):
            self.assertFalse(ssn.detect(value, self.resources)[0])
        self.assertFalse(ssn.detect(-123456789, self.resources)[0])

    def test_email_rules(self):
        for value in ("a@b.com", "first.last@example.org", "x+y@domain.co.il"):
            self.assertTrue(email.detect(value, self.resources)[0])
        for value in ("@example.com", "a@","a..b@example.com", ".a@example.com",
                      "a.@example.com", "a b@example.com", "a@example..com", "a@example"):
            self.assertFalse(email.detect(value, self.resources)[0])

    def test_phone_rules(self):
        for value in ("123-456-7890", "+972 (50) 123-4567", "1234567", 1234567890):
            self.assertTrue(phone_number.detect(value, self.resources)[0])
        for value in ("123456", "1234567890123456", "12+3456789", "++1234567", "123-ABC-7890", -1234567):
            self.assertFalse(phone_number.detect(value, self.resources)[0])

    def test_dob_rules(self):
        for value in ("1990-03-14", "14/03/1990", "03/14/1990", "14-03-1990"):
            self.assertTrue(date_of_birth.detect(value, self.resources)[0])
        for value in ("1990-02-30", "1990-13-01", "01/02/90", "2024-12-3100"):
            self.assertFalse(date_of_birth.detect(value, self.resources)[0])

    def test_city_rules(self):
        for value in ("Tel Aviv", "NEW YORK", "paris", "St. Louis"):
            self.assertTrue(city.detect(value, self.resources)[0])
        for value in ("A", "New York 2", "New_York", "New York, NY", " New York "):
            self.assertFalse(city.detect(value, self.resources)[0])

    def test_person_name_rules(self):
        for value in ("Emily Carter", "JANE DOE", "john smith", "Anne-Marie O'Neil"):
            self.assertTrue(person_name.detect(value, self.resources)[0])
        for value in ("Unknown", "Anonymous", "N/A", "Test User", "A", "John  Smith", "John_ Smith"):
            self.assertFalse(person_name.detect(value, self.resources)[0])

    def test_column_threshold_and_order(self):
        result = main.classify_column("email", ["a@example.com", "b@example.org", "c@example.net"], self.resources)
        self.assertEqual(result["data_class"], "Email Address")
        self.assertEqual([name for name, _ in main.DETECTORS][-2:], ["City", "Person Name"])


if __name__ == "__main__":
    unittest.main()
