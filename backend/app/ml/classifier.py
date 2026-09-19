"""Category classifier.

A logistic regression head over the same encoder the matcher uses, so the
model downloads and fits once and serves both jobs. Logistic regression rather
than LinearSVC because the blend needs a calibrated probability, not just a
label -- `category_confidence` is shown to the authority and feeds the score.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from app.ml.encoder import TextEncoder


@dataclass
class Prediction:
    category_key: str
    confidence: float
    # Full distribution, so the UI can offer the runner-up as a correction.
    scores: dict[str, float]

    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.55


class CategoryClassifier:
    def __init__(self, encoder: TextEncoder) -> None:
        self.encoder = encoder
        self.model: LogisticRegression | None = None
        self.classes: list[str] = []

    def fit(self, texts: list[str], labels: list[str]) -> "CategoryClassifier":
        features = self.encoder.encode(texts)

        self.model = LogisticRegression(
            max_iter=2000,
            C=8.0,
            class_weight="balanced",
        )
        self.model.fit(features, labels)
        self.classes = list(self.model.classes_)
        return self

    def predict(self, text: str) -> Prediction:
        return self.predict_many([text])[0]

    def predict_many(self, texts: list[str]) -> list[Prediction]:
        if self.model is None:
            raise RuntimeError("Classifier is not fitted. Run scripts/train_model.py.")

        features = self.encoder.encode(texts)
        probabilities = self.model.predict_proba(features)

        predictions = []
        for row in probabilities:
            best = int(np.argmax(row))
            predictions.append(
                Prediction(
                    category_key=self.classes[best],
                    confidence=float(row[best]),
                    scores={
                        cls: float(score)
                        for cls, score in zip(self.classes, row, strict=True)
                    },
                )
            )
        return predictions

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "classes": self.classes}, path)

    def load(self, path: Path) -> "CategoryClassifier":
        payload = joblib.load(path)
        self.model = payload["model"]
        self.classes = payload["classes"]
        return self
