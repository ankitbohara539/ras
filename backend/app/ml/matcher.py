"""The duplicate matcher.

Blends four signals into one score. The output is a ranked list of
suggestions -- this module never decides that two tickets are the same, it
only says how alike they look. An authority makes the call.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.geo import haversine_m
from app.ml.encoder import cosine_similarity
from app.ml.imaging import best_phash_similarity


@dataclass(frozen=True)
class MatchWeights:
    category: float = 0.35
    text: float = 0.30
    image: float = 0.20
    geo: float = 0.15

    def validate(self) -> None:
        total = self.category + self.text + self.image + self.geo
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Match weights must sum to 1.0, got {total:.4f}.")


@dataclass
class MatchCandidate:
    """A ticket the new report might belong under."""

    ticket_id: object
    category_key: str
    embedding: list[float] | None
    latitude: float
    longitude: float
    phashes: list[str | None]


@dataclass
class MatchInput:
    """The freshly submitted report."""

    category_key: str
    embedding: list[float] | None
    latitude: float
    longitude: float
    phashes: list[str | None]


@dataclass
class MatchResult:
    ticket_id: object
    score: float
    category_score: float
    text_score: float
    image_score: float
    geo_score: float
    distance_m: float

    def explain(self) -> str:
        """Plain-language reason, shown to the authority reviewing the merge."""
        parts = [f"{self.distance_m:.0f}m apart"]
        if self.category_score >= 1.0:
            parts.append("same category")
        if self.text_score >= 0.6:
            parts.append(f"descriptions {self.text_score:.0%} similar")
        if self.image_score >= 0.5:
            parts.append(f"photos {self.image_score:.0%} similar")
        return ", ".join(parts)


def geo_score(distance_m: float, radius_m: float) -> float:
    """Linear falloff from 1.0 at zero distance to 0.0 at the category radius.

    Linear rather than Gaussian because an authority has to be able to look at
    "60m of a 100m radius" and predict the number.
    """
    if radius_m <= 0:
        return 0.0
    if distance_m >= radius_m:
        return 0.0
    return 1.0 - (distance_m / radius_m)


def score_pair(
    new_report: MatchInput,
    candidate: MatchCandidate,
    radius_m: float,
    weights: MatchWeights,
) -> MatchResult:
    distance = haversine_m(
        new_report.latitude,
        new_report.longitude,
        candidate.latitude,
        candidate.longitude,
    )

    category = 1.0 if new_report.category_key == candidate.category_key else 0.0

    text = 0.0
    if new_report.embedding is not None and candidate.embedding is not None:
        text = cosine_similarity(new_report.embedding, candidate.embedding)

    image = best_phash_similarity(new_report.phashes, candidate.phashes)
    geo = geo_score(distance, radius_m)

    # Renormalise over the signals that actually exist. Most reports have no
    # photo, and leaving the image weight in the denominator would cap every
    # photo-less pair at 0.80 -- so a real duplicate described in Nepali and
    # English (near-zero char-ngram overlap) could never clear the threshold
    # on category and distance alone.
    has_photos = any(new_report.phashes) and any(candidate.phashes)

    active = weights.category + weights.text + weights.geo
    total = weights.category * category + weights.text * text + weights.geo * geo

    if has_photos:
        active += weights.image
        total += weights.image * image

    total = total / active if active else 0.0

    # float() on every field: these are written straight to the database, and
    # a numpy scalar leaking through has no psycopg2 adapter.
    return MatchResult(
        ticket_id=candidate.ticket_id,
        score=round(float(total), 4),
        category_score=round(float(category), 4),
        text_score=round(float(text), 4),
        image_score=round(float(image), 4),
        geo_score=round(float(geo), 4),
        distance_m=round(float(distance), 1),
    )


def rank_candidates(
    new_report: MatchInput,
    candidates: list[MatchCandidate],
    radius_m: float,
    weights: MatchWeights | None = None,
    min_score: float = 0.45,
    limit: int = 5,
) -> list[MatchResult]:
    """Score every candidate and return the plausible ones, best first."""
    weights = weights or MatchWeights()
    weights.validate()

    results = []
    for candidate in candidates:
        result = score_pair(new_report, candidate, radius_m, weights)

        # Distance is a gate, not just a weight. Two reports further apart than
        # the category radius are not the same incident, however similarly they
        # are worded -- and they are worded similarly often, because everyone
        # describes a pothole the same way. Without this, text similarity alone
        # (0.35 category + 0.30 text = 0.65) clears any sane threshold and the
        # matcher suggests merging every pothole in the municipality.
        if result.distance_m > radius_m:
            continue

        if result.score >= min_score:
            results.append(result)

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]
