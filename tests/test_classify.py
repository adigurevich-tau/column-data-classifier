import sys, unittest, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import classify as C

RES = C.Resources(today=dt.date(2026, 11, 12))
SSN, CITY, NAME, PHONE, EMAIL, DOB, NC = ("National ID (US SSN)", "City", "Person Name", "Phone Number",
                                          "Email Address", "Date of Birth", C.NOT_CLASSIFIED)

CASES = [
    # (header, values, expected)
    ("ssn", ["123-45-6781", "234-56-7892", "345-67-8903"], SSN),
    ("social_security_number", ["123456781", "234567892", "345678903"], SSN),       # bare digits + header
    ("employee_number", ["123456781", "234567892", "345678903"], NC),               # bare digits, no header
    ("tax_ref", ["123-45-6781", "234 56 7892", "345-67-8903"], SSN),                # separators alone are enough
    ("ssn", ["000-12-3456", "666-12-3456", "900-12-3456"], NC),                     # invalid SSNs
    ("phone", ["(212) 555-0101", "415-555-0112", "+1 512 555 0123"], PHONE),
    ("contact", ["+44 20 7946 0958", "+972 3 123 4567", "+49 30 1234567"], PHONE),
    ("mobile", ["0501234567", "0529876543", "0541112222"], PHONE),                 # bare local number + header
    ("zip", ["10001", "94105", "73301"], NC),
    ("amount", ["2125550101", "4155550112", "5125550123"], NC),                     # 10 digits, no header -> too ambiguous
    ("email", ["a@b.com", "First.Last@Corp.co.uk", "x+y@z.io"], EMAIL),
    ("email", ["a@b.com", "not an email", "also bad"], NC),
    ("notes", ["write to a@b.com", "call me", "ok"], NC),
    ("dob", ["1990-03-14", "1985-07-01", "1993-11-23"], DOB),
    ("birth_date", ["03/14/1990", "07/01/1985", "11/23/1993"], DOB),
    ("dob", ["14 Mar 1990", "1 Jul 1985", "March 3, 1970"], DOB),
    ("col7", ["1990-03-14", "1985-07-01", "1971-11-23", "1962-05-05"], DOB),         # no hint, plausible ages
    ("start_date", ["2022-01-02", "2021-06-15", "2023-03-20"], NC),
    ("hire_date", ["1990-03-14", "1985-07-01", "1971-11-23"], NC),                  # header says other date
    ("created_at", ["2024-01-02 10:00:00", "2024-02-02 11:30:00"], NC),
    ("dob", ["2024-12-3100", "1113-12-2443", "2022-08-1201"], NC),                  # impossible dates
    ("dob", ["2031-01-01", "2040-05-05", "2050-02-02"], NC),                        # future
    ("city", ["New York", "San Francisco", "Austin"], CITY),
    ("location", ["Paris", "Tel Aviv", "Berlin", "Tokyo"], CITY),
    ("city", ["Zzyzx", "Smallville", "Ogdenburg"], CITY),                           # unknown towns, header + shape (Low)
    ("place", ["Zzyzx", "Smallville", "Ogdenburg"], NC),                            # same values, no header
    ("state", ["NY", "CA", "TX", "MA"], NC),
    ("full_name", ["Emily Carter", "Jason Lee", "Maria Gonzalez"], NAME),
    ("contact", ["Carter, Emily", "Dr. Jason Lee Jr.", "Maria Gonzalez"], NAME),
    ("first_name", ["Emily", "Jason", "Oluwaseun"], NAME),
    ("name", ["Oluwaseun Adeyemi", "Zxcvb Qwerty"], NAME),                         # unseen names + header
    ("x", ["Oluwaseun Adeyemi", "Zxcvb Qwerty"], NC),                              # ...without header: not claimed
    ("title", ["Data Analyst", "Sales Engineer", "Product Manager"], NC),
    ("company_name", ["Acme Inc", "Globex Corp", "Initech LLC"], NC),
    ("x", ["San Diego", "Salt Lake City", "New York"], CITY),                       # multiword cities not names
    ("gender", ["F", "M", "Female"], NC),
    ("empty", ["", "", "N/A"], NC),
]


class T(unittest.TestCase):
    def test_cases(self):
        for header, values, expected in CASES:
            with self.subTest(header=header, values=values):
                r = C.classify_column(header, values, RES)
                self.assertEqual(r["data_class"], expected, r["reason"])

    def test_reason_present(self):
        r = C.classify_column("email", ["a@b.com"], RES)
        self.assertIn("1 of 1", r["reason"])

    def test_ssn_examples_masked(self):
        r = C.classify_column("ssn", ["123-45-6781"], RES)
        self.assertEqual(r["examples"], ["***-**-6781"])

    def test_junk_tolerance_threshold(self):
        vals = ["a%d@b.com" % i for i in range(19)] + ["junk"]
        self.assertEqual(C.classify_column("c", vals, RES)["data_class"], EMAIL)   # 95% >= 90%
        vals = ["a%d@b.com" % i for i in range(7)] + ["junk"] * 3
        self.assertEqual(C.classify_column("c", vals, RES)["data_class"], NC)      # 70% < 90%, no hint


if __name__ == "__main__":
    unittest.main()
