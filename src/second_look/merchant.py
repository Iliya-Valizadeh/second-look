"""Turn a transaction description into a merchant key for grouping (ADR 0002).

The steps run in a fixed order: normalize and upper-case, drop a known
payment-processor prefix, drop store and reference numbers, replace punctuation with
spaces, drop a trailing province code, then drop a trailing legal suffix. The key is
only for grouping. Callers should keep showing the original description next to any
flag, so a user can see which rows were grouped together.
"""

from __future__ import annotations

import re
import unicodedata

_PROCESSOR_PREFIXES = ("SQ *", "TST*", "PAYPAL *", "PP*")

_PROVINCE_CODES = frozenset(
    {"ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU"}
)

_LEGAL_SUFFIXES = frozenset({"INC", "LTD", "LLC", "CORP"})

_STORE_NUMBER_RE = re.compile(r"#\d+")
_LONG_DIGIT_RUN_RE = re.compile(r"\d{4,}")
_PUNCTUATION_RE = re.compile(r"[^\w\s&']")
_WHITESPACE_RE = re.compile(r"\s+")


def merchant_key(description: str) -> str:
    """Build the grouping key for a transaction description.

    Returns the upper-cased, space-collapsed description when the cleaning steps
    would otherwise leave nothing.
    """
    normalized = _collapse(unicodedata.normalize("NFKC", description).upper())

    working = normalized
    for prefix in _PROCESSOR_PREFIXES:
        if working.startswith(prefix):
            working = working[len(prefix) :]
            break

    working = _STORE_NUMBER_RE.sub("", working)
    working = _LONG_DIGIT_RUN_RE.sub("", working)
    working = _collapse(_PUNCTUATION_RE.sub(" ", working))

    words = working.split(" ") if working else []
    if words and words[-1] in _PROVINCE_CODES:
        words = words[:-1]
    if words and words[-1] in _LEGAL_SUFFIXES:
        words = words[:-1]

    key = " ".join(words).strip()
    return key if key else normalized


def _collapse(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()
