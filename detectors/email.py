"""Email address syntax checks based on the agreed mandatory rules."""
import re

_LOCAL_ALLOWED = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~%-]+$")
_DOMAIN_ALLOWED = re.compile(r"^[A-Za-z0-9.-]+$")


def detect(value, resources=None):
    """Check whether a value follows the mandatory email syntax rules."""
    if not isinstance(value, str) or value.count("@") != 1 or any(ch.isspace() for ch in value):
        return False, {}
    local, domain = value.split("@")
    if not local or not domain or local.startswith(".") or local.endswith(".") or ".." in local:
        return False, {}
    if not _LOCAL_ALLOWED.fullmatch(local) or not _DOMAIN_ALLOWED.fullmatch(domain):
        return False, {}
    labels = domain.split(".")
    if len(labels) < 2 or any(not label for label in labels):
        return False, {}
    if any(label.startswith("-") or label.endswith("-") for label in labels):
        return False, {}
    # TLD appearance is supplemental; a syntactically valid domain is enough for mandatory acceptance.
    tld = labels[-1]
    return True, {"valid_looking_tld": bool(re.fullmatch(r"[A-Za-z]{2,}", tld))}
