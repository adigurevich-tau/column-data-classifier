"""US state format detector with reference-list supplemental evidence."""
import re


_FORMAT = re.compile(r"^(?:[A-Za-z]{2}|[A-Za-z]+(?: [A-Za-z]+){0,2})$")


def detect(value, resources=None):
    """Check the state-name format and whether it matches a known US state."""
    if not isinstance(value, str) or value != value.strip():
        return False, {}
    normalized = re.sub(r"\s+", " ", value)
    if not _FORMAT.fullmatch(normalized):
        return False, {}
    states = getattr(resources, "us_states", set())
    known_us_state = normalized.casefold() in states
    return True, {"known_us_state": known_us_state}
