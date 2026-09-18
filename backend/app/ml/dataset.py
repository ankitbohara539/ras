"""Synthetic report generator.

Two jobs:

1. Labelled text for training the category classifier.
2. Duplicate *clusters* -- several differently-worded reports of one real-world
   incident at nearby coordinates -- which is what the matcher is evaluated
   against. Without positive pairs there is nothing to measure.

Everything is seeded, so a given seed always produces the same corpus.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field

from app.ml.templates import TEMPLATES, TITLES
from app.ml.vocab import (
    COMPLAINT_OPENERS_EN,
    COMPLAINT_OPENERS_NE,
    DURATION_EN,
    DURATION_NE,
    PLACES_EN,
    PLACES_NE,
    ROMAN_NEPALI_HINTS,
)

CATEGORY_KEYS = list(TEMPLATES)

# Typos people actually make on a phone keyboard.
_TYPO_SWAPS = [
    ("the", "teh"),
    ("road", "raod"),
    ("water", "watter"),
    ("please", "pls"),
    ("garbage", "garbge"),
    ("street", "streat"),
    ("light", "lite"),
    ("there", "ther"),
]


@dataclass
class SyntheticReport:
    text: str
    title: str
    category_key: str
    language: str
    latitude: float
    longitude: float
    # Reports sharing a cluster_id describe the same real-world incident.
    cluster_id: int | None = None
    is_cluster_seed: bool = False


@dataclass
class GeneratedCorpus:
    reports: list[SyntheticReport] = field(default_factory=list)

    @property
    def clusters(self) -> dict[int, list[SyntheticReport]]:
        grouped: dict[int, list[SyntheticReport]] = {}
        for report in self.reports:
            if report.cluster_id is not None:
                grouped.setdefault(report.cluster_id, []).append(report)
        return grouped

    def as_dicts(self) -> list[dict]:
        return [asdict(r) for r in self.reports]


def _offset_coords(
    lat: float, lon: float, distance_m: float, bearing_rad: float
) -> tuple[float, float]:
    """Move a point by distance_m along a bearing."""
    d_lat = (distance_m * math.cos(bearing_rad)) / 110_574.0
    d_lon = (distance_m * math.sin(bearing_rad)) / (
        111_320.0 * max(math.cos(math.radians(lat)), 1e-6)
    )
    return lat + d_lat, lon + d_lon


class ReportGenerator:
    def __init__(self, seed: int = 20250918) -> None:
        self.rng = random.Random(seed)

    # -- text ------------------------------------------------------------

    def _apply_typos(self, text: str) -> str:
        """Corrupt one word. Char n-grams should survive this; word tokens do not."""
        for correct, typo in self.rng.sample(_TYPO_SWAPS, k=len(_TYPO_SWAPS)):
            if correct in text:
                return text.replace(correct, typo, 1)
        return text

    def _maybe_code_mix(self, text: str, category_key: str) -> str:
        """Splice in Roman Nepali, which is how a lot of Nepal actually types."""
        hints = ROMAN_NEPALI_HINTS.get(category_key)
        if not hints:
            return text
        return f"{text} ({self.rng.choice(hints)})"

    def make_text(self, category_key: str, language: str) -> str:
        templates = TEMPLATES[category_key][language]
        template = self.rng.choice(templates)

        if language == "en":
            text = template.format(
                place=self.rng.choice(PLACES_EN),
                duration=self.rng.choice(DURATION_EN),
            )
            opener = self.rng.choice(COMPLAINT_OPENERS_EN)
        else:
            text = template.format(
                place=self.rng.choice(PLACES_NE),
                duration=self.rng.choice(DURATION_NE),
            )
            opener = self.rng.choice(COMPLAINT_OPENERS_NE)

        if opener:
            text = f"{text} {opener}"

        if language == "en":
            if self.rng.random() < 0.18:
                text = self._apply_typos(text)
            if self.rng.random() < 0.12:
                text = self._maybe_code_mix(text, category_key)
            if self.rng.random() < 0.10:
                text = text.lower()

        return text.strip()

    def make_title(self, category_key: str, language: str) -> str:
        title_en, title_ne = TITLES[category_key]
        return title_en if language == "en" else title_ne

    def _pick_language(self) -> str:
        return "ne" if self.rng.random() < 0.45 else "en"

    # -- reports ---------------------------------------------------------

    def make_report(
        self,
        category_key: str,
        latitude: float,
        longitude: float,
        language: str | None = None,
        cluster_id: int | None = None,
        is_cluster_seed: bool = False,
    ) -> SyntheticReport:
        language = language or self._pick_language()
        return SyntheticReport(
            text=self.make_text(category_key, language),
            title=self.make_title(category_key, language),
            category_key=category_key,
            language=language,
            latitude=round(latitude, 6),
            longitude=round(longitude, 6),
            cluster_id=cluster_id,
            is_cluster_seed=is_cluster_seed,
        )

    def make_cluster(
        self,
        category_key: str,
        latitude: float,
        longitude: float,
        radius_m: int,
        cluster_id: int,
        size: int,
    ) -> list[SyntheticReport]:
        """One incident reported `size` times by different people.

        Members land inside 70% of the category radius -- comfortably within
        matching distance -- and are always worded differently, sometimes in
        the other language, which is the case that keyword matching fails.
        """
        reports = [
            self.make_report(
                category_key,
                latitude,
                longitude,
                cluster_id=cluster_id,
                is_cluster_seed=True,
            )
        ]

        for _ in range(size - 1):
            distance = self.rng.uniform(0, radius_m * 0.7)
            bearing = self.rng.uniform(0, 2 * math.pi)
            lat, lon = _offset_coords(latitude, longitude, distance, bearing)
            reports.append(
                self.make_report(category_key, lat, lon, cluster_id=cluster_id)
            )

        return reports


def generate_training_corpus(
    samples_per_category: int = 220,
    seed: int = 20250918,
) -> GeneratedCorpus:
    """Balanced labelled text for the classifier. Coordinates are irrelevant here."""
    generator = ReportGenerator(seed)
    corpus = GeneratedCorpus()

    for category_key in CATEGORY_KEYS:
        for _ in range(samples_per_category):
            corpus.reports.append(
                generator.make_report(category_key, 27.7172, 85.3240)
            )

    generator.rng.shuffle(corpus.reports)
    return corpus


def generate_matcher_corpus(
    category_radii: dict[str, int],
    cluster_count: int = 60,
    singleton_count: int = 120,
    area_center: tuple[float, float] = (27.7172, 85.3240),
    area_spread_m: int = 4000,
    seed: int = 99,
) -> GeneratedCorpus:
    """Clusters plus unrelated singletons, for evaluating the matcher.

    The singletons matter more than the clusters: a matcher that merges
    everything scores perfectly on clusters alone.
    """
    generator = ReportGenerator(seed)
    corpus = GeneratedCorpus()
    center_lat, center_lon = area_center

    for cluster_id in range(cluster_count):
        category_key = generator.rng.choice(CATEGORY_KEYS)
        distance = generator.rng.uniform(0, area_spread_m)
        bearing = generator.rng.uniform(0, 2 * math.pi)
        lat, lon = _offset_coords(center_lat, center_lon, distance, bearing)

        corpus.reports.extend(
            generator.make_cluster(
                category_key,
                lat,
                lon,
                radius_m=category_radii.get(category_key, 80),
                cluster_id=cluster_id,
                size=generator.rng.randint(2, 5),
            )
        )

    for _ in range(singleton_count):
        category_key = generator.rng.choice(CATEGORY_KEYS)
        distance = generator.rng.uniform(0, area_spread_m)
        bearing = generator.rng.uniform(0, 2 * math.pi)
        lat, lon = _offset_coords(center_lat, center_lon, distance, bearing)
        corpus.reports.append(generator.make_report(category_key, lat, lon))

    return corpus
