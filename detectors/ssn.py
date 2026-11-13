"""US Social Security number checks."""
import re

_PATTERN = re.compile(r"^(?P<area>\\d{3})(?P<sep>[- ]?)(?P<group>\\d{2})(?P=sep)(?P<serial>\\d{4})$")


def detect(value, resources=None):
    if isinstance(value, bool):
        return False, {}
    if isinstance(value, int):
        if value < 0:
            return False, {}
        value = str(value)
    if not isinstance(value, str):
        return False, {}
    match = _PATTERN.fullmatch(value)
    if not match:
        return False, {}
    area, group, serial = match.group("area", "group", "serial")
    if area in {"000", "666"} or area.startswith("9") or group == "00" or serial == "0000":
        return False, {}
    # Allocation-area ceiling is retained only as supplemental evidence, not a validity rule.
    return True, {"formatted": bool(match.group("sep")), "area_at_or_below_772": int(area) <= 772}
