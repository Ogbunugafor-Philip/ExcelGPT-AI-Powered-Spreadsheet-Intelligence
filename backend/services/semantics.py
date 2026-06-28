"""
Column semantics — the shared brain behind "deep column intelligence".

Two pure, dependency-light helpers used across the backend so every layer
(profiler, intent engine, computation modules, packager, charts) speaks about
columns the same way:

* ``suggest_display_name(raw)`` — a human, presentation-ready label
  ("deposits_ngn" -> "Deposits (₦)", "num_customers" -> "No. of Customers").
* ``semantic_label(raw, series, inferred_type)`` — the *role* a column plays
  ("Revenue" -> "revenue_metric", "Branch" -> "entity_identifier").

These are intentionally free of pandas-heavy logic so they can be imported
anywhere without import cycles. ``fuzzywuzzy`` is used opportunistically for
near-miss keyword matching; the module degrades gracefully if it is absent.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

try:  # optional — improves recall on near-miss header spellings
    from fuzzywuzzy import fuzz  # type: ignore

    _HAVE_FUZZ = True
except Exception:  # noqa: BLE001 — any import failure just disables fuzzy fallback
    _HAVE_FUZZ = False


# ---------------------------------------------------------------------------
# Display names
# ---------------------------------------------------------------------------

# Currency-bearing suffix tokens -> the symbol we render in the display name.
_CURRENCY_TOKENS: dict[str, str] = {
    "ngn": "₦",
    "naira": "₦",
    "usd": "$",
    "dollar": "$",
    "dollars": "$",
    "gbp": "£",
    "eur": "€",
    "kes": "KSh",
    "ghs": "GH₵",
    "zar": "R",
}

# Tokens that should render as fixed abbreviations rather than Title Case.
_ABBREVIATIONS: dict[str, str] = {
    "id": "ID",
    "lga": "LGA",
    "fso": "FSO",
    "dsa": "DSA",
    "kpi": "KPI",
    "roi": "ROI",
    "ytd": "YTD",
    "mtd": "MTD",
    "qtd": "QTD",
    "yoy": "YoY",
    "mom": "MoM",
    "qoq": "QoQ",
    "nps": "NPS",
    "csat": "CSAT",
    "ebitda": "EBITDA",
    "pbt": "PBT",
    "pat": "PAT",
    "sku": "SKU",
    "atm": "ATM",
    "pos": "POS",
    "avg": "Avg",
    "max": "Max",
    "min": "Min",
    "std": "Std",
    "pct": "%",
    "percent": "%",
    "percentage": "%",
}

# Multi-token rewrites applied before per-token title casing.
_PHRASE_TOKENS: dict[str, str] = {
    "num": "No. of",
    "no": "No. of",
    "nbr": "No. of",
    "qty": "Quantity",
}

_SPLIT_RE = re.compile(r"[\s_\-/.]+")
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _raw_name(name: Any) -> str:
    if isinstance(name, dict):
        return str(name.get("name", ""))
    return str(name if name is not None else "")


def _tokenize(text: str) -> list[str]:
    """Split a raw header into lowercase word tokens (handles snake/camel/kebab)."""
    spaced = _CAMEL_RE.sub(" ", text)
    parts = _SPLIT_RE.split(spaced.strip())
    return [p for p in parts if p]


def suggest_display_name(column_name: Any) -> str:
    """Turn a raw column header into a clean, presentation-ready label.

    Examples
    --------
    >>> suggest_display_name("deposits_ngn")
    'Deposits (₦)'
    >>> suggest_display_name("num_customers")
    'No. of Customers'
    >>> suggest_display_name("growth_rate")
    'Growth Rate'
    """
    raw = _raw_name(column_name).strip()
    if not raw:
        return ""

    tokens = _tokenize(raw)
    if not tokens:
        return raw

    # Pull a trailing currency token into a symbol suffix ("deposits_ngn" -> "(₦)").
    currency_suffix = ""
    if len(tokens) > 1 and tokens[-1].lower() in _CURRENCY_TOKENS:
        currency_suffix = f" ({_CURRENCY_TOKENS[tokens[-1].lower()]})"
        tokens = tokens[:-1]

    words: list[str] = []
    for token in tokens:
        lower = token.lower()
        if lower in _PHRASE_TOKENS:
            words.append(_PHRASE_TOKENS[lower])
        elif lower in _ABBREVIATIONS:
            words.append(_ABBREVIATIONS[lower])
        elif lower in _CURRENCY_TOKENS:
            words.append(_CURRENCY_TOKENS[lower])
        elif token.isupper() and len(token) <= 5:
            words.append(token)  # preserve already-uppercase acronyms
        else:
            words.append(token.capitalize())

    label = " ".join(words).strip()
    # Avoid an awkward dangling "%" word becoming its own token elsewhere.
    label = label.replace(" %", " (%)") if label.endswith(" %") else label
    return (label + currency_suffix).strip()


def build_display_name_map(columns: Iterable[Any]) -> dict[str, str]:
    """Map every raw column name to its display name."""
    result: dict[str, str] = {}
    for column in columns:
        raw = _raw_name(column)
        if raw and raw not in result:
            result[raw] = suggest_display_name(raw)
    return result


# ---------------------------------------------------------------------------
# Semantic roles
# ---------------------------------------------------------------------------

# Ordered (label, keyword-list) rules. The FIRST rule whose keyword is found in
# the column name wins, so more specific roles must come before broader ones.
_SEMANTIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("time_dimension", ("month", "date", "period", "year", "quarter", "week", "day", "time", "fiscal", "fy")),
    ("growth_metric", ("growth", "yoy", "mom", "qoq", "pct", "percent", "rate", "change", "delta")),
    ("rank_metric", ("rank", "position", "ranking", "percentile", "placement")),
    ("target_metric", ("target", "budget", "plan", "goal", "quota", "objective")),
    ("actual_metric", ("actual", "achievement", "achieved", "attained", "realised", "realized")),
    ("geographic_dimension", ("region", "zone", "state", "lga", "province", "city", "district", "territory", "geo", "country")),
    ("score_metric", ("score", "rating", "kpi", "index", "grade", "csat", "nps", "satisfaction")),
    ("profit_metric", ("profit", "margin", "net", "earnings", "ebitda", "surplus", "pbt", "pat")),
    ("cost_metric", ("cost", "expense", "expenditure", "opex", "spend", "outflow", "fee")),
    ("volume_metric", ("count", "volume", "quantity", "qty", "units", "transactions", "txn", "tickets", "num", "nbr", "number")),
    ("revenue_metric", ("revenue", "sales", "turnover", "income", "deposit", "loan", "gmv", "inflow", "amount", "balance")),
    ("category_dimension", ("product", "channel", "category", "segment", "sku", "brand", "line", "class", "division", "type")),
    ("entity_identifier", ("branch", "outlet", "store", "account", "unit", "office", "department", "team", "company", "customer", "client", "code")),
    ("person_identifier", ("staff", "employee", "officer", "agent", "manager", "rep", "salesperson", "name", "person")),
)

_DIMENSION_LABELS = {
    "time_dimension",
    "geographic_dimension",
    "category_dimension",
    "entity_identifier",
    "person_identifier",
}
_METRIC_LABELS = {
    "revenue_metric",
    "target_metric",
    "actual_metric",
    "growth_metric",
    "rank_metric",
    "volume_metric",
    "cost_metric",
    "profit_metric",
    "score_metric",
}

# Every keyword paired with its rule label, for the fuzzy fallback pass.
_FLAT_KEYWORDS: tuple[tuple[str, str], ...] = tuple(
    (keyword, label) for label, keywords in _SEMANTIC_RULES for keyword in keywords
)


def _keyword_hit(tokens: list[str], compact: str, keyword: str) -> bool:
    """True if `keyword` is present as a token or substring of the compact name."""
    if keyword in tokens:
        return True
    for token in tokens:
        if token.startswith(keyword) or token.endswith(keyword):
            return True
    return keyword in compact


def _fuzzy_label(tokens: list[str]) -> str | None:
    if not (_HAVE_FUZZ and tokens):
        return None
    best_label: str | None = None
    best_score = 0
    for token in tokens:
        for keyword, label in _FLAT_KEYWORDS:
            score = fuzz.ratio(token, keyword)
            if score > best_score:
                best_score, best_label = score, label
    return best_label if best_score >= 86 else None


def semantic_label(column_name: Any, series: Any = None, inferred_type: str | None = None) -> str:
    """Return the semantic role for a column.

    Matching is fuzzy in spirit: the name is lowercased, split into tokens, and
    each rule's keywords are checked with contains / startswith / endswith. The
    inferred type breaks the rare dimension-vs-metric tie (e.g. a numeric column
    that only weakly matched a dimension keyword stays a metric).
    """
    raw = _raw_name(column_name)
    lower = raw.lower()
    compact = re.sub(r"[^a-z0-9]", "", lower)
    tokens = _tokenize(raw)
    if not compact:
        return "unknown"

    numeric_type = (inferred_type or "") in {"currency", "integer", "float", "percentage", "number"}

    for label, keywords in _SEMANTIC_RULES:
        if any(_keyword_hit(tokens, compact, keyword) for keyword in keywords):
            # A clearly numeric column that only matched a dimension role is more
            # likely an unlabelled metric than a dimension (e.g. "type_value": 42).
            if numeric_type and label in _DIMENSION_LABELS and not _looks_textual(series):
                continue
            return label

    fuzzy = _fuzzy_label(tokens)
    if fuzzy:
        return fuzzy

    # Last resort: classify by data shape so downstream still gets a useful hint.
    if numeric_type:
        return "volume_metric" if (inferred_type == "integer") else "unknown"
    return "unknown"


def _looks_textual(series: Any) -> bool:
    if series is None:
        return False
    try:
        non_null = series.dropna()
        if non_null.empty:
            return False
        textual = sum(1 for v in non_null if isinstance(v, str))
        return textual / len(non_null) >= 0.6
    except Exception:  # noqa: BLE001 — series may not be a pandas Series
        return False
