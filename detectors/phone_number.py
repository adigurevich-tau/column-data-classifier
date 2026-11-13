"""Phone number checks using the agreed general structural rules."""
import re

_ALLOWED = re.compile(r"^\\+?[0-9 ()-]+$")


def detect(value, resources=None):
    if isinstance(value, bool):
        return False, {}
    if isinstance(value, int):
        if value < 0:
            return False, {}
        value = str(value)
    if not isinstance(value, str) or not _ALLOWED.fullmatch(value):
        return False, {}
    if value.count("+") > 1 or ("+" in value and not value.startswith("+")):
        return False, {}
    digits = re.sub(r"\\D", "", value)
    if not 7 <= len(digits) <= 15:
        return False, {}
    return True, {"digit_count": len(digits), "has_country_prefix": value.startswith("+")}
