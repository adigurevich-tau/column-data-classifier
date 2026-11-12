# Sensitive-data column classifier - note

## How to run
    python3 classify.py sample_employees.csv          # text report (Python 3.8+, standard library only, nothing to install)
    python3 classify.py file.csv --json               # JSON
    python3 classify.py file.csv -v                   # also shows every candidate class and why it was accepted/rejected
    python3 tests/test_classify.py                    # 40 edge-case checks
Results on the sample file: `sample_output.txt`.

## Approach
Deterministic rules, one detector per class, evidence printed for every decision.
* Each value gets a level per class: STRONG (fits + passes validity checks), WEAK (right shape but ambiguous),
  or NO. Examples: SSN follows SSA rules (area not 000/666/9xx, group not 00, serial not 0000); phones need valid
  NANP digits or +country-code; dates must be real calendar dates implying age 0-120; cities come from a gazetteer
  (`data/cities.txt`); names need a known first/last name (`data/first_names.txt`, `surnames.txt`) and must not be
  a city or job-title word.
* Column decision = fixed rule table on s (share STRONG) and the header hint:
  no hint -> need s >= 90% (80% for city/name, whose lists are incomplete);
  hint -> s >= 60%, or shape-only >= 80% (Low confidence). **A header alone never classifies a column**, and WEAK
  matches (9 bare digits, unknown capitalised words) count only when the header agrees.
* Extra plausibility rule for DOB without a birth-related header: ages must be 18-100 with spread, and header words
  like start/hire/created veto it. That is why `start_date` is not DOB and `field_12` (impossible dates such as
  `2024-12-3100`) is not classified.
* Output: class, confidence (High/Medium/Low), and a reason with counts, header evidence, non-matching examples,
  and for unclassified columns the closest class and why it missed. SSN examples are masked.
* Gazetteers are plain text files: extend them without touching code. Handles delimiter sniffing, utf-8/cp1252,
  ragged rows, null-like placeholders.

## Options considered
* Sending columns to an LLM: rejected - not explainable/reproducible, cost and privacy on thousands of files.
* Presidio/spaCy NER or a trained classifier: good for names/cities in free text, but needs labelled data or heavy
  dependencies, and is harder to explain per column. Candidate for a later hybrid for names/cities only.
* Header-name matching only: trivial but wrong on renamed columns (`field_12`) and misleading ones; used only as a booster.
* Checksum-style validation: SSNs have none, so structural rules are used.

## What works / what doesn't
Works: structured identifiers (SSN, email, phone, formatted dates) are precise; ambiguity is resolved explicitly
(bare digits, state codes, start vs birth dates, multiword cities vs names).
Known weaknesses:
* Names/cities depend on gazetteer coverage -> false negatives for uncommon names/small towns when the header is
  uninformative (they only classify with a hint, at Low confidence).
* Single-word names that are also cities (Jordan, Austin) are only claimed with a header hint.
* Job titles/departments/products made of surnames ("Baker Street Cafe", "Carter Sales") can false-positive as names.
* Mixed columns (e.g. 70% emails, rest junk, no header) are rejected by the 90% threshold; ambiguous DD/MM vs MM/DD is ignored for DOB.
* Non-US phone formats are only partly covered; non-US national IDs are intentionally out of scope.
* Head sampling (first 100k rows) can be biased on sorted files; the whole column is not scanned.

## Next steps
1. Build a labelled set of columns, measure per-class precision/recall on thousands of files, and tune thresholds from data, not intuition.
2. Replace gazetteers with larger sources (GeoNames, name frequency lists) and add fuzzy/accents handling.
3. Add cross-column context (a `state` column beside `city`, `first`+`last` pairs) and value-uniqueness signals.
4. Log every false positive/negative from reviews into regression tests.
