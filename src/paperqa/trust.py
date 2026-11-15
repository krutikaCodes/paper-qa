from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping
from datetime import datetime
from typing import Any

from paperqa.university_rankings import top_university_matches

# Phase 2 plan: missing data counts as neutral, not as bad. Not knowing a paper's
# venue (e.g. an arXiv-only paper) is not evidence that the paper is weak.
NEUTRAL_SCORE = 0.5
# Matches DocDetails.UNDEFINED_JOURNAL_QUALITY: the venue's quality is unknown
UNKNOWN_SOURCE_QUALITY = -1
# Papers scoring below this are called low-trust in the gather_evidence warning
LOW_TRUST_THRESHOLD = 0.6


def _get_value(obj: Any, *names: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        for name in names:
            if name in obj:
                return obj[name]
        return default

    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def _store_trust_score(obj: Any, score: float) -> float:
    if isinstance(obj, MutableMapping):
        obj["trust_score"] = score
    elif hasattr(obj, "trust_score"):
        setattr(obj, "trust_score", score)
    return score


def _store_university_matches(
    obj: Any, institutions: Any, matches: list[tuple[str, int]]
) -> None:
    if isinstance(obj, MutableMapping):
        obj["top_university_affiliations"] = (
            [name for name, _ in matches] if institutions is not None else None
        )
        obj["top_university_rank"] = matches[0][1] if matches else None
    else:
        if hasattr(obj, "top_university_affiliations"):
            obj.top_university_affiliations = (
                [name for name, _ in matches] if institutions is not None else None
            )
        if hasattr(obj, "top_university_rank"):
            obj.top_university_rank = matches[0][1] if matches else None


def _normalize_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"true", "yes", "y", "1"}:
            return True
        if cleaned in {"false", "no", "n", "0"}:
            return False
    return bool(value)


def _normalize_source_quality(value: Any) -> float:
    if value is None or value == UNKNOWN_SOURCE_QUALITY:
        return NEUTRAL_SCORE

    if isinstance(value, str):
        cleaned = " ".join(
            value.strip().lower().replace("-", " ").replace("_", " ").split()
        )
        mapping = {
            "0": 0.0,
            "poor": 0.0,
            "poor quality": 0.0,
            "predatory": 0.0,
            "low": 0.0,
            "low quality": 0.0,
            "1": 0.5,
            "fair": 0.5,
            "medium": 0.5,
            "moderate": 0.5,
            "peer reviewed": 0.5,
            "reviewed": 0.5,
            "2": 0.8,
            "good": 0.8,
            "high": 0.8,
            "high quality": 0.8,
            "domain leading": 0.8,
            "domain leading peer reviewed": 0.8,
            "3": 1.0,
            "excellent": 1.0,
            "excellent quality": 1.0,
            "very high": 1.0,
            "highest quality": 1.0,
            "highest quality peer reviewed": 1.0,
        }
        if cleaned in mapping:
            return mapping[cleaned]

        try:
            value = float(cleaned)
        except ValueError:
            return 0.0

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0

    if numeric <= 0:
        return 0.0
    if numeric >= 3:
        return 1.0
    return {0: 0.0, 1: 0.5, 2: 0.8, 3: 1.0}.get(int(round(numeric)), 0.0)


def _citation_score(citation_count: Any, year: Any) -> float:
    try:
        citations = int(citation_count)
    except (TypeError, ValueError):
        return NEUTRAL_SCORE  # Citation count unknown

    if citations <= 0:
        return 0.0  # Known to have no citations

    try:
        publication_year = int(year)
    except (TypeError, ValueError):
        return NEUTRAL_SCORE  # Can't compute citations per year

    if publication_year <= 0:
        return 0.0

    age_years = max(1, datetime.now().year - publication_year)
    citations_per_year = citations / age_years
    return min(1.0, math.log1p(citations_per_year) / math.log1p(20.0))


def _paper_year(value: Any, fallback: Any = None) -> Any:
    if value is None:
        return fallback
    if isinstance(value, datetime):
        return value.year
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() and len(stripped) == 4:
            return int(stripped)
        try:
            return datetime.fromisoformat(stripped).year
        except ValueError:
            return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def score_trust(file: Any) -> float:
    """Score a paper-like record on a 0.0 to 1.0 trust scale.

    The score combines source quality, citations per year, retraction status,
    metadata completeness, and whether an author is affiliated with a top-100
    research university. Store the score on mutable mappings and records with a
    trust_score field.
    """
    source_quality = _get_value(
        file,
        "source_quality",
        "sourceQuality",
        "journal_quality",
        "journalQuality",
        "quality",
    )
    citations = _get_value(file, "citation_count", "citationCount", "cited_by_count")
    year = _paper_year(
        _get_value(file, "year", "publication_year", "publicationYear"),
        _paper_year(_get_value(file, "publication_date", "publicationDate")),
    )
    retracted = _normalize_bool(
        _get_value(file, "is_retracted", "retracted", "isRetracted")
    )
    institutions = _get_value(
        file, "institutions", "affiliations", "author_affiliations"
    )
    university_matches = top_university_matches(institutions)
    _store_university_matches(file, institutions, university_matches)

    if retracted is True:
        return _store_trust_score(file, 0.0)

    source_score = _normalize_source_quality(source_quality)
    citation_score = _citation_score(citations, year)
    retraction_score = 1.0 if retracted is False else NEUTRAL_SCORE
    university_score = 1.0 if university_matches else 0.0

    required_fields = [
        source_quality,
        citations,
        year,
        retracted,
    ]
    missing_count = sum(1 for value in required_fields if value is None)
    missing_score = 1.0 - (missing_count / len(required_fields))

    trust_score = (
        0.36 * source_score
        + 0.315 * citation_score
        + 0.135 * retraction_score
        + 0.09 * missing_score
        + 0.10 * university_score
    )
    return _store_trust_score(file, max(0.0, min(1.0, trust_score)))


def get_trust_score(file: Any) -> float:
    """Return a stored trust score or compute one from the available metadata."""
    trust = _get_value(file, "trust_score")
    return float(trust) if trust is not None else score_trust(file)


def context_rank_score(context: Any, use_trust_score: bool = False) -> float:
    """Return a context's relevance, optionally weighted by its document trust."""
    relevance_score = context.score
    if not use_trust_score:
        return relevance_score

    return relevance_score * get_trust_score(context.text.doc)


calculate_trust = score_trust
trust_score = score_trust

__all__ = [
    "calculate_trust",
    "context_rank_score",
    "get_trust_score",
    "score_trust",
    "trust_score",
]
