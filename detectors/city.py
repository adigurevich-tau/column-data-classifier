"""City value checks. The gazetteer is supplemental evidence."""
import re

_SHAPE = re.compile(r"^[A-Za-z][A-Za-z .']*$")


def _capitalization_ok(value):
    """Check whether text uses an accepted capitalization style."""
    return value.isupper() or value.islower() or value.istitle()


def detect(value, resources=None):
    """Check the basic city-name format and whether it appears in the city reference list."""
    if not isinstance(value, str) or value != value.strip():
        return False, {}
    text = value
    words = text.split()
    if len(text) < 2 or not 1 <= len(words) <= 4 or not _SHAPE.fullmatch(text) or not _capitalization_ok(text):
        return False, {}
    known = text.lower() in getattr(resources, "cities", set())
    return True, {"known_city": known}
