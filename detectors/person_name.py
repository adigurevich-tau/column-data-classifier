"""Person-name value checks. Name/city gazetteers add supplemental evidence."""
import re

_ALLOWED = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")
_PLACEHOLDERS = {"unknown", "anonymous", "n/a", "test user"}


def detect(value, resources=None):
    if not isinstance(value, str):
        return False, {}
    text = value.strip()
    if text.lower() in _PLACEHOLDERS or len(text) < 2 or not _ALLOWED.fullmatch(text):
        return False, {}
    if text != value or "  " in text or text.startswith(" ") or text.endswith(" "):
        return False, {}
    words = text.split(" ")
    if not 1 <= len(words) <= 5 or not (text.isupper() or text.islower() or text.istitle()):
        return False, {}
    normalized = text.lower()
    if normalized in getattr(resources, "cities", set()):
        return False, {}
    first_names = getattr(resources, "first_names", set())
    surnames = getattr(resources, "surnames", set())
    known_first = words[0].lower() in first_names
    known_last = words[-1].lower() in surnames
    return True, {"known_first_name": known_first, "known_last_name": known_last,
                  "known_name_components": known_first and known_last}
