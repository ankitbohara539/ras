"""Matcher behaviour.

The geo gate is the load-bearing rule here. Without it, similar wording alone
clears the threshold and the matcher suggests merging every pothole in the
municipality, so it gets the most direct test.
"""

import pytest

from app.ml.matcher import (
    MatchCandidate,
    MatchInput,
    MatchWeights,
    geo_score,
    rank_candidates,
    score_pair,
)

# Roughly 90m apart.
POINT_A = (27.7172, 85.3240)
POINT_B = (27.7180, 85.3240)
# Roughly 3km away.
POINT_FAR = (27.7440, 85.3240)

SIMILAR_VECTOR_A = [1.0, 0.0, 0.0]
SIMILAR_VECTOR_B = [0.95, 0.31, 0.0]
DIFFERENT_VECTOR = [0.0, 0.0, 1.0]


def make_input(point, category="pothole", embedding=None, phashes=None):
    return MatchInput(
        category_key=category,
        embedding=embedding,
        latitude=point[0],
        longitude=point[1],
        phashes=phashes or [],
    )


def make_candidate(
    point, category="pothole", embedding=None, phashes=None, ticket_id="T1"
):
    return MatchCandidate(
        ticket_id=ticket_id,
        category_key=category,
        embedding=embedding,
        latitude=point[0],
        longitude=point[1],
        phashes=phashes or [],
    )


class TestGeoScore:
    def test_same_point_scores_one(self):
        assert geo_score(0.0, 100.0) == 1.0

    def test_at_the_radius_scores_zero(self):
        assert geo_score(100.0, 100.0) == 0.0

    def test_halfway_scores_half(self):
        assert geo_score(50.0, 100.0) == pytest.approx(0.5)

    def test_beyond_the_radius_never_goes_negative(self):
        assert geo_score(5000.0, 100.0) == 0.0


class TestGeoGate:
    def test_identical_text_beyond_radius_is_not_suggested(self):
        """The regression that matters: similar wording must not beat distance."""
        results = rank_candidates(
            make_input(POINT_A, embedding=SIMILAR_VECTOR_A),
            [make_candidate(POINT_FAR, embedding=SIMILAR_VECTOR_A)],
            radius_m=100,
        )
        assert results == []

    def test_identical_text_within_radius_is_suggested(self):
        results = rank_candidates(
            make_input(POINT_A, embedding=SIMILAR_VECTOR_A),
            [make_candidate(POINT_B, embedding=SIMILAR_VECTOR_A)],
            radius_m=200,
        )
        assert len(results) == 1
        assert results[0].score > 0.9

    def test_a_wider_radius_admits_a_previously_gated_candidate(self):
        report = make_input(POINT_A, embedding=SIMILAR_VECTOR_A)
        candidate = make_candidate(POINT_B, embedding=SIMILAR_VECTOR_A)

        assert rank_candidates(report, [candidate], radius_m=50) == []
        assert len(rank_candidates(report, [candidate], radius_m=300)) == 1


class TestGpsSlack:
    def test_just_beyond_the_radius_is_suggested_with_slack(self):
        """Two phones at one pothole record points 68 m apart; radius is 60."""
        report = make_input(POINT_A, embedding=SIMILAR_VECTOR_A)
        candidate = make_candidate(POINT_B, embedding=SIMILAR_VECTOR_A)
        distance = score_pair(report, candidate, 1000, MatchWeights()).distance_m
        radius = distance - 8  # candidate sits 8 m outside the radius

        assert rank_candidates(report, [candidate], radius_m=radius) == []
        results = rank_candidates(report, [candidate], radius_m=radius, gps_slack_m=40)
        assert len(results) == 1
        # Outside the radius it earns nothing for distance.
        assert results[0].geo_score == 0.0

    def test_slack_does_not_reopen_far_away_matches(self):
        results = rank_candidates(
            make_input(POINT_A, embedding=SIMILAR_VECTOR_A),
            [make_candidate(POINT_FAR, embedding=SIMILAR_VECTOR_A)],
            radius_m=100,
            gps_slack_m=40,
        )
        assert results == []


class TestScoring:
    def test_different_category_scores_lower_than_same(self):
        report = make_input(POINT_A, embedding=SIMILAR_VECTOR_A)
        same = score_pair(
            report, make_candidate(POINT_B, embedding=SIMILAR_VECTOR_A), 200, MatchWeights()
        )
        different = score_pair(
            report,
            make_candidate(POINT_B, category="garbage", embedding=SIMILAR_VECTOR_A),
            200,
            MatchWeights(),
        )
        assert same.score > different.score

    def test_closer_reports_score_higher(self):
        report = make_input(POINT_A, embedding=SIMILAR_VECTOR_A)
        near = score_pair(
            report, make_candidate(POINT_A, embedding=SIMILAR_VECTOR_A), 500, MatchWeights()
        )
        far = score_pair(
            report, make_candidate(POINT_B, embedding=SIMILAR_VECTOR_A), 500, MatchWeights()
        )
        assert near.score > far.score

    def test_unrelated_text_scores_lower_than_similar_text(self):
        report = make_input(POINT_A, embedding=SIMILAR_VECTOR_A)
        similar = score_pair(
            report, make_candidate(POINT_B, embedding=SIMILAR_VECTOR_B), 200, MatchWeights()
        )
        unrelated = score_pair(
            report, make_candidate(POINT_B, embedding=DIFFERENT_VECTOR), 200, MatchWeights()
        )
        assert similar.score > unrelated.score

    def test_missing_photos_do_not_penalise_the_score(self):
        """Renormalisation: a photo-less pair must still be able to reach 1.0."""
        result = score_pair(
            make_input(POINT_A, embedding=SIMILAR_VECTOR_A),
            make_candidate(POINT_A, embedding=SIMILAR_VECTOR_A),
            200,
            MatchWeights(),
        )
        assert result.score == pytest.approx(1.0, abs=0.01)

    def test_results_are_ranked_best_first(self):
        report = make_input(POINT_A, embedding=SIMILAR_VECTOR_A)
        candidates = [
            make_candidate(POINT_B, embedding=DIFFERENT_VECTOR, ticket_id="weak"),
            make_candidate(POINT_A, embedding=SIMILAR_VECTOR_A, ticket_id="strong"),
        ]
        results = rank_candidates(report, candidates, radius_m=500, min_score=0.0)

        assert [r.ticket_id for r in results] == ["strong", "weak"]
        assert results[0].score >= results[1].score


class TestWeights:
    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            MatchWeights(category=0.5, text=0.5, image=0.5, geo=0.5).validate()

    def test_default_weights_are_valid(self):
        MatchWeights().validate()


class TestExplanation:
    def test_explanation_mentions_distance_and_category(self):
        result = score_pair(
            make_input(POINT_A, embedding=SIMILAR_VECTOR_A),
            make_candidate(POINT_B, embedding=SIMILAR_VECTOR_A),
            200,
            MatchWeights(),
        )
        explanation = result.explain()

        assert "m apart" in explanation
        assert "same category" in explanation
