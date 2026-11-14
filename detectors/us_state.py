"""US state name and postal-abbreviation detector."""
import re

def detect(value, resources=None):
    if not isinstance(value, str) or value != value.strip():
        return False, {}
    normalized = re.sub(r"\s+", " ", value).casefold()
    states = getattr(resources, "us_states", set())
    return normalized in states, {"known_us_state": normalized in states}
