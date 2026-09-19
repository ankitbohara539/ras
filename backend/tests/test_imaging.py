"""Perceptual hashing, and the type coercion the database depends on."""

import io

from PIL import Image, ImageDraw

from app.ml.imaging import (
    MAX_MEANINGFUL_DISTANCE,
    best_phash_similarity,
    compute_phash,
    hamming_distance,
    phash_similarity,
)
from app.ml.matcher import MatchCandidate, MatchInput, MatchWeights, score_pair


def make_image(shade: int = 108, shift: int = 0) -> bytes:
    image = Image.new("RGB", (320, 240), (shade, shade, shade))
    draw = ImageDraw.Draw(image)
    draw.ellipse([90 + shift, 80 + shift, 220 + shift, 160 + shift], fill=(30, 28, 25))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


class TestHashing:
    def test_identical_images_hash_identically(self) -> None:
        payload = make_image()
        assert compute_phash(payload) == compute_phash(payload)

    def test_recompression_barely_moves_the_hash(self) -> None:
        """The property the image signal actually relies on.

        Not bit-identical: heavy recompression of a low-detail image can shift
        a bit or two. What matters is that it stays far inside the threshold,
        so a re-sent photo still reads as the same photo.
        """
        original = make_image()
        reopened = Image.open(io.BytesIO(original))

        buffer = io.BytesIO()
        reopened.convert("RGB").save(buffer, format="JPEG", quality=40)

        distance = hamming_distance(
            compute_phash(original), compute_phash(buffer.getvalue())
        )

        assert distance <= 5, f"recompression moved the hash by {distance} bits"
        assert phash_similarity(
            compute_phash(original), compute_phash(buffer.getvalue())
        ) > 0.75

    def test_non_image_bytes_return_none(self) -> None:
        assert compute_phash(b"this is not an image") is None

    def test_missing_hash_scores_zero_not_none(self) -> None:
        """A report without a photo must not inflate the blend."""
        assert phash_similarity(None, "abcdef0123456789") == 0.0
        assert phash_similarity("abcdef0123456789", None) == 0.0
        assert phash_similarity(None, None) == 0.0

    def test_identical_hashes_score_one(self) -> None:
        digest = compute_phash(make_image())
        assert phash_similarity(digest, digest) == 1.0

    def test_best_match_wins_across_photo_sets(self) -> None:
        a = compute_phash(make_image(shade=108))
        b = compute_phash(make_image(shade=200))

        assert best_phash_similarity([b, a], [a]) == 1.0
        assert best_phash_similarity([], [a]) == 0.0


class TestNumpyCoercion:
    """These scores are written straight to Postgres.

    imagehash subtraction yields a numpy integer, which turns the blended
    score into np.float64. psycopg2 has no adapter for it and renders it as
    the literal text "np.float64(1.0)", producing invalid SQL. The bug only
    appears when the image signal is non-zero, so it hides easily.
    """

    def test_hamming_distance_is_a_builtin_int(self) -> None:
        digest = compute_phash(make_image())
        distance = hamming_distance(digest, digest)

        assert distance == 0
        assert type(distance) is int

    def test_similarity_is_a_builtin_float(self) -> None:
        digest = compute_phash(make_image())
        assert type(phash_similarity(digest, digest)) is float

    def test_match_scores_are_all_builtin_floats(self) -> None:
        digest = compute_phash(make_image())

        result = score_pair(
            MatchInput(
                category_key="pothole",
                embedding=[1.0, 0.0],
                latitude=27.7172,
                longitude=85.3240,
                phashes=[digest],
            ),
            MatchCandidate(
                ticket_id="T1",
                category_key="pothole",
                embedding=[1.0, 0.0],
                latitude=27.7172,
                longitude=85.3240,
                phashes=[digest],
            ),
            radius_m=100,
            weights=MatchWeights(),
        )

        for field in (
            result.score,
            result.category_score,
            result.text_score,
            result.image_score,
            result.geo_score,
            result.distance_m,
        ):
            assert type(field) is float, f"{field!r} is {type(field)}, not float"


class TestThreshold:
    def test_distance_beyond_the_threshold_scores_zero(self) -> None:
        near = compute_phash(make_image(shade=108))
        far = compute_phash(make_image(shade=240, shift=60))

        if hamming_distance(near, far) > MAX_MEANINGFUL_DISTANCE:
            assert phash_similarity(near, far) == 0.0
