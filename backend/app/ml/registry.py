"""Loads the trained artifacts once per process.

Kept separate from the API so the model can be exercised from a script with no
FastAPI or database involved.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.ml.classifier import CategoryClassifier
from app.ml.encoder import TfidfSvdEncoder

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ENCODER_PATH = ARTIFACT_DIR / "encoder.joblib"
CLASSIFIER_PATH = ARTIFACT_DIR / "classifier.joblib"


class ModelsNotTrained(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "No trained model found. Run:  python -m scripts.train_model"
        )


def artifacts_exist() -> bool:
    return ENCODER_PATH.exists() and CLASSIFIER_PATH.exists()


@lru_cache
def get_encoder() -> TfidfSvdEncoder:
    if not ENCODER_PATH.exists():
        raise ModelsNotTrained
    return TfidfSvdEncoder.load(ENCODER_PATH)


@lru_cache
def get_classifier() -> CategoryClassifier:
    if not CLASSIFIER_PATH.exists():
        raise ModelsNotTrained
    return CategoryClassifier(get_encoder()).load(CLASSIFIER_PATH)


def reset_cache() -> None:
    """Drop cached models so a retrain takes effect without a restart."""
    get_encoder.cache_clear()
    get_classifier.cache_clear()
