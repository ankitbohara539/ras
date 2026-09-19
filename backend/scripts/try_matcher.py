"""Show the matcher reasoning on a worked scenario.

    python -m scripts.try_matcher

Four reports already exist near Baneshwor. A fifth arrives, in Nepali,
describing the same pothole as the first. The output is what an authority
would see in the merge-review queue.
"""

from __future__ import annotations

import sys

from app.core.config import get_settings
from app.ml.matcher import MatchCandidate, MatchInput, MatchWeights, rank_candidates
from app.ml.registry import ModelsNotTrained, get_classifier, get_encoder
from app.seeds.categories import CATEGORY_SEEDS

RADII = {c["key"]: c["match_radius_m"] for c in CATEGORY_SEEDS}

EXISTING = [
    (
        "KTM-10-000141",
        "There is a big pothole on the road near the bus stop. "
        "It has been there for the last three days.",
        27.6915,
        85.3357,
    ),
    (
        "KTM-10-000142",
        "Garbage has been piling up in front of the school since last week.",
        27.6916,
        85.3358,
    ),
    (
        "KTM-10-000143",
        "The street light beside the temple has not been working for two weeks.",
        27.6918,
        85.3361,
    ),
    (
        "KTM-10-000144",
        "There is a big pothole on the road near the college gate.",
        27.7300,
        85.3400,  # same issue, ~4.5km away: must NOT be suggested
    ),
]

NEW_REPORT = (
    "बस स्टप नजिक सडकमा ठूलो खाल्डो छ। मोटरसाइकल दैनिक लड्छन्। "
    "कृपया हेरिदिनुहोस्।",
    27.6915,
    85.3358,
)


def main() -> int:
    try:
        encoder = get_encoder()
        classifier = get_classifier()
    except ModelsNotTrained as exc:
        print(exc)
        return 1

    settings = get_settings()
    weights = MatchWeights(
        category=settings.dedupe_weight_category,
        text=settings.dedupe_weight_text,
        image=settings.dedupe_weight_image,
        geo=settings.dedupe_weight_geo,
    )

    new_text, new_lat, new_lon = NEW_REPORT
    prediction = classifier.predict(new_text)
    radius = RADII.get(prediction.category_key, 80)

    print("NEW REPORT")
    print(f"  {new_text}")
    print(f"  at {new_lat}, {new_lon}")
    print(
        f"\n  classified as : {prediction.category_key} "
        f"({prediction.confidence:.0%} confidence)"
    )
    runner_up = sorted(prediction.scores.items(), key=lambda kv: -kv[1])[1]
    print(f"  runner-up     : {runner_up[0]} ({runner_up[1]:.0%})")
    print(f"  match radius  : {radius}m\n")

    candidates = []
    for code, text, lat, lon in EXISTING:
        candidate_prediction = classifier.predict(text)
        candidates.append(
            MatchCandidate(
                ticket_id=code,
                category_key=candidate_prediction.category_key,
                embedding=encoder.encode_one(text),
                latitude=lat,
                longitude=lon,
                phashes=[],
            )
        )

    results = rank_candidates(
        MatchInput(
            category_key=prediction.category_key,
            embedding=encoder.encode_one(new_text),
            latitude=new_lat,
            longitude=new_lon,
            phashes=[],
        ),
        candidates,
        radius_m=radius,
        weights=weights,
        min_score=settings.dedupe_min_score,
        limit=settings.dedupe_max_candidates,
    )

    print("EXISTING TICKETS NEARBY")
    for code, text, _, _ in EXISTING:
        print(f"  {code}  {text[:62]}")

    print("\nSUGGESTED DUPLICATES (authority decides; nothing is merged)")
    if not results:
        print("  none above threshold -- this becomes a new parent ticket")

    for result in results:
        print(f"\n  {result.ticket_id}   score {result.score:.2f}")
        print(f"    {result.explain()}")
        print(
            f"    category {result.category_score:.2f} | "
            f"text {result.text_score:.2f} | "
            f"image {result.image_score:.2f} | "
            f"geo {result.geo_score:.2f}"
        )

    suggested = {r.ticket_id for r in results}
    print("\nNOT SUGGESTED")
    for code, _, _, _ in EXISTING:
        if code not in suggested:
            reason = (
                "beyond the match radius"
                if code == "KTM-10-000144"
                else "different category or too dissimilar"
            )
            print(f"  {code}  -- {reason}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
