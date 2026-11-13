"""Date-of-birth parsing and plausibility checks."""
import datetime as dt
import re

_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y")
_YEAR4 = re.compile(r"^(?:\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{4}/\d{2}/\d{2}|\d{2}-\d{2}-\d{4})$")


def parse(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if not isinstance(value, str) or not _YEAR4.fullmatch(value):
        return None
    for fmt in _FORMATS:
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def detect(value, resources=None):
    parsed = parse(value)
    if parsed is None:
        return False, {}
    today = getattr(resources, "today", dt.date.today())
    age_years = (today - parsed).days / 365.2425
    return True, {"date": parsed, "age_years": age_years, "plausible_birth_age": 0 <= age_years <= 120}
