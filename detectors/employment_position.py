"""Employment-position detector backed by an editable reference list."""
import re

def _normalize(value):
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

def detect(value, resources=None):
    if not isinstance(value, str) or value != value.strip() or not value:
        return False, {}
    positions = getattr(resources, "employment_positions", set())
    normalized = _normalize(value)
    matched = normalized in positions
    return matched, {"known_employment_position": matched}
