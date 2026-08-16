"""Train the lightweight classifier once during the container image build."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import joblib
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.neural_network import MLPClassifier

LOG = logging.getLogger("train-model")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SENTENCE_MODEL = os.getenv(
    "SENTENCE_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
DATA_PATH = Path(os.getenv("TRAINING_DATA_PATH", "data/muestra_nlp_sample.jsonl"))
MODEL_PATH = Path(os.getenv("MODEL_OUTPUT_PATH", "model/classifier.joblib"))
METADATA_PATH = Path(os.getenv("MODEL_METADATA_PATH", "model/metadata.json"))
TRAINING_ROWS = int(os.getenv("TRAINING_ROWS", "2000"))
MAX_CLASSES = int(os.getenv("MAX_CLASSES", "20"))


def load_training_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Training data not found: {DATA_PATH}")

    if DATA_PATH.suffix == ".jsonl":
        data = pd.read_json(DATA_PATH, lines=True)
    else:
        data = pd.read_csv(
            DATA_PATH,
            usecols=["Issue", "Consumer complaint narrative"],
            nrows=TRAINING_ROWS,
        )

    data = data.dropna(subset=["Issue", "Consumer complaint narrative"]).head(TRAINING_ROWS)
    top_classes = data["Issue"].value_counts().head(MAX_CLASSES).index
    data = data[data["Issue"].isin(top_classes)].copy()
    data["clean_text"] = (
        data["Consumer complaint narrative"].astype(str).str.replace("XXXX", "[MASK]", regex=False)
    )

    if data["Issue"].nunique() < 2:
        raise ValueError("At least two Issue classes are required to train the classifier")

    return data


def main() -> None:
    data = load_training_data()
    LOG.info("Training with %s rows and %s classes", len(data), data["Issue"].nunique())

    encoder = SentenceTransformer(SENTENCE_MODEL, device="cpu")
    features = encoder.encode(
        data["clean_text"].tolist(),
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    classifier = MLPClassifier(
        hidden_layer_sizes=(128,),
        activation="relu",
        max_iter=300,
        random_state=42,
    )
    classifier.fit(features, data["Issue"].tolist())

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(classifier, MODEL_PATH, compress=3)

    metadata = {
        "sentence_model": SENTENCE_MODEL,
        "training_rows": int(len(data)),
        "classes": sorted(map(str, classifier.classes_.tolist())),
    }
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.info("Model saved to %s", MODEL_PATH)


if __name__ == "__main__":
    main()
