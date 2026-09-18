"""Text encoding.

`TextEncoder` is the seam. Today it is TF-IDF over character n-grams reduced
with SVD -- sklearn only, ~50MB installed, and character n-grams handle
Devanagari and Latin script in one vectoriser with no language detection and
no tokeniser that knows Nepali.

Swapping in a multilingual sentence-transformer later means writing one more
subclass; nothing downstream changes because everything consumes the
EMBEDDING_DIM-length unit vector this produces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import Normalizer

from app.models.ticket import EMBEDDING_DIM


class TextEncoder(ABC):
    """Turns report text into a fixed-length unit vector."""

    dim: int = EMBEDDING_DIM

    @abstractmethod
    def fit(self, texts: list[str]) -> "TextEncoder": ...

    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray: ...

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0].tolist()


class TfidfSvdEncoder(TextEncoder):
    """Character n-gram TF-IDF, reduced to a dense vector by SVD.

    Character n-grams rather than words on purpose: they survive the typos and
    the Roman-Nepali code mixing that word tokens break on, and they need no
    stopword list for Nepali (there isn't a good one).
    """

    def __init__(self, dim: int = EMBEDDING_DIM, random_state: int = 42) -> None:
        self.dim = dim
        self.random_state = random_state
        self.pipeline: Pipeline | None = None

    def _build(self, n_features: int) -> Pipeline:
        # SVD cannot produce more components than the vocabulary supports.
        n_components = min(self.dim, max(2, n_features - 1))

        return Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        analyzer="char_wb",
                        ngram_range=(3, 5),
                        min_df=2,
                        max_features=60_000,
                        sublinear_tf=True,
                        lowercase=True,
                    ),
                ),
                (
                    "svd",
                    TruncatedSVD(
                        n_components=n_components,
                        random_state=self.random_state,
                    ),
                ),
                # Unit length, so cosine similarity is just a dot product.
                ("normalize", Normalizer(copy=False)),
            ]
        )

    def fit(self, texts: list[str]) -> "TfidfSvdEncoder":
        probe = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=60_000
        )
        n_features = probe.fit_transform(texts).shape[1]

        self.pipeline = self._build(n_features)
        self.pipeline.fit(texts)
        self.dim = self.pipeline.named_steps["svd"].n_components
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        if self.pipeline is None:
            raise RuntimeError("Encoder is not fitted. Run scripts/train_model.py.")

        vectors = self.pipeline.transform(texts)
        return self._pad(np.asarray(vectors, dtype=np.float32))

    def _pad(self, vectors: np.ndarray) -> np.ndarray:
        """Pad to EMBEDDING_DIM so the database column always matches.

        A small corpus can yield fewer SVD components than the column width;
        zero-padding keeps cosine similarity unchanged.
        """
        if vectors.shape[1] == EMBEDDING_DIM:
            return vectors

        padded = np.zeros((vectors.shape[0], EMBEDDING_DIM), dtype=np.float32)
        width = min(vectors.shape[1], EMBEDDING_DIM)
        padded[:, :width] = vectors[:, :width]
        return padded

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": self.pipeline, "dim": self.dim}, path)

    @classmethod
    def load(cls, path: Path) -> "TfidfSvdEncoder":
        payload = joblib.load(path)
        encoder = cls(dim=payload["dim"])
        encoder.pipeline = payload["pipeline"]
        return encoder


def cosine_similarity(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    """Cosine similarity, clamped to [0, 1].

    SVD output can be slightly negative; a negative "similarity" would make the
    weighted blend behave oddly, so the floor is zero.
    """
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)

    norm = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if norm == 0.0:
        return 0.0

    return max(0.0, min(1.0, float(np.dot(va, vb)) / norm))
