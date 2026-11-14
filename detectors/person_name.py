"""Person-name value checks. Name/city gazetteers add supplemental evidence."""
import re

_ALLOWED = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")
_PLACEHOLDERS = {"unknown", "anonymous", "n/a", "test user"}


def detect(value, resources=None):
    """Check person-name structure and collect name-reference evidence."""
    if not isinstance(value, str):
        return False, {}
    text = value.strip()
    if text.lower() in _PLACEHOLDERS or len(text) < 2:
        return False, {}
    if text != value or "  " in text or text.startswith(" ") or text.endswith(" "):
        return False, {}

    surname_first = "," in text
    if surname_first:
        if text.count(",") != 1:
            return False, {}
        surname, given = (part.strip() for part in text.split(",", 1))
        if not surname or not given or not _ALLOWED.fullmatch(surname) or not _ALLOWED.fullmatch(given):
            return False, {}
        words = surname.split() + given.split()
        if not 2 <= len(words) <= 5:
            return False, {}
        if not all(part.istitle() or part.isupper() or part.islower() for part in (surname, given)):
            return False, {}
        first_word = given.split()[0]
        last_word = surname.split()[-1]
    else:
        if not _ALLOWED.fullmatch(text):
            return False, {}
        words = text.split(" ")
        if not 1 <= len(words) <= 5 or not (text.isupper() or text.islower() or text.istitle()):
            return False, {}
        first_word = words[0]
        last_word = words[-1]

    normalized = text.lower()
    if normalized in getattr(resources, "cities", set()):
        return False, {}
    first_names = getattr(resources, "first_names", set())
    surnames = getattr(resources, "surnames", set())
    known_first = first_word.lower() in first_names
    known_last = last_word.lower() in surnames
    return True, {
        "known_first_name": known_first,
        "known_last_name": known_last,
        "known_name_components": known_first and known_last,
        "surname_first_format": surname_first,
    }
