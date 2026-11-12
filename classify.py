#!/usr/bin/env python3
"""
classify.py - rule-based, explainable sensitive-data classifier for CSV columns.

Usage:
    python classify.py file.csv            # human-readable report
    python classify.py file.csv --json     # machine-readable
    python classify.py file.csv -v         # also show every candidate class and why it lost

Design (see NOTE.md for the longer version)
-------------------------------------------
For every column we run one detector per data class over the non-empty values.
A detector gives each value a level:
    STRONG - value fits the class and passes validity checks (e.g. a valid SSN, a known city)
    WEAK   - value has the right *shape* but is ambiguous on its own (9 bare digits, an unknown
             capitalised word). WEAK matches are only counted when the column header also
             points at the class.
    NO     - value does not fit.
The column-level decision is a small, fixed rule table over two numbers:
    s = share of values that are STRONG        w = share that are STRONG or WEAK
and one boolean: does the header name hint at the class?
    no header hint : classify if s >= class threshold (0.80 - 0.90)
    header hint    : classify if s >= 0.60, or (shape-only) w >= 0.80  -> Low confidence
A header hint alone never classifies a column; the values must agree.
Everything is deterministic and every decision prints the counts that produced it.
No network, no ML, standard library only.  Gazetteers live in data/*.txt (editable, no code change).
"""
import argparse
import csv
import datetime as dt
import io
import json
import re
import statistics
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
NO, WEAK, STRONG = 0, 1, 2
NULL_VALUES = {"", "null", "none", "n/a", "na", "nan", "nil", "-", "--", "?", "undefined", "unknown"}
NOT_CLASSIFIED = "Not classified"


# --------------------------------------------------------------------------- resources
def load_set(filename):
    path = DATA_DIR / filename
    out = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("#"):
                continue
            out.update(x.strip().lower() for x in line.split(",") if x.strip())
    return out


class Resources:
    def __init__(self, today=None):
        self.cities = load_set("cities.txt")
        self.first_names = load_set("first_names.txt")
        self.surnames = load_set("surnames.txt")
        self.today = today or dt.date.today()


TITLES = {"mr", "mrs", "ms", "miss", "mx", "dr", "prof", "sir", "madam", "mister"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "esq", "dds"}
# Words that make a multi-word value much more likely to be a job title / department / etc. than a person.
NON_NAME_WORDS = {
    "manager", "engineer", "analyst", "director", "officer", "developer", "designer", "specialist",
    "consultant", "coordinator", "assistant", "associate", "administrator", "architect", "scientist",
    "executive", "supervisor", "technician", "representative", "sales", "marketing", "finance",
    "support", "operations", "department", "team", "inc", "llc", "ltd", "corp", "company", "street",
    "avenue", "road", "university", "bank", "hospital", "department",
}


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


# --------------------------------------------------------------------------- value detectors
# Each returns (level, aux). aux is extra info used by column checks (only DOB uses it).
SSN_RE = re.compile(r"^(\d{3})([- ]?)(\d{2})\2(\d{4})$")


def det_ssn(v, res):
    m = SSN_RE.match(v)
    if not m:
        return NO, None
    area, sep, group, serial = m.group(1), m.group(2), m.group(3), m.group(4)
    # SSA rules: area not 000/666/9xx, group not 00, serial not 0000
    if area in ("000", "666") or area[0] == "9" or group == "00" or serial == "0000":
        return NO, None
    return (STRONG if sep else WEAK), None  # 9 bare digits could be any ID -> needs header hint


NANP_RE = re.compile(
    r"^(?:\+?1[\s.\-]?)?(?:\((\d{3})\)|(\d{3}))([\s.\-]?)(\d{3})([\s.\-]?)(\d{4})(?:\s*(?:x|ext\.?)\s*\d{1,6})?$", re.I)
INTL_RE = re.compile(r"^\+\d{1,3}[\s.\-]?(?:\(?\d{1,4}\)?[\s.\-]?){1,5}\d$")
TRUNK0_RE = re.compile(r"^0\d{1,2}([\s.\-]?)\d{3}[\s.\-]?\d{3,4}$")  # e.g. 050-123-4567, 03-123-4567


def det_phone(v, res):
    m = NANP_RE.match(v)
    if m:
        area = m.group(1) or m.group(2)
        exchange = m.group(4)
        if area[0] in "23456789" and exchange[0] in "23456789":
            formatted = bool(m.group(1)) or bool(m.group(3)) or bool(m.group(5)) or v.startswith("+")
            return (STRONG if formatted else WEAK), None
        # invalid NANP area/exchange: fall through to the other phone formats
    if v.startswith("+") and INTL_RE.match(v) and 8 <= len(re.sub(r"\D", "", v)) <= 15:
        return STRONG, None
    m = TRUNK0_RE.match(v)
    if m:
        return (STRONG if m.group(1) or re.search(r"[\s.\-]", v) else WEAK), None
    return NO, None


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


def det_email(v, res):
    return (STRONG if EMAIL_RE.match(v) and ".." not in v else NO), None


DATE_FMT_STRONG = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y",
                   "%d.%m.%Y", "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"]
DATE_FMT_WEAK = ["%m/%d/%y", "%d/%m/%y", "%m-%d-%y", "%d-%m-%y", "%d.%m.%y", "%Y%m%d"]  # 2-digit year / bare digits
ISO_DT_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ]\d{1,2}:\d{2}")


def parse_date(v):
    """Return (date, is_strong_format) for the first format that parses cleanly, else (None, False)."""
    m = ISO_DT_RE.match(v)
    if m:
        v = m.group(1)
    for fmts, strong in ((DATE_FMT_STRONG, True), (DATE_FMT_WEAK, False)):
        for f in fmts:
            try:
                return dt.datetime.strptime(v, f).date(), strong
            except ValueError:
                continue
    return None, False


def det_dob(v, res):
    d, strong = parse_date(v)
    if d is None:
        return NO, None
    age = (res.today - d).days / 365.25
    if not (0 <= age <= 120):
        return NO, None  # future dates / year 1113 / 'born 1800s' are not plausible birth dates
    return (STRONG if strong else WEAK), age


CITY_SHAPE = re.compile(r"^[A-Za-z][A-Za-z.'’\- ]{2,40}$")


def det_city(v, res):
    base = v.strip()
    if "," in base:  # "Austin, TX" / "Paris, France"
        head, tail = [p.strip() for p in base.split(",", 1)]
        if re.fullmatch(r"[A-Za-z .]{2,25}", tail):
            base = head
    if norm(base) in res.cities:
        return STRONG, None
    words = base.split()
    if CITY_SHAPE.match(base) and 1 <= len(words) <= 4 and base[0].isupper() and not (len(base) <= 2):
        return WEAK, None  # looks like a place name but we don't know it
    return NO, None


NAME_TOKEN = re.compile(r"^[A-Za-z][A-Za-z'’\-.]*$")


def det_name(v, res):
    s = v.strip()
    if len(s) > 60 or any(c.isdigit() for c in s) or "@" in s or "_" in s:
        return NO, None
    if " " in s and norm(s) in res.cities:
        return NO, None  # "San Diego", "Salt Lake City" are cities, not people
    if s.count(",") == 1:  # "Carter, Emily"
        last, first = [p.strip() for p in s.split(",")]
        s = f"{first} {last}"
    elif "," in s:
        return NO, None
    toks = s.split()
    while toks and toks[0].lower().rstrip(".") in TITLES:
        toks = toks[1:]
    while toks and toks[-1].lower().rstrip(".") in SUFFIXES:
        toks = toks[:-1]
    if not 1 <= len(toks) <= 4 or not all(NAME_TOKEN.match(t) for t in toks):
        return NO, None
    low = [t.lower().strip(".") for t in toks]
    if any(t in NON_NAME_WORDS for t in low):
        return NO, None
    known_first = low[0] in res.first_names
    known_last = low[-1] in res.surnames
    titlecase = all(t[0].isupper() for t in toks)
    if len(toks) == 1:
        if len(low[0]) < 3:
            return NO, None  # state codes / initials such as 'MA', 'LI'
        if low[0] in res.cities:
            return WEAK, None  # 'Austin', 'Jordan', 'Victoria' - ambiguous alone
        if known_first or known_last:
            return STRONG, None
        return (WEAK if titlecase else NO), None
    if known_first or known_last:
        return STRONG, None
    return (WEAK if titlecase else NO), None  # e.g. unseen name: right shape, unknown words


# --------------------------------------------------------------------------- header hints
def header_tokens(h):
    h = re.sub(r"([a-z])([A-Z])", r"\1 \2", h)
    toks = [t for t in re.split(r"[^A-Za-z0-9]+", h.lower()) if t]
    return toks, "".join(toks)


def hint_ssn(t, j):
    return "ssn" in t or any(k in j for k in ("socialsecurity", "socsec", "nationalid", "taxpayerid"))


def hint_phone(t, j):
    return bool(set(t) & {"phone", "tel", "telephone", "mobile", "cell", "cellphone", "fax", "msisdn"}) or "phone" in j


def hint_email(t, j):
    return "mail" in t or "email" in j


def hint_dob(t, j):
    return bool(set(t) & {"dob", "bday", "birthday", "birthdate", "born"}) or "birth" in j


def hint_city(t, j):
    return bool(set(t) & {"city", "town", "municipality", "locality"})


NEG_NAME = {"company", "user", "username", "file", "product", "department", "dept", "city", "state", "street",
            "title", "org", "organization", "account", "bank", "school", "brand", "project", "team", "host",
            "domain", "table", "column", "device", "model", "country", "county", "region", "role", "job"}


def hint_name(t, j):
    if set(t) & NEG_NAME:
        return False
    return bool(set(t) & {"name", "fullname", "firstname", "lastname", "surname", "fname", "lname",
                          "forename", "givenname", "familyname"}) or any(k in j for k in ("fullname", "firstname", "lastname"))


DOB_NEG_TOKENS = {"start", "hire", "hired", "created", "updated", "modified", "end", "join", "joined", "expiry",
                  "expires", "expire", "due", "order", "signup", "registration", "login", "last", "issued",
                  "issue", "effective", "termination", "closed", "opened", "purchase", "transaction",
                  "event", "timestamp", "ts", "at", "date"}


def dob_column_check(header_toks, aux, n):
    """Used only when the header does NOT mention birth: dates alone are not enough, they must look like birthdays."""
    neg = set(header_toks) & DOB_NEG_TOKENS
    if neg - {"date"}:
        return False, f'header word(s) {sorted(neg - {"date"})} indicate a different kind of date'
    ages = [a for a in aux if a is not None]
    if not ages:
        return False, "no valid dates"
    adult = sum(1 for a in ages if 18 <= a <= 100) / n
    spread = statistics.pstdev([dt_year for dt_year in ages]) if len(ages) > 1 else 0
    if adult < 0.9:
        return False, (f"only {adult:.0%} of the dates imply an age of 18-100 "
                       f"(median implied age {statistics.median(ages):.0f}); not a plausible birth-date column")
    if spread < 5:
        return False, f"implied ages vary by only {spread:.1f} years; birth dates usually spread wider"
    return True, "implied ages are plausible for birth dates (18-100, spread %.0f years)" % spread


# --------------------------------------------------------------------------- class table
CLASSES = [
    dict(name="National ID (US SSN)", detect=det_ssn, hint=hint_ssn, thr=0.90,
         desc="are valid SSNs (NNN-NN-NNNN; area not 000/666/9xx, group not 00, serial not 0000)",
         weak_desc="9 bare digits that pass SSN validity rules", mask=True),
    dict(name="Email Address", detect=det_email, hint=hint_email, thr=0.90,
         desc="are syntactically valid email addresses", weak_desc=""),
    dict(name="Phone Number", detect=det_phone, hint=hint_phone, thr=0.90,
         desc="are phone numbers (formatted US/NANP with valid area/exchange digits, +country-code, or local 0-prefixed)",
         weak_desc="bare 10/11-digit numbers that could be phones"),
    dict(name="Date of Birth", detect=det_dob, hint=hint_dob, thr=0.90, column_check=dob_column_check,
         desc="are valid calendar dates implying an age of 0-120",
         weak_desc="dates with 2-digit year or bare digits"),
    dict(name="City", detect=det_city, hint=hint_city, thr=0.80,
         desc="are in the city gazetteer", weak_desc="look like place names but are not in the gazetteer"),
    dict(name="Person Name", detect=det_name, hint=hint_name, thr=0.80,
         desc="look like person names (known first/last name, not a city or job-title word)",
         weak_desc="have name shape (capitalised words) but no known first/last name"),
]
CONF_RANK = {"High": 3, "Medium": 2, "Low": 1}


def mask_ssn(v):
    return re.sub(r"\d", "*", v[:-4]) + v[-4:] if len(v) >= 4 else v


def evaluate(cls, header, values, res):
    n = len(values)
    toks, joined = header_tokens(header)
    hint = bool(cls["hint"](toks, joined))
    strong = weak = 0
    aux = []
    misses = []
    cache = {}
    for v in values:
        if v not in cache:
            cache[v] = cls["detect"](v, res)
        lvl, a = cache[v]
        if lvl == STRONG:
            strong += 1
            aux.append(a)
        elif lvl == WEAK:
            weak += 1
            aux.append(a)
        else:
            misses.append(v)
    s, w = strong / n, (strong + weak) / n
    cand = dict(cls=cls["name"], strong=strong, weak=weak, n=n, s=s, w=w, hint=hint, accepted=False,
                confidence=None, why_not="", used_weak=False, note="")
    # --- decision rule table
    if hint:
        if s >= 0.60:
            cand.update(accepted=True, confidence="High" if s >= 0.90 else "Medium")
        elif w >= 0.80 and weak > 0:
            cand.update(accepted=True, confidence="Low", used_weak=True)
        else:
            cand["why_not"] = (f"header hints at it but values disagree: {strong}/{n} strong ({s:.0%}), "
                               f"{strong + weak}/{n} incl. weak ({w:.0%}); need >=60% strong or >=80% incl. weak")
    else:
        if s >= cls["thr"]:
            cand.update(accepted=True, confidence="High" if s >= 0.95 else "Medium")
        else:
            cand["why_not"] = (f"{strong}/{n} strong matches ({s:.0%}); without a header hint need >= {cls['thr']:.0%}"
                               + (f" ({weak} weak shape-only match(es) ignored without a header hint)" if weak else ""))
    # --- class-specific column plausibility check (DOB without birth hint)
    if cand["accepted"] and not hint and "column_check" in cls:
        ok, why = cls["column_check"](toks, aux, n)
        cand["note"] = why
        if not ok:
            cand.update(accepted=False, confidence=None, why_not=why)
    if cand["accepted"] and n < 3:
        cand["confidence"] = "Low"
        cand["note"] = (cand["note"] + "; " if cand["note"] else "") + f"only {n} non-empty value(s)"
    mask = cls.get("mask", False)
    cand["misses"] = [mask_ssn(m) if mask else m for m in misses[:3]]
    return cand


def build_reason(cls, cand, header):
    pct = lambda x: f"{x:.0%}"
    parts = [f"{cand['strong']} of {cand['n']} non-empty values {cls['desc']} ({pct(cand['s'])})."]
    if cand["used_weak"] and cand["weak"]:
        parts.append(f"A further {cand['weak']} {cls['weak_desc']} - counted only because the header agrees.")
    parts.append(f'Header "{header}" ' + ("matches this class." if cand["hint"]
                                           else "gives no hint; decision rests on values alone."))
    if cand["note"]:
        parts.append(cand["note"].capitalize() + ".")
    if cand["misses"]:
        parts.append("Non-matching examples: " + ", ".join(repr(m) for m in cand["misses"]) + ".")
    return " ".join(parts)


def classify_column(header, values, res):
    """values: raw strings. Returns a result dict."""
    values = [v.strip() for v in values]
    non_empty = [v for v in values if v.lower() not in NULL_VALUES]
    out = dict(column=header, data_class=NOT_CLASSIFIED, confidence=None, reason="", rows=len(values),
               non_empty=len(non_empty), candidates=[], examples=[])
    if not non_empty:
        out["reason"] = "Column is empty (or contains only null-like placeholders)."
        return out
    cands = [(c, evaluate(c, header, non_empty, res)) for c in CLASSES]
    out["candidates"] = [dict(data_class=c["name"], strong=e["strong"], weak=e["weak"], non_empty=e["n"],
                              header_hint=e["hint"], accepted=e["accepted"], rejected_because=e["why_not"] or None)
                         for c, e in cands]
    accepted = [(c, e) for c, e in cands if e["accepted"]]
    if accepted:
        # Tie-break: header hint, then confidence, then strong share. (list order is the final tie-break)
        accepted.sort(key=lambda ce: (ce[1]["hint"], CONF_RANK[ce[1]["confidence"]], ce[1]["s"]), reverse=True)
        cls, cand = accepted[0]
        out.update(data_class=cls["name"], confidence=cand["confidence"], reason=build_reason(cls, cand, header))
        if len(accepted) > 1:
            others = ", ".join(f"{c['name']} ({e['s']:.0%})" for c, e in accepted[1:])
            out["reason"] += f" Also passed its threshold but ranked lower: {others}."
        shown = [mask_ssn(v) if cls.get("mask") else v for v in dict.fromkeys(non_empty)][:3]
        out["examples"] = shown
    else:
        best_cls, best = max(cands, key=lambda ce: (ce[1]["s"], ce[1]["hint"], ce[1]["w"]))
        uniq = list(dict.fromkeys(non_empty))[:3]
        out["examples"] = [mask_ssn(v) if re.fullmatch(r"[\d\- ]{9,11}", v) else v for v in uniq]
        if best["s"] == 0 and not best["hint"]:
            out["reason"] = (f"None of the {best['n']} non-empty values matched any of the 6 patterns "
                             f"(e.g. {', '.join(repr(u) for u in uniq)}).")
        else:
            out["reason"] = f"No class met its rule. Closest: {best_cls['name']} - {best['why_not']}."
        datey = sum(1 for v in non_empty if re.fullmatch(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}", v))
        if datey / len(non_empty) >= 0.5 and best["s"] < 0.5:
            out["reason"] += (f" Note: {datey}/{len(non_empty)} values are date-shaped but are not valid calendar "
                              f"dates (e.g. {next(v for v in non_empty if re.fullmatch(r'[0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4}', v))!r}).")
    return out


# --------------------------------------------------------------------------- IO
def read_csv(path, max_rows):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1")
    try:
        delim = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ","
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    try:
        header = next(reader)
    except StopIteration:
        return [], []
    header = [(h.strip() or f"column_{i}") for i, h in enumerate(header)]
    cols = [[] for _ in header]
    for r_i, row in enumerate(reader):
        if max_rows and r_i >= max_rows:
            break
        if not row:
            continue
        for i in range(len(header)):
            cols[i].append(row[i] if i < len(row) else "")
    return header, cols


def format_text(results, path):
    lines = [f"File: {path}", f"Columns: {len(results)}", ""]
    for r in results:
        conf = f"  [confidence: {r['confidence']}]" if r["confidence"] else ""
        lines.append(f'Column "{r["column"]}" -> {r["data_class"]}{conf}')
        lines.append(f"  Reason: {r['reason']}")
        lines.append("")
    return "\n".join(lines)


def format_verbose(results, path):
    lines = [format_text(results, path), "---- candidate details ----"]
    for r in results:
        lines.append(f'Column "{r["column"]}" (non-empty: {r["non_empty"]}/{r["rows"]})')
        for c in r["candidates"]:
            flag = "ACCEPT" if c["accepted"] else "reject"
            lines.append(f'   {flag}  {c["data_class"]:<22} strong={c["strong"]} weak={c["weak"]} hint={c["header_hint"]}'
                         + (f' -> {c["rejected_because"]}' if c["rejected_because"] else ""))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Classify CSV columns into sensitive data classes.")
    ap.add_argument("csv_path")
    ap.add_argument("--json", action="store_true", help="output JSON")
    ap.add_argument("-v", "--verbose", action="store_true", help="show all candidate classes per column")
    ap.add_argument("--max-rows", type=int, default=100000, help="only inspect the first N data rows (0 = all)")
    args = ap.parse_args(argv)
    header, cols = read_csv(args.csv_path, args.max_rows)
    res = Resources()
    results = [classify_column(h, c, res) for h, c in zip(header, cols)]
    if args.json:
        print(json.dumps({"file": args.csv_path, "columns": results}, indent=2))
    elif args.verbose:
        print(format_verbose(results, args.csv_path))
    else:
        print(format_text(results, args.csv_path))


if __name__ == "__main__":
    main()
