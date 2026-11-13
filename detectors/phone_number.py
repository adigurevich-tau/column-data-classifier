"""Phone number checks using general structural rules and US-format evidence."""
import re

_ALLOWED = re.compile(r"^\\+?[0-9 ().-]+$")
_EXTENSION = re.compile(r"^(.*?)(?:\\s*(?:x|ext\\.?|extension)\\s*(\\d{1,6}))$", re.IGNORECASE)
_US_FORMAT = re.compile(
    r"^(?:\\+?1[ .-]?)?(?:\\([2-9]\\d{2}\\)|[2-9]\\d{2})"
    r"[ .-]?[2-9]\\d{2}[ .-]?\\d{4}$"
)


def detect(value, resources=None):
    if isinstance(value, bool):
        return False, {}
    if isinstance(value, int):
        if value < 0:
            return False, {}
        value = str(value)
    if not isinstance(value, str):
        return False, {}

    # Extensions are optional and are not counted as part of the main number.
    stripped = value.strip()
    extension_match = _EXTENSION.fullmatch(stripped)
    if extension_match:
        main_number, extension = extension_match.groups()
        if not extension or not main_number.strip():
            return False, {}
        has_extension = True
    else:
        main_number = stripped
        extension = ""
        has_extension = False

    main_number = main_number.strip()
    if not _ALLOWED.fullmatch(main_number):
        return False, {}

    # Date-shaped strings are not accepted as phone numbers.
    if (
        re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", main_number)
        or re.fullmatch(r"\\d{4}-\\d{2}-\\d{4}", main_number)
        or re.fullmatch(r"\\d{2}[/-]\\d{2}[/-]\\d{4}", main_number)
    ):
        return False, {}
    if main_number.count("+") > 1 or ("+" in main_number and not main_number.startswith("+")):
        return False, {}

    digits = re.sub(r"\\D", "", main_number)
    if not 7 <= len(digits) <= 15:
        return False, {}
    return True, {
        "digit_count": len(digits),
        "has_country_prefix": main_number.startswith("+") or main_number.startswith("00"),
        "formatted_us_number": bool(_US_FORMAT.fullmatch(main_number)),
        "has_extension": has_extension,
        "extension_digit_count": len(extension),
    }
