"""Phone number checks using general structural rules and US-format evidence."""
import re

_ALLOWED = re.compile(r"^\+?[0-9 ().-]+$")
_US_FORMAT = re.compile(
    r"^(?:\+?1[ .-]?)?(?:\([2-9]\d{2}\)|[2-9]\d{2})"
    r"[ .-]?[2-9]\d{2}[ .-]?\d{4}$"
)


def detect(value, resources=None):
    if isinstance(value, bool):
        return False, {}
    if isinstance(value, int):
        if value < 0:
            return False, {}
        value = str(value)
    if not isinstance(value, str) or not _ALLOWED.fullmatch(value):
        return False, {}
    # Date-shaped strings are not accepted as phone numbers.
    stripped = value.strip()
    if (
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped)
        or re.fullmatch(r"\d{4}-\d{2}-\d{4}", stripped)
        or re.fullmatch(r"\d{2}[/-]\d{2}[/-]\d{4}", stripped)
    ):
        return False, {}
    if value.count("+") > 1 or ("+" in value and not value.startswith("+")):
        return False, {}
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 15:
        return False, {}
    return True, {
        "digit_count": len(digits),
        "has_country_prefix": value.startswith("+"),
        "formatted_us_number": bool(_US_FORMAT.fullmatch(value.strip())),
    }
