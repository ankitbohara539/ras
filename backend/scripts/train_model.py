"""Generate data, train the encoder and classifier, then evaluate both.

    python -m scripts.train_model
    python -m scripts.train_model --samples 400 --no-db

The evaluation at the end is the point. A classifier accuracy alone says
nothing about whether the matcher works, so this also measures the matcher on
held-out duplicate clusters and, crucially, on unrelated singletons.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

import numpy as np
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

from app.core.config import get_settings
from app.ml.classifier import CategoryClassifier
from app.ml.dataset import generate_matcher_corpus, generate_training_corpus
from app.ml.encoder import TfidfSvdEncoder
from app.ml.matcher import (
    MatchCandidate,
    MatchInput,
    MatchWeights,
    rank_candidates,
)
from app.ml.registry import CLASSIFIER_PATH, ENCODER_PATH, reset_cache
from app.seeds.categories import CATEGORY_SEEDS

DEFAULT_RADII = {c["key"]: c["match_radius_m"] for c in CATEGORY_SEEDS}


def load_radii(use_db: bool) -> dict[str, int]:
    """Prefer the radii actually configured in the database."""
    if not use_db:
        return DEFAULT_RADII

    try:
        from sqlalchemy import select

        from app.db.session import get_session_factory
        from app.models.category import Category

        session = get_session_factory()()
        try:
            radii = {
                c.key: c.match_radius_m for c in session.scalars(select(Category))
            }
            return radii or DEFAULT_RADII
        finally:
            session.close()
    except Exception as exc:
        print(f"  (database unavailable, using seed radii: {exc})")
        return DEFAULT_RADII


def train(samples_per_category: int, seed: int) -> tuple[TfidfSvdEncoder, CategoryClassifier, float]:
    print(f"\n1. Generating {samples_per_category} samples per category ...")
    corpus = generate_training_corpus(samples_per_category, seed=seed)
    texts = [r.text for r in corpus.reports]
    labels = [r.category_key for r in corpus.reports]

    language_counts = Counter(r.language for r in corpus.reports)
    print(f"   {len(texts)} reports  |  {dict(language_counts)}")

    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=seed, stratify=labels
    )

    print("\n2. Fitting the encoder (char 3-5 gram TF-IDF -> SVD) ...")
    encoder = TfidfSvdEncoder().fit(train_texts)
    print(f"   embedding dimension: {encoder.dim}")

    print("\n3. Training the category classifier ...")
    classifier = CategoryClassifier(encoder).fit(train_texts, train_labels)

    predictions = [p.category_key for p in classifier.predict_many(test_texts)]
    accuracy = float(np.mean([p == t for p, t in zip(predictions, test_labels, strict=True)]))

    print(f"\n   held-out accuracy: {accuracy:.1%}\n")
    print(classification_report(test_labels, predictions, zero_division=0))

    return encoder, classifier, accuracy


def evaluate_matcher(
    encoder: TfidfSvdEncoder,
    classifier: CategoryClassifier,
    radii: dict[str, int],
    weights: MatchWeights,
    min_score: float,
) -> None:
    """Measure the matcher on clusters and, more importantly, on singletons."""
    print("\n4. Evaluating the matcher on held-out clusters ...")
    corpus = generate_matcher_corpus(radii, seed=4242)

    reports = corpus.reports
    embeddings = encoder.encode([r.text for r in reports])
    predicted = classifier.predict_many([r.text for r in reports])

    # Every report is scored against everything that came before it, which is
    # what happens in production: a ticket can only match an existing one.
    hits = misses = false_merges = correct_rejections = 0

    for index, report in enumerate(reports):
        if index == 0:
            continue

        new_report = MatchInput(
            category_key=predicted[index].category_key,
            embedding=embeddings[index].tolist(),
            latitude=report.latitude,
            longitude=report.longitude,
            phashes=[],
        )

        candidates = [
            MatchCandidate(
                ticket_id=other_index,
                category_key=predicted[other_index].category_key,
                embedding=embeddings[other_index].tolist(),
                latitude=reports[other_index].latitude,
                longitude=reports[other_index].longitude,
                phashes=[],
            )
            for other_index in range(index)
        ]

        radius = radii.get(report.category_key, 80)
        results = rank_candidates(
            new_report, candidates, radius, weights, min_score=min_score, limit=1
        )

        earlier_in_cluster = report.cluster_id is not None and any(
            reports[i].cluster_id == report.cluster_id for i in range(index)
        )

        if earlier_in_cluster:
            if results and reports[results[0].ticket_id].cluster_id == report.cluster_id:
                hits += 1
            else:
                misses += 1
        else:
            if results:
                false_merges += 1
            else:
                correct_rejections += 1

    duplicates = hits + misses
    originals = false_merges + correct_rejections

    recall = hits / duplicates if duplicates else 0.0
    false_rate = false_merges / originals if originals else 0.0

    print(f"   duplicate reports    {duplicates:>5}")
    print(f"     correctly matched  {hits:>5}  ({recall:.1%} recall)")
    print(f"     missed             {misses:>5}")
    print(f"   original reports     {originals:>5}")
    print(f"     wrongly suggested  {false_merges:>5}  ({false_rate:.1%} false-suggest rate)")
    print(f"     correctly left     {correct_rejections:>5}")
    print(
        "\n   Note: a wrong suggestion costs an authority one click to dismiss."
        "\n   A missed duplicate creates a second ticket nobody links up."
        "\n   The threshold is tuned to favour recall for that reason."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the classification models.")
    parser.add_argument("--samples", type=int, default=260, help="samples per category")
    parser.add_argument("--seed", type=int, default=20250918)
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="use seed radii instead of reading the categories table",
    )
    parser.add_argument(
        "--skip-eval", action="store_true", help="train and save without evaluating"
    )
    args = parser.parse_args()

    settings = get_settings()
    weights = MatchWeights(
        category=settings.dedupe_weight_category,
        text=settings.dedupe_weight_text,
        image=settings.dedupe_weight_image,
        geo=settings.dedupe_weight_geo,
    )
    weights.validate()

    radii = load_radii(use_db=not args.no_db)
    encoder, classifier, _ = train(args.samples, args.seed)

    if not args.skip_eval:
        evaluate_matcher(encoder, classifier, radii, weights, settings.dedupe_min_score)

    print("\n5. Saving artifacts ...")
    encoder.save(ENCODER_PATH)
    classifier.save(CLASSIFIER_PATH)
    reset_cache()
    print(f"   {ENCODER_PATH}")
    print(f"   {CLASSIFIER_PATH}")

    print(
        "\nReminder: this model is trained on data this repository generates."
        "\nThe accuracy above describes the generator, not Kathmandu. It proves"
        "\nthe pipeline runs end to end -- say so when you present it."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
